#!/usr/bin/env python3
"""Fit and evaluate the preregistered hard-cell pairwise candidate ranker."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import opportunity_table, read_candidates
except ModuleNotFoundError:  # Direct execution from scripts/.
    from terminal_grounded_critic import opportunity_table, read_candidates


SCHEMA_VERSION = 1
FEATURES = (
    "candidate_parallel_value",
    "candidate_autoregressive_value",
    "autoregressive_value_delta",
    "candidate_first_action_l1",
    "candidate_action_chunk_l1",
    "candidate_action_chunk_l2",
    "candidate_action_consensus_first",
    "candidate_action_consensus_chunk",
    "latent_action_copy_std_mean",
    "latent_action_copy_std_max",
    "latent_action_first_step_copy_l2_std",
    "latent_future_proprio_copy_std_mean",
    "latent_future_proprio_copy_std_max",
    "latent_value_element_std_mean",
    "latent_value_element_std_max",
    "autoregressive_latent_future_proprio_copy_std_mean",
    "autoregressive_latent_future_proprio_copy_std_max",
    "autoregressive_latent_value_element_std_mean",
    "autoregressive_latent_value_element_std_max",
    "autoregressive_future_proprio_l2",
)
PARALLEL_PROPRIO = tuple(
    f"candidate_predicted_future_proprio_d{dimension}" for dimension in range(9)
)
AUTOREGRESSIVE_PROPRIO = tuple(
    f"candidate_autoregressive_predicted_future_proprio_d{dimension}"
    for dimension in range(9)
)
ALPHAS = (0.1, 1.0, 10.0, 100.0)
KAPPAS = (0.0, 0.5, 1.0, 1.5)
BOOTSTRAP_MEMBERS = 32
BOOTSTRAP_SEED = 2_026_08_30


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sign_pvalue(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(rescues, harms) + 1))
    return float(min(1.0, 2.0 * tail / (2**discordant)))


def prepare_candidates(paths: Sequence[Path]) -> pd.DataFrame:
    frame = read_candidates(paths, require_features=False)
    frame = frame.loc[
        frame["factor"].isin(["Object", "Position"])
        & pd.to_numeric(frame["task_id"], errors="coerce").eq(0)
        & pd.to_numeric(frame.get("query_idx", -1), errors="coerce").eq(0)
        & pd.to_numeric(frame["candidate_idx"], errors="coerce").lt(8)
    ].copy()
    if frame.empty:
        raise ValueError("No Object/Position task0 q0 K8 candidates found")
    if "experiment_split" not in frame:
        raise ValueError("Candidates are missing experiment_split")
    if frame["factor"].eq("Position").any():
        position_cases = frame.loc[frame["factor"].eq("Position"), "case_id"].astype(str)
        if not position_cases.str.contains("y0p3|y0.3", case=False, regex=True).all():
            raise ValueError("Position candidates include a perturbation other than y0.3")

    required = {
        *FEATURES,
        *PARALLEL_PROPRIO,
        *AUTOREGRESSIVE_PROPRIO,
        "candidate_value",
        "candidate_idx",
        "terminal_success_bool",
        "terminal_utility_v1",
        "terminal_adverse_event",
    }
    derived = {"autoregressive_value_delta", "autoregressive_future_proprio_l2"}
    missing = sorted((required - derived) - set(frame.columns))
    if missing:
        raise ValueError(f"Candidate tables are missing pairwise features: {missing}")

    frame["candidate_parallel_value"] = pd.to_numeric(
        frame["candidate_parallel_value"], errors="coerce"
    )
    frame["candidate_autoregressive_value"] = pd.to_numeric(
        frame["candidate_autoregressive_value"], errors="coerce"
    )
    alias_error = np.abs(
        pd.to_numeric(frame["candidate_value"], errors="coerce")
        - frame["candidate_parallel_value"]
    )
    if not np.isfinite(alias_error).all() or float(alias_error.max()) > 1e-12:
        raise ValueError("candidate_value is not an exact parallel-value alias")
    frame["autoregressive_value_delta"] = (
        frame["candidate_autoregressive_value"] - frame["candidate_parallel_value"]
    )
    parallel = frame.loc[:, list(PARALLEL_PROPRIO)].apply(pd.to_numeric, errors="coerce")
    autoregressive = frame.loc[:, list(AUTOREGRESSIVE_PROPRIO)].apply(
        pd.to_numeric, errors="coerce"
    )
    frame["autoregressive_future_proprio_l2"] = np.linalg.norm(
        autoregressive.to_numpy(dtype=float) - parallel.to_numpy(dtype=float), axis=1
    )
    frame.loc[:, list(FEATURES)] = frame.loc[:, list(FEATURES)].apply(
        pd.to_numeric, errors="coerce"
    )
    if not np.isfinite(frame.loc[:, list(FEATURES)].to_numpy(dtype=float)).all():
        raise ValueError("Pairwise online features contain non-finite values")

    key = ["factor", "task_id", "init_state_id", "query_idx", "candidate_idx"]
    if frame.duplicated(key).any():
        duplicates = frame.loc[frame.duplicated(key, keep=False), key]
        raise ValueError(f"Duplicate candidate keys:\n{duplicates.to_string(index=False)}")
    counts = frame.groupby("analysis_snapshot_id")["candidate_idx"].nunique()
    if not counts.eq(8).all():
        raise ValueError(f"Every exact state must contain K8 candidates: {counts.to_dict()}")
    return frame.sort_values(["factor", "init_state_id", "candidate_idx"]).reset_index(
        drop=True
    )


def _within_state_z(frame: pd.DataFrame) -> np.ndarray:
    numeric = frame.loc[:, list(FEATURES)].to_numpy(dtype=np.float64)
    result = np.empty_like(numeric)
    for _snapshot, indices in frame.groupby("analysis_snapshot_id", sort=False).groups.items():
        positions = np.asarray(list(indices), dtype=int)
        values = numeric[positions]
        mean = values.mean(axis=0)
        std = values.std(axis=0, ddof=0)
        std[std < 1e-8] = 1.0
        result[positions] = (values - mean) / std
    return result


def _pair_dataset(
    frame: pd.DataFrame, z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows: list[np.ndarray] = []
    labels: list[float] = []
    groups: list[str] = []
    for _snapshot, state in frame.groupby("analysis_snapshot_id", sort=False):
        positions = state.index.to_numpy(dtype=int)
        utility = state["terminal_utility_v1"].to_numpy(dtype=float)
        group_name = str(state["independent_group"].iloc[0])
        for left in range(len(state)):
            for right in range(left + 1, len(state)):
                if abs(utility[left] - utility[right]) <= 1e-12:
                    continue
                if utility[left] > utility[right]:
                    difference = z[positions[left]] - z[positions[right]]
                else:
                    difference = z[positions[right]] - z[positions[left]]
                rows.extend([difference, -difference])
                labels.extend([1.0, 0.0])
                groups.extend([group_name, group_name])
    if not rows:
        raise ValueError("No non-tied utility pairs are available")
    return np.stack(rows), np.asarray(labels), np.asarray(groups, dtype=str)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _fit_logistic(
    x: np.ndarray,
    y: np.ndarray,
    *,
    alpha: float,
    max_iterations: int = 100,
) -> np.ndarray:
    coefficient = np.zeros(x.shape[1], dtype=np.float64)
    identity = np.eye(x.shape[1], dtype=np.float64)
    for _iteration in range(max_iterations):
        probability = _sigmoid(x @ coefficient)
        weight = np.maximum(probability * (1.0 - probability), 1e-8)
        gradient = x.T @ (probability - y) + alpha * coefficient
        hessian = x.T @ (weight[:, None] * x) + alpha * identity
        step = np.linalg.solve(hessian, gradient)
        coefficient -= step
        if float(np.max(np.abs(step))) < 1e-9:
            break
    return coefficient


def _ordering_accuracy(
    frame: pd.DataFrame, scores: np.ndarray, *, target: str
) -> tuple[float, int]:
    state_scores: list[float] = []
    comparisons = 0
    for _snapshot, state in frame.groupby("analysis_snapshot_id", sort=False):
        positions = state.index.to_numpy(dtype=int)
        labels = state[target].to_numpy(dtype=float)
        values = scores[positions]
        correct = []
        for left in range(len(state)):
            for right in range(left + 1, len(state)):
                if abs(labels[left] - labels[right]) <= 1e-12:
                    continue
                sign = 1.0 if labels[left] > labels[right] else -1.0
                margin = sign * (values[left] - values[right])
                correct.append(float(margin > 0.0) + 0.5 * float(margin == 0.0))
        if correct:
            state_scores.append(float(np.mean(correct)))
            comparisons += len(correct)
    return (float(np.mean(state_scores)) if state_scores else float("nan"), comparisons)


def _cross_validate_alpha(frame: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    frame = frame.reset_index(drop=True)
    z = _within_state_z(frame)
    x_pairs, y_pairs, pair_groups = _pair_dataset(frame, z)
    groups = sorted(frame["independent_group"].unique().tolist())
    rows: list[dict[str, object]] = []
    for alpha in ALPHAS:
        fold_scores = []
        fold_pairs = 0
        for held_group in groups:
            train_pair_mask = pair_groups != held_group
            held_row_mask = frame["independent_group"].eq(held_group).to_numpy()
            if not train_pair_mask.any() or not held_row_mask.any():
                continue
            coefficient = _fit_logistic(
                x_pairs[train_pair_mask], y_pairs[train_pair_mask], alpha=alpha
            )
            held = frame.loc[held_row_mask].reset_index(drop=True)
            held_scores = _within_state_z(held) @ coefficient
            accuracy, pairs = _ordering_accuracy(
                held, held_scores, target="terminal_utility_v1"
            )
            if np.isfinite(accuracy):
                fold_scores.append(accuracy)
                fold_pairs += pairs
        rows.append(
            {
                "alpha": alpha,
                "groups_scored": len(fold_scores),
                "utility_pairwise_accuracy": (
                    float(np.mean(fold_scores)) if fold_scores else np.nan
                ),
                "utility_pairs": int(fold_pairs),
            }
        )
    result = pd.DataFrame(rows)
    finite = result.loc[result["utility_pairwise_accuracy"].notna()]
    if finite.empty:
        raise ValueError("Grouped CV has no non-tied held-out groups")
    best_accuracy = float(finite["utility_pairwise_accuracy"].max())
    best_alpha = float(
        finite.loc[
            np.isclose(finite["utility_pairwise_accuracy"], best_accuracy), "alpha"
        ].max()
    )
    result["selected"] = result["alpha"].eq(best_alpha)
    return best_alpha, result


def _bootstrap_coefficients(
    frame: pd.DataFrame,
    *,
    alpha: float,
    members: int,
    seed: int,
) -> tuple[np.ndarray, int]:
    frame = frame.reset_index(drop=True)
    z = _within_state_z(frame)
    x_pairs, y_pairs, pair_groups = _pair_dataset(frame, z)
    unique_groups = np.unique(pair_groups)
    rng = np.random.default_rng(seed)
    coefficients = []
    for _member in range(members):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        sampled_indices = np.concatenate(
            [np.flatnonzero(pair_groups == group) for group in sampled_groups]
        )
        coefficients.append(
            _fit_logistic(x_pairs[sampled_indices], y_pairs[sampled_indices], alpha=alpha)
        )
    return np.stack(coefficients), int(len(x_pairs) // 2)


def _score_members(frame: pd.DataFrame, model: Mapping[str, Any]) -> np.ndarray:
    result = np.zeros((len(frame), int(model["bootstrap_members"])), dtype=np.float64)
    for factor, scoped in frame.groupby("factor", sort=False):
        parameters = model["factor_heads"].get(str(factor))
        if parameters is None:
            raise ValueError(f"Frozen model has no head for factor {factor}")
        positions = scoped.index.to_numpy(dtype=int)
        local = scoped.reset_index(drop=True)
        z = _within_state_z(local)
        coefficients = np.asarray(parameters["coefficients"], dtype=np.float64)
        result[positions] = z @ coefficients.T
    return result


def select_candidates(
    frame: pd.DataFrame,
    model: Mapping[str, Any],
    *,
    kappa_override: Mapping[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = frame.reset_index(drop=True).copy()
    member_scores = _score_members(frame, model)
    frame["ranker_score_mean"] = member_scores.mean(axis=1)
    frame["ranker_score_std"] = member_scores.std(axis=1, ddof=0)
    states: list[dict[str, object]] = []
    for snapshot, state in frame.groupby("analysis_snapshot_id", sort=False):
        positions = state.index.to_numpy(dtype=int)
        factor = str(state["factor"].iloc[0])
        values = state["candidate_parallel_value"].to_numpy(dtype=float)
        autoregressive_values = state["candidate_autoregressive_value"].to_numpy(
            dtype=float
        )
        means = member_scores[positions].mean(axis=1)
        baseline_local = int(np.argmax(values))
        autoregressive_local = int(np.argmax(autoregressive_values))
        ranker_local = int(np.argmax(means))
        baseline_position = int(positions[baseline_local])
        ranker_position = int(positions[ranker_local])
        margin_members = (
            member_scores[ranker_position] - member_scores[baseline_position]
        )
        kappa = float(
            (kappa_override or {}).get(
                factor, model["factor_heads"][factor]["calibrated_kappa"]
            )
        )
        margin_mean = float(margin_members.mean())
        margin_std = float(margin_members.std(ddof=0))
        margin_lcb = margin_mean - kappa * margin_std
        switch = bool(ranker_local != baseline_local and margin_lcb > 0.0)
        selected_local = ranker_local if switch else baseline_local
        oracle_local = int(np.argmax(state["terminal_utility_v1"].to_numpy(dtype=float)))
        success = state["terminal_success_bool"].to_numpy(dtype=bool)
        adverse = state["terminal_adverse_event"].to_numpy(dtype=float)
        utility = state["terminal_utility_v1"].to_numpy(dtype=float)
        states.append(
            {
                "analysis_snapshot_id": snapshot,
                "factor": factor,
                "suite": str(state["suite"].iloc[0]),
                "task_id": int(state["task_id"].iloc[0]),
                "init_state_id": int(state["init_state_id"].iloc[0]),
                "query_idx": int(state["query_idx"].iloc[0]),
                "independent_group": str(state["independent_group"].iloc[0]),
                "mixed_pool": bool(success.any() and not success.all()),
                "oracle_success": bool(success.any()),
                "maxv_candidate_idx": int(state.iloc[baseline_local]["candidate_idx"]),
                "autoregressive_candidate_idx": int(
                    state.iloc[autoregressive_local]["candidate_idx"]
                ),
                "ranker_candidate_idx": int(state.iloc[ranker_local]["candidate_idx"]),
                "selected_candidate_idx": int(state.iloc[selected_local]["candidate_idx"]),
                "oracle_candidate_idx": int(state.iloc[oracle_local]["candidate_idx"]),
                "calibrated_kappa": kappa,
                "ranker_margin_mean": margin_mean,
                "ranker_margin_std": margin_std,
                "ranker_margin_lcb": margin_lcb,
                "switched": switch,
                "maxv_success": bool(success[baseline_local]),
                "autoregressive_success": bool(success[autoregressive_local]),
                "ranker_success": bool(success[ranker_local]),
                "selected_success": bool(success[selected_local]),
                "maxv_utility": float(utility[baseline_local]),
                "autoregressive_utility": float(utility[autoregressive_local]),
                "ranker_utility": float(utility[ranker_local]),
                "selected_utility": float(utility[selected_local]),
                "oracle_utility": float(utility[oracle_local]),
                "maxv_adverse": float(adverse[baseline_local]),
                "autoregressive_adverse": float(adverse[autoregressive_local]),
                "ranker_adverse": float(adverse[ranker_local]),
                "selected_adverse": float(adverse[selected_local]),
                "rescue": bool(not success[baseline_local] and success[selected_local]),
                "harm": bool(success[baseline_local] and not success[selected_local]),
            }
        )
    return frame, pd.DataFrame(states)


def _summarize_states(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scopes = [(factor, group) for factor, group in states.groupby("factor", sort=True)]
    scopes.append(("All", states))
    for factor, group in scopes:
        mixed = group.loc[group["mixed_pool"]]
        switches = group.loc[group["switched"]]
        rows.append(
            {
                "factor": factor,
                "states": int(len(group)),
                "mixed_states": int(len(mixed)),
                "maxv_sr": float(group["maxv_success"].mean()),
                "autoregressive_sr": float(group["autoregressive_success"].mean()),
                "ranker_sr": float(group["ranker_success"].mean()),
                "selected_sr": float(group["selected_success"].mean()),
                "oracle_sr": float(group["oracle_success"].mean()),
                "mixed_maxv_top1": (
                    float(mixed["maxv_success"].mean()) if len(mixed) else np.nan
                ),
                "mixed_autoregressive_top1": (
                    float(mixed["autoregressive_success"].mean())
                    if len(mixed)
                    else np.nan
                ),
                "mixed_ranker_top1": (
                    float(mixed["ranker_success"].mean()) if len(mixed) else np.nan
                ),
                "mixed_selected_top1": (
                    float(mixed["selected_success"].mean()) if len(mixed) else np.nan
                ),
                "mixed_selected_delta_states": int(
                    mixed["selected_success"].sum() - mixed["maxv_success"].sum()
                ),
                "selected_utility_delta": float(
                    (group["selected_utility"] - group["maxv_utility"]).mean()
                ),
                "switches": int(group["switched"].sum()),
                "switch_precision": (
                    float(switches["rescue"].mean()) if len(switches) else np.nan
                ),
                "rescues": int(group["rescue"].sum()),
                "harms": int(group["harm"].sum()),
                "adverse_delta_events": float(
                    (group["selected_adverse"] - group["maxv_adverse"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _grouped_bootstrap_intervals(
    states: pd.DataFrame, *, draws: int = 5000, seed: int = BOOTSTRAP_SEED
) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(seed)
    scopes = [(factor, group) for factor, group in states.groupby("factor", sort=True)]
    scopes.append(("All", states))
    for factor, scoped in scopes:
        grouped = (
            scoped.assign(
                raw_success_delta=(
                    scoped["ranker_success"].astype(float)
                    - scoped["maxv_success"].astype(float)
                ),
                selected_success_delta=(
                    scoped["selected_success"].astype(float)
                    - scoped["maxv_success"].astype(float)
                ),
                selected_utility_delta=(
                    scoped["selected_utility"] - scoped["maxv_utility"]
                ),
                selected_adverse_delta=(
                    scoped["selected_adverse"] - scoped["maxv_adverse"]
                ),
            )
            .groupby("independent_group")[[
                "raw_success_delta",
                "selected_success_delta",
                "selected_utility_delta",
                "selected_adverse_delta",
            ]]
            .mean()
        )
        values = grouped.to_numpy(dtype=float)
        sampled = rng.integers(0, len(values), size=(draws, len(values)))
        distributions = values[sampled].mean(axis=1)
        for index, metric in enumerate(grouped.columns):
            distribution = distributions[:, index]
            rows.append(
                {
                    "factor": factor,
                    "metric": metric,
                    "groups": int(len(grouped)),
                    "point": float(values[:, index].mean()),
                    "ci_low": float(np.quantile(distribution, 0.025)),
                    "ci_high": float(np.quantile(distribution, 0.975)),
                    "probability_positive": float(np.mean(distribution > 0.0)),
                }
            )
    return pd.DataFrame(rows)


def _opportunity_summary(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    states = opportunity_table(frame)
    rows = []
    for factor, group in list(states.groupby("factor", sort=True)) + [("All", states)]:
        rows.append(
            {
                "factor": factor,
                "states": int(len(group)),
                "mixed_states": int(group["outcome_heterogeneous"].sum()),
                "success_rescues": int(group["success_rescue"].sum()),
                "maxv_sr": float(group["maxv_success"].mean()),
                "oracle_sr": float(group["oracle_success"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    combined = summary.loc[summary["factor"].eq("All")].iloc[0]
    factors = summary.loc[summary["factor"].ne("All")]
    gate = bool(
        int(combined["mixed_states"]) >= 8
        and int(combined["success_rescues"]) >= 3
        and factors["mixed_states"].ge(3).all()
    )
    return states, summary, gate


def _choose_kappas(
    calibration: pd.DataFrame, model: Mapping[str, Any]
) -> tuple[dict[str, float], pd.DataFrame]:
    rows = []
    selected: dict[str, float] = {}
    for factor, factor_frame in calibration.groupby("factor", sort=True):
        candidates = []
        for kappa in KAPPAS:
            _scored, states = select_candidates(
                factor_frame.reset_index(drop=True),
                model,
                kappa_override={str(factor): kappa},
            )
            row = {
                "factor": str(factor),
                "kappa": kappa,
                "states": int(len(states)),
                "switches": int(states["switched"].sum()),
                "rescues": int(states["rescue"].sum()),
                "harms": int(states["harm"].sum()),
                "net_rescues": int(states["rescue"].sum() - states["harm"].sum()),
                "utility_delta": float(
                    (states["selected_utility"] - states["maxv_utility"]).mean()
                ),
                "adverse_delta": float(
                    (states["selected_adverse"] - states["maxv_adverse"]).sum()
                ),
            }
            candidates.append(row)
            rows.append(row)
        best = max(
            candidates,
            key=lambda row: (
                row["net_rescues"],
                row["utility_delta"],
                -row["adverse_delta"],
                -row["switches"],
                row["kappa"],
            ),
        )
        selected[str(factor)] = float(best["kappa"])
    result = pd.DataFrame(rows)
    result["selected"] = result.apply(
        lambda row: np.isclose(row["kappa"], selected[str(row["factor"])]), axis=1
    )
    return selected, result


def fit_ranker(
    candidate_files: Sequence[Path], model_output: Path, output_dir: Path
) -> dict[str, Any]:
    frame = prepare_candidates(candidate_files)
    development = frame.loc[frame["experiment_split"].eq("development")].copy()
    calibration = frame.loc[frame["experiment_split"].eq("calibration")].copy()
    if set(development["factor"].unique()) != {"Object", "Position"}:
        raise ValueError("Development must contain Object and Position")
    if set(calibration["factor"].unique()) != {"Object", "Position"}:
        raise ValueError("Calibration must contain Object and Position")
    for factor, scoped in development.groupby("factor"):
        if set(scoped["init_state_id"].unique()) != set(range(10, 25)):
            raise ValueError(f"{factor}: development init states must be exactly 10-24")
    for factor, scoped in calibration.groupby("factor"):
        if set(scoped["init_state_id"].unique()) != set(range(25, 30)):
            raise ValueError(f"{factor}: calibration init states must be exactly 25-29")
    overlap = set(development["independent_group"]) & set(calibration["independent_group"])
    if overlap:
        raise ValueError(f"Development/calibration overlap: {sorted(overlap)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    opportunity_states, opportunity_summary, opportunity_pass = _opportunity_summary(
        frame
    )
    opportunity_states.to_csv(output_dir / "opportunity_states.csv", index=False)
    opportunity_summary.to_csv(output_dir / "opportunity_summary.csv", index=False)
    if not opportunity_pass:
        payload = {
            "stage": "development_calibration",
            "opportunity_gate": "FAIL",
            "candidate_rows": int(len(frame)),
            "states": int(frame["analysis_snapshot_id"].nunique()),
        }
        (output_dir / "summary.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "RESULTS.md").write_text(
            "# Hard-cell pairwise ranker: development/calibration\n\n"
            "Opportunity gate: **FAIL**. Holdout was not collected.\n\n"
            + opportunity_summary.to_markdown(index=False)
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError("Opportunity gate failed; holdout is not permitted")

    factor_heads: dict[str, Any] = {}
    cv_parts = []
    coefficient_rows = []
    for factor, scoped in development.groupby("factor", sort=True):
        alpha, cv = _cross_validate_alpha(scoped)
        cv.insert(0, "factor", factor)
        cv_parts.append(cv)
        coefficients, pair_count = _bootstrap_coefficients(
            scoped,
            alpha=alpha,
            members=BOOTSTRAP_MEMBERS,
            seed=BOOTSTRAP_SEED + sum(ord(char) for char in str(factor)),
        )
        factor_heads[str(factor)] = {
            "alpha": alpha,
            "development_states": int(scoped["analysis_snapshot_id"].nunique()),
            "development_groups": int(scoped["independent_group"].nunique()),
            "non_tied_pairs": pair_count,
            "coefficients": coefficients.tolist(),
            "calibrated_kappa": 0.0,
        }
        for index, feature in enumerate(FEATURES):
            coefficient_rows.append(
                {
                    "factor": factor,
                    "feature": feature,
                    "coefficient_mean": float(coefficients[:, index].mean()),
                    "coefficient_std": float(coefficients[:, index].std(ddof=0)),
                }
            )

    resolved = [path.expanduser().resolve() for path in candidate_files]
    model: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_name": "hard_cell_pairwise_ranker_v1",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "features": list(FEATURES),
        "alphas_considered": list(ALPHAS),
        "kappas_considered": list(KAPPAS),
        "bootstrap_members": BOOTSTRAP_MEMBERS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "development_groups": sorted(development["independent_group"].unique().tolist()),
        "calibration_groups": sorted(calibration["independent_group"].unique().tolist()),
        "source_files": [str(path) for path in resolved],
        "source_sha256": {str(path): _sha256(path) for path in resolved},
        "factor_heads": factor_heads,
    }
    kappas, calibration_grid = _choose_kappas(calibration, model)
    for factor, kappa in kappas.items():
        model["factor_heads"][factor]["calibrated_kappa"] = kappa
    canonical = json.dumps(model, sort_keys=True, separators=(",", ":")).encode("utf-8")
    model["frozen_payload_sha256"] = hashlib.sha256(canonical).hexdigest()

    model_output.parent.mkdir(parents=True, exist_ok=True)
    model_output.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    cv_results = pd.concat(cv_parts, ignore_index=True)
    coefficients = pd.DataFrame(coefficient_rows)
    _calibration_scored, calibration_states = select_candidates(calibration, model)
    calibration_summary = _summarize_states(calibration_states)
    cv_results.to_csv(output_dir / "cross_validation.csv", index=False)
    coefficients.to_csv(output_dir / "coefficient_summary.csv", index=False)
    calibration_grid.to_csv(output_dir / "calibration_kappa_grid.csv", index=False)
    calibration_states.to_csv(output_dir / "calibration_states.csv", index=False)
    calibration_summary.to_csv(output_dir / "calibration_summary.csv", index=False)

    payload = {
        "stage": "development_calibration",
        "opportunity_gate": "PASS",
        "candidate_rows": int(len(frame)),
        "development_states": int(development["analysis_snapshot_id"].nunique()),
        "calibration_states": int(calibration["analysis_snapshot_id"].nunique()),
        "frozen_payload_sha256": model["frozen_payload_sha256"],
        "selected_alpha": {
            factor: float(parameters["alpha"])
            for factor, parameters in model["factor_heads"].items()
        },
        "selected_kappa": kappas,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Hard-cell pairwise ranker: development/calibration",
        "",
        "Opportunity gate: **PASS**.",
        "",
        "## Proposal opportunity",
        "",
        opportunity_summary.to_markdown(index=False),
        "",
        "## Grouped cross-validation",
        "",
        cv_results.to_markdown(index=False),
        "",
        "## Calibration selector",
        "",
        calibration_summary.to_markdown(index=False),
        "",
        f"Frozen payload SHA-256: `{model['frozen_payload_sha256']}`.",
        "",
        "The model is frozen before untouched holdout collection.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def _holdout_plot(summary: pd.DataFrame, states: pd.DataFrame, path: Path) -> None:
    shown = summary.loc[summary["factor"].ne("All")]
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    x = np.arange(len(shown))
    width = 0.2
    for offset, column, label in (
        (-2.0, "maxv_sr", "parallel max(value)"),
        (-1.0, "autoregressive_sr", "AR max(value)"),
        (0.0, "ranker_sr", "raw ranker"),
        (1.0, "selected_sr", "calibrated selector"),
        (2.0, "oracle_sr", "oracle in K8"),
    ):
        axes[0].bar(x + offset * width, shown[column], width * 0.9, label=label)
    axes[0].set_xticks(x, shown["factor"])
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Terminal success rate")
    axes[0].set_title("Untouched holdout selection")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    colors = np.where(states["rescue"], "#16856b", np.where(states["harm"], "#c84a3d", "#4c78a8"))
    axes[1].scatter(states["ranker_margin_mean"], states["ranker_margin_lcb"], c=colors)
    axes[1].axhline(0.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_xlabel("Bootstrap mean margin over max(value)")
    axes[1].set_ylabel("Calibrated margin LCB")
    axes[1].set_title("Switch evidence (green=rescue, red=harm)")
    axes[1].grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def evaluate_ranker(
    candidate_files: Sequence[Path], model_path: Path, output_dir: Path
) -> dict[str, Any]:
    frame = prepare_candidates(candidate_files)
    if not frame["experiment_split"].eq("holdout").all():
        raise ValueError("Evaluation input must contain only holdout rows")
    if set(frame["factor"].unique()) != {"Object", "Position"}:
        raise ValueError("Holdout must contain Object and Position")
    for factor, scoped in frame.groupby("factor"):
        if set(scoped["init_state_id"].unique()) != set(range(30, 40)):
            raise ValueError(f"{factor}: holdout init states must be exactly 30-39")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    holdout_groups = set(frame["independent_group"])
    seen_groups = set(model["development_groups"]) | set(model["calibration_groups"])
    overlap = sorted(holdout_groups & seen_groups)
    if overlap:
        raise ValueError(f"Frozen-model/holdout group overlap: {overlap}")
    if list(model["features"]) != list(FEATURES):
        raise ValueError("Frozen model feature schema does not match evaluator")

    candidate_scores, states = select_candidates(frame, model)
    summary = _summarize_states(states)
    bootstrap = _grouped_bootstrap_intervals(states)
    ordering_rows = []
    for factor, scoped in candidate_scores.groupby("factor", sort=True):
        baseline_accuracy, baseline_pairs = _ordering_accuracy(
            scoped.reset_index(drop=True),
            scoped["candidate_parallel_value"].to_numpy(dtype=float),
            target="terminal_success_bool",
        )
        autoregressive_accuracy, autoregressive_pairs = _ordering_accuracy(
            scoped.reset_index(drop=True),
            scoped["candidate_autoregressive_value"].to_numpy(dtype=float),
            target="terminal_success_bool",
        )
        ranker_accuracy, ranker_pairs = _ordering_accuracy(
            scoped.reset_index(drop=True),
            scoped["ranker_score_mean"].to_numpy(dtype=float),
            target="terminal_success_bool",
        )
        ordering_rows.append(
            {
                "factor": factor,
                "success_pairs": min(
                    baseline_pairs, autoregressive_pairs, ranker_pairs
                ),
                "maxv_pairwise_accuracy": baseline_accuracy,
                "autoregressive_pairwise_accuracy": autoregressive_accuracy,
                "ranker_pairwise_accuracy": ranker_accuracy,
            }
        )
    ordering = pd.DataFrame(ordering_rows)
    combined = summary.loc[summary["factor"].eq("All")].iloc[0]
    factors = summary.loc[summary["factor"].ne("All")]
    gate_pass = bool(
        int(combined["mixed_selected_delta_states"]) >= 2
        and int(combined["rescues"]) > int(combined["harms"])
        and (factors["selected_sr"] - factors["maxv_sr"]).ge(0.0).all()
        and float(combined["adverse_delta_events"]) <= 1.0
    )
    payload = {
        "stage": "untouched_holdout",
        "candidate_rows": int(len(frame)),
        "states": int(len(states)),
        "mixed_states": int(states["mixed_pool"].sum()),
        "frozen_payload_sha256": model["frozen_payload_sha256"],
        "maxv_sr": float(combined["maxv_sr"]),
        "autoregressive_sr": float(combined["autoregressive_sr"]),
        "ranker_sr": float(combined["ranker_sr"]),
        "selected_sr": float(combined["selected_sr"]),
        "oracle_sr": float(combined["oracle_sr"]),
        "mixed_selected_delta_states": int(combined["mixed_selected_delta_states"]),
        "switches": int(combined["switches"]),
        "rescues": int(combined["rescues"]),
        "harms": int(combined["harms"]),
        "paired_sign_pvalue": _sign_pvalue(
            int(combined["rescues"]), int(combined["harms"])
        ),
        "adverse_delta_events": float(combined["adverse_delta_events"]),
        "gate": "PASS" if gate_pass else "FAIL",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_scores.to_parquet(output_dir / "holdout_candidate_scores.parquet", index=False)
    candidate_scores.to_csv(output_dir / "holdout_candidate_scores.csv", index=False)
    states.to_csv(output_dir / "holdout_state_comparison.csv", index=False)
    summary.to_csv(output_dir / "holdout_summary.csv", index=False)
    ordering.to_csv(output_dir / "holdout_pairwise_accuracy.csv", index=False)
    bootstrap.to_csv(output_dir / "holdout_bootstrap_intervals.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _holdout_plot(summary, states, output_dir / "holdout_pairwise_ranker.png")
    report = [
        "# Hard-cell pairwise ranker: untouched holdout",
        "",
        f"Frozen model: `{model['frozen_payload_sha256']}`.",
        f"Preregistered holdout gate: **{payload['gate']}**.",
        "",
        "## Terminal selection",
        "",
        summary.to_markdown(index=False),
        "",
        "## Within-state success/fail ordering",
        "",
        ordering.to_markdown(index=False),
        "",
        "## Grouped bootstrap deltas",
        "",
        bootstrap.to_markdown(index=False),
        "",
        f"Exact paired sign p-value over rescues/harms: {payload['paired_sign_pvalue']:.6g}.",
        "",
    ]
    if gate_pass:
        report.extend(
            [
                "The frozen selector improved untouched exact-state terminal ranking.",
                "The next permitted test is paired closed-loop planning on new tasks/init states.",
            ]
        )
    else:
        report.extend(
            [
                "The frozen linear pairwise feature family did not pass the terminal gate.",
                "Do not tune it on these holdout states; move to a nonlinear semantic consequence critic or re-query/recovery.",
            ]
        )
    (output_dir / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fit_parser = subparsers.add_parser("fit")
    fit_parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    fit_parser.add_argument("--model-output", type=Path, required=True)
    fit_parser.add_argument("--output-dir", type=Path, required=True)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    evaluate_parser.add_argument("--model", type=Path, required=True)
    evaluate_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fit":
        payload = fit_ranker(args.candidate_files, args.model_output, args.output_dir)
    else:
        payload = evaluate_ranker(args.candidate_files, args.model, args.output_dir)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

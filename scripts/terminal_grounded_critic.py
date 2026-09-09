#!/usr/bin/env python3
"""Fit and evaluate the preregistered terminal-grounded candidate critic."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ACTION_DIM = 7
PROPRIO_DIM = 9
MODEL_SCHEMA_VERSION = 1
DEFAULT_ALPHA = 10.0
DEFAULT_ENSEMBLE_MEMBERS = 32
DEFAULT_SEED = 2_026_08_29
DEFAULT_CONFORMAL_ALPHA = 0.10
UNCERTAINTY_FLOOR = 1e-3

FROZEN_RANKER_FEATURES = (
    "candidate_value",
    "candidate_first_action_l1",
    "candidate_action_chunk_l1",
    "candidate_action_chunk_l2",
    "latent_action_copy_std_mean",
    "latent_action_copy_std_max",
    "latent_action_first_step_copy_l2_std",
    "latent_future_proprio_copy_std_mean",
    "latent_future_proprio_copy_std_max",
    "latent_value_element_std_mean",
    "latent_value_element_std_max",
)
ACTION_FEATURES = tuple(
    f"candidate_action_{summary}_d{dimension}"
    for summary in ("first", "last", "mean", "std")
    for dimension in range(ACTION_DIM)
)
CONSENSUS_FEATURES = (
    "candidate_action_consensus_first",
    "candidate_action_consensus_chunk",
)
FUTURE_PROPRIO_FEATURES = tuple(
    f"candidate_predicted_future_proprio_d{dimension}"
    for dimension in range(PROPRIO_DIM)
)
TERMINAL_CRITIC_FEATURES = (
    *FROZEN_RANKER_FEATURES,
    *ACTION_FEATURES,
    *CONSENSUS_FEATURES,
    *FUTURE_PROPRIO_FEATURES,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _factor(frame: pd.DataFrame) -> pd.Series:
    if "factor" in frame:
        return frame["factor"].astype(str)
    case = frame.get("case_id", pd.Series("", index=frame.index)).astype(str)
    suite = frame.get("suite", pd.Series("", index=frame.index)).astype(str)
    result = pd.Series("Object", index=frame.index, dtype=object)
    result.loc[case.str.contains("position", case=False) | suite.str.contains("temp")] = (
        "Position"
    )
    result.loc[
        case.str.contains("environment", case=False) | suite.str.contains("env")
    ] = "Environment"
    return result


def _as_bool(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    return values.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})


def read_candidates(
    paths: Sequence[Path], *, require_features: bool = True
) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        frame = (
            pd.read_parquet(resolved)
            if resolved.suffix == ".parquet"
            else pd.read_csv(resolved)
        )
        frame = frame.copy()
        frame["source_run"] = resolved.name.replace("__candidate_outcomes.parquet", "").replace(
            "__candidate_outcomes.csv", ""
        )
        frame["source_path"] = str(resolved)
        parts.append(frame)
    if not parts:
        raise ValueError("At least one candidate table is required")
    result = pd.concat(parts, ignore_index=True, sort=False)
    required = {
        "snapshot_id",
        "suite",
        "task_id",
        "init_state_id",
        "candidate_idx",
        "candidate_value",
        "terminal_available",
        "terminal_success",
        "terminal_utility_v1",
    }
    missing = sorted(required - set(result.columns))
    if missing:
        raise ValueError(f"Candidate tables are missing required columns: {missing}")
    missing_features = sorted(set(TERMINAL_CRITIC_FEATURES) - set(result.columns))
    if require_features and missing_features:
        raise ValueError(
            "Candidate tables predate terminal-critic causal features: "
            + ", ".join(missing_features)
        )
    result = result.loc[_as_bool(result["terminal_available"])].copy()
    if result.empty:
        raise ValueError("Candidate tables contain no terminal branches")
    result["factor"] = _factor(result)
    result["analysis_snapshot_id"] = (
        result["source_run"].astype(str) + "::" + result["snapshot_id"].astype(str)
    )
    result["independent_group"] = (
        result["factor"].astype(str)
        + "|"
        + result["suite"].astype(str)
        + "|"
        + result["task_id"].astype(str)
        + "|"
        + result["init_state_id"].astype(str)
    )
    result["terminal_success_bool"] = _as_bool(result["terminal_success"])
    adverse = pd.Series(False, index=result.index)
    for column in (
        "terminal_target_drop_candidate",
        "terminal_wrong_object_interaction_candidate",
        "terminal_official_safety_violation",
    ):
        if column in result:
            adverse |= _as_bool(result[column])
    if "terminal_failure_type" in result:
        adverse |= result["terminal_failure_type"].astype(str).eq(
            "kinematic_deadlock_candidate"
        )
    result["terminal_adverse_event"] = adverse.astype(float)
    result["terminal_utility_v1"] = pd.to_numeric(
        result["terminal_utility_v1"], errors="coerce"
    )
    result["candidate_value"] = pd.to_numeric(result["candidate_value"], errors="coerce")
    if result["terminal_utility_v1"].isna().any():
        raise ValueError("terminal_utility_v1 contains missing values")
    return add_advantage_target(result)


def add_advantage_target(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    baselines = []
    for _snapshot, group in result.groupby("analysis_snapshot_id", sort=False):
        values = pd.to_numeric(group["candidate_value"], errors="coerce")
        baseline_index = values.idxmax() if values.notna().any() else group.index[0]
        baseline = result.loc[baseline_index]
        baselines.extend(
            {
                "index": int(index),
                "baseline_candidate_idx": int(baseline["candidate_idx"]),
                "baseline_terminal_utility": float(baseline["terminal_utility_v1"]),
                "baseline_terminal_success": bool(baseline["terminal_success_bool"]),
                "baseline_terminal_risk": float(baseline["terminal_adverse_event"]),
            }
            for index in group.index
        )
    baseline_frame = pd.DataFrame(baselines).set_index("index")
    for column in baseline_frame:
        result[column] = baseline_frame.loc[result.index, column].to_numpy()
    result["terminal_advantage"] = (
        result["terminal_utility_v1"] - result["baseline_terminal_utility"]
    )
    return result


def validate_candidate_sets(frame: pd.DataFrame) -> int:
    counts = frame.groupby("analysis_snapshot_id")["candidate_idx"].count()
    unique = sorted(counts.unique().tolist())
    if len(unique) != 1 or unique[0] < 2:
        raise ValueError(f"Candidate counts are incomplete or disagree: {unique}")
    duplicates = frame.duplicated(["analysis_snapshot_id", "candidate_idx"])
    if duplicates.any():
        raise ValueError("Duplicate candidate rows found within a snapshot")
    return int(unique[0])


def opportunity_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for snapshot, group in frame.groupby("analysis_snapshot_id", sort=False):
        success = group["terminal_success_bool"].to_numpy(dtype=bool)
        utility = group["terminal_utility_v1"].to_numpy(dtype=float)
        baseline_idx = int(group["baseline_candidate_idx"].iloc[0])
        baseline_row = group.loc[group["candidate_idx"].eq(baseline_idx)].iloc[0]
        rows.append(
            {
                "analysis_snapshot_id": snapshot,
                "factor": str(group["factor"].iloc[0]),
                "case_id": str(group.get("case_id", pd.Series("unknown")).iloc[0]),
                "independent_group": str(group["independent_group"].iloc[0]),
                "suite": str(group["suite"].iloc[0]),
                "task_id": int(group["task_id"].iloc[0]),
                "task_description": str(
                    group.get("task_description", pd.Series("unknown")).iloc[0]
                ),
                "init_state_id": int(group["init_state_id"].iloc[0]),
                "query_idx": int(group.get("query_idx", pd.Series(-1)).iloc[0]),
                "phase": str(group.get("phase_at_snapshot", pd.Series("unknown")).iloc[0]),
                "candidates": int(len(group)),
                "outcome_heterogeneous": bool(np.unique(success).size > 1),
                "maxv_success": bool(baseline_row["terminal_success_bool"]),
                "oracle_success": bool(success.max()),
                "success_rescue": bool(
                    not baseline_row["terminal_success_bool"] and success.max()
                ),
                "success_harm_possible": bool(
                    baseline_row["terminal_success_bool"] and (~success).any()
                ),
                "maxv_utility": float(baseline_row["terminal_utility_v1"]),
                "oracle_utility": float(utility.max()),
                "utility_rescue": bool(
                    utility.max() > float(baseline_row["terminal_utility_v1"]) + 1e-12
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_opportunity(frame: pd.DataFrame) -> pd.DataFrame:
    opportunity = opportunity_table(frame)
    rows = []
    for factor, group in list(opportunity.groupby("factor")) + [("All", opportunity)]:
        rows.append(
            {
                "factor": factor,
                "snapshots": int(len(group)),
                "independent_groups": int(group["independent_group"].nunique()),
                "heterogeneous_snapshots": int(group["outcome_heterogeneous"].sum()),
                "success_rescues": int(group["success_rescue"].sum()),
                "utility_rescues": int(group["utility_rescue"].sum()),
                "maxv_sr": float(group["maxv_success"].mean()),
                "oracle_sr": float(group["oracle_success"].mean()),
                "oracle_gap_pp": float(
                    100.0 * (group["oracle_success"].mean() - group["maxv_success"].mean())
                ),
                "maxv_utility": float(group["maxv_utility"].mean()),
                "oracle_utility": float(group["oracle_utility"].mean()),
            }
        )
    return pd.DataFrame(rows)


def opportunity_gate(frame: pd.DataFrame) -> dict[str, Any]:
    opportunity = opportunity_table(frame)
    heterogeneous = int(opportunity["outcome_heterogeneous"].sum())
    rescues = int(opportunity["success_rescue"].sum())
    return {
        "passed": bool(heterogeneous >= 8 and rescues >= 4),
        "heterogeneous_snapshots": heterogeneous,
        "required_heterogeneous_snapshots": 8,
        "success_rescues": rescues,
        "required_success_rescues": 4,
        "snapshots": int(len(opportunity)),
        "independent_groups": int(opportunity["independent_group"].nunique()),
    }


def _within_snapshot_z(frame: pd.DataFrame) -> np.ndarray:
    numeric = frame[list(TERMINAL_CRITIC_FEATURES)].apply(pd.to_numeric, errors="coerce")
    grouped = numeric.groupby(frame["analysis_snapshot_id"])
    means = grouped.transform("mean")
    std = grouped.transform(lambda values: values.std(ddof=0))
    std = std.mask(~np.isfinite(std) | (std < 1e-8), 1.0)
    return ((numeric - means) / std).to_numpy(dtype=np.float64)


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, float]:
    design = np.column_stack([np.ones(len(x), dtype=np.float64), x])
    penalty = np.eye(design.shape[1], dtype=np.float64) * float(alpha)
    penalty[0, 0] = 0.0
    parameters = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
    return parameters[1:], float(parameters[0])


def _bootstrap_ensemble(
    x: np.ndarray,
    advantage: np.ndarray,
    risk: np.ndarray,
    groups: np.ndarray,
    *,
    members: int,
    alpha: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(seed)
    advantage_coefficients = []
    advantage_intercepts = []
    risk_coefficients = []
    risk_intercepts = []
    for _member in range(members):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        indices = np.concatenate([np.flatnonzero(groups == group) for group in sampled])
        coefficient, intercept = _ridge_fit(x[indices], advantage[indices], alpha)
        advantage_coefficients.append(coefficient)
        advantage_intercepts.append(intercept)
        coefficient, intercept = _ridge_fit(x[indices], risk[indices], alpha)
        risk_coefficients.append(coefficient)
        risk_intercepts.append(intercept)
    return (
        np.stack(advantage_coefficients),
        np.asarray(advantage_intercepts),
        np.stack(risk_coefficients),
        np.asarray(risk_intercepts),
    )


def _finite_sample_quantile(values: np.ndarray, alpha: float) -> float:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if len(finite) == 0:
        return 0.0
    level = min(1.0, np.ceil((len(finite) + 1) * (1.0 - alpha)) / len(finite))
    return float(max(0.0, np.quantile(finite, level, method="higher")))


def _predict_members(
    frame: pd.DataFrame,
    parameters: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    x = _within_snapshot_z(frame)
    median = np.asarray(parameters["impute_median"], dtype=np.float64)
    mean = np.asarray(parameters["standardization_mean"], dtype=np.float64)
    std = np.asarray(parameters["standardization_std"], dtype=np.float64)
    x = np.where(np.isfinite(x), x, median)
    x = (x - mean) / std
    advantage = (
        x @ np.asarray(parameters["advantage_coefficients"], dtype=np.float64).T
        + np.asarray(parameters["advantage_intercepts"], dtype=np.float64)[None, :]
    )
    risk = (
        x @ np.asarray(parameters["risk_coefficients"], dtype=np.float64).T
        + np.asarray(parameters["risk_intercepts"], dtype=np.float64)[None, :]
    )
    return advantage, risk


def _calibrate_head(
    calibration: pd.DataFrame,
    parameters: Mapping[str, Any],
    *,
    conformal_alpha: float,
) -> tuple[float, float]:
    advantage_members, risk_members = _predict_members(calibration, parameters)
    indexed = calibration.reset_index(drop=True)
    advantage_residuals = []
    risk_residuals = []
    floor = float(parameters["uncertainty_floor"])
    for _group_name, group in indexed.groupby("independent_group", sort=False):
        group_advantage = []
        group_risk = []
        for _snapshot, state in group.groupby("analysis_snapshot_id", sort=False):
            positions = state.index.to_numpy(dtype=int)
            baseline_idx = int(state["baseline_candidate_idx"].iloc[0])
            baseline_position = int(
                state.index[state["candidate_idx"].eq(baseline_idx)][0]
            )
            advantage_delta = (
                advantage_members[positions]
                - advantage_members[baseline_position][None, :]
            )
            mean = advantage_delta.mean(axis=1)
            std = advantage_delta.std(axis=1, ddof=0)
            actual = state["terminal_advantage"].to_numpy(dtype=float)
            nonbaseline = state["candidate_idx"].to_numpy(dtype=int) != baseline_idx
            if nonbaseline.any():
                group_advantage.extend(
                    ((mean[nonbaseline] - actual[nonbaseline]) / np.maximum(std[nonbaseline], floor)).tolist()
                )
            risk_mean = risk_members[positions].mean(axis=1)
            risk_std = risk_members[positions].std(axis=1, ddof=0)
            actual_risk = state["terminal_adverse_event"].to_numpy(dtype=float)
            group_risk.extend(
                ((actual_risk - risk_mean) / np.maximum(risk_std, floor)).tolist()
            )
        if group_advantage:
            advantage_residuals.append(max(group_advantage))
        if group_risk:
            risk_residuals.append(max(group_risk))
    return (
        _finite_sample_quantile(np.asarray(advantage_residuals), conformal_alpha),
        _finite_sample_quantile(np.asarray(risk_residuals), conformal_alpha),
    )


def fit_model(
    training: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    alpha: float = DEFAULT_ALPHA,
    members: int = DEFAULT_ENSEMBLE_MEMBERS,
    seed: int = DEFAULT_SEED,
    conformal_alpha: float = DEFAULT_CONFORMAL_ALPHA,
    source_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    expected_candidates = validate_candidate_sets(training)
    if validate_candidate_sets(calibration) != expected_candidates:
        raise ValueError("Training and calibration candidate counts disagree")
    overlap = sorted(
        set(training["independent_group"]) & set(calibration["independent_group"])
    )
    if overlap:
        raise ValueError(f"Training/calibration group overlap: {overlap[:5]}")
    if alpha <= 0 or members < 4:
        raise ValueError("alpha must be positive and members must be at least four")
    heads: dict[str, Any] = {}
    for factor, scoped in training.groupby("factor", sort=True):
        scoped = scoped.reset_index(drop=True)
        scoped_calibration = calibration.loc[calibration["factor"].eq(factor)].reset_index(
            drop=True
        )
        if scoped["independent_group"].nunique() < 4:
            raise ValueError(f"{factor}: at least four training groups are required")
        if scoped_calibration["independent_group"].nunique() < 2:
            raise ValueError(f"{factor}: at least two calibration groups are required")
        x = _within_snapshot_z(scoped)
        median = np.nanmedian(x, axis=0)
        median = np.where(np.isfinite(median), median, 0.0)
        x = np.where(np.isfinite(x), x, median)
        mean = x.mean(axis=0)
        std = x.std(axis=0)
        std[std < 1e-8] = 1.0
        x = (x - mean) / std
        ensemble = _bootstrap_ensemble(
            x,
            scoped["terminal_advantage"].to_numpy(dtype=float),
            scoped["terminal_adverse_event"].to_numpy(dtype=float),
            scoped["independent_group"].to_numpy(dtype=str),
            members=members,
            alpha=alpha,
            seed=seed + sum(ord(char) for char in str(factor)),
        )
        parameters: dict[str, Any] = {
            "candidate_rows": int(len(scoped)),
            "snapshots": int(scoped["analysis_snapshot_id"].nunique()),
            "independent_groups": int(scoped["independent_group"].nunique()),
            "calibration_rows": int(len(scoped_calibration)),
            "calibration_groups": int(scoped_calibration["independent_group"].nunique()),
            "impute_median": median.tolist(),
            "standardization_mean": mean.tolist(),
            "standardization_std": std.tolist(),
            "advantage_coefficients": ensemble[0].tolist(),
            "advantage_intercepts": ensemble[1].tolist(),
            "risk_coefficients": ensemble[2].tolist(),
            "risk_intercepts": ensemble[3].tolist(),
            "uncertainty_floor": UNCERTAINTY_FLOOR,
            "risk_margin": 0.0,
        }
        advantage_q, risk_q = _calibrate_head(
            scoped_calibration,
            parameters,
            conformal_alpha=conformal_alpha,
        )
        parameters["advantage_conformal_q"] = advantage_q
        parameters["risk_conformal_q"] = risk_q
        heads[str(factor)] = parameters

    resolved_sources = [path.expanduser().resolve() for path in source_paths]
    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_name": "terminal_grounded_conservative_critic_v1",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "features": list(TERMINAL_CRITIC_FEATURES),
        "expected_candidates": expected_candidates,
        "target": "terminal_advantage_to_max_value",
        "risk_target": "terminal_drop_or_wrong_or_deadlock_or_violation",
        "ridge_alpha": float(alpha),
        "ensemble_members": int(members),
        "bootstrap_seed": int(seed),
        "conformal_alpha": float(conformal_alpha),
        "training_sources": [str(path) for path in resolved_sources],
        "training_source_sha256": {
            str(path): _sha256(path) for path in resolved_sources if path.is_file()
        },
        "training_groups": sorted(training["independent_group"].unique().tolist()),
        "calibration_groups": sorted(
            calibration["independent_group"].unique().tolist()
        ),
        "factor_heads": heads,
    }
    canonical = json.dumps(model, sort_keys=True, separators=(",", ":")).encode("utf-8")
    model["frozen_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    return model


def write_model(model: Mapping[str, Any], path: Path) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")


def read_model(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def coefficient_summary(model: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    features = list(model["features"])
    for factor, parameters in model.get("factor_heads", {}).items():
        advantage = np.asarray(parameters["advantage_coefficients"], dtype=float)
        risk = np.asarray(parameters["risk_coefficients"], dtype=float)
        for index, feature in enumerate(features):
            rows.append(
                {
                    "factor": str(factor),
                    "feature": feature,
                    "advantage_coefficient_mean": float(advantage[:, index].mean()),
                    "advantage_coefficient_std": float(advantage[:, index].std(ddof=0)),
                    "risk_coefficient_mean": float(risk[:, index].mean()),
                    "risk_coefficient_std": float(risk[:, index].std(ddof=0)),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["advantage_abs_rank"] = result.groupby("factor")[
            "advantage_coefficient_mean"
        ].transform(lambda values: values.abs().rank(method="first", ascending=False))
        result["risk_abs_rank"] = result.groupby("factor")[
            "risk_coefficient_mean"
        ].transform(lambda values: values.abs().rank(method="first", ascending=False))
    return result


def _plot_coefficients(summary: pd.DataFrame, output: Path, *, top_k: int = 15) -> None:
    if summary.empty:
        return
    factor = str(summary["factor"].iloc[0])
    scoped = summary.loc[summary["factor"].eq(factor)]
    figure, axes = plt.subplots(1, 2, figsize=(14, 6))
    for axis, target, title in (
        (axes[0], "advantage_coefficient_mean", "Terminal advantage head"),
        (axes[1], "risk_coefficient_mean", "Safety-risk head"),
    ):
        selected = scoped.reindex(scoped[target].abs().sort_values().tail(top_k).index)
        colors = np.where(selected[target].to_numpy() >= 0.0, "#b91c1c", "#2563eb")
        axis.barh(selected["feature"], selected[target], color=colors)
        axis.axvline(0.0, color="black", linewidth=1)
        axis.set_title(title)
        axis.set_xlabel("Mean standardized bootstrap coefficient")
        axis.grid(axis="x", alpha=0.25)
    figure.suptitle(f"{factor}: largest frozen critic coefficients")
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _select_frame(
    frame: pd.DataFrame,
    model: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_parts = []
    states = []
    for factor, factor_frame in frame.groupby("factor", sort=False):
        parameters = model.get("factor_heads", {}).get(str(factor))
        if parameters is not None:
            advantage_members, risk_members = _predict_members(
                factor_frame.reset_index(drop=True), parameters
            )
            local = factor_frame.reset_index(drop=True).copy()
            local["_row_position"] = np.arange(len(local))
        else:
            local = factor_frame.reset_index(drop=True).copy()
            advantage_members = np.zeros((len(local), 1), dtype=float)
            risk_members = np.zeros((len(local), 1), dtype=float)
        for snapshot, group in local.groupby("analysis_snapshot_id", sort=False):
            positions = group.index.to_numpy(dtype=int)
            values = group["candidate_value"].to_numpy(dtype=float)
            baseline_local = int(np.nanargmax(values))
            baseline_position = int(positions[baseline_local])
            baseline_idx = int(group.iloc[baseline_local]["candidate_idx"])
            advantage_delta = (
                advantage_members[positions]
                - advantage_members[baseline_position][None, :]
            )
            advantage_mean = advantage_delta.mean(axis=1)
            advantage_std = advantage_delta.std(axis=1, ddof=0)
            proposed_local = int(np.argmax(advantage_mean))
            proposed_position = int(positions[proposed_local])
            proposed_idx = int(group.iloc[proposed_local]["candidate_idx"])
            if parameters is None:
                advantage_lcb = 0.0
                risk_ucb = np.zeros(len(group), dtype=float)
                switch = False
                reason = "missing_factor_head"
            else:
                floor = float(parameters["uncertainty_floor"])
                advantage_lcb = float(
                    advantage_mean[proposed_local]
                    - float(parameters["advantage_conformal_q"])
                    * max(float(advantage_std[proposed_local]), floor)
                )
                risk_mean = risk_members[positions].mean(axis=1)
                risk_std = risk_members[positions].std(axis=1, ddof=0)
                risk_ucb = risk_mean + float(parameters["risk_conformal_q"]) * np.maximum(
                    risk_std, floor
                )
                safety_ok = bool(
                    risk_ucb[proposed_local]
                    <= risk_ucb[baseline_local] + float(parameters.get("risk_margin", 0.0))
                )
                switch = bool(
                    proposed_idx != baseline_idx and advantage_lcb > 0.0 and safety_ok
                )
                if proposed_idx == baseline_idx:
                    reason = "critic_agrees_with_max_value"
                elif advantage_lcb <= 0.0:
                    reason = "non_positive_advantage_lcb"
                elif not safety_ok:
                    reason = "safety_risk_gate"
                else:
                    reason = "accepted"
            selected_idx = proposed_idx if switch else baseline_idx
            oracle_row = group.loc[group["terminal_utility_v1"].idxmax()]
            baseline_row = group.loc[group["candidate_idx"].eq(baseline_idx)].iloc[0]
            selected_row = group.loc[group["candidate_idx"].eq(selected_idx)].iloc[0]
            for local_index, (_, candidate) in enumerate(group.iterrows()):
                scored = candidate.to_dict()
                scored.update(
                    {
                        "critic_advantage_mean": float(advantage_mean[local_index]),
                        "critic_advantage_std": float(advantage_std[local_index]),
                        "critic_risk_ucb": float(risk_ucb[local_index]),
                        "critic_selected": bool(int(candidate["candidate_idx"]) == selected_idx),
                    }
                )
                scored_parts.append(scored)
            states.append(
                {
                    "analysis_snapshot_id": snapshot,
                    "factor": str(factor),
                    "independent_group": str(group["independent_group"].iloc[0]),
                    "baseline_candidate_idx": baseline_idx,
                    "proposed_candidate_idx": proposed_idx,
                    "selected_candidate_idx": selected_idx,
                    "oracle_candidate_idx": int(oracle_row["candidate_idx"]),
                    "switched": switch,
                    "fallback_reason": reason,
                    "advantage_lcb": advantage_lcb,
                    "maxv_success": bool(baseline_row["terminal_success_bool"]),
                    "critic_success": bool(selected_row["terminal_success_bool"]),
                    "oracle_success": bool(group["terminal_success_bool"].max()),
                    "maxv_utility": float(baseline_row["terminal_utility_v1"]),
                    "critic_utility": float(selected_row["terminal_utility_v1"]),
                    "oracle_utility": float(group["terminal_utility_v1"].max()),
                    "maxv_risk": float(baseline_row["terminal_adverse_event"]),
                    "critic_risk": float(selected_row["terminal_adverse_event"]),
                    "rescue": bool(
                        not baseline_row["terminal_success_bool"]
                        and selected_row["terminal_success_bool"]
                    ),
                    "harm": bool(
                        baseline_row["terminal_success_bool"]
                        and not selected_row["terminal_success_bool"]
                    ),
                }
            )
    return pd.DataFrame(scored_parts), pd.DataFrame(states)


def grouped_bootstrap_deltas(
    states: pd.DataFrame,
    *,
    draws: int = 5000,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for factor, scoped in list(states.groupby("factor")) + [("All", states)]:
        group_values = (
            scoped.assign(
                success_delta=scoped["critic_success"].astype(float)
                - scoped["maxv_success"].astype(float),
                utility_delta=scoped["critic_utility"] - scoped["maxv_utility"],
                risk_delta=scoped["critic_risk"] - scoped["maxv_risk"],
            )
            .groupby("independent_group")[["success_delta", "utility_delta", "risk_delta"]]
            .mean()
        )
        array = group_values.to_numpy(dtype=float)
        sampled = rng.integers(0, len(array), size=(draws, len(array)))
        distributions = array[sampled].mean(axis=1)
        for index, metric in enumerate(group_values.columns):
            values = distributions[:, index]
            rows.append(
                {
                    "factor": factor,
                    "metric": metric,
                    "groups": int(len(array)),
                    "point": float(array[:, index].mean()),
                    "ci_low": float(np.quantile(values, 0.025)),
                    "ci_high": float(np.quantile(values, 0.975)),
                }
            )
    return pd.DataFrame(rows)


def summarize_selection(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor, scoped in list(states.groupby("factor")) + [("All", states)]:
        switches = scoped.loc[scoped["switched"]]
        rows.append(
            {
                "factor": factor,
                "snapshots": int(len(scoped)),
                "independent_groups": int(scoped["independent_group"].nunique()),
                "maxv_sr": float(scoped["maxv_success"].mean()),
                "critic_sr": float(scoped["critic_success"].mean()),
                "oracle_sr": float(scoped["oracle_success"].mean()),
                "success_delta_pp": float(
                    100.0
                    * (scoped["critic_success"].mean() - scoped["maxv_success"].mean())
                ),
                "maxv_utility": float(scoped["maxv_utility"].mean()),
                "critic_utility": float(scoped["critic_utility"].mean()),
                "oracle_utility": float(scoped["oracle_utility"].mean()),
                "utility_delta": float(
                    (scoped["critic_utility"] - scoped["maxv_utility"]).mean()
                ),
                "switches": int(scoped["switched"].sum()),
                "switch_rate": float(scoped["switched"].mean()),
                "switch_precision": float(switches["rescue"].mean()) if len(switches) else np.nan,
                "rescues": int(scoped["rescue"].sum()),
                "harms": int(scoped["harm"].sum()),
                "maxv_adverse_rate": float(scoped["maxv_risk"].mean()),
                "critic_adverse_rate": float(scoped["critic_risk"].mean()),
            }
        )
    return pd.DataFrame(rows)


def coverage_diagnostics(
    frame: pd.DataFrame,
    model: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Measure one-sided advantage and risk coverage without changing selection."""
    rows = []
    for factor, factor_frame in frame.groupby("factor", sort=False):
        parameters = model.get("factor_heads", {}).get(str(factor))
        if parameters is None:
            continue
        local = factor_frame.reset_index(drop=True)
        advantage_members, risk_members = _predict_members(local, parameters)
        floor = float(parameters["uncertainty_floor"])
        advantage_q = float(parameters["advantage_conformal_q"])
        risk_q = float(parameters["risk_conformal_q"])
        for snapshot, group in local.groupby("analysis_snapshot_id", sort=False):
            positions = group.index.to_numpy(dtype=int)
            baseline_idx = int(group["baseline_candidate_idx"].iloc[0])
            baseline_position = int(
                group.index[group["candidate_idx"].eq(baseline_idx)][0]
            )
            advantage_delta = (
                advantage_members[positions]
                - advantage_members[baseline_position][None, :]
            )
            advantage_mean = advantage_delta.mean(axis=1)
            advantage_std = advantage_delta.std(axis=1, ddof=0)
            advantage_lcb = advantage_mean - advantage_q * np.maximum(
                advantage_std, floor
            )
            actual_advantage = group["terminal_advantage"].to_numpy(dtype=float)
            nonbaseline = group["candidate_idx"].to_numpy(dtype=int) != baseline_idx
            advantage_covered = actual_advantage[nonbaseline] >= (
                advantage_lcb[nonbaseline] - 1e-12
            )

            risk_mean = risk_members[positions].mean(axis=1)
            risk_std = risk_members[positions].std(axis=1, ddof=0)
            risk_ucb = risk_mean + risk_q * np.maximum(risk_std, floor)
            actual_risk = group["terminal_adverse_event"].to_numpy(dtype=float)
            risk_covered = actual_risk <= (risk_ucb + 1e-12)
            clipped_risk = np.clip(risk_mean, 0.0, 1.0)
            rows.append(
                {
                    "analysis_snapshot_id": snapshot,
                    "factor": str(factor),
                    "independent_group": str(group["independent_group"].iloc[0]),
                    "advantage_candidates": int(nonbaseline.sum()),
                    "advantage_covered": int(advantage_covered.sum()),
                    "advantage_all_covered": bool(advantage_covered.all()),
                    "advantage_mean_lcb_slack": float(
                        np.mean(actual_advantage[nonbaseline] - advantage_lcb[nonbaseline])
                    ),
                    "risk_candidates": int(len(group)),
                    "risk_covered": int(risk_covered.sum()),
                    "risk_all_covered": bool(risk_covered.all()),
                    "risk_predicted_mean": float(clipped_risk.mean()),
                    "risk_observed_mean": float(actual_risk.mean()),
                    "risk_brier": float(np.square(clipped_risk - actual_risk).mean()),
                }
            )
    states = pd.DataFrame(rows)
    summaries = []
    if not states.empty:
        for factor, scoped in list(states.groupby("factor")) + [("All", states)]:
            summaries.append(
                {
                    "factor": factor,
                    "snapshots": int(len(scoped)),
                    "independent_groups": int(scoped["independent_group"].nunique()),
                    "advantage_candidate_coverage": float(
                        scoped["advantage_covered"].sum()
                        / scoped["advantage_candidates"].sum()
                    ),
                    "advantage_simultaneous_state_coverage": float(
                        scoped["advantage_all_covered"].mean()
                    ),
                    "advantage_mean_lcb_slack": float(
                        scoped["advantage_mean_lcb_slack"].mean()
                    ),
                    "risk_candidate_coverage": float(
                        scoped["risk_covered"].sum() / scoped["risk_candidates"].sum()
                    ),
                    "risk_simultaneous_state_coverage": float(
                        scoped["risk_all_covered"].mean()
                    ),
                    "risk_predicted_mean": float(scoped["risk_predicted_mean"].mean()),
                    "risk_observed_mean": float(scoped["risk_observed_mean"].mean()),
                    "risk_brier": float(scoped["risk_brier"].mean()),
                }
            )
    return states, pd.DataFrame(summaries)


def offline_gate(states: pd.DataFrame, ci: pd.DataFrame, model: Mapping[str, Any]) -> dict[str, Any]:
    model_groups = set(model.get("training_groups", ())) | set(
        model.get("calibration_groups", ())
    )
    overlap = sorted(model_groups & set(states["independent_group"]))
    summary = summarize_selection(states)
    overall = summary.loc[summary["factor"].eq("All")].iloc[0]
    utility_ci = ci.loc[
        ci["factor"].eq("All") & ci["metric"].eq("utility_delta")
    ].iloc[0]
    checks = {
        "zero_group_overlap": not overlap,
        "switch_rate_in_2_to_30_percent": bool(0.02 <= overall["switch_rate"] <= 0.30),
        "positive_net_rescues": bool(overall["rescues"] > overall["harms"]),
        "nonnegative_terminal_utility": bool(overall["utility_delta"] >= 0.0),
        "safety_regression_at_most_one_event": bool(
            states["critic_risk"].sum() - states["maxv_risk"].sum() <= 1
        ),
        "utility_ci_lower_nonnegative": bool(utility_ci["ci_low"] >= 0.0),
    }
    return {
        "passed": bool(all(checks.values())),
        "checks": checks,
        "group_overlap": overlap,
        "summary": {key: (None if pd.isna(value) else float(value)) for key, value in overall.items() if key not in {"factor"}},
        "utility_delta_ci": {
            "low": float(utility_ci["ci_low"]),
            "high": float(utility_ci["ci_high"]),
        },
    }


def _write_opportunity(frame: pd.DataFrame, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    opportunity = opportunity_table(frame)
    summary = summarize_opportunity(frame)
    gate = opportunity_gate(frame)
    by_task_query = (
        opportunity.groupby(
            ["factor", "task_id", "task_description", "query_idx"],
            as_index=False,
        )
        .agg(
            snapshots=("analysis_snapshot_id", "size"),
            heterogeneous_snapshots=("outcome_heterogeneous", "sum"),
            success_rescues=("success_rescue", "sum"),
            maxv_sr=("maxv_success", "mean"),
            oracle_sr=("oracle_success", "mean"),
        )
        .sort_values(["factor", "task_id", "query_idx"])
    )
    opportunity.to_csv(output_dir / "terminal_opportunity_states.csv", index=False)
    summary.to_csv(output_dir / "terminal_opportunity_summary.csv", index=False)
    by_task_query.to_csv(
        output_dir / "terminal_opportunity_by_task_query.csv", index=False
    )
    (output_dir / "opportunity_gate.json").write_text(
        json.dumps(gate, indent=2) + "\n", encoding="utf-8"
    )

    factor_summary = summary.loc[summary["factor"].ne("All")].copy()
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    positions = np.arange(len(factor_summary))
    width = 0.36
    axes[0].bar(
        positions - width / 2,
        factor_summary["maxv_sr"],
        width,
        label="max(value)",
    )
    axes[0].bar(
        positions + width / 2,
        factor_summary["oracle_sr"],
        width,
        label="oracle in pool",
    )
    axes[0].set_xticks(positions, factor_summary["factor"])
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Terminal success rate")
    axes[0].set_title("Achievable candidate-pool gap")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    task_summary = (
        opportunity.groupby("task_id", as_index=False)
        .agg(
            heterogeneous_snapshots=("outcome_heterogeneous", "sum"),
            success_rescues=("success_rescue", "sum"),
        )
        .sort_values("task_id")
    )
    task_positions = np.arange(len(task_summary))
    axes[1].bar(
        task_positions - width / 2,
        task_summary["heterogeneous_snapshots"],
        width,
        label="heterogeneous",
    )
    axes[1].bar(
        task_positions + width / 2,
        task_summary["success_rescues"],
        width,
        label="maxV-fail rescues",
    )
    axes[1].set_xticks(task_positions, task_summary["task_id"].astype(str))
    axes[1].set_xlabel("Task id")
    axes[1].set_ylabel("Snapshot count")
    axes[1].set_title("Where selection can change the outcome")
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "terminal_opportunity_overview.png", dpi=180)
    plt.close(figure)
    return gate


def _write_analysis_report(
    output_dir: Path,
    *,
    title: str,
    opportunity: pd.DataFrame,
    gate_name: str,
    gate: Mapping[str, Any],
    selection: pd.DataFrame | None = None,
    intervals: pd.DataFrame | None = None,
    coverage: pd.DataFrame | None = None,
    coefficients: pd.DataFrame | None = None,
    model: Mapping[str, Any] | None = None,
) -> None:
    lines = [
        f"# {title}",
        "",
        f"- {gate_name}: **{'PASS' if gate['passed'] else 'FAIL'}**.",
        "",
        "## Candidate-pool opportunity",
        "",
        opportunity.to_markdown(index=False),
    ]
    if model is not None:
        lines.extend(
            [
                "",
                "## Frozen model",
                "",
                f"- Name: `{model['model_name']}`.",
                f"- Payload SHA-256: `{model['frozen_payload_sha256']}`.",
                f"- Ensemble members: {model['ensemble_members']}.",
                f"- Ridge alpha: {model['ridge_alpha']}.",
                f"- Expected candidates: {model['expected_candidates']}.",
            ]
        )
    if selection is not None and not selection.empty:
        lines.extend(["", "## Conservative selection", "", selection.to_markdown(index=False)])
    if intervals is not None and not intervals.empty:
        lines.extend(["", "## Grouped bootstrap", "", intervals.to_markdown(index=False)])
    if coverage is not None and not coverage.empty:
        lines.extend(["", "## Interval coverage", "", coverage.to_markdown(index=False)])
    if coefficients is not None and not coefficients.empty:
        top = coefficients.loc[
            coefficients["advantage_abs_rank"].le(10)
            | coefficients["risk_abs_rank"].le(10)
        ].sort_values(["factor", "advantage_abs_rank", "risk_abs_rank"])
        lines.extend(["", "## Largest frozen coefficients", "", top.to_markdown(index=False)])
    lines.extend(
        [
            "",
            f"## {gate_name}",
            "",
            "```json",
            json.dumps(gate, indent=2),
            "```",
        ]
    )
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_audit(args: argparse.Namespace) -> int:
    candidates = read_candidates(args.candidate_files)
    validate_candidate_sets(candidates)
    output_dir = args.output_dir.resolve()
    gate = _write_opportunity(candidates, output_dir)
    _write_analysis_report(
        output_dir,
        title="Terminal candidate-pool opportunity audit",
        opportunity=summarize_opportunity(candidates),
        gate_name="Opportunity gate",
        gate=gate,
    )
    print(json.dumps(gate, indent=2))
    return 0


def command_fit(args: argparse.Namespace) -> int:
    training = read_candidates(args.training_files)
    calibration = read_candidates(args.calibration_files)
    validate_candidate_sets(training)
    validate_candidate_sets(calibration)
    output_dir = args.output_dir.resolve()
    combined = pd.concat([training, calibration], ignore_index=True)
    gate = _write_opportunity(combined, output_dir)
    if not gate["passed"] and not args.allow_failed_opportunity_gate:
        _write_analysis_report(
            output_dir,
            title="Terminal-grounded critic development result",
            opportunity=summarize_opportunity(combined),
            gate_name="Opportunity gate",
            gate=gate,
        )
        print(json.dumps(gate, indent=2))
        print("[terminal-critic] opportunity gate failed; model was not fitted")
        return 4
    model = fit_model(
        training,
        calibration,
        alpha=args.ridge_alpha,
        members=args.ensemble_members,
        seed=args.seed,
        conformal_alpha=args.conformal_alpha,
        source_paths=[*args.training_files, *args.calibration_files],
    )
    write_model(model, args.output_model)
    coefficients = coefficient_summary(model)
    coefficients.to_csv(output_dir / "frozen_coefficient_summary.csv", index=False)
    _plot_coefficients(coefficients, output_dir / "frozen_coefficient_summary.png")
    scored, states = _select_frame(calibration, model)
    coverage_states, coverage_summary = coverage_diagnostics(calibration, model)
    scored.to_parquet(output_dir / "calibration_candidates_scored.parquet", index=False)
    states.to_csv(output_dir / "calibration_state_outcomes.csv", index=False)
    selection_summary = summarize_selection(states)
    selection_summary.to_csv(
        output_dir / "calibration_selection_summary.csv", index=False
    )
    coverage_states.to_csv(output_dir / "calibration_coverage_states.csv", index=False)
    coverage_summary.to_csv(
        output_dir / "calibration_coverage_summary.csv", index=False
    )
    _write_analysis_report(
        output_dir,
        title="Terminal-grounded critic development result",
        opportunity=summarize_opportunity(combined),
        gate_name="Opportunity gate",
        gate=gate,
        selection=selection_summary,
        coverage=coverage_summary,
        coefficients=coefficients,
        model=model,
    )
    print(f"[terminal-critic] wrote frozen model: {args.output_model.resolve()}")
    print(f"[terminal-critic] payload sha256: {model['frozen_payload_sha256']}")
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    model = read_model(args.model)
    candidates = read_candidates(args.candidate_files)
    validate_candidate_sets(candidates)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_opportunity(candidates, output_dir)
    scored, states = _select_frame(candidates, model)
    coverage_states, coverage_summary = coverage_diagnostics(candidates, model)
    summary = summarize_selection(states)
    ci = grouped_bootstrap_deltas(
        states, draws=args.bootstrap_draws, seed=args.seed
    )
    gate = offline_gate(states, ci, model)
    scored.to_parquet(output_dir / "holdout_candidates_scored.parquet", index=False)
    states.to_csv(output_dir / "holdout_state_outcomes.csv", index=False)
    summary.to_csv(output_dir / "holdout_selection_summary.csv", index=False)
    coverage_states.to_csv(output_dir / "holdout_coverage_states.csv", index=False)
    coverage_summary.to_csv(output_dir / "holdout_coverage_summary.csv", index=False)
    ci.to_csv(output_dir / "holdout_grouped_bootstrap_ci.csv", index=False)
    (output_dir / "offline_gate.json").write_text(
        json.dumps(gate, indent=2) + "\n", encoding="utf-8"
    )
    _write_analysis_report(
        output_dir,
        title="Frozen terminal-grounded critic holdout result",
        opportunity=summarize_opportunity(candidates),
        gate_name="Offline critic gate",
        gate=gate,
        selection=summary,
        intervals=ci,
        coverage=coverage_summary,
        model=model,
    )

    plot = summary.loc[summary["factor"].ne("All")].copy()
    if not plot.empty:
        positions = np.arange(len(plot))
        width = 0.25
        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.bar(positions - width, plot["maxv_sr"], width, label="max(value)")
        axis.bar(positions, plot["critic_sr"], width, label="terminal critic")
        axis.bar(positions + width, plot["oracle_sr"], width, label="oracle in pool")
        axis.set_xticks(positions, plot["factor"])
        axis.set_ylim(0.0, 1.05)
        axis.set_ylabel("Terminal success rate")
        axis.legend()
        axis.grid(axis="y", alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / "terminal_sr_comparison.png", dpi=180)
        plt.close(figure)
    print(json.dumps(gate, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Measure terminal oracle opportunity")
    audit.add_argument("--candidate-files", type=Path, nargs="+", required=True)
    audit.add_argument("--output-dir", type=Path, required=True)
    audit.set_defaults(func=command_audit)

    fit = subparsers.add_parser("fit", help="Fit and conformally calibrate a frozen critic")
    fit.add_argument("--training-files", type=Path, nargs="+", required=True)
    fit.add_argument("--calibration-files", type=Path, nargs="+", required=True)
    fit.add_argument("--output-model", type=Path, required=True)
    fit.add_argument("--output-dir", type=Path, required=True)
    fit.add_argument("--ridge-alpha", type=float, default=DEFAULT_ALPHA)
    fit.add_argument("--ensemble-members", type=int, default=DEFAULT_ENSEMBLE_MEMBERS)
    fit.add_argument("--conformal-alpha", type=float, default=DEFAULT_CONFORMAL_ALPHA)
    fit.add_argument("--seed", type=int, default=DEFAULT_SEED)
    fit.add_argument("--allow-failed-opportunity-gate", action="store_true")
    fit.set_defaults(func=command_fit)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a frozen critic on holdout")
    evaluate.add_argument("--model", type=Path, required=True)
    evaluate.add_argument("--candidate-files", type=Path, nargs="+", required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--bootstrap-draws", type=int, default=5000)
    evaluate.add_argument("--seed", type=int, default=DEFAULT_SEED)
    evaluate.set_defaults(func=command_evaluate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

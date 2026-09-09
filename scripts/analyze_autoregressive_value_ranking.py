#!/usr/bin/env python3
"""Compare parallel and action-conditioned autoregressive candidate values."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import read_candidates
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from terminal_grounded_critic import read_candidates


ACTION_SIGNATURE_FEATURES = tuple(
    f"candidate_action_{summary}_d{dimension}"
    for summary in ("first", "last", "mean", "std")
    for dimension in range(7)
)
PARALLEL_FUTURE_PROPRIO_FEATURES = tuple(
    f"candidate_predicted_future_proprio_d{dimension}" for dimension in range(9)
)
AUTOREGRESSIVE_FUTURE_PROPRIO_FEATURES = tuple(
    f"candidate_autoregressive_predicted_future_proprio_d{dimension}"
    for dimension in range(9)
)
STATE_KEY = ("condition", "factor", "task_id", "init_state_id", "query_idx")
CANDIDATE_KEY = (*STATE_KEY, "rollout_seed", "candidate_idx", "candidate_seed")


def _condition(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series("Object", index=frame.index, dtype=object)
    result.loc[frame["factor"].eq("Position")] = "Position-y0.3"
    return result


def _prepare_dual(paths: Sequence[Path]) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    frame = read_candidates(paths, require_features=False)
    frame = frame.loc[
        frame["factor"].isin(["Object", "Position"])
        & frame["task_id"].eq(0)
        & frame["query_idx"].eq(0)
        & frame["candidate_idx"].lt(8)
    ].copy()
    if frame.empty:
        raise ValueError("No q0 K8 dual-evaluator candidates found")
    if frame["factor"].eq("Position").any():
        position_case = frame.loc[frame["factor"].eq("Position"), "case_id"].astype(str)
        if not position_case.str.contains("y0p3|y0.3", case=False, regex=True).all():
            raise ValueError("Input contains a Position condition other than y0.3")
    frame["condition"] = _condition(frame)
    required_values = ("candidate_parallel_value", "candidate_autoregressive_value")
    for column in (*ACTION_SIGNATURE_FEATURES, "candidate_value", *required_values):
        if column not in frame:
            raise ValueError(f"Dual-evaluator candidates are missing {column}")
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    checked = [*ACTION_SIGNATURE_FEATURES, "candidate_value", *required_values]
    if frame[checked].isna().any().any():
        raise ValueError("Dual-evaluator candidates contain non-finite features")
    proprio_columns = (
        *PARALLEL_FUTURE_PROPRIO_FEATURES,
        *AUTOREGRESSIVE_FUTURE_PROPRIO_FEATURES,
    )
    available_proprio_columns = [column for column in proprio_columns if column in frame]
    if available_proprio_columns and len(available_proprio_columns) != len(proprio_columns):
        missing = sorted(set(proprio_columns) - set(available_proprio_columns))
        raise ValueError(f"Dual-evaluator candidates have incomplete future proprio: {missing}")
    if available_proprio_columns:
        proprio_column_list = list(proprio_columns)
        frame.loc[:, proprio_column_list] = frame.loc[:, proprio_column_list].apply(
            pd.to_numeric, errors="coerce"
        )
        if frame.loc[:, proprio_column_list].isna().any().any():
            raise ValueError("Dual-evaluator future proprio contains non-finite values")
        parallel_proprio = frame.loc[:, PARALLEL_FUTURE_PROPRIO_FEATURES].to_numpy(
            dtype=float
        )
        autoregressive_proprio = frame.loc[
            :, AUTOREGRESSIVE_FUTURE_PROPRIO_FEATURES
        ].to_numpy(dtype=float)
        proprio_difference = autoregressive_proprio - parallel_proprio
        frame["future_proprio_l2_autoregressive_vs_parallel"] = np.linalg.norm(
            proprio_difference, axis=1
        )
        frame["future_proprio_rmse_autoregressive_vs_parallel"] = np.sqrt(
            np.mean(np.square(proprio_difference), axis=1)
        )
    if frame.duplicated(list(CANDIDATE_KEY)).any():
        duplicates = frame.loc[frame.duplicated(list(CANDIDATE_KEY), keep=False), list(CANDIDATE_KEY)]
        raise ValueError(f"Duplicate candidate keys:\n{duplicates.to_string(index=False)}")
    parallel_alias_error = float(
        np.max(np.abs(frame["candidate_value"] - frame["candidate_parallel_value"]))
    )
    parallel = frame.copy()
    parallel["candidate_value"] = parallel["candidate_parallel_value"]
    parallel["evaluator"] = "parallel"
    autoregressive = frame.copy()
    autoregressive["candidate_value"] = autoregressive[
        "candidate_autoregressive_value"
    ]
    autoregressive["evaluator"] = "autoregressive"
    return parallel, autoregressive, parallel_alias_error


def _pairwise_accuracy(values: np.ndarray, labels: np.ndarray) -> float:
    successful = values[labels]
    failed = values[~labels]
    if not len(successful) or not len(failed):
        return float("nan")
    differences = successful[:, None] - failed[None, :]
    return float(np.mean((differences > 0) + 0.5 * (differences == 0)))


def _spearman(left: np.ndarray, right: np.ndarray) -> float:
    left_rank = pd.Series(left).rank(method="average").to_numpy(dtype=float)
    right_rank = pd.Series(right).rank(method="average").to_numpy(dtype=float)
    if np.std(left_rank) == 0 or np.std(right_rank) == 0:
        return float("nan")
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def _paired_sign_pvalue(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(rescues, harms) + 1))
    return float(min(1.0, 2.0 * tail / (2**discordant)))


def compare_candidates(
    parallel: pd.DataFrame,
    autoregressive: pd.DataFrame,
    *,
    expected_candidates: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = [
        *CANDIDATE_KEY,
        "candidate_value",
        "terminal_success_bool",
        "terminal_failure_type",
        *ACTION_SIGNATURE_FEATURES,
    ]
    consequence_features = [
        column
        for column in (
            "future_proprio_l2_autoregressive_vs_parallel",
            "future_proprio_rmse_autoregressive_vs_parallel",
        )
        if column in parallel and column in autoregressive
    ]
    keep.extend(consequence_features)
    paired = parallel[keep].merge(
        autoregressive[keep],
        on=list(CANDIDATE_KEY),
        how="outer",
        suffixes=("_parallel", "_autoregressive"),
        indicator=True,
        validate="one_to_one",
    )
    if len(paired) != expected_candidates or not paired["_merge"].eq("both").all():
        counts = paired["_merge"].value_counts().to_dict()
        raise ValueError(
            f"Expected {expected_candidates} exactly paired candidates, got {len(paired)}: {counts}"
        )

    action_differences = []
    for feature in ACTION_SIGNATURE_FEATURES:
        difference = (
            paired[f"{feature}_parallel"] - paired[f"{feature}_autoregressive"]
        ).abs()
        paired[f"action_abs_diff__{feature}"] = difference
        action_differences.append(difference.to_numpy(dtype=float))
    stacked_differences = np.stack(action_differences, axis=1)
    paired["action_signature_max_abs"] = stacked_differences.max(axis=1)
    paired["action_signature_mean_abs"] = stacked_differences.mean(axis=1)
    paired["terminal_outcome_agrees"] = paired["terminal_success_bool_parallel"].eq(
        paired["terminal_success_bool_autoregressive"]
    )
    paired["value_delta_autoregressive_minus_parallel"] = (
        paired["candidate_value_autoregressive"] - paired["candidate_value_parallel"]
    )
    for feature in consequence_features:
        parallel_feature = paired[f"{feature}_parallel"]
        autoregressive_feature = paired[f"{feature}_autoregressive"]
        if not np.allclose(parallel_feature, autoregressive_feature, rtol=0.0, atol=0.0):
            raise ValueError(f"Same-pass diagnostic differs between evaluator views: {feature}")
        paired[feature] = parallel_feature

    state_rows: list[dict[str, object]] = []
    for state_key, group in paired.groupby(list(STATE_KEY), sort=True):
        group = group.sort_values("candidate_idx")
        labels = group["terminal_success_bool_parallel"].to_numpy(dtype=bool)
        parallel_values = group["candidate_value_parallel"].to_numpy(dtype=float)
        autoregressive_values = group["candidate_value_autoregressive"].to_numpy(dtype=float)
        parallel_position = int(np.argmax(parallel_values))
        autoregressive_position = int(np.argmax(autoregressive_values))
        parallel_idx = int(group.iloc[parallel_position]["candidate_idx"])
        autoregressive_idx = int(group.iloc[autoregressive_position]["candidate_idx"])
        parallel_success = bool(labels[parallel_position])
        autoregressive_success = bool(labels[autoregressive_position])
        row = dict(zip(STATE_KEY, state_key))
        row.update(
            {
                "candidates": int(len(group)),
                "mixed_pool": bool(labels.any() and not labels.all()),
                "oracle_success": bool(labels.any()),
                "parallel_selected_idx": parallel_idx,
                "autoregressive_selected_idx": autoregressive_idx,
                "selector_switched": parallel_idx != autoregressive_idx,
                "parallel_selected_success": parallel_success,
                "autoregressive_selected_success": autoregressive_success,
                "selector_rescue": bool(not parallel_success and autoregressive_success),
                "selector_harm": bool(parallel_success and not autoregressive_success),
                "parallel_pairwise_accuracy": _pairwise_accuracy(parallel_values, labels),
                "autoregressive_pairwise_accuracy": _pairwise_accuracy(
                    autoregressive_values, labels
                ),
                "parallel_autoregressive_value_spearman": _spearman(
                    parallel_values, autoregressive_values
                ),
                "parallel_value_range": float(np.ptp(parallel_values)),
                "autoregressive_value_range": float(np.ptp(autoregressive_values)),
                "action_signature_max_abs": float(group["action_signature_max_abs"].max()),
                "terminal_outcome_agreement": float(group["terminal_outcome_agrees"].mean()),
            }
        )
        if consequence_features:
            row.update(
                {
                    "future_proprio_l2_mean": float(
                        group["future_proprio_l2_autoregressive_vs_parallel"].mean()
                    ),
                    "future_proprio_l2_max": float(
                        group["future_proprio_l2_autoregressive_vs_parallel"].max()
                    ),
                }
            )
        state_rows.append(row)
    return paired, pd.DataFrame.from_records(state_rows)


def summarize(states: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scopes = [(factor, group) for factor, group in states.groupby("factor", sort=True)]
    scopes.append(("All", states))
    for factor, group in scopes:
        mixed = group.loc[group["mixed_pool"]]
        rescues = int(group["selector_rescue"].sum())
        harms = int(group["selector_harm"].sum())
        rows.append(
            {
                "factor": factor,
                "states": int(len(group)),
                "mixed_states": int(len(mixed)),
                "oracle_success_rate": float(group["oracle_success"].mean()),
                "parallel_all_state_success_rate": float(
                    group["parallel_selected_success"].mean()
                ),
                "autoregressive_all_state_success_rate": float(
                    group["autoregressive_selected_success"].mean()
                ),
                "parallel_mixed_top1_success_rate": (
                    float(mixed["parallel_selected_success"].mean())
                    if len(mixed)
                    else np.nan
                ),
                "autoregressive_mixed_top1_success_rate": (
                    float(mixed["autoregressive_selected_success"].mean())
                    if len(mixed)
                    else np.nan
                ),
                "mixed_top1_delta_states": int(
                    mixed["autoregressive_selected_success"].sum()
                    - mixed["parallel_selected_success"].sum()
                ),
                "parallel_pairwise_accuracy": (
                    float(mixed["parallel_pairwise_accuracy"].mean())
                    if len(mixed)
                    else np.nan
                ),
                "autoregressive_pairwise_accuracy": (
                    float(mixed["autoregressive_pairwise_accuracy"].mean())
                    if len(mixed)
                    else np.nan
                ),
                "switches": int(group["selector_switched"].sum()),
                "rescues": rescues,
                "harms": harms,
                "paired_sign_pvalue": _paired_sign_pvalue(rescues, harms),
                "parallel_autoregressive_value_spearman_mean": float(
                    group["parallel_autoregressive_value_spearman"].mean()
                ),
                "future_proprio_l2_mean": (
                    float(group["future_proprio_l2_mean"].mean())
                    if "future_proprio_l2_mean" in group
                    else np.nan
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


def _plot(paired: pd.DataFrame, states: pd.DataFrame, summary: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(14, 10))
    colors = np.where(paired["terminal_success_bool_parallel"], "#16856b", "#c84a3d")
    axes[0, 0].scatter(
        paired["candidate_value_parallel"],
        paired["candidate_value_autoregressive"],
        c=colors,
        alpha=0.72,
        s=36,
    )
    lower = float(
        min(paired["candidate_value_parallel"].min(), paired["candidate_value_autoregressive"].min())
    )
    upper = float(
        max(paired["candidate_value_parallel"].max(), paired["candidate_value_autoregressive"].max())
    )
    axes[0, 0].plot([lower, upper], [lower, upper], "k--", linewidth=1)
    axes[0, 0].set_xlabel("Parallel value")
    axes[0, 0].set_ylabel("Autoregressive value")
    axes[0, 0].set_title("Matched candidate values (green=success)")
    axes[0, 0].grid(alpha=0.2)

    shown = summary.loc[summary["factor"].ne("All") & summary["mixed_states"].gt(0)]
    x = np.arange(len(shown))
    width = 0.36
    axes[0, 1].bar(
        x - width / 2,
        shown["parallel_mixed_top1_success_rate"],
        width,
        label="parallel",
    )
    axes[0, 1].bar(
        x + width / 2,
        shown["autoregressive_mixed_top1_success_rate"],
        width,
        label="action -> future -> value",
    )
    axes[0, 1].set_xticks(x, shown["factor"])
    axes[0, 1].set_ylim(0, 1.05)
    axes[0, 1].set_ylabel("Top-1 terminal success")
    axes[0, 1].set_title("Ranking on mixed pools")
    axes[0, 1].legend()
    axes[0, 1].grid(axis="y", alpha=0.2)

    ordered = states.sort_values(["factor", "init_state_id"])
    labels = [f"{row.factor}:i{int(row.init_state_id)}" for row in ordered.itertuples()]
    y = np.arange(len(ordered))
    axes[1, 0].scatter(
        ordered["parallel_selected_success"].astype(int),
        y - 0.12,
        marker="s",
        s=80,
        label="parallel",
    )
    axes[1, 0].scatter(
        ordered["autoregressive_selected_success"].astype(int),
        y + 0.12,
        marker="o",
        s=70,
        label="autoregressive",
    )
    axes[1, 0].set_yticks(y, labels)
    axes[1, 0].set_xticks([0, 1], ["fail", "success"])
    axes[1, 0].set_xlim(-0.25, 1.25)
    axes[1, 0].set_title("Selected terminal outcome per exact state")
    axes[1, 0].legend()
    axes[1, 0].grid(axis="x", alpha=0.2)

    axes[1, 1].hist(
        paired["action_signature_max_abs"], bins=20, color="#4c78a8", alpha=0.85
    )
    axes[1, 1].axvline(1e-5, color="#c84a3d", linestyle="--", label="validity threshold")
    axes[1, 1].set_xlabel("Max absolute action-signature difference")
    axes[1, 1].set_ylabel("Candidates")
    axes[1, 1].set_title("Action invariance sanity check")
    axes[1, 1].legend()
    axes[1, 1].grid(axis="y", alpha=0.2)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def analyze(
    candidate_files: Sequence[Path],
    output_dir: Path,
    *,
    expected_candidates: int = 80,
) -> dict[str, object]:
    parallel, autoregressive, parallel_alias_error = _prepare_dual(candidate_files)
    paired, states = compare_candidates(
        parallel, autoregressive, expected_candidates=expected_candidates
    )
    summary = summarize(states)
    combined = summary.loc[summary["factor"].eq("All")].iloc[0]
    factors = summary.loc[summary["factor"].ne("All") & summary["mixed_states"].gt(0)]

    action_max_abs = float(paired["action_signature_max_abs"].max())
    outcome_agreement = float(paired["terminal_outcome_agrees"].mean())
    validity_pass = bool(
        action_max_abs <= 1e-12
        and outcome_agreement == 1.0
        and parallel_alias_error <= 1e-12
    )
    efficacy_pass = bool(
        int(combined["mixed_top1_delta_states"]) >= 1
        and int(combined["rescues"]) > int(combined["harms"])
        and factors["mixed_top1_delta_states"].ge(0).all()
    )
    gate = "PASS" if validity_pass and efficacy_pass else "FAIL"
    if not validity_pass:
        gate = "INVALID"

    payload: dict[str, object] = {
        "candidate_files": len(candidate_files),
        "paired_candidates": int(len(paired)),
        "states": int(len(states)),
        "mixed_states": int(states["mixed_pool"].sum()),
        "action_signature_max_abs": action_max_abs,
        "parallel_value_alias_max_abs": parallel_alias_error,
        "terminal_outcome_agreement": outcome_agreement,
        "parallel_mixed_top1_success_rate": float(
            combined["parallel_mixed_top1_success_rate"]
        ),
        "autoregressive_mixed_top1_success_rate": float(
            combined["autoregressive_mixed_top1_success_rate"]
        ),
        "mixed_top1_delta_states": int(combined["mixed_top1_delta_states"]),
        "rescues": int(combined["rescues"]),
        "harms": int(combined["harms"]),
        "candidate_value_spearman": _spearman(
            paired["candidate_value_parallel"].to_numpy(dtype=float),
            paired["candidate_value_autoregressive"].to_numpy(dtype=float),
        ),
        "future_proprio_l2_mean": (
            float(paired["future_proprio_l2_autoregressive_vs_parallel"].mean())
            if "future_proprio_l2_autoregressive_vs_parallel" in paired
            else float("nan")
        ),
        "future_proprio_l2_p95": (
            float(
                paired["future_proprio_l2_autoregressive_vs_parallel"].quantile(0.95)
            )
            if "future_proprio_l2_autoregressive_vs_parallel" in paired
            else float("nan")
        ),
        "validity_pass": validity_pass,
        "efficacy_pass": efficacy_pass,
        "gate": gate,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output_dir / "matched_candidates.csv", index=False)
    states.to_csv(output_dir / "state_comparison.csv", index=False)
    summary.to_csv(output_dir / "summary_by_factor.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    _plot(paired, states, summary, output_dir / "autoregressive_value_comparison.png")

    report = [
        "# Action-conditioned autoregressive value: results",
        "",
        "Сравнение выполнено в одном forward lineage для каждого candidate:",
        "action генерируется один раз, затем из того же latent получаются",
        "parallel value и последовательный `action -> future -> value`. Метка",
        "успеха означает terminal success после общей frozen parallel continuation",
        "policy; меняется только способ получения candidate value.",
        "",
        "## Validity",
        "",
        f"- Matched candidates: {payload['paired_candidates']}.",
        f"- Action-signature max abs difference: {action_max_abs:.3e}.",
        f"- Stored parallel-value alias error: {parallel_alias_error:.3e}.",
        f"- Matched terminal-outcome agreement: {outcome_agreement:.3%}.",
        f"- Validity gate: **{'PASS' if validity_pass else 'FAIL'}**.",
        f"- Candidate-level parallel/AR value Spearman: {payload['candidate_value_spearman']:.4f}.",
        f"- Parallel/AR future-proprio L2 mean / p95: "
        f"{payload['future_proprio_l2_mean']:.4f} / {payload['future_proprio_l2_p95']:.4f}.",
        "",
        "## Ranking results",
        "",
        summary.to_markdown(index=False),
        "",
        f"Overall preregistered gate: **{gate}**.",
        "",
        "## Interpretation",
        "",
    ]
    if gate == "PASS":
        report.extend(
            [
                "Последовательная оценка `action -> future -> value` улучшила",
                "paired terminal ranking без изменения action pool. Следующий шаг:",
                "заморозить этот evaluator и проверить его closed-loop на новых init",
                "states; текущие состояния больше не использовать для настройки.",
            ]
        )
    elif gate == "INVALID":
        report.extend(
            [
                "Action/outcome invariance не подтверждена, поэтому causal",
                "интерпретация сравнения невозможна. Нужно исправить matching или",
                "отделить переоценку сохранённых действий от генерации proposals.",
            ]
        )
    else:
        report.extend(
            [
                "Авторегрессионный value не дал устойчивого paired улучшения.",
                "Следующий приоритет: learned within-state advantage critic на",
                "action-conditioned features, с отдельными development/holdout init.",
            ]
        )
    (output_dir / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-candidates", type=int, default=80)
    args = parser.parse_args()
    payload = analyze(
        args.candidate_files,
        args.output_dir,
        expected_candidates=args.expected_candidates,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

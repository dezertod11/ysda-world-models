#!/usr/bin/env python3
"""Build compact, leakage-aware tables from the long LIBERO validation run."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


EPISODE_KEYS = [
    "source_run",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_seed",
]

DIRECT_METRICS = [
    "action_first_step_l2_std",
    "action_std_mean",
    "value_std",
    "value_range",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "flow_path_dispersion_action_vfd_weighted",
    "flow_path_dispersion_future_proprio_vfd_weighted",
    "flow_path_dispersion_future_image_vfd_weighted",
    "flow_path_dispersion_value_vfd_weighted",
    "value_mean",
]

PREDICTION_ERRORS = [
    "prediction_error_future_image_mse",
    "prediction_error_future_wrist_mse",
    "prediction_error_future_proprio_l2",
    "prediction_error_value_abs_chunk_success",
]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def auc_score(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    positives = int(frame["label"].sum())
    negatives = len(frame) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = frame["score"].rank(method="average")
    rank_sum = float(ranks[frame["label"]].sum())
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    positives = int(frame["label"].sum())
    if positives == 0:
        return float("nan")
    frame = frame.sort_values("score", ascending=False)
    precision = frame["label"].astype(int).cumsum() / np.arange(1, len(frame) + 1)
    return float(precision[frame["label"]].sum() / positives)


def conformal_upper_threshold(success_scores: Sequence[float], alpha: float) -> float:
    scores = np.sort(np.asarray(pd.Series(success_scores).dropna(), dtype=float))
    if len(scores) == 0:
        return float("nan")
    rank = min(len(scores), int(math.ceil((len(scores) + 1) * (1 - alpha))))
    return float(scores[rank - 1])


def classification_metrics(labels: Sequence[bool], predictions: Sequence[bool]) -> dict[str, float]:
    labels_array = np.asarray(labels, dtype=bool)
    prediction_array = np.asarray(predictions, dtype=bool)
    tp = int(np.sum(labels_array & prediction_array))
    fn = int(np.sum(labels_array & ~prediction_array))
    tn = int(np.sum(~labels_array & ~prediction_array))
    fp = int(np.sum(~labels_array & prediction_array))
    tpr = tp / (tp + fn) if tp + fn else float("nan")
    tnr = tn / (tn + fp) if tn + fp else float("nan")
    return {
        "balanced_accuracy": 0.5 * (tpr + tnr),
        "tpr": tpr,
        "fpr": 1.0 - tnr,
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
    }


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def pearson_correlation(left: pd.Series, right: pd.Series) -> float:
    left_values = left.to_numpy(dtype=float)
    right_values = right.to_numpy(dtype=float)
    if len(left_values) < 2 or np.nanstd(left_values) == 0 or np.nanstd(right_values) == 0:
        return float("nan")
    return float(np.corrcoef(left_values, right_values)[0, 1])


def direct_detector_table(traces: pd.DataFrame, alpha: float) -> pd.DataFrame:
    frame = traces.loc[
        (traces["case_id"] == "direct_milk_task5_init0")
        & (traces["planning_strategy"] == "first")
    ].copy()
    frame["fail"] = ~parse_bool(frame["success"])
    rows = []
    for query_idx in [0, 3, 4, 5, 8, 9]:
        query = frame.loc[frame["query_idx"] == query_idx]
        for metric in DIRECT_METRICS:
            if metric not in query or not query[metric].notna().any():
                continue
            calibration = query.loc[query["experiment_split"] == "calibration"].dropna(
                subset=[metric]
            )
            holdout = query.loc[query["experiment_split"] == "holdout"].dropna(
                subset=[metric]
            )
            if calibration.empty or holdout.empty:
                continue
            threshold = conformal_upper_threshold(
                calibration.loc[~calibration["fail"], metric],
                alpha,
            )
            classification = classification_metrics(
                holdout["fail"],
                holdout[metric].ge(threshold),
            )
            rows.append(
                {
                    "query_idx": query_idx,
                    "query_t": int(query["t"].min()),
                    "metric": metric,
                    "alpha": alpha,
                    "calibration_episodes_alive": len(calibration),
                    "calibration_success_alive": int((~calibration["fail"]).sum()),
                    "holdout_episodes_alive": len(holdout),
                    "holdout_fail_alive": int(holdout["fail"].sum()),
                    "calibration_auc": auc_score(calibration["fail"], calibration[metric]),
                    "holdout_auc": auc_score(holdout["fail"], holdout[metric]),
                    "holdout_auprc": average_precision(holdout["fail"], holdout[metric]),
                    "threshold": threshold,
                    **classification,
                }
            )
    return pd.DataFrame(rows)


def pooled_planning_table(paired: pd.DataFrame) -> pd.DataFrame:
    common = paired.loc[
        paired["experiment_split"].isin(["holdout", "generalization"])
        & paired["prediction_mode"].eq("parallel")
        & paired["num_samples"].eq(4)
        & paired["num_open_loop_steps"].eq(16)
        & paired["planning_action_weight"].eq(0.5)
    ].copy()
    preferred_case_ids = {
        "milk_task5_init0",
        "yellow_task8_init0",
        "long_mug_task4_init0",
    }
    preferred = common.loc[
        common["case_id"].isin(preferred_case_ids)
        & common["num_denoising_steps_action"].eq(5)
    ]
    frame = preferred if not preferred.empty else common
    rows = []
    group_columns = [
        "prediction_mode",
        "num_samples",
        "num_open_loop_steps",
        "num_denoising_steps_action",
        "planning_strategy",
        "planning_risk_lambda",
        "planning_action_weight",
    ]
    for keys, group in frame.groupby(group_columns, dropna=False):
        paired_rollouts = int(group["paired_rollouts"].sum())
        baseline_successes = int(
            round((group["baseline_success_rate"] * group["paired_rollouts"]).sum())
        )
        strategy_successes = int(
            round((group["strategy_success_rate"] * group["paired_rollouts"]).sum())
        )
        wins = int(group["wins"].sum())
        losses = int(group["losses"].sum())
        ties = int(group["ties"].sum())
        rows.append(
            {
                **dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,))),
                "cases": int(group["case_id"].nunique()),
                "paired_rollouts": paired_rollouts,
                "baseline_successes": baseline_successes,
                "strategy_successes": strategy_successes,
                "baseline_success_rate": baseline_successes / paired_rollouts,
                "strategy_success_rate": strategy_successes / paired_rollouts,
                "delta_success_rate": (strategy_successes - baseline_successes)
                / paired_rollouts,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
            }
        )
    result_columns = group_columns + [
        "cases",
        "paired_rollouts",
        "baseline_successes",
        "strategy_successes",
        "baseline_success_rate",
        "strategy_success_rate",
        "delta_success_rate",
        "wins",
        "losses",
        "ties",
        "mcnemar_exact_p",
    ]
    if not rows:
        return pd.DataFrame(columns=result_columns)
    return pd.DataFrame(rows, columns=result_columns).sort_values(
        "delta_success_rate", ascending=False
    )


def controlled_prediction_error_correlations(
    traces: pd.DataFrame,
    max_query: int,
) -> pd.DataFrame:
    frame = traces.loc[
        (traces["case_id"] == "direct_milk_task5_init0")
        & (traces["planning_strategy"] == "first")
        & (traces["query_idx"] <= max_query)
    ].copy()
    rows = []
    group_columns = ["experiment_split", "query_idx"]
    for metric in DIRECT_METRICS:
        if metric not in frame:
            continue
        for error in PREDICTION_ERRORS:
            if error not in frame:
                continue
            pair = frame[group_columns + [metric, error]].dropna().copy()
            if len(pair) < 20:
                continue
            pair["metric_rank"] = pair.groupby(group_columns)[metric].rank(pct=True)
            pair["error_rank"] = pair.groupby(group_columns)[error].rank(pct=True)
            rows.append(
                {
                    "max_query": max_query,
                    "metric": metric,
                    "prediction_error": error,
                    "rows": len(pair),
                    "query_controlled_rank_correlation": pearson_correlation(
                        pair["metric_rank"],
                        pair["error_rank"],
                    ),
                }
            )
    columns = [
        "max_query",
        "metric",
        "prediction_error",
        "rows",
        "query_controlled_rank_correlation",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        "query_controlled_rank_correlation",
        key=lambda values: values.abs(),
        ascending=False,
    )


def case_outcome_table(episodes: pd.DataFrame) -> pd.DataFrame:
    frame = episodes.copy()
    frame["success"] = parse_bool(frame["success"])
    rows = []
    for (case_id, split), group in frame.groupby(
        ["case_id", "experiment_split"],
        dropna=False,
    ):
        failures = group.loc[~group["success"]]
        failure_counts = failures["failure_type"].fillna("unknown").value_counts()
        rows.append(
            {
                "case_id": case_id,
                "experiment_split": split,
                "rollout_executions": len(group),
                "successes": int(group["success"].sum()),
                "failures": len(failures),
                "success_rate": float(group["success"].mean()),
                "failure_types": "; ".join(
                    f"{name}:{count}" for name, count in failure_counts.items()
                ),
                "drop_candidates_all": int(parse_bool(group["target_drop_candidate"]).sum()),
                "wrong_object_candidates_all": int(
                    parse_bool(group["wrong_object_interaction_candidate"]).sum()
                ),
                "official_safety_violations": int(
                    parse_bool(group["official_safety_violation"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["case_id", "experiment_split"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=0.1)
    args = parser.parse_args()

    traces = pd.read_parquet(args.analysis_dir / "all_query_traces.parquet")
    episodes = pd.read_csv(args.analysis_dir / "episode_outcomes.csv")
    paired = pd.read_csv(args.analysis_dir / "paired_vs_max_value.csv")

    direct_detector_table(traces, args.alpha).to_csv(
        args.analysis_dir / "prespecified_detector_exact_query.csv",
        index=False,
    )
    pooled_planning_table(paired).to_csv(
        args.analysis_dir / "pooled_planning_confirmatory.csv",
        index=False,
    )
    controlled_prediction_error_correlations(traces, max_query=5).to_csv(
        args.analysis_dir / "prediction_error_correlations_q0_5.csv",
        index=False,
    )
    case_outcome_table(episodes).to_csv(
        args.analysis_dir / "case_outcome_summary.csv",
        index=False,
    )
    print(f"Wrote compact result tables to {args.analysis_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Analyze corrected LIBERO-PRO boundary outcomes and early risk signals."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


CASE_KEYS = ["suite", "task_id", "init_state_id"]
EPISODE_KEYS = [
    "source_trace",
    "suite",
    "task_id",
    "init_state_id",
    "pair_id",
    "rollout_id",
    "rollout_seed",
]
TASK_OOD_SUITES = {
    "libero_goal_task",
    "libero_spatial_task",
    "libero_object_task",
    "libero_10_task",
}


@dataclass(frozen=True)
class MetricSpec:
    name: str
    column: str
    multiplier: float = 1.0
    family: str = "uncertainty"
    preregistered: bool = True


EARLY_METRICS = (
    MetricSpec("action_first_step_std", "action_first_step_l2_std"),
    MetricSpec("action_chunk_std", "action_std_mean"),
    MetricSpec("value_std", "value_std"),
    MetricSpec("value_range", "value_range"),
    MetricSpec("negative_mean_value", "value_mean", -1.0, "value"),
    MetricSpec("negative_selected_value", "selected_value", -1.0, "value"),
    MetricSpec(
        "latent_action_copy_std",
        "latent_action_copy_std_mean_mean_over_samples",
        family="latent",
    ),
    MetricSpec(
        "latent_future_proprio_copy_std",
        "latent_future_proprio_copy_std_mean_mean_over_samples",
        family="latent",
    ),
    MetricSpec(
        "latent_value_element_std",
        "latent_value_element_std_mean_mean_over_samples",
        family="latent",
    ),
    MetricSpec("selected_overlap_rmse", "overlap_selected_rmse", family="overlap"),
    MetricSpec(
        "selected_overlap_all_rmse",
        "overlap_selected_all_rmse",
        family="overlap",
    ),
    MetricSpec(
        "overlap_cosine_distance", "overlap_cosine_distance", family="overlap"
    ),
    MetricSpec(
        "future_proprio_error",
        "prediction_error_future_proprio_l2",
        family="feedback",
    ),
    MetricSpec(
        "overlap_rotation_rmse",
        "overlap_rot_rmse",
        family="overlap",
        preregistered=False,
    ),
    MetricSpec(
        "overlap_normalized_shift",
        "overlap_shift",
        family="overlap",
        preregistered=False,
    ),
    MetricSpec(
        "future_image_error",
        "prediction_error_future_image_mse",
        family="feedback",
        preregistered=False,
    ),
)


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def auc_score(labels: Sequence[bool], scores: Sequence[float]) -> float:
    labels_array = np.asarray(labels, dtype=bool)
    scores_array = np.asarray(scores, dtype=float)
    valid = np.isfinite(scores_array)
    labels_array = labels_array[valid]
    scores_array = scores_array[valid]
    positives = int(labels_array.sum())
    negatives = len(labels_array) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = stats.rankdata(scores_array)
    rank_sum = float(ranks[labels_array].sum())
    return (rank_sum - positives * (positives + 1) / 2) / (
        positives * negatives
    )


def benjamini_hochberg(p_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    valid_indices = np.flatnonzero(np.isfinite(values))
    if not len(valid_indices):
        return result
    order = valid_indices[np.argsort(values[valid_indices])]
    adjusted = values[order] * len(order) / np.arange(1, len(order) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result[order] = np.minimum(adjusted, 1.0)
    return result


def load_traces(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not paths:
        raise FileNotFoundError(f"No query traces under {campaign_dir / 'runs'}")
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = path.name
        frames.append(frame)
    traces = pd.concat(frames, ignore_index=True, sort=False).copy()
    traces["success"] = parse_bool(traces["success"])
    traces["failure"] = ~traces["success"]
    return traces


def make_episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    frame = traces.sort_values(EPISODE_KEYS + ["query_idx"])
    return frame.groupby(EPISODE_KEYS, dropna=False, sort=False).first().reset_index()


def case_table(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in episodes.groupby(CASE_KEYS, dropna=False, sort=True):
        successes = int(group["success"].sum())
        failures = int(len(group) - successes)
        rows.append(
            {
                **dict(zip(CASE_KEYS, keys)),
                "num_rollouts": int(len(group)),
                "num_success": successes,
                "num_failed": failures,
                "success_rate": successes / len(group),
                "confirmed_mixed": successes >= 2 and failures >= 2,
                "provisional_mixed": min(successes, failures) == 1,
            }
        )
    return pd.DataFrame(rows)


def early_episode_scores(
    traces: pd.DataFrame, specs: Sequence[MetricSpec], max_query: int = 3
) -> pd.DataFrame:
    early = traces.loc[traces["query_idx"].le(max_query)].copy()
    rows = []
    for keys, group in early.groupby(EPISODE_KEYS, dropna=False, sort=False):
        row = dict(zip(EPISODE_KEYS, keys))
        row["failure"] = bool(group["failure"].iloc[0])
        for spec in specs:
            if spec.column not in group:
                row[spec.name] = float("nan")
                continue
            values = (
                pd.to_numeric(group[spec.column], errors="coerce").to_numpy(float)
                * spec.multiplier
            )
            row[spec.name] = (
                float(np.nanmax(values)) if np.isfinite(values).any() else float("nan")
            )
        rows.append(row)
    return pd.DataFrame(rows)


def macro_case_auc(frame: pd.DataFrame, score_column: str) -> tuple[float, dict[str, float]]:
    values = {}
    for keys, group in frame.groupby(CASE_KEYS, dropna=False, sort=True):
        label = f"{keys[0]}/task{int(keys[1])}/init{int(keys[2])}"
        values[label] = auc_score(group["failure"], group[score_column])
    finite = [value for value in values.values() if np.isfinite(value)]
    return (float(np.mean(finite)) if finite else float("nan")), values


def stratified_inference(
    frame: pd.DataFrame,
    score_column: str,
    observed_auc: float,
    samples: int,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    groups = [group.reset_index(drop=True) for _, group in frame.groupby(CASE_KEYS)]
    bootstrap = np.empty(samples, dtype=float)
    permuted = np.empty(samples, dtype=float)
    for sample_index in range(samples):
        bootstrap_aucs = []
        permutation_aucs = []
        for group in groups:
            positive = group.loc[group["failure"]]
            negative = group.loc[~group["failure"]]
            if len(positive) == 0 or len(negative) == 0:
                continue
            boot_positive = positive.iloc[rng.integers(0, len(positive), len(positive))]
            boot_negative = negative.iloc[rng.integers(0, len(negative), len(negative))]
            boot_group = pd.concat([boot_positive, boot_negative], ignore_index=True)
            bootstrap_aucs.append(
                auc_score(boot_group["failure"], boot_group[score_column])
            )

            shuffled = group["failure"].to_numpy(copy=True)
            rng.shuffle(shuffled)
            permutation_aucs.append(auc_score(shuffled, group[score_column]))
        bootstrap[sample_index] = np.mean(bootstrap_aucs)
        permuted[sample_index] = np.mean(permutation_aucs)
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    p_value = (1.0 + np.sum(permuted >= observed_auc)) / (samples + 1.0)
    return float(low), float(high), float(p_value)


def early_metric_table(
    traces: pd.DataFrame,
    cases: pd.DataFrame,
    specs: Sequence[MetricSpec],
    max_query: int,
    inference_samples: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = early_episode_scores(traces, specs, max_query=max_query)
    confirmed_keys = cases.loc[cases["confirmed_mixed"], CASE_KEYS]
    confirmed = scores.merge(confirmed_keys, on=CASE_KEYS, how="inner")
    rng = np.random.default_rng(seed)
    rows = []
    for spec in specs:
        macro_auc, per_case = macro_case_auc(confirmed, spec.name)
        low, high, p_value = stratified_inference(
            confirmed, spec.name, macro_auc, inference_samples, rng
        )
        rows.append(
            {
                "metric": spec.name,
                "source_column": spec.column,
                "family": spec.family,
                "preregistered": spec.preregistered,
                "max_query": max_query,
                "max_executed_steps": 8 * (max_query + 1),
                "num_episodes": int(len(confirmed)),
                "num_failures": int(confirmed["failure"].sum()),
                "macro_failure_auc": macro_auc,
                "bootstrap_ci95_low": low,
                "bootstrap_ci95_high": high,
                "per_case_auc_json": json.dumps(per_case, sort_keys=True),
                "stratified_permutation_p": p_value,
            }
        )
    result = pd.DataFrame(rows)
    result["bh_q_value"] = benjamini_hochberg(result["stratified_permutation_p"])
    result = result.sort_values("macro_failure_auc", ascending=False).reset_index(drop=True)
    return result, confirmed


def suite_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    return (
        episodes.groupby("suite", sort=True)
        .agg(
            num_rollouts=("success", "size"),
            num_success=("success", "sum"),
            target_drop_failures=(
                "target_drop_candidate",
                lambda values: int(parse_bool(values).sum()),
            ),
            wrong_object_events=(
                "wrong_object_interaction_candidate",
                lambda values: int(parse_bool(values).sum()),
            ),
        )
        .reset_index()
        .assign(
            num_failed=lambda frame: frame["num_rollouts"] - frame["num_success"],
            success_rate=lambda frame: frame["num_success"] / frame["num_rollouts"],
        )
    )


def failure_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    failed = episodes.loc[~episodes["success"]].copy()
    failed["group"] = np.where(
        failed["suite"].isin(TASK_OOD_SUITES), "task_ood", "mixed_control"
    )
    return (
        failed.groupby(["group", "failure_type"], dropna=False)
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["group", "count"], ascending=[True, False])
    )


def task_difficulty_table(
    traces: pd.DataFrame, cases: pd.DataFrame, specs: Sequence[MetricSpec]
) -> pd.DataFrame:
    query_zero = traces.loc[
        traces["suite"].isin(TASK_OOD_SUITES) & traces["query_idx"].eq(0)
    ].copy()
    rows = []
    for spec in specs:
        if spec.column not in query_zero:
            continue
        scored = query_zero.assign(
            _score=pd.to_numeric(query_zero[spec.column], errors="coerce")
            * spec.multiplier
        )
        case_scores = (
            scored.groupby(CASE_KEYS, dropna=False)["_score"].mean().reset_index()
            .rename(columns={"_score": spec.name})
        )
        merged = case_scores.merge(cases, on=CASE_KEYS, how="inner")
        deterministic = merged.loc[merged["success_rate"].isin([0.0, 1.0])].copy()
        labels = deterministic["success_rate"].eq(0.0)
        rows.append(
            {
                "metric": spec.name,
                "family": spec.family,
                "num_deterministic_cases": int(len(deterministic)),
                "num_all_fail_cases": int(labels.sum()),
                "failure_auc": auc_score(labels, deterministic[spec.name]),
                "spearman_with_success_rate": float(
                    stats.spearmanr(merged[spec.name], merged["success_rate"]).statistic
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("failure_auc", ascending=False)


def fixed_query_feedback_table(
    traces: pd.DataFrame, cases: pd.DataFrame, max_query: int = 10
) -> pd.DataFrame:
    confirmed_keys = cases.loc[cases["confirmed_mixed"], CASE_KEYS]
    selected = traces.merge(confirmed_keys, on=CASE_KEYS, how="inner")
    rows = []
    for query_idx in range(max_query + 1):
        query = selected.loc[selected["query_idx"].eq(query_idx)]
        macro_auc, per_case = macro_case_auc(query, "prediction_error_future_proprio_l2")
        rows.append(
            {
                "query_idx": query_idx,
                "observed_after_step": 8 * (query_idx + 1),
                "num_episodes": int(len(query)),
                "macro_failure_auc": macro_auc,
                "per_case_auc_json": json.dumps(per_case, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def plot_suite_outcomes(summary: pd.DataFrame, output: Path) -> None:
    ordered = summary.sort_values("success_rate")
    fig, axis = plt.subplots(figsize=(10, 5))
    positions = np.arange(len(ordered))
    axis.barh(positions, ordered["num_failed"], color="#D1495B", label="failed")
    axis.barh(
        positions,
        ordered["num_success"],
        left=ordered["num_failed"],
        color="#2A9D8F",
        label="success",
    )
    axis.set_yticks(positions, ordered["suite"])
    axis.set_xlabel("Rollouts")
    axis.set_title("Corrected LIBERO-PRO outcomes")
    axis.legend()
    axis.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=170)
    plt.close(fig)


def plot_early_auc(metrics: pd.DataFrame, output: Path) -> None:
    ordered = metrics.sort_values("macro_failure_auc")
    fig, axis = plt.subplots(figsize=(10, 7))
    y = np.arange(len(ordered))
    auc = ordered["macro_failure_auc"].to_numpy(float)
    low = np.maximum(auc - ordered["bootstrap_ci95_low"].to_numpy(float), 0.0)
    high = np.maximum(ordered["bootstrap_ci95_high"].to_numpy(float) - auc, 0.0)
    colors = ["#457B9D" if value else "#E9C46A" for value in ordered["preregistered"]]
    axis.errorbar(auc, y, xerr=np.vstack([low, high]), fmt="none", ecolor="#303030", capsize=2)
    axis.scatter(auc, y, c=colors, s=42, zorder=3)
    axis.axvline(0.5, color="#444444", linestyle="--", linewidth=1)
    axis.set_yticks(y, ordered["metric"])
    axis.set_xlim(0.0, 1.0)
    axis.set_xlabel("Macro AUROC for failure (two confirmed mixed cases)")
    axis.set_title("Early risk signals, queries 0-3")
    axis.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output, dpi=170)
    plt.close(fig)


def analyze(
    campaign_dir: Path,
    output_dir: Path,
    max_early_query: int = 3,
    inference_samples: int = 5000,
    seed: int = 20260824,
) -> dict[str, object]:
    traces = load_traces(campaign_dir)
    episodes = make_episode_table(traces)
    cases = case_table(episodes)
    early_metrics, confirmed_scores = early_metric_table(
        traces,
        cases,
        EARLY_METRICS,
        max_query=max_early_query,
        inference_samples=inference_samples,
        seed=seed,
    )
    suites = suite_summary(episodes)
    failures = failure_summary(episodes)
    difficulty = task_difficulty_table(traces, cases, EARLY_METRICS)
    feedback = fixed_query_feedback_table(traces, cases)

    output_dir.mkdir(parents=True, exist_ok=True)
    suites.to_csv(output_dir / "suite_outcomes.csv", index=False)
    failures.to_csv(output_dir / "failure_type_counts.csv", index=False)
    cases.to_csv(output_dir / "case_outcomes.csv", index=False)
    early_metrics.to_csv(output_dir / "mixed_early_metric_auc.csv", index=False)
    confirmed_scores.to_csv(output_dir / "mixed_early_episode_scores.csv", index=False)
    difficulty.to_csv(output_dir / "task_difficulty_metric_auc.csv", index=False)
    feedback.to_csv(output_dir / "future_proprio_feedback_by_query.csv", index=False)
    plot_suite_outcomes(suites, output_dir / "suite_outcomes.png")
    plot_early_auc(early_metrics, output_dir / "mixed_early_metric_auc.png")

    task_cases = cases.loc[cases["suite"].isin(TASK_OOD_SUITES)]
    preregistered = early_metrics.loc[early_metrics["preregistered"]]
    exploratory = early_metrics.loc[~early_metrics["preregistered"]]
    best_preregistered = preregistered.iloc[0]
    best_exploratory = exploratory.iloc[0]
    feedback_q5 = feedback.loc[feedback["query_idx"].eq(5)].iloc[0]
    result: dict[str, object] = {
        "campaign_dir": str(campaign_dir),
        "num_rollouts": int(len(episodes)),
        "num_success": int(episodes["success"].sum()),
        "num_failed": int((~episodes["success"]).sum()),
        "task_ood_cases": int(len(task_cases)),
        "task_ood_all_fail_cases": int(task_cases["success_rate"].eq(0).sum()),
        "task_ood_all_success_cases": int(task_cases["success_rate"].eq(1).sum()),
        "task_ood_mixed_cases": int(task_cases["success_rate"].between(0, 1, inclusive="neither").sum()),
        "confirmed_mixed_cases": int(cases["confirmed_mixed"].sum()),
        "confirmed_mixed_episodes": int(len(confirmed_scores)),
        "confirmed_mixed_failures": int(confirmed_scores["failure"].sum()),
        "best_preregistered_early_metric": str(best_preregistered["metric"]),
        "best_preregistered_early_macro_auc": float(best_preregistered["macro_failure_auc"]),
        "best_exploratory_early_metric": str(best_exploratory["metric"]),
        "best_exploratory_early_macro_auc": float(best_exploratory["macro_failure_auc"]),
        "best_exploratory_bh_q": float(best_exploratory["bh_q_value"]),
        "future_proprio_feedback_q5_macro_auc": float(feedback_q5["macro_failure_auc"]),
        "metrics_with_bh_q_below_0_05": int(early_metrics["bh_q_value"].lt(0.05).sum()),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-early-query", type=int, default=3)
    parser.add_argument("--inference-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260824)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "ground_truth_results"
    summary = analyze(
        args.campaign_dir,
        output_dir,
        max_early_query=args.max_early_query,
        inference_samples=args.inference_samples,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

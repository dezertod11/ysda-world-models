#!/usr/bin/env python3
"""Analyze paired closed-loop max-value versus frozen-ranker rollouts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


BASELINE = "max_value"
METHOD = "frozen_factor_ridge"
EXPECTED_FACTORS = ("Environment", "Object", "Position")
PAIR_KEYS = (
    "factor",
    "case_id",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_seed",
)
Q0_NUMERIC_TOLERANCES = {
    "candidate_values_json": 5e-4,
    "candidate_frozen_ranker_scores_json": 2e-3,
    "candidate_first_actions_json": 5e-3,
}
FROZEN_FEATURES = (
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


def _first(group: pd.DataFrame, column: str, default: Any) -> Any:
    return group[column].iloc[0] if column in group else default


def _last(group: pd.DataFrame, column: str, default: Any) -> Any:
    return group[column].iloc[-1] if column in group else default


def _episode_rows(path: Path) -> pd.DataFrame:
    trace = pd.read_parquet(path)
    if trace.empty:
        return pd.DataFrame()
    grouping = [column for column in ("pair_id", "rollout_id") if column in trace]
    if len(grouping) != 2:
        raise ValueError(f"{path}: trace lacks pair_id/rollout_id")
    rows = []
    for (_pair_id, _rollout_id), group in trace.groupby(grouping, dropna=False):
        group = group.sort_values("query_idx")
        strategy = str(_first(group, "planning_strategy", ""))
        factor = str(_first(group, "planning_frozen_ranker_factor", ""))
        if strategy not in {BASELINE, METHOD}:
            continue
        rows.append(
            {
                "source_file": str(path),
                "source_run": path.name.removesuffix("__query_traces.parquet"),
                "factor": factor,
                "case_id": str(_first(group, "case_id", "")),
                "suite": str(_first(group, "suite", "")),
                "task_id": int(_first(group, "task_id", -1)),
                "task_description": str(_first(group, "task_description", "")),
                "init_state_id": int(_first(group, "init_state_id", -1)),
                "pair_id": int(_first(group, "pair_id", -1)),
                "rollout_id": int(_first(group, "rollout_id", -1)),
                "rollout_seed": int(_first(group, "rollout_seed", -1)),
                "planning_strategy": strategy,
                "success": bool(_last(group, "success", False)),
                "final_t": int(_last(group, "final_t", 0)),
                "num_queries": int(len(group)),
                "selected_not_max_value_rate": float(
                    (~group["max_value_selected"].astype(bool)).mean()
                    if "max_value_selected" in group
                    else np.nan
                ),
                "mean_value_sacrifice": float(
                    (group["max_value"] - group["selected_value"]).mean()
                    if {"max_value", "selected_value"}.issubset(group)
                    else np.nan
                ),
                "model_payload_sha256": str(
                    _first(group, "planning_frozen_ranker_payload_sha256", "")
                ),
                "candidate_count_min": int(group["num_samples"].min()),
                "candidate_count_max": int(group["num_samples"].max()),
                "failure_type": str(_last(group, "failure_type", "unknown")),
                "target_drop": bool(_last(group, "target_drop_candidate", False)),
                "official_safety_violation": bool(
                    _last(group, "official_safety_violation", False)
                ),
            }
        )
    return pd.DataFrame(rows)


def load_campaign_episodes(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trace_paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not trace_paths:
        raise FileNotFoundError(f"No query traces under {campaign_dir / 'runs'}")
    episode_frames = [_episode_rows(path) for path in trace_paths]
    episodes = pd.concat([frame for frame in episode_frames if not frame.empty], ignore_index=True)
    if episodes.empty:
        raise ValueError("No max-value/frozen-ranker episodes found")
    if set(episodes["factor"]) != set(EXPECTED_FACTORS):
        raise ValueError(f"Unexpected factors: {sorted(episodes['factor'].unique())}")

    duplicated = episodes.duplicated([*PAIR_KEYS, "planning_strategy"], keep=False)
    if duplicated.any():
        examples = episodes.loc[duplicated, [*PAIR_KEYS, "planning_strategy"]].head()
        raise ValueError(f"Duplicate strategy outcomes for paired keys:\n{examples}")
    paired = episodes.pivot(index=list(PAIR_KEYS), columns="planning_strategy")
    paired.columns = [f"{column}__{strategy}" for column, strategy in paired.columns]
    paired = paired.reset_index()
    required = {f"success__{BASELINE}", f"success__{METHOD}"}
    paired["pair_complete"] = paired[list(required)].notna().all(axis=1)
    paired["success_delta"] = (
        paired[f"success__{METHOD}"].astype(float)
        - paired[f"success__{BASELINE}"].astype(float)
    )
    paired["discordance"] = np.select(
        [paired["success_delta"].eq(1), paired["success_delta"].eq(-1)],
        ["frozen_gain", "frozen_loss"],
        default="same_outcome",
    )
    paired["independent_group"] = (
        paired["factor"].astype(str)
        + "|"
        + paired["case_id"].astype(str)
        + "|"
        + paired["suite"].astype(str)
        + "|"
        + paired["task_id"].astype(str)
        + "|"
        + paired["init_state_id"].astype(str)
    )
    return episodes, paired


def summarize_factors(paired: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor, group in paired.groupby("factor", sort=True):
        baseline = group[f"success__{BASELINE}"].astype(bool)
        method = group[f"success__{METHOD}"].astype(bool)
        gains = int((~baseline & method).sum())
        losses = int((baseline & ~method).sum())
        discordant = gains + losses
        pvalue = (
            float(stats.binomtest(gains, discordant, 0.5).pvalue)
            if discordant
            else 1.0
        )
        rows.append(
            {
                "factor": factor,
                "paired_rollouts": int(len(group)),
                "independent_groups": int(group["independent_group"].nunique()),
                "max_value_successes": int(baseline.sum()),
                "max_value_sr": float(baseline.mean()),
                "frozen_ranker_successes": int(method.sum()),
                "frozen_ranker_sr": float(method.mean()),
                "sr_delta": float(method.mean() - baseline.mean()),
                "frozen_gains": gains,
                "frozen_losses": losses,
                "same_outcome": int(len(group) - discordant),
                "mcnemar_exact_p": pvalue,
            }
        )
    return pd.DataFrame(rows)


def grouped_bootstrap(
    paired: pd.DataFrame,
    *,
    draws: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = (
        paired.groupby(["factor", "independent_group"], as_index=False)["success_delta"]
        .mean()
    )
    rng = np.random.default_rng(seed)
    samples: dict[str, np.ndarray] = {}
    for factor in EXPECTED_FACTORS:
        values = grouped.loc[grouped["factor"].eq(factor), "success_delta"].to_numpy(
            dtype=float
        )
        if len(values) == 0:
            raise ValueError(f"No independent groups for {factor}")
        indices = rng.integers(0, len(values), size=(draws, len(values)))
        samples[factor] = values[indices].mean(axis=1)
    samples["All"] = np.vstack([samples[factor] for factor in EXPECTED_FACTORS]).mean(
        axis=0
    )
    bootstrap = pd.concat(
        [
            pd.DataFrame(
                {"draw": np.arange(draws), "factor": factor, "sr_delta": values}
            )
            for factor, values in samples.items()
        ],
        ignore_index=True,
    )
    point = grouped.groupby("factor")["success_delta"].mean().to_dict()
    point["All"] = float(np.mean([point[factor] for factor in EXPECTED_FACTORS]))
    rows = []
    for factor in (*EXPECTED_FACTORS, "All"):
        values = samples[factor]
        rows.append(
            {
                "factor": factor,
                "independent_groups": int(
                    grouped["independent_group"].nunique()
                    if factor == "All"
                    else grouped.loc[grouped["factor"].eq(factor), "independent_group"].nunique()
                ),
                "sr_delta": float(point[factor]),
                "ci95_lower": float(np.quantile(values, 0.025)),
                "ci95_upper": float(np.quantile(values, 0.975)),
                "probability_delta_above_zero": float((values > 0).mean()),
            }
        )
    return bootstrap, pd.DataFrame(rows)


def q0_integrity(campaign_dir: Path) -> pd.DataFrame:
    frames = []
    columns = [
        *PAIR_KEYS,
        "planning_strategy",
        "candidate_values_json",
        "candidate_frozen_ranker_scores_json",
        "candidate_first_actions_json",
        "selected_sample_idx",
        "max_value_sample_idx",
        "planning_frozen_ranker_payload_sha256",
        "num_samples",
    ]
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "query_idx" not in trace:
            continue
        q0 = trace.loc[trace["query_idx"].eq(0)].copy()
        if "factor" not in q0 and "planning_frozen_ranker_factor" in q0:
            q0["factor"] = q0["planning_frozen_ranker_factor"]
        available = [column for column in columns if column in q0]
        if set(PAIR_KEYS) - set(available):
            continue
        frames.append(q0[available])
    if not frames:
        raise ValueError("No query-0 rows with complete pairing keys were found")
    rows = pd.concat(frames, ignore_index=True)
    pivot = rows.pivot_table(
        index=list(PAIR_KEYS),
        columns="planning_strategy",
        aggfunc="first",
    )
    pivot.columns = [f"{column}__{strategy}" for column, strategy in pivot.columns]
    pivot = pivot.reset_index()
    for column, tolerance in Q0_NUMERIC_TOLERANCES.items():
        def difference(row: pd.Series) -> float:
            baseline = np.asarray(json.loads(row[f"{column}__{BASELINE}"]), dtype=float)
            method = np.asarray(json.loads(row[f"{column}__{METHOD}"]), dtype=float)
            if baseline.shape != method.shape:
                return float("inf")
            if not np.array_equal(np.isnan(baseline), np.isnan(method)):
                return float("inf")
            finite = np.isfinite(baseline) & np.isfinite(method)
            if not finite.any():
                return 0.0
            return float(np.max(np.abs(baseline[finite] - method[finite])))

        pivot[f"{column}_max_abs_diff"] = pivot.apply(difference, axis=1)
        pivot[f"{column}_match"] = pivot[f"{column}_max_abs_diff"].le(tolerance)
    pivot["baseline_selected_argmax_value"] = (
        pivot[f"selected_sample_idx__{BASELINE}"].astype(int)
        == pivot[f"max_value_sample_idx__{BASELINE}"].astype(int)
    )
    pivot["frozen_selected_argmax_score"] = pivot.apply(
        lambda row: int(row[f"selected_sample_idx__{METHOD}"])
        == int(np.argmax(json.loads(row[f"candidate_frozen_ranker_scores_json__{METHOD}"]))),
        axis=1,
    )
    pivot["selectors_disagree"] = (
        pivot[f"selected_sample_idx__{BASELINE}"].astype(int)
        != pivot[f"selected_sample_idx__{METHOD}"].astype(int)
    )
    return pivot


def task_init_summary(paired: pd.DataFrame) -> pd.DataFrame:
    return (
        paired.groupby(
            [
                "factor",
                "case_id",
                "suite",
                "task_id",
                f"task_description__{BASELINE}",
                "init_state_id",
            ],
            as_index=False,
        )
        .agg(
            paired_rollouts=("success_delta", "size"),
            max_value_sr=(f"success__{BASELINE}", "mean"),
            frozen_ranker_sr=(f"success__{METHOD}", "mean"),
            sr_delta=("success_delta", "mean"),
            frozen_gains=("success_delta", lambda values: int((values == 1).sum())),
            frozen_losses=("success_delta", lambda values: int((values == -1).sum())),
        )
        .rename(columns={f"task_description__{BASELINE}": "task_description"})
    )


def failure_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    failed = episodes.loc[~episodes["success"]].copy()
    if failed.empty:
        return pd.DataFrame()
    return (
        failed.groupby(["factor", "planning_strategy", "failure_type"], as_index=False)
        .agg(episodes=("success", "size"), target_drops=("target_drop", "sum"))
        .sort_values(["factor", "planning_strategy", "episodes"], ascending=[True, True, False])
    )


def query_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    return (
        episodes.groupby(["factor", "planning_strategy"], as_index=False)
        .agg(
            episodes=("success", "size"),
            success_rate=("success", "mean"),
            mean_final_t=("final_t", "mean"),
            mean_queries=("num_queries", "mean"),
            selected_not_max_value_rate=("selected_not_max_value_rate", "mean"),
            mean_value_sacrifice=("mean_value_sacrifice", "mean"),
        )
    )


def prediction_error_summary(campaign_dir: Path) -> pd.DataFrame:
    metrics = (
        "prediction_error_future_image_mse",
        "prediction_error_future_image_ssim_global",
        "prediction_error_future_wrist_mse",
        "prediction_error_future_wrist_ssim_global",
        "prediction_error_future_proprio_l2",
        "prediction_error_value_abs_chunk_success",
        "prediction_error_value_abs_final_success",
    )
    episode_frames = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "planning_strategy" not in trace:
            continue
        trace = trace.loc[trace["planning_strategy"].isin({BASELINE, METHOD})].copy()
        if trace.empty:
            continue
        if "factor" not in trace:
            trace["factor"] = trace.get("planning_frozen_ranker_factor", "")
        available = [metric for metric in metrics if metric in trace]
        if not available:
            continue
        grouping = ["factor", "planning_strategy", "pair_id", "rollout_id"]
        episode = trace.groupby(grouping, as_index=False)[available].mean()
        episode_frames.append(episode)
    if not episode_frames:
        return pd.DataFrame()
    episodes = pd.concat(episode_frames, ignore_index=True)
    rows = []
    for (factor, strategy), group in episodes.groupby(
        ["factor", "planning_strategy"], sort=True
    ):
        row: dict[str, Any] = {
            "factor": factor,
            "planning_strategy": strategy,
            "episodes": int(len(group)),
        }
        for metric in metrics:
            if metric not in group:
                continue
            values = pd.to_numeric(group[metric], errors="coerce").dropna()
            row[f"{metric}__mean"] = float(values.mean()) if len(values) else np.nan
            row[f"{metric}__median"] = float(values.median()) if len(values) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def query_level_summary(campaign_dir: Path) -> pd.DataFrame:
    columns = (
        "query_idx",
        "max_value_selected",
        "max_value",
        "selected_value",
        "prediction_error_future_image_mse",
        "prediction_error_future_proprio_l2",
    )
    frames = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "planning_strategy" not in trace:
            continue
        trace = trace.loc[trace["planning_strategy"].isin({BASELINE, METHOD})].copy()
        if "factor" not in trace:
            trace["factor"] = trace.get("planning_frozen_ranker_factor", "")
        available = [column for column in columns if column in trace]
        frames.append(trace[["factor", "planning_strategy", *available]])
    if not frames:
        return pd.DataFrame()
    queries = pd.concat(frames, ignore_index=True)
    queries["selected_not_max_value"] = ~queries["max_value_selected"].astype(bool)
    queries["value_sacrifice"] = queries["max_value"] - queries["selected_value"]
    aggregations: dict[str, tuple[str, str]] = {
        "episodes_at_query": ("selected_not_max_value", "size"),
        "selected_not_max_value_rate": ("selected_not_max_value", "mean"),
        "mean_value_sacrifice": ("value_sacrifice", "mean"),
    }
    if "prediction_error_future_image_mse" in queries:
        aggregations["mean_future_image_mse"] = (
            "prediction_error_future_image_mse",
            "mean",
        )
    if "prediction_error_future_proprio_l2" in queries:
        aggregations["mean_future_proprio_l2"] = (
            "prediction_error_future_proprio_l2",
            "mean",
        )
    return (
        queries.groupby(["factor", "planning_strategy", "query_idx"], as_index=False)
        .agg(**aggregations)
        .sort_values(["factor", "planning_strategy", "query_idx"])
    )


def candidate_preference_summary(campaign_dir: Path) -> pd.DataFrame:
    """Describe how ranker choices differ from max-value choices in each pool."""
    rows = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        required = {
            "planning_strategy",
            "planning_frozen_ranker_factor",
            "selected_sample_idx",
            "candidate_values_json",
            "candidate_frozen_ranker_features_json",
        }
        if trace.empty or not required.issubset(trace):
            continue
        trace = trace.loc[trace["planning_strategy"].eq(METHOD)]
        for row in trace.itertuples(index=False):
            values = np.asarray(json.loads(row.candidate_values_json), dtype=float)
            features = np.asarray(
                json.loads(row.candidate_frozen_ranker_features_json), dtype=float
            )
            if features.shape != (len(values), len(FROZEN_FEATURES)):
                raise ValueError(
                    f"{path}: unexpected frozen feature shape {features.shape}"
                )
            selected = int(row.selected_sample_idx)
            max_value = int(np.nanargmax(values))
            if selected == max_value:
                continue
            means = np.nanmean(features, axis=0)
            scales = np.nanstd(features, axis=0)
            scales = np.where(np.isfinite(scales) & (scales > 1e-12), scales, 1.0)
            standardized = (features - means) / scales
            for index, feature in enumerate(FROZEN_FEATURES):
                rows.append(
                    {
                        "factor": str(row.planning_frozen_ranker_factor),
                        "feature": feature,
                        "selected_minus_max_value_z": float(
                            standardized[selected, index]
                            - standardized[max_value, index]
                        ),
                        "selected_minus_max_value_raw": float(
                            features[selected, index] - features[max_value, index]
                        ),
                    }
                )
    columns = [
        "factor",
        "feature",
        "disagreeing_queries",
        "mean_selected_minus_max_value_z",
        "median_selected_minus_max_value_z",
        "mean_selected_minus_max_value_raw",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows)
        .groupby(["factor", "feature"], as_index=False)
        .agg(
            disagreeing_queries=("selected_minus_max_value_z", "size"),
            mean_selected_minus_max_value_z=(
                "selected_minus_max_value_z",
                "mean",
            ),
            median_selected_minus_max_value_z=(
                "selected_minus_max_value_z",
                "median",
            ),
            mean_selected_minus_max_value_raw=(
                "selected_minus_max_value_raw",
                "mean",
            ),
        )
        .loc[:, columns]
    )


def integrity_summary(integrity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column, tolerance in Q0_NUMERIC_TOLERANCES.items():
        difference = integrity[f"{column}_max_abs_diff"]
        rows.append(
            {
                "quantity": column,
                "pairs": int(len(integrity)),
                "absolute_tolerance": float(tolerance),
                "max_abs_difference": float(difference.max()),
                "p95_abs_difference": float(difference.quantile(0.95)),
                "match_rate": float(integrity[f"{column}_match"].mean()),
            }
        )
    rows.append(
        {
            "quantity": "selector_disagreement",
            "pairs": int(len(integrity)),
            "absolute_tolerance": np.nan,
            "max_abs_difference": np.nan,
            "p95_abs_difference": np.nan,
            "match_rate": float(integrity["selectors_disagree"].mean()),
        }
    )
    return pd.DataFrame(rows)


def evaluate_gate(
    episodes: pd.DataFrame,
    paired: pd.DataFrame,
    intervals: pd.DataFrame,
    integrity: pd.DataFrame,
    *,
    expected_pairs_per_factor: int,
    expected_model_sha: str,
) -> dict[str, Any]:
    factor_counts = paired.groupby("factor").size().to_dict()
    complete_pair_count = bool(paired["pair_complete"].all())
    expected_counts = bool(
        all(factor_counts.get(factor, 0) == expected_pairs_per_factor for factor in EXPECTED_FACTORS)
    )
    macro = intervals.loc[intervals["factor"].eq("All")].iloc[0]
    per_factor = intervals.loc[intervals["factor"].isin(EXPECTED_FACTORS)]
    hashes = sorted(value for value in episodes["model_payload_sha256"].unique() if value)
    model_hash_matches = bool(hashes == [expected_model_sha]) if expected_model_sha else len(hashes) == 1
    q0_columns = [column for column in integrity if column.endswith("_match")]
    q0_candidates_match = bool(integrity[q0_columns].all().all())
    selectors_correct = bool(
        integrity["baseline_selected_argmax_value"].all()
        and integrity["frozen_selected_argmax_score"].all()
    )
    ranker_is_active = bool(integrity["selectors_disagree"].any())
    six_candidates = bool(
        episodes["candidate_count_min"].eq(6).all()
        and episodes["candidate_count_max"].eq(6).all()
    )
    no_material_regression = bool((per_factor["sr_delta"] >= -0.05).all())
    no_significant_regression = bool((per_factor["ci95_upper"] >= 0.0).all())
    macro_positive = bool(float(macro["ci95_lower"]) > 0.0)
    passed = bool(
        complete_pair_count
        and expected_counts
        and model_hash_matches
        and q0_candidates_match
        and selectors_correct
        and ranker_is_active
        and six_candidates
        and macro_positive
        and no_material_regression
        and no_significant_regression
    )
    return {
        "passed": passed,
        "complete_pairs": complete_pair_count,
        "expected_pairs_per_factor": int(expected_pairs_per_factor),
        "factor_pair_counts": {key: int(value) for key, value in factor_counts.items()},
        "expected_factor_counts": expected_counts,
        "model_payload_sha256": hashes,
        "model_hash_matches": model_hash_matches,
        "q0_candidate_pools_match": q0_candidates_match,
        "selectors_match_definitions": selectors_correct,
        "ranker_changes_at_least_one_query0_selection": ranker_is_active,
        "six_candidates_every_query": six_candidates,
        "macro_ci95_lower_above_zero": macro_positive,
        "no_factor_material_regression_below_minus_5pp": no_material_regression,
        "no_factor_ci95_entirely_below_zero": no_significant_regression,
    }


def _plot_success(summary: pd.DataFrame, output: Path) -> None:
    factors = list(EXPECTED_FACTORS)
    x = np.arange(len(factors), dtype=float)
    width = 0.36
    indexed = summary.set_index("factor")
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(x - width / 2, indexed.loc[factors, "max_value_sr"], width, label="maxV-H16", color="#4b5563")
    ax.bar(x + width / 2, indexed.loc[factors, "frozen_ranker_sr"], width, label="frozen-ranker-H16", color="#2563eb")
    ax.set_xticks(x, factors)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("terminal success rate")
    ax.set_title("Paired closed-loop LIBERO-PRO validation")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_intervals(intervals: pd.DataFrame, output: Path) -> None:
    scoped = intervals.loc[intervals["factor"].isin((*EXPECTED_FACTORS, "All"))].copy()
    order = [*EXPECTED_FACTORS, "All"]
    scoped["factor"] = pd.Categorical(scoped["factor"], categories=order, ordered=True)
    scoped = scoped.sort_values("factor")
    point = scoped["sr_delta"].to_numpy(float)
    low = scoped["ci95_lower"].to_numpy(float)
    high = scoped["ci95_upper"].to_numpy(float)
    y = np.arange(len(scoped), dtype=float)
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    for index, factor in enumerate(scoped["factor"].astype(str)):
        color = "#2d6a4f" if low[index] > 0 else "#2563eb"
        ax.errorbar(
            point[index],
            y[index],
            xerr=[[point[index] - low[index]], [high[index] - point[index]]],
            fmt="o",
            color=color,
            capsize=5,
            linewidth=2,
        )
    ax.axvline(0.0, color="#111827", linestyle="--", linewidth=1)
    ax.set_yticks(y, scoped["factor"].astype(str))
    ax.set_xlabel("SR delta: frozen ranker - max value")
    ax.set_title("Task/init grouped bootstrap 95% intervals")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_discordances(summary: pd.DataFrame, output: Path) -> None:
    factors = list(EXPECTED_FACTORS)
    indexed = summary.set_index("factor")
    x = np.arange(len(factors), dtype=float)
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(
        x - width / 2,
        indexed.loc[factors, "frozen_gains"],
        width,
        label="frozen gain",
        color="#2d6a4f",
    )
    ax.bar(
        x + width / 2,
        indexed.loc[factors, "frozen_losses"],
        width,
        label="frozen loss",
        color="#b91c1c",
    )
    ax.set_xticks(x, factors)
    ax.set_ylabel("paired rollout count")
    ax.set_title("Discordant terminal outcomes")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_selection(query: pd.DataFrame, output: Path) -> None:
    scoped = query.loc[query["planning_strategy"].eq(METHOD)].set_index("factor")
    factors = [factor for factor in EXPECTED_FACTORS if factor in scoped.index]
    if not factors:
        return
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(
        factors,
        scoped.loc[factors, "selected_not_max_value_rate"],
        color="#6d28d9",
    )
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("fraction of queries")
    ax.set_title("How often the frozen ranker rejects max value")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_failure_modes(failures: pd.DataFrame, output: Path) -> None:
    if failures.empty:
        return
    pivot = failures.pivot_table(
        index=["factor", "planning_strategy"],
        columns="failure_type",
        values="episodes",
        aggfunc="sum",
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
    ax.set_ylabel("failed episodes")
    ax.set_xlabel("factor / strategy")
    ax.set_title("Failure-mode composition")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(title="failure type", fontsize=8)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_prediction_errors(prediction: pd.DataFrame, output: Path) -> None:
    metric = "prediction_error_future_proprio_l2__mean"
    if prediction.empty or metric not in prediction:
        return
    pivot = prediction.pivot(index="factor", columns="planning_strategy", values=metric)
    factors = [factor for factor in EXPECTED_FACTORS if factor in pivot.index]
    if not factors:
        return
    x = np.arange(len(factors), dtype=float)
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.bar(
        x - width / 2,
        pivot.loc[factors, BASELINE],
        width,
        label="maxV-H16",
        color="#4b5563",
    )
    ax.bar(
        x + width / 2,
        pivot.loc[factors, METHOD],
        width,
        label="frozen-ranker-H16",
        color="#2563eb",
    )
    ax.set_xticks(x, factors)
    ax.set_ylabel("episode-macro future proprio L2")
    ax.set_title("Prediction error after executing selected chunks")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_query_selection(query_level: pd.DataFrame, output: Path) -> None:
    if query_level.empty:
        return
    scoped = query_level.loc[query_level["planning_strategy"].eq(METHOD)]
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    for factor in EXPECTED_FACTORS:
        group = scoped.loc[scoped["factor"].eq(factor)].sort_values("query_idx")
        if group.empty:
            continue
        ax.plot(
            group["query_idx"],
            group["selected_not_max_value_rate"],
            marker="o",
            linewidth=1.8,
            label=factor,
        )
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("query index")
    ax.set_ylabel("ranker rejects max value")
    ax.set_title("Frozen-ranker selection behavior over the episode")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_candidate_preferences(summary: pd.DataFrame, output: Path) -> None:
    if summary.empty:
        return
    matrix = (
        summary.pivot(
            index="factor",
            columns="feature",
            values="mean_selected_minus_max_value_z",
        )
        .reindex(index=EXPECTED_FACTORS, columns=FROZEN_FEATURES)
        .astype(float)
    )
    values = matrix.to_numpy()
    limit = max(float(np.nanmax(np.abs(values))), 0.1)
    fig, ax = plt.subplots(figsize=(13.5, 4.4))
    image = ax.imshow(values, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(np.arange(len(FROZEN_FEATURES)), FROZEN_FEATURES, rotation=55, ha="right")
    ax.set_yticks(np.arange(len(EXPECTED_FACTORS)), EXPECTED_FACTORS)
    ax.set_title("Frozen ranker preference relative to max-value candidate")
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            if np.isfinite(value):
                ax.text(
                    column,
                    row,
                    f"{value:+.2f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if abs(value) > 0.55 * limit else "black",
                )
    colorbar = fig.colorbar(image, ax=ax, pad=0.015)
    colorbar.set_label("selected minus maxV, within-pool z")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def write_results(
    output: Path,
    factor_summary: pd.DataFrame,
    intervals: pd.DataFrame,
    query: pd.DataFrame,
    task_summary: pd.DataFrame,
    failures: pd.DataFrame,
    prediction: pd.DataFrame,
    candidate_preference: pd.DataFrame,
    integrity_report: pd.DataFrame,
    gate: dict[str, Any],
    paired_count: int,
) -> None:
    lines = [
        "# Frozen H16 ranker: paired closed-loop result",
        "",
        f"- Complete paired rollouts: **{paired_count}**.",
        f"- Formal gate: **{'PASS' if gate['passed'] else 'FAIL'}**.",
        "- Primary endpoint: terminal success-rate delta, frozen ranker minus max value.",
        "",
        "## Terminal success",
        "",
        factor_summary.to_markdown(index=False),
        "",
        "## Grouped bootstrap",
        "",
        intervals.to_markdown(index=False),
        "",
        "## Selection and compute",
        "",
        query.to_markdown(index=False),
        "",
        "## Query-zero integrity",
        "",
        integrity_report.to_markdown(index=False),
        "",
        "## Prediction errors",
        "",
        prediction.to_markdown(index=False) if not prediction.empty else "No prediction-error columns found.",
        "",
        "Full query-index trajectories are in `query_level_summary.csv` and "
        "`ranker_selection_by_query.png`.",
        "",
        "## Candidate preference",
        "",
        candidate_preference.to_markdown(index=False)
        if not candidate_preference.empty
        else "Candidate-level frozen features were not recorded.",
        "",
        "## Failure modes",
        "",
        failures.to_markdown(index=False) if not failures.empty else "No failed episodes.",
        "",
        "## Task/init groups",
        "",
        task_summary.to_markdown(index=False),
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(gate, indent=2),
        "```",
    ]
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(
    campaign_dir: Path,
    output_dir: Path,
    *,
    draws: int,
    seed: int,
    expected_pairs_per_factor: int,
    expected_model_sha: str,
) -> dict[str, Any]:
    episodes, paired = load_campaign_episodes(campaign_dir)
    factor_summary = summarize_factors(paired)
    bootstrap, intervals = grouped_bootstrap(paired, draws=draws, seed=seed)
    integrity = q0_integrity(campaign_dir)
    task_summary = task_init_summary(paired)
    failures = failure_summary(episodes)
    queries = query_summary(episodes)
    prediction = prediction_error_summary(campaign_dir)
    query_level = query_level_summary(campaign_dir)
    candidate_preference = candidate_preference_summary(campaign_dir)
    integrity_report = integrity_summary(integrity)
    gate = evaluate_gate(
        episodes,
        paired,
        intervals,
        integrity,
        expected_pairs_per_factor=expected_pairs_per_factor,
        expected_model_sha=expected_model_sha,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    episodes.to_parquet(output_dir / "episode_outcomes.parquet", index=False)
    paired.to_csv(output_dir / "paired_seed_outcomes.csv", index=False)
    paired.loc[paired["discordance"].ne("same_outcome")].to_csv(
        output_dir / "discordant_pairs.csv", index=False
    )
    factor_summary.to_csv(output_dir / "paired_factor_summary.csv", index=False)
    intervals.to_csv(output_dir / "grouped_bootstrap_intervals.csv", index=False)
    bootstrap.to_parquet(output_dir / "grouped_bootstrap_draws.parquet", index=False)
    integrity.to_csv(output_dir / "q0_pairing_integrity.csv", index=False)
    task_summary.to_csv(output_dir / "task_init_summary.csv", index=False)
    failures.to_csv(output_dir / "failure_mode_summary.csv", index=False)
    queries.to_csv(output_dir / "query_compute_summary.csv", index=False)
    prediction.to_csv(output_dir / "prediction_error_summary.csv", index=False)
    query_level.to_csv(output_dir / "query_level_summary.csv", index=False)
    candidate_preference.to_csv(
        output_dir / "candidate_preference_summary.csv", index=False
    )
    integrity_report.to_csv(output_dir / "q0_integrity_summary.csv", index=False)
    _plot_success(factor_summary, output_dir / "paired_terminal_success.png")
    _plot_intervals(intervals, output_dir / "paired_sr_delta_ci.png")
    _plot_discordances(factor_summary, output_dir / "paired_discordances.png")
    _plot_selection(queries, output_dir / "ranker_selection_rate.png")
    _plot_failure_modes(failures, output_dir / "failure_mode_composition.png")
    _plot_prediction_errors(prediction, output_dir / "prediction_error_proprio.png")
    _plot_query_selection(query_level, output_dir / "ranker_selection_by_query.png")
    _plot_candidate_preferences(
        candidate_preference, output_dir / "candidate_preference_heatmap.png"
    )
    summary = {
        "campaign_dir": str(campaign_dir.resolve()),
        "paired_rollouts": int(len(paired)),
        "episode_rollouts": int(len(episodes)),
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
        "factor_summary": json.loads(factor_summary.to_json(orient="records")),
        "grouped_bootstrap_intervals": json.loads(
            intervals.to_json(orient="records")
        ),
        "query_compute_summary": json.loads(queries.to_json(orient="records")),
        "candidate_preference_summary": json.loads(
            candidate_preference.to_json(orient="records")
        ),
        "gate": gate,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_results(
        output_dir,
        factor_summary,
        intervals,
        queries,
        task_summary,
        failures,
        prediction,
        candidate_preference,
        integrity_report,
        gate,
        len(paired),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260829)
    parser.add_argument("--expected-pairs-per-factor", type=int, default=120)
    parser.add_argument("--expected-model-sha", default="")
    args = parser.parse_args()
    result = analyze(
        args.campaign_dir.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        draws=args.bootstrap_draws,
        seed=args.bootstrap_seed,
        expected_pairs_per_factor=args.expected_pairs_per_factor,
        expected_model_sha=args.expected_model_sha,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

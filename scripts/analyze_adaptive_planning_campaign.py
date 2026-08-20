#!/usr/bin/env python3
"""Summarize paired adaptive-planning campaigns from query-level traces."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAIR_KEYS = ["case_id", "suite", "task_id", "init_state_id", "rollout_seed"]
CONFIG_COLUMNS = [
    "planning_strategy",
    "planning_risk_lambda",
    "planning_difficulty_threshold",
    "planning_value_margin",
    "planning_uncertainty_margin",
    "planning_phase_fraction",
    "planning_short_open_loop_steps",
    "planning_surrogate_error_threshold",
]
ONLINE_METRICS = [
    "action_first_step_l2_std",
    "value_std",
    "value_range",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_action_internal_consistency_mean",
    "candidate_action_consensus_first_mean",
    "candidate_value_mean",
    "planning_predicted_proprio_error",
]
PREDICTION_ERROR_METRICS = [
    "prediction_error_future_image_mse",
    "prediction_error_future_wrist_mse",
    "prediction_error_future_proprio_l2",
]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def stratified_bootstrap_ci(
    frame: pd.DataFrame, *, seed: int = 20260813, samples: int = 10000
) -> tuple[float, float]:
    groups = [group["delta"].to_numpy(dtype=float) for _, group in frame.groupby("case_id")]
    rng = np.random.default_rng(seed)
    values = np.empty(samples, dtype=float)
    for index in range(samples):
        draws = [group[rng.integers(0, len(group), len(group))] for group in groups]
        values[index] = float(np.concatenate(draws).mean())
    low, high = np.quantile(values, [0.025, 0.975])
    return float(low), float(high)


def within_group_zscore(values: pd.Series, groups: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    means = numeric.groupby(groups).transform("mean")
    scales = numeric.groupby(groups).transform(lambda item: item.std(ddof=0))
    return ((numeric - means) / scales.replace(0.0, np.nan)).fillna(0.0)


def binary_auc(labels: pd.Series, scores: pd.Series) -> float:
    frame = pd.DataFrame(
        {"label": parse_bool(labels), "score": pd.to_numeric(scores, errors="coerce")}
    ).dropna()
    positives = int(frame["label"].sum())
    negatives = len(frame) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = frame["score"].rank(method="average")
    rank_sum = float(ranks.loc[frame["label"]].sum())
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def strategy_id(row: pd.Series) -> str:
    strategy = str(row["planning_strategy"])
    risk_lambda = float(row.get("planning_risk_lambda", 0.0))
    if strategy == "max_value":
        return "max_value"
    if strategy == "max_value_replay":
        return "max_value_replay"
    if strategy == "uncertainty_penalty_action":
        return f"action_l{risk_lambda:g}"
    if strategy == "uncertainty_penalty_action_replay":
        return f"action_l{risk_lambda:g}_replay"
    if strategy == "difficulty_gated_action":
        return f"difficulty_l{risk_lambda:g}_t{float(row['planning_difficulty_threshold']):g}"
    if strategy == "margin_gated_action":
        return (
            f"margin_l{risk_lambda:g}_v{float(row['planning_value_margin']):g}"
            f"_u{float(row['planning_uncertainty_margin']):g}"
        )
    if strategy == "consensus_action":
        return f"consensus_l{risk_lambda:g}"
    if strategy == "phase_gated_action":
        return f"phase_l{risk_lambda:g}_r{float(row['planning_phase_fraction']):g}"
    if strategy == "phase_requery_action":
        return (
            f"phase_requery_l{risk_lambda:g}_r{float(row['planning_phase_fraction']):g}"
            f"_h{int(row['planning_short_open_loop_steps'])}"
        )
    if strategy == "disagreement_requery_action":
        return f"requery_l{risk_lambda:g}_h{int(row['planning_short_open_loop_steps'])}"
    if strategy == "difficulty_gated_requery_action":
        return (
            f"difficulty_requery_l{risk_lambda:g}"
            f"_t{float(row['planning_difficulty_threshold']):g}"
            f"_h{int(row['planning_short_open_loop_steps'])}"
        )
    if strategy in {
        "surrogate_gated_requery_action",
        "surrogate_horizon_action",
        "surrogate_disagreement_requery_action",
        "phase_surrogate_requery_action",
    }:
        prefix = {
            "surrogate_gated_requery_action": "surrogate_gate",
            "surrogate_horizon_action": "surrogate_horizon",
            "surrogate_disagreement_requery_action": "surrogate_disagreement",
            "phase_surrogate_requery_action": "phase_surrogate",
        }[strategy]
        phase = (
            f"_r{float(row['planning_phase_fraction']):g}"
            if strategy == "phase_surrogate_requery_action"
            else ""
        )
        return (
            f"{prefix}_l{risk_lambda:g}{phase}"
            f"_e{float(row['planning_surrogate_error_threshold']):.12g}"
            f"_h{int(row['planning_short_open_loop_steps'])}"
        )
    return f"{strategy}_l{risk_lambda:g}"


def load_traces(campaign_dirs: Sequence[Path]) -> pd.DataFrame:
    frames = []
    for campaign_dir in campaign_dirs:
        for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
            frame = pd.read_parquet(path)
            if frame.empty:
                continue
            frame = frame.copy()
            frame["source_campaign"] = campaign_dir.name
            frame["source_run"] = (
                campaign_dir.name + "/" + path.name.removesuffix("__query_traces.parquet")
            )
            frames.append(frame)
    if not frames:
        roots = ", ".join(str(path / "runs") for path in campaign_dirs)
        raise FileNotFoundError(f"No query traces under: {roots}")
    traces = pd.concat(frames, ignore_index=True, sort=False)
    for column, default in {
        "planning_difficulty_threshold": 0.088588,
        "planning_value_margin": 0.002,
        "planning_uncertainty_margin": 0.0,
        "planning_phase_fraction": 0.5,
        "planning_short_open_loop_steps": 8,
        "planning_surrogate_error_threshold": 0.08841767562905925,
    }.items():
        if column not in traces:
            traces[column] = default
        traces[column] = pd.to_numeric(traces[column], errors="coerce").fillna(default)
    traces["strategy_id"] = traces.apply(strategy_id, axis=1)
    traces["success"] = parse_bool(traces["success"])
    return traces


def episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    order = traces.sort_values(["source_run", "query_idx"])
    group_keys = ["source_run", "strategy_id"] + PAIR_KEYS
    first = order.groupby(group_keys, dropna=False).first().reset_index()
    aggregates = (
        order.groupby(group_keys, dropna=False)
        .agg(
            num_queries_observed=("query_idx", "size"),
            rerank_rate=("max_value_selected", lambda values: 1.0 - parse_bool(values).mean()),
            gate_rate=("planning_query_risk_enabled", lambda values: parse_bool(values).mean()),
            requery_rate=("planning_requery_triggered", lambda values: parse_bool(values).mean()),
            surrogate_alarm_rate=("planning_surrogate_alarm", lambda values: parse_bool(values).mean()),
            mean_selected_open_loop_steps=("planning_selected_open_loop_steps", "mean"),
        )
        .reset_index()
    )
    keep = group_keys + CONFIG_COLUMNS + [
        "experiment_split",
        "num_open_loop_steps",
        "success",
        "final_t",
        "num_queries",
        "failure_type",
        "target_drop_candidate",
        "wrong_object_interaction_candidate",
    ]
    keep = [column for column in keep if column in first]
    episodes = first[keep].merge(aggregates, on=group_keys, how="left")
    final_t = pd.to_numeric(episodes["final_t"], errors="coerce").clip(lower=1)
    nominal_horizon = pd.to_numeric(
        episodes.get("num_open_loop_steps", pd.Series(16, index=episodes.index)),
        errors="coerce",
    ).fillna(16).clip(lower=1)
    episodes["nominal_queries_for_executed_steps"] = np.ceil(final_t / nominal_horizon)
    episodes["query_compute_ratio"] = (
        episodes["num_queries_observed"] / episodes["nominal_queries_for_executed_steps"]
    )
    return episodes


def paired_tables(
    episodes: pd.DataFrame, *, baseline_id: str = "max_value"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = episodes.loc[
        episodes["strategy_id"].eq(baseline_id),
        PAIR_KEYS + ["success", "num_queries_observed", "query_compute_ratio"],
    ]
    baseline = baseline.drop_duplicates(PAIR_KEYS).rename(
        columns={
            "success": "baseline_success",
            "num_queries_observed": "baseline_num_queries",
            "query_compute_ratio": "baseline_query_compute_ratio",
        }
    )
    rows = []
    paired_rows = []
    for (case_id, config), group in episodes.loc[
        ~episodes["strategy_id"].eq(baseline_id)
    ].groupby(["case_id", "strategy_id"], sort=True):
        paired = group.merge(baseline, on=PAIR_KEYS, how="inner")
        if paired.empty:
            continue
        paired["delta"] = paired["success"].astype(int) - paired["baseline_success"].astype(int)
        wins = int(paired["delta"].eq(1).sum())
        losses = int(paired["delta"].eq(-1).sum())
        rows.append(
            {
                "case_id": case_id,
                "baseline_strategy_id": baseline_id,
                "strategy_id": config,
                "paired_rollouts": len(paired),
                "baseline_successes": int(paired["baseline_success"].sum()),
                "strategy_successes": int(paired["success"].sum()),
                "baseline_success_rate": float(paired["baseline_success"].mean()),
                "strategy_success_rate": float(paired["success"].mean()),
                "delta_success_rate": float(paired["delta"].mean()),
                "wins": wins,
                "losses": losses,
                "ties": int(paired["delta"].eq(0).sum()),
                "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
                "baseline_mean_queries": float(paired["baseline_num_queries"].mean()),
                "mean_queries": float(group["num_queries_observed"].mean()),
                "query_overhead_ratio": float(
                    group["query_compute_ratio"].mean()
                    / paired["baseline_query_compute_ratio"].mean()
                ),
                "actual_query_count_ratio": float(
                    group["num_queries_observed"].mean()
                    / paired["baseline_num_queries"].mean()
                ),
                "mean_rerank_rate": float(group["rerank_rate"].mean()),
                "mean_gate_rate": float(group["gate_rate"].mean()),
                "mean_requery_rate": float(group["requery_rate"].mean()),
                "mean_surrogate_alarm_rate": float(
                    group["surrogate_alarm_rate"].mean()
                ),
                "mean_selected_open_loop_steps": float(
                    group["mean_selected_open_loop_steps"].mean()
                ),
            }
        )
        paired_rows.append(
            paired[PAIR_KEYS + ["strategy_id", "baseline_success", "success", "delta"]]
            .assign(baseline_strategy_id=baseline_id)
        )
    per_case = pd.DataFrame(rows)
    paired_seeds = pd.concat(paired_rows, ignore_index=True) if paired_rows else pd.DataFrame()
    return per_case, paired_seeds


def failure_mode_paired_table(
    episodes: pd.DataFrame, *, baseline_id: str = "max_value"
) -> pd.DataFrame:
    """Compare secondary interaction/failure labels on the same rollout seeds."""
    event_builders = {
        "target_drop_candidate": lambda frame: parse_bool(
            frame["target_drop_candidate"]
        ),
        "wrong_object_interaction_candidate": lambda frame: parse_bool(
            frame["wrong_object_interaction_candidate"]
        ),
        "timeout_no_goal": lambda frame: frame["failure_type"].eq(
            "timeout_no_goal"
        ),
        "kinematic_deadlock_candidate": lambda frame: frame["failure_type"].eq(
            "kinematic_deadlock_candidate"
        ),
    }

    def event_frame(frame: pd.DataFrame, suffix: str) -> pd.DataFrame:
        result = frame[PAIR_KEYS].copy()
        for name, builder in event_builders.items():
            result[f"{name}_{suffix}"] = builder(frame).to_numpy(dtype=bool)
        return result

    baseline_rows = episodes.loc[episodes["strategy_id"].eq(baseline_id)].drop_duplicates(
        PAIR_KEYS
    )
    baseline = event_frame(baseline_rows, "baseline")
    rows: list[dict[str, object]] = []
    for strategy_id, group in episodes.loc[
        ~episodes["strategy_id"].eq(baseline_id)
    ].groupby("strategy_id", sort=True):
        strategy = event_frame(group.drop_duplicates(PAIR_KEYS), "strategy")
        paired = baseline.merge(strategy, on=PAIR_KEYS, how="inner")
        for event in event_builders:
            baseline_event = parse_bool(paired[f"{event}_baseline"])
            strategy_event = parse_bool(paired[f"{event}_strategy"])
            reduced = int((baseline_event & ~strategy_event).sum())
            increased = int((~baseline_event & strategy_event).sum())
            rows.append(
                {
                    "baseline_strategy_id": baseline_id,
                    "strategy_id": strategy_id,
                    "event": event,
                    "paired_rollouts": len(paired),
                    "baseline_event_count": int(baseline_event.sum()),
                    "strategy_event_count": int(strategy_event.sum()),
                    "baseline_event_rate": float(baseline_event.mean()),
                    "strategy_event_rate": float(strategy_event.mean()),
                    "delta_event_rate": float(
                        strategy_event.mean() - baseline_event.mean()
                    ),
                    "event_reduced": reduced,
                    "event_increased": increased,
                    "event_unchanged": int(len(paired) - reduced - increased),
                    "mcnemar_exact_p": exact_mcnemar_p(reduced, increased),
                }
            )
    return pd.DataFrame(rows)


def pooled_table(per_case: pd.DataFrame, paired_seeds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, group in per_case.groupby("strategy_id", sort=True):
        total = int(group["paired_rollouts"].sum())
        wins = int(group["wins"].sum())
        losses = int(group["losses"].sum())
        strategy_successes = int(group["strategy_successes"].sum())
        baseline_successes = int(group["baseline_successes"].sum())
        seed_rows = paired_seeds.loc[paired_seeds["strategy_id"].eq(strategy)]
        ci_low, ci_high = stratified_bootstrap_ci(seed_rows)
        baseline_mean_queries = float(
            np.average(group["baseline_mean_queries"], weights=group["paired_rollouts"])
        )
        strategy_mean_queries = float(
            np.average(group["mean_queries"], weights=group["paired_rollouts"])
        )
        rows.append(
            {
                "baseline_strategy_id": str(group["baseline_strategy_id"].iloc[0]),
                "strategy_id": strategy,
                "num_cases": int(group["case_id"].nunique()),
                "paired_rollouts": total,
                "baseline_successes": baseline_successes,
                "strategy_successes": strategy_successes,
                "baseline_success_rate": baseline_successes / total,
                "strategy_success_rate": strategy_successes / total,
                "delta_success_rate": (strategy_successes - baseline_successes) / total,
                "delta_ci_low": ci_low,
                "delta_ci_high": ci_high,
                "min_case_delta": float(group["delta_success_rate"].min()),
                "max_case_delta": float(group["delta_success_rate"].max()),
                "wins": wins,
                "losses": losses,
                "ties": int(group["ties"].sum()),
                "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
                "baseline_mean_queries": baseline_mean_queries,
                "mean_queries": strategy_mean_queries,
                "query_overhead_ratio": float(
                    np.average(group["query_overhead_ratio"], weights=group["paired_rollouts"])
                ),
                "actual_query_count_ratio": strategy_mean_queries / baseline_mean_queries,
                "mean_requery_rate": float(
                    np.average(group["mean_requery_rate"], weights=group["paired_rollouts"])
                ),
                "mean_surrogate_alarm_rate": float(
                    np.average(
                        group["mean_surrogate_alarm_rate"],
                        weights=group["paired_rollouts"],
                    )
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["num_cases", "strategy_success_rate", "min_case_delta"],
        ascending=[False, False, False],
    )


def selection_tables(pooled: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the preregistered maximin/compute-aware screening rule."""
    if pooled.empty:
        return pd.DataFrame(), pd.DataFrame()
    max_cases = int(pooled["num_cases"].max())
    candidates = pooled.loc[pooled["num_cases"].eq(max_cases)].copy()

    def category(strategy_id: str) -> str | None:
        if strategy_id.startswith(("surrogate_", "phase_surrogate_")):
            return "surrogate_adaptive"
        if strategy_id.startswith(
            (
                "difficulty_l",
                "margin_l",
                "consensus_l",
                "phase_l",
                "requery_l",
                "difficulty_requery_l",
                "phase_requery_l",
            )
        ):
            return "non_surrogate_adaptive"
        return None

    candidates["selection_category"] = candidates["strategy_id"].map(category)
    candidates = candidates.loc[candidates["selection_category"].notna()].copy()
    if candidates.empty:
        return candidates, pd.DataFrame()
    candidates["selection_utility"] = (
        candidates["delta_success_rate"]
        + 0.5 * candidates["min_case_delta"]
        - 0.02 * (candidates["query_overhead_ratio"] - 1.0).clip(lower=0.0)
    )
    candidates = candidates.sort_values(
        [
            "selection_category",
            "selection_utility",
            "query_overhead_ratio",
            "strategy_id",
        ],
        ascending=[True, False, True, True],
    )
    selected = candidates.groupby("selection_category", sort=True).head(1).copy()
    return candidates, selected


def case_stratum(case_id: str) -> str:
    holdout_prefixes = ("spatial_mug_", "long_milk_", "goal_mug_")
    value = str(case_id)
    if value.endswith(("_surrogate_screen", "_surrogate_confirm")):
        return "new_ood_holdout" if value.startswith("new_ood_") else "known_boundary"
    return (
        "new_ood_holdout"
        if value.startswith(("new_ood_", *holdout_prefixes))
        else "known_boundary"
    )


def pooled_strata_tables(
    per_case: pd.DataFrame, paired_seeds: pd.DataFrame
) -> pd.DataFrame:
    if per_case.empty or paired_seeds.empty:
        return pd.DataFrame()
    per_case = per_case.copy()
    paired_seeds = paired_seeds.copy()
    per_case["case_stratum"] = per_case["case_id"].map(case_stratum)
    paired_seeds["case_stratum"] = paired_seeds["case_id"].map(case_stratum)
    frames = []
    for stratum in ("known_boundary", "new_ood_holdout"):
        case_rows = per_case.loc[per_case["case_stratum"].eq(stratum)].drop(
            columns="case_stratum"
        )
        seed_rows = paired_seeds.loc[paired_seeds["case_stratum"].eq(stratum)].drop(
            columns="case_stratum"
        )
        if case_rows.empty:
            continue
        pooled = pooled_table(case_rows, seed_rows)
        pooled.insert(0, "case_stratum", stratum)
        frames.append(pooled)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def frozen_selection_table(path: Path, pooled: pd.DataFrame) -> pd.DataFrame:
    selected = pd.read_csv(path)
    required = {"selection_category", "strategy_id"}
    if not required.issubset(selected.columns):
        raise ValueError(f"Frozen selection is missing columns: {sorted(required - set(selected))}")
    selected = selected[["selection_category", "strategy_id"]].drop_duplicates()
    result = selected.merge(pooled, on="strategy_id", how="left", validate="one_to_one")
    if result["paired_rollouts"].isna().any():
        missing = result.loc[result["paired_rollouts"].isna(), "strategy_id"].tolist()
        raise ValueError(f"Frozen strategies missing from campaign: {missing}")
    ordered = result["mcnemar_exact_p"].sort_values().index
    adjusted = pd.Series(index=result.index, dtype=float)
    running = 0.0
    count = len(result)
    for rank, index in enumerate(ordered):
        raw = float(result.loc[index, "mcnemar_exact_p"])
        running = max(running, min(1.0, raw * (count - rank)))
        adjusted.loc[index] = running
    result["mcnemar_holm_p"] = adjusted
    return result


def replay_control_tables(
    episodes: pd.DataFrame, traces: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    comparisons = [
        ("max_value", "max_value_replay"),
        ("action_l1", "action_l1_replay"),
    ]
    pair_frames = []
    summary_rows = []
    q0 = traces.loc[traces["query_idx"].eq(0)].copy()
    for reference_id, replay_id in comparisons:
        reference = episodes.loc[
            episodes["strategy_id"].eq(reference_id), PAIR_KEYS + ["success"]
        ].drop_duplicates(PAIR_KEYS)
        replay = episodes.loc[
            episodes["strategy_id"].eq(replay_id), PAIR_KEYS + ["success"]
        ].drop_duplicates(PAIR_KEYS)
        paired = reference.merge(
            replay,
            on=PAIR_KEYS,
            suffixes=("_reference", "_replay"),
        )
        if paired.empty:
            continue
        paired["reference_id"] = reference_id
        paired["replay_id"] = replay_id
        paired["outcome_disagreement"] = paired["success_reference"].ne(
            paired["success_replay"]
        )

        ref_q0 = q0.loc[
            q0["strategy_id"].eq(reference_id), PAIR_KEYS + ["candidate_values_json"]
        ].drop_duplicates(PAIR_KEYS)
        rep_q0 = q0.loc[
            q0["strategy_id"].eq(replay_id), PAIR_KEYS + ["candidate_values_json"]
        ].drop_duplicates(PAIR_KEYS)
        q0_paired = ref_q0.merge(
            rep_q0,
            on=PAIR_KEYS,
            suffixes=("_reference", "_replay"),
        )
        if not q0_paired.empty:
            q0_paired["q0_candidate_value_max_abs_diff"] = q0_paired.apply(
                lambda row: float(
                    np.max(
                        np.abs(
                            np.asarray(json.loads(row["candidate_values_json_reference"]))
                            - np.asarray(json.loads(row["candidate_values_json_replay"]))
                        )
                    )
                ),
                axis=1,
            )
            paired = paired.merge(
                q0_paired[PAIR_KEYS + ["q0_candidate_value_max_abs_diff"]],
                on=PAIR_KEYS,
                how="left",
            )
        else:
            paired["q0_candidate_value_max_abs_diff"] = np.nan

        pair_frames.append(paired)
        summary_rows.append(
            {
                "reference_id": reference_id,
                "replay_id": replay_id,
                "paired_rollouts": len(paired),
                "reference_success_rate": float(paired["success_reference"].mean()),
                "replay_success_rate": float(paired["success_replay"].mean()),
                "outcome_disagreements": int(paired["outcome_disagreement"].sum()),
                "outcome_disagreement_rate": float(paired["outcome_disagreement"].mean()),
                "q0_candidate_value_max_abs_diff_mean": float(
                    paired["q0_candidate_value_max_abs_diff"].mean()
                ),
                "q0_candidate_value_max_abs_diff_max": float(
                    paired["q0_candidate_value_max_abs_diff"].max()
                ),
            }
        )
    pairs = pd.concat(pair_frames, ignore_index=True) if pair_frames else pd.DataFrame()
    return pd.DataFrame(summary_rows), pairs


def difficulty_diagnostics(
    episodes: pd.DataFrame, traces: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_columns = [
        "candidate_value_mean",
        "candidate_value_std",
        "candidate_value_range",
        "candidate_action_internal_consistency_mean",
        "candidate_action_consensus_first_mean",
    ]
    available_metrics = [column for column in metric_columns if column in traces]
    q0 = traces.loc[
        traces["strategy_id"].eq("max_value") & traces["query_idx"].eq(0),
        PAIR_KEYS + ["success", "planning_difficulty_threshold"] + available_metrics,
    ].drop_duplicates(PAIR_KEYS)
    if q0.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    q0 = q0.copy()
    q0["difficulty_gate_on"] = q0["candidate_value_mean"].ge(
        q0["planning_difficulty_threshold"]
    )

    aggregations: dict[str, tuple[str, str]] = {
        "rollouts": ("rollout_seed", "size"),
        "baseline_success_rate": ("success", "mean"),
        "difficulty_gate_rate": ("difficulty_gate_on", "mean"),
    }
    for column in available_metrics:
        aggregations[f"q0_{column}_mean"] = (column, "mean")
        aggregations[f"q0_{column}_std"] = (column, "std")
    by_case = q0.groupby("case_id", as_index=False).agg(**aggregations)

    action = episodes.loc[
        episodes["strategy_id"].eq("action_l1"), PAIR_KEYS + ["success"]
    ].drop_duplicates(PAIR_KEYS).rename(columns={"success": "action_success"})
    actual_ids = sorted(
        strategy
        for strategy in episodes["strategy_id"].unique()
        if str(strategy).startswith("difficulty_l1_t")
    )
    paired = q0.rename(columns={"success": "baseline_success"}).merge(
        action, on=PAIR_KEYS, how="inner"
    )
    paired["counterfactual_gate_success"] = np.where(
        paired["difficulty_gate_on"],
        paired["action_success"],
        paired["baseline_success"],
    ).astype(bool)
    if actual_ids:
        actual = episodes.loc[
            episodes["strategy_id"].eq(actual_ids[0]), PAIR_KEYS + ["success"]
        ].drop_duplicates(PAIR_KEYS).rename(columns={"success": "actual_gate_success"})
        paired = paired.merge(actual, on=PAIR_KEYS, how="left")

    def summarize(group: pd.DataFrame, case_id: str) -> dict[str, float | int | str]:
        row: dict[str, float | int | str] = {
            "case_id": case_id,
            "paired_rollouts": len(group),
            "difficulty_gate_rate": float(group["difficulty_gate_on"].mean()),
            "baseline_success_rate": float(group["baseline_success"].mean()),
            "action_success_rate": float(group["action_success"].mean()),
            "counterfactual_gate_success_rate": float(
                group["counterfactual_gate_success"].mean()
            ),
        }
        row["counterfactual_delta_vs_baseline"] = (
            float(row["counterfactual_gate_success_rate"])
            - float(row["baseline_success_rate"])
        )
        if "actual_gate_success" in group:
            valid = group["actual_gate_success"].notna()
            row["actual_gate_paired_rollouts"] = int(valid.sum())
            row["actual_gate_success_rate"] = (
                float(group.loc[valid, "actual_gate_success"].mean()) if valid.any() else np.nan
            )
            row["actual_gate_delta_vs_baseline"] = (
                float(row["actual_gate_success_rate"])
                - float(group.loc[valid, "baseline_success"].mean())
                if valid.any()
                else np.nan
            )
        return row

    summaries = [
        summarize(group, str(case_id)) for case_id, group in paired.groupby("case_id")
    ]
    summaries.append(summarize(paired, "POOLED"))
    return q0, by_case, pd.DataFrame(summaries)


def prediction_error_correlations(traces: pd.DataFrame) -> pd.DataFrame:
    baseline = traces.loc[traces["strategy_id"].eq("max_value")].copy()
    rows = []
    for online_metric in ONLINE_METRICS:
        if online_metric not in baseline:
            continue
        for error_metric in PREDICTION_ERROR_METRICS:
            if error_metric not in baseline:
                continue
            frame = baseline[["case_id", online_metric, error_metric]].copy()
            frame[online_metric] = pd.to_numeric(frame[online_metric], errors="coerce")
            frame[error_metric] = pd.to_numeric(frame[error_metric], errors="coerce")
            frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
            if len(frame) < 4:
                continue
            raw = frame[online_metric].rank().corr(frame[error_metric].rank())
            x_rank = frame.groupby("case_id")[online_metric].rank(method="average")
            y_rank = frame.groupby("case_id")[error_metric].rank(method="average")
            x_controlled = within_group_zscore(
                x_rank, frame["case_id"]
            )
            y_controlled = within_group_zscore(
                y_rank, frame["case_id"]
            )
            rows.append(
                {
                    "online_metric": online_metric,
                    "prediction_error": error_metric,
                    "queries": len(frame),
                    "cases": int(frame["case_id"].nunique()),
                    "raw_spearman": float(raw),
                    "case_controlled_rank_correlation": float(
                        x_controlled.corr(y_controlled)
                    ),
                }
            )
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    return result.sort_values(
        "case_controlled_rank_correlation",
        key=lambda values: values.abs(),
        ascending=False,
    )


def surrogate_transfer_diagnostics(traces: pd.DataFrame) -> pd.DataFrame:
    required = {
        "case_id",
        "strategy_id",
        "planning_predicted_proprio_error",
        "prediction_error_future_proprio_l2",
    }
    if not required.issubset(traces.columns):
        return pd.DataFrame()
    baseline = traces.loc[traces["strategy_id"].eq("max_value")].copy()
    baseline["predicted_error"] = pd.to_numeric(
        baseline["planning_predicted_proprio_error"], errors="coerce"
    )
    baseline["actual_error"] = pd.to_numeric(
        baseline["prediction_error_future_proprio_l2"], errors="coerce"
    )
    baseline = baseline.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["predicted_error", "actual_error"]
    )
    if baseline.empty:
        return pd.DataFrame()
    baseline["case_stratum"] = baseline["case_id"].map(case_stratum)
    if "planning_surrogate_alarm" in baseline:
        baseline["alarm"] = parse_bool(baseline["planning_surrogate_alarm"])
    else:
        threshold = pd.to_numeric(
            baseline.get(
                "planning_surrogate_error_threshold",
                pd.Series(0.08841767562905925, index=baseline.index),
            ),
            errors="coerce",
        ).fillna(0.08841767562905925)
        baseline["alarm"] = baseline["predicted_error"].ge(threshold)

    def summarize(group: pd.DataFrame, stratum: str) -> dict[str, object]:
        group = group.copy()
        actual_q75 = group.groupby("case_id")["actual_error"].transform(
            lambda values: values.quantile(0.75)
        )
        group["case_relative_top_quartile"] = group["actual_error"].ge(actual_q75)
        x_rank = group.groupby("case_id")["predicted_error"].rank(method="average")
        y_rank = group.groupby("case_id")["actual_error"].rank(method="average")
        controlled_x = within_group_zscore(x_rank, group["case_id"])
        controlled_y = within_group_zscore(y_rank, group["case_id"])
        alarm = parse_bool(group["alarm"])
        high_error = parse_bool(group["case_relative_top_quartile"])
        alarm_count = int(alarm.sum())
        high_count = int(high_error.sum())
        median_actual = float(group["actual_error"].median())
        alarm_median = float(group.loc[alarm, "actual_error"].median()) if alarm_count else np.nan
        quiet_median = (
            float(group.loc[~alarm, "actual_error"].median()) if (~alarm).any() else np.nan
        )
        return {
            "case_stratum": stratum,
            "queries": len(group),
            "cases": int(group["case_id"].nunique()),
            "raw_spearman": float(
                group["predicted_error"].rank().corr(group["actual_error"].rank())
            ),
            "case_controlled_rank_correlation": float(controlled_x.corr(controlled_y)),
            "case_relative_top_quartile_auc": float(
                binary_auc(high_error, group["predicted_error"])
            ),
            "alarm_rate": float(alarm.mean()),
            "alarm_precision_top_quartile": (
                float((alarm & high_error).sum() / alarm_count) if alarm_count else np.nan
            ),
            "alarm_recall_top_quartile": (
                float((alarm & high_error).sum() / high_count) if high_count else np.nan
            ),
            "median_predicted_error": float(group["predicted_error"].median()),
            "median_actual_error": median_actual,
            "median_prediction_to_actual_ratio": (
                float(group["predicted_error"].median() / median_actual)
                if median_actual > 0.0
                else np.nan
            ),
            "median_actual_error_alarm": alarm_median,
            "median_actual_error_no_alarm": quiet_median,
            "alarm_actual_error_lift": (
                alarm_median / quiet_median
                if np.isfinite(alarm_median) and np.isfinite(quiet_median) and quiet_median > 0.0
                else np.nan
            ),
            "mean_absolute_log_error": float(
                np.abs(
                    np.log(np.clip(group["predicted_error"], 1e-10, None))
                    - np.log(np.clip(group["actual_error"], 1e-10, None))
                ).mean()
            ),
        }

    rows = [summarize(baseline, "all")]
    for stratum in ("known_boundary", "new_ood_holdout"):
        group = baseline.loc[baseline["case_stratum"].eq(stratum)]
        if not group.empty:
            rows.append(summarize(group, stratum))
    return pd.DataFrame(rows)


def early_failure_predictors(traces: pd.DataFrame, max_query: int = 3) -> pd.DataFrame:
    baseline = traces.loc[
        traces["strategy_id"].eq("max_value") & traces["query_idx"].le(max_query)
    ].copy()
    group_keys = PAIR_KEYS
    feature_frames = []
    for metric in ONLINE_METRICS:
        if metric not in baseline:
            continue
        grouped = baseline.groupby(group_keys, dropna=False)[metric]
        frame = grouped.agg(["mean", "max", "first", "last"]).reset_index()
        frame["delta"] = frame["last"] - frame["first"]
        frame = frame.drop(columns=["first", "last"]).rename(
            columns={name: f"{metric}__{name}" for name in ("mean", "max", "delta")}
        )
        feature_frames.append(frame)
    if not feature_frames:
        return pd.DataFrame()
    features = feature_frames[0]
    for frame in feature_frames[1:]:
        features = features.merge(frame, on=group_keys, how="outer")
    outcomes = (
        baseline.sort_values("query_idx")
        .groupby(group_keys, dropna=False)
        .first()[["success"]]
        .reset_index()
    )
    features = features.merge(outcomes, on=group_keys, how="inner")
    features["failed"] = ~parse_bool(features["success"])
    rows = []
    for feature in [column for column in features if "__" in column]:
        frame = features[["case_id", "failed", feature]].dropna()
        if len(frame) < 4:
            continue
        raw_auc = binary_auc(frame["failed"], frame[feature])
        controlled = within_group_zscore(frame[feature], frame["case_id"])
        controlled_auc = binary_auc(frame["failed"], controlled)
        rows.append(
            {
                "feature": feature,
                "episodes": len(frame),
                "failures": int(frame["failed"].sum()),
                "cases": int(frame["case_id"].nunique()),
                "raw_auc_high_predicts_fail": raw_auc,
                "case_controlled_auc_high_predicts_fail": controlled_auc,
                "case_controlled_oriented_auc": max(
                    controlled_auc, 1.0 - controlled_auc
                ),
                "risk_direction": "high" if controlled_auc >= 0.5 else "low",
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        "case_controlled_oriented_auc", ascending=False
    )


def save_plots(
    per_case: pd.DataFrame,
    pooled: pd.DataFrame,
    output_dir: Path,
    *,
    highlighted_strategy_ids: Sequence[str] = (),
) -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    complete = pooled.loc[pooled["num_cases"].eq(pooled["num_cases"].max())].head(15)
    selected = complete["strategy_id"].tolist()
    heat = per_case.loc[per_case["strategy_id"].isin(selected)].pivot(
        index="strategy_id", columns="case_id", values="delta_success_rate"
    )
    if not heat.empty:
        fig, ax = plt.subplots(figsize=(11, max(4, 0.45 * len(heat))))
        image = ax.imshow(heat.to_numpy(), cmap="RdYlGn", vmin=-0.5, vmax=0.5, aspect="auto")
        ax.set_xticks(range(len(heat.columns)), [str(value) for value in heat.columns], rotation=20, ha="right")
        ax.set_yticks(range(len(heat.index)), [str(value) for value in heat.index])
        for row in range(len(heat.index)):
            for column in range(len(heat.columns)):
                value = heat.iloc[row, column]
                if np.isfinite(value):
                    ax.text(column, row, f"{value:+.2f}", ha="center", va="center", fontsize=8)
        ax.set_title("Paired success delta relative to max(value)")
        fig.colorbar(image, ax=ax, label="success-rate delta")
        fig.tight_layout()
        fig.savefig(plot_dir / "paired_delta_heatmap.png", dpi=170)
        plt.close(fig)

    if not complete.empty:
        ordered = complete.sort_values("delta_success_rate")
        fig, ax = plt.subplots(figsize=(10, max(4, 0.45 * len(ordered))))
        colors = ["#2f855a" if value >= 0 else "#c53030" for value in ordered["delta_success_rate"]]
        deltas = ordered["delta_success_rate"].to_numpy(dtype=float)
        ci_errors = np.vstack(
            [
                deltas - ordered["delta_ci_low"].to_numpy(dtype=float),
                ordered["delta_ci_high"].to_numpy(dtype=float) - deltas,
            ]
        )
        ax.barh(
            ordered["strategy_id"],
            deltas,
            xerr=ci_errors,
            color=colors,
            error_kw={"ecolor": "#1a202c", "capsize": 3, "linewidth": 1},
        )
        ax.axvline(0.0, color="black", linewidth=1)
        ax.set_xlabel("Pooled paired success delta")
        ax.set_title("Adaptive planning comparison")
        fig.tight_layout()
        fig.savefig(plot_dir / "pooled_strategy_delta.png", dpi=170)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 7))
        adaptive = ordered["strategy_id"].str.contains("requery")
        ax.scatter(
            ordered.loc[~adaptive, "query_overhead_ratio"],
            ordered.loc[~adaptive, "delta_success_rate"],
            color="#2b6cb0",
            s=55,
            label="ranking/gating",
        )
        ax.scatter(
            ordered.loc[adaptive, "query_overhead_ratio"],
            ordered.loc[adaptive, "delta_success_rate"],
            color="#c05621",
            marker="s",
            s=60,
            label="adaptive horizon",
        )
        ax.errorbar(
            ordered["query_overhead_ratio"],
            ordered["delta_success_rate"],
            yerr=ci_errors,
            fmt="none",
            ecolor="#4a5568",
            elinewidth=1,
            capsize=3,
            alpha=0.8,
        )
        highlighted = set(highlighted_strategy_ids) | {"action_l1"}
        highlighted_rows = ordered.loc[ordered["strategy_id"].isin(highlighted)]
        if not highlighted_rows.empty:
            ax.scatter(
                highlighted_rows["query_overhead_ratio"],
                highlighted_rows["delta_success_rate"],
                facecolors="none",
                edgecolors="#111827",
                linewidths=1.5,
                s=125,
                zorder=4,
            )
        for _, row in highlighted_rows.iterrows():
            ax.annotate(
                row["strategy_id"],
                (row["query_overhead_ratio"], row["delta_success_rate"]),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )
        ax.axhline(0.0, color="black", linewidth=1)
        ax.axvline(1.0, color="black", linewidth=1, linestyle="--")
        ax.set_xlabel("Normalized model-query cost")
        ax.set_ylabel("Pooled paired success delta")
        ax.set_title("Success versus inference cost")
        ax.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / "success_compute_tradeoff.png", dpi=170)
        plt.close(fig)


def save_diagnostic_plots(
    error_correlations: pd.DataFrame,
    early_predictors: pd.DataFrame,
    output_dir: Path,
) -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    if not error_correlations.empty:
        top = error_correlations.head(12).iloc[::-1]
        labels = top["online_metric"] + " -> " + top["prediction_error"]
        fig, ax = plt.subplots(figsize=(11, max(5, 0.48 * len(top))))
        ax.barh(labels, top["case_controlled_rank_correlation"], color="#2f855a")
        ax.axvline(0.0, color="black", linewidth=1)
        ax.set_xlabel("Case-controlled rank correlation")
        ax.set_title("Online uncertainty versus next-chunk prediction error")
        fig.tight_layout()
        fig.savefig(plot_dir / "uncertainty_prediction_error_correlations.png", dpi=170)
        plt.close(fig)

    if not early_predictors.empty:
        top = early_predictors.head(12).iloc[::-1]
        colors = ["#c53030" if direction == "high" else "#2b6cb0" for direction in top["risk_direction"]]
        fig, ax = plt.subplots(figsize=(11, max(5, 0.48 * len(top))))
        ax.barh(top["feature"], top["case_controlled_oriented_auc"], color=colors)
        ax.axvline(0.5, color="black", linewidth=1, linestyle="--")
        ax.set_xlim(0.5, 1.0)
        ax.set_xlabel("Case-controlled oriented AUROC")
        ax.set_title("Early q=0..3 task-failure predictors")
        fig.tight_layout()
        fig.savefig(plot_dir / "early_failure_predictor_auc.png", dpi=170)
        plt.close(fig)


def write_report(
    campaign_dirs: Sequence[Path],
    output_dir: Path,
    episodes: pd.DataFrame,
    per_case: pd.DataFrame,
    pooled: pd.DataFrame,
    replay_summary: pd.DataFrame,
    selection_candidates: pd.DataFrame,
    selected: pd.DataFrame,
    difficulty_summary: pd.DataFrame,
    error_correlations: pd.DataFrame,
    surrogate_transfer: pd.DataFrame,
    early_predictors: pd.DataFrame,
    pooled_by_stratum: pd.DataFrame,
    frozen_results: pd.DataFrame,
    frozen_vs_action: pd.DataFrame,
    failure_modes: pd.DataFrame,
) -> None:
    max_cases = int(pooled["num_cases"].max()) if not pooled.empty else 0
    complete = pooled.loc[pooled["num_cases"].eq(max_cases)].head(12)

    def report_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
        except ValueError:
            return str(path)

    evidence_note = (
        "This is a frozen confirmatory evaluation on disjoint seeds: the two "
        "adaptive strategies and all hyperparameters were selected before these "
        "outcomes were observed."
        if not frozen_results.empty
        else (
            "These are calibration/screening results. A strategy becomes "
            "confirmatory only after its hyperparameters are frozen and rerun "
            "on disjoint seeds."
        )
    )
    key_findings: list[str] = []
    if not frozen_results.empty:
        for row in frozen_results.itertuples(index=False):
            key_findings.append(
                f"- **`{row.strategy_id}`:** {int(row.strategy_successes)}/"
                f"{int(row.paired_rollouts)} success versus "
                f"{int(row.baseline_successes)}/{int(row.paired_rollouts)} for "
                f"`max(value)`; delta {100 * row.delta_success_rate:+.1f} pp "
                f"(95% paired bootstrap CI "
                f"[{100 * row.delta_ci_low:+.1f}, {100 * row.delta_ci_high:+.1f}] pp), "
                f"Holm p={row.mcnemar_holm_p:.4g}, per-case delta "
                f"[{100 * row.min_case_delta:+.1f}, "
                f"{100 * row.max_case_delta:+.1f}] pp, normalized query cost "
                f"{row.query_overhead_ratio:.2f}x."
            )
        if not frozen_vs_action.empty:
            strongest = frozen_vs_action.sort_values(
                "delta_success_rate", ascending=False
            ).iloc[0]
            key_findings.append(
                f"- Against fixed `action_l1`, `{strongest['strategy_id']}` has "
                f"delta {100 * strongest['delta_success_rate']:+.1f} pp "
                f"(CI [{100 * strongest['delta_ci_low']:+.1f}, "
                f"{100 * strongest['delta_ci_high']:+.1f}] pp; exact McNemar "
                f"p={strongest['mcnemar_exact_p']:.4g})."
            )
        if not replay_summary.empty:
            noise = ", ".join(
                f"`{row.reference_id}` {100 * row.outcome_disagreement_rate:.1f}%"
                for row in replay_summary.itertuples(index=False)
            )
            key_findings.append(
                f"- Exact-replay outcome disagreement (empirical noise floor): {noise}."
            )
        if not early_predictors.empty:
            top = early_predictors.iloc[0]
            key_findings.append(
                f"- The best early q=0..3 failure feature is "
                f"`{top['feature']}` with case-controlled oriented AUROC "
                f"{top['case_controlled_oriented_auc']:.3f}; current metrics are "
                "stronger as within-state ranking signals than as a universal "
                "episode-failure threshold."
            )
        if not error_correlations.empty:
            top = error_correlations.iloc[0]
            key_findings.append(
                f"- Strongest next-chunk mechanism association: "
                f"`{top['online_metric']}` versus `{top['prediction_error']}`, "
                f"case-controlled rank correlation "
                f"{top['case_controlled_rank_correlation']:.3f}."
            )
        if not surrogate_transfer.empty:
            transfer = surrogate_transfer.loc[
                surrogate_transfer["case_stratum"].eq("all")
            ].iloc[0]
            key_findings.append(
                "- Frozen future-proprio surrogate transfer: case-controlled "
                f"rank correlation {transfer['case_controlled_rank_correlation']:.3f}, "
                "case-relative top-quartile AUROC "
                f"{transfer['case_relative_top_quartile_auc']:.3f}, alarm rate "
                f"{100 * transfer['alarm_rate']:.1f}%, and median calibration ratio "
                f"{transfer['median_prediction_to_actual_ratio']:.2f}x."
            )
    elif not selected.empty:
        for row in selected.itertuples(index=False):
            key_findings.append(
                f"- Calibration selected **`{row.strategy_id}`** for "
                f"`{row.selection_category}`: delta "
                f"{100 * row.delta_success_rate:+.1f} pp, worst-case delta "
                f"{100 * row.min_case_delta:+.1f} pp, normalized query cost "
                f"{row.query_overhead_ratio:.2f}x, selection utility "
                f"J={row.selection_utility:.3f}."
            )
    lines = [
        "# Adaptive planning campaign",
        "",
        "Sources: "
        + ", ".join(f"`{report_path(path)}`" for path in campaign_dirs)
        + ".",
        "",
        f"Loaded {len(episodes)} strategy executions across {episodes['case_id'].nunique()} cases.",
        "",
        "## Confirmatory interpretation"
        if not frozen_results.empty
        else "## Calibration interpretation",
        "",
        *key_findings,
        "",
        "## Pooled paired ranking",
        "",
        complete.to_markdown(index=False) if not complete.empty else "No complete paired results yet.",
        "",
        "![Pooled delta](plots/pooled_strategy_delta.png)",
        "",
        "![Success versus compute](plots/success_compute_tradeoff.png)",
        "",
        "## Per-case robustness",
        "",
        "![Per-case delta](plots/paired_delta_heatmap.png)",
        "",
        "## Replay noise floor",
        "",
        replay_summary.to_markdown(index=False)
        if not replay_summary.empty
        else "Replay controls are not complete yet.",
        "",
        "## Frozen confirmatory strategies"
        if not frozen_results.empty
        else "## Preregistered strategy selection",
        "",
        frozen_results.to_markdown(index=False)
        if not frozen_results.empty
        else selected[
            [
                "selection_category",
                "strategy_id",
                "selection_utility",
                "delta_success_rate",
                "min_case_delta",
                "query_overhead_ratio",
            ]
        ].to_markdown(index=False) if not selected.empty
        else "No eligible strategy is complete yet.",
        "",
        "The full eligible screening ranking is saved in `selection_candidates.csv`."
        if frozen_results.empty
        else "Strategies were frozen by the supplied screening selection file.",
        "",
        "### Against fixed action penalty (lambda=1)",
        "",
        frozen_vs_action.to_markdown(index=False)
        if not frozen_vs_action.empty
        else "Paired fixed-penalty comparison is unavailable.",
        "",
        "## Results by confirmatory stratum",
        "",
        pooled_by_stratum.to_markdown(index=False)
        if not pooled_by_stratum.empty
        else "Stratified results are unavailable.",
        "",
        "## Paired failure-mode diagnostics",
        "",
        failure_modes.to_markdown(index=False)
        if not failure_modes.empty
        else "Failure-mode diagnostics are unavailable.",
        "",
        "These labels are exploratory LIBERO-PRO heuristics, not official "
        "LIBERO-Safety constraints. Their unadjusted exact tests describe a "
        "possible change in failure mode and are not additional primary endpoints.",
        "",
        "## Difficulty-gate diagnostic",
        "",
        difficulty_summary.to_markdown(index=False)
        if not difficulty_summary.empty
        else "Difficulty diagnostics are not complete yet.",
        "",
        "`counterfactual_gate` combines separately executed max-value/action outcomes;",
        "`actual_gate` is the online gated policy and is the causal rollout result.",
        "",
        "## Mechanism diagnostics",
        "",
        "### Frozen future-proprio surrogate transfer",
        "",
        surrogate_transfer.to_markdown(index=False)
        if not surrogate_transfer.empty
        else "Surrogate transfer diagnostics are unavailable.",
        "",
        "Top case-controlled correlations between online uncertainty and next-chunk error:",
        "",
        "![Prediction error correlations](plots/uncertainty_prediction_error_correlations.png)",
        "",
        error_correlations.head(12).to_markdown(index=False)
        if not error_correlations.empty
        else "Prediction-error diagnostics are unavailable.",
        "",
        "Top early q=0..3 task-failure predictors:",
        "",
        "![Early failure AUROC](plots/early_failure_predictor_auc.png)",
        "",
        early_predictors.head(12).to_markdown(index=False)
        if not early_predictors.empty
        else "Early-failure diagnostics are unavailable.",
        "",
        "These mechanism tables are exploratory. In particular, they are not used to",
        "change the preregistered screening utility or confirmatory strategies.",
        "",
        evidence_note,
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument(
        "--additional-campaign-dir",
        type=Path,
        action="append",
        default=[],
        help="Additional campaign whose traces belong to the same calibration split.",
    )
    parser.add_argument(
        "--frozen-selection-csv",
        type=Path,
        default=None,
        help="Screening selection to evaluate without reselecting on these outcomes.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    campaign_dir = args.campaign_dir.resolve()
    campaign_dirs = [campaign_dir] + [path.resolve() for path in args.additional_campaign_dir]
    output_dir = (args.output_dir or (campaign_dir / "analysis" / "adaptive_summary")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    traces = load_traces(campaign_dirs)
    episodes = episode_table(traces)
    per_case, paired_seeds = paired_tables(episodes)
    pooled = pooled_table(per_case, paired_seeds)
    action_per_case, action_paired_seeds = paired_tables(
        episodes, baseline_id="action_l1"
    )
    pooled_vs_action = (
        pooled_table(action_per_case, action_paired_seeds)
        if not action_per_case.empty
        else pd.DataFrame()
    )
    pooled_by_stratum = pooled_strata_tables(per_case, paired_seeds)
    if args.frozen_selection_csv is None:
        selection_candidates, selected = selection_tables(pooled)
        frozen_results = pd.DataFrame()
    else:
        selection_candidates = pd.DataFrame()
        selected = pd.DataFrame()
        frozen_results = frozen_selection_table(
            args.frozen_selection_csv.resolve(), pooled
        )
    frozen_vs_action = pd.DataFrame()
    if not frozen_results.empty and not pooled_vs_action.empty:
        frozen_vs_action = frozen_results[["selection_category", "strategy_id"]].merge(
            pooled_vs_action, on="strategy_id", how="left", validate="one_to_one"
        )
    replay_summary, replay_pairs = replay_control_tables(episodes, traces)
    q0_difficulty, q0_difficulty_by_case, difficulty_summary = difficulty_diagnostics(
        episodes, traces
    )
    error_correlations = prediction_error_correlations(traces)
    surrogate_transfer = surrogate_transfer_diagnostics(traces)
    early_predictors = early_failure_predictors(traces)
    failure_modes = failure_mode_paired_table(episodes)
    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    per_case.to_csv(output_dir / "paired_by_case.csv", index=False)
    paired_seeds.to_csv(output_dir / "paired_seed_outcomes.csv", index=False)
    pooled.to_csv(output_dir / "pooled_strategies.csv", index=False)
    action_per_case.to_csv(output_dir / "paired_vs_action_l1_by_case.csv", index=False)
    action_paired_seeds.to_csv(
        output_dir / "paired_vs_action_l1_seed_outcomes.csv", index=False
    )
    pooled_vs_action.to_csv(output_dir / "pooled_vs_action_l1.csv", index=False)
    pooled_by_stratum.to_csv(output_dir / "pooled_by_stratum.csv", index=False)
    selection_candidates.to_csv(output_dir / "selection_candidates.csv", index=False)
    selected.to_csv(output_dir / "selected_for_confirmatory.csv", index=False)
    frozen_results.to_csv(output_dir / "frozen_confirmatory_results.csv", index=False)
    frozen_vs_action.to_csv(output_dir / "frozen_vs_action_l1.csv", index=False)
    replay_summary.to_csv(output_dir / "replay_control_summary.csv", index=False)
    replay_pairs.to_csv(output_dir / "replay_control_pairs.csv", index=False)
    q0_difficulty.to_csv(output_dir / "q0_difficulty_episodes.csv", index=False)
    q0_difficulty_by_case.to_csv(output_dir / "q0_difficulty_by_case.csv", index=False)
    difficulty_summary.to_csv(output_dir / "difficulty_gate_summary.csv", index=False)
    error_correlations.to_csv(output_dir / "prediction_error_correlations.csv", index=False)
    surrogate_transfer.to_csv(
        output_dir / "surrogate_transfer_diagnostics.csv", index=False
    )
    early_predictors.to_csv(output_dir / "early_failure_predictors_q0_3.csv", index=False)
    failure_modes.to_csv(output_dir / "paired_failure_modes.csv", index=False)
    highlighted = (
        frozen_results["strategy_id"].tolist()
        if not frozen_results.empty
        else selected["strategy_id"].tolist()
    )
    save_plots(
        per_case,
        pooled,
        output_dir,
        highlighted_strategy_ids=highlighted,
    )
    save_diagnostic_plots(error_correlations, early_predictors, output_dir)
    write_report(
        campaign_dirs,
        output_dir,
        episodes,
        per_case,
        pooled,
        replay_summary,
        selection_candidates,
        selected,
        difficulty_summary,
        error_correlations,
        surrogate_transfer,
        early_predictors,
        pooled_by_stratum,
        frozen_results,
        frozen_vs_action,
        failure_modes,
    )
    summary = {
        "campaign_dirs": [str(path) for path in campaign_dirs],
        "strategy_executions": int(len(episodes)),
        "cases": int(episodes["case_id"].nunique()),
        "strategies": int(episodes["strategy_id"].nunique()),
        "complete_strategy_cases": int(pooled["num_cases"].max()) if not pooled.empty else 0,
        "replay_controls": replay_summary.to_dict(orient="records"),
        "selected_for_confirmatory": selected.to_dict(orient="records"),
        "frozen_confirmatory_results": frozen_results.to_dict(orient="records"),
        "frozen_vs_action_l1": frozen_vs_action.to_dict(orient="records"),
        "difficulty_gate": difficulty_summary.to_dict(orient="records"),
        "surrogate_transfer": surrogate_transfer.to_dict(orient="records"),
        "paired_failure_modes": failure_modes.to_dict(orient="records"),
        "top_complete_strategies": pooled.head(10).to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

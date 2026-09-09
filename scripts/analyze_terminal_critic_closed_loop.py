#!/usr/bin/env python3
"""Analyze paired max-value versus terminal-grounded critic rollouts."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


BASELINE = "max_value"
METHOD = "terminal_grounded_critic"
EXPECTED_TASKS = (8, 9)
PAIR_KEYS = (
    "factor",
    "case_id",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_seed",
)
Q0_TOLERANCES = {
    "candidate_values_json": 5e-4,
    "candidate_first_actions_json": 5e-3,
}
VIDEO_PATTERN = re.compile(
    r"(?P<suite>.+)__task(?P<task>\d+)__init(?P<init>\d+)"
    r"__pair(?P<pair>\d+)__rollout(?P<rollout>\d+)__seed(?P<seed>\d+)"
    r"__success(?P<success>True|False)__t(?P<final_t>\d+)"
)


def _first(group: pd.DataFrame, column: str, default: Any) -> Any:
    return group[column].iloc[0] if column in group else default


def _last(group: pd.DataFrame, column: str, default: Any) -> Any:
    return group[column].iloc[-1] if column in group else default


def _episode_rows(path: Path) -> pd.DataFrame:
    trace = pd.read_parquet(path)
    if trace.empty or not {"pair_id", "rollout_id"}.issubset(trace):
        return pd.DataFrame()
    grouping = [
        column
        for column in (
            "suite",
            "task_id",
            "init_state_id",
            "rollout_seed",
            "pair_id",
            "rollout_id",
        )
        if column in trace
    ]
    rows = []
    for _episode_key, group in trace.groupby(grouping, dropna=False):
        group = group.sort_values("query_idx")
        strategy = str(_first(group, "planning_strategy", ""))
        if strategy not in {BASELINE, METHOD}:
            continue
        factor = str(
            _first(
                group,
                "factor",
                _first(group, "planning_terminal_critic_factor", "Object"),
            )
        )
        failure = str(_last(group, "failure_type", "unknown"))
        target_drop = bool(_last(group, "target_drop_candidate", False))
        wrong_object = bool(
            _last(group, "wrong_object_interaction_candidate", False)
        )
        violation = bool(_last(group, "official_safety_violation", False))
        deadlock = failure == "kinematic_deadlock_candidate"
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
                "switches": int(
                    group.get(
                        "planning_terminal_critic_switched",
                        pd.Series(False, index=group.index),
                    )
                    .fillna(False)
                    .astype(bool)
                    .sum()
                ),
                "switch_rate": float(
                    group.get(
                        "planning_terminal_critic_switched",
                        pd.Series(False, index=group.index),
                    )
                    .fillna(False)
                    .astype(bool)
                    .mean()
                ),
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
                    _first(group, "planning_terminal_critic_payload_sha256", "")
                ),
                "candidate_count_min": int(group["num_samples"].min()),
                "candidate_count_max": int(group["num_samples"].max()),
                "failure_type": failure,
                "target_drop": target_drop,
                "wrong_object": wrong_object,
                "deadlock": deadlock,
                "official_safety_violation": violation,
                "adverse_event": bool(
                    target_drop or wrong_object or deadlock or violation
                ),
            }
        )
    return pd.DataFrame(rows)


def load_campaign_episodes(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not paths:
        raise FileNotFoundError(f"No query traces under {campaign_dir / 'runs'}")
    frames = [_episode_rows(path) for path in paths]
    episodes = pd.concat(
        [frame for frame in frames if not frame.empty], ignore_index=True
    )
    if episodes.empty:
        raise ValueError("No max-value/terminal-critic episodes found")
    duplicated = episodes.duplicated([*PAIR_KEYS, "planning_strategy"], keep=False)
    if duplicated.any():
        example = episodes.loc[
            duplicated, [*PAIR_KEYS, "planning_strategy"]
        ].head()
        raise ValueError(f"Duplicate paired strategy outcomes:\n{example}")

    paired = episodes.pivot(index=list(PAIR_KEYS), columns="planning_strategy")
    paired.columns = [f"{column}__{strategy}" for column, strategy in paired.columns]
    paired = paired.reset_index()
    required = [f"success__{BASELINE}", f"success__{METHOD}"]
    paired["pair_complete"] = paired[required].notna().all(axis=1)
    complete = paired.loc[paired["pair_complete"]].copy()
    complete["success_delta"] = (
        complete[f"success__{METHOD}"].astype(float)
        - complete[f"success__{BASELINE}"].astype(float)
    )
    complete["adverse_delta"] = (
        complete[f"adverse_event__{METHOD}"].astype(float)
        - complete[f"adverse_event__{BASELINE}"].astype(float)
    )
    complete["discordance"] = np.select(
        [complete["success_delta"].eq(1), complete["success_delta"].eq(-1)],
        ["critic_rescue", "critic_harm"],
        default="same_outcome",
    )
    complete["independent_group"] = (
        complete["factor"].astype(str)
        + "|"
        + complete["case_id"].astype(str)
        + "|"
        + complete["suite"].astype(str)
        + "|"
        + complete["task_id"].astype(str)
        + "|"
        + complete["init_state_id"].astype(str)
    )
    complete.attrs["all_pair_count"] = len(paired)
    complete.attrs["incomplete_pair_count"] = int((~paired["pair_complete"]).sum())
    return episodes, complete


def _summary_row(label: str, group: pd.DataFrame) -> dict[str, Any]:
    baseline = group[f"success__{BASELINE}"].astype(bool)
    method = group[f"success__{METHOD}"].astype(bool)
    rescues = int((~baseline & method).sum())
    harms = int((baseline & ~method).sum())
    discordant = rescues + harms
    return {
        "scope": label,
        "paired_rollouts": int(len(group)),
        "independent_groups": int(group["independent_group"].nunique()),
        "max_value_successes": int(baseline.sum()),
        "max_value_sr": float(baseline.mean()),
        "terminal_critic_successes": int(method.sum()),
        "terminal_critic_sr": float(method.mean()),
        "sr_delta": float(method.mean() - baseline.mean()),
        "critic_rescues": rescues,
        "critic_harms": harms,
        "same_outcome": int(len(group) - discordant),
        "mcnemar_exact_p": float(
            stats.binomtest(rescues, discordant, 0.5).pvalue
            if discordant
            else 1.0
        ),
        "max_value_adverse_events": int(
            group[f"adverse_event__{BASELINE}"].astype(bool).sum()
        ),
        "terminal_critic_adverse_events": int(
            group[f"adverse_event__{METHOD}"].astype(bool).sum()
        ),
    }


def summarize_outcomes(paired: pd.DataFrame) -> pd.DataFrame:
    rows = [_summary_row("All", paired)]
    rows.extend(
        _summary_row(f"task_{int(task_id)}", group)
        for task_id, group in paired.groupby("task_id", sort=True)
    )
    return pd.DataFrame(rows)


def grouped_bootstrap(
    paired: pd.DataFrame, *, draws: int, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = paired.groupby("independent_group", as_index=False).agg(
        success_delta=("success_delta", "mean"),
        adverse_delta=("adverse_delta", "mean"),
    )
    values = grouped[["success_delta", "adverse_delta"]].to_numpy(dtype=float)
    if len(values) == 0:
        raise ValueError("No complete independent groups")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(draws, len(values)))
    samples = values[indices].mean(axis=1)
    rows = []
    for index, metric in enumerate(("success_delta", "adverse_delta")):
        distribution = samples[:, index]
        rows.append(
            {
                "metric": metric,
                "independent_groups": int(len(values)),
                "point": float(values[:, index].mean()),
                "ci95_lower": float(np.quantile(distribution, 0.025)),
                "ci95_upper": float(np.quantile(distribution, 0.975)),
                "probability_above_zero": float((distribution > 0).mean()),
            }
        )
    draws_frame = pd.DataFrame(
        {
            "draw": np.arange(draws),
            "success_delta": samples[:, 0],
            "adverse_delta": samples[:, 1],
        }
    )
    return draws_frame, pd.DataFrame(rows)


def _json_max_abs_difference(left: str, right: str) -> float:
    first = np.asarray(json.loads(left), dtype=float)
    second = np.asarray(json.loads(right), dtype=float)
    if first.shape != second.shape or not np.array_equal(
        np.isnan(first), np.isnan(second)
    ):
        return float("inf")
    finite = np.isfinite(first) & np.isfinite(second)
    return float(np.max(np.abs(first[finite] - second[finite]))) if finite.any() else 0.0


def q0_integrity(campaign_dir: Path) -> pd.DataFrame:
    columns = [
        *PAIR_KEYS,
        "planning_strategy",
        *Q0_TOLERANCES,
        "selected_sample_idx",
        "max_value_sample_idx",
        "num_samples",
        "planning_terminal_critic_payload_sha256",
        "planning_terminal_critic_switched",
        "planning_terminal_critic_proposed_idx",
        "planning_terminal_critic_advantage_lcb",
        "planning_terminal_critic_risk_ucb_proposed",
        "planning_terminal_critic_risk_ucb_baseline",
    ]
    frames = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "query_idx" not in trace:
            continue
        q0 = trace.loc[
            trace["query_idx"].eq(0)
            & trace["planning_strategy"].isin({BASELINE, METHOD})
        ].copy()
        if "factor" not in q0:
            q0["factor"] = q0.get("planning_terminal_critic_factor", "Object")
        available = [column for column in columns if column in q0]
        if set(PAIR_KEYS) - set(available):
            continue
        frames.append(q0[available])
    if not frames:
        raise ValueError("No query-zero rows with pairing keys")
    rows = pd.concat(frames, ignore_index=True)
    pivot = rows.pivot_table(
        index=list(PAIR_KEYS), columns="planning_strategy", aggfunc="first"
    )
    pivot.columns = [f"{column}__{strategy}" for column, strategy in pivot.columns]
    pivot = pivot.reset_index()
    for column, tolerance in Q0_TOLERANCES.items():
        pivot[f"{column}_max_abs_diff"] = pivot.apply(
            lambda row: _json_max_abs_difference(
                row[f"{column}__{BASELINE}"], row[f"{column}__{METHOD}"]
            ),
            axis=1,
        )
        pivot[f"{column}_match"] = pivot[
            f"{column}_max_abs_diff"
        ].le(tolerance)
    pivot["baseline_selected_argmax_value"] = (
        pivot[f"selected_sample_idx__{BASELINE}"].astype(int)
        == pivot[f"max_value_sample_idx__{BASELINE}"].astype(int)
    )
    switched = pivot[f"planning_terminal_critic_switched__{METHOD}"].astype(bool)
    selected = pivot[f"selected_sample_idx__{METHOD}"].astype(int)
    proposed = pivot[f"planning_terminal_critic_proposed_idx__{METHOD}"].astype(int)
    max_value = pivot[f"max_value_sample_idx__{METHOD}"].astype(int)
    certified = (
        pivot[f"planning_terminal_critic_advantage_lcb__{METHOD}"].astype(float)
        > 0.0
    ) & (
        pivot[f"planning_terminal_critic_risk_ucb_proposed__{METHOD}"].astype(float)
        <= pivot[f"planning_terminal_critic_risk_ucb_baseline__{METHOD}"].astype(float)
        + 1e-12
    )
    pivot["critic_selection_valid"] = np.where(
        switched,
        selected.eq(proposed) & proposed.ne(max_value) & certified,
        selected.eq(max_value),
    )
    pivot["critic_switched"] = switched
    return pivot


def query_diagnostics(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "planning_strategy" not in trace:
            continue
        scoped = trace.loc[trace["planning_strategy"].isin({BASELINE, METHOD})].copy()
        if "factor" not in scoped:
            scoped["factor"] = scoped.get(
                "planning_terminal_critic_factor", "Object"
            )
        frames.append(scoped)
    queries = pd.concat(frames, ignore_index=True)
    queries["value_sacrifice"] = queries["max_value"] - queries["selected_value"]
    queries["critic_switched"] = queries.get(
        "planning_terminal_critic_switched",
        pd.Series(False, index=queries.index),
    ).astype(bool)
    summary = (
        queries.groupby(["planning_strategy", "query_idx"], as_index=False)
        .agg(
            query_rows=("success", "size"),
            switch_rate=("critic_switched", "mean"),
            mean_value_sacrifice=("value_sacrifice", "mean"),
            mean_advantage_lcb=("planning_terminal_critic_advantage_lcb", "mean"),
            mean_risk_ucb_proposed=(
                "planning_terminal_critic_risk_ucb_proposed",
                "mean",
            ),
            mean_risk_ucb_baseline=(
                "planning_terminal_critic_risk_ucb_baseline",
                "mean",
            ),
        )
        .sort_values(["planning_strategy", "query_idx"])
    )
    fallback = (
        queries.loc[queries["planning_strategy"].eq(METHOD)]
        .groupby("planning_terminal_critic_fallback_reason", as_index=False)
        .agg(query_rows=("success", "size"), switches=("critic_switched", "sum"))
        .sort_values("query_rows", ascending=False)
    )
    return summary, fallback


def episode_compute_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    return (
        episodes.groupby("planning_strategy", as_index=False)
        .agg(
            episodes=("success", "size"),
            success_rate=("success", "mean"),
            mean_final_t=("final_t", "mean"),
            mean_queries=("num_queries", "mean"),
            mean_switches=("switches", "mean"),
            switch_rate=("switch_rate", "mean"),
            mean_value_sacrifice=("mean_value_sacrifice", "mean"),
        )
    )


def failure_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    failed = episodes.loc[~episodes["success"]]
    if failed.empty:
        return pd.DataFrame()
    return (
        failed.groupby(["planning_strategy", "failure_type"], as_index=False)
        .agg(episodes=("success", "size"), target_drops=("target_drop", "sum"))
        .sort_values(["planning_strategy", "episodes"], ascending=[True, False])
    )


def prediction_error_summary(campaign_dir: Path) -> pd.DataFrame:
    metrics = (
        "prediction_error_future_image_mse",
        "prediction_error_future_wrist_mse",
        "prediction_error_future_proprio_l2",
        "prediction_error_value_abs_chunk_success",
        "prediction_error_value_abs_final_success",
    )
    rows = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty:
            continue
        available = [metric for metric in metrics if metric in trace]
        for strategy, group in trace.groupby("planning_strategy"):
            if strategy not in {BASELINE, METHOD}:
                continue
            row: dict[str, Any] = {
                "source_run": path.name.removesuffix("__query_traces.parquet"),
                "planning_strategy": strategy,
                "query_rows": int(len(group)),
            }
            for metric in available:
                values = pd.to_numeric(group[metric], errors="coerce")
                row[f"{metric}__mean"] = float(values.mean())
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    run_level = pd.DataFrame(rows)
    numeric = [column for column in run_level if column.endswith("__mean")]
    return run_level.groupby("planning_strategy", as_index=False)[numeric].mean()


def integrity_summary(integrity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column, tolerance in Q0_TOLERANCES.items():
        values = integrity[f"{column}_max_abs_diff"]
        rows.append(
            {
                "quantity": column,
                "pairs": int(len(integrity)),
                "tolerance": float(tolerance),
                "max_abs_difference": float(values.max()),
                "match_rate": float(integrity[f"{column}_match"].mean()),
            }
        )
    rows.extend(
        [
            {
                "quantity": "baseline_selector_valid",
                "pairs": int(len(integrity)),
                "tolerance": np.nan,
                "max_abs_difference": np.nan,
                "match_rate": float(
                    integrity["baseline_selected_argmax_value"].mean()
                ),
            },
            {
                "quantity": "critic_selector_valid",
                "pairs": int(len(integrity)),
                "tolerance": np.nan,
                "max_abs_difference": np.nan,
                "match_rate": float(integrity["critic_selection_valid"].mean()),
            },
        ]
    )
    return pd.DataFrame(rows)


def evaluate_gate(
    episodes: pd.DataFrame,
    paired: pd.DataFrame,
    intervals: pd.DataFrame,
    integrity: pd.DataFrame,
    *,
    expected_pairs_per_task: int,
    expected_model_sha: str,
    expected_candidates: int,
) -> dict[str, Any]:
    task_counts = paired.groupby("task_id").size().to_dict()
    success_interval = intervals.loc[
        intervals["metric"].eq("success_delta")
    ].iloc[0]
    expected_counts = bool(
        set(task_counts) == set(EXPECTED_TASKS)
        and all(count == expected_pairs_per_task for count in task_counts.values())
    )
    hashes = sorted(
        value for value in episodes["model_payload_sha256"].unique() if value
    )
    hash_ok = hashes == [expected_model_sha] if expected_model_sha else len(hashes) == 1
    pool_matches = bool(
        integrity[[f"{column}_match" for column in Q0_TOLERANCES]].all().all()
    )
    selectors_valid = bool(
        integrity["baseline_selected_argmax_value"].all()
        and integrity["critic_selection_valid"].all()
    )
    candidate_count_ok = bool(
        episodes["candidate_count_min"].eq(expected_candidates).all()
        and episodes["candidate_count_max"].eq(expected_candidates).all()
    )
    switches = int(
        episodes.loc[episodes["planning_strategy"].eq(METHOD), "switches"].sum()
    )
    rescue_count = int(paired["success_delta"].eq(1).sum())
    harm_count = int(paired["success_delta"].eq(-1).sum())
    adverse_delta = int(
        paired[f"adverse_event__{METHOD}"].sum()
        - paired[f"adverse_event__{BASELINE}"].sum()
    )
    point_positive = bool(success_interval["point"] > 0.0)
    checks = {
        "all_pairs_complete": paired.attrs.get("incomplete_pair_count", 0) == 0,
        "expected_pairs_per_task": expected_counts,
        "model_hash_matches": hash_ok,
        "query0_candidate_pools_match": pool_matches,
        "selectors_follow_frozen_rule": selectors_valid,
        "candidate_count_matches_model": candidate_count_ok,
        "critic_is_active": switches > 0,
        "positive_net_rescues": rescue_count > harm_count,
        "positive_grouped_sr_point_estimate": point_positive,
        "adverse_event_regression_at_most_one": adverse_delta <= 1,
    }
    return {
        "passed": bool(all(checks.values())),
        "strong_terminal_claim": bool(success_interval["ci95_lower"] > 0.0),
        "checks": checks,
        "task_pair_counts": {str(key): int(value) for key, value in task_counts.items()},
        "model_payload_sha256": hashes,
        "critic_switches": switches,
        "critic_rescues": rescue_count,
        "critic_harms": harm_count,
        "adverse_event_delta": adverse_delta,
        "success_delta": float(success_interval["point"]),
        "success_delta_ci95": [
            float(success_interval["ci95_lower"]),
            float(success_interval["ci95_upper"]),
        ],
    }


def video_index(campaign_dir: Path, output_dir: Path, paired: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for path in sorted((campaign_dir / "videos").rglob("*.mp4")):
        match = VIDEO_PATTERN.search(path.name)
        if match is None:
            continue
        strategy = next(
            (name for name in (METHOD, BASELINE) if f"__{name}__l" in str(path)),
            "unknown",
        )
        rows.append(
            {
                "suite": match.group("suite"),
                "task_id": int(match.group("task")),
                "init_state_id": int(match.group("init")),
                "rollout_seed": int(match.group("seed")),
                "planning_strategy": strategy,
                "video_success": match.group("success") == "True",
                "final_t": int(match.group("final_t")),
                "video_path": str(path.resolve()),
            }
        )
    videos = pd.DataFrame(rows)
    if videos.empty:
        return videos
    labels = paired[
        ["suite", "task_id", "init_state_id", "rollout_seed", "discordance"]
    ]
    videos = videos.merge(
        labels,
        on=["suite", "task_id", "init_state_id", "rollout_seed"],
        how="left",
    )
    videos.to_csv(output_dir / "video_index.csv", index=False)

    cards = []
    for keys, group in videos.groupby(
        ["task_id", "init_state_id", "rollout_seed", "discordance"], dropna=False
    ):
        task, init_state, seed, discordance = keys
        players = []
        for row in group.sort_values("planning_strategy").itertuples(index=False):
            relative = os.path.relpath(row.video_path, output_dir)
            players.append(
                "<div><h4>"
                + html.escape(f"{row.planning_strategy}: success={row.video_success}")
                + "</h4><video controls preload='metadata' width='480' src='"
                + html.escape(relative)
                + "'></video></div>"
            )
        cards.append(
            "<section><h3>"
            + html.escape(
                f"task={task}, init={init_state}, seed={seed}, {discordance}"
            )
            + "</h3><div class='pair'>"
            + "".join(players)
            + "</div></section>"
        )
    document = (
        "<!doctype html><meta charset='utf-8'><title>Terminal critic videos</title>"
        "<style>body{font-family:sans-serif;margin:24px}.pair{display:flex;gap:16px;"
        "flex-wrap:wrap}section{border-bottom:1px solid #ccc;padding-bottom:20px}</style>"
        "<h1>Paired terminal-critic rollout videos</h1>"
        + "".join(cards)
    )
    (output_dir / "video_index.html").write_text(document, encoding="utf-8")
    return videos


def _write_plots(
    outcome: pd.DataFrame,
    intervals: pd.DataFrame,
    query: pd.DataFrame,
    failures: pd.DataFrame,
    output_dir: Path,
) -> None:
    tasks = outcome.loc[outcome["scope"].str.startswith("task_")]
    positions = np.arange(len(tasks))
    width = 0.36
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(positions - width / 2, tasks["max_value_sr"], width, label="max(value)")
    axis.bar(
        positions + width / 2,
        tasks["terminal_critic_sr"],
        width,
        label="terminal critic",
    )
    axis.set_xticks(positions, tasks["scope"])
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Terminal success rate")
    axis.set_title("Paired closed-loop success")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "paired_terminal_success.png", dpi=180)
    plt.close(figure)

    success = intervals.loc[intervals["metric"].eq("success_delta")].iloc[0]
    figure, axis = plt.subplots(figsize=(7, 2.8))
    axis.errorbar(
        [success["point"]],
        [0],
        xerr=[
            [success["point"] - success["ci95_lower"]],
            [success["ci95_upper"] - success["point"]],
        ],
        fmt="o",
        capsize=5,
    )
    axis.axvline(0.0, color="black", linestyle="--", linewidth=1)
    axis.set_yticks([0], ["Object"])
    axis.set_xlabel("SR delta: terminal critic - max(value)")
    axis.set_title("Task/init grouped bootstrap 95% CI")
    axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "paired_sr_delta_ci.png", dpi=180)
    plt.close(figure)

    scoped = query.loc[query["planning_strategy"].eq(METHOD)]
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(scoped["query_idx"], scoped["switch_rate"], marker="o")
    axis.set_ylim(0.0, 1.0)
    axis.set_xlabel("Query index")
    axis.set_ylabel("Switch rate")
    axis.set_title("Conservative critic interventions")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "critic_switch_rate_by_query.png", dpi=180)
    plt.close(figure)

    if not failures.empty:
        pivot = failures.pivot_table(
            index="planning_strategy",
            columns="failure_type",
            values="episodes",
            aggfunc="sum",
            fill_value=0,
        )
        figure, axis = plt.subplots(figsize=(9, 4.8))
        pivot.plot(kind="bar", stacked=True, ax=axis, colormap="tab20")
        axis.set_ylabel("Failed episodes")
        axis.set_xlabel("")
        axis.set_title("Failure-mode composition")
        axis.grid(axis="y", alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / "failure_mode_composition.png", dpi=180)
        plt.close(figure)


def write_results(
    output_dir: Path,
    outcome: pd.DataFrame,
    intervals: pd.DataFrame,
    compute: pd.DataFrame,
    fallback: pd.DataFrame,
    failures: pd.DataFrame,
    prediction: pd.DataFrame,
    integrity: pd.DataFrame,
    gate: dict[str, Any],
    video_count: int,
) -> None:
    lines = [
        "# Terminal-grounded critic: paired closed-loop result",
        "",
        f"- Formal deployment gate: **{'PASS' if gate['passed'] else 'FAIL'}**.",
        f"- CI-supported terminal claim: **{'YES' if gate['strong_terminal_claim'] else 'NO'}**.",
        f"- Indexed videos: **{video_count}**.",
        "",
        "## Terminal success",
        "",
        outcome.to_markdown(index=False),
        "",
        "## Grouped bootstrap",
        "",
        intervals.to_markdown(index=False),
        "",
        "## Selection and compute",
        "",
        compute.to_markdown(index=False),
        "",
        "## Fallback reasons",
        "",
        fallback.to_markdown(index=False),
        "",
        "## Query-zero integrity",
        "",
        integrity.to_markdown(index=False),
        "",
        "## Prediction errors",
        "",
        prediction.to_markdown(index=False)
        if not prediction.empty
        else "No prediction-error columns found.",
        "",
        "## Failure modes",
        "",
        failures.to_markdown(index=False) if not failures.empty else "No failed episodes.",
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(gate, indent=2),
        "```",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(
    campaign_dir: Path,
    output_dir: Path,
    *,
    draws: int,
    seed: int,
    expected_pairs_per_task: int,
    expected_model_sha: str,
    expected_candidates: int,
) -> dict[str, Any]:
    episodes, paired = load_campaign_episodes(campaign_dir)
    if set(episodes["factor"]) != {"Object"}:
        raise ValueError(f"Expected only Object, got {sorted(episodes['factor'].unique())}")
    outcome = summarize_outcomes(paired)
    bootstrap, intervals = grouped_bootstrap(paired, draws=draws, seed=seed)
    q0 = q0_integrity(campaign_dir)
    integrity = integrity_summary(q0)
    query, fallback = query_diagnostics(campaign_dir)
    compute = episode_compute_summary(episodes)
    failures = failure_summary(episodes)
    prediction = prediction_error_summary(campaign_dir)
    gate = evaluate_gate(
        episodes,
        paired,
        intervals,
        q0,
        expected_pairs_per_task=expected_pairs_per_task,
        expected_model_sha=expected_model_sha,
        expected_candidates=expected_candidates,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    episodes.to_parquet(output_dir / "episode_outcomes.parquet", index=False)
    paired.to_csv(output_dir / "paired_seed_outcomes.csv", index=False)
    paired.loc[paired["discordance"].ne("same_outcome")].to_csv(
        output_dir / "discordant_pairs.csv", index=False
    )
    outcome.to_csv(output_dir / "paired_outcome_summary.csv", index=False)
    intervals.to_csv(output_dir / "grouped_bootstrap_intervals.csv", index=False)
    bootstrap.to_parquet(output_dir / "grouped_bootstrap_draws.parquet", index=False)
    q0.to_csv(output_dir / "q0_pairing_integrity.csv", index=False)
    integrity.to_csv(output_dir / "q0_integrity_summary.csv", index=False)
    query.to_csv(output_dir / "query_level_summary.csv", index=False)
    fallback.to_csv(output_dir / "fallback_reason_summary.csv", index=False)
    compute.to_csv(output_dir / "episode_compute_summary.csv", index=False)
    failures.to_csv(output_dir / "failure_mode_summary.csv", index=False)
    prediction.to_csv(output_dir / "prediction_error_summary.csv", index=False)
    videos = video_index(campaign_dir, output_dir, paired)
    _write_plots(outcome, intervals, query, failures, output_dir)
    write_results(
        output_dir,
        outcome,
        intervals,
        compute,
        fallback,
        failures,
        prediction,
        integrity,
        gate,
        len(videos),
    )
    summary = {
        "campaign_dir": str(campaign_dir.resolve()),
        "paired_rollouts": int(len(paired)),
        "episode_rollouts": int(len(episodes)),
        "outcome_summary": json.loads(outcome.to_json(orient="records")),
        "grouped_bootstrap": json.loads(intervals.to_json(orient="records")),
        "gate": gate,
        "video_count": int(len(videos)),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=5000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260830)
    parser.add_argument("--expected-pairs-per-task", type=int, default=60)
    parser.add_argument("--expected-model-sha", default="")
    parser.add_argument("--expected-candidates", type=int, default=8)
    args = parser.parse_args()
    result = analyze(
        args.campaign_dir.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        draws=args.bootstrap_draws,
        seed=args.bootstrap_seed,
        expected_pairs_per_task=args.expected_pairs_per_task,
        expected_model_sha=args.expected_model_sha,
        expected_candidates=args.expected_candidates,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

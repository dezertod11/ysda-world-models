#!/usr/bin/env python3
"""Build the frozen LIBERO-PRO Object baseline leaderboard from campaign traces."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METHOD_LABELS = {
    "first": "Cosmos Policy (no planning)",
    "max_value": "Cosmos Policy + max(value)",
    "disagreement_requery_action": "Ours: risk-aware + adaptive requery",
}
METHOD_ORDER = list(METHOD_LABELS.values())
FACTOR_ORDER = ["Object", "Position", "Environment"]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def parse_int_spec(value: Any) -> list[int]:
    result: list[int] = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lower, upper = part.split("-", 1)
            result.extend(range(int(lower), int(upper) + 1))
        else:
            result.append(int(part))
    return result


def factor_from_suite(suite: str) -> str:
    if suite == "libero_object_object":
        return "Object"
    if suite == "libero_object_env":
        return "Environment"
    if suite == "libero_object_temp":
        return "Position"
    raise ValueError(f"Unsupported LIBERO-PRO Object suite: {suite}")


def method_from_strategy(strategy: str) -> str:
    try:
        return METHOD_LABELS[strategy]
    except KeyError as error:
        raise ValueError(f"Unsupported benchmark strategy: {strategy}") from error


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def task_cluster_ci(
    task_values: Sequence[float], *, seed: int = 20260825, samples: int = 10000
) -> tuple[float, float]:
    values = np.asarray(task_values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(samples, len(values)), replace=True).mean(axis=1)
    low, high = np.quantile(draws, [0.025, 0.975])
    return float(low), float(high)


def _read_trace(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def _trace_paths_for_prefix(run_dir: Path, prefix: str) -> list[Path]:
    parquet = sorted(run_dir.glob(f"{prefix}*__query_traces.parquet"))
    if parquet:
        return parquet
    return sorted(run_dir.glob(f"{prefix}*__query_traces.csv"))


def load_campaign_traces(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest_path = campaign_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_dir = campaign_dir / "runs"
    frames: list[pd.DataFrame] = []
    inventory: list[dict[str, Any]] = []

    for job in manifest["jobs"]:
        env: Mapping[str, str] = job["environment"]
        prefix = env.get("LIBERO_PRO_PLANNING_GRID_PREFIX", "")
        if not prefix:
            continue
        suite = env["LIBERO_PRO_PLANNING_GRID_SUITES"]
        factor = factor_from_suite(suite)
        level = env.get("LIBERO_PRO_POSITION_LEVEL", "")
        expected = (
            len(parse_int_spec(env["LIBERO_PRO_PLANNING_GRID_TASK_IDS"]))
            * len(parse_int_spec(env["LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS"]))
            * int(env["LIBERO_PRO_PLANNING_GRID_MAX_ROLLOUTS_PER_INIT"])
        )
        paths = _trace_paths_for_prefix(run_dir, prefix)
        actual_for_job = 0
        methods_for_job: set[str] = set()
        for path in paths:
            frame = _read_trace(path)
            if frame.empty:
                continue
            frame = frame.copy()
            frame["source_job"] = job["name"]
            frame["source_trace"] = path.stem.removesuffix("__query_traces")
            frame["factor"] = factor
            frame["position_level"] = level
            frames.append(frame)
            strategy = str(frame["planning_strategy"].dropna().iloc[0])
            methods_for_job.add(method_from_strategy(strategy))
            episode_columns = [
                "suite",
                "task_id",
                "init_state_id",
                "rollout_seed",
            ]
            actual_for_job += len(frame.drop_duplicates(episode_columns))
        method = ""
        if len(methods_for_job) == 1:
            method = next(iter(methods_for_job))
        elif not paths:
            strategy_spec = env.get("LIBERO_PRO_PLANNING_GRID_STRATEGY_LAMBDAS", "")
            strategy = strategy_spec.split(":", 1)[0].strip()
            method = METHOD_LABELS.get(strategy, strategy)
        inventory.append(
            {
                "job": job["name"],
                "factor": factor,
                "position_level": level,
                "method": method,
                "expected_episodes": expected,
                "observed_episodes": actual_for_job,
                "complete": actual_for_job >= expected,
                "trace_files": len(paths),
            }
        )

    if not frames:
        raise FileNotFoundError(f"No query traces found under {run_dir}")
    return pd.concat(frames, ignore_index=True, sort=False), pd.DataFrame(inventory)


def build_episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "source_trace",
        "factor",
        "position_level",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
    ]
    traces = traces.copy()
    traces["success"] = parse_bool(traces["success"])
    traces["planning_requery_triggered"] = parse_bool(
        traces.get("planning_requery_triggered", pd.Series(False, index=traces.index))
    )
    num_samples = traces.get("num_samples", pd.Series(1, index=traces.index))
    query_idx = traces.get("query_idx", pd.Series(0, index=traces.index))
    traces["num_samples"] = pd.to_numeric(num_samples, errors="coerce").fillna(1)
    traces["query_idx"] = pd.to_numeric(query_idx, errors="coerce").fillna(0)
    traces = traces.sort_values(keys + ["query_idx"])

    aggregates = (
        traces.groupby(keys, dropna=False)
        .agg(
            observed_queries=("query_idx", "size"),
            candidate_generations=("num_samples", "sum"),
            adaptive_requeries=("planning_requery_triggered", "sum"),
        )
        .reset_index()
    )
    episodes = traces.drop_duplicates(keys, keep="last").merge(aggregates, on=keys, how="left")
    episodes["method"] = episodes["planning_strategy"].map(method_from_strategy)
    episodes["task_id"] = pd.to_numeric(episodes["task_id"], errors="raise").astype(int)
    episodes["init_state_id"] = pd.to_numeric(episodes["init_state_id"], errors="raise").astype(int)
    episodes["rollout_seed"] = pd.to_numeric(episodes["rollout_seed"], errors="raise").astype(int)
    final_t = episodes.get("final_t", pd.Series(np.nan, index=episodes.index))
    episodes["final_t"] = pd.to_numeric(final_t, errors="coerce")
    fixed_horizon_queries = np.ceil(episodes["final_t"].clip(lower=1) / 16.0)
    episodes["query_multiplier_vs_h16"] = episodes["observed_queries"] / fixed_horizon_queries
    return episodes


def score_tables(episodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    position = episodes.loc[episodes["factor"].eq("Position")].copy()
    non_position = episodes.loc[~episodes["factor"].eq("Position")].copy()
    position_cells = (
        position.groupby(["method", "factor", "task_id", "position_level"], dropna=False)
        .agg(success_rate=("success", "mean"), episodes=("success", "size"))
        .reset_index()
    )
    non_position_cells = (
        non_position.assign(position_level="all")
        .groupby(["method", "factor", "task_id", "position_level"], dropna=False)
        .agg(success_rate=("success", "mean"), episodes=("success", "size"))
        .reset_index()
    )
    cells = pd.concat([non_position_cells, position_cells], ignore_index=True)
    task_scores = (
        cells.groupby(["method", "factor", "task_id"], dropna=False)
        .agg(success_rate=("success_rate", "mean"), cells=("success_rate", "size"), episodes=("episodes", "sum"))
        .reset_index()
    )

    rows: list[dict[str, Any]] = []
    for (method, factor), group in task_scores.groupby(["method", "factor"], sort=False):
        low, high = task_cluster_ci(group["success_rate"].to_numpy())
        episode_subset = episodes.loc[
            episodes["method"].eq(method) & episodes["factor"].eq(factor)
        ]
        rows.append(
            {
                "method": method,
                "factor": factor,
                "success_rate": float(group["success_rate"].mean()),
                "ci95_low": low,
                "ci95_high": high,
                "successes": int(episode_subset["success"].sum()),
                "episodes": int(len(episode_subset)),
                "tasks": int(group["task_id"].nunique()),
            }
        )
    scores = pd.DataFrame(rows)

    leaderboard = scores.pivot(index="method", columns="factor", values="success_rate")
    leaderboard = leaderboard.reindex(index=METHOD_ORDER, columns=FACTOR_ORDER)
    leaderboard["Mean"] = leaderboard.mean(axis=1, skipna=False)
    leaderboard = leaderboard.reset_index()
    return cells, task_scores, scores.merge(
        leaderboard[["method", "Mean"]], on="method", how="left"
    )


def paired_comparisons(episodes: pd.DataFrame) -> pd.DataFrame:
    pair_keys = [
        "factor",
        "position_level",
        "task_id",
        "init_state_id",
        "rollout_seed",
    ]
    rows: list[dict[str, Any]] = []
    comparison_pairs = [
        (METHOD_LABELS["max_value"], METHOD_LABELS["first"]),
        (METHOD_LABELS["disagreement_requery_action"], METHOD_LABELS["first"]),
        (METHOD_LABELS["disagreement_requery_action"], METHOD_LABELS["max_value"]),
    ]
    for factor in FACTOR_ORDER:
        factor_rows = episodes.loc[episodes["factor"].eq(factor)]
        for candidate, reference in comparison_pairs:
            left = factor_rows.loc[
                factor_rows["method"].eq(candidate), pair_keys + ["success"]
            ]
            right = factor_rows.loc[
                factor_rows["method"].eq(reference), pair_keys + ["success"]
            ]
            if left.duplicated(pair_keys).any() or right.duplicated(pair_keys).any():
                raise ValueError(
                    f"Duplicate paired episode keys for {factor}: {candidate} vs {reference}"
                )
            merged = left.merge(
                right, on=pair_keys, suffixes=("_candidate", "_reference")
            )
            if merged.empty:
                continue
            merged["delta"] = (
                merged["success_candidate"].astype(float)
                - merged["success_reference"].astype(float)
            )
            per_task = merged.groupby("task_id")["delta"].mean()
            low, high = task_cluster_ci(per_task.to_numpy())
            wins = int((merged["delta"] > 0).sum())
            losses = int((merged["delta"] < 0).sum())
            rows.append(
                {
                    "factor": factor,
                    "candidate": candidate,
                    "reference": reference,
                    "paired_episodes": int(len(merged)),
                    "delta_success_rate": float(per_task.mean()),
                    "ci95_low": low,
                    "ci95_high": high,
                    "wins": wins,
                    "losses": losses,
                    "ties": int((merged["delta"] == 0).sum()),
                    "mcnemar_p": exact_mcnemar_p(wins, losses),
                }
            )
    return pd.DataFrame(rows)


def compute_table(episodes: pd.DataFrame) -> pd.DataFrame:
    return (
        episodes.groupby(["method", "factor"], dropna=False)
        .agg(
            episodes=("success", "size"),
            mean_queries=("observed_queries", "mean"),
            mean_candidate_generations=("candidate_generations", "mean"),
            mean_adaptive_requeries=("adaptive_requeries", "mean"),
            mean_query_multiplier_vs_h16=("query_multiplier_vs_h16", "mean"),
            mean_executed_steps=("final_t", "mean"),
        )
        .reset_index()
    )


def plot_scores(scores: pd.DataFrame, output_path: Path) -> None:
    fig, axis = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(FACTOR_ORDER), dtype=float)
    width = 0.25
    for index, method in enumerate(METHOD_ORDER):
        rows = scores.loc[scores["method"].eq(method)].set_index("factor").reindex(FACTOR_ORDER)
        values = rows["success_rate"].to_numpy(dtype=float)
        lower = values - rows["ci95_low"].to_numpy(dtype=float)
        upper = rows["ci95_high"].to_numpy(dtype=float) - values
        axis.bar(x + (index - 1) * width, values, width, label=method)
        axis.errorbar(
            x + (index - 1) * width,
            values,
            yerr=np.vstack([lower, upper]),
            fmt="none",
            color="black",
            capsize=3,
            linewidth=1,
        )
    axis.set_xticks(x, FACTOR_ORDER)
    axis.set_ylim(0.0, 1.0)
    axis.set_ylabel("Success rate")
    axis.set_title("LIBERO-PRO Object baseline comparison")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=1, frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _percent(value: float) -> str:
    return "" if not np.isfinite(value) else f"{100.0 * value:.1f}%"


def write_report(
    output_path: Path,
    campaign_dir: Path,
    leaderboard: pd.DataFrame,
    inventory: pd.DataFrame,
    comparisons: pd.DataFrame,
) -> None:
    table = leaderboard.copy()
    for column in FACTOR_ORDER + ["Mean"]:
        table[column] = table[column].map(_percent)
    complete = bool(inventory["complete"].all())
    lines = [
        "# LIBERO-PRO Object baseline results",
        "",
        f"Campaign: `{campaign_dir}`",
        "",
        f"Status: **{'complete' if complete else 'partial'}** "
        f"({int(inventory['observed_episodes'].sum())}/{int(inventory['expected_episodes'].sum())} method-episodes).",
        "",
        "## Primary leaderboard",
        "",
        table.to_markdown(index=False),
        "",
        "`Position` is the equal-weight macro-average over x/y shifts 0.1...0.5; `Mean` is the equal-weight mean of Object, Position, and Environment.",
        "",
        "## Paired comparisons",
        "",
    ]
    if comparisons.empty:
        lines.append("No complete paired comparisons are available yet.")
    else:
        shown = comparisons.copy()
        for column in ["delta_success_rate", "ci95_low", "ci95_high"]:
            shown[column] = shown[column].map(_percent)
        lines.append(shown.to_markdown(index=False))
    lines.extend(
        [
            "",
            "Intervals use a 10,000-sample task-cluster bootstrap. McNemar p-values use only paired discordant outcomes and are descriptive until the benchmark protocol is confirmed.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def analyze(campaign_dir: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    traces, inventory = load_campaign_traces(campaign_dir)
    episodes = build_episode_table(traces)
    cells, task_scores, scores = score_tables(episodes)
    leaderboard = scores.pivot(index="method", columns="factor", values="success_rate")
    leaderboard = leaderboard.reindex(index=METHOD_ORDER, columns=FACTOR_ORDER)
    leaderboard["Mean"] = leaderboard.mean(axis=1, skipna=False)
    leaderboard = leaderboard.reset_index()
    comparisons = paired_comparisons(episodes)
    compute = compute_table(episodes)

    outputs = {
        "episodes": output_dir / "episodes.csv",
        "inventory": output_dir / "run_inventory.csv",
        "cells": output_dir / "cell_scores.csv",
        "tasks": output_dir / "task_scores.csv",
        "scores": output_dir / "factor_scores.csv",
        "leaderboard": output_dir / "leaderboard.csv",
        "comparisons": output_dir / "paired_comparisons.csv",
        "compute": output_dir / "compute_metrics.csv",
        "plot": output_dir / "success_rate_by_perturbation.png",
        "report": output_dir / "RESULTS.md",
    }
    episodes.to_csv(outputs["episodes"], index=False)
    inventory.to_csv(outputs["inventory"], index=False)
    cells.to_csv(outputs["cells"], index=False)
    task_scores.to_csv(outputs["tasks"], index=False)
    scores.to_csv(outputs["scores"], index=False)
    leaderboard.to_csv(outputs["leaderboard"], index=False)
    comparisons.to_csv(outputs["comparisons"], index=False)
    compute.to_csv(outputs["compute"], index=False)
    plot_scores(scores, outputs["plot"])
    write_report(outputs["report"], campaign_dir, leaderboard, inventory, comparisons)
    return outputs


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "benchmark"
    outputs = analyze(args.campaign_dir.resolve(), output_dir.resolve())
    print(f"Saved LIBERO-PRO Object leaderboard to {outputs['leaderboard']}")
    print(f"Report: {outputs['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Analyze broad LIBERO-PRO Object feedback-horizon controls."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


METHODS = ["maxV-H16", "maxV-H8", "random-H8", "horizon-only", "risk-H8"]
FACTORS = ["Object", "Position", "Environment"]
POSITION_LEVELS = [
    "x0.1", "x0.2", "x0.3", "x0.4", "x0.5",
    "y0.1", "y0.2", "y0.3", "y0.4", "y0.5",
]
PAIR_KEYS = ["factor", "position_level", "task_id", "init_state_id", "rollout_seed"]
CONTRASTS = [
    ("maxV-H8", "maxV-H16"),
    ("horizon-only", "maxV-H16"),
    ("random-H8", "maxV-H16"),
    ("horizon-only", "random-H8"),
    ("risk-H8", "horizon-only"),
    ("risk-H8", "maxV-H16"),
]
BASELINE_LABELS = {
    "Cosmos Policy + max(value)": "maxV-H16",
    "Ours: risk-aware + adaptive requery": "risk-H8",
}


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def factor_from_suite(suite: str) -> str:
    return {
        "libero_object_object": "Object",
        "libero_object_temp": "Position",
        "libero_object_env": "Environment",
    }[suite]


def method_from_trace(frame: pd.DataFrame) -> str:
    strategy = str(frame["planning_strategy"].dropna().iloc[0])
    if strategy == "max_value":
        horizon = int(pd.to_numeric(frame["num_open_loop_steps"], errors="raise").iloc[0])
        if horizon != 8:
            raise ValueError(f"P0 control max_value trace has unexpected horizon {horizon}")
        return "maxV-H8"
    if strategy == "max_value_disagreement_requery":
        return "horizon-only"
    if strategy == "max_value_random_requery_43":
        return "random-H8"
    raise ValueError(f"Unsupported P0 control strategy: {strategy}")


def read_trace(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def trace_paths(run_dir: Path, prefix: str) -> list[Path]:
    parquet = sorted(run_dir.glob(f"{prefix}*__query_traces.parquet"))
    parquet_stems = {path.stem for path in parquet}
    csv = [
        path
        for path in sorted(run_dir.glob(f"{prefix}*__query_traces.csv"))
        if path.stem not in parquet_stems
    ]
    return parquet + csv


def build_episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["source_trace", *PAIR_KEYS, "suite"]
    traces = traces.copy()
    traces["success"] = parse_bool(traces["success"])
    traces["planning_requery_triggered"] = parse_bool(
        traces.get("planning_requery_triggered", pd.Series(False, index=traces.index))
    )
    traces["query_idx"] = pd.to_numeric(traces["query_idx"], errors="raise")
    traces["num_samples"] = pd.to_numeric(traces["num_samples"], errors="raise")
    aggregates = (
        traces.groupby(group_keys, dropna=False)
        .agg(
            observed_queries=("query_idx", "size"),
            candidate_generations=("num_samples", "sum"),
            adaptive_requeries=("planning_requery_triggered", "sum"),
        )
        .reset_index()
    )
    episodes = (
        traces.sort_values(group_keys + ["query_idx"])
        .drop_duplicates(group_keys, keep="last")
        .merge(aggregates, on=group_keys, how="left")
    )
    for column in ["task_id", "init_state_id", "rollout_seed"]:
        episodes[column] = pd.to_numeric(episodes[column], errors="raise").astype(int)
    episodes["final_t"] = pd.to_numeric(episodes["final_t"], errors="coerce")
    fixed_queries = np.ceil(episodes["final_t"].clip(lower=1) / 16.0)
    episodes["query_multiplier_vs_h16"] = episodes["observed_queries"] / fixed_queries
    return episodes


def load_control_episodes(campaign_dir: Path) -> pd.DataFrame:
    manifest = json.loads((campaign_dir / "manifest.json").read_text(encoding="utf-8"))
    run_dir = campaign_dir / "runs"
    frames: list[pd.DataFrame] = []
    for job in manifest["jobs"]:
        env = job["environment"]
        prefix = env.get("LIBERO_PRO_PLANNING_GRID_PREFIX")
        if not prefix:
            continue
        suite = env["LIBERO_PRO_PLANNING_GRID_SUITES"]
        factor = factor_from_suite(suite)
        level = env.get("LIBERO_PRO_POSITION_LEVEL", "all")
        for path in trace_paths(run_dir, prefix):
            frame = read_trace(path)
            if frame.empty:
                continue
            frame = frame.copy()
            frame["source_trace"] = path.stem.removesuffix("__query_traces")
            frame["factor"] = factor
            frame["position_level"] = level
            frame["method"] = method_from_trace(frame)
            frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No P0 query traces under {run_dir}")
    return build_episode_table(pd.concat(frames, ignore_index=True, sort=False))


def load_baseline_episodes(baseline_dir: Path) -> pd.DataFrame:
    episodes = pd.read_csv(baseline_dir / "analysis/benchmark/episodes.csv", low_memory=False)
    episodes = episodes.loc[episodes["method"].isin(BASELINE_LABELS)].copy()
    episodes["method"] = episodes["method"].map(BASELINE_LABELS)
    episodes["success"] = parse_bool(episodes["success"])
    episodes["position_level"] = episodes["position_level"].fillna("all")
    return episodes


def score_tables(episodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    position = (
        episodes.loc[episodes["factor"].eq("Position")]
        .groupby(["method", "factor", "task_id", "position_level"], dropna=False)
        .agg(success_rate=("success", "mean"), episodes=("success", "size"))
        .reset_index()
    )
    other = (
        episodes.loc[~episodes["factor"].eq("Position")]
        .assign(position_level="all")
        .groupby(["method", "factor", "task_id", "position_level"], dropna=False)
        .agg(success_rate=("success", "mean"), episodes=("success", "size"))
        .reset_index()
    )
    cells = pd.concat([other, position], ignore_index=True)
    tasks = (
        cells.groupby(["method", "factor", "task_id"], dropna=False)
        .agg(success_rate=("success_rate", "mean"), cells=("success_rate", "size"))
        .reset_index()
    )
    factors = (
        tasks.groupby(["method", "factor"], dropna=False)
        .agg(success_rate=("success_rate", "mean"), tasks=("task_id", "nunique"))
        .reset_index()
    )
    leaderboard = (
        factors.pivot(index="method", columns="factor", values="success_rate")
        .reindex(index=METHODS, columns=FACTORS)
    )
    leaderboard["Mean"] = leaderboard.mean(axis=1, skipna=False)
    return factors, leaderboard.reset_index()


def cluster_ci(values: Sequence[float], seed: int = 20260826) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.choice(array, size=(10000, len(array)), replace=True).mean(axis=1)
    return tuple(float(value) for value in np.quantile(draws, [0.025, 0.975]))


def paired_comparisons(episodes: pd.DataFrame, *, overall: bool) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    factor_groups = [("Overall", episodes)] if overall else [
        (factor, episodes.loc[episodes["factor"].eq(factor)]) for factor in FACTORS
    ]
    for factor, frame in factor_groups:
        for candidate, reference in CONTRASTS:
            left = frame.loc[frame["method"].eq(candidate), PAIR_KEYS + ["success"]]
            right = frame.loc[frame["method"].eq(reference), PAIR_KEYS + ["success"]]
            merged = left.merge(right, on=PAIR_KEYS, suffixes=("_candidate", "_reference"))
            if merged.empty:
                continue
            merged["delta"] = (
                merged["success_candidate"].astype(float)
                - merged["success_reference"].astype(float)
            )
            cluster = merged.groupby(["factor", "task_id"])["delta"].mean().reset_index()
            if overall:
                estimate = float(cluster.groupby("factor")["delta"].mean().reindex(FACTORS).mean())
                rng = np.random.default_rng(20260826)
                draws = []
                for factor_name in FACTORS:
                    values = cluster.loc[cluster["factor"].eq(factor_name), "delta"].to_numpy()
                    draws.append(rng.choice(values, size=(10000, len(values)), replace=True).mean(axis=1))
                low, high = np.quantile(np.vstack(draws).mean(axis=0), [0.025, 0.975])
            else:
                estimate = float(cluster["delta"].mean())
                low, high = cluster_ci(cluster["delta"].to_numpy())
            wins = int((merged["delta"] > 0).sum())
            losses = int((merged["delta"] < 0).sum())
            rows.append(
                {
                    "factor": factor,
                    "candidate": candidate,
                    "reference": reference,
                    "paired_episodes": len(merged),
                    "delta_success_rate": estimate,
                    "ci95_low": float(low),
                    "ci95_high": float(high),
                    "wins": wins,
                    "losses": losses,
                    "ties": int((merged["delta"] == 0).sum()),
                    "mcnemar_p": exact_mcnemar_p(wins, losses),
                }
            )
    return pd.DataFrame(rows)


def compute_table(episodes: pd.DataFrame) -> pd.DataFrame:
    return (
        episodes.groupby("method", dropna=False)
        .agg(
            episodes=("success", "size"),
            mean_queries=("observed_queries", "mean"),
            mean_candidate_generations=("candidate_generations", "mean"),
            mean_requeries=("adaptive_requeries", "mean"),
            mean_query_multiplier=("query_multiplier_vs_h16", "mean"),
            mean_steps=("final_t", "mean"),
        )
        .reindex(METHODS)
        .reset_index()
    )


def percent(value: float) -> str:
    return "" if not np.isfinite(value) else f"{100 * value:.1f}%"


def plot_factor_scores(factors: pd.DataFrame, output: Path) -> None:
    fig, axis = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(FACTORS))
    width = 0.16
    for index, method in enumerate(METHODS):
        values = (
            factors.loc[factors["method"].eq(method)]
            .set_index("factor")["success_rate"]
            .reindex(FACTORS)
        )
        axis.bar(x + (index - 2) * width, values, width, label=method)
    axis.set_xticks(x, FACTORS)
    axis.set_ylim(0, 1)
    axis.set_ylabel("Success rate")
    axis.set_title("LIBERO-PRO Object: causal feedback-horizon controls")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_frontier(leaderboard: pd.DataFrame, compute: pd.DataFrame, output: Path) -> None:
    merged = leaderboard[["method", "Mean"]].merge(
        compute[["method", "mean_candidate_generations"]], on="method"
    )
    fig, axis = plt.subplots(figsize=(7.5, 5.5))
    for row in merged.itertuples(index=False):
        axis.scatter(row.mean_candidate_generations, row.Mean, s=55)
        axis.annotate(row.method, (row.mean_candidate_generations, row.Mean), xytext=(5, 5), textcoords="offset points")
    axis.set_xlabel("Mean candidate generations per episode")
    axis.set_ylabel("Factor-macro success rate")
    axis.set_title("Success / compute frontier")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_report(
    output: Path,
    leaderboard: pd.DataFrame,
    comparisons: pd.DataFrame,
    compute: pd.DataFrame,
) -> None:
    shown = leaderboard.copy()
    for column in FACTORS + ["Mean"]:
        shown[column] = shown[column].map(percent)
    paired = comparisons.loc[comparisons["factor"].eq("Overall")].copy()
    for column in ["delta_success_rate", "ci95_low", "ci95_high"]:
        paired[column] = paired[column].map(percent)
    compute_shown = compute.copy()
    for column in ["mean_queries", "mean_candidate_generations", "mean_requeries", "mean_query_multiplier", "mean_steps"]:
        compute_shown[column] = compute_shown[column].map(lambda value: f"{value:.2f}")
    lines = [
        "# P0 broad causal horizon controls",
        "",
        "## Leaderboard",
        "",
        shown.to_markdown(index=False),
        "",
        "![Factor scores](factor_scores.png)",
        "",
        "## Frozen overall contrasts",
        "",
        paired.to_markdown(index=False),
        "",
        "## Compute",
        "",
        compute_shown.to_markdown(index=False),
        "",
        "![Success/compute frontier](success_compute_frontier.png)",
        "",
        "Primary score gives equal weight to Object, Position, and Environment. Position gives equal weight to all available shift/task cells.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(campaign_dir: Path, baseline_dir: Path, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    controls = load_control_episodes(campaign_dir)
    baseline = load_baseline_episodes(baseline_dir)
    episodes = pd.concat([baseline, controls], ignore_index=True, sort=False)
    duplicates = episodes.duplicated(["method", *PAIR_KEYS])
    if duplicates.any():
        raise ValueError("Duplicate method/episode keys in combined P0 data")
    factors, leaderboard = score_tables(episodes)
    comparisons = pd.concat(
        [paired_comparisons(episodes, overall=False), paired_comparisons(episodes, overall=True)],
        ignore_index=True,
    )
    compute = compute_table(episodes)
    outputs = {
        "episodes": output_dir / "episodes.csv",
        "factors": output_dir / "factor_scores.csv",
        "leaderboard": output_dir / "leaderboard.csv",
        "comparisons": output_dir / "paired_comparisons.csv",
        "compute": output_dir / "compute.csv",
        "factor_plot": output_dir / "factor_scores.png",
        "frontier_plot": output_dir / "success_compute_frontier.png",
        "report": output_dir / "RESULTS.md",
    }
    episodes.to_csv(outputs["episodes"], index=False)
    factors.to_csv(outputs["factors"], index=False)
    leaderboard.to_csv(outputs["leaderboard"], index=False)
    comparisons.to_csv(outputs["comparisons"], index=False)
    compute.to_csv(outputs["compute"], index=False)
    plot_factor_scores(factors, outputs["factor_plot"])
    plot_frontier(leaderboard, compute, outputs["frontier_plot"])
    write_report(outputs["report"], leaderboard, comparisons, compute)
    return outputs


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_dir", type=Path)
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("experiments/campaigns/pro_object_baselines_pilot_20260825"),
    )
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir or args.campaign_dir / "analysis/horizon_controls"
    outputs = analyze(
        args.campaign_dir.resolve(), args.baseline_dir.resolve(), output_dir.resolve()
    )
    print(f"Saved P0 report to {outputs['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

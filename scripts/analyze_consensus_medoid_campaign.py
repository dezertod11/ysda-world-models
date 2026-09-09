#!/usr/bin/env python3
"""Summarize paired closed-loop consensus-medoid campaign outcomes."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import binomtest


PAIR_KEYS = ["suite", "task_id", "init_state_id", "rollout_seed"]


def _load_traces(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not paths:
        raise FileNotFoundError(f"No query traces under {campaign_dir / 'runs'}")
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    missing = set(PAIR_KEYS + ["planning_strategy", "success"]) - set(traces)
    if missing:
        raise ValueError(f"Missing required trace columns: {sorted(missing)}")
    episodes = (
        traces.sort_values("query_idx")
        .groupby([*PAIR_KEYS, "planning_strategy"], as_index=False, dropna=False)
        .first()
    )
    duplicate = episodes.duplicated([*PAIR_KEYS, "planning_strategy"], keep=False)
    if duplicate.any():
        raise ValueError("Duplicate strategy outcome for a paired rollout")
    episodes["success"] = episodes["success"].astype(bool)
    return episodes


def _cluster_bootstrap_interval(
    paired: pd.DataFrame,
    left: str,
    right: str,
    *,
    repeats: int = 20000,
    seed: int = 20260907,
) -> tuple[float, float]:
    effects = paired[right].astype(float) - paired[left].astype(float)
    groups = paired["init_state_id"].to_numpy()
    unique_groups = np.unique(groups)
    rng = np.random.default_rng(seed)
    estimates = np.empty(repeats, dtype=np.float64)
    for index in range(repeats):
        sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        sampled_effects = np.concatenate(
            [effects.to_numpy()[groups == group] for group in sampled]
        )
        estimates[index] = sampled_effects.mean()
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper)


def analyze(campaign_dir: Path, output_dir: Path) -> None:
    traces = _load_traces(campaign_dir)
    episodes = _episode_table(traces)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = (
        episodes.groupby("planning_strategy", as_index=False)
        .agg(
            episodes=("success", "size"),
            successes=("success", "sum"),
            success_rate=("success", "mean"),
            mean_final_t=("final_t", "mean"),
            mean_queries=("num_queries", "mean"),
        )
        .sort_values("success_rate", ascending=False)
    )

    query_aggregations = {
        "query_rows": ("query_idx", "size"),
        "selected_not_max_value_rate": ("max_value_selected", lambda x: 1.0 - x.astype(bool).mean()),
    }
    if "planning_query_risk_enabled" in traces:
        query_aggregations["guarded_switch_rate"] = (
            "planning_query_risk_enabled",
            lambda x: x.astype(bool).mean(),
        )
    query_summary = traces.groupby("planning_strategy", as_index=False).agg(
        **query_aggregations
    )

    strategies = sorted(episodes["planning_strategy"].unique())
    pair_rows = []
    for left, right in itertools.combinations(strategies, 2):
        subset = episodes.loc[
            episodes["planning_strategy"].isin({left, right}),
            [*PAIR_KEYS, "planning_strategy", "success"],
        ]
        paired = subset.pivot(index=PAIR_KEYS, columns="planning_strategy", values="success").dropna()
        paired = paired.reset_index()
        if paired.empty:
            continue
        rescue = int(((~paired[left].astype(bool)) & paired[right].astype(bool)).sum())
        harm = int((paired[left].astype(bool) & (~paired[right].astype(bool))).sum())
        discordant = rescue + harm
        p_value = float(
            binomtest(min(rescue, harm), discordant, 0.5).pvalue
            if discordant
            else 1.0
        )
        ci_low, ci_high = _cluster_bootstrap_interval(paired, left, right)
        pair_rows.append(
            {
                "reference": left,
                "method": right,
                "paired_episodes": len(paired),
                "reference_success_rate": float(paired[left].mean()),
                "method_success_rate": float(paired[right].mean()),
                "delta_success_rate": float(paired[right].mean() - paired[left].mean()),
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "rescues": rescue,
                "harms": harm,
                "mcnemar_exact_p": p_value,
            }
        )
    paired_effects = pd.DataFrame(pair_rows)

    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    summary.to_csv(output_dir / "strategy_summary.csv", index=False)
    query_summary.to_csv(output_dir / "query_summary.csv", index=False)
    paired_effects.to_csv(output_dir / "paired_effects.csv", index=False)

    report = [
        "# Consensus-medoid campaign result",
        "",
        f"Campaign: `{campaign_dir}`",
        "",
        "## Strategy-level SR",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Exact paired effects",
        "",
        (
            paired_effects.to_markdown(index=False, floatfmt=".4f")
            if len(paired_effects)
            else "No complete cross-strategy pairs were found."
        ),
        "",
        "## Query-level behavior",
        "",
        query_summary.to_markdown(index=False, floatfmt=".4f"),
        "",
        "The attached-file SR values are prior claims and are not merged into this table.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir or (args.campaign_dir / "consensus_analysis")
    analyze(args.campaign_dir, output_dir)
    print(f"Saved consensus analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Summarize task failures, official safety costs, and diagnostic candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_trace(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def episode_group_columns(frame: pd.DataFrame) -> List[str]:
    candidates = [
        "suite",
        "task_id",
        "pair_id",
        "rollout_id",
        "init_state_id",
        "rollout_seed",
    ]
    return [column for column in candidates if column in frame.columns]


def first_existing(frame: pd.DataFrame, names: List[str], default):
    for name in names:
        if name in frame:
            return frame[name]
    return pd.Series(default, index=frame.index)


def analyze(trace_path: Path, output_dir: Path) -> None:
    traces = load_trace(trace_path)
    if traces.empty:
        raise ValueError(f"Trace is empty: {trace_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    group_columns = episode_group_columns(traces)
    episodes = traces.sort_values("query_idx").groupby(group_columns, dropna=False).first().reset_index()
    if "failure_type" not in episodes:
        episodes["failure_type"] = np.where(
            episodes["success"].astype(bool),
            "success",
            "legacy_unclassified_failure",
        )
    if "safe_task_success" not in episodes:
        violation = first_existing(episodes, ["official_safety_violation"], False).astype(bool)
        episodes["safe_task_success"] = episodes["success"].astype(bool) & ~violation

    summary_aggregations = {
        "episodes": ("failure_type", "size"),
        "success_rate": ("success", "mean"),
        "safe_task_success_rate": ("safe_task_success", "mean"),
    }
    if "final_t" in episodes:
        summary_aggregations["median_final_t"] = ("final_t", "median")
    failure_summary = (
        episodes.groupby(["suite", "failure_type"], dropna=False)
        .agg(**summary_aggregations)
        .reset_index()
    )

    failure_event_t = first_existing(traces, ["failure_event_t"], -1).fillna(-1).astype(int)
    traces["failure_event_t"] = failure_event_t
    traces["steps_to_failure_event"] = np.where(
        failure_event_t >= 0,
        failure_event_t - traces["t"].astype(int),
        np.nan,
    )
    traces["query_is_pre_failure"] = (
        ~traces["success"].astype(bool)
        & (failure_event_t >= 0)
        & (traces["t"].astype(int) < failure_event_t)
    )
    traces["failure_event_in_executed_chunk"] = (
        ~traces["success"].astype(bool)
        & (failure_event_t > traces["t"].astype(int))
        & (failure_event_t <= traces["t_after"].astype(int))
    )

    episodes.to_csv(output_dir / "episode_failure_modes.csv", index=False)
    failure_summary.to_csv(output_dir / "failure_mode_summary.csv", index=False)
    traces.to_csv(output_dir / "query_traces_with_failure_labels.csv", index=False)
    traces.loc[traces["query_is_pre_failure"]].to_csv(
        output_dir / "online_pre_failure_queries.csv",
        index=False,
    )

    counts = episodes["failure_type"].value_counts().sort_values()
    fig, axis = plt.subplots(figsize=(10, max(3.5, 0.45 * len(counts))))
    counts.plot.barh(ax=axis, color="#2f6b8a")
    axis.set_xlabel("Episodes")
    axis.set_ylabel("")
    axis.set_title("Episode outcomes and diagnostic failure modes")
    fig.tight_layout()
    fig.savefig(output_dir / "failure_mode_counts.png", dpi=160)
    plt.close(fig)

    diagnostic_columns = [
        column
        for column in [
            "episode_target_lift_max",
            "episode_goal_progress_max",
            "episode_eef_dimensionless_jerk_proxy",
            "target_drop_candidate",
            "wrong_object_interaction_candidate",
            "kinematic_deadlock_candidate",
            "official_safety_violation",
        ]
        if column in episodes
    ]
    diagnostic_summary = {}
    for column in diagnostic_columns:
        values = pd.to_numeric(episodes[column], errors="coerce")
        diagnostic_summary[column] = {
            "mean": float(values.mean()),
            "median": float(values.median()),
            "max": float(values.max()),
        }

    summary = {
        "trace_file": str(trace_path.resolve()),
        "num_query_rows": int(len(traces)),
        "num_episodes": int(len(episodes)),
        "num_success": int(episodes["success"].astype(bool).sum()),
        "num_failed": int((~episodes["success"].astype(bool)).sum()),
        "num_safe_task_success": int(episodes["safe_task_success"].astype(bool).sum()),
        "failure_type_counts": {
            str(key): int(value) for key, value in episodes["failure_type"].value_counts().items()
        },
        "diagnostics": diagnostic_summary,
        "online_feature_warning": (
            "Columns prefixed observed_ and prediction_error_ are known only after executing the "
            "selected chunk. Do not use them as same-query planning inputs."
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.trace_file.with_name(
        f"{args.trace_file.stem}__failure_analysis"
    )
    analyze(args.trace_file, output_dir)


if __name__ == "__main__":
    main()

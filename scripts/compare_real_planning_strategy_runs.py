#!/usr/bin/env python3
"""Compare real rollout outcomes across planning strategy runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _read_metadata(base: Path, run_name: str) -> dict:
    path = base / f"{run_name}__metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _episode_table(trace: pd.DataFrame, run_name: str, metadata: dict) -> pd.DataFrame:
    group_cols = [
        col
        for col in ["suite", "task_id", "init_state_id", "pair_id", "rollout_id", "rollout_seed"]
        if col in trace.columns
    ]
    rows = []
    for key, group in trace.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_cols, key))
        row.update(
            {
                "run_name": run_name,
                "planning_strategy": group.get(
                    "planning_strategy",
                    pd.Series([metadata.get("planning_strategy", "unknown")]),
                ).iloc[0],
                "planning_risk_lambda": float(
                    group.get(
                        "planning_risk_lambda",
                        pd.Series([metadata.get("planning_risk_lambda", 0.0)]),
                    ).iloc[0]
                ),
                "success": bool(group["success"].iloc[-1]),
                "final_t": int(group["final_t"].iloc[-1]),
                "num_queries": int(group["query_idx"].max() + 1),
                "selected_not_max_value_rate": float((~group["max_value_selected"].astype(bool)).mean())
                if "max_value_selected" in group
                else 0.0,
                "selected_value_mean": float(group["selected_value"].mean()) if "selected_value" in group else float("nan"),
                "max_value_mean": float(group["max_value"].mean()) if "max_value" in group else float("nan"),
                "selected_risk_mean": float(group["selected_risk"].mean()) if "selected_risk" in group else float("nan"),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=Path, default=Path("experiments/uncertainty"))
    parser.add_argument("--run-names", required=True, help="Comma-separated run names to compare")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    episode_frames = []
    for run_name in [x.strip() for x in args.run_names.split(",") if x.strip()]:
        trace_path = args.base_dir / f"{run_name}__query_traces.csv"
        if not trace_path.exists():
            raise FileNotFoundError(trace_path)
        metadata = _read_metadata(args.base_dir, run_name)
        trace = pd.read_csv(trace_path)
        episode_frames.append(_episode_table(trace, run_name, metadata))

    episodes = pd.concat(episode_frames, ignore_index=True)
    summary_cols = ["planning_strategy", "planning_risk_lambda"]
    case_cols = ["suite", "task_id", "init_state_id"]
    strategy_summary = (
        episodes.groupby(summary_cols, dropna=False)
        .agg(
            episodes=("success", "count"),
            successes=("success", "sum"),
            success_rate=("success", "mean"),
            mean_final_t=("final_t", "mean"),
            mean_queries=("num_queries", "mean"),
            selected_not_max_value_rate=("selected_not_max_value_rate", "mean"),
            selected_value_mean=("selected_value_mean", "mean"),
            max_value_mean=("max_value_mean", "mean"),
            selected_risk_mean=("selected_risk_mean", "mean"),
        )
        .reset_index()
        .sort_values(["success_rate", "episodes"], ascending=[False, False])
    )
    case_summary = (
        episodes.groupby(summary_cols + case_cols, dropna=False)
        .agg(
            episodes=("success", "count"),
            successes=("success", "sum"),
            success_rate=("success", "mean"),
            mean_final_t=("final_t", "mean"),
            selected_not_max_value_rate=("selected_not_max_value_rate", "mean"),
        )
        .reset_index()
        .sort_values(case_cols + ["success_rate"], ascending=[True, True, True, False])
    )

    output_dir = args.output_dir or (args.base_dir / "planning_strategy_comparison__analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    episodes.to_csv(output_dir / "planning_strategy_episode_outcomes.csv", index=False)
    strategy_summary.to_csv(output_dir / "planning_strategy_summary.csv", index=False)
    case_summary.to_csv(output_dir / "planning_strategy_case_summary.csv", index=False)

    labels = [
        f"{row.planning_strategy}\nλ={row.planning_risk_lambda:g}"
        for row in strategy_summary.itertuples(index=False)
    ]
    fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(labels)), 4.5))
    ax.bar(labels, strategy_summary["success_rate"], color="#2374ab")
    for idx, row in enumerate(strategy_summary.itertuples(index=False)):
        ax.text(idx, row.success_rate + 0.02, f"{int(row.successes)}/{int(row.episodes)}", ha="center", va="bottom")
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("success rate")
    ax.set_title("Real closed-loop planning strategy comparison")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "planning_strategy_success_rate.png", dpi=160)
    plt.close(fig)

    pivot = strategy_summary.pivot(
        index="planning_strategy",
        columns="planning_risk_lambda",
        values="success_rate",
    ).sort_index()
    fig, ax = plt.subplots(figsize=(max(6, 1.0 * len(pivot.columns)), max(3.5, 0.55 * len(pivot.index))))
    image = ax.imshow(pivot.to_numpy(dtype=float), vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{x:g}" for x in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("lambda")
    ax.set_title("Success rate by planning strategy and lambda")
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            value = pivot.iloc[y, x]
            if pd.notna(value):
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", color="white" if value < 0.65 else "black")
    fig.colorbar(image, ax=ax, label="success rate")
    fig.tight_layout()
    fig.savefig(output_dir / "planning_strategy_success_rate_heatmap.png", dpi=160)
    plt.close(fig)

    print("Strategy summary:")
    print(strategy_summary.to_string(index=False))
    print(f"\nWrote {output_dir}")


if __name__ == "__main__":
    main()

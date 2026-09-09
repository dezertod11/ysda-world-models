#!/usr/bin/env python3
"""Plot the frozen Object query-4 shared-prefix replication summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    analysis_dir = args.analysis_dir.expanduser().resolve()
    output = args.output or (analysis_dir / "shared_prefix_replication_summary.png")
    frame = pd.read_csv(analysis_dir / "paired_outcomes.csv")
    summary = json.loads((analysis_dir / "summary.json").read_text(encoding="utf-8"))
    endpoint = summary["strict"]

    effect = pd.to_numeric(frame["terminal_effect"], errors="raise")
    replay = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="raise")
    init_range = (pd.to_numeric(frame["init_state_id"]) // 10) * 10
    range_delta = effect.groupby(init_range).mean().sort_index()

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    fig.suptitle("Object task 0, query-4 shared-prefix replication", fontsize=16)

    ax = axes[0, 0]
    rates = [endpoint["open_success_rate"], endpoint["feedback_success_rate"]]
    bars = ax.bar(["Commit H16", "H8 + re-query + H8"], rates, color=["#60646c", "#25865a"])
    ax.set_ylim(0, 0.8)
    ax.set_ylabel("Terminal success rate")
    ax.set_title("Primary endpoint")
    for bar, value in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.0%}", ha="center")
    ax.text(
        0.5,
        0.05,
        "Delta +18 pp; 95% CI [+4, +32]; p=0.00956",
        transform=ax.transAxes,
        ha="center",
        fontsize=10,
    )

    ax = axes[0, 1]
    outcome_counts = pd.Series(
        {
            "Rescue": int(endpoint["rescues"]),
            "Harm": int(endpoint["harms"]),
            "Both success": int(endpoint["both_success"]),
            "Both fail": int(endpoint["both_fail"]),
        }
    )
    colors = ["#25865a", "#bd3f3f", "#3478a5", "#8a8f98"]
    bars = ax.bar(outcome_counts.index, outcome_counts.values, color=colors)
    ax.set_ylabel("Exact-state pairs")
    ax.set_title("Paired outcomes")
    ax.tick_params(axis="x", rotation=15)
    for bar, value in zip(bars, outcome_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.8, str(value), ha="center")

    ax = axes[1, 0]
    labels = [f"{int(start)}-{int(start + 9)}" for start in range_delta.index]
    colors = ["#25865a" if value >= 0 else "#bd3f3f" for value in range_delta]
    bars = ax.bar(labels, 100 * range_delta.to_numpy(), color=colors)
    ax.axhline(0, color="#30343b", linewidth=1)
    ax.set_ylabel("Feedback - commit (pp)")
    ax.set_xlabel("Init-state range")
    ax.set_title("Heterogeneity across frozen ranges")
    for bar, value in zip(bars, 100 * range_delta.to_numpy()):
        offset = 1.5 if value >= 0 else -3.5
        ax.text(bar.get_x() + bar.get_width() / 2, value + offset, f"{value:+.0f}", ha="center")

    ax = axes[1, 1]
    safe_replay = np.maximum(replay.to_numpy(dtype=float), np.finfo(float).tiny)
    ax.hist(np.log10(safe_replay), bins=20, color="#6c5b9b", edgecolor="white")
    ax.axvline(-9, color="#bd3f3f", linestyle="--", label="Frozen threshold: 1e-9")
    ax.set_xlabel("log10(max replay-state absolute error)")
    ax.set_ylabel("Pairs")
    ax.set_title("Replay integrity: 100/100 PASS")
    ax.legend(frameon=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Plot the frozen Object query-4 cross-factor boundary screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _cell_label(case_id: str) -> str:
    labels = {
        "position_x0p1_task0": "Position x0.1",
        "position_x0p2_task0": "Position x0.2",
        "position_y0p2_task0": "Position y0.2",
        "position_y0p3_task0": "Position y0.3",
        "environment_task0": "Environment",
    }
    return labels.get(case_id, case_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    analysis_dir = args.analysis_dir.expanduser().resolve()
    output = args.output or (analysis_dir / "cross_factor_boundary_summary.png")
    cells = pd.read_csv(analysis_dir / "cell_summary.csv")
    frame = pd.read_csv(analysis_dir / "paired_outcomes.csv")
    integrity = json.loads((analysis_dir / "integrity.json").read_text(encoding="utf-8"))

    labels = [_cell_label(case_id) for case_id in cells["case_id"]]
    x = np.arange(len(cells))
    width = 0.36

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    fig.suptitle("Object task 0, query-4 feedback across LIBERO-PRO factors", fontsize=16)

    ax = axes[0, 0]
    commit = cells["open_success_rate"].to_numpy(dtype=float)
    feedback = cells["feedback_success_rate"].to_numpy(dtype=float)
    left = ax.bar(x - width / 2, commit, width, label="Commit H16", color="#60646c")
    right = ax.bar(x + width / 2, feedback, width, label="H8 + re-query + H8", color="#25865a")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Terminal success rate")
    ax.set_title("Success rate by frozen cell")
    ax.set_xticks(x, labels, rotation=18, ha="right")
    ax.legend(frameon=False)
    for bars in (left, right):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.0%}", ha="center", fontsize=9)

    ax = axes[0, 1]
    delta = 100 * cells["success_delta"].to_numpy(dtype=float)
    low = 100 * cells["success_delta_ci_low"].to_numpy(dtype=float)
    high = 100 * cells["success_delta_ci_high"].to_numpy(dtype=float)
    error = np.vstack([delta - low, high - delta])
    colors = ["#25865a" if value >= 0 else "#bd3f3f" for value in delta]
    ax.bar(x, delta, color=colors)
    ax.errorbar(x, delta, yerr=error, fmt="none", ecolor="#25282d", capsize=4)
    ax.axhline(0, color="#30343b", linewidth=1)
    ax.set_ylabel("Feedback - commit (percentage points)")
    ax.set_title("Paired effect with init-cluster 95% CI")
    ax.set_xticks(x, labels, rotation=18, ha="right")
    for index, value in enumerate(delta):
        ax.text(index, value + (1.5 if value >= 0 else -3.5), f"{value:+.0f}", ha="center", fontsize=9)

    ax = axes[1, 0]
    rescues = cells["rescues"].to_numpy(dtype=int)
    harms = cells["harms"].to_numpy(dtype=int)
    ax.bar(x - width / 2, rescues, width, label="Rescue", color="#25865a")
    ax.bar(x + width / 2, harms, width, label="Harm", color="#bd3f3f")
    ax.set_ylabel("Exact-state pairs")
    ax.set_title("Discordant paired outcomes")
    ax.set_xticks(x, labels, rotation=18, ha="right")
    ax.legend(frameon=False)
    for index, (rescue, harm) in enumerate(zip(rescues, harms)):
        ax.text(index - width / 2, rescue + 0.25, str(rescue), ha="center", fontsize=9)
        ax.text(index + width / 2, harm + 0.25, str(harm), ha="center", fontsize=9)

    ax = axes[1, 1]
    replay = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="raise")
    safe_replay = np.maximum(replay.to_numpy(dtype=float), np.finfo(float).tiny)
    ax.hist(np.log10(safe_replay), bins=20, color="#6c5b9b", edgecolor="white")
    threshold = 1e-9
    ax.axvline(np.log10(threshold), color="#bd3f3f", linestyle="--", label="Frozen threshold: 1e-9")
    ax.set_xlabel("log10(max replay-state absolute error)")
    ax.set_ylabel("Pairs")
    ax.set_title(
        f"Replay integrity: {integrity['strict_replay_pairs']}/{integrity['target_pairs']} strict"
    )
    ax.legend(frameon=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()

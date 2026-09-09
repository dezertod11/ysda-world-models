#!/usr/bin/env python3
"""Plot the frozen Object query-4 Position direction holdout."""

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
    output = args.output or (analysis_dir / "position_direction_holdout_summary.png")
    cells = pd.read_csv(analysis_dir / "condition_summary.csv").sort_values("perturbation")
    frame = pd.read_csv(analysis_dir / "paired_outcomes.csv")
    summary = json.loads((analysis_dir / "summary.json").read_text(encoding="utf-8"))
    integrity = summary["integrity"]
    interaction = summary["interaction"]

    labels = [f"Position {value}" for value in cells["perturbation"]]
    x = np.arange(len(cells))
    width = 0.34
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    fig.suptitle("Object task 0, query-4 Position direction holdout", fontsize=16)

    ax = axes[0, 0]
    commit = cells["open_success_rate"].to_numpy(dtype=float)
    feedback = cells["feedback_success_rate"].to_numpy(dtype=float)
    left = ax.bar(x - width / 2, commit, width, label="Commit H16", color="#60646c")
    right = ax.bar(x + width / 2, feedback, width, label="H8 + re-query + H8", color="#25865a")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Terminal success rate")
    ax.set_title("Confirmatory success rate")
    ax.set_xticks(x, labels)
    ax.legend(frameon=False)
    for bars in (left, right):
        for bar in bars:
            value = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.0%}", ha="center")

    ax = axes[0, 1]
    delta = 100 * cells["success_delta"].to_numpy(dtype=float)
    low = 100 * cells["success_delta_ci_low"].to_numpy(dtype=float)
    high = 100 * cells["success_delta_ci_high"].to_numpy(dtype=float)
    ax.bar(x, delta, color=["#25865a" if value >= 0 else "#bd3f3f" for value in delta])
    ax.errorbar(x, delta, yerr=np.vstack([delta - low, high - delta]), fmt="none", ecolor="#25282d", capsize=5)
    ax.axhline(0, color="#30343b", linewidth=1)
    ax.set_ylabel("Feedback - commit (pp)")
    ax.set_title("Init-cluster 95% CI")
    ax.set_xticks(x, labels)

    ax = axes[1, 0]
    rescues = cells["rescues"].to_numpy(dtype=int)
    harms = cells["harms"].to_numpy(dtype=int)
    ax.bar(x - width / 2, rescues, width, label="Rescue", color="#25865a")
    ax.bar(x + width / 2, harms, width, label="Harm", color="#bd3f3f")
    ax.set_ylabel("Exact-state pairs")
    ax.set_title("Discordant outcomes")
    ax.set_xticks(x, labels)
    ax.legend(frameon=False)

    ax = axes[1, 1]
    replay = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    replay = np.maximum(replay.dropna().to_numpy(dtype=float), np.finfo(float).tiny)
    ax.hist(np.log10(replay), bins=20, color="#6c5b9b", edgecolor="white")
    ax.axvline(-9, color="#bd3f3f", linestyle="--", label="Threshold: 1e-9")
    ax.set_xlabel("log10(max replay-state absolute error)")
    ax.set_ylabel("Pairs")
    ax.set_title(
        f"Interaction {100 * interaction['interaction_delta']:+.1f} pp; "
        f"strict {integrity['strict_replay_pairs']}/{integrity['target_pairs']}"
    )
    ax.legend(frameon=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()

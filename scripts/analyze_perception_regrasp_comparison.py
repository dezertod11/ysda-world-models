#!/usr/bin/env python3
"""Compare learned RGB regrasp with the paired privileged upper bound."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _branches(path: Path) -> pd.DataFrame:
    path = path.expanduser().resolve()
    if path.is_dir():
        path = path / "analysis" / "all_recovery_branches.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def build_pairs(learned: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    learned = learned.loc[learned["proposal"].eq("perception_regrasp_h8")].copy()
    reference = reference.loc[reference["proposal"].eq("privileged_regrasp_h8")].copy()
    if learned["row_uid"].duplicated().any() or reference["row_uid"].duplicated().any():
        raise ValueError("each proposal must contain one row per frozen state")
    columns = [
        "row_uid",
        "independent_group",
        "position_level",
        "task_id",
        "terminal_success",
        "terminal_failure_type",
    ]
    optional = [
        "perception_object",
        "perception_peak_probability",
        "perception_entropy",
        "perception_score_range",
    ]
    left = learned[columns + [name for name in optional if name in learned]].rename(
        columns={
            "terminal_success": "learned_success",
            "terminal_failure_type": "learned_failure_type",
        }
    )
    right = reference[["row_uid", "terminal_success", "terminal_failure_type"]].rename(
        columns={
            "terminal_success": "privileged_success",
            "terminal_failure_type": "privileged_failure_type",
        }
    )
    paired = left.merge(right, on="row_uid", how="left", validate="one_to_one")
    if paired["privileged_success"].isna().any():
        raise ValueError("reference does not cover every learned state")
    paired["learned_success"] = paired["learned_success"].astype(bool)
    paired["privileged_success"] = paired["privileged_success"].astype(bool)
    return paired


def summarize_pairs(
    paired: pd.DataFrame, *, bootstrap_repetitions: int, seed: int
) -> dict[str, Any]:
    learned = paired["learned_success"].to_numpy(dtype=bool)
    privileged = paired["privileged_success"].to_numpy(dtype=bool)
    learned_only = int(np.sum(learned & ~privileged))
    privileged_only = int(np.sum(~learned & privileged))
    both = int(np.sum(learned & privileged))
    neither = int(np.sum(~learned & ~privileged))
    discordant = learned_only + privileged_only
    group_delta = (
        paired.assign(delta=learned.astype(float) - privileged.astype(float))
        .groupby("independent_group", sort=True)["delta"]
        .mean()
        .to_numpy()
    )
    rng = np.random.default_rng(seed)
    draws = rng.choice(
        group_delta,
        size=(bootstrap_repetitions, len(group_delta)),
        replace=True,
    ).mean(axis=1)
    privileged_successes = int(privileged.sum())
    return {
        "states": len(paired),
        "groups": int(paired["independent_group"].nunique()),
        "learned_successes": int(learned.sum()),
        "learned_success_rate": float(learned.mean()),
        "privileged_successes": privileged_successes,
        "privileged_success_rate": float(privileged.mean()),
        "learned_minus_privileged": float(learned.mean() - privileged.mean()),
        "learned_minus_privileged_cluster_ci_low": float(np.quantile(draws, 0.025)),
        "learned_minus_privileged_cluster_ci_high": float(np.quantile(draws, 0.975)),
        "both_success": both,
        "learned_only_success": learned_only,
        "privileged_only_success": privileged_only,
        "neither_success": neither,
        "privileged_success_coverage": (
            float(both / privileged_successes) if privileged_successes else None
        ),
        "mcnemar_exact_p": (
            float(binomtest(min(learned_only, privileged_only), discordant, 0.5).pvalue)
            if discordant
            else 1.0
        ),
    }


def _cell_summary(paired: pd.DataFrame) -> pd.DataFrame:
    return (
        paired.groupby(["position_level", "task_id"], as_index=False)
        .agg(
            states=("row_uid", "size"),
            learned_successes=("learned_success", "sum"),
            learned_sr=("learned_success", "mean"),
            privileged_successes=("privileged_success", "sum"),
            privileged_sr=("privileged_success", "mean"),
        )
        .assign(delta=lambda frame: frame["learned_sr"] - frame["privileged_sr"])
    )


def _plot(cell: pd.DataFrame, output: Path) -> None:
    import matplotlib.pyplot as plt

    labels = [f"{row.position_level}/t{row.task_id}" for row in cell.itertuples()]
    x = np.arange(len(cell))
    width = 0.38
    figure, axis = plt.subplots(figsize=(11, 4.8))
    axis.bar(x - width / 2, cell["learned_sr"], width, label="RGB regrasp")
    axis.bar(x + width / 2, cell["privileged_sr"], width, label="Privileged pose")
    axis.set_xticks(x, labels, rotation=35, ha="right")
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Terminal success rate")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learned-campaign", type=Path, required=True)
    parser.add_argument(
        "--reference",
        type=Path,
        default=PROJECT_ROOT
        / "experiments/campaigns/recovery_proposal_opportunity_20260904",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260904)
    args = parser.parse_args()

    paired = build_pairs(_branches(args.learned_campaign), _branches(args.reference))
    summary = summarize_pairs(
        paired,
        bootstrap_repetitions=args.bootstrap_repetitions,
        seed=args.seed,
    )
    cells = _cell_summary(paired)
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output / "perception_vs_privileged_pairs.csv", index=False)
    cells.to_csv(output / "perception_vs_privileged_cells.csv", index=False)
    (output / "perception_vs_privileged_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    _plot(cells, output / "perception_vs_privileged_cells.png")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

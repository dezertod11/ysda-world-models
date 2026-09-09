#!/usr/bin/env python3
"""Build a cross-campaign atlas of terminal candidate-pool opportunity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import opportunity_table, read_candidates
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from terminal_grounded_critic import opportunity_table, read_candidates


def _campaign_from_path(value: str) -> str:
    parts = Path(value).parts
    try:
        return parts[parts.index("campaigns") + 1]
    except (ValueError, IndexError):
        return "unknown"


def _state_table(candidates: pd.DataFrame) -> pd.DataFrame:
    states = opportunity_table(candidates)
    metadata_columns = ["source_run", "source_path"]
    for column in (
        "prediction_mode",
        "num_open_loop_steps",
        "num_denoising_steps_action",
    ):
        if column in candidates:
            metadata_columns.append(column)
    metadata = (
        candidates.groupby("analysis_snapshot_id", as_index=False)[metadata_columns]
        .first()
        .copy()
    )
    states = states.merge(metadata, on="analysis_snapshot_id", how="left")
    states["campaign"] = states["source_path"].map(_campaign_from_path)
    states["all_candidates_fail"] = ~states["oracle_success"]
    states["all_candidates_succeed"] = (
        states["maxv_success"] & ~states["outcome_heterogeneous"]
    )
    return states


def _summarize(states: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    result = (
        states.groupby(list(keys), as_index=False, dropna=False)
        .agg(
            snapshots=("analysis_snapshot_id", "size"),
            independent_groups=("independent_group", "nunique"),
            candidates_min=("candidates", "min"),
            candidates_max=("candidates", "max"),
            heterogeneous_snapshots=("outcome_heterogeneous", "sum"),
            success_rescues=("success_rescue", "sum"),
            utility_rescues=("utility_rescue", "sum"),
            all_candidates_fail=("all_candidates_fail", "sum"),
            all_candidates_succeed=("all_candidates_succeed", "sum"),
            maxv_sr=("maxv_success", "mean"),
            oracle_sr=("oracle_success", "mean"),
            maxv_utility=("maxv_utility", "mean"),
            oracle_utility=("oracle_utility", "mean"),
        )
        .reset_index(drop=True)
    )
    result["oracle_gap_pp"] = 100.0 * (result["oracle_sr"] - result["maxv_sr"])
    result["rescue_rate"] = result["success_rescues"] / result["snapshots"]
    return result.sort_values(
        ["oracle_gap_pp", "success_rescues", "snapshots"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _plot_cells(cells: pd.DataFrame, destination: Path) -> None:
    shown = cells.loc[
        cells["heterogeneous_snapshots"].gt(0)
        | cells["all_candidates_fail"].gt(0)
        | cells["maxv_sr"].lt(1.0)
    ].copy()
    if shown.empty:
        shown = cells.head(20).copy()
    shown = shown.head(30).iloc[::-1]
    labels = [
        f"{row.factor} t{int(row.task_id)} q{int(row.query_idx)} K{int(row.candidates_max)}"
        for row in shown.itertuples()
    ]
    positions = np.arange(len(shown))
    figure, axis = plt.subplots(figsize=(10, max(4.5, 0.36 * len(shown) + 1.5)))
    axis.barh(positions - 0.18, shown["maxv_sr"], 0.36, label="max(value)")
    axis.barh(positions + 0.18, shown["oracle_sr"], 0.36, label="oracle in pool")
    axis.set_yticks(positions, labels)
    axis.set_xlim(0.0, 1.05)
    axis.set_xlabel("Terminal success rate")
    axis.grid(axis="x", alpha=0.25)
    axis.legend(loc="lower right")
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def _write_report(
    output_dir: Path,
    states: pd.DataFrame,
    campaign_summary: pd.DataFrame,
    cells: pd.DataFrame,
) -> None:
    useful = cells.loc[cells["success_rescues"].gt(0)].copy()
    hard_no_choice = cells.loc[
        cells["all_candidates_fail"].gt(0) & cells["success_rescues"].eq(0)
    ].copy()
    lines = [
        "# Terminal proposal-opportunity atlas",
        "",
        "This is a retrospective inventory of outcome-independent terminal branches.",
        "It measures whether a candidate pool contains a better terminal action; it",
        "does not evaluate a learned selector and is not a confirmatory claim.",
        "",
        "## Coverage",
        "",
        f"- Candidate tables: {states['source_path'].nunique()}.",
        f"- Exact-state snapshots: {len(states)}.",
        f"- Independent task/init groups: {states['independent_group'].nunique()}.",
        f"- Heterogeneous pools: {int(states['outcome_heterogeneous'].sum())}.",
        f"- Rescuable max(value) failures: {int(states['success_rescue'].sum())}.",
        "",
        "## By campaign and factor",
        "",
        campaign_summary.to_markdown(index=False),
        "",
        "## Cells with observed terminal rescue",
        "",
        useful.to_markdown(index=False) if not useful.empty else "No rescue cells.",
        "",
        "## Hard cells without candidate choice",
        "",
        hard_no_choice.to_markdown(index=False)
        if not hard_no_choice.empty
        else "No all-fail cells.",
        "",
        "## Routing rule for the next experiment",
        "",
        "A new selector is trained only after a prespecified proposal pool shows",
        "nonzero rescue support and at least a 5 percentage-point oracle gap on",
        "independent init-state holdout. All-fail cells require proposal diversity,",
        "feedback, or recovery rather than another score over the same candidates.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_atlas(candidate_files: Sequence[Path], output_dir: Path) -> dict[str, object]:
    candidates = read_candidates(candidate_files, require_features=False)
    states = _state_table(candidates)
    campaign_summary = _summarize(states, ["campaign", "factor"])
    cell_summary = _summarize(
        states,
        [
            "campaign",
            "factor",
            "case_id",
            "suite",
            "task_id",
            "task_description",
            "query_idx",
        ],
    )
    cross_campaign = _summarize(
        states,
        ["factor", "case_id", "suite", "task_id", "task_description", "query_idx"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    states.to_csv(output_dir / "opportunity_states.csv", index=False)
    campaign_summary.to_csv(output_dir / "campaign_factor_summary.csv", index=False)
    cell_summary.to_csv(output_dir / "campaign_task_query_summary.csv", index=False)
    cross_campaign.to_csv(output_dir / "cross_campaign_task_query_summary.csv", index=False)
    _plot_cells(cell_summary, output_dir / "terminal_oracle_gap_by_cell.png")
    _write_report(output_dir, states, campaign_summary, cell_summary)
    summary = {
        "candidate_tables": int(states["source_path"].nunique()),
        "snapshots": int(len(states)),
        "independent_groups": int(states["independent_group"].nunique()),
        "heterogeneous_snapshots": int(states["outcome_heterogeneous"].sum()),
        "success_rescues": int(states["success_rescue"].sum()),
        "all_candidates_fail": int(states["all_candidates_fail"].sum()),
        "all_candidates_succeed": int(states["all_candidates_succeed"].sum()),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_atlas(args.candidate_files, args.output_dir), indent=2))


if __name__ == "__main__":
    main()

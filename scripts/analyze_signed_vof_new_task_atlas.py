#!/usr/bin/env python3
"""Analyze a baseline-only LIBERO-PRO Position atlas for signed-VoF transfer."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EXPECTED_CANDIDATES = 4
DEFAULT_EXPECTED_STATES = 180
LEVEL_PATTERN = re.compile(r"position_([xy]\d+p\d+)_tasks")


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def decode_position_level(case_id: str) -> str:
    match = LEVEL_PATTERN.search(case_id)
    if not match:
        raise ValueError(f"Cannot decode Position level from case_id={case_id!r}")
    return match.group(1).replace("p", ".")


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return float("nan"), float("nan")
    z = 1.959963984540054
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    radius = z * np.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return float(center - radius), float(center + radius)


def load_selected_baselines(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = sorted((campaign_dir / "runs").glob("*__candidate_outcomes.parquet"))
    if not paths:
        raise FileNotFoundError(f"No candidate outcome files under {campaign_dir / 'runs'}")
    parts = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_file"] = path.name
        parts.append(frame)
    candidates = pd.concat(parts, ignore_index=True)
    # snapshot_id does not encode the Position level, so the same task/init/query
    # identifier legitimately repeats across atlas jobs.
    candidates["atlas_state_id"] = (
        candidates["source_file"].astype(str)
        + "|"
        + candidates["snapshot_id"].astype(str)
    )
    required = {
        "snapshot_id",
        "case_id",
        "task_id",
        "init_state_id",
        "rollout_id",
        "candidate_idx",
        "candidate_is_max_value",
        "terminal_available",
        "terminal_success",
    }
    missing = sorted(required.difference(candidates.columns))
    if missing:
        raise ValueError(f"Candidate files miss required columns: {missing}")

    pool = candidates.groupby("atlas_state_id", sort=False).agg(
        candidate_rows=("candidate_idx", "size"),
        unique_candidates=("candidate_idx", "nunique"),
        max_value_rows=("candidate_is_max_value", lambda values: int(_as_bool(values).sum())),
    )
    pool["pool_integrity"] = (
        pool["candidate_rows"].eq(EXPECTED_CANDIDATES)
        & pool["unique_candidates"].eq(EXPECTED_CANDIDATES)
        & pool["max_value_rows"].eq(1)
    )
    selected = candidates.loc[_as_bool(candidates["candidate_is_max_value"])].copy()
    selected = selected.merge(
        pool.reset_index(), on="atlas_state_id", how="left", validate="one_to_one"
    )
    selected["terminal_available_bool"] = _as_bool(selected["terminal_available"])
    selected["terminal_success_bool"] = _as_bool(selected["terminal_success"])
    selected["strict_usable"] = selected["pool_integrity"] & selected["terminal_available_bool"]
    selected["position_level"] = selected["case_id"].astype(str).map(decode_position_level)
    selected["direction"] = selected["position_level"].str[0]
    return candidates, selected


def summarize_cells(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (level, task_id), group in selected.groupby(["position_level", "task_id"], sort=True):
        strict = group.loc[group["strict_usable"]]
        successes = int(strict["terminal_success_bool"].sum())
        total = int(len(strict))
        rate = successes / total if total else float("nan")
        lower, upper = wilson_interval(successes, total)
        rows.append(
            {
                "position_level": level,
                "direction": str(level)[0],
                "task_id": int(task_id),
                "task_description": str(group["task_description"].iloc[0]) if "task_description" in group else "",
                "attempted_states": int(len(group)),
                "strict_states": total,
                "successes": successes,
                "failures": total - successes,
                "commit_success_rate": rate,
                "commit_success_ci_low": lower,
                "commit_success_ci_high": upper,
                "boundary_distance": abs(rate - 0.5) if np.isfinite(rate) else float("inf"),
                "eligible_boundary": bool(total >= 4 and 0.20 <= rate <= 0.80),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["boundary_distance", "strict_states", "task_id", "position_level"],
        ascending=[True, False, True, True],
    ).reset_index(drop=True)


def select_boundary_cells(summary: pd.DataFrame, maximum: int = 6) -> pd.DataFrame:
    return summary.loc[summary["eligible_boundary"]].head(maximum).copy()


def build_gate(
    selected_rows: pd.DataFrame,
    cell_summary: pd.DataFrame,
    *,
    expected_states: int,
) -> dict[str, object]:
    strict_states = int(selected_rows["strict_usable"].sum())
    chosen = select_boundary_cells(cell_summary)
    checks = {
        "strict_completeness_at_least_95pct": strict_states >= int(np.ceil(0.95 * expected_states)),
        "at_least_six_boundary_cells": int(cell_summary["eligible_boundary"].sum()) >= 6,
        "selected_cover_at_least_three_tasks": int(chosen["task_id"].nunique()) >= 3,
        "selected_cover_both_directions": set(chosen["direction"].astype(str)) == {"x", "y"},
    }
    return {
        "expected_states": expected_states,
        "attempted_states": int(len(selected_rows)),
        "strict_states": strict_states,
        "eligible_cells": int(cell_summary["eligible_boundary"].sum()),
        "selected_cells": int(len(chosen)),
        "selected_tasks": int(chosen["task_id"].nunique()),
        "selected_directions": sorted(chosen["direction"].astype(str).unique().tolist()),
        "checks": checks,
        "pass": bool(all(checks.values())),
        "decision": "advance_to_frozen_router_new_task_holdout" if all(checks.values()) else "stop_and_redesign_boundary_atlas",
    }


def plot_atlas(summary: pd.DataFrame, chosen: pd.DataFrame, output: Path) -> None:
    levels = ["x0.2", "y0.1", "y0.2", "y0.3"]
    tasks = sorted(summary["task_id"].unique())
    matrix = np.full((len(levels), len(tasks)), np.nan)
    labels = np.full(matrix.shape, "", dtype=object)
    selected_keys = set(zip(chosen["position_level"], chosen["task_id"]))
    for row in summary.itertuples(index=False):
        y = levels.index(row.position_level)
        x = tasks.index(row.task_id)
        matrix[y, x] = row.commit_success_rate
        mark = "*" if (row.position_level, row.task_id) in selected_keys else ""
        labels[y, x] = f"{row.successes}/{row.strict_states}{mark}"
    fig, ax = plt.subplots(figsize=(12, 4.4))
    image = ax.imshow(matrix, vmin=0.0, vmax=1.0, cmap="RdYlGn", aspect="auto")
    for y in range(len(levels)):
        for x in range(len(tasks)):
            ax.text(x, y, labels[y, x], ha="center", va="center", fontsize=9)
    ax.set_xticks(range(len(tasks)), [str(task) for task in tasks])
    ax.set_yticks(range(len(levels)), levels)
    ax.set_xlabel("LIBERO-PRO Object task id")
    ax.set_ylabel("Position perturbation")
    ax.set_title("Baseline commit success at q4 (star = selected boundary cell)")
    fig.colorbar(image, ax=ax, label="Success rate")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-states", type=int, default=DEFAULT_EXPECTED_STATES)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates, selected = load_selected_baselines(campaign_dir)
    summary = summarize_cells(selected)
    chosen = select_boundary_cells(summary)
    gate = build_gate(selected, summary, expected_states=args.expected_states)

    summary.to_csv(output_dir / "cell_summary.csv", index=False)
    selected.to_parquet(output_dir / "selected_baseline_states.parquet", index=False)
    selection = {
        "selection_rule": "strict n>=4, 0.20<=commit_SR<=0.80; rank by |SR-0.5| then n, task, level; take first 6",
        "holdout_init_state_ids": "5-24",
        "holdout_rollouts_per_init": 2,
        "cells": chosen.to_dict(orient="records"),
        "gate": gate,
    }
    (output_dir / "selected_cells.json").write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    plot_atlas(summary, chosen, output_dir / "baseline_boundary_atlas.png")

    lines = [
        "# Signed-VoF new-task baseline atlas",
        "",
        "This stage used only max-value commit outcomes. No feedback branch or router",
        "prediction participated in cell selection.",
        "",
        f"- Candidate rows: {len(candidates)}",
        f"- Attempted decision states: {len(selected)}",
        f"- Strict usable states: {int(selected['strict_usable'].sum())}/{args.expected_states}",
        f"- Eligible boundary cells: {int(summary['eligible_boundary'].sum())}",
        f"- Gate: **{'PASS' if gate['pass'] else 'FAIL'}**",
        f"- Decision: `{gate['decision']}`",
        "",
        "## Selected cells",
        "",
        chosen.to_markdown(index=False) if len(chosen) else "No cells selected.",
        "",
        "A PASS authorizes a prospective frozen-router holdout on init states 5-24.",
        "It is not itself evidence that the router transfers.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(gate, indent=2))
    print(f"Results: {output_dir}")
    return 0 if gate["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

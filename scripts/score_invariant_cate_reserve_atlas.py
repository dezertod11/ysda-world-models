#!/usr/bin/env python3
"""Outcome-blind scoring of unused baseline-atlas cells with the frozen CATE router."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from invariant_cate_router import build_prequery_dataset, predict_frozen_cate
except ModuleNotFoundError:
    from scripts.invariant_cate_router import build_prequery_dataset, predict_frozen_cate


def _cell_keys(frame: pd.DataFrame) -> set[tuple[str, int]]:
    return set(
        zip(frame["position_level"].astype(str), frame["task_id"].astype(int))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas-states", type=Path, required=True)
    parser.add_argument("--cell-summary", type=Path, required=True)
    parser.add_argument("--previous-selection", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--router", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    states = pd.read_parquet(args.atlas_states).copy()
    states["source_run"] = states["source_file"].astype(str).str.removesuffix(
        "__candidate_outcomes.parquet"
    )
    cells = pd.read_csv(args.cell_summary)
    cells = cells.loc[cells["eligible_boundary"].astype(bool)].copy()
    previous = json.loads(args.previous_selection.read_text(encoding="utf-8"))
    used = {
        (str(cell["position_level"]), int(cell["task_id"]))
        for cell in previous["cells"]
    }
    reserve = cells.loc[
        [
            (str(row.position_level), int(row.task_id)) not in used
            for row in cells.itertuples(index=False)
        ]
    ].copy()
    reserve_keys = _cell_keys(reserve)
    states = states.loc[
        [
            (str(row.position_level), int(row.task_id)) in reserve_keys
            for row in states.itertuples(index=False)
        ]
    ].reset_index(drop=True)
    features = build_prequery_dataset(
        states,
        args.campaign_dir.expanduser().resolve(),
        require_labels=False,
    )
    router = json.loads(args.router.read_text(encoding="utf-8"))
    prediction = predict_frozen_cate(router, features)
    output = pd.concat(
        [
            features[
                [
                    "snapshot_id",
                    "source_run",
                    "sidecar_path",
                    "position_level",
                    "task_id",
                    "init_state_id",
                    "rollout_id",
                    "task_description",
                    "independent_group",
                ]
            ],
            states[["terminal_success_bool"]].rename(
                columns={"terminal_success_bool": "atlas_commit_success"}
            ),
            prediction,
        ],
        axis=1,
    )
    summary = (
        output.groupby(["position_level", "task_id", "task_description"], sort=True)
        .agg(
            states=("snapshot_id", "size"),
            atlas_commit_sr=("atlas_commit_success", "mean"),
            support_rate=("supported", "mean"),
            query_rate=("router_query", "mean"),
            cate_mean=("predicted_cate", "mean"),
            cate_min=("predicted_cate", "min"),
            cate_max=("predicted_cate", "max"),
            support_distance_mean=("support_distance", "mean"),
        )
        .reset_index()
    )
    gate = {
        "reserve_cells": int(len(reserve)),
        "reserve_states": int(len(output)),
        "new_tasks": sorted(set(output["task_id"].astype(int)) - set(router["training_tasks"])),
        "support_rate": float(output["supported"].mean()),
        "query_rate": float(output["router_query"].mean()),
        "checks": {
            "ten_unused_boundary_cells": len(reserve) == 10,
            "fifty_outcome_blind_states": len(output) == 50,
            "contains_new_tasks": len(set(output["task_id"].astype(int)) - set(router["training_tasks"])) >= 3,
            "sufficient_feature_support": float(output["supported"].mean()) >= 0.50,
            "nondegenerate_query_rate": 0.05 <= float(output["router_query"].mean()) <= 0.80,
        },
    }
    gate["pass"] = bool(all(gate["checks"].values()))
    gate["decision"] = (
        "freeze_full_reserve_holdout" if gate["pass"] else "stop_before_feedback_collection"
    )
    output.to_parquet(output_dir / "reserve_atlas_predictions.parquet", index=False)
    summary.to_csv(output_dir / "reserve_cell_summary.csv", index=False)
    reserve.to_csv(output_dir / "reserve_cells.csv", index=False)
    (output_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Outcome-blind invariant-CATE reserve atlas",
        "",
        f"- Reserve cells / states: {len(reserve)} / {len(output)}.",
        f"- New task IDs: {gate['new_tasks']}.",
        f"- Support rate: {100 * gate['support_rate']:.1f}%.",
        f"- Query rate: {100 * gate['query_rate']:.1f}%.",
        f"- Gate: **{'PASS' if gate['pass'] else 'FAIL'}**.",
        f"- Decision: `{gate['decision']}`.",
        "",
        summary.to_markdown(index=False),
        "",
        "Feedback outcomes were not available or used in this scoring step.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(gate, indent=2))
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

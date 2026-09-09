#!/usr/bin/env python3
"""Freeze a full-reserve LIBERO-PRO holdout for the invariant CATE router."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = PROJECT_ROOT / "experiments/INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md"
DEFAULT_ROUTER = PROJECT_ROOT / "experiments/frozen_models/invariant_cate_relative_a01_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def compact_level(level: str) -> str:
    return level.replace(".", "p")


def build_config(cells: pd.DataFrame) -> dict[str, object]:
    if len(cells) != 10:
        raise ValueError(f"Expected all ten unused boundary cells, got {len(cells)}")
    jobs = []
    job_index = 0
    for cell_index, row in enumerate(cells.itertuples(index=False)):
        task_id = int(row.task_id)
        level = str(row.position_level)
        for shard_index, (lower, upper) in enumerate(((5, 14), (15, 24))):
            name = f"position_{compact_level(level)}_task{task_id}_init{lower}_{upper}"
            jobs.append(
                {
                    "name": name,
                    "kind": "pro_position_counterfactual_feedback",
                    "case_id": name,
                    "suites": "libero_object_temp",
                    "position_level": level,
                    "task_ids": str(task_id),
                    "init_state_ids": f"{lower}-{upper}",
                    "rollouts_per_init": 2,
                    "base_seed": 30_000_000 + cell_index * 100_000 + shard_index * 1_940,
                    "target_decision_states": 20,
                    "gpu_slot": job_index % 5,
                }
            )
            job_index += 1
    defaults = {
        "rollout_seed_step": 97,
        "uncertainty_seeds": "0,1,2,3",
        "max_timesteps": 280,
        "sampling_mode": "fixed_queries",
        "snapshot_query_indices": "4",
        "phase_cap_fraction": 1.0,
        "consequence_horizon_steps": 16,
        "terminal_continuation_fraction": 1.0,
        "terminal_selected_feedback_only": True,
        "continuation_num_candidates": 0,
        "skip_feedback_branch": False,
        "query_cost": 0.025,
        "num_denoising_steps_action": 5,
        "prediction_mode": "parallel",
        "continuation_prediction_mode": "parallel",
        "num_denoising_steps_future_state": 1,
        "num_denoising_steps_value": 1,
        "num_future_state_samples": 1,
        "num_value_samples": 1,
        "value_ensemble_aggregation": "average",
        "experiment_split": "holdout",
    }
    return {
        "schema_version": 1,
        "profiles": {
            "invariant_cate_reserve_holdout": {
                "description": "Frozen invariant CATE router on all ten untouched LIBERO-PRO Object boundary cells",
                "jobs": jobs,
            }
        },
        "defaults": defaults,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reserve-cells", type=Path, required=True)
    parser.add_argument("--atlas-gate", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--router", type=Path, default=DEFAULT_ROUTER)
    args = parser.parse_args()

    atlas_gate = json.loads(args.atlas_gate.read_text(encoding="utf-8"))
    if not atlas_gate.get("pass"):
        raise ValueError("Outcome-blind reserve atlas gate did not pass")
    cells = pd.read_csv(args.reserve_cells).sort_values(
        ["task_id", "position_level"]
    ).reset_index(drop=True)
    config = build_config(cells)
    args.config.parent.mkdir(parents=True, exist_ok=True)
    args.config.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    router = json.loads(args.router.read_text(encoding="utf-8"))
    training_tasks = set(int(value) for value in router["training_tasks"])
    holdout_tasks = set(cells["task_id"].astype(int))
    manifest = {
        "schema_version": 1,
        "frozen_before_feedback_outcomes": True,
        "reserve_cells": portable(args.reserve_cells),
        "reserve_cells_sha256": sha256(args.reserve_cells),
        "atlas_gate": portable(args.atlas_gate),
        "atlas_gate_sha256": sha256(args.atlas_gate),
        "campaign_config_sha256": sha256(args.config),
        "protocol_sha256": sha256(args.protocol),
        "frozen_router": portable(args.router),
        "frozen_router_file_sha256": sha256(args.router),
        "frozen_router_payload_sha256": router["frozen_payload_sha256"],
        "cells": cells.to_dict(orient="records"),
        "training_tasks": sorted(training_tasks),
        "novel_tasks": sorted(holdout_tasks - training_tasks),
        "init_state_ids": "5-24",
        "rollouts_per_init": 2,
        "target_pairs": 400,
        "minimum_strict_pairs": 380,
        "snapshot_query_idx": 4,
        "query_cost": 0.025,
        "maximum_query_rate": 0.60,
        "bootstrap_repetitions": 10_000,
        "bootstrap_seed": 20260907,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Config: {args.config}")
    print(f"Manifest: {args.manifest}")
    print(f"Cells/jobs/pairs: {len(cells)}/{len(config['profiles']['invariant_cate_reserve_holdout']['jobs'])}/400")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

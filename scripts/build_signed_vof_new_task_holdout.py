#!/usr/bin/env python3
"""Build and freeze the new-task signed-VoF holdout after the blind atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = PROJECT_ROOT / "experiments/SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md"
DEFAULT_ROUTER = PROJECT_ROOT / "experiments/frozen_models/signed_vof_pre_state_action_a10_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_level(level: str) -> str:
    return level.replace(".", "p")


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def build_config(selection: dict[str, object]) -> dict[str, object]:
    gate = selection["gate"]
    if not isinstance(gate, dict) or not gate.get("pass"):
        raise ValueError("Baseline atlas gate did not pass")
    cells = selection["cells"]
    if not isinstance(cells, list) or len(cells) != 6:
        raise ValueError(f"Expected exactly six frozen cells, got {len(cells)}")
    jobs = []
    job_index = 0
    for cell_index, cell in enumerate(cells):
        task_id = int(cell["task_id"])
        level = str(cell["position_level"])
        if task_id == 0:
            raise ValueError("Task 0 cannot enter the new-task holdout")
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
                    "base_seed": 20_000_000 + cell_index * 100_000 + shard_index * 1_940,
                    "target_decision_states": 20,
                    "gpu_slot": job_index % 6,
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
            "signed_vof_new_task_holdout": {
                "description": "Prospective frozen signed-VoF router holdout on blind-atlas-selected LIBERO-PRO Object cells",
                "jobs": jobs,
            }
        },
        "defaults": defaults,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--router", type=Path, default=DEFAULT_ROUTER)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    config = build_config(selection)
    args.config.parent.mkdir(parents=True, exist_ok=True)
    args.config.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "frozen_before_feedback_outcomes": True,
        "atlas_selection": portable_path(args.selection),
        "atlas_selection_sha256": sha256(args.selection),
        "campaign_config_sha256": sha256(args.config),
        "protocol_sha256": sha256(args.protocol),
        "frozen_router_sha256": sha256(args.router),
        "frozen_router": portable_path(args.router),
        "selected_cells": selection["cells"],
        "task_zero_excluded": True,
        "init_state_ids": "5-24",
        "rollouts_per_init": 2,
        "target_pairs": 240,
        "minimum_strict_pairs": 228,
        "snapshot_query_idx": 4,
        "query_cost": 0.025,
        "bootstrap_repetitions": 10000,
        "bootstrap_seed": 20260904,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Holdout config: {args.config}")
    print(f"Freeze manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

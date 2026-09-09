#!/usr/bin/env python3
"""Build deterministic paired video replays from closed-loop discordances."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


MODEL_PATH = "experiments/frozen_models/factor_h16_dense_ridge_v1.json"


def _balanced_take(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    buckets = {
        factor: group.sort_values(
            ["case_id", "suite", "task_id", "init_state_id", "rollout_seed"]
        ).to_dict("records")
        for factor, group in frame.groupby("factor", sort=True)
    }
    selected: list[dict[str, object]] = []
    while len(selected) < count and any(buckets.values()):
        for factor in sorted(buckets):
            if buckets[factor] and len(selected) < count:
                selected.append(buckets[factor].pop(0))
    return pd.DataFrame(selected)


def select_discordances(frame: pd.DataFrame, per_direction: int) -> pd.DataFrame:
    required = {
        "factor",
        "case_id",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "discordance",
    }
    missing = sorted(required - set(frame))
    if missing:
        raise ValueError(f"Discordance table is missing columns: {missing}")
    parts = []
    for direction in ("frozen_gain", "frozen_loss"):
        scoped = frame.loc[frame["discordance"].eq(direction)].copy()
        if not scoped.empty:
            parts.append(_balanced_take(scoped, per_direction))
    if not parts:
        raise ValueError("No frozen_gain or frozen_loss pairs are available for replay")
    selected = pd.concat(parts, ignore_index=True)
    selected["replay_index"] = selected.groupby("discordance").cumcount()
    return selected


def _position_level(case_id: str) -> str:
    for token in ("x0p3", "y0p3"):
        if token in case_id:
            return token.replace("p", ".")
    raise ValueError(f"Cannot infer position level from case_id={case_id!r}")


def _job(row: pd.Series) -> dict[str, object]:
    factor = str(row["factor"])
    direction = str(row["discordance"])
    index = int(row["replay_index"])
    suffix = (
        f"{direction}_{factor.lower()}_{index:02d}_task{int(row['task_id'])}"
        f"_init{int(row['init_state_id'])}_seed{int(row['rollout_seed'])}"
    )
    job: dict[str, object] = {
        "name": suffix,
        "case_id": f"frozen_video__{row['case_id']}__{direction}_{index:02d}",
        "suites": str(row["suite"]),
        "task_ids": str(int(row["task_id"])),
        "init_state_ids": str(int(row["init_state_id"])),
        "max_rollouts": 1,
        "base_seed": int(row["rollout_seed"]),
        "planning_frozen_ranker_factor": factor,
    }
    if factor == "Environment":
        job["kind"] = "pro_environment_planning_grid"
        job["environment_num_init_states"] = 10
        job["environment_seed"] = 20260829
    elif factor == "Position":
        job["kind"] = "pro_position_planning_grid"
        job["position_level"] = _position_level(str(row["case_id"]))
    elif factor == "Object":
        job["kind"] = "pro_planning_grid"
    else:
        raise ValueError(f"Unknown factor: {factor}")
    return job


def build_config(selected: pd.DataFrame) -> dict[str, object]:
    return {
        "schema_version": 1,
        "profiles": {
            "frozen_h16_discordant_video_replays": {
                "description": (
                    "Post-hoc paired video replays of frozen-ranker gains and losses; "
                    "excluded from primary statistics"
                ),
                "jobs": [_job(row) for _, row in selected.iterrows()],
            }
        },
        "defaults": {
            "min_success": 999,
            "min_failed": 999,
            "save_videos": True,
            "collect_prediction_errors": True,
            "collect_safety_signals": True,
            "record_denoising_trace": False,
            "terminate_on_safety_violation": False,
            "rollout_seed_step": 97,
            "uncertainty_seeds": "0,1,2,3,4,5",
            "max_timesteps": 280,
            "num_open_loop_steps": 16,
            "num_denoising_steps_action": 5,
            "prediction_mode": "parallel",
            "num_denoising_steps_future_state": 1,
            "num_denoising_steps_value": 1,
            "num_future_state_samples": 1,
            "num_value_samples": 1,
            "value_ensemble_aggregation": "average",
            "strategy_lambdas": "max_value:0 frozen_factor_ridge:0",
            "planning_frozen_ranker_model": MODEL_PATH,
            "experiment_split": "generalization",
            "record_temporal_overlap": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discordant-pairs", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    parser.add_argument("--selection-csv", type=Path, required=True)
    parser.add_argument("--per-direction", type=int, default=5)
    args = parser.parse_args()
    frame = pd.read_csv(args.discordant_pairs.expanduser().resolve())
    selected = select_discordances(frame, args.per_direction)
    config = build_config(selected)
    output = args.output_config.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    selection = args.selection_csv.expanduser().resolve()
    selection.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(selection, index=False)
    print(f"selected={len(selected)} config={output} selection={selection}")


if __name__ == "__main__":
    main()

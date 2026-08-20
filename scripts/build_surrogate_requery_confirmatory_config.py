#!/usr/bin/env python3
"""Build a frozen confirmatory campaign from surrogate screening selection."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from build_adaptive_confirmatory_config import parse_strategy_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_CONFIG = (
    PROJECT_ROOT / "experiments/configs/libero_campaign_surrogate_requery_screening.json"
)
DEFAULT_SELECTION = (
    PROJECT_ROOT
    / "experiments/campaigns/surrogate_screening_20260819/analysis/adaptive_summary"
    / "selected_for_confirmatory.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "experiments/configs/libero_campaign_surrogate_requery_confirmatory.json"
)

# Cases are frozen before screening results are used. The first six repeat the
# characterized boundary tasks with new seeds. The remaining six add distinct
# LIBERO-PRO generalization axes and object/task families.
CASES = [
    {
        "name": "known_milk",
        "case_id": "milk_task5_init0_surrogate_confirm",
        "suites": "libero_spatial_with_milk",
        "task_ids": "5",
        "init_state_ids": "0",
        "base_seed": 910000,
        "max_timesteps": 220,
    },
    {
        "name": "known_yellow",
        "case_id": "yellow_task8_init0_surrogate_confirm",
        "suites": "libero_spatial_with_yellow_book",
        "task_ids": "8",
        "init_state_ids": "0",
        "base_seed": 920000,
        "max_timesteps": 220,
    },
    {
        "name": "known_long_mug",
        "case_id": "long_mug_task4_init0_surrogate_confirm",
        "suites": "libero_10_with_mug",
        "task_ids": "4",
        "init_state_ids": "0",
        "base_seed": 930000,
        "max_timesteps": 520,
    },
    {
        "name": "known_spatial_mug",
        "case_id": "spatial_mug_task0_init0_surrogate_confirm",
        "suites": "libero_spatial_with_mug",
        "task_ids": "0",
        "init_state_ids": "0",
        "base_seed": 940000,
        "max_timesteps": 220,
    },
    {
        "name": "known_long_milk",
        "case_id": "long_milk_task9_init0_surrogate_confirm",
        "suites": "libero_10_with_milk",
        "task_ids": "9",
        "init_state_ids": "0",
        "base_seed": 950000,
        "max_timesteps": 520,
    },
    {
        "name": "known_goal_mug",
        "case_id": "goal_mug_task9_init0_surrogate_confirm",
        "suites": "libero_goal_with_mug",
        "task_ids": "9",
        "init_state_ids": "0",
        "base_seed": 960000,
        "max_timesteps": 320,
    },
    {
        "name": "new_spatial_object",
        "case_id": "new_ood_spatial_object_task0_init0_surrogate_confirm",
        "suites": "libero_spatial_object",
        "task_ids": "0",
        "init_state_ids": "0",
        "base_seed": 970000,
        "max_timesteps": 220,
    },
    {
        "name": "new_spatial_language",
        "case_id": "new_ood_spatial_lan_task6_init0_surrogate_confirm",
        "suites": "libero_spatial_lan",
        "task_ids": "6",
        "init_state_ids": "0",
        "base_seed": 980000,
        "max_timesteps": 220,
    },
    {
        "name": "new_spatial_swap",
        "case_id": "new_ood_spatial_swap_task8_init0_surrogate_confirm",
        "suites": "libero_spatial_swap",
        "task_ids": "8",
        "init_state_ids": "0",
        "base_seed": 990000,
        "max_timesteps": 220,
    },
    {
        "name": "new_goal_task",
        "case_id": "new_ood_goal_task_task6_init0_surrogate_confirm",
        "suites": "libero_goal_task",
        "task_ids": "6",
        "init_state_ids": "0",
        "base_seed": 1000000,
        "max_timesteps": 300,
    },
    {
        "name": "new_object_appearance",
        "case_id": "new_ood_object_object_task7_init0_surrogate_confirm",
        "suites": "libero_object_object",
        "task_ids": "7",
        "init_state_ids": "0",
        "base_seed": 1010000,
        "max_timesteps": 280,
    },
    {
        "name": "new_long_swap",
        "case_id": "new_ood_long_swap_task4_init0_surrogate_confirm",
        "suites": "libero_10_swap",
        "task_ids": "4",
        "init_state_ids": "0",
        "base_seed": 1020000,
        "max_timesteps": 520,
    },
]


def read_selection(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    selected = {row["selection_category"]: row["strategy_id"] for row in rows}
    expected = {"non_surrogate_adaptive", "surrogate_adaptive"}
    if set(selected) != expected:
        raise ValueError(
            f"Expected exactly {sorted(expected)}, got {sorted(selected)} from {path}"
        )
    return selected


def build_config(
    base_config: dict,
    selected: dict[str, str],
    *,
    max_rollouts: int,
) -> dict:
    controls = {
        "max_value": "max_value:0",
        "action_l1": "uncertainty_penalty_action:1.0",
        "requery_l1_h8": "disagreement_requery_action:1.0",
    }
    parsed = {
        category: parse_strategy_id(strategy_id)
        for category, strategy_id in selected.items()
    }

    jobs: list[dict[str, object]] = []
    for case_index, case in enumerate(CASES):
        common: dict[str, object] = {
            "kind": "pro_planning_grid",
            "experiment_split": "holdout",
            "max_rollouts": max_rollouts,
            **{key: value for key, value in case.items() if key != "name"},
        }
        jobs.append(
            {
                "name": f"{case['name']}__controls",
                "gpu_slot": len(jobs),
                **common,
                "strategy_lambdas": " ".join(controls.values()),
            }
        )
        for category in ("non_surrogate_adaptive", "surrogate_adaptive"):
            strategy_id = selected[category]
            if strategy_id in controls:
                continue
            token, overrides = parsed[category]
            jobs.append(
                {
                    "name": f"{case['name']}__{category}",
                    "gpu_slot": len(jobs),
                    **common,
                    "strategy_lambdas": token,
                    **overrides,
                }
            )

    defaults = dict(base_config["defaults"])
    defaults.update(
        {
            "save_videos": False,
            "collect_prediction_errors": True,
            "collect_safety_signals": True,
            "record_denoising_trace": False,
            "rollout_seed_step": 97,
            "num_open_loop_steps": 16,
            "num_denoising_steps_action": 10,
            "prediction_mode": "parallel",
            "planning_short_open_loop_steps": 8,
        }
    )
    return {
        "schema_version": 1,
        "profiles": {
            "surrogate_confirmatory": {
                "description": (
                    "Frozen paired confirmatory evaluation on 12 cases: "
                    f"non-surrogate={selected['non_surrogate_adaptive']}, "
                    f"surrogate={selected['surrogate_adaptive']}"
                ),
                "jobs": jobs,
            }
        },
        "defaults": defaults,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    parser.add_argument("--selection-csv", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rollouts", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_rollouts < 1:
        raise ValueError("--max-rollouts must be positive")
    selected = read_selection(args.selection_csv)
    base_config = json.loads(args.base_config.read_text(encoding="utf-8"))
    config = build_config(base_config, selected, max_rollouts=args.max_rollouts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Selected: " + ", ".join(f"{key}={value}" for key, value in selected.items()))
    print(f"Jobs: {len(config['profiles']['surrogate_confirmatory']['jobs'])}")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

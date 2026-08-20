#!/usr/bin/env python3
"""Build the preregistered surrogate/phase requery screening campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments/configs/libero_campaign_surrogate_requery_screening.json"
CASES = [
    {
        "slug": "milk",
        "case_id": "milk_task5_init0_surrogate_screen",
        "suite": "libero_spatial_with_milk",
        "task_id": 5,
        "max_timesteps": 220,
        "base_seed": 810000,
    },
    {
        "slug": "yellow",
        "case_id": "yellow_task8_init0_surrogate_screen",
        "suite": "libero_spatial_with_yellow_book",
        "task_id": 8,
        "max_timesteps": 220,
        "base_seed": 820000,
    },
    {
        "slug": "long_mug",
        "case_id": "long_mug_task4_init0_surrogate_screen",
        "suite": "libero_10_with_mug",
        "task_id": 4,
        "max_timesteps": 520,
        "base_seed": 830000,
    },
    {
        "slug": "spatial_mug",
        "case_id": "spatial_mug_task0_init0_surrogate_screen",
        "suite": "libero_spatial_with_mug",
        "task_id": 0,
        "max_timesteps": 220,
        "base_seed": 840000,
    },
    {
        "slug": "long_milk",
        "case_id": "long_milk_task9_init0_surrogate_screen",
        "suite": "libero_10_with_milk",
        "task_id": 9,
        "max_timesteps": 520,
        "base_seed": 850000,
    },
    {
        "slug": "goal_mug",
        "case_id": "goal_mug_task9_init0_surrogate_screen",
        "suite": "libero_goal_with_mug",
        "task_id": 9,
        "max_timesteps": 320,
        "base_seed": 860000,
    },
]
CORE_CONTROL_STRATEGIES = " ".join(
    [
        "max_value:0",
        "uncertainty_penalty_action:1.0",
        "phase_gated_action:1.0",
        "disagreement_requery_action:1.0",
        "phase_requery_action:1.0",
    ]
)
CORE_SURROGATE_STRATEGIES = " ".join(
    [
        "surrogate_gated_requery_action:1.0",
        "surrogate_horizon_action:1.0",
        "surrogate_disagreement_requery_action:1.0",
        "phase_surrogate_requery_action:1.0",
    ]
)
SURROGATE_SWEEP_STRATEGIES = " ".join(
    [
        "surrogate_gated_requery_action:1.0",
        "surrogate_horizon_action:1.0",
        "phase_surrogate_requery_action:1.0",
    ]
)
PHASE_SWEEP_STRATEGIES = "phase_requery_action:1.0 phase_surrogate_requery_action:1.0"


def job(case: dict[str, object], gpu_slot: int, suffix: str, **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "name": f"{case['slug']}__{suffix}",
        "kind": "pro_planning_grid",
        "gpu_slot": gpu_slot,
        "case_id": case["case_id"],
        "experiment_split": "calibration",
        "suites": case["suite"],
        "task_ids": str(case["task_id"]),
        "init_state_ids": "0",
        "max_rollouts": 8,
        "base_seed": case["base_seed"],
        "max_timesteps": case["max_timesteps"],
    }
    result.update(overrides)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke_case = CASES[0]
    smoke = [
        job(
            smoke_case,
            0,
            "smoke",
            max_rollouts=1,
            strategy_lambdas=(
                "phase_requery_action:1.0 surrogate_gated_requery_action:1.0 "
                "surrogate_horizon_action:1.0 surrogate_disagreement_requery_action:1.0 "
                "phase_surrogate_requery_action:1.0"
            ),
            planning_phase_fraction=0.3,
            planning_surrogate_error_threshold=0.08841767562905925,
        )
    ]
    screening = []
    for gpu_slot, case in enumerate(CASES):
        screening.extend(
            [
                job(
                    case,
                    gpu_slot,
                    "core_controls",
                    strategy_lambdas=CORE_CONTROL_STRATEGIES,
                    planning_phase_fraction=0.3,
                    planning_surrogate_error_threshold=0.08841767562905925,
                ),
                job(
                    case,
                    gpu_slot + len(CASES),
                    "core_surrogate",
                    strategy_lambdas=CORE_SURROGATE_STRATEGIES,
                    planning_phase_fraction=0.3,
                    planning_surrogate_error_threshold=0.08841767562905925,
                ),
                job(
                    case,
                    gpu_slot,
                    "surrogate_q60",
                    strategy_lambdas=SURROGATE_SWEEP_STRATEGIES,
                    planning_phase_fraction=0.3,
                    planning_surrogate_error_threshold=0.06300548431629303,
                ),
                job(
                    case,
                    gpu_slot + len(CASES),
                    "surrogate_q90",
                    strategy_lambdas=SURROGATE_SWEEP_STRATEGIES,
                    planning_phase_fraction=0.3,
                    planning_surrogate_error_threshold=0.1468499806786273,
                ),
                job(
                    case,
                    gpu_slot + len(CASES),
                    "phase_r05",
                    strategy_lambdas=PHASE_SWEEP_STRATEGIES,
                    planning_phase_fraction=0.5,
                    planning_surrogate_error_threshold=0.08841767562905925,
                ),
            ]
        )

    config = {
        "schema_version": 1,
        "profiles": {
            "surrogate_smoke": {
                "description": "One-rollout smoke test for the frozen prediction-error surrogate strategies.",
                "jobs": smoke,
            },
            "surrogate_screening": {
                "description": (
                    "Paired screening of surrogate-triggered and phase-aware replanning on six "
                    "LIBERO-PRO boundary cases with seeds disjoint from prior campaigns."
                ),
                "jobs": screening,
            },
        },
        "defaults": {
            "uncertainty_seeds": "0,1,2,3",
            "min_success": 999,
            "min_failed": 999,
            "save_videos": False,
            "collect_prediction_errors": True,
            "collect_safety_signals": True,
            "record_denoising_trace": False,
            "terminate_on_safety_violation": False,
            "rollout_seed_step": 97,
            "num_open_loop_steps": 16,
            "num_denoising_steps_action": 10,
            "prediction_mode": "parallel",
            "num_denoising_steps_future_state": 1,
            "num_denoising_steps_value": 1,
            "num_future_state_samples": 1,
            "num_value_samples": 1,
            "value_ensemble_aggregation": "average",
            "planning_action_weight": 0.5,
            "planning_difficulty_threshold": 0.088588,
            "planning_value_margin": 0.002,
            "planning_uncertainty_margin": 0.0,
            "planning_phase_fraction": 0.3,
            "planning_short_open_loop_steps": 8,
            "planning_surrogate_error_threshold": 0.08841767562905925,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

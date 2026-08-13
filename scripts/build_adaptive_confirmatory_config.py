#!/usr/bin/env python3
"""Build the frozen adaptive-planning confirmatory campaign config."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Sequence


CASES = [
    {
        "name": "known_milk",
        "case_id": "milk_task5_init0_adaptive_confirm",
        "suites": "libero_spatial_with_milk",
        "task_ids": "5",
        "init_state_ids": "0",
        "base_seed": 710000,
        "max_timesteps": 220,
    },
    {
        "name": "known_yellow",
        "case_id": "yellow_task8_init0_adaptive_confirm",
        "suites": "libero_spatial_with_yellow_book",
        "task_ids": "8",
        "init_state_ids": "0",
        "base_seed": 720000,
        "max_timesteps": 220,
    },
    {
        "name": "known_long_mug",
        "case_id": "long_mug_task4_init0_adaptive_confirm",
        "suites": "libero_10_with_mug",
        "task_ids": "4",
        "init_state_ids": "0",
        "base_seed": 730000,
        "max_timesteps": 520,
    },
    {
        "name": "holdout_spatial_mug",
        "case_id": "spatial_mug_task0_init0_adaptive_confirm",
        "suites": "libero_spatial_with_mug",
        "task_ids": "0",
        "init_state_ids": "0",
        "base_seed": 740000,
        "max_timesteps": 220,
    },
    {
        "name": "holdout_long_milk",
        "case_id": "long_milk_task9_init0_adaptive_confirm",
        "suites": "libero_10_with_milk",
        "task_ids": "9",
        "init_state_ids": "0",
        "base_seed": 750000,
        "max_timesteps": 520,
    },
    {
        "name": "holdout_goal_mug",
        "case_id": "goal_mug_task9_init0_adaptive_confirm",
        "suites": "libero_goal_with_mug",
        "task_ids": "9",
        "init_state_ids": "0",
        "base_seed": 760000,
        "max_timesteps": 320,
    },
]


def number(text: str) -> float:
    return float(text)


def parse_strategy_id(strategy_id: str) -> tuple[str, dict[str, float | int]]:
    patterns: list[tuple[str, str]] = [
        (
            r"difficulty_requery_l(?P<risk>[-+0-9.eE]+)_t(?P<threshold>[-+0-9.eE]+)_h(?P<horizon>\d+)",
            "difficulty_gated_requery_action",
        ),
        (
            r"difficulty_l(?P<risk>[-+0-9.eE]+)_t(?P<threshold>[-+0-9.eE]+)",
            "difficulty_gated_action",
        ),
        (
            r"margin_l(?P<risk>[-+0-9.eE]+)_v(?P<value_margin>[-+0-9.eE]+)_u(?P<uncertainty_margin>[-+0-9.eE]+)",
            "margin_gated_action",
        ),
        (r"consensus_l(?P<risk>[-+0-9.eE]+)", "consensus_action"),
        (
            r"phase_l(?P<risk>[-+0-9.eE]+)_r(?P<phase_fraction>[-+0-9.eE]+)",
            "phase_gated_action",
        ),
        (
            r"requery_l(?P<risk>[-+0-9.eE]+)_h(?P<horizon>\d+)",
            "disagreement_requery_action",
        ),
    ]
    for pattern, planning_strategy in patterns:
        match = re.fullmatch(pattern, strategy_id)
        if match is None:
            continue
        values = match.groupdict()
        overrides: dict[str, float | int] = {}
        if values.get("threshold") is not None:
            overrides["planning_difficulty_threshold"] = number(values["threshold"])
        if values.get("value_margin") is not None:
            overrides["planning_value_margin"] = number(values["value_margin"])
        if values.get("uncertainty_margin") is not None:
            overrides["planning_uncertainty_margin"] = number(values["uncertainty_margin"])
        if values.get("phase_fraction") is not None:
            overrides["planning_phase_fraction"] = number(values["phase_fraction"])
        if values.get("horizon") is not None:
            overrides["planning_short_open_loop_steps"] = int(values["horizon"])
        return f"{planning_strategy}:{number(values['risk']):g}", overrides
    raise ValueError(f"Unsupported selected strategy_id: {strategy_id}")


def read_selected(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    by_category = {row["selection_category"]: row["strategy_id"] for row in rows}
    expected = {"no_extra_inference", "adaptive_horizon"}
    if set(by_category) != expected:
        raise ValueError(
            f"Expected exactly categories {sorted(expected)}, got {sorted(by_category)}"
        )
    return {
        "no_extra_inference": by_category["no_extra_inference"],
        "adaptive_horizon": by_category["adaptive_horizon"],
    }


def build_config(
    base_config: dict,
    selected_by_category: dict[str, str],
    *,
    max_rollouts: int,
) -> dict:
    control_tokens = [
        "max_value:0",
        "max_value_replay:0",
        "uncertainty_penalty_action:1.0",
        "uncertainty_penalty_action_replay:1.0",
    ]
    selected = {
        category: parse_strategy_id(strategy_id)
        for category, strategy_id in selected_by_category.items()
    }

    jobs = []
    for gpu_slot, case in enumerate(CASES):
        common = {
            "kind": "pro_planning_grid",
            "gpu_slot": gpu_slot,
            # The collector's split vocabulary uses "holdout" for frozen
            # confirmatory evaluation; the campaign name records the protocol.
            "experiment_split": "holdout",
            "max_rollouts": max_rollouts,
            **{key: value for key, value in case.items() if key != "name"},
        }
        jobs.append(
            {
                "name": f"{case['name']}__controls",
                **common,
                "strategy_lambdas": " ".join(control_tokens),
            }
        )
        for category in ("no_extra_inference", "adaptive_horizon"):
            token, overrides = selected[category]
            jobs.append(
                {
                    "name": f"{case['name']}__{category}",
                    **common,
                    "strategy_lambdas": token,
                    **overrides,
                }
            )

    return {
        "schema_version": 1,
        "profiles": {
            "adaptive_confirmatory": {
                "description": (
                    "Frozen paired confirmatory evaluation of "
                    + ", ".join(selected_by_category.values())
                ),
                "jobs": jobs,
            }
        },
        "defaults": base_config["defaults"],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--selection-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rollouts", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_rollouts < 1:
        raise ValueError("--max-rollouts must be positive")
    selected_by_category = read_selected(args.selection_csv)
    base_config = json.loads(args.base_config.read_text(encoding="utf-8"))
    config = build_config(
        base_config, selected_by_category, max_rollouts=args.max_rollouts
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(
        "Selected: "
        + ", ".join(
            f"{category}={strategy_id}"
            for category, strategy_id in selected_by_category.items()
        )
    )
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

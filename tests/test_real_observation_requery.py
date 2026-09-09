from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_real_observation_requery import (
    aggregate_episodes,
    evaluate_gates,
    method_from_row,
)


ROOT = Path(__file__).resolve().parents[1]


def test_campaign_uses_frozen_untouched_split_and_three_methods() -> None:
    config = json.loads(
        (ROOT / "experiments/configs/libero_campaign_real_observation_requery.json").read_text()
    )
    jobs = config["profiles"]["real_observation_requery_holdout"]["jobs"]

    assert len(jobs) == 9
    assert {job["init_state_ids"] for job in jobs} == {"40-49"}
    assert config["defaults"]["experiment_split"] == "holdout"
    assert {job["strategy_lambdas"] for job in jobs} == {
        "max_value:0",
        "max_value_gripper_requery:0",
    }
    assert {
        (job["num_open_loop_steps"], job["strategy_lambdas"])
        for job in jobs
    } == {
        (16, "max_value:0"),
        (8, "max_value:0"),
        (16, "max_value_gripper_requery:0"),
    }


def test_episode_aggregation_computes_actual_query_multiplier() -> None:
    traces = pd.DataFrame(
        {
            "method": ["maxV-gripper-H8/H16"] * 6,
            "factor": ["Object"] * 6,
            "case_id": ["feedback_object_task0"] * 6,
            "suite": ["libero_object_object"] * 6,
            "task_id": [0] * 6,
            "init_state_id": [40] * 6,
            "rollout_seed": [7100000] * 6,
            "query_idx": list(range(6)),
            "final_t": [80] * 6,
            "success": [True] * 6,
            "planning_requery_triggered": [False, True, False, False, True, False],
            "max_value_selected": [True] * 6,
        }
    )

    episodes = aggregate_episodes(traces)

    assert len(episodes) == 1
    assert episodes.iloc[0]["query_count"] == 6
    assert episodes.iloc[0]["h16_reference_queries"] == 5
    assert episodes.iloc[0]["query_multiplier"] == 1.2
    assert episodes.iloc[0]["requery_count"] == 2


def test_method_mapping_keeps_selection_and_horizon_separate() -> None:
    assert method_from_row(pd.Series({"planning_strategy": "max_value", "num_open_loop_steps": 16})) == "maxV-H16"
    assert method_from_row(pd.Series({"planning_strategy": "max_value", "num_open_loop_steps": 8})) == "maxV-H8"
    assert method_from_row(
        pd.Series(
            {
                "planning_strategy": "max_value_gripper_requery",
                "num_open_loop_steps": 16,
            }
        )
    ) == "maxV-gripper-H8/H16"


def test_preregistered_gate_requires_success_and_compute_conditions() -> None:
    method_summary = pd.DataFrame(
        {
            "method": ["maxV-H16", "maxV-H8", "maxV-gripper-H8/H16"],
            "mean_query_multiplier": [1.0, 1.9, 1.4],
        }
    )
    contrasts = pd.DataFrame(
        {
            "method": ["maxV-H8", "maxV-gripper-H8/H16"],
            "rescues": [3, 4],
            "harms": [1, 1],
            "delta_success_rate": [0.05, 0.075],
        }
    )
    factor_delta = pd.DataFrame(
        {
            "method": ["maxV-gripper-H8/H16"] * 3,
            "delta_success_states": [1, 0, 2],
        }
    )
    utilities = pd.DataFrame(
        {
            "query_cost": [0.025] * 3,
            "method": ["maxV-H16", "maxV-H8", "maxV-gripper-H8/H16"],
            "mean_utility": [0.4, 0.42, 0.45],
        }
    )

    gates = evaluate_gates(method_summary, contrasts, factor_delta, utilities)

    assert gates["adaptive_gate_passed"] is True
    assert gates["fixed_h8_mechanism_supported"] is True

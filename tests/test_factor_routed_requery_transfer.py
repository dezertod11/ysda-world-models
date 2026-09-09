from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_factor_routed_requery_transfer import (
    ADAPTIVE,
    BASELINE,
    ROUTED,
    _json_default,
    build_factor_route,
    evaluate_gate,
)


ROOT = Path(__file__).resolve().parents[1]


def test_transfer_config_uses_new_tasks_and_balanced_gpu_slots() -> None:
    config = json.loads(
        (
            ROOT
            / "experiments/configs/libero_campaign_factor_routed_requery_transfer.json"
        ).read_text()
    )
    jobs = config["profiles"]["factor_routed_requery_transfer"]["jobs"]

    assert len(jobs) == 6
    assert {job["init_state_ids"] for job in jobs} == {"40-49"}
    assert {job["gpu_slot"] for job in jobs} == {0, 1, 2}
    assert config["defaults"]["experiment_split"] == "generalization"
    assert {
        job["task_ids"] for job in jobs if "object_" in job["name"]
    } == {"1-3"}
    assert {
        job["task_ids"] for job in jobs if "position_" in job["name"]
    } == {"1-3"}
    assert {
        job["task_ids"] for job in jobs if "environment_" in job["name"]
    } == {"1,3,4"}


def episode(method: str, factor: str, success: bool, multiplier: float) -> dict:
    key = f"{factor}|suite|task1|init40|seed1"
    return {
        "state_key": key,
        "method": method,
        "factor": factor,
        "case_id": factor.lower(),
        "suite": "suite",
        "task_id": 1,
        "init_state_id": 40,
        "rollout_seed": 1,
        "success": success,
        "final_t": 100,
        "query_count": 10,
        "h16_reference_queries": 7,
        "query_multiplier": multiplier,
        "requery_count": 2,
        "trigger_rate": 0.2,
        "max_value_selected_rate": 1.0,
        "timeout": False,
        "time_to_success": 100.0 if success else float("nan"),
        "target_drop_candidate": False,
        "wrong_object_interaction": False,
        "official_safety_violation": False,
    }


def test_factor_route_keeps_object_h16_and_uses_adaptive_elsewhere() -> None:
    rows = []
    for factor in ["Object", "Position", "Environment"]:
        rows.append(episode(BASELINE, factor, success=False, multiplier=1.0))
        rows.append(episode(ADAPTIVE, factor, success=True, multiplier=1.4))
    episodes = pd.DataFrame(rows)

    route = build_factor_route(episodes).set_index("factor")

    assert set(route["method"]) == {ROUTED}
    assert bool(route.loc["Object", "success"]) is False
    assert route.loc["Object", "routed_source_method"] == BASELINE
    assert bool(route.loc["Position", "success"]) is True
    assert route.loc["Position", "routed_source_method"] == ADAPTIVE
    assert bool(route.loc["Environment", "success"]) is True
    assert route.loc["Environment", "routed_source_method"] == ADAPTIVE


def test_transfer_gate_checks_factor_and_compute_constraints() -> None:
    method_summary = pd.DataFrame(
        {
            "method": [BASELINE, ADAPTIVE, ROUTED],
            "mean_query_multiplier": [1.0, 1.4, 1.25],
        }
    )
    contrasts = pd.DataFrame(
        {
            "method": [ADAPTIVE, ROUTED],
            "rescues": [7, 6],
            "harms": [3, 1],
            "delta_success_rate": [0.04, 0.06],
        }
    )
    factor_contrasts = pd.DataFrame(
        {
            "factor": ["Object", "Position", "Environment"],
            "method": [ROUTED] * 3,
            "delta_success_rate": [0.0, 0.1, 0.1],
        }
    )
    utilities = pd.DataFrame(
        {
            "query_cost": [0.025] * 3,
            "method": [BASELINE, ADAPTIVE, ROUTED],
            "mean_utility": [0.2, 0.21, 0.24],
        }
    )

    gate = evaluate_gate(
        method_summary,
        contrasts,
        factor_contrasts,
        utilities,
        {"passed": True},
    )

    assert gate["gate_passed"] is True


def test_json_summary_serializes_numpy_scalars() -> None:
    payload = {"integer": np.int64(3), "flag": np.bool_(True)}

    assert json.loads(json.dumps(payload, default=_json_default)) == {
        "integer": 3,
        "flag": True,
    }

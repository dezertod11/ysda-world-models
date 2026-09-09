from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_phase_vof_terminal_transfer import (
    PHASE_ROUTE,
    TRIGGER_PHASES,
    paired_contrasts,
    prepare_states,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase_vof_config_is_independent_and_compute_reduced() -> None:
    config = json.loads(
        (
            ROOT
            / "experiments/configs/libero_campaign_phase_vof_terminal_transfer.json"
        ).read_text()
    )
    profile = config["profiles"]["phase_vof_terminal_transfer"]
    jobs = profile["jobs"]
    defaults = config["defaults"]

    assert [job["task_ids"] for job in jobs] == ["5", "8", "9", "9"]
    assert [job["init_state_ids"] for job in jobs] == [
        "10-19",
        "10-14",
        "10-14",
        "15-19",
    ]
    assert [job["target_decision_states"] for job in jobs] == [34, 14, 15, 15]
    assert {job["gpu_slot"] for job in jobs} == {0, 1, 3, 4}
    assert jobs[3]["base_seed"] == 9500000 + 10 * 97
    assert defaults["terminal_continuation_fraction"] == 1.0
    assert defaults["terminal_selected_feedback_only"] is True
    assert defaults["experiment_split"] == "generalization"


def test_frozen_phase_rule_uses_only_grasp_and_transport() -> None:
    rows = []
    for index, phase in enumerate(["approach", "grasp", "transport", "release"]):
        rows.append(
            {
                "source_run": "run",
                "snapshot_id": f"state{index}",
                "suite": "libero_object_env",
                "task_id": 5,
                "init_state_id": 10 + index,
                "rollout_seed": 100 + index,
                "phase_at_snapshot": phase,
                "experiment_split": "generalization",
                "main_open_replay_state_max_abs": 0.0,
                "dense_vof_v2": 0.1 if phase in TRIGGER_PHASES else -0.1,
                "open_terminal_available": True,
                "feedback_terminal_available": True,
                "open_terminal_success": False,
                "feedback_terminal_success": True,
                "open_terminal_target_drop_candidate": False,
                "feedback_terminal_target_drop_candidate": False,
                "open_terminal_wrong_object_interaction_candidate": False,
                "feedback_terminal_wrong_object_interaction_candidate": False,
                "open_terminal_official_safety_violation": False,
                "feedback_terminal_official_safety_violation": False,
            }
        )

    states = prepare_states(pd.DataFrame(rows))

    assert states.loc[states["trigger"], "phase"].tolist() == ["grasp", "transport"]
    assert states["route_success"].tolist() == [False, True, True, False]
    contrast = paired_contrasts(states)
    route = contrast.loc[contrast["method"].eq(PHASE_ROUTE)].iloc[0]
    assert int(route["rescues"]) == 2
    assert int(route["harms"]) == 0

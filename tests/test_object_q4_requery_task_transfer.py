from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_object_q4_requery_task_transfer import validate_transfer


ROOT = Path(__file__).resolve().parents[1]


def test_transfer_config_is_frozen_on_untouched_tasks() -> None:
    config = json.loads(
        (
            ROOT
            / "experiments/configs/libero_campaign_object_q4_requery_task_transfer_20260901.json"
        ).read_text()
    )
    jobs = config["profiles"]["object_q4_requery_task_transfer"]["jobs"]
    defaults = config["defaults"]

    assert [job["task_ids"] for job in jobs] == ["1-2", "3-4", "5-6", "7", "8", "9"]
    assert {job["init_state_ids"] for job in jobs} == {"40-49"}
    assert sum(int(job["target_decision_states"]) for job in jobs) == 180
    assert {job["gpu_slot"] for job in jobs} == set(range(6))
    assert defaults["snapshot_query_indices"] == "4"
    assert defaults["consequence_horizon_steps"] == 16
    assert defaults["terminal_selected_feedback_only"] is True
    assert defaults["query_cost"] == 0.025


def test_transfer_integrity_requires_balanced_task_init_coverage() -> None:
    rows = []
    for task_id in [1, 2]:
        for init_state_id in [40, 41]:
            for rollout_id in [0, 1]:
                rows.append(
                    {
                        "suite": "libero_object_object",
                        "task_id": task_id,
                        "init_state_id": init_state_id,
                        "query_idx": 4,
                        "analysis_state_key": f"{task_id}|{init_state_id}|{rollout_id}",
                        "main_open_replay_state_max_abs": 1e-13,
                    }
                )
    manifest = {
        "suite": "libero_object_object",
        "task_ids": [1, 2],
        "init_state_ids": [40, 41],
        "snapshot_query_indices": [4],
        "target_pairs": 8,
        "rollouts_per_task_init": 2,
        "replay_integrity_threshold": 1e-9,
    }

    valid = validate_transfer(pd.DataFrame(rows), manifest)
    assert valid["valid"] is True

    incomplete = validate_transfer(pd.DataFrame(rows[:-1]), manifest)
    assert incomplete["valid"] is False


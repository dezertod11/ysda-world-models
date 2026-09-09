from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_cosmos_query_reproducibility import compare_artifacts
from scripts.analyze_object_q4_shared_prefix_replication import (
    expected_keys,
    validate_integrity,
)
from scripts.diagnose_cosmos_query_reproducibility import within_process_diagnostics
from scripts.run_libero_experiment_campaign import expand_jobs, load_campaign


ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, object]:
    return {
        "suite": "libero_object_object",
        "task_ids": [0],
        "snapshot_query_idx": 4,
        "init_state_ids": [0],
        "rollouts_per_init": 2,
        "rollout_seed_step": 97,
        "target_pairs": 2,
        "num_candidates": 4,
        "experiment_split": "holdout",
        "replay_integrity_threshold": 1e-9,
        "minimum_strict_replay_pairs": 2,
        "shards": [{"init_state_ids": [0], "base_seed": 1000}],
    }


def test_frozen_config_has_100_shared_prefix_pairs() -> None:
    campaign = load_campaign(
        ROOT
        / "experiments/configs/libero_campaign_object_q4_shared_prefix_replication_20260902.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["object_q4_shared_prefix_replication"],
        campaign["defaults"],
    )
    assert len(jobs) == 5
    assert sum(int(job["target_decision_states"]) for job in jobs) == 100
    assert all(job["snapshot_query_indices"] == "4" for job in jobs)
    assert all(job["terminal_continuation_fraction"] == 1.0 for job in jobs)
    assert all(job["terminal_selected_feedback_only"] is True for job in jobs)


def test_expected_keys_use_shard_local_episode_order() -> None:
    assert expected_keys(_manifest()) == {(0, 0, 1000), (0, 1, 1097)}


def test_integrity_accepts_complete_exact_state_pairs() -> None:
    rows = []
    candidates = []
    for rollout_id, seed in enumerate((1000, 1097)):
        snapshot = f"state-{rollout_id}"
        rows.append(
            {
                "snapshot_id": snapshot,
                "suite": "libero_object_object",
                "task_id": 0,
                "init_state_id": 0,
                "rollout_id": rollout_id,
                "rollout_seed": seed,
                "query_idx": 4,
                "experiment_split": "holdout",
                "feedback_feedback_requery_performed": True,
                "open_terminal_success": False,
                "feedback_terminal_success": True,
                "main_open_replay_state_max_abs": 0.0,
            }
        )
        for index in range(4):
            candidates.append(
                {
                    "snapshot_id": snapshot,
                    "candidate_is_max_value": index == 2,
                }
            )
    checks = validate_integrity(pd.DataFrame(rows), pd.DataFrame(candidates), _manifest())
    assert checks["valid"] is True


def test_repeatability_helpers_detect_cross_process_drift() -> None:
    actions = np.zeros((2, 2, 4, 16, 7), dtype=np.float32)
    values = np.zeros((2, 2, 4), dtype=np.float32)
    selected = np.zeros((2, 2), dtype=np.int64)
    assert within_process_diagnostics(actions, values, selected)["exact"] is True

    common = {
        "init_state_ids": np.array([0, 1]),
        "candidate_seeds": np.zeros((2, 4), dtype=np.int64),
        "observation_hashes": np.array(["a", "b"]),
        "simulator_hashes": np.array(["c", "d"]),
        "actions": actions,
        "values": values,
        "selected_indices": selected,
    }
    drifted = {key: value.copy() for key, value in common.items()}
    drifted["actions"][0, 0, 0, 0, 0] = 1e-3
    result = compare_artifacts(
        common, drifted, action_tolerance=1e-5, value_tolerance=1e-5
    )
    assert result["inputs_match"] is True
    assert result["strict_match"] is False

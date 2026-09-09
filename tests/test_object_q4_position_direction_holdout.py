from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_object_q4_cross_factor_boundary_screen import expected_keys
from scripts.analyze_object_q4_position_direction_holdout import (
    attach_holdout_metadata,
    interaction_bootstrap,
)
from scripts.run_libero_experiment_campaign import expand_jobs, load_campaign


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/configs/libero_campaign_object_q4_position_direction_holdout_20260902.json"
MANIFEST = ROOT / "experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_FREEZE_MANIFEST_20260902.json"


def test_config_expands_to_six_shards_and_120_pairs() -> None:
    campaign = load_campaign(CONFIG)
    jobs = expand_jobs(
        campaign["profiles"]["object_q4_position_direction_holdout"],
        campaign["defaults"],
    )
    assert len(jobs) == 6
    assert sum(int(job["target_decision_states"]) for job in jobs) == 120
    assert {job["position_level"] for job in jobs} == {"x0.2", "y0.2"}
    assert all(job["rollouts_per_init"] == 2 for job in jobs)
    assert all(job["experiment_split"] == "holdout" for job in jobs)


def test_manifest_has_complete_unique_key_schedule() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    keys = expected_keys(manifest)
    assert len(keys) == 120
    assert len({key[-1] for key in keys}) == 120
    assert {key[2] for key in keys} == set(range(20, 50))


def test_holdout_metadata_clusters_two_rollouts_by_condition_and_init() -> None:
    manifest = {
        "cells": [
            {
                "case_id": "y_shard",
                "condition_id": "position_y0p2_task0",
                "factor": "Position",
                "position_level": "y0.2",
                "shard": "init20_29",
            }
        ]
    }
    frame = pd.DataFrame(
        {
            "case_id": ["y_shard", "y_shard"],
            "init_state_id": [20, 20],
            "factor": ["Object", "Object"],
            "independent_group": ["old-a", "old-b"],
        }
    )
    result = attach_holdout_metadata(frame, manifest)
    assert result["independent_group"].nunique() == 1
    assert result["independent_group"].iloc[0] == "position_y0p2_task0|init20"
    assert set(result["factor"]) == {"Position"}


def test_interaction_bootstrap_uses_matched_init_clusters() -> None:
    rows = []
    for init_state_id in range(20, 25):
        for rollout_id in range(2):
            rows.append(
                {
                    "condition_id": "position_y0p2_task0",
                    "init_state_id": init_state_id,
                    "terminal_effect": 1,
                }
            )
            rows.append(
                {
                    "condition_id": "position_x0p2_task0",
                    "init_state_id": init_state_id,
                    "terminal_effect": 0,
                }
            )
    result = interaction_bootstrap(
        pd.DataFrame(rows),
        primary_condition="position_y0p2_task0",
        control_condition="position_x0p2_task0",
        repetitions=100,
        seed=7,
    )
    assert result["shared_init_clusters"] == 5
    assert result["interaction_delta"] == 1.0
    assert result["interaction_ci_low"] == 1.0
    assert result["interaction_ci_high"] == 1.0

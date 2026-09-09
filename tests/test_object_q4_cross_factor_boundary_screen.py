from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.analyze_object_q4_cross_factor_boundary_screen import (
    add_boundary_flags,
    attach_cell_metadata,
    expected_keys,
    validate_integrity,
)
from scripts.run_libero_experiment_campaign import expand_jobs, load_campaign


ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, object]:
    return {
        "rollouts_per_init": 1,
        "rollout_seed_step": 97,
        "minimum_effect_direction_pairs": 3,
        "minimum_discordant_pairs": 3,
        "minimum_pooled_successes": 4,
        "minimum_pooled_failures": 4,
        "cells": [
            {
                "case_id": "position_x0p2_task0",
                "suite": "libero_object_temp",
                "init_state_ids": [0, 1],
                "base_seed": 1000,
            }
        ],
    }


def test_config_expands_to_five_cells_and_100_pairs() -> None:
    campaign = load_campaign(
        ROOT
        / "experiments/configs/libero_campaign_object_q4_cross_factor_boundary_screen_20260902.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["object_q4_cross_factor_boundary_screen"],
        campaign["defaults"],
    )
    assert len(jobs) == 5
    assert sum(int(job["target_decision_states"]) for job in jobs) == 100
    assert {job["case_id"] for job in jobs} == {
        "position_x0p1_task0",
        "position_x0p2_task0",
        "position_y0p2_task0",
        "position_y0p3_task0",
        "environment_task0",
    }
    assert all(job["snapshot_query_indices"] == "4" for job in jobs)


def test_expected_keys_use_cell_local_seed_order() -> None:
    assert expected_keys(_manifest()) == {
        ("position_x0p2_task0", "libero_object_temp", 0, 0, 1000),
        ("position_x0p2_task0", "libero_object_temp", 1, 0, 1097),
    }


def test_frozen_cell_factor_overrides_suite_derived_factor() -> None:
    manifest = _manifest()
    manifest["cells"][0]["factor"] = "Position"
    manifest["cells"][0]["position_level"] = "x0.2"
    frame = pd.DataFrame(
        {
            "case_id": ["position_x0p2_task0"],
            "factor": ["Object"],
            "independent_group": ["group-0"],
        }
    )

    result = attach_cell_metadata(frame, manifest)

    assert result.loc[0, "factor"] == "Position"
    assert result.loc[0, "perturbation"] == "x0.2"
    assert result.loc[0, "independent_group"] == "position_x0p2_task0|group-0"


def test_boundary_flags_distinguish_selector_and_efficacy_support() -> None:
    rows = pd.DataFrame(
        [
            {
                "case_id": "selector",
                "states": 20,
                "open_success_rate": 0.5,
                "feedback_success_rate": 0.6,
                "rescues": 5,
                "harms": 3,
            },
            {
                "case_id": "efficacy_only",
                "states": 20,
                "open_success_rate": 0.1,
                "feedback_success_rate": 0.3,
                "rescues": 4,
                "harms": 0,
            },
            {
                "case_id": "floor",
                "states": 20,
                "open_success_rate": 0.0,
                "feedback_success_rate": 0.0,
                "rescues": 0,
                "harms": 0,
            },
        ]
    )
    result = add_boundary_flags(rows, _manifest()).set_index("case_id")
    assert bool(result.loc["selector", "effect_support"])
    assert bool(result.loc["efficacy_only", "non_ceiling_opportunity"])
    assert not bool(result.loc["floor", "eligible_for_new_seed_holdout"])


def test_integrity_scopes_snapshot_ids_by_case() -> None:
    manifest = {
        "rollouts_per_init": 1,
        "rollout_seed_step": 97,
        "target_pairs": 2,
        "snapshot_query_idx": 4,
        "experiment_split": "screen",
        "num_candidates": 4,
        "replay_integrity_threshold": 1e-9,
        "minimum_strict_replay_pairs": 2,
        "cells": [
            {
                "case_id": "cell_a",
                "suite": "shared_suite",
                "init_state_ids": [0],
                "base_seed": 1000,
            },
            {
                "case_id": "cell_b",
                "suite": "shared_suite",
                "init_state_ids": [0],
                "base_seed": 2000,
            },
        ],
    }
    frame = pd.DataFrame(
        [
            {
                "case_id": case_id,
                "suite": "shared_suite",
                "init_state_id": 0,
                "rollout_id": 0,
                "rollout_seed": seed,
                "snapshot_id": "shared_suite__task0__init0__rollout0__query4",
                "query_idx": 4,
                "experiment_split": "screen",
                "open_terminal_success": False,
                "feedback_terminal_success": True,
                "feedback_feedback_requery_performed": True,
                "main_open_replay_state_max_abs": 0.0,
            }
            for case_id, seed in (("cell_a", 1000), ("cell_b", 2000))
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "case_id": case_id,
                "snapshot_id": "shared_suite__task0__init0__rollout0__query4",
                "candidate_idx": candidate_idx,
                "candidate_is_max_value": candidate_idx == 2,
            }
            for case_id in ("cell_a", "cell_b")
            for candidate_idx in range(4)
        ]
    )

    integrity = validate_integrity(frame, candidates, manifest)

    assert integrity["duplicate_decision_keys"] == 0
    assert integrity["candidate_pool_size_valid"]
    assert integrity["one_max_value_candidate_per_pool"]
    assert integrity["valid"]

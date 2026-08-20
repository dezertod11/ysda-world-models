import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_adaptive_planning_campaign import (
    case_stratum as analysis_stratum,
    failure_mode_paired_table,
    surrogate_transfer_diagnostics,
)
from build_adaptive_video_replay_config import case_stratum as replay_stratum
from build_surrogate_requery_notebook import episode_diagnostic_table
from build_surrogate_requery_confirmatory_config import build_config


def test_surrogate_confirmatory_strata_keep_repeated_cases_separate_from_new_ood():
    expected = {
        "spatial_mug_task0_init0_surrogate_confirm": "known_boundary",
        "long_milk_task9_init0_surrogate_screen": "known_boundary",
        "new_ood_spatial_swap_task8_init0_surrogate_confirm": "new_ood_holdout",
        # Preserve the earlier adaptive-campaign convention.
        "spatial_mug_task0_init0_adaptive_confirm": "new_ood_holdout",
        "milk_task5_init0_adaptive_confirm": "known_boundary",
    }

    for case_id, stratum in expected.items():
        assert analysis_stratum(case_id) == stratum
        assert replay_stratum(case_id) == stratum


def test_episode_diagnostic_table_counts_failures_and_interaction_flags():
    episodes = pd.DataFrame(
        {
            "strategy_id": ["max_value", "max_value", "action_l1"],
            "success": [True, False, False],
            "failure_type": [None, "timeout", "timeout"],
            "target_drop_candidate": [False, True, False],
            "wrong_object_interaction_candidate": [False, False, True],
            "num_queries_observed": [8, 14, 16],
        }
    )

    table = episode_diagnostic_table(episodes, {"max_value", "action_l1"})

    assert "1/2" in table
    assert "timeout: 1" in table
    assert "Target-drop flags" in table
    assert "Wrong-object flags" in table


def test_confirmatory_config_assigns_one_worker_slot_per_job():
    config = build_config(
        {"defaults": {}},
        {
            "non_surrogate_adaptive": "requery_l1_h8",
            "surrogate_adaptive": "phase_surrogate_l1_r0.5_e0.0884176756291_h8",
        },
        max_rollouts=20,
    )
    jobs = config["profiles"]["surrogate_confirmatory"]["jobs"]

    assert len(jobs) == 24
    assert [job["gpu_slot"] for job in jobs] == list(range(24))


def test_surrogate_transfer_diagnostics_separate_boundary_and_new_ood():
    rows = []
    for case_id in (
        "milk_task5_init0_surrogate_confirm",
        "new_ood_spatial_swap_task8_init0_surrogate_confirm",
    ):
        for value in (0.01, 0.02, 0.04, 0.08):
            rows.append(
                {
                    "case_id": case_id,
                    "strategy_id": "max_value",
                    "planning_predicted_proprio_error": value,
                    "prediction_error_future_proprio_l2": value,
                    "planning_surrogate_alarm": value >= 0.04,
                }
            )

    diagnostics = surrogate_transfer_diagnostics(pd.DataFrame(rows)).set_index(
        "case_stratum"
    )

    assert set(diagnostics.index) == {"all", "known_boundary", "new_ood_holdout"}
    assert diagnostics.loc["all", "case_relative_top_quartile_auc"] == 1.0
    assert diagnostics.loc["all", "case_controlled_rank_correlation"] == pytest.approx(1.0)


def test_failure_mode_table_uses_paired_event_changes():
    rows = []
    for strategy_id, drops, timeouts in (
        ("max_value", [True, False], [False, True]),
        ("phase_surrogate_l1_r0.5_e0.1_h8", [False, True], [True, True]),
    ):
        for seed, (drop, timeout) in enumerate(zip(drops, timeouts)):
            rows.append(
                {
                    "case_id": "case",
                    "suite": "suite",
                    "task_id": 0,
                    "init_state_id": 0,
                    "rollout_seed": seed,
                    "strategy_id": strategy_id,
                    "target_drop_candidate": drop,
                    "wrong_object_interaction_candidate": False,
                    "failure_type": "timeout_no_goal" if timeout else "success",
                }
            )

    result = failure_mode_paired_table(pd.DataFrame(rows))
    drop = result.loc[result["event"].eq("target_drop_candidate")].iloc[0]
    timeout = result.loc[result["event"].eq("timeout_no_goal")].iloc[0]

    assert drop["event_reduced"] == 1
    assert drop["event_increased"] == 1
    assert drop["mcnemar_exact_p"] == 1.0
    assert timeout["event_increased"] == 1

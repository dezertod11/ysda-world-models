import math
from pathlib import Path

import pytest
import numpy as np
import pandas as pd

from scripts.analyze_counterfactual_feedback import (
    budget_table,
    candidate_ranking,
    grouped_ridge_predictions,
)
from scripts.counterfactual_feedback_utils import (
    deterministic_unit_interval,
    local_branch_utility,
    should_run_terminal_continuation,
    terminal_branch_utility,
    value_of_feedback,
)
from scripts.run_libero_experiment_campaign import build_job, expand_jobs, load_campaign


ROOT = Path(__file__).resolve().parents[1]


def test_deterministic_fraction_is_stable_and_bounded():
    first = deterministic_unit_interval("suite", 1, 2, 3)
    second = deterministic_unit_interval("suite", 1, 2, 3)

    assert first == second
    assert 0.0 <= first < 1.0
    assert first != deterministic_unit_interval("suite", 1, 2, 4)


def test_terminal_continuation_fraction_validates_bounds():
    assert not should_run_terminal_continuation(0.0, "state")
    assert should_run_terminal_continuation(1.0, "state")
    with pytest.raises(ValueError):
        should_run_terminal_continuation(1.01, "state")


def test_local_utility_keeps_success_and_safety_separate():
    safe_success = local_branch_utility(
        {
            "local_success": True,
            "observed_goal_progress_delta": 1.0,
            "observed_target_goal_satisfied_fraction_end": 1.0,
        }
    )
    unsafe_success = local_branch_utility(
        {
            "local_success": True,
            "observed_goal_progress_delta": 1.0,
            "observed_target_goal_satisfied_fraction_end": 1.0,
            "observed_official_safety_violation": 1.0,
        }
    )

    assert safe_success == 3.25
    assert unsafe_success == 2.25


def test_value_of_feedback_is_matched_utility_difference_minus_cost():
    open_metrics = {"local_success": False}
    feedback_metrics = {
        "local_success": True,
        "observed_goal_progress_delta": 0.5,
    }

    assert math.isclose(
        value_of_feedback(open_metrics, feedback_metrics, query_cost=0.2),
        local_branch_utility(feedback_metrics) - local_branch_utility(open_metrics) - 0.2,
    )


def test_terminal_utility_uses_terminal_labels():
    safe = terminal_branch_utility(
        {"terminal_success": True, "terminal_goal_progress_max": 1.0}
    )
    dropped = terminal_branch_utility(
        {
            "terminal_success": True,
            "terminal_goal_progress_max": 1.0,
            "terminal_target_drop_candidate": True,
        }
    )

    assert safe == 3.0
    assert dropped == 2.0


def test_counterfactual_campaign_has_300_states_across_12_jobs(tmp_path):
    campaign = load_campaign(
        ROOT / "experiments/configs/libero_campaign_counterfactual_feedback_pilot.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["counterfactual_feedback_pilot_p1_p2"],
        campaign["defaults"],
    )

    assert len(jobs) == 12
    assert sum(int(job["target_decision_states"]) for job in jobs) == 300
    position = next(job for job in jobs if job["name"] == "position_snapshots_x0p1")
    commands, environment, _marker = build_job(position, "pilot", tmp_path)
    assert commands[-1][-1].endswith("run_libero_pro_counterfactual_feedback_collect.sh")
    assert environment["LIBERO_PRO_VOF_TARGET_DECISION_STATES"] == "10"
    assert environment["LIBERO_PRO_POSITION_LEVEL"] == "x0.1"


def test_grouped_ridge_and_budget_tables_use_out_of_fold_scores():
    frame = pd.DataFrame(
        {
            "snapshot_id": [f"s{index}" for index in range(40)],
            "suite": ["suite"] * 40,
            "task_id": np.arange(40) % 10,
            "init_state_id": np.arange(40) // 10,
            "value_range": np.linspace(0.0, 1.0, 40),
            "local_vof": np.linspace(-0.5, 0.5, 40),
        }
    )

    prediction, features = grouped_ridge_predictions(
        frame, "local_vof", features=("value_range",)
    )
    budgets = budget_table(frame, "local_vof", prediction)

    assert features == ["value_range"]
    assert np.isfinite(prediction).sum() == len(frame)
    assert set(budgets["budget"]) == {0.1, 0.2, 0.3}
    assert {"grouped_oof_ridge", "random", "oracle", "value_range"}.issubset(
        set(budgets["method"])
    )


def test_candidate_ranking_reports_cosmos_value_regret():
    candidates = pd.DataFrame(
        {
            "snapshot_id": ["a", "a", "b", "b"],
            "factor": ["Object"] * 4,
            "phase_at_snapshot": ["grasp"] * 4,
            "candidate_idx": [0, 1, 0, 1],
            "candidate_value": [0.9, 0.1, 0.2, 0.8],
            "local_utility_v1": [1.0, 0.0, 1.0, 0.0],
            "latent_action_first_step_copy_l2_std": [0.1, 0.2, 0.1, 0.2],
        }
    )

    summary = candidate_ranking(candidates, "local_utility_v1")
    cosmos = summary.loc[summary["method"].eq("cosmos_value")].iloc[0]

    assert cosmos["snapshots"] == 2
    assert cosmos["mean_regret"] == 0.5
    assert cosmos["top1_accuracy"] == 0.5

import math
from pathlib import Path

import pytest
import numpy as np
import pandas as pd

from scripts.analyze_counterfactual_feedback import (
    budget_table,
    candidate_ranking,
    grouped_candidate_ridge_predictions,
    grouped_ridge_predictions,
    horizon_comparison,
    load_campaign as load_counterfactual_results,
)
from scripts.counterfactual_feedback_utils import (
    dense_branch_utility_v2,
    deterministic_unit_interval,
    local_branch_utility,
    snapshot_is_scheduled,
    should_continue_candidate_to_terminal,
    should_run_terminal_continuation,
    terminal_branch_utility,
    value_of_feedback,
)
from scripts.dense_consequence_utils import (
    GoalGeometry,
    geometry_delta_metrics,
    observation_from_libero_proprio,
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


def test_selected_feedback_only_keeps_exactly_the_commit_candidate():
    decisions = [
        should_continue_candidate_to_terminal(True, True, index, 2)
        for index in range(4)
    ]

    assert decisions == [False, False, True, False]
    assert should_continue_candidate_to_terminal(True, False, 0, 2)
    assert not should_continue_candidate_to_terminal(False, False, 2, 2)


def test_fixed_query_sampling_is_independent_of_phase_counts():
    assert snapshot_is_scheduled(
        "fixed_queries",
        query_idx=3,
        phase="approach",
        phases_seen_in_episode={"approach"},
        phase_count=100,
        phase_cap=1,
        fixed_query_indices={0, 3, 6, 9},
    )
    assert not snapshot_is_scheduled(
        "fixed_queries",
        query_idx=4,
        phase="grasp",
        phases_seen_in_episode=set(),
        phase_count=0,
        phase_cap=10,
        fixed_query_indices={0, 3, 6, 9},
    )


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


def test_dense_geometry_is_directional_and_preserves_components():
    start = GoalGeometry(
        goal_pairs=(("in", "target", "goal"),),
        target_positions={"target": np.array([0.0, 0.0, 0.0])},
        anchor_positions={"goal": np.array([1.0, 0.0, 0.0])},
        eef_position=np.array([0.0, 1.0, 0.0]),
    )
    end = GoalGeometry(
        goal_pairs=(("in", "target", "goal"),),
        target_positions={"target": np.array([0.2, 0.0, 0.05])},
        anchor_positions={"goal": np.array([1.0, 0.0, 0.0])},
        eef_position=np.array([0.2, 0.5, 0.0]),
    )

    metrics = geometry_delta_metrics(start, end)

    assert metrics["dense_goal_pair_count"] == 1
    assert metrics["dense_target_goal_distance_improvement_mean"] > 0
    assert metrics["dense_target_eef_distance_improvement_mean"] > 0
    assert math.isclose(metrics["dense_target_lift_end_mean"], 0.05)


def test_dense_utility_uses_phase_components_and_failure_penalties():
    metrics = {
        "dense_target_goal_distance_improvement_mean": 0.125,
        "dense_target_eef_distance_improvement_mean": 0.05,
        "dense_target_lift_end_mean": 0.025,
        "observed_goal_progress_delta": 0.0,
    }

    assert math.isclose(dense_branch_utility_v2(metrics, "approach"), 0.5)
    assert math.isclose(dense_branch_utility_v2(metrics, "grasp"), 0.5)
    assert math.isclose(
        dense_branch_utility_v2(
            {**metrics, "observed_target_drop_candidate": True}, "grasp"
        ),
        -0.5,
    )


def test_dense_relabel_extracts_eef_position_from_libero_proprio():
    observation = observation_from_libero_proprio(
        np.array([0.01, 0.02, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0])
    )

    assert np.array_equal(observation["robot0_eef_pos"], np.array([1.0, 2.0, 3.0]))


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


def test_h32_campaign_has_matched_horizon_and_six_candidates(tmp_path):
    campaign = load_campaign(
        ROOT
        / "experiments/configs/libero_campaign_counterfactual_feedback_h32_pilot.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["counterfactual_feedback_h32_pilot"],
        campaign["defaults"],
    )

    assert len(jobs) == 4
    assert sum(int(job["target_decision_states"]) for job in jobs) == 48
    commands, environment, _marker = build_job(jobs[0], "h32", tmp_path)
    assert commands[-1][-1].endswith("run_libero_pro_counterfactual_feedback_collect.sh")
    assert environment["LIBERO_PRO_VOF_CONSEQUENCE_HORIZON_STEPS"] == "32"
    assert environment["LIBERO_PRO_VOF_UNCERTAINTY_SEEDS"] == "0,1,2,3,4,5"


def test_frozen_h16_holdout_is_fixed_and_has_240_states(tmp_path):
    campaign = load_campaign(
        ROOT
        / "experiments/configs/libero_campaign_frozen_h16_ranker_holdout.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["frozen_h16_ranker_holdout"],
        campaign["defaults"],
    )

    assert len(jobs) == 4
    assert sum(int(job["target_decision_states"]) for job in jobs) == 240
    assert all(job["experiment_split"] == "holdout" for job in jobs)
    assert all(job["consequence_horizon_steps"] == 16 for job in jobs)
    _commands, environment, _marker = build_job(jobs[0], "holdout", tmp_path)
    assert environment["LIBERO_PRO_VOF_SAMPLING_MODE"] == "fixed_queries"
    assert environment["LIBERO_PRO_VOF_SNAPSHOT_QUERY_INDICES"] == "0,3,6,9"


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


def test_grouped_candidate_ranker_is_out_of_fold_and_uses_candidate_features():
    rows = []
    for snapshot in range(40):
        for candidate_idx in (0, 1):
            rows.append(
                {
                    "snapshot_id": f"s{snapshot}",
                    "suite": "suite",
                    "task_id": snapshot % 10,
                    "init_state_id": snapshot // 10,
                    "factor": "Object",
                    "phase_at_snapshot": "grasp",
                    "candidate_idx": candidate_idx,
                    "candidate_value": float(1 - candidate_idx),
                    "latent_action_copy_std_mean": float(candidate_idx),
                    "dense_utility_v2": float(candidate_idx),
                }
            )
    candidates = pd.DataFrame(rows)

    scores, features = grouped_candidate_ridge_predictions(
        candidates, "dense_utility_v2"
    )
    summary = candidate_ranking(
        candidates,
        "dense_utility_v2",
        extra_scores={"grouped_oof_candidate_ridge": scores},
    )
    cosmos = summary.loc[summary["method"].eq("cosmos_value")].iloc[0]
    learned = summary.loc[
        summary["method"].eq("grouped_oof_candidate_ridge")
    ].iloc[0]

    assert set(features) == {"candidate_value", "latent_action_copy_std_mean"}
    assert np.isfinite(scores).all()
    assert learned["mean_regret"] < cosmos["mean_regret"]


def test_horizon_comparison_reports_sign_changes_and_candidate_ties():
    feedback = pd.DataFrame(
        {
            "factor": ["Object", "Object"],
            "dense_vof_v2": [0.1, -0.2],
            "h32_dense_vof_v2": [0.2, 0.3],
        }
    )
    candidates = pd.DataFrame(
        {
            "snapshot_id": ["a", "a", "b", "b"],
            "factor": ["Object"] * 4,
            "dense_utility_v2": [0.0, 1.0, 0.0, 1.0],
            "h32_dense_utility_v2": [0.5, 0.5, 0.0, 1.0],
        }
    )

    vof, support = horizon_comparison(feedback, candidates)
    pooled_vof = vof.loc[vof["factor"].eq("All")].iloc[0]
    pooled_support = support.loc[support["factor"].eq("All")].iloc[0]

    assert pooled_vof["states"] == 2
    assert pooled_vof["sign_agreement"] == 0.5
    assert pooled_support["h16_non_tied"] == 2
    assert pooled_support["h32_non_tied"] == 1
    assert pooled_support["h16_utility_range_mean"] == pytest.approx(1.0)
    assert pooled_support["h32_utility_range_mean"] == pytest.approx(0.5)


def test_pooled_analysis_keeps_same_snapshot_id_from_different_runs_distinct(tmp_path):
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    feedback = pd.DataFrame(
        {
            "snapshot_id": ["shared"],
            "suite": ["libero_object_temp"],
            "task_id": [0],
            "init_state_id": [0],
        }
    )
    candidates = pd.DataFrame(
        {
            "snapshot_id": ["shared", "shared"],
            "suite": ["libero_object_temp"] * 2,
            "task_id": [0, 0],
            "init_state_id": [0, 0],
            "phase_at_snapshot": ["approach"] * 2,
            "candidate_idx": [0, 1],
            "candidate_value": [0.9, 0.1],
            "local_utility_v1": [1.0, 0.0],
        }
    )
    for run_name in ("position_x0p1", "position_x0p2"):
        feedback.to_csv(run_dir / f"{run_name}__feedback_pairs.csv", index=False)
        candidates.to_csv(run_dir / f"{run_name}__candidate_outcomes.csv", index=False)

    pooled_feedback, pooled_candidates = load_counterfactual_results(tmp_path)
    summary = candidate_ranking(pooled_candidates, "local_utility_v1")
    cosmos = summary.loc[summary["method"].eq("cosmos_value")].iloc[0]

    assert pooled_feedback["analysis_snapshot_id"].nunique() == 2
    assert pooled_candidates["analysis_snapshot_id"].nunique() == 2
    assert cosmos["snapshots"] == 2

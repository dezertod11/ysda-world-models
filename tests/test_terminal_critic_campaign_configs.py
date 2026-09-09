from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "experiments" / "configs"


def _jobs(filename: str, profile: str) -> list[dict[str, object]]:
    payload = json.loads((CONFIG_DIR / filename).read_text(encoding="utf-8"))
    return payload["profiles"][profile]["jobs"]


def test_holdout_is_split_by_init_without_changing_original_seeds() -> None:
    jobs = _jobs(
        "libero_campaign_terminal_critic_holdout.json", "terminal_critic_holdout"
    )

    assert len(jobs) == 10
    observed = set()
    for job in jobs:
        task = int(job["task_ids"])
        init_state = int(job["init_state_ids"])
        observed.add((task, init_state))
        base = 4_500_000 if task == 8 else 4_600_000
        assert int(job["base_seed"]) == base + init_state * 97
        assert int(job["target_decision_states"]) == 2
    assert observed == {(task, init_state) for task in (8, 9) for init_state in range(5)}


def test_closed_loop_is_split_by_init_without_changing_original_seeds() -> None:
    jobs = _jobs(
        "libero_campaign_terminal_critic_closed_loop.json",
        "terminal_critic_closed_loop",
    )

    assert len(jobs) == 10
    observed = set()
    for job in jobs:
        task = int(job["task_ids"])
        init_state = int(job["init_state_ids"])
        observed.add((task, init_state))
        base = 4_700_000 if task == 8 else 4_800_000
        assert int(job["base_seed"]) == base + (init_state - 5) * 10_000
        assert int(job["max_rollouts"]) == 12
        assert job["strategy_lambdas"] == "max_value:0 terminal_grounded_critic:0"
    assert observed == {
        (task, init_state) for task in (8, 9) for init_state in range(5, 10)
    }


def test_k16_opportunity_screen_is_frozen_to_hard_cells() -> None:
    payload = json.loads(
        (CONFIG_DIR / "libero_campaign_proposal_opportunity_k16.json").read_text(
            encoding="utf-8"
        )
    )
    jobs = payload["profiles"]["proposal_opportunity_k16"]["jobs"]
    defaults = payload["defaults"]

    assert len(defaults["uncertainty_seeds"].split(",")) == 16
    assert defaults["sampling_mode"] == "fixed_queries"
    assert defaults["snapshot_query_indices"] == "0,3"
    assert defaults["terminal_continuation_fraction"] == 1.0
    assert defaults["skip_feedback_branch"] is True
    assert len(jobs) == 10
    assert {(job["kind"], job["task_ids"]) for job in jobs} == {
        ("pro_counterfactual_feedback", "0"),
        ("pro_environment_counterfactual_feedback", "0"),
        ("pro_environment_counterfactual_feedback", "2"),
        ("pro_position_counterfactual_feedback", "0"),
    }
    assert {job["init_state_ids"] for job in jobs} == {"5-7", "8-9"}
    assert sum(int(job["target_decision_states"]) for job in jobs) == 50
    assert {int(job["gpu_slot"]) for job in jobs} == set(range(8))

    expected_seeds = {
        "object_task0_init5_7_k16": 5_100_000,
        "object_task0_init8_9_k16": 5_100_291,
        "environment_task0_init5_7_k16": 5_200_000,
        "environment_task0_init8_9_k16": 5_200_291,
        "environment_task2_init5_7_k16": 5_200_485,
        "environment_task2_init8_9_k16": 5_200_776,
        "position_x0p3_task0_init5_7_k16": 5_300_000,
        "position_x0p3_task0_init8_9_k16": 5_300_291,
        "position_y0p3_task0_init5_7_k16": 5_310_000,
        "position_y0p3_task0_init8_9_k16": 5_310_291,
    }
    assert {job["name"]: int(job["base_seed"]) for job in jobs} == expected_seeds


def test_autoregressive_value_screen_keeps_actions_and_continuation_controlled() -> None:
    payload = json.loads(
        (CONFIG_DIR / "libero_campaign_autoregressive_value_ranking.json").read_text(
            encoding="utf-8"
        )
    )
    jobs = payload["profiles"]["autoregressive_value_ranking"]["jobs"]
    defaults = payload["defaults"]

    assert len(jobs) == 10
    assert defaults["uncertainty_seeds"] == "0,1,2,3,4,5,6,7"
    assert defaults["prediction_mode"] == "dual"
    assert defaults["continuation_prediction_mode"] == "parallel"
    assert defaults["sampling_mode"] == "fixed_queries"
    assert defaults["snapshot_query_indices"] == "0"
    assert defaults["continuation_num_candidates"] == 2
    assert defaults["terminal_continuation_fraction"] == 1.0
    assert all(int(job["target_decision_states"]) == 1 for job in jobs)
    assert {int(job["init_state_ids"]) for job in jobs} == set(range(5, 10))
    assert {int(job["base_seed"]) for job in jobs} == {
        5_100_000 + offset * 97 for offset in range(5)
    } | {5_310_000 + offset * 97 for offset in range(5)}


def test_hard_cell_pairwise_ranker_has_disjoint_frozen_init_splits() -> None:
    payload = json.loads(
        (CONFIG_DIR / "libero_campaign_hard_cell_pairwise_ranker.json").read_text(
            encoding="utf-8"
        )
    )
    development_calibration = payload["profiles"][
        "hard_cell_pairwise_development_calibration"
    ]["jobs"]
    holdout = payload["profiles"]["hard_cell_pairwise_holdout"]["jobs"]
    defaults = payload["defaults"]

    assert len(development_calibration) == 8
    assert len(holdout) == 20
    assert defaults["prediction_mode"] == "dual"
    assert defaults["continuation_prediction_mode"] == "parallel"
    assert defaults["uncertainty_seeds"] == "0,1,2,3,4,5,6,7"
    assert defaults["snapshot_query_indices"] == "0"
    assert defaults["terminal_continuation_fraction"] == 1.0
    assert defaults["continuation_num_candidates"] == 2

    observed_ranges = {
        (job["experiment_split"], job["init_state_ids"])
        for job in development_calibration
    }
    assert observed_ranges == {
        ("development", "10-14"),
        ("development", "15-19"),
        ("development", "20-24"),
        ("calibration", "25-29"),
    }
    assert {
        (job["kind"], int(job["init_state_ids"])) for job in holdout
    } == {
        (kind, init_state)
        for kind in ("pro_counterfactual_feedback", "pro_position_counterfactual_feedback")
        for init_state in range(30, 40)
    }
    for job in holdout:
        init_state = int(job["init_state_ids"])
        base = 6_100_000 if job["kind"] == "pro_counterfactual_feedback" else 6_300_000
        assert int(job["base_seed"]) == base + (init_state - 10) * 97
        assert int(job["target_decision_states"]) == 1
    assert sum(
        int(job["target_decision_states"]) for job in development_calibration
    ) == 40
    assert sum(int(job["target_decision_states"]) for job in holdout) == 20

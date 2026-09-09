from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_terminal_critic_closed_loop import analyze


def _row(
    *,
    strategy: str,
    task_id: int,
    pair_id: int,
    success: bool,
    switched: bool,
) -> dict[str, object]:
    values = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    first_actions = [[float(candidate), *([0.0] * 6)] for candidate in range(8)]
    selected = 1 if switched else 0
    return {
        "pair_id": pair_id,
        "rollout_id": 0,
        "query_idx": 0,
        "factor": "Object",
        "case_id": "terminal_critic_object_closed_loop",
        "suite": "libero_object_object",
        "task_id": task_id,
        "task_description": f"task {task_id}",
        "init_state_id": 5 + pair_id,
        "rollout_seed": 1000 * task_id + pair_id,
        "planning_strategy": strategy,
        "success": success,
        "final_t": 100 if success else 280,
        "max_value_selected": not switched,
        "max_value": values[0],
        "selected_value": values[selected],
        "planning_terminal_critic_payload_sha256": "frozen-hash",
        "planning_terminal_critic_switched": switched,
        "planning_terminal_critic_proposed_idx": selected,
        "planning_terminal_critic_advantage_lcb": 0.2 if switched else 0.0,
        "planning_terminal_critic_risk_ucb_proposed": 0.1,
        "planning_terminal_critic_risk_ucb_baseline": 0.2,
        "planning_terminal_critic_fallback_reason": (
            "accepted" if switched else "critic_agrees_with_max_value"
        ),
        "candidate_values_json": json.dumps(values),
        "candidate_first_actions_json": json.dumps(first_actions),
        "selected_sample_idx": selected,
        "max_value_sample_idx": 0,
        "num_samples": 8,
        "failure_type": "success" if success else "timeout_no_goal",
        "target_drop_candidate": False,
        "wrong_object_interaction_candidate": False,
        "official_safety_violation": False,
        "prediction_error_future_image_mse": 0.1,
        "prediction_error_future_wrist_mse": 0.2,
        "prediction_error_future_proprio_l2": 0.3,
        "prediction_error_value_abs_chunk_success": 0.4,
        "prediction_error_value_abs_final_success": 0.5,
    }


def test_closed_loop_analysis_builds_paired_gate_and_artifacts(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    runs = campaign / "runs"
    runs.mkdir(parents=True)
    baseline_rows = []
    method_rows = []
    for task_id in (8, 9):
        for pair_id in range(2):
            baseline_success = not (task_id == 8 and pair_id == 0)
            baseline_rows.append(
                _row(
                    strategy="max_value",
                    task_id=task_id,
                    pair_id=pair_id,
                    success=baseline_success,
                    switched=False,
                )
            )
            method_rows.append(
                _row(
                    strategy="terminal_grounded_critic",
                    task_id=task_id,
                    pair_id=pair_id,
                    success=True,
                    switched=not baseline_success,
                )
            )
    pd.DataFrame(baseline_rows).to_parquet(
        runs / "baseline__query_traces.parquet", index=False
    )
    pd.DataFrame(method_rows).to_parquet(
        runs / "critic__query_traces.parquet", index=False
    )

    output = tmp_path / "analysis"
    result = analyze(
        campaign,
        output,
        draws=200,
        seed=17,
        expected_pairs_per_task=2,
        expected_model_sha="frozen-hash",
        expected_candidates=8,
    )

    assert result["paired_rollouts"] == 4
    assert result["gate"]["passed"] is True
    assert result["gate"]["critic_rescues"] == 1
    assert result["gate"]["critic_harms"] == 0
    assert (output / "RESULTS.md").is_file()
    assert (output / "paired_terminal_success.png").is_file()
    assert (output / "critic_switch_rate_by_query.png").is_file()

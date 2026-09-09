from __future__ import annotations

import pandas as pd

from scripts.analyze_proposal_value_ranking import state_diagnostics


def test_state_diagnostics_detects_greedy_harm_from_larger_pool() -> None:
    rows = []
    for candidate_idx in range(16):
        rows.append(
            {
                "analysis_snapshot_id": "state",
                "factor": "Position",
                "case_id": "position_y0p3",
                "suite": "libero_object_temp",
                "task_id": 0,
                "task_description": "pick the object",
                "init_state_id": 7,
                "query_idx": 0,
                "phase_at_snapshot": "approach",
                "candidate_idx": candidate_idx,
                "candidate_seed": candidate_idx,
                "candidate_value": (
                    0.60 if candidate_idx == 4 else 0.50 - 0.01 * candidate_idx
                ),
                "terminal_success_bool": candidate_idx == 0,
                "terminal_failure_type": (
                    "success" if candidate_idx == 0 else "timeout_no_goal"
                ),
            }
        )

    state = state_diagnostics(pd.DataFrame(rows)).iloc[0]

    assert bool(state["outcome_heterogeneous"])
    assert bool(state["k4_selected_success"])
    assert not bool(state["k8_selected_success"])
    assert bool(state["k4_to_k8_greedy_harm"])
    assert state["top_candidate_idx"] == 4
    assert state["best_success_candidate_idx"] == 0
    assert abs(state["top_over_best_success_margin"] - 0.10) < 1e-12

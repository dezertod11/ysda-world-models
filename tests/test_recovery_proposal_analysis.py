import pandas as pd

from scripts.analyze_recovery_proposal_opportunity import (
    binary_auc,
    proposal_gate,
    stratified_binary_auc,
)


def _passing_summary():
    return {
        "n_states": 80,
        "strict_replay_rate": 1.0,
        "success_rate": 0.15,
        "success_ci_low": 0.03,
        "rescued_cells": 5,
        "rescued_tasks": 4,
        "safety_rate_delta": 0.0,
        "drop_rate_delta": 0.025,
    }


def test_proposal_gate_reports_specific_failure():
    summary = _passing_summary()
    passed, failed = proposal_gate(summary)
    assert passed
    assert failed == []
    summary["drop_rate_delta"] = 0.10
    passed, failed = proposal_gate(summary)
    assert not passed
    assert failed == ["drop_delta_at_most_5pp"]


def test_binary_auc_handles_ties_and_direction():
    assert binary_auc([False, False, True, True], [0.0, 1.0, 2.0, 3.0]) == 1.0
    assert binary_auc([False, True], [1.0, 1.0]) == 0.5


def test_stratified_auc_uses_only_within_stratum_pairs():
    auc, strata, pairs = stratified_binary_auc(
        [False, True, False, True],
        [100.0, 101.0, 0.0, 1.0],
        ["a", "a", "b", "b"],
    )
    assert auc == 1.0
    assert strata == 2
    assert pairs == 2

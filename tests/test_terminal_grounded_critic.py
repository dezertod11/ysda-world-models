from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.terminal_grounded_critic import (
    TERMINAL_CRITIC_FEATURES,
    _plot_coefficients,
    _select_frame,
    coefficient_summary,
    coverage_diagnostics,
    fit_model,
    opportunity_gate,
    opportunity_table,
    read_candidates,
    validate_candidate_sets,
)


def candidate_frame(
    *,
    task_offset: int,
    groups: int,
    candidates: int = 3,
    source_run: str,
) -> pd.DataFrame:
    rows = []
    for group_index in range(groups):
        snapshot = f"{source_run}::snapshot{group_index}"
        for candidate_idx in range(candidates):
            succeeds = candidate_idx == 1 and group_index % 2 == 0
            row = {
                "analysis_snapshot_id": snapshot,
                "source_run": source_run,
                "snapshot_id": f"snapshot{group_index}",
                "suite": "libero_object_object",
                "factor": "Object",
                "task_id": task_offset + group_index,
                "init_state_id": 0,
                "candidate_idx": candidate_idx,
                "candidate_value": 1.0 - 0.1 * candidate_idx,
                "terminal_available": True,
                "terminal_success": succeeds,
                "terminal_success_bool": succeeds,
                "terminal_utility_v1": 3.0 if succeeds else 0.0,
                "terminal_adverse_event": float(candidate_idx == 2),
                "baseline_candidate_idx": 0,
                "baseline_terminal_utility": 0.0,
                "baseline_terminal_success": False,
                "baseline_terminal_risk": 0.0,
                "terminal_advantage": 3.0 if succeeds else 0.0,
                "independent_group": f"Object|libero_object_object|{task_offset + group_index}|0",
                "query_idx": 0,
                "phase_at_snapshot": "approach",
            }
            row.update({feature: 0.0 for feature in TERMINAL_CRITIC_FEATURES})
            row["candidate_value"] = 1.0 - 0.1 * candidate_idx
            row["candidate_action_first_d0"] = float(candidate_idx)
            rows.append(row)
    return pd.DataFrame(rows)


def test_opportunity_gate_uses_candidate_level_terminal_counterfactuals() -> None:
    frame = candidate_frame(task_offset=0, groups=10, source_run="screen")

    opportunity = opportunity_table(frame)
    gate = opportunity_gate(frame)

    assert len(opportunity) == 10
    assert opportunity["outcome_heterogeneous"].sum() == 5
    assert opportunity["success_rescue"].sum() == 5
    assert gate["passed"] is False
    assert gate["required_heterogeneous_snapshots"] == 8


def test_fit_model_keeps_groups_disjoint_and_builds_bootstrap_heads(
    tmp_path: Path,
) -> None:
    training = candidate_frame(task_offset=0, groups=6, source_run="train")
    calibration = candidate_frame(task_offset=10, groups=3, source_run="calibration")

    model = fit_model(training, calibration, members=8, seed=17)
    scored, states = _select_frame(calibration, model)

    assert model["expected_candidates"] == 3
    assert model["ensemble_members"] == 8
    assert set(model["training_groups"]).isdisjoint(model["calibration_groups"])
    assert len(scored) == len(calibration)
    assert len(states) == calibration["analysis_snapshot_id"].nunique()
    assert np.isfinite(states["advantage_lcb"]).all()

    coefficients = coefficient_summary(model)
    assert len(coefficients) == len(TERMINAL_CRITIC_FEATURES)
    assert coefficients["advantage_abs_rank"].min() == 1
    assert coefficients["risk_abs_rank"].max() == len(TERMINAL_CRITIC_FEATURES)
    coefficient_plot = tmp_path / "coefficients.png"
    _plot_coefficients(coefficients, coefficient_plot)
    assert coefficient_plot.is_file()

    coverage_states, coverage_summary = coverage_diagnostics(calibration, model)
    assert len(coverage_states) == calibration["analysis_snapshot_id"].nunique()
    assert set(coverage_summary["factor"]) == {"Object", "All"}
    assert coverage_summary["advantage_candidate_coverage"].between(0.0, 1.0).all()
    assert coverage_summary["risk_candidate_coverage"].between(0.0, 1.0).all()


def test_fit_model_rejects_group_leakage() -> None:
    training = candidate_frame(task_offset=0, groups=6, source_run="train")
    calibration = training.copy()

    with pytest.raises(ValueError, match="overlap"):
        fit_model(training, calibration, members=4)


def test_validate_candidate_sets_rejects_partial_snapshot() -> None:
    frame = candidate_frame(task_offset=0, groups=2, source_run="partial")
    frame = frame.drop(frame.index[-1])

    with pytest.raises(ValueError, match="disagree"):
        validate_candidate_sets(frame)


def test_read_candidates_allows_label_only_opportunity_audit(tmp_path: Path) -> None:
    frame = candidate_frame(task_offset=0, groups=2, source_run="legacy")
    legacy = frame.drop(
        columns=[feature for feature in TERMINAL_CRITIC_FEATURES if feature != "candidate_value"]
    ).drop(
        columns=[
            "analysis_snapshot_id",
            "source_run",
            "factor",
            "terminal_success_bool",
            "terminal_adverse_event",
            "baseline_candidate_idx",
            "baseline_terminal_utility",
            "baseline_terminal_success",
            "baseline_terminal_risk",
            "terminal_advantage",
            "independent_group",
        ]
    )
    path = tmp_path / "legacy__candidate_outcomes.parquet"
    legacy.to_parquet(path, index=False)

    with pytest.raises(ValueError, match="predate terminal-critic causal features"):
        read_candidates([path])

    audited = read_candidates([path], require_features=False)
    assert audited["analysis_snapshot_id"].nunique() == 2
    assert opportunity_table(audited)["success_rescue"].sum() == 1

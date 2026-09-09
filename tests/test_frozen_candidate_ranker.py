from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_counterfactual_feedback import CANDIDATE_RANK_FEATURES
from scripts.frozen_candidate_ranker import (
    candidate_selection_outcomes,
    fit_frozen_model,
    group_overlap,
    grouped_bootstrap_regret_delta,
    holdout_gate,
    predict_frozen_model,
    prepare_candidates,
)


def candidate_frame(*, task_offset: int, groups_per_factor: int = 20) -> pd.DataFrame:
    rows = []
    for factor_index, factor in enumerate(("Object", "Environment", "Position")):
        suite = {
            "Object": "libero_object_object",
            "Environment": "libero_object_env",
            "Position": "libero_object_temp",
        }[factor]
        for group_index in range(groups_per_factor):
            task_id = task_offset + factor_index * 100 + group_index
            for candidate_idx in range(3):
                signal = float(candidate_idx)
                row = {
                    "snapshot_id": f"{factor}-{task_id}",
                    "analysis_snapshot_id": f"{factor}-{task_id}",
                    "suite": suite,
                    "task_id": task_id,
                    "init_state_id": 0,
                    "candidate_idx": candidate_idx,
                    "factor": factor,
                    "phase_at_snapshot": "approach",
                    "candidate_value": -signal,
                    "dense_utility_v2": signal,
                }
                for feature_index, feature in enumerate(CANDIDATE_RANK_FEATURES):
                    row[feature] = signal * (feature_index + 1)
                row["candidate_value"] = -signal
                rows.append(row)
    return pd.DataFrame(rows)


def test_frozen_ranker_fits_once_and_generalizes_to_disjoint_groups():
    train = candidate_frame(task_offset=0)
    holdout = candidate_frame(task_offset=1000)
    model = fit_frozen_model(train)

    assert set(model["factors"]) == {"Object", "Environment", "Position"}
    assert not group_overlap(holdout, model)
    scores = predict_frozen_model(holdout, model)
    outcomes = candidate_selection_outcomes(
        holdout, scores, target="dense_utility_v2"
    )
    learned = outcomes.loc[outcomes["method"].eq("frozen_factor_ridge")]
    cosmos = outcomes.loc[outcomes["method"].eq("cosmos_value")]

    assert learned["regret"].eq(0.0).all()
    assert cosmos["regret"].gt(0.0).all()


def test_group_overlap_rejects_reused_task_init_identity():
    train = candidate_frame(task_offset=0, groups_per_factor=5)
    model = fit_frozen_model(train)

    assert group_overlap(train, model)


def test_grouped_bootstrap_gate_requires_all_factors_and_negative_macro_ci():
    train = candidate_frame(task_offset=0)
    holdout = prepare_candidates(candidate_frame(task_offset=1000))
    model = fit_frozen_model(train)
    scores = predict_frozen_model(holdout, model)
    outcomes = candidate_selection_outcomes(
        holdout, scores, target="dense_utility_v2"
    )
    _draws, intervals = grouped_bootstrap_regret_delta(
        outcomes, draws=500, seed=123
    )
    gate = holdout_gate(
        intervals,
        overlap=[],
        expected_factors=("Environment", "Object", "Position"),
        required_groups=20,
    )

    assert gate["passed"]
    assert gate["macro_ci95_upper_below_zero"]


def test_frozen_model_requires_the_preregistered_feature_set():
    frame = candidate_frame(task_offset=0).drop(columns=[CANDIDATE_RANK_FEATURES[-1]])

    with pytest.raises(ValueError, match="feature set"):
        fit_frozen_model(frame)

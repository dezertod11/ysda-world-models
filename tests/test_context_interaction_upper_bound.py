from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_context_interaction_upper_bound import (
    CORE_DYNAMIC_FEATURES,
    OBJECT_SLOPE_FEATURES,
    append_context_interactions,
    evaluate_score,
    ridge_path_predict,
    upper_bound_feature_families,
    within_cell_grouped_folds,
)


def synthetic_frame() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(7)
    for task_id in (1, 2):
        for level, direction, magnitude in (("x0.2", 1.0, 0.2), ("y0.1", 0.0, 0.1)):
            cell = f"{level}|task{task_id}"
            for group_id in range(5):
                for repeat in range(2):
                    record = {
                        "row_uid": f"{cell}|{group_id}|{repeat}",
                        "task_id": task_id,
                        "position_level": level,
                        "phase_at_snapshot": ("approach", "grasp", "transport")[
                            group_id % 3
                        ],
                        "cell_key": cell,
                        "independent_group": f"{cell}|init{group_id}",
                        "f_context_direction_x": direction,
                        "f_context_magnitude": magnitude,
                        "commit_success": float((group_id + repeat) % 2),
                        "feedback_success": float((group_id + repeat + task_id) % 2),
                        "direct_success": float(task_id - 1.5),
                        "direct_terminal_utility": float(task_id - 1.5) / 2,
                        "direct_grounded": float(task_id - 1.5) / 3,
                        "terminal_effect": 1 if group_id == 0 else (-1 if group_id == 1 else 0),
                    }
                    for feature in CORE_DYNAMIC_FEATURES:
                        record[feature] = float(rng.normal())
                    for feature in OBJECT_SLOPE_FEATURES:
                        record[feature] = float(rng.normal())
                    rows.append(record)
    return pd.DataFrame(rows)


def test_context_interactions_match_declared_products() -> None:
    frame, groups = append_context_interactions(synthetic_frame())
    expected = frame["f_oracle_task_1"] * frame["f_oracle_magnitude"]
    name = "f_oracle_cross_oracle_task_1__oracle_magnitude"
    np.testing.assert_allclose(frame[name], expected)
    assert name in groups["pairwise"]
    assert not any("success" in name or "terminal" in name for name in groups["pairwise"])


def test_upper_bound_families_add_context_and_object_slopes() -> None:
    frame, context = append_context_interactions(synthetic_frame())
    families = upper_bound_feature_families(frame, context)
    assert set(families) == {
        "relative_control",
        "oracle_context_only",
        "relative_oracle_additive",
        "relative_oracle_interactions",
        "relative_oracle_dynamic_slopes",
        "relative_object_oracle_dynamic_slopes",
    }
    assert len(families["relative_oracle_dynamic_slopes"]) > len(
        families["relative_oracle_interactions"]
    )
    assert len(families["relative_object_oracle_dynamic_slopes"]) > len(
        families["relative_oracle_dynamic_slopes"]
    )


def test_within_cell_folds_keep_groups_intact_and_balance_cells() -> None:
    frame = synthetic_frame()
    folds = within_cell_grouped_folds(frame)
    assigned = frame.assign(fold=folds)
    assert assigned.groupby("independent_group")["fold"].nunique().max() == 1
    counts = assigned.groupby(["cell_key", "fold"]).size()
    assert counts.nunique() == 1
    assert counts.iloc[0] == 2


def test_ridge_path_recovers_multitarget_linear_relation() -> None:
    rng = np.random.default_rng(3)
    train = rng.normal(size=(80, 5))
    test = rng.normal(size=(20, 5))
    weights = rng.normal(size=(5, 2))
    offset = np.array([0.7, -1.2])
    target = offset + train @ weights
    prediction = ridge_path_predict(train, target, test, alphas=(1e-9,))[1e-9]
    np.testing.assert_allclose(prediction, offset + test @ weights, atol=1e-7)


def test_evaluate_score_selects_highest_ranked_rescues() -> None:
    frame = pd.DataFrame(
        {
            "terminal_effect": [-1, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            "cell_key": ["a"] * 5 + ["b"] * 5,
        }
    )
    metrics, query, quintiles = evaluate_score(
        frame, np.arange(len(frame), dtype=float), budget=0.2
    )
    assert query.tolist() == [False] * 8 + [True, True]
    assert metrics["rescues"] == 2
    assert metrics["harms"] == 0
    assert np.isclose(metrics["raw_gain"], 0.2)
    assert np.isclose(metrics["adjusted_gain"], 0.195)
    assert len(quintiles) == 5

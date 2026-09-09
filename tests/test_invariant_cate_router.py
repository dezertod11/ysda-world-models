from pathlib import Path

import numpy as np
import pandas as pd

from scripts.invariant_cate_router import (
    apply_support_mode,
    derive_invariant_sidecar_features,
    feature_families,
    fit_potential_ensemble,
    fit_robust_scaler,
    fit_support_reference,
    predict_frozen_cate,
    predict_potential_ensemble,
    transform_values,
    validate_feature_names,
)


def test_sidecar_features_are_relative_and_leakage_safe(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.npz"
    actions = np.zeros((4, 16, 7), dtype=np.float32)
    actions[2, :, 0] = 0.1
    actions[2, :8, 6] = 1.0
    actions[2, 8:, 6] = -1.0
    current = np.asarray([0.02, -0.02, 0.1, 0.2, 0.3, 1, 0, 0, 0], dtype=np.float32)
    future = np.tile(current, (4, 1))
    future[2, 2:5] += np.asarray([0.1, 0.0, 0.0])
    np.savez(
        path,
        selected_max_value_idx=np.asarray(2),
        candidate_actions=actions,
        candidate_values=np.asarray([0.1, 0.2, 0.5, 0.3]),
        candidate_predicted_future_proprio=future,
        current_proprio=current,
        feedback_endpoint_proprio=np.full(9, 999.0),
    )
    features = derive_invariant_sidecar_features(path)
    validate_feature_names(features)
    assert np.isclose(features["f_future_position_delta_norm"], 0.1)
    assert features["f_action_gripper_transition_count"] == 1.0
    assert not any("endpoint" in feature for feature in features)


def test_bounded_potential_heads_return_probabilities() -> None:
    values = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
    commit = np.asarray([0, 0, 1, 1])
    feedback = np.asarray([0, 1, 1, 1])
    groups = np.asarray(["a", "b", "c", "d"])
    scaler = fit_robust_scaler(values)
    transformed = transform_values(values, scaler)
    models = fit_potential_ensemble(
        transformed,
        commit,
        feedback,
        groups,
        alpha=0.01,
        estimators=4,
        seed=7,
    )
    p_commit, p_feedback, cate, cate_std = predict_potential_ensemble(
        models, transformed
    )
    assert np.all((0 <= p_commit) & (p_commit <= 1))
    assert np.all((0 <= p_feedback) & (p_feedback <= 1))
    assert np.all((-1 <= cate) & (cate <= 1))
    assert np.all(cate_std >= 0)


def test_feature_families_keep_privileged_phase_separate() -> None:
    frame = pd.DataFrame(
        {
            "f_core_value": [1.0],
            "f_action_path": [2.0],
            "f_context_magnitude": [0.2],
            "f_priv_phase_grasp": [1.0],
        }
    )
    families = feature_families(frame)
    assert "f_priv_phase_grasp" not in families["relative_context"]
    assert "f_priv_phase_grasp" in families["privileged_phase_diagnostic"]


def test_support_modes_are_conservative() -> None:
    distances = np.asarray([0.2, 1.2, 0.3])
    levels = ["x0.2", "y0.3", "y0.1"]
    mask = apply_support_mode(
        "known_level_knn_q99",
        levels=levels,
        known_levels=["x0.2", "y0.1"],
        distances=distances,
        distance_threshold=1.0,
    )
    assert mask.tolist() == [True, False, True]


def test_frozen_prediction_applies_cost_and_support() -> None:
    frame = pd.DataFrame(
        {
            "position_level": ["x0.2", "y0.3"],
            "f_core_value": [-1.0, 1.0],
        }
    )
    values = frame[["f_core_value"]].to_numpy(float)
    scaler = fit_robust_scaler(values)
    transformed = transform_values(values, scaler)
    models = fit_potential_ensemble(
        transformed,
        np.asarray([0, 1]),
        np.asarray([1, 1]),
        ["a", "b"],
        alpha=0.1,
        estimators=1,
        seed=1,
    )
    support_values = transform_values(values, scaler, clipped=False)
    support = fit_support_reference(support_values, ["a", "b"])
    support["known_levels"] = ["x0.2"]
    payload = {
        "features": ["f_core_value"],
        "scaler": scaler.to_payload(),
        "models": models,
        "support": support,
        "router": {
            "beta": 0.0,
            "query_cost": -1.0,
            "support_mode": "known_level",
        },
    }
    prediction = predict_frozen_cate(payload, frame)
    assert prediction["router_query"].tolist() == [True, False]

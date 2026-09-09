from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_signed_vof_router import (
    DEFAULT_QUERY_COST,
    MODEL_SPECS,
    ModelSpec,
    _policy_statistics,
    derive_sidecar_features,
    grouped_oof_predictions,
    validate_feature_manifest,
)
from scripts.freeze_signed_vof_router import (
    _absolute_threshold,
    predict_frozen_payload,
    select_with_frozen_threshold,
)


def _write_sidecar(path: Path, endpoint_value: float) -> None:
    old = np.zeros((4, 16, 7), dtype=np.float32)
    new = np.zeros((4, 16, 7), dtype=np.float32)
    old[2, 8:16, 0] = 1.0
    new[1, :8, 0] = 0.25
    np.savez_compressed(
        path,
        current_proprio=np.arange(9, dtype=np.float32),
        selected_max_value_idx=np.asarray(2),
        feedback_requery_selected_idx=np.asarray(1),
        candidate_actions=old,
        feedback_requery_actions=new,
        candidate_values=np.asarray([0.0, 0.1, 0.4, 0.2], dtype=np.float32),
        feedback_requery_values=np.asarray([0.1, 0.6, 0.3, 0.2], dtype=np.float32),
        feedback_endpoint_proprio=np.full(9, endpoint_value, dtype=np.float32),
        feedback_endpoint_state=np.full(20, endpoint_value, dtype=np.float64),
    )


def test_sidecar_features_ignore_realized_endpoint_arrays(tmp_path: Path) -> None:
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    _write_sidecar(first, 1.0)
    _write_sidecar(second, 1_000_000.0)
    left = derive_sidecar_features(first)
    right = derive_sidecar_features(second)
    assert left == right
    assert left["post_tail_l2_mean"] == pytest.approx(0.75)
    assert left["post_new_minus_old_value"] == pytest.approx(0.2)


def test_feature_manifest_rejects_outcome_leakage() -> None:
    validate_feature_manifest()
    with pytest.raises(ValueError, match="Outcome leakage"):
        validate_feature_manifest(
            [ModelSpec("bad", "pre", ("feedback_terminal_success",), 1.0)]
        )
    assert all(
        not feature.startswith("feedback_query_")
        for spec in MODEL_SPECS
        if spec.stage == "pre"
        for feature in spec.features
    )


def test_grouped_oof_predictions_learn_signed_effect_without_nan() -> None:
    rows = []
    for group in range(12):
        for repeat in range(2):
            value = (group - 5.5) / 5.5 + 0.01 * repeat
            rows.append(
                {
                    "independent_group": f"g{group}",
                    "x": value,
                    "terminal_effect": float(np.sign(value)),
                }
            )
    frame = pd.DataFrame(rows)
    spec = ModelSpec("synthetic", "pre", ("x",), 1.0)
    mean, std = grouped_oof_predictions(frame, spec)
    assert np.isfinite(mean).all()
    assert np.isfinite(std).all()
    assert np.corrcoef(mean, frame["terminal_effect"])[0, 1] > 0.8


def test_policy_statistics_charge_query_only_when_available() -> None:
    frame = pd.DataFrame(
        {
            "terminal_effect": [1, -1, 0, 1],
            "open_success": [False, True, False, False],
        }
    )
    selected = np.asarray([True, False, False, True])
    pre = _policy_statistics(
        frame, selected, stage="pre", query_cost=DEFAULT_QUERY_COST
    )
    post = _policy_statistics(
        frame, selected, stage="post", query_cost=DEFAULT_QUERY_COST
    )
    assert pre["raw_success_delta"] == pytest.approx(0.5)
    assert pre["adjusted_success_delta"] == pytest.approx(0.5 - 0.5 * DEFAULT_QUERY_COST)
    assert post["adjusted_success_delta"] == pytest.approx(0.5 - DEFAULT_QUERY_COST)
    assert pre["method_success_rate"] == pytest.approx(0.75)


def test_frozen_payload_prediction_and_absolute_threshold() -> None:
    frame = pd.DataFrame({"a": [1.0, 2.0, np.nan], "b": [3.0, 5.0, 7.0]})
    payload = {
        "active_features": ["a", "b"],
        "preprocessing": {
            "impute_median": [2.0, 5.0],
            "mean": [2.0, 5.0],
            "scale": [1.0, 2.0],
        },
        "ridge": {
            "coefficients": [0.5, 1.0, -0.25],
            "covariance": np.eye(3).tolist(),
            "residual_scale": 0.2,
        },
        "router": {
            "beta": 0.0,
            "absolute_score_threshold": 0.4,
            "threshold_operator": ">",
        },
    }
    mean, std, score = predict_frozen_payload(payload, frame)
    assert mean.tolist() == pytest.approx([-0.25, 0.5, 0.25])
    assert np.isfinite(std).all()
    assert score.tolist() == pytest.approx(mean.tolist())
    assert select_with_frozen_threshold(payload, score).tolist() == [False, True, False]

    threshold, operator, count = _absolute_threshold(
        np.asarray([0.1, 0.2, 0.3, 0.4]), 0.5
    )
    assert threshold == pytest.approx(0.25)
    assert operator == ">"
    assert count == 2

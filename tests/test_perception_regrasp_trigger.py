import numpy as np

import pytest

from scripts.perception_regrasp_trigger import evaluate_trigger, resolve_intervention_strategy


ARTIFACT = {
    "schema_version": 1,
    "global_conservative_score_range": 40.0,
    "minimum_miss_distance_m": 0.08,
    "maximum_reach_distance_m": 0.50,
    "objects": {
        "butter": {
            "score_range_lower": 15.0,
            "workspace_lower_xyz": [-0.20, -0.30, -0.05],
            "workspace_upper_xyz": [0.10, 0.10, 0.30],
        }
    },
}


def localization(score=30.0, x=0.0, y=0.0, z=0.02):
    return {
        "perception_object": "butter",
        "perception_world_x": x,
        "perception_world_y": y,
        "perception_world_z": z,
        "perception_score_range": score,
    }


def test_workspace_trigger_accepts_calibrated_visible_miss():
    decision = evaluate_trigger(
        localization(), np.array([0.0, -0.10, 0.10]), ARTIFACT, mode="workspace_calibrated"
    )
    assert decision.passed
    assert decision.estimated_target_eef_distance_m > 0.08


def test_workspace_trigger_rejects_close_target_and_out_of_workspace():
    close = evaluate_trigger(
        localization(), np.array([0.0, 0.0, 0.02]), ARTIFACT, mode="workspace_calibrated"
    )
    outside = evaluate_trigger(
        localization(x=-0.40), np.array([0.0, 0.0, 0.10]), ARTIFACT, mode="workspace_calibrated"
    )
    assert not close.passed and not close.miss_distance_pass
    assert not outside.passed and not outside.workspace_pass


def test_global_trigger_is_stricter_and_post_retreat_can_skip_miss_test():
    strict = evaluate_trigger(
        localization(score=30.0),
        np.array([0.0, -0.10, 0.10]),
        ARTIFACT,
        mode="global_conservative",
    )
    post_retreat = evaluate_trigger(
        localization(score=45.0),
        np.array([0.0, 0.0, 0.02]),
        ARTIFACT,
        mode="global_conservative",
        require_miss=False,
    )
    assert not strict.passed and not strict.confidence_pass
    assert post_retreat.passed


def test_intervention_strategy_resolves_trigger_and_primitive():
    assert resolve_intervention_strategy("workspace_calibrated") == (
        "workspace_calibrated",
        "perception_regrasp",
    )
    assert resolve_intervention_strategy("workspace_retreat_only") == (
        "workspace_calibrated",
        "retreat_only",
    )
    with pytest.raises(ValueError):
        resolve_intervention_strategy("unknown")

from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_semantic_vof import (
    PRIVILEGED_TOKENS,
    SCALAR_FEATURES,
    SEMANTIC_FEATURES,
    grouped_oof,
    mean_pairwise_cosine_distance,
    semantic_record,
    uplift_at_budget,
)


def test_pairwise_cosine_distance() -> None:
    values = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    assert np.isclose(mean_pairwise_cosine_distance(values), 1.0)


def test_semantic_record_uses_selected_candidate() -> None:
    current = np.asarray([1.0, 0.0])
    futures = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    text = np.asarray([0.0, 1.0])
    record = semantic_record(current, futures, current, futures, text, selected=1)
    assert np.isclose(record["clip_agent_selected_goal_delta"], 1.0)
    assert np.isclose(record["clip_agent_selected_motion"], 1.0)
    assert np.isclose(record["clip_agent_selected_goal_rank"], 1.0)


def test_grouped_oof_is_finite_and_uplift_selects_high_scores() -> None:
    frame = pd.DataFrame(
        {
            "group": ["a", "a", "b", "b", "c", "c"],
            "feature": [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0],
            "dense_vof_v2": [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0],
        }
    )
    prediction = grouped_oof(frame, ["feature"], "group")
    assert np.isfinite(prediction).all()
    target = frame["dense_vof_v2"].to_numpy()
    result = uplift_at_budget(target, target, 1 / 3)
    assert result["mean_selected_vof"] > 0


def test_primary_features_are_deployable() -> None:
    forbidden = [
        feature
        for feature in SCALAR_FEATURES + SEMANTIC_FEATURES
        if any(token in feature.lower() for token in PRIVILEGED_TOKENS)
    ]
    assert forbidden == []

from __future__ import annotations

import numpy as np

from scripts.object_contact_vof import (
    attention_statistics,
    image_relation_statistics,
    object_relation_record,
    parse_target_object,
)


def test_parse_target_object() -> None:
    assert (
        parse_target_object("pick the chocolate pudding and place it in the basket")
        == "chocolate pudding"
    )


def test_attention_statistics_tracks_peak_location() -> None:
    similarity = np.zeros(49)
    similarity[-1] = 2.0
    stats = attention_statistics(similarity, temperature=0.05)
    assert stats["center_x"] > 0.9
    assert stats["center_y"] > 0.9
    assert 0.0 <= stats["attention_entropy"] <= 1.0


def test_image_relation_statistics_detects_separated_concepts() -> None:
    patches = np.zeros((49, 2))
    patches[:, 0] = 1.0
    patches[-1] = [0.0, 1.0]
    stats = image_relation_statistics(
        patches,
        np.asarray([1.0, 0.0]),
        np.asarray([0.0, 1.0]),
        np.asarray([1.0, 0.0]),
        temperature=0.01,
    )
    assert stats["relation_distance"] > 1.0
    assert stats["target_global_similarity"] == 0.0
    assert stats["goal_global_similarity"] == 1.0


def test_object_relation_record_uses_selected_candidate() -> None:
    current = np.tile(np.asarray([[1.0, 0.0]]), (49, 1))
    future = np.stack([current.copy(), current.copy()])
    future[1, -1] = [0.0, 1.0]
    current_global = np.asarray([1.0, 0.0])
    future_global = np.asarray([[1.0, 0.0], [0.0, 1.0]])
    record = object_relation_record(
        agent_current_patches=current,
        agent_future_patches=future,
        agent_current_global=current_global,
        agent_future_global=future_global,
        wrist_current_patches=current,
        wrist_future_patches=future,
        wrist_current_global=current_global,
        wrist_future_global=future_global,
        target_text=np.asarray([0.0, 1.0]),
        goal_text=np.asarray([1.0, 0.0]),
        selected=1,
    )
    assert np.isclose(
        record["f_obj_agent_selected_delta_target_global_similarity"], 1.0
    )
    assert record["f_obj_agent_selected_rank_target_global_similarity"] == 1.0
    assert all(key.startswith("f_obj_") for key in record)

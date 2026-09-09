import numpy as np
import pandas as pd
import pytest

from scripts.recovery_proposal_utils import (
    cartesian_servo_action,
    continuation_seeds,
    group_balanced_selection,
    parse_proposals,
)


def test_group_balanced_selection_prefers_distinct_groups_and_is_deterministic():
    frame = pd.DataFrame(
        {
            "row_uid": [f"row-{index}" for index in range(8)],
            "independent_group": ["a", "a", "a", "b", "b", "c", "d", "d"],
        }
    )
    first = group_balanced_selection(frame, count=4, seed=17)
    second = group_balanced_selection(frame.sample(frac=1, random_state=3), count=4, seed=17)
    assert first["row_uid"].tolist() == second["row_uid"].tolist()
    assert first["independent_group"].nunique() == 4


def test_group_balanced_selection_rejects_short_or_duplicate_input():
    frame = pd.DataFrame({"row_uid": ["a"], "independent_group": ["g"]})
    with pytest.raises(ValueError, match="only 1"):
        group_balanced_selection(frame, count=2, seed=1)
    duplicate = pd.concat([frame, frame], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        group_balanced_selection(duplicate, count=1, seed=1)


def test_cartesian_servo_action_clips_motion_and_sets_gripper():
    action = cartesian_servo_action([0.0, 0.0, 0.0], [0.10, -0.025, 0.01], gripper=-2)
    np.testing.assert_allclose(action, [1.0, -0.5, 0.2, 0.0, 0.0, 0.0, -1.0])


def test_proposal_parsing_and_continuation_seeds_are_stable_and_branch_specific():
    proposals = parse_proposals("frequent_requery_h4,lift_hold_h8")
    assert [proposal.execution_horizon for proposal in proposals] == [4, 8]
    first = continuation_seeds(100, proposals[0].name, 64, [0, 1, 2, 3])
    assert first == continuation_seeds(100, proposals[0].name, 64, [0, 1, 2, 3])
    assert first != continuation_seeds(100, proposals[1].name, 64, [0, 1, 2, 3])


def test_perception_regrasp_is_a_deployable_h8_proposal():
    proposal = parse_proposals("perception_regrasp_h8")[0]
    assert proposal.deployable
    assert proposal.execution_horizon == 8
    assert proposal.primitive == "perception_regrasp"

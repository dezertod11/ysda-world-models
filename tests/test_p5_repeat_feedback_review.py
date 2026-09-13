import numpy as np
import pytest

from scripts.review_p5_repeat_feedback import repeat_selection


def test_held_out_label_does_not_select_candidate():
    outcomes = np.array([[0, 1, 1], [1, 0, 0]])
    before = repeat_selection(outcomes, [.8, .9])[0]
    changed = outcomes.copy()
    changed[:, 0] = [1, 0]
    after = repeat_selection(changed, [.8, .9])[0]
    assert before['chosen'] == after['chosen'] == 0
    assert before['selected_success'] == 0 and after['selected_success'] == 1


def test_ties_use_frozen_value_then_index():
    outcomes = np.ones((3, 3), dtype=int)
    assert all(row['chosen'] == 1 for row in repeat_selection(outcomes, [.3, .8, .8]))


def test_in_sample_best_can_fail_on_every_held_out_suffix():
    outcomes = np.eye(3, dtype=int)
    rows = repeat_selection(outcomes, [.9, .8, .7])
    assert outcomes.mean(1).max() == pytest.approx(1/3)
    assert sum(row['selected_success'] for row in rows) == 0
    assert sum(row['baseline_success'] for row in rows) == 1


def test_consistently_better_candidate_survives_split():
    rows = repeat_selection([[0, 0, 0], [1, 1, 1]], [.9, .2])
    assert all(row['chosen'] == 1 and row['selected_success'] == 1 for row in rows)


def test_invalid_outcomes_are_rejected():
    with pytest.raises(ValueError):
        repeat_selection([[0, 2]], [.2])
    with pytest.raises(ValueError):
        repeat_selection([[0]], [.2])
    with pytest.raises(ValueError):
        repeat_selection([[0, .5]], [.2])

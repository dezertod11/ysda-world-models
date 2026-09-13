import numpy as np
import pytest

from scripts.audit_p5_fresh_feedback import boundary_metrics


def test_gripper_float_noise_is_not_a_reopen():
    old = np.zeros((16, 7))
    old[:, 6] = 1.001
    fresh = old.copy()
    fresh[8:, 6] = 0.997
    result = boundary_metrics(fresh, old)
    assert not result["boundary_gripper_reopens"]
    assert result["gripper_sign_mismatch_fraction"] == 0


def test_boundary_uses_new_head_at_index_eight_and_controller_clip():
    old = np.zeros((16, 7))
    old[:, 6] = 1
    fresh = old.copy()
    fresh[8, 0] = 2
    fresh[8, 6] = -1
    result = boundary_metrics(fresh, old)
    assert result["boundary_xyz_l2"] == 1
    assert result["replacement_xyz_l2_mean"] == pytest.approx(1 / 8)
    assert result["boundary_gripper_reopens"]
    assert result["gripper_sign_mismatch_fraction"] == pytest.approx(1 / 8)


def test_incomplete_window_is_not_silently_analyzed():
    with pytest.raises(ValueError, match="first 16"):
        boundary_metrics(np.zeros((12, 7)), np.zeros((16, 7)))

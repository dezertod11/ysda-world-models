from dataclasses import dataclass
import numpy as np
import pytest

from scripts.recovery_grounding_diagnostic import replace_waypoint, projection_metrics, select_cases


@dataclass(frozen=True)
class Loc:
    world_position: np.ndarray
    score_range: float = 19.


def test_waypoint_interventions_preserve_confidence_and_input():
    old = Loc(np.array([1., 2., 3.]))
    target = np.array([4., 5., 6.])
    assert replace_waypoint(old, target, 'rgb_replay') is old
    xy = replace_waypoint(old, target, 'oracle_xy_fixed_gate')
    np.testing.assert_array_equal(xy.world_position, [4, 5, 3])
    assert xy.score_range == old.score_range
    np.testing.assert_array_equal(old.world_position, [1, 2, 3])
    np.testing.assert_array_equal(replace_waypoint(old, target, 'oracle_xyz_fixed_gate').world_position, target)
    with pytest.raises(ValueError):
        replace_waypoint(old, [np.nan, 1, 2], 'oracle_xyz_fixed_gate')


def test_geometry_separates_pixel_error_and_transform_error():
    k = np.array([[100., 0., 112.], [0., 100., 112.], [0., 0., 1.]])
    camera = np.diag([1., -1., -1., 1.])
    camera[2, 3] = 1.
    loc = dict(perception_pixel_row=112., perception_pixel_col=122.,
               perception_world_x=.1, perception_world_y=0., perception_world_z=0.)
    metric = projection_metrics(loc, np.zeros(3), k, camera)
    assert metric['pixel_center_error'] == pytest.approx(10)
    assert metric['xy_error_m'] == pytest.approx(.1)
    assert metric['world_reconstruction_error_m'] < 1e-12
    assert metric['gt_projection_roundtrip_error_m'] < 1e-12


def test_manifest_rejects_outcome_selected_subset():
    with pytest.raises(ValueError):
        select_cases(dict(jobs=[]))


def test_manifest_covers_both_cohorts_with_equal_counts():
    import pandas as pd
    from scripts.recovery_confirmation import make_jobs
    calibration = pd.DataFrame(columns=['position_level', 'task_id', 'init_state_id'])
    cases = select_cases(dict(jobs=make_jobs(calibration)))
    assert len(cases) == 32
    assert sum(j['cohort'] == 'transfer' for j in cases) == 16
    assert {j['init_state_id'] for j in cases} == {25, 26}
    assert all('terminal_success' not in j for j in cases)

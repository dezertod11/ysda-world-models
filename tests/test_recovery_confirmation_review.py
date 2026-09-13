import numpy as np
import pandas as pd
import pytest

from scripts.p5_candidate_replication import atomic_npz
from scripts.p5_repeat_feedback import digest
from scripts.review_recovery_confirmation_results import paired_counts, prefix_pose_audit


def test_counts_are_paired_and_do_not_call_stops_failures():
    data = pd.DataFrame([
        dict(job_id='a', arm='control', terminal_success=False),
        dict(job_id='a', arm='method', terminal_success=True),
        dict(job_id='b', arm='control', terminal_success=True),
        dict(job_id='b', arm='method', terminal_success=False),
        dict(job_id='c', arm='control', terminal_success=True),
        dict(job_id='c', arm='method', terminal_success=True),
    ])
    counts = paired_counts(data, 'method', 'control')
    assert counts['n'] == 3 and counts['rescue'] == counts['harm'] == 1
    assert counts['difference_pp'] == 0
    with pytest.raises(ValueError, match='matched'):
        paired_counts(data.iloc[:-1], 'method', 'control')


def test_pose_audit_uses_named_target_and_validates_frozen_prefix(tmp_path):
    path = tmp_path / 'prefix_72.npz'
    atomic_npz(path, obs__target_1_pos=np.array([1., 2., 3.]),
               obs__robot0_eef_pos=np.zeros(3), obs__decoy_1_pos=np.zeros(3))
    row = dict(prefix_sha256=digest(path), terminal_episode_target_objects='target_1',
        intervention=dict(initial_localization=dict(perception_world_x=1.03,
                                                   perception_world_y=2.04, perception_world_z=3.)))
    result = prefix_pose_audit(tmp_path, row)
    assert result['localization_xy_error_m'] == pytest.approx(.05)
    assert result['offline_gt_only'] and result['true_xyz'] == [1., 2., 3.]
    with pytest.raises(ValueError, match='changed'):
        prefix_pose_audit(tmp_path, dict(row, prefix_sha256='bad'))

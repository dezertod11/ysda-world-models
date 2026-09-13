import numpy as np
import pytest

from scripts.review_grounded_probe_results import same_trajectory


@pytest.mark.parametrize('changed', (None, 'executed_actions', 'final_state', 'signals'))
def test_trajectory_parity_checks_actions_state_and_signals(tmp_path, changed):
    folder = tmp_path / 'screen' / 'case'
    folder.mkdir(parents=True)
    reference = dict(executed_actions=np.zeros((3, 7)), final_state=np.zeros(12),
                     signals=np.array([[0., np.nan], [1., np.nan]]))
    other = {k: v.copy() for k, v in reference.items()}
    if changed is not None:
        other[changed].flat[0] = 1
    np.savez(folder / 'left.npz', **reference)
    np.savez(folder / 'right.npz', **other)
    assert same_trajectory(tmp_path, 'screen', 'case', 'left', 'right') == (changed is None)

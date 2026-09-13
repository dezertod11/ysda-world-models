import copy

import numpy as np
import pytest

from scripts.review_night_results_20260912 import decoder_trace_audit


def example():
    actions = np.zeros((3, 16, 7), dtype=np.float32)
    actions[1] = 0.25
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    queries, arrays = [], dict(executed_actions=np.repeat(actions[1, :8], 2, axis=0), frame_t=np.arange(17))
    for q in range(2):
        queries.append(dict(query=q, t=q * 8, t_after=(q + 1) * 8, executed=8,
            index=1, candidate_seeds=[1, 999, 998], prediction_error_horizon_aligned=False,
            prediction_errors={}, common_q0_pool=q == 0, selectors={'decoder_costs': [2, 1, 3]}))
        arrays[f'q{q:03d}_actions'] = actions.copy()
        for camera in ('external', 'wrist'):
            arrays[f'q{q:03d}_input_{camera}'] = image.copy()
            arrays[f'q{q:03d}_actual_{camera}'] = image.copy()
    row = dict(terminal_final_t=16, video_frames=17, selector_uses_simulator_labels=False,
        generated_horizon=16, executed_horizon=8, prediction_mode='parallel',
        arm='decoder_full_h8', seed_group=0, candidate_calls_logical=6, queries=queries)
    return row, arrays


def test_trace_checks_actions_feedback_and_horizon():
    row, arrays = example()
    assert decoder_trace_audit(row, arrays) == 2


@pytest.mark.parametrize('corruption', ['actions', 'image', 'future_error', 'seed', 'choice', 'time', 'frames'])
def test_trace_rejects_contract_violation(corruption):
    row, arrays = copy.deepcopy(example())
    if corruption == 'actions':
        arrays['executed_actions'][0, 0] = 99
    elif corruption == 'image':
        arrays['q001_input_wrist'][0, 0, 0] = 99
    elif corruption == 'future_error':
        row['queries'][0]['prediction_errors'] = {'mse': 1}
    elif corruption == 'seed':
        row['queries'][0]['candidate_seeds'][0] = 9999
    elif corruption == 'choice':
        row['queries'][0]['index'] = 0
    elif corruption == 'time':
        row['queries'][1]['t'] = 7
    else:
        row['video_frames'] = 16
    with pytest.raises((ValueError, AssertionError)):
        decoder_trace_audit(row, arrays)

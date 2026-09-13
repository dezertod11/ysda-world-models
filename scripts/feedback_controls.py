"""Preregistered matched-budget feedback controls; no simulator imports."""
from pathlib import Path

import numpy as np

NAME = 'feedback_controls_20260910'
ARMS = ('open16', 'stale_k4', 'fresh_k1', 'fresh_k4', 'fresh_continuity_k4')
CONTRASTS = (('fresh_k4', 'open16'), ('fresh_k4', 'fresh_k1'),
             ('fresh_continuity_k4', 'fresh_k4'))
CONTINUITY_LAMBDA = 0.10


def continuity_cost(actions, old_actions):
    actions, old_actions = np.asarray(actions), np.asarray(old_actions)
    if actions.shape != (4, 16, 7) or old_actions.shape != (16, 7):
        raise ValueError('Expected K4/H16x7 and H16x7')
    if not np.isfinite(actions).all() or not np.isfinite(old_actions).all():
        raise ValueError('Non-finite actions')
    new, old = np.clip(actions[:, :8], -1, 1), np.clip(old_actions[8:], -1, 1)
    xyz = np.linalg.norm(new[..., :3] - old[None, :, :3], axis=-1).mean(axis=1) / (2*np.sqrt(3))
    rot = np.linalg.norm(new[..., 3:6] - old[None, :, 3:6], axis=-1).mean(axis=1) / (2*np.sqrt(3))
    grip = (np.sign(new[..., 6]) != np.sign(old[None, :, 6])).mean(axis=1)
    return .5*xyz + .25*rot + .25*grip


def choose_tail(arm, old, fresh, fresh_values, stale, stale_values):
    fresh_values, stale_values = np.asarray(fresh_values), np.asarray(stale_values)
    if fresh_values.shape != (4,) or stale_values.shape != (4,):
        raise ValueError('Expected four values')
    if not np.isfinite(fresh_values).all() or not np.isfinite(stale_values).all():
        raise ValueError('Non-finite values')
    cost = continuity_cost(fresh, old)
    if arm == 'open16':
        return np.asarray(old)[8:16], -1, cost
    if arm == 'stale_k4':
        index = int(np.argmax(stale_values))
        return np.asarray(stale)[index, 8:16], index, cost
    if arm == 'fresh_k1':
        index = 0
    elif arm == 'fresh_k4':
        index = int(np.argmax(fresh_values))
    elif arm == 'fresh_continuity_k4':
        index = int(np.argmax(fresh_values - CONTINUITY_LAMBDA*cost))
    else:
        raise ValueError(arm)
    return np.asarray(fresh)[index, :8], index, cost


def make_jobs(source):
    specs = [('object_q4', 'p5_object_object', 0, 64),
             ('position_x_q3', 'p5_position_x0.2', 2, 48),
             ('position_y_q3', 'p5_position_y0.2', 9, 48)]
    jobs = []
    for cell, (label, case, task, t) in enumerate(specs):
        pool = next(p for p in source['pools'] if p['case_id'] == case and p['task_id'] == task)
        for phase, inits, repeats in [('smoke', (12,), (0,)), ('screen', (13,14,15,16), (0,1))]:
            for init in inits:
                for repeat in repeats:
                    base = 1_600_000_000 + cell*10_000_000 + init*100_000 + repeat*10_000
                    jobs.append(dict(id=f'{label}_i{init}_r{repeat}', cell=label, phase=phase,
                        suite=pool['suite'], environment=pool['environment'], task_id=task,
                        init_state_id=init, repeat=repeat, t=t, description=pool['task_description'],
                        prefix_seed=base, query_seed=base+2000, suffix_seed=base+5000))
    return jobs


def check_predecessor(state, lock_is_free):
    if not lock_is_free:
        return 'waiting_predecessor'
    if state.get('active'):
        return 'waiting_predecessor'
    if state.get('status') in ('completed', 'budget_exhausted'):
        return 'ready'
    if state.get('status') == 'partial' and state.get('finished_at'):
        return 'ready'
    if state.get('status') in ('failed', 'analysis_failed'):
        return 'blocked_predecessor_failure'
    return 'waiting_predecessor'


def job_done(directory, job):
    import json
    marker = Path(directory)/job['phase']/job['id']/'completed.json'
    if not marker.exists():
        return False
    value = json.loads(marker.read_text())
    if value['status'] == 'skipped':
        return True
    for arm in ARMS:
        path = marker.parent/(arm+'.json')
        if not path.exists() or not path.with_suffix('.npz').exists():
            return False
        row = json.loads(path.read_text())
        if row['job_id'] != job['id'] or row['suffix_seed'] != job['suffix_seed']:
            raise ValueError('Mismatched completed branch')
        if not row['terminal_available'] or not row['prefix_integrity']:
            raise ValueError('Invalid completed branch')
        if not (marker.parent/(arm+'.mp4')).is_file():
            return False
    return True

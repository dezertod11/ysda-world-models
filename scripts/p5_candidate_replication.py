"""Frozen design and CPU helpers for conditional candidate replication."""
from pathlib import Path

import numpy as np

NAME = 'p5_candidate_replication_20260910'
REPEATS = 10
NEIGHBOR_INITS = (9, 10, 11, 12)
ANCHORS = (('pool_13', (4, 3, 5)), ('pool_11', (7, 6)))


def make_jobs(source):
    pools = {p['id']: p for p in source['pools']}
    jobs = []
    for name, indices in ANCHORS:
        pool = pools[name]
        assert indices[0] == pool['selected']
        jobs.append(dict(id=f'repeat_{name}', kind='replication', source_pool=name,
            task_id=pool['task_id'], init_state_id=pool['init_state_id'],
            suite=pool['suite'], environment=pool['environment'],
            description=pool['task_description'], candidates=list(indices), baseline=indices[0],
            sidecar=pool['sidecar'], sidecar_sha256=pool['sidecar_sha256'], t=48))
    for task in (0, 2):
        reference = next(p for p in pools.values() if p['task_id'] == task and p['case_id'] == 'p5_position_x0.2')
        for init in NEIGHBOR_INITS:
            jobs.append(dict(id=f'neighbor_t{task}_i{init}', kind='neighbor', task_id=task,
                init_state_id=init, suite=reference['suite'], environment=reference['environment'],
                description=reference['task_description'], candidates=list(range(8)), t=48,
                prefix_seed=700_000_000 + task*1_000_000 + init*10_000))
    for index, job in enumerate(jobs):
        job['seed_base'] = 1_100_000_000 + index*1_000_000
        job['expected_branches'] = REPEATS * len(job['candidates'])
    assert len(jobs) == 10 and sum(j['expected_branches'] for j in jobs) == 690
    return jobs


def branch_schedule(job, smoke=False):
    candidates = job['candidates'] if job['kind'] == 'replication' else ([0] if smoke else job['candidates'])
    rows = []
    for repeat in range(1 if smoke else REPEATS):
        offset = repeat % len(candidates)
        for candidate in candidates[offset:] + candidates[:offset]:
            seed = job['seed_base'] + repeat*10_000 + (100_000_000 if smoke else 0)
            rows.append((repeat, candidate, seed))
    return rows


def atomic_npz(path, **arrays):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        np.savez_compressed(stream, **arrays)
    temporary.replace(path)


def signal_arrays(records):
    """Keep scalar time series tabular and preserve vector-valued fields separately."""
    arrays = {}
    scalars = []
    if not records:
        return dict(signal_keys=np.asarray([], dtype=str), signals=np.empty((0, 0)))
    keys = sorted(records[0])
    for key in keys:
        try:
            values = np.asarray([row[key] for row in records])
        except (ValueError, KeyError) as error:
            raise ValueError(f'Inconsistent signal field: {key}') from error
        if values.dtype.kind == 'O':
            raise ValueError(f'Object-valued signal field: {key}')
        if values.ndim == 1 and values.dtype.kind in 'bifu':
            scalars.append(key)
        else:
            arrays[f'signal_field__{key}'] = values
    arrays['signal_keys'] = np.asarray(scalars)
    arrays['signals'] = np.asarray([[row[key] for key in scalars] for row in records], dtype=float)
    return arrays


def local_frame_metrics(records, boundary=64):
    """Only executed-chunk observations; terminal continuation cannot leak in."""
    segment = [r for r in records if r['t'] <= boundary]
    if not segment:
        return dict(local_frames=0)
    return dict(local_frames=len(segment),
        local_contact_steps=sum(float(r.get('robot_target_contact_count', 0)) > 0 for r in segment),
        local_drop=any(r.get('target_drop_candidate', 0) > 0 for r in segment),
        local_wrong_object=any(r.get('wrong_object_interaction_candidate', 0) > 0 for r in segment),
        local_target_lift_max=max(float(r.get('target_lift_max', 0)) for r in segment),
        local_goal_progress_end=float(segment[-1].get('goal_progress', float('nan'))))

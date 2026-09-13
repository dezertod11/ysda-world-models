"""Frozen replication and timing study; no outcome-driven nightly selection."""
from pathlib import Path
import hashlib
import json

NAME = 'recovery_confirmation_20260913'
ARMS = ('continue_h8', 'physical_regrasp', 'refresh_preserve_only')
TIMES = (56, 72, 88)
TASKS = (1, 2, 4, 5, 6, 7, 8, 9)
REPLICATION = (('x0.2', 5), ('x0.2', 6), ('x0.2', 9), ('y0.2', 4),
               ('y0.2', 6), ('y0.2', 9), ('y0.3', 1), ('y0.3', 5))
TRANSFER = tuple(('x0.3', task) for task in TASKS)
PRIMARY = (('replication', 'physical_regrasp', 'continue_h8'),
           ('transfer', 'physical_regrasp', 'continue_h8'),
           ('all', 'refresh_preserve_only', 'physical_regrasp'),
           ('all', 'physical_regrasp', 'baseline_h16'))


def seed_for(level, task, init):
    key = f'{NAME}|{level}|{task}|{init}'.encode()
    return 300_000_000 + int.from_bytes(hashlib.sha256(key).digest()[:4], 'big') % 900_000_000


def make_jobs(calibration):
    jobs = []
    # Complete balanced blocks first if the wall-clock budget truncates the queue.
    for init in range(25, 33):
        for index, (level, task) in enumerate(REPLICATION + TRANSFER):
            overlap = calibration[(calibration.position_level == level) &
                                  (calibration.task_id == task)]
            if init in set(overlap.init_state_id):
                raise ValueError('Calibration init overlap')
            cohort = 'replication' if index < len(REPLICATION) else 'transfer'
            if cohort == 'transfer' and len(overlap):
                raise ValueError('Transfer cell occurred in localizer calibration')
            case = f'{level}_t{task}_i{init}'
            jobs.append(dict(id=case, case_id=case, phase='main', boundary=72,
                cell=f'{level}_t{task}', position_level=level, task_id=task,
                init_state_id=init, repeat=0, rollout_seed=seed_for(level, task, init),
                cohort=cohort, calibration_cell_seen=bool(len(overlap)),
                suite='libero_object_temp'))
    main = list(jobs)
    for init in range(25, 33):
        for job in main:
            if job['init_state_id'] == init:
                for boundary in (56, 88):
                    jobs.append(dict(job, id=f'{job["id"]}_b{boundary}', phase='timing', boundary=boundary))
    return jobs


def expected_arms(job):
    return ('baseline_h16',) + ARMS if job['phase'] == 'main' else ARMS


def suffix_query(boundary):
    if boundary not in TIMES:
        raise ValueError('Unregistered boundary')
    return boundary // 16 + 1


def job_done(directory, job, *, hashes=False):
    try:
        from scripts.p5_repeat_feedback import digest
    except ModuleNotFoundError:
        from p5_repeat_feedback import digest
    folder = Path(directory) / job['phase'] / job['id']
    marker = folder / 'completed.json'
    if not marker.exists():
        return False
    if json.loads(marker.read_text())['arms'] != list(expected_arms(job)):
        raise ValueError('Changed completed arm set')
    for arm in expected_arms(job):
        path = folder / (arm + '.json')
        row = json.loads(path.read_text())
        if row['job_id'] != job['id'] or row['rollout_seed'] != job['rollout_seed']:
            raise ValueError('Changed completed identity')
        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
            if not path.with_suffix(ext).exists():
                raise ValueError('Missing completed artifact')
            if hashes and digest(path.with_suffix(ext)) != row[key]:
                raise ValueError('Changed completed artifact')
    return True

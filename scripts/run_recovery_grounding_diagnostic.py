#!/usr/bin/env python3
"""Bounded idle-only queue: geometry, replay, oracle waypoints, event shadow parity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

from recovery_grounding_diagnostic import NAME, ARMS, SMOKE_CASES, select_cases
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'experiments/campaigns' / NAME
SOURCE = ROOT / 'experiments/campaigns/recovery_confirmation_20260913'
STAGES = ('geometry', 'smoke', 'oracle', 'shadow')


def prepare():
    old = json.loads((SOURCE / 'config.json').read_text())
    cases = select_cases(old)
    for job in cases:
        folder = SOURCE / 'main' / job['id']
        job['source_hashes'] = {name: digest(folder / name) for name in
            ('prefix_72.npz', 'prefix_72.json', 'physical_regrasp.json', 'physical_regrasp.npz')}
    dependencies = set(old['scripts']) | {
        'recovery_grounding_diagnostic.py', 'collect_recovery_grounding_diagnostic.py',
        'run_recovery_grounding_diagnostic.py', 'analyze_recovery_grounding_diagnostic.py',
        'resume_recovery_confirmation.py', 'event_feedback.py', 'event_feedback_libero.py',
        'collect_event_feedback.py', 'calibrate_event_feedback.py',
        'collect_perception_regrasp_calibration.py', 'cosmos_env_libero_pro.sh', 'cosmos_env.sh'}
    mask = ROOT / 'experiments/campaigns/grounded_probe_20260911_v2/mask_model'
    cfg = dict(name=NAME, source_campaign=str(SOURCE), source_config_sha256=digest(SOURCE / 'config.json'),
        cases=cases, arms=list(ARMS), stages=list(STAGES), max_workers=2, gpu_candidates=list('06371245'),
        deadline_epoch=json.loads((SOURCE / 'budget.json').read_text())['deadline_epoch'],
        scripts={name: digest(ROOT / 'scripts' / name) for name in sorted(dependencies)},
        mask=str(mask), mask_hashes={name: digest(mask / name) for name in ('mask.json', 'mask.pt', 'freeze.json')},
        event_parameters=str(ROOT / 'experiments/event_feedback_20260913/parameters_smoke.json'),
        event_parameters_sha256=digest(ROOT / 'experiments/event_feedback_20260913/parameters_smoke.json'),
        purpose='Post-hoc mechanism diagnostic, not a deployable result or new holdout',
        selection='All sixteen source cells at init25 and init26, no success/gate filtering',
        gate_controls='Fixed RGB eligibility and post-retreat gate; oracle variants add explicit physical waypoint bounds',
        shadow_cases=list(SMOKE_CASES), automatic_fit=False, automatic_holdout=False)
    path = DIRECTORY / 'config.json'
    if path.exists() and json.loads(path.read_text()) != cfg:
        raise ValueError('Changed frozen diagnostic configuration; do not overwrite')
    atomic_json(path, cfg)
    for case in cases:
        if case['id'] in SMOKE_CASES:
            atomic_json(DIRECTORY / 'shadow_cases' / (case['id'] + '.json'),
                [{k: case[k] for k in ('suite', 'task_id', 'init_state_id', 'rollout_seed')}])
    return cfg


def validate(cfg):
    import run_recovery_confirmation as original
    old = json.loads((SOURCE / 'config.json').read_text())
    if digest(SOURCE / 'config.json') != cfg['source_config_sha256']:
        raise ValueError('Changed original scientific configuration')
    original.validate(old)
    for name, sha in cfg['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Changed diagnostic source: ' + name)
    for name, sha in cfg['mask_hashes'].items():
        if digest(Path(cfg['mask']) / name) != sha:
            raise ValueError('Changed shadow mask: ' + name)
    if digest(cfg['event_parameters']) != cfg['event_parameters_sha256']:
        raise ValueError('Changed shadow parameters')


def done(stage, job):
    if stage == 'geometry':
        path = DIRECTORY / stage / (job['id'] + '.json')
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        return data['numerical_geometry_pass'] and digest(path.with_suffix('.png')) == data['figure_sha256']
    if stage == 'shadow':
        stem = f'{job["suite"]}_t{job["task_id"]}_i{job["init_state_id"]}_s{job["rollout_seed"]}'
        paths = [DIRECTORY / 'shadow' / job['id'] / mode / (stem + '.json') for mode in ('none', 'shadow')]
    else:
        arms = ARMS[:1] if stage == 'smoke' else ARMS
        paths = [DIRECTORY / 'rollouts' / job['id'] / (arm + '.json') for arm in arms]
    for path in paths:
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
            if digest(path.with_suffix(ext)) != data[key]:
                raise ValueError('Changed committed artifact ' + str(path))
        if stage == 'smoke' and not data['replay_reference_verified']:
            raise ValueError('Replay control failed')
    return True


def execute(cfg):
    from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    validate(cfg)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    mutex = threading.RLock()
    state = dict(status='running', pid=os.getpid(), active={}, completed={},
        started_at=datetime.now(timezone.utc).isoformat(), deadline_epoch=cfg['deadline_epoch'])
    old = json.loads((SOURCE / 'config.json').read_text())
    def publish(**values):
        with mutex:
            state.update(values, updated_at=datetime.now(timezone.utc).isoformat(),
                         seconds_until_deadline=max(0, int(cfg['deadline_epoch'] - time.time())))
            atomic_json(DIRECTORY / 'sequence_status.json', state)
    def acquire():
        parent = ROOT / '.runtime/grounded_gpu_claims'
        parent.mkdir(parents=True, exist_ok=True)
        for gpu in cfg['gpu_candidates']:
            handle = (parent / (gpu + '.lock')).open('a')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if gpu_is_free(gpu):
                    return gpu, handle
            except BlockingIOError:
                pass
            handle.close()
        return None, None
    try:
        for stage in STAGES:
            jobs = [j for j in cfg['cases'] if stage not in ('smoke', 'shadow') or j['id'] in SMOKE_CASES]
            pending = [j for j in jobs if not done(stage, j)]
            state['completed'][stage] = len(jobs) - len(pending)
            publish(stage=stage, planned_cases=len(jobs), waiting_for_idle_gpu=False)
            def worker():
                while not stopped.is_set() and time.time() < cfg['deadline_epoch']:
                    with mutex:
                        if not pending:
                            return
                    if shutil.disk_usage(DIRECTORY).free < 15 * 1024**3:
                        raise RuntimeError('Less than 15 GiB output storage free')
                    gpu, handle = acquire()
                    if gpu is None:
                        publish(waiting_for_idle_gpu=True)
                        stopped.wait(15)
                        continue
                    process = None
                    try:
                        with mutex:
                            if not pending:
                                return
                            level = pending[0]['position_level']
                            selected = [j for j in pending if j['position_level'] == level][:4 if stage in ('geometry', 'oracle') else 1]
                            for job in selected:
                                pending.remove(job)
                        batch = DIRECTORY / 'batches' / f'{stage}_{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(batch, dict(campaign=str(DIRECTORY), stage=stage, jobs=selected,
                                               deadline_epoch=cfg['deadline_epoch']))
                        variant = ROOT / '.runtime/libero_pro_position' / level
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=old['runtime'],
                            HF_HUB_OFFLINE='1', WANDB_MODE='offline', OMP_NUM_THREADS='2',
                            OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0',
                            LIBERO_CONFIG_PATH=str(DIRECTORY / 'configs' / batch.stem),
                            LIBERO_BDDL_FILES_PATH=str(variant / 'bddl_files'),
                            LIBERO_INIT_STATES_PATH=str(variant / 'init_files'))
                        calls = [[str(ROOT / 'scripts/collect_recovery_grounding_diagnostic.py'), '--batch', str(batch)]]
                        if stage == 'shadow':
                            job = selected[0]
                            calls = [[str(ROOT / 'scripts/collect_event_feedback.py'),
                                '--cases', str(DIRECTORY / 'shadow_cases' / (job['id'] + '.json')),
                                '--output', str(DIRECTORY / 'shadow' / job['id'] / mode),
                                '--parameters', cfg['event_parameters'], '--method', 'regrasp', '--timing', mode,
                                '--localizer', old['localizer'], '--trigger', old['trigger'], '--mask', cfg['mask'],
                                '--hours', str(max(.001, (cfg['deadline_epoch'] - time.time()) / 3600))]
                                for mode in ('none', 'shadow')]
                        for call in calls:
                            command = ['bash', '-ec',
                                'source "$1"\ncd "$COSMOS_REPO"\nshift\nexec "$COSMOS_VENV/bin/python" "$@"',
                                'grounding-diagnostic', str(ROOT / 'scripts/cosmos_env_libero_pro.sh')] + call
                            with batch.with_suffix('.log').open('a') as log:
                                process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=log, start_new_session=True)
                                with mutex:
                                    state['active'][gpu] = dict(pid=process.pid, jobs=[j['id'] for j in selected],
                                                               log=str(batch.with_suffix('.log')))
                                publish(waiting_for_idle_gpu=False)
                                termination = None
                                while process.poll() is None:
                                    if (stopped.is_set() or time.time() >= cfg['deadline_epoch']) and termination is None:
                                        os.killpg(process.pid, signal.SIGTERM)
                                        termination = time.time()
                                    if termination is not None and time.time() - termination > 120:
                                        os.killpg(process.pid, signal.SIGKILL)
                                        process.wait()
                                    time.sleep(3)
                                    publish()
                                if process.returncode:
                                    raise RuntimeError(f'Worker exit {process.returncode}: {batch.with_suffix(".log")}')
                        if not all(done(stage, j) for j in selected):
                            if time.time() >= cfg['deadline_epoch'] or stopped.is_set():
                                return
                            raise RuntimeError('Uncommitted diagnostic output: ' + str(batch))
                        with mutex:
                            state['completed'][stage] += len(selected)
                    except BaseException:
                        stopped.set()
                        raise
                    finally:
                        if process is not None and process.poll() is None:
                            os.killpg(process.pid, signal.SIGTERM)
                            try:
                                process.wait(timeout=120)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.wait()
                        handle.close()
                        with mutex:
                            state['active'].pop(gpu, None)
                        publish()
            with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
                futures = [pool.submit(worker) for _ in range(cfg['max_workers'])]
                for future in futures:
                    future.result()
            complete = all(done(stage, j) for j in jobs)
            with (DIRECTORY / 'analysis.log').open('a') as log:
                subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_recovery_grounding_diagnostic.py'),
                    '--campaign', str(DIRECTORY)], cwd=ROOT, stdout=log, stderr=log, check=True)
            if not complete:
                publish(status='partial', reason='deadline_or_stop')
                return
        publish(status='completed', stage='analysis_complete')
    except BaseException as error:
        stopped.set()
        publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare', 'launch', 'execute', 'status'):
        group.add_argument('--' + mode, action='store_true')
    args = parser.parse_args()
    if args.status:
        print((DIRECTORY / 'sequence_status.json').read_text())
        return
    import run_recovery_confirmation as original
    if ROOT != original.REMOTE:
        raise ValueError('Canonical server only')
    if args.prepare:
        cfg = prepare()
        print(json.dumps(dict(cases=len(cfg['cases']), oracle_outcomes=len(cfg['cases']) * len(ARMS),
                              deadline_epoch=cfg['deadline_epoch']), indent=2))
        return
    cfg = json.loads((DIRECTORY / 'config.json').read_text())
    validate(cfg)
    if args.execute:
        execute(cfg)
        return
    with (DIRECTORY / 'sequence.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if time.time() >= cfg['deadline_epoch']:
        raise ValueError('Frozen resource deadline expired')
    with (DIRECTORY / 'launcher.log').open('a') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    result = dict(pid=process.pid, started_at=datetime.now(timezone.utc).isoformat(),
                  config_sha256=digest(DIRECTORY / 'config.json'), deadline_epoch=cfg['deadline_epoch'])
    atomic_json(DIRECTORY / 'launch.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

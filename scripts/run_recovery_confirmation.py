#!/usr/bin/env python3
"""Nine-hour, resumable, idle-only recovery confirmation dispatcher."""
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

from recovery_confirmation import NAME, ARMS, TIMES, PRIMARY, make_jobs, expected_arms, job_done
from p5_repeat_feedback import atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY = ROOT / 'experiments/campaigns' / NAME
FILES = ('recovery_confirmation.py', 'collect_recovery_confirmation.py',
         'run_recovery_confirmation.py', 'analyze_recovery_confirmation.py')


def prepare():
    import pandas as pd
    old_path = ROOT / 'experiments/campaigns/observation_contract_20260911/config.json'
    old = json.loads(old_path.read_text())
    calibration = 'experiments/frozen_models/perception_regrasp_20260904/calibration_manifest.csv'
    jobs = []
    for source_id in ('x0.2_t2_i46_r0', 'x0.2_t9_i46_r0', 'x0.1_t9_i46_r0'):
        source_job = next(j for j in old['jobs'] if j['phase'] == 'screen' and
                          j['source_id'] == source_id and j['suffix_repeat'] == 0)
        source = old_path.parent / 'screen' / source_job['id']
        hashes = {name: digest(source / name) for name in
            ['prefix.npz', 'prefix.json'] + [a + e for a in ARMS for e in ('.json', '.npz')]}
        jobs.append(dict(source_job, phase='smoke', id=source_id, case_id=source_id,
            source_id=source_job['id'], source_hashes=hashes, boundary=72, cohort='technical'))
    jobs += make_jobs(pd.read_csv(ROOT / calibration))
    assets = {}
    for level in sorted({j['position_level'] for j in jobs}):
        for kind in ('bddl_files', 'init_files'):
            parent = ROOT / 'LIBERO-PRO/libero/libero' / kind / ('libero_object_temp_' + level)
            files = sorted(p for p in parent.iterdir() if p.is_file())
            if len(files) != 10:
                raise ValueError('Expected ten benchmark assets in ' + str(parent))
            for source in files:
                target = ROOT / '.runtime/libero_pro_position' / level / kind / 'libero_object_temp' / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists() or digest(target) != digest(source):
                    shutil.copy2(source, target)
                assets[str(target.relative_to(ROOT))] = digest(target)
    scripts = {name: digest(ROOT / 'scripts' / name) for name in set(old['scripts']) | set(FILES)}
    cfg = dict(name=NAME, jobs=jobs, arms=list(ARMS), boundaries=list(TIMES), primary=list(PRIMARY),
        runtime=old['runtime'], runtime_hashes=old['runtime_hashes'], artifacts=old['artifacts'],
        localizer=old['localizer'], trigger=old['trigger'], scripts=scripts, position_files=assets,
        calibration=calibration, calibration_sha256=digest(ROOT / calibration),
        source_config=str(old_path.relative_to(ROOT)), source_config_sha256=digest(old_path),
        replay_source=str(REMOTE / old_path.parent.relative_to(ROOT)),
        gpu_candidates=list('12367045'), max_workers=8, hours=9, grace_seconds=120,
        max_batch_main=4, max_batch_timing=8, generated_horizon=16, suffix_horizon=8,
        K=4, denoising_steps=5, prediction_mode='parallel', physical_max_t=280,
        automatic_fit=False, automatic_holdout=False,
        sampling_scope='fresh seeds on calibration-disjoint inits, not globally untouched init states',
        transfer_scope='x0.3 cells absent in localizer calibration; not new objects or official whole benchmark',
        phase_order=['smoke', 'main', 'timing'])
    cfg = json.loads(json.dumps(cfg))
    path = DIRECTORY / 'config.json'
    if path.exists() and json.loads(path.read_text()) != cfg:
        raise ValueError('Frozen configuration changed; use a new campaign identifier')
    if not path.exists():
        atomic_json(path, cfg)
    return cfg


def validate(cfg):
    for name, sha in cfg['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Changed script: ' + name)
    for mapping in ('artifacts', 'position_files'):
        for name, sha in cfg[mapping].items():
            if digest(ROOT / name) != sha:
                raise ValueError('Changed asset: ' + name)
    for name, sha in cfg['runtime_hashes'].items():
        if digest(name) != sha:
            raise ValueError('Changed model runtime: ' + name)
    for name, key in ((cfg['calibration'], 'calibration_sha256'), (cfg['source_config'], 'source_config_sha256')):
        if digest(ROOT / name) != cfg[key]:
            raise ValueError('Changed frozen source: ' + name)
    for job in cfg['jobs']:
        if job['phase'] == 'smoke':
            for name, sha in job['source_hashes'].items():
                if digest(Path(cfg['replay_source']) / 'screen' / job['source_id'] / name) != sha:
                    raise ValueError('Changed smoke reference')


def execute(cfg):
    from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = DIRECTORY / 'budget.json'
    if not path.exists():
        now = time.time()
        atomic_json(path, dict(start_epoch=now, deadline_epoch=now + cfg['hours'] * 3600))
    budget = json.loads(path.read_text())
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    mutex, occupied = threading.RLock(), set()
    state = dict(status='running', stage='preflight', pid=os.getpid(), active={},
        deadline_epoch=budget['deadline_epoch'], started_at=datetime.fromtimestamp(
            budget['start_epoch'], timezone.utc).isoformat(), automatic_holdout=False)
    completed = {p: set() for p in cfg['phase_order']}
    total = sum(len(expected_arms(j)) for j in cfg['jobs'])

    def publish(**values):
        with mutex:
            state.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            counts = {p: sum(len(expected_arms(j)) for j in cfg['jobs'] if
                j['phase'] == p and j['id'] in completed[p]) for p in completed}
            state.update(completed_branches=counts, expected_branches=total,
                seconds_until_deadline=max(0, int(budget['deadline_epoch'] - time.time())))
            if sum(counts.values()):
                rate = sum(counts.values()) / max(1, time.time() - budget['start_epoch'])
                state['eta_remaining_seconds'] = int((total - sum(counts.values())) / rate)
            atomic_json(DIRECTORY / 'sequence_status.json', state)

    def acquire():
        for gpu in cfg['gpu_candidates']:
            with mutex:
                if gpu in occupied:
                    continue
                occupied.add(gpu)
            parent = ROOT / '.runtime/grounded_gpu_claims'
            parent.mkdir(parents=True, exist_ok=True)
            handle = (parent / (gpu + '.lock')).open('a')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if gpu_is_free(gpu):
                    return gpu, handle
            except BlockingIOError:
                pass
            handle.close()
            with mutex:
                occupied.discard(gpu)
        return None, None

    def analyze(phase, require_complete):
        command = [sys.executable, str(ROOT / 'scripts/analyze_recovery_confirmation.py'),
                   '--campaign', str(DIRECTORY), '--phase', phase]
        if require_complete:
            command.append('--require-complete')
        with (DIRECTORY / f'analysis_{phase}.log').open('a') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)

    try:
        publish()
        validate(cfg)
        for job in cfg['jobs']:
            if job_done(DIRECTORY, job, hashes=True):
                completed[job['phase']].add(job['id'])
        for phase in cfg['phase_order']:
            jobs = [j for j in cfg['jobs'] if j['phase'] == phase]
            pending = [j for j in jobs if j['id'] not in completed[phase]]
            attempts = {}
            publish(stage=phase, waiting_for_idle_gpu=False)

            def worker():
                while not stop.is_set() and time.time() < budget['deadline_epoch']:
                    with mutex:
                        if not pending:
                            return
                    if shutil.disk_usage(DIRECTORY).free < 15 * 1024**3:
                        raise RuntimeError('Output filesystem has less than 15 GiB free')
                    gpu, handle = acquire()
                    if gpu is None:
                        publish(waiting_for_idle_gpu=True)
                        stop.wait(15)
                        continue
                    process = None
                    try:
                        with mutex:
                            if not pending:
                                return
                            level = pending[0]['position_level']
                            limit = 1 if phase == 'smoke' else cfg['max_batch_' + phase]
                            selected = [j for j in pending if j['position_level'] == level][:limit]
                            for job in selected:
                                pending.remove(job)
                        payload = DIRECTORY / 'batches' / f'{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(payload, dict(campaign=str(DIRECTORY), jobs=selected,
                                                 deadline_epoch=budget['deadline_epoch']))
                        variant = ROOT / '.runtime/libero_pro_position' / level
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=cfg['runtime'],
                            HF_HUB_OFFLINE='1', WANDB_MODE='offline', OMP_NUM_THREADS='2',
                            OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0',
                            LIBERO_BDDL_FILES_PATH=str(variant / 'bddl_files'),
                            LIBERO_INIT_STATES_PATH=str(variant / 'init_files'),
                            LIBERO_CONFIG_PATH=str(DIRECTORY / 'configs' / payload.stem))
                        command = ['bash', '-ec',
                            'source "$1"\ncd "$COSMOS_REPO"\nexec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                            'recovery-confirm', str(ROOT / 'scripts/cosmos_env_libero_pro.sh'),
                            str(ROOT / 'scripts/collect_recovery_confirmation.py'), str(payload)]
                        with payload.with_suffix('.log').open('a') as log:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)
                            with mutex:
                                state['active'][gpu] = dict(pid=process.pid, jobs=[j['id'] for j in selected],
                                    log=str(payload.with_suffix('.log')))
                            publish(waiting_for_idle_gpu=False)
                            terminated = None
                            while process.poll() is None:
                                if (stop.is_set() or time.time() >= budget['deadline_epoch']) and terminated is None:
                                    os.killpg(process.pid, signal.SIGTERM)
                                    terminated = time.time()
                                if terminated is not None and time.time() - terminated > cfg['grace_seconds']:
                                    os.killpg(process.pid, signal.SIGKILL)
                                    process.wait()
                                stop.wait(5) if not stop.is_set() else time.sleep(1)
                                publish()
                        with mutex:
                            for job in selected:
                                if job_done(DIRECTORY, job, hashes=True):
                                    completed[phase].add(job['id'])
                                elif not stop.is_set() and time.time() < budget['deadline_epoch']:
                                    attempts[job['id']] = attempts.get(job['id'], 0) + 1
                                    if attempts[job['id']] > 1:
                                        raise RuntimeError('Repeated incomplete worker: ' + str(payload))
                                    pending.append(job)
                                    state.setdefault('retry_logs', []).append(str(payload.with_suffix('.log')))
                    except BaseException:
                        stop.set()
                        raise
                    finally:
                        if process is not None and process.poll() is None:
                            os.killpg(process.pid, signal.SIGTERM)
                            try:
                                process.wait(timeout=cfg['grace_seconds'])
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.wait()
                        handle.close()
                        with mutex:
                            occupied.discard(gpu)
                            state['active'].pop(gpu, None)
                        publish()

            with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
                futures = [pool.submit(worker) for _ in range(cfg['max_workers'])]
                for future in futures:
                    future.result()
            complete = all(j['id'] in completed[phase] for j in jobs)
            analyze(phase, complete)
            if not complete:
                publish(status='partial', stop_reason='deadline_or_stop', stage=phase)
                return
        publish(status='completed', stage='analysis_complete')
    except BaseException as error:
        stop.set()
        publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'launch', 'execute', 'status', 'validate'):
        group.add_argument('--' + name, action='store_true')
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        cfg = prepare()
        print(json.dumps(dict(jobs=len(cfg['jobs']), branches=sum(len(expected_arms(j)) for j in cfg['jobs']),
                              config=str(DIRECTORY / 'config.json')), indent=2))
        return
    if args.status:
        print((DIRECTORY / 'sequence_status.json').read_text())
        return
    cfg = json.loads((DIRECTORY / 'config.json').read_text())
    if ROOT != REMOTE:
        raise ValueError('GPU commands are restricted to the canonical server project')
    validate(cfg)
    if args.validate:
        print('Frozen sources, runtime, assets and replay inputs verified')
    elif args.execute:
        execute(cfg)
    else:
        with (DIRECTORY / 'sequence.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Already active')
                return
        with (DIRECTORY / 'launcher.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute'],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        result = dict(pid=process.pid, config_sha256=digest(DIRECTORY / 'config.json'),
                      started_at=datetime.now(timezone.utc).isoformat(), hours=cfg['hours'])
        atomic_json(DIRECTORY / 'launch.json', result)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

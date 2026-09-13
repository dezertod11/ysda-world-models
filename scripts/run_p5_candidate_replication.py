#!/usr/bin/env python3
"""Autonomous idle-GPU queue with frozen inputs, smoke gate, and CPU report."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

try:
    from scripts.p5_repeat_feedback import atomic_json, digest
    from scripts.p5_candidate_replication import NAME, branch_schedule, make_jobs
    from scripts.run_libero_experiment_campaign import gpu_is_free
except ModuleNotFoundError:
    from p5_repeat_feedback import atomic_json, digest
    from p5_candidate_replication import NAME, branch_schedule, make_jobs
    from run_libero_experiment_campaign import gpu_is_free

ROOT = Path(__file__).resolve().parents[1]
NEW_SCRIPTS = ('p5_candidate_replication.py', 'collect_p5_candidate_replication.py',
               'run_p5_candidate_replication.py', 'analyze_p5_candidate_replication.py')


def prepare(directory, hours):
    source = ROOT / 'experiments/campaigns/p5_repeat_feedback_20260910/config.json'
    previous = json.loads(source.read_text())
    hashes = dict(previous['scripts'], **{name: digest(ROOT / 'scripts' / name) for name in NEW_SCRIPTS})
    for name, value in hashes.items():
        assert digest(ROOT / 'scripts' / name) == value, name
    for name, value in previous['runtime_hashes'].items():
        assert digest(name) == value, name
    path = directory / 'config.json'
    if path.exists():
        config = json.loads(path.read_text())
        assert config['scripts'] == hashes and config['source_config_sha256'] == digest(source)
        return config
    config = dict(name=NAME, source_config_sha256=digest(source), source_config=str(source),
        created_at=datetime.now(timezone.utc).isoformat(), deadline_epoch=time.time()+hours*3600,
        max_workers=3, batch_size=2, gpu_candidates=list('13502467'),
        jobs=make_jobs(previous), scripts=hashes, runtime=previous['runtime'], runtime_hashes=previous['runtime_hashes'],
        expected_branches=690, expected_smoke_branches=6,
        smoke_jobs=['repeat_pool_13', 'repeat_pool_11', 'neighbor_t2_i12'],
        primary_pairs=[['repeat_pool_13', 3, 4], ['repeat_pool_13', 5, 4], ['repeat_pool_11', 6, 7]],
        suffix_repeats=10, neighbor_split=[[0,1,2,3,4], [5,6,7,8,9]],
        protocol='conditional_replication_and_new_pool_diagnostic_not_new_controller',
        no_automatic_fit_or_holdout=True)
    for job in config['jobs']:
        if job['kind'] == 'replication':
            assert digest(job['sidecar']) == job['sidecar_sha256']
    atomic_json(path, config)
    return config


def done(directory, job, smoke):
    sub = directory / ('smoke' if smoke else 'runs') / job['id']
    marker = sub / 'completed.json'
    if not marker.exists():
        return False
    if json.loads(marker.read_text())['status'] == 'skipped':
        return True
    for repeat, index, seed in branch_schedule(job, smoke):
        path = sub / f'r{repeat:02d}_c{index}.json'
        if not path.exists() or not path.with_suffix('.npz').exists():
            return False
        row = json.loads(path.read_text())
        if row['suffix_seed'] != seed or not row['terminal_available']:
            raise ValueError(f'Invalid completed branch: {path}')
        if row['video_path'] and not (directory / row['video_path']).exists():
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--hours', type=float, default=12)
    args = parser.parse_args()
    directory = ROOT / 'experiments/campaigns' / NAME
    directory.mkdir(parents=True, exist_ok=True)
    if args.status:
        for file in ['sequence_status.json', 'analysis/summary.json']:
            if (directory / file).exists():
                print((directory / file).read_text())
        return
    lock = (directory / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = prepare(directory, args.hours)
    print(f'Frozen {NAME}: 690 branches + 6 smoke; 3 idle-only workers', flush=True)
    if args.launch:
        lock.close()
        with (directory/'launcher.log').open('a') as log:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute'],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        launch = dict(pid=child.pid, started_at=datetime.now(timezone.utc).isoformat(),
                      config_sha256=digest(directory/'config.json'))
        atomic_json(directory/'launch.json', launch)
        print(json.dumps(launch), flush=True)
        return
    if not args.execute:
        return
    state = dict(status='running', stage='smoke', pid=os.getpid(), active={},
                 started_at=datetime.now(timezone.utc).isoformat(), expected_branches=690)
    mutex = threading.RLock()
    occupied = set()
    stop = threading.Event()
    def publish():
        with mutex:
            files = list((directory / 'runs').glob('*/r*_c*.json'))
            state.update(completed_branches=len(files), updated_at=datetime.now(timezone.utc).isoformat(),
                         deadline_epoch=config['deadline_epoch'])
            records = [json.loads(p.read_text()) for p in files]
            if records:
                per_branch = sum(r['elapsed_seconds'] for r in records) / len(records)
                active = len(state['active'])
                state['estimated_seconds_remaining_if_current_workers_stay_available'] = (
                    (690-len(records))*per_branch/active if active else None)
            atomic_json(directory / 'sequence_status.json', state)
    def signal_stop(*_):
        stop.set()
    signal.signal(signal.SIGTERM, signal_stop)
    signal.signal(signal.SIGINT, signal_stop)
    def heartbeat():
        while not stop.wait(15):
            publish()
    heart = threading.Thread(target=heartbeat, daemon=True)
    heart.start()
    publish()
    def process(jobs, gpu, smoke):
        for name, sha in config['scripts'].items():
            assert digest(ROOT / 'scripts' / name) == sha, name
        for name, sha in config['runtime_hashes'].items():
            assert digest(name) == sha, name
        path = directory / 'batches' / f'{time.time_ns()}_gpu{gpu}.json'
        atomic_json(path, dict(jobs=jobs, campaign=str(directory), smoke=smoke,
                               deadline_epoch=config['deadline_epoch']))
        env = dict(os.environ, **jobs[0]['environment'], CUDA_VISIBLE_DEVICES=gpu,
            COSMOS_REPO=config['runtime'], HF_HUB_OFFLINE='1', WANDB_MODE='offline',
            OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
            LIBERO_CONFIG_PATH=str(directory / 'configs' / path.stem),
            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0', PYTHONUNBUFFERED='1')
        command = ['bash', '-ec', 'source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                   'replication', str(ROOT/'scripts/cosmos_env_libero_pro.sh'),
                   str(ROOT/'scripts/collect_p5_candidate_replication.py'), str(path)]
        with path.with_suffix('.log').open('a') as log:
            child = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            with mutex:
                state['active'][gpu] = dict(pid=child.pid, jobs=[j['id'] for j in jobs], batch=str(path))
            publish()
            sent = False
            while child.poll() is None:
                if stop.is_set() and not sent:
                    child.terminate()
                    sent = True
                if time.time() > config['deadline_epoch'] + 600:
                    child.terminate()
                    try:
                        child.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                    raise TimeoutError('Owned worker exceeded deadline grace')
                time.sleep(2)
            if child.returncode:
                raise RuntimeError(f'Worker failed; inspect {path.with_suffix(".log")}')
    def phase(jobs, smoke):
        pending = [job for job in jobs if not done(directory, job, smoke)]
        def work():
            while not stop.is_set() and time.time() < config['deadline_epoch']:
                with mutex:
                    if not pending:
                        return
                gpu = None
                for candidate in config['gpu_candidates']:
                    with mutex:
                        if candidate in occupied:
                            continue
                        occupied.add(candidate)
                    if gpu_is_free(candidate):
                        gpu = candidate
                        break
                    with mutex:
                        occupied.remove(candidate)
                if gpu is None:
                    stop.wait(10)
                    continue
                try:
                    with mutex:
                        if not pending:
                            return
                        first = pending[0]
                        jobs = [j for j in pending if j['environment'] == first['environment']][:1 if smoke else config['batch_size']]
                        for job in jobs:
                            pending.remove(job)
                    process(jobs, gpu, smoke)
                except BaseException:
                    stop.set()
                    raise
                finally:
                    with mutex:
                        occupied.discard(gpu)
                        state['active'].pop(gpu, None)
                    publish()
        with ThreadPoolExecutor(max_workers=config['max_workers']) as executor:
            futures = [executor.submit(work) for _ in range(config['max_workers'])]
            for future in futures:
                future.result()
    error = None
    try:
        smoke_jobs = [j for j in config['jobs'] if j['id'] in config['smoke_jobs']]
        phase(smoke_jobs, True)
        if all(done(directory, j, True) for j in smoke_jobs) and not stop.is_set():
            state['stage'] = 'replication_and_neighbor_pools'
            publish()
            phase(config['jobs'], False)
        state['status'] = 'completed' if all(done(directory, j, False) for j in config['jobs']) else 'partial'
    except BaseException as exc:
        error = exc
        state.update(status='failed', error=repr(exc))
    finally:
        stop.set()
        heart.join()
        publish()
        result = subprocess.run([sys.executable, str(ROOT/'scripts/analyze_p5_candidate_replication.py'), '--campaign', str(directory)], cwd=ROOT)
        if result.returncode:
            state.update(status='analysis_failed', analysis_returncode=result.returncode)
        state['finished_at'] = datetime.now(timezone.utc).isoformat()
        publish()
    if error:
        raise error


if __name__ == '__main__':
    main()

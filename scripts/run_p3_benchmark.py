#!/usr/bin/env python3
"""Autonomous, bounded, resumable P3 benchmark on exclusively idle GPUs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import csv
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

from p3_benchmark import NAME, ARMS, benchmark_jobs, asset_root
from event_feedback import EventConfig
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')


def prepare(directory, hours):
    reference = ROOT / 'experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/episode_outcomes.csv'
    with reference.open() as f:
        jobs = benchmark_jobs(list(csv.DictReader(f)))
    old = json.loads((ROOT / 'experiments/campaigns/recovery_confirmation_20260913/config.json').read_text())
    smoke = []
    for key in ('x0.2_t5_i25', 'x0.3_t1_i25'):
        source = next(j for j in old['jobs'] if j['id'] == key and j['phase'] == 'main')
        row = json.loads((ROOT / 'experiments/campaigns/recovery_confirmation_20260913/main' / key / 'physical_regrasp.json').read_text())
        smoke.append(dict(id=key, phase='smoke', factor='Position', level=source['position_level'],
            suite='libero_object_temp', task_id=source['task_id'], init_state_id=source['init_state_id'],
            rollout_seed=source['rollout_seed'], task_description=row['task_description']))
    assets = {}
    for job in smoke + jobs:
        base = ROOT / asset_root(job)
        for kind in ('bddl_files', 'init_files'):
            parent = base / kind / job['suite']
            if job['factor'] == 'Position' and not parent.exists():
                source = ROOT / 'LIBERO-PRO/libero/libero' / kind / (job['suite'] + '_' + job['level'])
                shutil.copytree(source, parent)
            files = sorted(p for p in parent.glob('*') if p.is_file())
            if len(files) != 10:
                raise ValueError('Expected ten benchmark assets: ' + str(parent))
            for p in files:
                key = str(p.relative_to(ROOT))
                if key not in assets:
                    assets[key] = digest(p)
    mask = ROOT / 'experiments/campaigns/grounded_probe_20260911_v2/mask_model'
    artifacts = dict(old['artifacts'])
    for p in mask.glob('*'):
        if p.is_file():
            artifacts[str(p.relative_to(ROOT))] = digest(p)
    scripts = {p.name: digest(p) for p in (ROOT / 'scripts').glob('*.py')}
    runtime = Path(old['runtime']) / 'cosmos_policy'
    runtime_hashes = {str(p): digest(p) for p in runtime.rglob('*.py')}
    cfg = dict(name=directory.name, created_at=datetime.now(timezone.utc).isoformat(), jobs=smoke + jobs,
        arms=list(ARMS), runtime=old['runtime'], runtime_hashes=runtime_hashes,
        localizer=old['localizer'], trigger=old['trigger'], mask=str(mask), scripts=scripts,
        assets=assets, artifacts=artifacts, source_manifest=str(reference), reference_sha256=digest(reference),
        event_parameters=asdict(EventConfig()), hours=hours, gpu_candidates=list('01234567'),
        max_workers=8, max_batch=6, idle_only=True, deadline_policy='launch time + hours; no silent extension',
        K=4, prediction_mode='parallel', denoising_steps=5, generated_horizon=16, max_steps=280,
        historical_control_step=72, seed_scheme='rollout_seed + query * 1000 + candidate_index',
        event_rule='Persistent mask-based miss after close near target; gate; one recovery; H8 after recovery',
        event_uncertainty_routing=False, automatic_fit=False, automatic_holdout=False,
        scope='Historical valid199 support, new paired collection; exploratory transfer, not untouched holdout')
    path = directory / 'config.json'
    if path.exists():
        raise ValueError('Already prepared; use --launch to resume unchanged settings')
    atomic_json(path, cfg)
    for name in scripts:
        target = directory / 'source/scripts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'scripts' / name, target)
    return cfg


def validate(cfg):
    for name, sha in cfg['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Frozen script changed: ' + name)
    for mapping in ('assets', 'artifacts', 'runtime_hashes'):
        for name, sha in cfg[mapping].items():
            if digest(ROOT / name) != sha:
                raise ValueError('Frozen asset changed: ' + name)


def done(directory, job):
    path = directory / job['phase'] / job['id'] / 'completed.json'
    if not path.exists():
        return False
    marker = json.loads(path.read_text())
    if marker['config_sha256'] != digest(directory / 'config.json') or not marker['audit_pass']:
        raise ValueError('Invalid case marker')
    return True


def execute(directory):
    from run_libero_experiment_campaign import gpu_is_free
    cfg = json.loads((directory / 'config.json').read_text())
    lock = (directory / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    validate(cfg)
    budget_path = directory / 'budget.json'
    if not budget_path.exists():
        now = time.time()
        atomic_json(budget_path, dict(start_epoch=now, deadline_epoch=now + cfg['hours'] * 3600))
    budget = json.loads(budget_path.read_text())
    stop = threading.Event()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    mutex = threading.RLock()
    state = dict(status='running', stage='smoke', pid=os.getpid(), active={}, expected_rollouts=995,
                 deadline_epoch=budget['deadline_epoch'], started_at=budget['start_epoch'])
    finished = {j['id'] for j in cfg['jobs'] if done(directory, j)}
    def publish(**updates):
        with mutex:
            state.update(updates, updated_at=datetime.now(timezone.utc).isoformat())
            n = sum(j['id'] in finished for j in cfg['jobs'] if j['phase'] == 'main')
            completed = sum(1 for j in cfg['jobs'] if j['phase'] == 'main'
                for a in ARMS if (directory / 'main' / j['id'] / (a + '.json')).exists())
            elapsed = time.time() - budget['start_epoch']
            state.update(matched_cases=n, completed_rollouts=completed,
                seconds_until_deadline=max(0, int(budget['deadline_epoch'] - time.time())),
                eta_remaining_seconds=int((995-completed)*elapsed/completed) if completed else None)
            atomic_json(directory / 'sequence_status.json', state)
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
    def analyze(verify=False):
        command = [sys.executable, str(ROOT / 'scripts/analyze_p3_benchmark.py'), '--campaign', str(directory)]
        if not verify:
            command.append('--already-audited')
        with (directory / 'analysis.log').open('a') as log:
            subprocess.run(command, stdout=log, stderr=log, check=True, cwd=ROOT)
    try:
        for phase in ('smoke', 'main'):
            pending = [j for j in cfg['jobs'] if j['phase'] == phase and j['id'] not in finished]
            publish(stage=phase)
            def worker():
                while not stop.is_set() and time.time() < budget['deadline_epoch']:
                    with mutex:
                        if not pending:
                            return
                    if shutil.disk_usage(directory).free < 15 * 1024**3:
                        stop.set()
                        raise RuntimeError('Output disk below 15 GiB')
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
                            first = pending[0]
                            selected = [j for j in pending if (j['suite'], j['level']) ==
                                (first['suite'], first['level'])][:1 if phase == 'smoke' else cfg['max_batch']]
                            for j in selected:
                                pending.remove(j)
                        batch = directory / 'batches' / f'{phase}_{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(batch, dict(campaign=str(directory), jobs=selected, deadline_epoch=budget['deadline_epoch']))
                        base = ROOT / asset_root(selected[0])
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=cfg['runtime'],
                            HF_HUB_OFFLINE='1', WANDB_MODE='offline', OMP_NUM_THREADS='2',
                            OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0',
                            LIBERO_CONFIG_PATH=str(directory / 'configs' / batch.stem),
                            LIBERO_BDDL_FILES_PATH=str(base / 'bddl_files'), LIBERO_INIT_STATES_PATH=str(base / 'init_files'))
                        cmd = ['bash', '-ec', 'source "$1"\ncd "$COSMOS_REPO"\nshift\nexec "$COSMOS_VENV/bin/python" "$@"',
                            'p3-benchmark', str(ROOT / 'scripts/cosmos_env_libero_pro.sh'),
                            str(ROOT / 'scripts/collect_p3_benchmark.py'), '--batch', str(batch)]
                        with batch.with_suffix('.log').open('a') as log:
                            process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)
                            with mutex:
                                state['active'][gpu] = dict(pid=process.pid, jobs=[j['id'] for j in selected], log=str(batch.with_suffix('.log')))
                            publish(waiting_for_idle_gpu=False)
                            termination = None
                            while process.poll() is None:
                                if (stop.is_set() or time.time() >= budget['deadline_epoch']) and termination is None:
                                    os.killpg(process.pid, signal.SIGTERM)
                                    termination = time.time()
                                if termination is not None and time.time() - termination > 120:
                                    os.killpg(process.pid, signal.SIGKILL)
                                    process.wait()
                                time.sleep(5)
                                with mutex:
                                    finished.update(j['id'] for j in selected if done(directory, j))
                                publish()
                            if process.returncode and not stop.is_set() and time.time() < budget['deadline_epoch']:
                                raise RuntimeError('Worker failed; inspect ' + str(batch.with_suffix('.log')))
                        if not all(done(directory, j) for j in selected) and not stop.is_set() and time.time() < budget['deadline_epoch']:
                            raise RuntimeError('Incomplete worker without deadline: ' + str(batch))
                        with mutex:
                            finished.update(j['id'] for j in selected if done(directory, j))
                    except BaseException:
                        stop.set()
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
            if any(j['id'] not in finished for j in cfg['jobs'] if j['phase'] == phase):
                analyze()
                publish(status='partial', reason='deadline_or_stop')
                return
            analyze(verify=True)
        publish(status='completed', stage='analysis_complete')
    except BaseException as error:
        try:
            analyze()
        finally:
            publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, default=ROOT / 'experiments/campaigns' / NAME)
    parser.add_argument('--hours', type=float, default=22)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare', 'launch', 'execute', 'status'):
        modes.add_argument('--' + mode, action='store_true')
    args = parser.parse_args()
    directory = args.campaign.resolve()
    if args.status:
        print((directory / 'sequence_status.json').read_text())
        return
    if ROOT != REMOTE or not directory.is_relative_to(ROOT / 'experiments/campaigns'):
        raise ValueError('Use canonical server campaign directory')
    if args.prepare:
        cfg = prepare(directory, args.hours)
        print(json.dumps(dict(cases=199, arms=cfg['arms'], hours=cfg['hours'])))
    elif args.execute:
        execute(directory)
    else:
        with (directory / 'launcher.log').open('a') as log:
            p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute', '--campaign', str(directory)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        atomic_json(directory / 'launch.json', dict(pid=p.pid, started_at=datetime.now(timezone.utc).isoformat()))
        print(json.dumps(dict(pid=p.pid, campaign=str(directory))))


if __name__ == '__main__':
    main()

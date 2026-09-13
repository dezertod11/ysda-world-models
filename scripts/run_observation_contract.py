#!/usr/bin/env python3
"""Autonomous observation-contract study with a strict replay-first gate."""
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
    from scripts.observation_contract import NAME, ARMS, make_jobs, CONTRASTS, ORACLES, PARAMS
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from observation_contract import NAME, ARMS, make_jobs, CONTRASTS, ORACLES, PARAMS
    from p5_repeat_feedback import atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY = ROOT / 'experiments/campaigns' / NAME
FILES = ('observation_contract.py', 'collect_observation_contract.py',
         'run_observation_contract.py', 'analyze_observation_contract.py')


def prepare():
    source = 'experiments/campaigns/timing_eligibility_20260911_v2'
    old = json.loads((ROOT / source / 'config.json').read_text())
    jobs = make_jobs(old)
    position_files = {}
    for level in sorted({j['position_level'] for j in jobs}):
        for kind in ('bddl_files', 'init_files'):
            source_dir = ROOT / 'LIBERO-PRO/libero/libero' / kind / ('libero_object_temp_' + level)
            files = [p for p in source_dir.iterdir() if p.is_file()]
            if len(files) != 10:
                raise ValueError('Expected ten tasks in ' + str(source_dir))
            for file in files:
                target = Path('.runtime/libero_pro_position') / level / kind / 'libero_object_temp' / file.name
                position_files[str(target)] = digest(file)
    for job in jobs:
        folder = ROOT / source / job['source_phase'] / job['source_id']
        names = ['prefix.npz', 'prefix.json']
        names += [a + ext for a in ARMS[:2] for ext in ('.json', '.npz')]
        job['source_hashes'] = {name: digest(folder / name) for name in names}
    cfg = dict(name=NAME, arms=ARMS, jobs=jobs, contrasts=CONTRASTS,
        source_config=source + '/config.json', source_config_sha256=digest(ROOT / source / 'config.json'),
        replay_source=str(REMOTE / source), scripts=dict(old['scripts'], **{n: digest(ROOT / 'scripts' / n) for n in FILES}),
        artifacts=old['artifacts'], runtime=old['runtime'], runtime_hashes=old['runtime_hashes'],
        localizer=old['localizer'], trigger=old['trigger'], position_files=position_files, gpu_candidates=list('12345670'),
        max_workers=7, batch_size=2, hours=8, K=4, generated_horizon=16, executed_suffix_horizon=8,
        prefix_t=72, physical_max_t=280, denoising_steps=5, prediction_mode='parallel',
        primary='refresh_preserve_regrasp', oracle_arms=list(ORACLES), params=PARAMS,
        automatic_holdout=False, previous_holdout_38_45_unopened=True,
        scientific_scope='development_mechanism_96_existing_prefixes_with_two_suffix_seeds_not_new_init_holdout',
        hard_deadline_epoch=datetime.fromisoformat('2026-09-12T05:00:00+03:00').timestamp())
    cfg = json.loads(json.dumps(cfg))
    path = DIRECTORY / 'config.json'
    if path.exists() and json.loads(path.read_text()) != cfg:
        raise ValueError('Frozen configuration changed')
    if not path.exists():
        atomic_json(path, cfg)
    return cfg


def validate(cfg):
    for name, sha in cfg['position_files'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Changed prepared position asset ' + name)
    for name, sha in cfg['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Changed source ' + name)
    for name, sha in cfg['artifacts'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Changed artifact ' + name)
    for name, sha in cfg['runtime_hashes'].items():
        if digest(name) != sha:
            raise ValueError('Changed runtime ' + name)
    if digest(ROOT / cfg['source_config']) != cfg['source_config_sha256']:
        raise ValueError('Changed parent')
    for job in cfg['jobs']:
        if job['phase'] == 'smoke':
            folder = Path(cfg['replay_source']) / job['source_phase'] / job['source_id']
            for name, sha in job['source_hashes'].items():
                if digest(folder / name) != sha:
                    raise ValueError('Changed replay source')


def done(job):
    folder = DIRECTORY / job['phase'] / job['id']
    if not (folder / 'completed.json').exists():
        return False
    if json.loads((folder / 'completed.json').read_text())['arms'] != list(ARMS):
        raise ValueError('Arms changed on resume')
    meta = json.loads((folder / 'prefix.json').read_text())
    if digest(folder / 'prefix.npz') != meta['sha256']:
        raise ValueError('Changed prefix')
    for arm in ARMS:
        path = folder / (arm + '.json')
        row = json.loads(path.read_text())
        if row['rollout_seed'] != job['rollout_seed'] or row['prefix_sha256'] != meta['sha256']:
            raise ValueError('Changed branch identity')
        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
            if digest(path.with_suffix(ext)) != row[key]:
                raise ValueError('Changed branch artifact')
    return True


def run(cfg):
    try:
        from scripts.run_libero_experiment_campaign import gpu_is_free
    except ModuleNotFoundError:
        from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    budget_path = DIRECTORY / 'budget.json'
    if not budget_path.exists():
        atomic_json(budget_path, dict(start_epoch=time.time(),
            deadline_epoch=min(time.time() + cfg['hours'] * 3600, cfg['hard_deadline_epoch'])))
    budget = json.loads(budget_path.read_text())
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    mutex = threading.RLock()
    occupied = set()
    state = dict(status='running', stage='smoke', pid=os.getpid(), active={},
                 deadline_epoch=budget['deadline_epoch'], holdout_started=False)
    def publish(**values):
        with mutex:
            state.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            state['completed_branches'] = {p: sum(f.stem in ARMS for f in (DIRECTORY / p).glob('*/*.json'))
                                           for p in ('smoke', 'screen')}
            n = sum(state['completed_branches'].values())
            state['seconds_until_deadline'] = max(0, int(budget['deadline_epoch'] - time.time()))
            if n:
                rate = n / max(1, time.time() - budget['start_epoch'])
                state['eta_remaining_seconds'] = int(max(0, len(cfg['jobs']) * len(ARMS) - n) / rate)
            atomic_json(DIRECTORY / 'sequence_status.json', state)
    def acquire():
        for gpu in cfg['gpu_candidates']:
            with mutex:
                if gpu in occupied:
                    continue
                occupied.add(gpu)
            path = ROOT / '.runtime/grounded_gpu_claims'
            path.mkdir(parents=True, exist_ok=True)
            handle = (path / (gpu + '.lock')).open('a')
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
    try:
        validate(cfg)
        publish()
        for phase in ('smoke', 'screen'):
            jobs = [j for j in cfg['jobs'] if j['phase'] == phase]
            pending = [j for j in jobs if not done(j)]
            attempts = {}
            publish(stage=phase, expected_current_branches=len(jobs) * len(ARMS))
            def worker():
                while not stop.is_set() and time.time() < budget['deadline_epoch']:
                    with mutex:
                        if not pending:
                            return
                    gpu, handle = acquire()
                    if gpu is None:
                        publish(waiting_for_idle_gpu=True)
                        stop.wait(15)
                        continue
                    try:
                        with mutex:
                            if not pending:
                                return
                            selected = [j for j in pending if j['position_level'] == pending[0]['position_level']][:cfg['batch_size']]
                            for j in selected:
                                pending.remove(j)
                        validate(cfg)
                        batch = DIRECTORY / 'batches' / f'{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(batch, dict(campaign=str(DIRECTORY), jobs=selected, deadline_epoch=budget['deadline_epoch']))
                        level = selected[0]['position_level']
                        variant = ROOT / '.runtime/libero_pro_position' / level
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=cfg['runtime'], HF_HUB_OFFLINE='1',
                            WANDB_MODE='offline', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0', LIBERO_BDDL_FILES_PATH=str(variant / 'bddl_files'),
                            LIBERO_INIT_STATES_PATH=str(variant / 'init_files'), LIBERO_CONFIG_PATH=str(DIRECTORY / 'configs' / batch.stem))
                        # Assets are already prepared and hash-checked; do not rewrite the full NFS volume.
                        command = ['bash', '-ec', 'source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                            'observation', str(ROOT / 'scripts/cosmos_env_libero_pro.sh'),
                            str(ROOT / 'scripts/collect_observation_contract.py'), str(batch)]
                        with batch.with_suffix('.log').open('a') as log:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                            with mutex:
                                state['active'][gpu] = dict(pid=process.pid, jobs=[j['id'] for j in selected], log=str(batch.with_suffix('.log')))
                            publish(waiting_for_idle_gpu=False)
                            terminated = None
                            while process.poll() is None:
                                if (stop.is_set() or time.time() > budget['deadline_epoch']) and terminated is None:
                                    process.terminate()
                                    terminated = time.time()
                                if terminated is not None and time.time() - terminated > 120:
                                    process.kill()
                                    process.wait()
                                time.sleep(5)
                                publish()
                        if process.returncode and not stop.is_set() and time.time() < budget['deadline_epoch']:
                            with mutex:
                                for job in selected:
                                    attempts[job['id']] = attempts.get(job['id'], 0) + 1
                                    if attempts[job['id']] > 1:
                                        raise RuntimeError('Worker failed twice: ' + str(batch))
                                    pending.append(job)
                                state.setdefault('retry_logs', []).append(str(batch.with_suffix('.log')))
                    except BaseException:
                        stop.set()
                        raise
                    finally:
                        handle.close()
                        with mutex:
                            occupied.discard(gpu)
                            state['active'].pop(gpu, None)
                        publish()
            with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
                futures = [pool.submit(worker) for _ in range(cfg['max_workers'])]
                for future in futures:
                    future.result()
            if not all(done(j) for j in jobs):
                publish(status='partial')
                return
            subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_observation_contract.py'),
                            '--campaign', str(DIRECTORY), '--phase', phase], cwd=ROOT, check=True)
        publish(status='completed')
    except BaseException as error:
        publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    for arg in ('prepare', 'launch', 'execute', 'status'):
        group.add_argument('--' + arg, action='store_true')
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if args.status:
        for name in ('sequence_status.json', 'analysis/smoke/summary.json', 'analysis/screen/summary.json'):
            path = DIRECTORY / name
            if path.exists():
                print(path.read_text())
        return
    cfg = prepare()
    if not (args.launch or args.execute):
        print('Prepared: 24 replay smoke + 1536 development branches; two suffix seeds, oracle arms separate; no holdout')
        return
    if ROOT != REMOTE:
        raise ValueError('GPU execution only in canonical server workspace')
    validate(cfg)
    if args.execute:
        run(cfg)
        return
    with (DIRECTORY / 'sequence.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Already active')
            return
    with (DIRECTORY / 'launcher.log').open('a') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute'], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    launch = dict(pid=process.pid, config_sha256=digest(DIRECTORY / 'config.json'), started_at=datetime.now(timezone.utc).isoformat())
    atomic_json(DIRECTORY / 'launch.json', launch)
    print(json.dumps(launch))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Frozen full-rollout transfer queue; waits for the existing campaign to drain."""
from __future__ import annotations

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

from decoder_token_medoid import NAME, ARMS, UPSTREAM, make_jobs
from p5_repeat_feedback import atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY = ROOT / 'experiments/campaigns' / NAME
FILES = ('decoder_token_medoid.py', 'collect_decoder_token_medoid.py',
         'run_decoder_token_medoid.py', 'analyze_decoder_token_medoid.py')


def asset_root(job):
    if job['factor'] == 'Position':
        return Path('.runtime/libero_pro_position') / job['level']
    if job['factor'] == 'Environment':
        return Path('.runtime/trajectory_consensus_20260908_environment')
    return Path('LIBERO-PRO/libero/libero')


def prepare():
    parent = ROOT / 'experiments/campaigns/observation_contract_20260911/config.json'
    old = json.loads(parent.read_text())
    jobs = make_jobs()
    assets = {}
    for suite, base in {(j['suite'], asset_root(j)) for j in jobs}:
        for kind in ('bddl_files', 'init_files'):
            files = sorted((ROOT / base / kind / suite).glob('*'))
            files = [p for p in files if p.is_file()]
            if len(files) != 10:
                raise ValueError(f'Expected ten assets: {base}/{kind}/{suite}')
            for path in files:
                assets[str(path.relative_to(ROOT))] = digest(path)
    runtime_hashes = dict(old['runtime_hashes'])
    for name in ('_src/predict2/networks/minimal_v4_dit.py', '_src/predict2/networks/minimal_v1_lvg_dit.py',
                 'models/policy_video2world_model.py', 'conditioner.py',
                 'experiments/robot/libero/consensus_medoid.py'):
        runtime_hashes[str(Path(old['runtime']) / 'cosmos_policy' / name)] = digest(ROOT / 'cosmos-policy/cosmos_policy' / name)
    external = ROOT / '.external/Robotics_project_YSDA'
    commit = subprocess.check_output(['git', '-C', str(external), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != UPSTREAM:
        raise ValueError('Upstream revision changed')
    references = {}
    paths = [external / p for p in ('LICENSE', 'docs/RESULTS.md',
        'scripts/eval/groot_n17_decoder_action_token_medoid_server.py', 'eval/libero/run.py')]
    paths += sorted((external / 'eval_outputs/simpler_bridge').glob('**/summary.json'))
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        relative = path.relative_to(external)
        target = DIRECTORY / 'reference' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) != digest(path):
            raise ValueError('Archived reference changed')
        if not target.exists():
            shutil.copy2(path, target)
        references[str(relative)] = digest(target)
    cfg = dict(name=NAME, arms=ARMS, jobs=jobs, upstream_commit=commit,
        upstream_repo='https://github.com/Doub1e05/Robotics_project_YSDA', references=references,
        scripts=dict(old['scripts'], **{n: digest(ROOT / 'scripts' / n) for n in FILES}),
        runtime=old['runtime'], runtime_hashes=runtime_hashes, assets=assets,
        gpu_candidates=list('12345670'), max_workers=7, batch_size=3,
        dependency='observation_contract_20260911', max_run_hours_after_first_admission=24,
        K=3, generated_horizon=16, executed_horizon=16, max_steps=280, settle_steps=10,
        denoising_steps=5, prediction_mode='parallel', fixed_seeds_each_query=True,
        primary='decoder_medoid', early_action_count=4, early_weight=4.,
        action_medoid=dict(horizon=5, discount=.9, xyz=1., rotation=.5, gripper=.25),
        automatic_hyperparameter_search=False, automatic_holdout=False,
        scientific_scope='development_transfer_180_paired_configs_720_full_rollouts_not_full_standard_benchmark',
        source_architecture='GR00T_N1.7_final_DiT_action_tokens',
        transfer_architecture='Cosmos_2B_action_slice_final_block_with_decoder_incidence_weighting')
    cfg = json.loads(json.dumps(cfg))
    path = DIRECTORY / 'config.json'
    if path.exists() and json.loads(path.read_text()) != cfg:
        raise ValueError('Refusing to change frozen configuration')
    atomic_json(path, cfg)
    return cfg


def validate(cfg):
    for name, sha in cfg['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Changed script: ' + name)
    for name, sha in cfg['assets'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Changed benchmark asset: ' + name)
    for name, sha in cfg['runtime_hashes'].items():
        if digest(name) != sha:
            raise ValueError('Changed frozen Cosmos runtime: ' + name)
    for name, sha in cfg['references'].items():
        if digest(DIRECTORY / 'reference' / name) != sha:
            raise ValueError('Changed reference: ' + name)


def done(job):
    folder = DIRECTORY / job['phase'] / job['id']
    if not (folder / 'completed.json').exists():
        return False
    if job['phase'] == 'smoke':
        audit = json.loads((folder / 'hook_audit.json').read_text())
        return audit['passed'] and digest(folder / 'hook_features.npz') == audit['feature_sha256']
    from collect_decoder_token_medoid import committed
    for arm in ARMS:
        path = folder / (arm + '.json')
        if not committed(path):
            return False
        row = json.loads(path.read_text())
        if any(row[key] != job[key] for key in ('id', 'candidate_seeds', 'env_seed', 'init_state_id')):
            raise ValueError('Resume identity mismatch')
    return True


def dependency_ready(state):
    if state.get('status') in ('failed', 'superseded'):
        raise RuntimeError('Previous campaign failed; inspect before starting new workloads')
    return state.get('status') in ('completed', 'partial') and not state.get('active')


def run(cfg):
    from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    mutex = threading.RLock()
    occupied = set()
    budget_path = DIRECTORY / 'budget.json'
    budget = json.loads(budget_path.read_text()) if budget_path.exists() else None
    state = dict(status='waiting_dependency', pid=os.getpid(), active={}, dependency=cfg['dependency'])
    def publish(**values):
        with mutex:
            state.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            state['completed_rollouts'] = sum(p.stem in ARMS for p in (DIRECTORY / 'screen').glob('*/*.json'))
            state['expected_rollouts'] = 720
            state['completed_smokes'] = len(list((DIRECTORY / 'smoke').glob('*/completed.json')))
            if budget:
                state['deadline_epoch'] = budget['deadline_epoch']
                state['seconds_until_deadline'] = max(0, int(budget['deadline_epoch'] - time.time()))
                n = state['completed_rollouts']
                state['eta_remaining_seconds'] = int((720 - n) * (time.time() - budget['start_epoch']) / n) if n else None
            atomic_json(DIRECTORY / 'sequence_status.json', state)
    def expired():
        return budget is not None and time.time() >= budget['deadline_epoch']
    def acquire():
        nonlocal budget
        for gpu in cfg['gpu_candidates']:
            with mutex:
                if gpu in occupied:
                    continue
                occupied.add(gpu)
            root = ROOT / '.runtime/grounded_gpu_claims'
            root.mkdir(parents=True, exist_ok=True)
            handle = (root / (gpu + '.lock')).open('a')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if gpu_is_free(gpu):
                    with mutex:
                        if budget is None:
                            budget = dict(start_epoch=time.time(),
                                deadline_epoch=time.time() + cfg['max_run_hours_after_first_admission'] * 3600)
                            atomic_json(budget_path, budget)
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
        dependency = ROOT / 'experiments/campaigns' / cfg['dependency'] / 'sequence_status.json'
        while not stop.is_set():
            previous = json.loads(dependency.read_text())
            if dependency_ready(previous):
                break
            publish(dependency_status=previous.get('status'), dependency_active=previous.get('active'))
            stop.wait(30)
        if stop.is_set():
            publish(status='paused')
            return
        for phase in ('smoke', 'screen'):
            jobs = [j for j in cfg['jobs'] if j['phase'] == phase]
            pending = [j for j in jobs if not done(j)]
            attempts = {}
            publish(status='running', stage=phase)
            def worker():
                while not stop.is_set() and not expired():
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
                            first = pending[0]
                            selected = [j for j in pending if (j['suite'], j['level']) == (first['suite'], first['level'])][:cfg['batch_size']]
                            for j in selected:
                                pending.remove(j)
                        validate(cfg)
                        batch = DIRECTORY / 'batches' / f'{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(batch, dict(campaign=str(DIRECTORY), jobs=selected, deadline_epoch=budget['deadline_epoch']))
                        base = ROOT / asset_root(first)
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=cfg['runtime'], HF_HUB_OFFLINE='1',
                            WANDB_MODE='offline', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0', LIBERO_BDDL_FILES_PATH=str(base / 'bddl_files'),
                            LIBERO_INIT_STATES_PATH=str(base / 'init_files'), LIBERO_CONFIG_PATH=str(DIRECTORY / 'configs' / batch.stem))
                        command = ['bash', '-ec', 'source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                            'decoder_medoid', str(ROOT / 'scripts/cosmos_env_libero_pro.sh'),
                            str(ROOT / 'scripts/collect_decoder_token_medoid.py'), str(batch)]
                        with batch.with_suffix('.log').open('a') as log:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                            with mutex:
                                state['active'][gpu] = dict(pid=process.pid, jobs=[j['id'] for j in selected], log=str(batch.with_suffix('.log')))
                            publish(waiting_for_idle_gpu=False)
                            terminated = None
                            while process.poll() is None:
                                if (stop.is_set() or expired()) and terminated is None:
                                    process.terminate()
                                    terminated = time.time()
                                if terminated is not None and time.time() - terminated > 120:
                                    process.kill()
                                    process.wait()
                                stop.wait(5) if not stop.is_set() else time.sleep(1)
                                publish()
                        incomplete = [j for j in selected if not done(j)]
                        if incomplete and not stop.is_set() and not expired():
                            with mutex:
                                for job in incomplete:
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
                if phase == 'screen':
                    subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_decoder_token_medoid.py'),
                                    '--campaign', str(DIRECTORY)], check=True)
                return
            if phase == 'screen':
                subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_decoder_token_medoid.py'),
                                '--campaign', str(DIRECTORY)], check=True)
        publish(status='completed')
    except BaseException as error:
        publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for arg in ('prepare', 'launch', 'execute', 'status', 'validate'):
        group.add_argument('--' + arg, action='store_true')
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        cfg = prepare()
        print(f'Frozen {len(cfg["jobs"])} jobs: three parity smokes + 720 full rollouts')
        return
    if args.status:
        path = DIRECTORY / 'sequence_status.json'
        print(path.read_text() if path.exists() else 'Prepared but not launched')
        return
    cfg = json.loads((DIRECTORY / 'config.json').read_text())
    if ROOT != REMOTE:
        raise ValueError('Queue execution only in canonical server workspace')
    validate(cfg)
    if args.validate:
        print('Frozen scripts, runtime, assets and upstream evidence verified')
        return
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
    launch = dict(pid=process.pid, config_sha256=digest(DIRECTORY / 'config.json'),
                  launched_at=datetime.now(timezone.utc).isoformat())
    atomic_json(DIRECTORY / 'launch.json', launch)
    print(json.dumps(launch))


if __name__ == '__main__':
    main()

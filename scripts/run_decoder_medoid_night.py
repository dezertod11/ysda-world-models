#!/usr/bin/env python3
"""Deadline-bounded, idle-only queue; the original scientific config is immutable."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import run_decoder_token_medoid as base
from decoder_medoid_night import (BASE_CONFIG_SHA256, DEADLINE, PLAN_FILE, STAGES, STAGE_ARMS,
                                  admissible_batch, deadline_times, ordered_jobs)
from p5_repeat_feedback import atomic_json, digest

ROOT, DIRECTORY = base.ROOT, base.DIRECTORY
FILES = ('decoder_medoid_night.py', 'collect_decoder_medoid_extensions.py',
         'run_decoder_medoid_night.py', 'analyze_decoder_medoid_night.py')


def prepare():
    if digest(DIRECTORY / 'config.json') != BASE_CONFIG_SHA256:
        raise ValueError('Original scientific config changed')
    cfg = json.loads((DIRECTORY / 'config.json').read_text())
    plan = dict(version=1, base_config_sha256=BASE_CONFIG_SHA256, deadline_moscow=DEADLINE,
        **deadline_times(), gpu_candidates=list('01234567'), max_workers=8, max_batch_size=3,
        idle_only=True, no_gpu_sharing=True, dependency=cfg['dependency'],
        scripts={name: digest(ROOT / 'scripts' / name) for name in FILES},
        jobs=ordered_jobs(cfg['jobs']), priorities=list(STAGES),
        expected_rollouts=dict(screen=720, seed_controls=360, horizon8=360),
        admission='Whole paired groups; conservative p95 duration x 1.5, stage floor, 180s save/bootstrap reserve.',
        extensions='Fixed second/third candidate K1; generated H16 executed H8 max-value/full-medoid/prefix-medoid.',
        no_result_based_selection=True, full_completion_not_guaranteed=True)
    path = DIRECTORY / PLAN_FILE
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError('Refusing to rewrite frozen night plan')
    atomic_json(path, plan)
    print(json.dumps({k: plan[k] for k in ('deadline_moscow', 'expected_rollouts', 'compute_deadline_epoch')}))


def validate(plan, cfg):
    if digest(DIRECTORY / 'config.json') != plan['base_config_sha256']:
        raise ValueError('Base config changed')
    for name, sha in plan['scripts'].items():
        if digest(ROOT / 'scripts' / name) != sha:
            raise ValueError('Night script changed: ' + name)
    base.validate(cfg)


def process_start(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def signal_owned(record, sig, *, group=False):
    if process_start(record['pid']) != record['start_ticks']:
        return False
    try:
        if group:
            if os.getpgid(record['pid']) != record['pid']:
                raise ValueError('Worker is not its own process-group leader')
            os.killpg(record['pid'], sig)
        else:
            os.kill(record['pid'], sig)
        return True
    except ProcessLookupError:
        return False


def watchdog(plan, supervisor):
    sent_term, sent_kill, supervisor_term = set(), set(), None
    while process_start(supervisor['pid']) == supervisor['start_ticks']:
        now = time.time()
        path = DIRECTORY / 'night_process_registry.json'
        if path.exists():
            registry = json.loads(path.read_text())
            if registry['supervisor'] == supervisor:
                for record in registry['workers'].values():
                    key = (record['pid'], record['start_ticks'])
                    if now >= plan['compute_deadline_epoch'] and key not in sent_term:
                        signal_owned(record, signal.SIGTERM, group=True)
                        sent_term.add(key)
                    if now >= plan['kill_deadline_epoch'] and key not in sent_kill:
                        signal_owned(record, signal.SIGKILL, group=True)
                        sent_kill.add(key)
        if now >= plan['deadline_epoch'] - 60 and supervisor_term is None:
            signal_owned(supervisor, signal.SIGTERM)
            supervisor_term = now
        if supervisor_term and now - supervisor_term >= 15:
            signal_owned(supervisor, signal.SIGKILL)
            atomic_json(DIRECTORY / 'night_watchdog_stop.json', dict(
                time=datetime.now(timezone.utc).isoformat(), reason='Supervisor exceeded reporting deadline'))
            return
        time.sleep(5)


def job_done(job):
    if job['phase'] in ('smoke', 'screen'):
        return base.done(job)
    from collect_decoder_token_medoid import committed
    folder = DIRECTORY / job['phase'] / job['id']
    if not (folder / 'completed.json').exists():
        return False
    parent = DIRECTORY / job['parent_phase'] / job['id']
    start = json.loads((parent / 'start.json').read_text())
    pool = json.loads((parent / 'q0_pool.json').read_text())
    for arm in STAGE_ARMS[job['phase']]:
        path = folder / (arm + '.json')
        if not committed(path):
            return False
        row = json.loads(path.read_text())
        if any(row[k] != job[k] for k in ('id', 'candidate_seeds', 'env_seed', 'init_state_id', 'phase')):
            raise ValueError('Extension resume identity mismatch')
        if row['initial_sha256'] != start['sha256'] or row['q0_pool_sha256'] != pool['sha256']:
            raise ValueError('Extension no longer matches its parent')
    return True


def run(plan, cfg):
    from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY / 'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    supervisor = dict(pid=os.getpid(), start_ticks=process_start(os.getpid()))
    active, verified, attempts, durations = {}, set(), {}, {s: [] for s in STAGES}
    state = dict(status='waiting_dependency', pid=os.getpid(), active={}, dependency=cfg['dependency'],
        night_plan=PLAN_FILE, deadline_epoch=plan['deadline_epoch'], compute_deadline_epoch=plan['compute_deadline_epoch'],
        expected_rollouts=1440, stage_expected_rollouts=plan['expected_rollouts'])
    def completed(job):
        key = (job['phase'], job['id'])
        if key not in verified and job_done(job):
            verified.add(key)
        return key in verified
    def publish(**values):
        state.update(values, updated_at=datetime.now(timezone.utc).isoformat())
        state['active'] = {gpu: {k: row[k] for k in ('pid', 'start_ticks', 'jobs', 'log', 'stage')}
                           for gpu, row in active.items()}
        counts = {stage: sum(p.stem in STAGE_ARMS[stage] for p in (DIRECTORY / stage).glob('*/*.json'))
                  for stage in STAGES if stage != 'smoke'}
        state.update(stage_completed_rollouts=counts, completed_rollouts=sum(counts.values()),
            completed_smokes=len(list((DIRECTORY / 'smoke').glob('*/completed.json'))),
            seconds_until_deadline=max(0, int(plan['deadline_epoch'] - time.time())),
            seconds_until_compute_cutoff=max(0, int(plan['compute_deadline_epoch'] - time.time())))
        atomic_json(DIRECTORY / 'night_process_registry.json', dict(supervisor=supervisor, workers=state['active']))
        atomic_json(DIRECTORY / 'sequence_status.json', state)
    def expired():
        return time.time() >= plan['compute_deadline_epoch']
    def sleep(seconds):
        until = time.monotonic() + seconds
        while not stopped and time.monotonic() < until:
            time.sleep(min(1, max(0, until - time.monotonic())))
    def stop_workers():
        for row in active.values():
            if row['process'].poll() is None:
                signal_owned(row, signal.SIGTERM, group=True)
        limit = time.monotonic() + 120
        for row in active.values():
            process = row['process']
            try:
                process.wait(timeout=max(0, limit - time.monotonic()))
            except subprocess.TimeoutExpired:
                signal_owned(row, signal.SIGKILL, group=True)
                process.wait(timeout=15)
            row['handle'].close()
        active.clear()
        publish()
    publish()
    with (DIRECTORY / 'night_watchdog.log').open('a') as log:
        guard = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--watchdog',
            '--supervisor-pid', str(supervisor['pid']), '--supervisor-start', supervisor['start_ticks']],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    atomic_json(DIRECTORY / 'night_budget.json', dict(**deadline_times(), started_at=time.time(), watchdog_pid=guard.pid))
    failure = None
    try:
        validate(plan, cfg)
        dependency = ROOT / 'experiments/campaigns' / cfg['dependency'] / 'sequence_status.json'
        while not stopped and not expired():
            previous = json.loads(dependency.read_text())
            if base.dependency_ready(previous):
                break
            publish(dependency_status=previous.get('status'), dependency_active=previous.get('active'))
            sleep(20)
        for stage in STAGES:
            if stopped or expired():
                break
            jobs = [j for j in plan['jobs'] if j['phase'] == stage]
            pending = [j for j in jobs if not completed(j)]
            publish(status='running', stage=stage)
            while (pending or active) and not stopped and not expired():
                for gpu, row in list(active.items()):
                    if row['process'].poll() is None:
                        continue
                    missing = [j for j in row['selected'] if not completed(j)]
                    elapsed = time.monotonic() - row['started']
                    if not missing:
                        durations[stage].append(elapsed / len(row['selected']))
                    row['handle'].close()
                    del active[gpu]
                    if missing:
                        for job in missing:
                            key = (stage, job['id'])
                            attempts[key] = attempts.get(key, 0) + 1
                            if attempts[key] >= 2:
                                raise RuntimeError('Worker failed twice; inspect ' + row['log'])
                        pending = missing + pending
                        state.setdefault('retry_logs', []).append(row['log'])
                if not pending:
                    publish()
                    sleep(5)
                    continue
                if not admissible_batch(stage, plan['compute_deadline_epoch'] - time.time(), len(pending), durations[stage]):
                    publish(admission_closed=True, reason='Insufficient conservative time for another paired group')
                    if not active:
                        break
                    sleep(5)
                    continue
                for gpu in plan['gpu_candidates']:
                    if not pending or stopped or expired() or len(active) >= plan['max_workers']:
                        break
                    if gpu in active:
                        continue
                    claim = ROOT / '.runtime/grounded_gpu_claims' / (gpu + '.lock')
                    claim.parent.mkdir(parents=True, exist_ok=True)
                    handle = claim.open('a')
                    handed_off = False
                    try:
                        try:
                            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            continue
                        if not gpu_is_free(gpu):
                            continue
                        first = pending[0]
                        same = [j for j in pending if (j['suite'], j['level']) == (first['suite'], first['level'])]
                        size = admissible_batch(stage, plan['compute_deadline_epoch'] - time.time(), len(same), durations[stage])
                        if not size or stopped or expired():
                            break
                        selected = same[:size]
                        validate(plan, cfg)
                        batch = DIRECTORY / 'night_batches' / f'{time.time_ns()}_gpu{gpu}.json'
                        atomic_json(batch, dict(campaign=str(DIRECTORY), jobs=selected, deadline_epoch=plan['compute_deadline_epoch'],
                                               night_plan_sha256=digest(DIRECTORY / PLAN_FILE)))
                        assets = ROOT / base.asset_root(first)
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, COSMOS_REPO=cfg['runtime'], HF_HUB_OFFLINE='1',
                            WANDB_MODE='offline', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', PYTHONUNBUFFERED='1',
                            MLSPACE_ALLOW_GPU0='1' if gpu == '0' else '0', LIBERO_BDDL_FILES_PATH=str(assets / 'bddl_files'),
                            LIBERO_INIT_STATES_PATH=str(assets / 'init_files'), LIBERO_CONFIG_PATH=str(DIRECTORY / 'configs' / batch.stem))
                        collector = 'collect_decoder_token_medoid.py' if stage in ('smoke', 'screen') else 'collect_decoder_medoid_extensions.py'
                        command = ['bash', '-ec', 'source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                            'decoder_night', str(ROOT / 'scripts/cosmos_env_libero_pro.sh'), str(ROOT / 'scripts' / collector), str(batch)]
                        with batch.with_suffix('.log').open('a') as log:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)
                        active[gpu] = dict(pid=process.pid, start_ticks=process_start(process.pid), process=process, handle=handle,
                            jobs=[j['id'] for j in selected], selected=selected, stage=stage, log=str(batch.with_suffix('.log')),
                            started=time.monotonic())
                        handed_off = True
                        for j in selected:
                            pending.remove(j)
                        publish(waiting_for_idle_gpu=False)
                    finally:
                        if not handed_off:
                            handle.close()
                publish(waiting_for_idle_gpu=bool(pending) and not active)
                sleep(5 if active else 15)
            if active:
                stop_workers()
            if not all(completed(j) for j in jobs):
                break
        complete = all(completed(j) for j in plan['jobs'])
        state['calculation_status'] = 'completed' if complete else ('paused' if stopped else 'partial')
    except BaseException as error:
        failure = repr(error)
        state.update(calculation_status='failed', error=failure)
    finally:
        stop_workers()
    publish(status='analyzing')
    for script in ('analyze_decoder_token_medoid.py', 'analyze_decoder_medoid_night.py'):
        allowance = min(600, plan['report_deadline_epoch'] - time.time())
        if allowance <= 0:
            state.setdefault('analysis_errors', []).append('Reporting deadline reached before ' + script)
            break
        try:
            with (DIRECTORY / 'night_analysis.log').open('a') as log:
                subprocess.run([sys.executable, str(ROOT / 'scripts' / script), '--campaign', str(DIRECTORY)],
                    cwd=ROOT, stdout=log, stderr=log, check=True, timeout=allowance)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            state.setdefault('analysis_errors', []).append(repr(error))
    publish(status=state['calculation_status'], finished_at=datetime.now(timezone.utc).isoformat(),
            reports_complete=not state.get('analysis_errors'))
    atomic_json(DIRECTORY / 'night_finished.json', state)
    guard.terminate()
    guard.wait(timeout=15)
    if failure:
        raise RuntimeError(failure)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for option in ('prepare', 'validate', 'launch', 'execute', 'watchdog', 'status'):
        group.add_argument('--' + option, action='store_true')
    parser.add_argument('--supervisor-pid', type=int)
    parser.add_argument('--supervisor-start')
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return
    if args.status:
        print((DIRECTORY / 'sequence_status.json').read_text())
        return
    plan = json.loads((DIRECTORY / PLAN_FILE).read_text())
    if args.watchdog:
        watchdog(plan, dict(pid=args.supervisor_pid, start_ticks=args.supervisor_start))
        return
    if ROOT != base.REMOTE:
        raise ValueError('Queue execution only in canonical server workspace')
    cfg = json.loads((DIRECTORY / 'config.json').read_text())
    validate(plan, cfg)
    if args.validate:
        print('Base and night plan verified; deadline ' + plan['deadline_moscow'])
    elif args.execute:
        run(plan, cfg)
    else:
        if time.time() >= plan['compute_deadline_epoch']:
            raise ValueError('Compute deadline already passed; never silently extend it')
        with (DIRECTORY / 'sequence.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (DIRECTORY / 'night_launcher.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--execute'], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        launch = dict(pid=process.pid, plan_sha256=digest(DIRECTORY / PLAN_FILE),
            base_config_sha256=digest(DIRECTORY / 'config.json'), deadline_moscow=DEADLINE,
            launched_at=datetime.now(timezone.utc).isoformat())
        atomic_json(DIRECTORY / 'night_launch.json', launch)
        print(json.dumps(launch))


if __name__ == '__main__':
    main()

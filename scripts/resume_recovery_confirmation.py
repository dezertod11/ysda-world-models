#!/usr/bin/env python3
"""Explicit resource-only restart of a frozen, interrupted recovery campaign."""
import argparse
from datetime import datetime, timezone
import errno
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

try:
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from p5_repeat_feedback import atomic_json, digest


def resource_config(config, amendment):
    if amendment['hours'] <= 0 or not math.isfinite(amendment['hours']):
        raise ValueError('Positive finite resource window required')
    if not 1 <= amendment['max_workers'] <= 8:
        raise ValueError('Invalid worker cap')
    result = dict(config)
    result['max_workers'] = amendment['max_workers']
    return result


def assert_previous_processes_stopped(directory):
    path = directory / 'sequence_status.json'
    if not path.exists():
        return
    status = json.loads(path.read_text())
    pids = [status.get('pid')] + [x.get('pid') for x in status.get('active', {}).values()]
    for pid in pids:
        if pid and Path(f'/proc/{pid}').exists():
            stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if stat[0] == 'Z':
                continue
            raise RuntimeError(f'Previous PID {pid} still exists; inspect before resuming')


def retry_atomic_json(path, value):
    for attempt in range(4):
        try:
            return atomic_json(path, value)
        except OSError as error:
            if error.errno != errno.ENOSPC or attempt == 3:
                raise
            print(f'Transient NFS ENOSPC writing {path}; retry {attempt + 1}/3', flush=True)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--launch', action='store_true')
    group.add_argument('--execute', type=Path)
    parser.add_argument('--hours', type=float, default=9.)
    parser.add_argument('--max-workers', type=int, default=5)
    parser.add_argument('--reuse-budget', action='store_true', help='Retry without extending the existing deadline')
    args = parser.parse_args()
    import run_recovery_confirmation as frozen
    if frozen.ROOT != frozen.REMOTE:
        raise ValueError('Canonical server only')
    directory = frozen.DIRECTORY
    config_path = directory / 'config.json'
    config = json.loads(config_path.read_text())
    if args.execute:
        amendment = json.loads(args.execute.read_text())
        if digest(config_path) != amendment['config_sha256']:
            raise ValueError('Scientific configuration changed')
        if digest(Path(__file__)) != amendment['resume_script_sha256']:
            raise ValueError('Resume implementation changed')
        if json.loads((directory / 'budget.json').read_text()) != amendment['new_budget']:
            raise ValueError('Resource budget changed after launch')
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        print('Resource-only resume; frozen scientific config unchanged', flush=True)
        frozen.atomic_json = retry_atomic_json
        frozen.execute(resource_config(config, amendment))
        return
    settings = dict(hours=args.hours, max_workers=args.max_workers)
    resource_config(config, settings)
    with (directory / 'resource_resume.lock').open('a') as launch_lock:
        fcntl.flock(launch_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (directory / 'sequence.lock').open('a') as sequence_lock:
            fcntl.flock(sequence_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert_previous_processes_stopped(directory)
            frozen.validate(config)
            now = time.time()
            stamp = datetime.fromtimestamp(now, timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            archive = directory / 'resource_resumes' / stamp
            archive.mkdir(parents=True, exist_ok=False)
            for name in ('budget.json', 'sequence_status.json', 'launch.json'):
                path = directory / name
                if path.exists():
                    atomic_json(archive / name, json.loads(path.read_text()))
            budget = (json.loads((archive / 'budget.json').read_text()) if args.reuse_budget else
                      dict(start_epoch=now, deadline_epoch=now + args.hours * 3600))
            if budget['deadline_epoch'] <= now:
                raise ValueError('Existing budget expired')
            amendment = dict(**settings, created_at=datetime.now(timezone.utc).isoformat(),
                reason='Explicit user request to finish frozen main and timing; no scientific changes',
                config_sha256=digest(config_path), resume_script_sha256=digest(Path(__file__)),
                new_budget=budget, previous_budget=json.loads((archive / 'budget.json').read_text()),
                phase_order=config['phase_order'], gpu_candidates=config['gpu_candidates'],
                idle_only=True, repeat_completed=False, automatic_fit=False, automatic_holdout=False,
                dispatcher_status_io='bounded 3x5s retry on transient NFS ENOSPC; collector unchanged',
                reused_deadline=bool(args.reuse_budget))
            amendment_path = archive / 'amendment.json'
            atomic_json(amendment_path, amendment)
            atomic_json(directory / 'budget.json', budget)
        with (archive / 'launcher.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                '--execute', str(amendment_path)], cwd=frozen.ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True,
                env=dict(os.environ, PYTHONUNBUFFERED='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
        launch = dict(pid=process.pid, amendment=str(amendment_path),
            log=str(archive / 'launcher.log'), deadline_epoch=budget['deadline_epoch'],
            started_at=datetime.now(timezone.utc).isoformat(), config_sha256=amendment['config_sha256'])
        atomic_json(archive / 'launch.json', launch)
        atomic_json(directory / 'resume_launch.json', launch)
        print(json.dumps(launch, indent=2))


if __name__ == '__main__':
    main()

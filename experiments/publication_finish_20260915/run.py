#!/usr/bin/env python3
"""Deadline-bound, opt-in scoped recovery replication using snapshot v2."""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_recovery_confirmation as legacy
from recovery_confirmation import expected_arms
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json

PARENT = ROOT / 'experiments/campaigns/recovery_confirmation_20260913'
CAMPAIGN = ROOT / 'experiments/campaigns/recovery_scoped_runtime_v2_20260915'
SMOKE = ROOT / 'experiments/campaigns/recovery_scoped_runtime_v2_20260915_smoke'
V2 = ROOT / 'experiments/runtime_replay_v2'
DEADLINE = '2026-09-16T07:50:00+03:00'


def deadline_epoch(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.timestamp() <= time.time():
        raise ValueError('A future timezone-aware deadline is required')
    return parsed.timestamp()


def make_config(source, name, files, smoke=False):
    cfg = copy.deepcopy(source)
    cfg['jobs'] = [j for j in cfg['jobs'] if j['phase'] != 'smoke']
    if smoke:
        cfg['jobs'] = [next(j for j in cfg['jobs'] if j['phase'] == 'main'
                           and j['cohort'] == cohort) for cohort in ('replication', 'transfer')]
    cfg.update(name=name, runtime_snapshot_version=2, versioned_files=files,
               parent_config_sha256=digest(PARENT / 'config.json'),
               gpu_candidates=list('01234567'), max_workers=8,
               phase_order=['main'] if smoke else ['main', 'timing'], hours=0,
               technical_only=smoke, automatic_fit=False, automatic_holdout=False,
               sampling_scope='Fresh snapshot-v2 collection on the unchanged historical init25-32 support; '
                              'technical validation only' if smoke else
                              'Corrected-runtime replication on unchanged historical init25-32 support; '
                              'not unseen task generalization',
               deadline_policy='Explicit shared deadline; no automatic extension or outcome-driven promotion')
    return cfg


def validate(config):
    if config.get('runtime_snapshot_version') != 2:
        raise ValueError('Fresh snapshot-v2 campaign required')
    if config['parent_config_sha256'] != digest(PARENT / 'config.json'):
        raise ValueError('Historical configuration changed')
    for path, sha in config['versioned_files'].items():
        if digest(ROOT / path) != sha:
            raise ValueError('Versioned code changed: ' + path)
    legacy.validate(config)


def prepare():
    if ROOT != legacy.REMOTE:
        raise ValueError('Prepare on the canonical server only')
    source = json.loads((PARENT / 'config.json').read_text())
    files = {str(p.relative_to(ROOT)): digest(p)
             for p in [*HERE.glob('*.py'), V2 / 'runtime_snapshot.py']}
    stages = []
    for directory, smoke in ((SMOKE, True), (CAMPAIGN, False)):
        config = make_config(source, directory.name, files, smoke)
        validate(config)
        path = directory / 'config.json'
        if path.exists() and json.loads(path.read_text()) != config:
            raise ValueError('Refuse to overwrite a scientific config')
        if not path.exists():
            atomic_json(path, config)
        stages.append(dict(campaign=str(directory), config_sha256=digest(path),
                           branches=sum(len(expected_arms(j)) for j in config['jobs'])))
    atomic_json(HERE / 'prepared.json', dict(stages=stages, scientific_results='pending'))
    return stages


def redirect(command):
    replacements = {str(ROOT / 'scripts/collect_recovery_confirmation.py'): str(HERE / 'collect.py'),
                    str(ROOT / 'scripts/analyze_recovery_confirmation.py'): str(HERE / 'analyze.py')}
    return [replacements.get(x, x) if isinstance(x, str) else x for x in command]


class ProcessAdapter:
    def Popen(self, command, *args, **kwargs):
        return subprocess.Popen(redirect(command), *args, **kwargs)

    def run(self, command, *args, **kwargs):
        return subprocess.run(redirect(command), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(subprocess, name)


def status():
    result = {}
    for directory in (SMOKE, CAMPAIGN):
        path = directory / 'sequence_status.json'
        result[directory.name] = json.loads(path.read_text()) if path.exists() else {'status': 'not_started'}
    return result


def execute(deadline):
    if ROOT != legacy.REMOTE:
        raise ValueError('GPU execution is server-only')
    with (HERE / 'execution.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for directory in (SMOKE, CAMPAIGN):
            if time.time() >= deadline:
                break
            config = json.loads((directory / 'config.json').read_text())
            validate(config)
            path = directory / 'sequence_status.json'
            if path.exists() and json.loads(path.read_text()).get('status') == 'completed':
                continue
            budget = directory / 'budget.json'
            if budget.exists() and json.loads(budget.read_text())['deadline_epoch'] != deadline:
                raise ValueError('Cannot silently extend an existing budget')
            if not budget.exists():
                atomic_json(budget, dict(start_epoch=time.time(), deadline_epoch=deadline))
            legacy.DIRECTORY = directory
            legacy.subprocess = ProcessAdapter()
            legacy.atomic_json = atomic_json
            legacy.execute(config)
            if json.loads(path.read_text()).get('status') != 'completed':
                break
        atomic_json(HERE / 'last_status.json', status())


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    for option in ('prepare', 'launch', 'execute', 'status'):
        modes.add_argument('--' + option, action='store_true')
    parser.add_argument('--deadline', default=DEADLINE)
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(), indent=2)); return
    if args.prepare:
        print(json.dumps(prepare(), indent=2)); return
    deadline = deadline_epoch(args.deadline)
    if args.execute:
        execute(deadline); return
    if ROOT != legacy.REMOTE:
        raise ValueError('Launch on the canonical server only')
    with (HERE / 'launcher.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior = HERE / 'launch.json'
        if prior.exists():
            pid = json.loads(prior.read_text())['pid']
            cmdline = Path(f'/proc/{pid}/cmdline')
            if cmdline.exists() and str(HERE / 'run.py').encode() in cmdline.read_bytes():
                print('Already running: ' + str(pid)); return
        for directory in (SMOKE, CAMPAIGN):
            validate(json.loads((directory / 'config.json').read_text()))
        with (HERE / 'launcher.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(HERE / 'run.py'), '--execute',
                                        '--deadline', args.deadline], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        info = dict(pid=process.pid, launched_at=datetime.now(timezone.utc).isoformat(),
                    deadline_epoch=deadline, gpu_policy='idle-only 0-7; one worker per GPU',
                    branches=1288, submission_automatic=False)
        atomic_json(prior, info)
        print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()

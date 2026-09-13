#!/usr/bin/env python3
"""Guarded resource migration: parity gate, drain old children, resume same campaign."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

from libero_resident import atomic_json
from run_libero_resident_campaign import validate_parity

ROOT = Path(__file__).resolve().parents[1]
NIGHT = ROOT / "experiments/campaigns/consensus_p5_night_20260909"
REFERENCES = ROOT / "experiments/campaigns/consensus_references_20260909_valid199"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def process_table():
    rows = subprocess.check_output(["ps", "-eo", "pid=,ppid=,stat=,args="], text=True)
    return {int(parts[0]): (int(parts[1]), parts[2], parts[3])
            for line in rows.splitlines() if len(parts := line.split(None, 3)) == 4}


def descendants(table, parent):
    result = set()
    for _ in range(20):
        found = {pid for pid, (ppid, _, _) in table.items() if ppid == parent or ppid in result}
        if found == result:
            break
        result = found
    return result


def assert_owned(pid, needle):
    process = Path('/proc') / str(pid)
    cwd = str((process / 'cwd').resolve(strict=True))
    command = (process / 'cmdline').read_bytes().decode().replace('\0', ' ')
    if not cwd.startswith(str(ROOT) + '/') and cwd != str(ROOT):
        raise RuntimeError(f"Refusing to control PID {pid}: different project")
    if needle not in command:
        raise RuntimeError(f"Refusing to control PID {pid}: different command")


def start_night(gpus):
    command = [sys.executable, '-u', str(ROOT/'scripts/run_consensus_valid_support_night.py'),
               '--execute', '--gpus', gpus]
    with (NIGHT/'sequence.log').open('a') as log:
        child = subprocess.Popen(command, cwd=ROOT, env=os.environ.copy(), stdout=log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    return child


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parity-report', type=Path, required=True)
    parser.add_argument('--staged-launcher', type=Path, required=True)
    parser.add_argument('--gpus', default='0,1,2,3,4,5,6,7')
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    lock = (NIGHT/'resident_activation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = NIGHT/'resident_activation.json'
    def status(state, **extra):
        atomic_json(state_path, dict(status=state, updated_at=datetime.now(timezone.utc).isoformat(),
                                   pid=os.getpid(), **extra))
    while not args.parity_report.exists():
        if not args.wait:
            raise FileNotFoundError(args.parity_report)
        status('waiting_parity', report=str(args.parity_report))
        time.sleep(10)
    os.environ['COSMOS_REPO'] = str(REFERENCES/'source/cosmos-policy')
    try:
        validate_parity(args.parity_report, REFERENCES/'config.json')
    except BaseException as error:
        status('blocked_parity', error=repr(error))
        raise
    previous = json.loads((NIGHT/'sequence_status.json').read_text())
    if previous.get('stage') != 'reference_references':
        status('not_applied', reason='Reference stage is no longer active; later stages are untouched')
        return
    supervisor, runner = previous['pid'], previous['child_pid']
    assert_owned(supervisor, 'scripts/run_consensus_valid_support_night.py')
    assert_owned(runner, '--run-prefix consensus_references_20260909_valid199')
    source = ROOT/'scripts/run_consensus_valid_support_night.py'
    old_amendment = json.loads((NIGHT/'resource_amendment_gpu07.json').read_text())
    if sha(source) != old_amendment['script_changes']['run_consensus_valid_support_night.py']['new_sha256']:
        raise RuntimeError('Launcher changed independently; refusing to replace it')
    backup = NIGHT/'resource_resident_backup'
    backup.mkdir(exist_ok=True)
    if (backup/'launcher.py').exists():
        raise FileExistsError('Migration backup already exists; inspect the previous attempt')
    shutil.copy2(source, backup/'launcher.py')
    for original in [NIGHT/'sequence_status.json', REFERENCES/'manifest.json']:
        shutil.copy2(original, backup/original.name)
    manifest = json.loads((REFERENCES/'manifest.json').read_text())
    markers = {j['completion_marker']: sha(j['completion_marker']) for j in manifest['jobs']
               if Path(j['completion_marker']).is_file()}
    atomic_json(backup/'marker_sha256.json', markers)
    paused, terminated, installed = [], False, False
    amendment_path = NIGHT/'resource_amendment_resident.json'
    try:
        # Stop only dispatchers. Already-running collector/encoder children finish normally.
        for pid in (supervisor, runner):
            os.kill(pid, signal.SIGSTOP)
            paused.append(pid)
        deadline = time.monotonic()+1800
        while True:
            table = process_table()
            live = [pid for pid in descendants(table, runner) if not table[pid][1].startswith('Z')]
            if not live:
                break
            status('draining_legacy_jobs', old_supervisor=supervisor, old_runner=runner, child_pids=live)
            if time.monotonic() >= deadline:
                raise TimeoutError('Legacy jobs did not drain; dispatchers will be resumed')
            time.sleep(2)
        for pid in (runner, supervisor):
            os.kill(pid, signal.SIGTERM)
            os.kill(pid, signal.SIGCONT)
        paused.clear()
        terminated = True
        time.sleep(2)
        staged = args.staged_launcher
        temporary = source.with_suffix('.resident.tmp')
        shutil.copy2(staged, temporary)
        temporary.replace(source)
        installed = True
        adapters = ('libero_resident.py','libero_resident_worker.py',
                    'run_libero_resident_campaign.py','verify_libero_resident.py')
        amendment = dict(original_freeze_sha256=sha(NIGHT/'freeze.json'),
            previous_resource_amendment_sha256=sha(NIGHT/'resource_amendment_gpu07.json'),
            old_launcher_sha256=sha(backup/'launcher.py'), new_launcher_sha256=sha(source),
            adapter_sha256={name:sha(ROOT/'scripts'/name) for name in adapters},
            parity_report_relative=str(args.parity_report.relative_to(ROOT)),
            parity_report_sha256=sha(args.parity_report), method_configuration_changed=False,
            scope='references_only', gpu_policy='idle_only_no_compute_processes', batch_size=8,
            completed_markers_preserved=len(markers), created_at=datetime.now(timezone.utc).isoformat())
        atomic_json(amendment_path, amendment)
        subprocess.run([sys.executable,str(source)], cwd=ROOT,check=True)
        child=start_night(args.gpus)
        for _ in range(18):
            if child.poll() is not None:
                raise RuntimeError('New supervisor exited during startup')
            fresh=json.loads((NIGHT/'sequence_status.json').read_text())
            if fresh.get('pid')==child.pid and fresh.get('stage')=='reference_references' and fresh.get('child_pid'):
                command=(Path('/proc')/str(fresh['child_pid'])/'cmdline').read_bytes()
                if b'run_libero_resident_campaign.py' in command:
                    break
            time.sleep(5)
        else:
            status('started_unverified', new_supervisor=child.pid, completed_markers_preserved=len(markers))
            return
        if any(sha(path)!=digest for path,digest in markers.items()):
            raise RuntimeError('Pre-existing completion marker changed')
        status('active', new_supervisor=child.pid, new_runner=fresh['child_pid'],
               completed_markers_preserved=len(markers), parity_report=str(args.parity_report))
    except BaseException as error:
        for pid in paused:
            try: os.kill(pid,signal.SIGCONT)
            except ProcessLookupError: pass
        if installed:
            shutil.copy2(backup/'launcher.py',source)
            if amendment_path.exists(): amendment_path.unlink()
        if terminated:
            # Do not launch a duplicate if a newly started supervisor is still alive.
            current=json.loads((NIGHT/'sequence_status.json').read_text())
            pid=current.get('pid')
            if not pid or not (Path('/proc')/str(pid)).exists():
                start_night(args.gpus)
        status('rolled_back',error=repr(error))
        raise


if __name__=='__main__':
    main()

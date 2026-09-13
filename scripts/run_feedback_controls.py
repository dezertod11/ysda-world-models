#!/usr/bin/env python3
"""Serializable research queue, strict idle admission, bounded offline delivery."""
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
    from scripts.feedback_controls import NAME, ARMS, make_jobs, check_predecessor, job_done
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from feedback_controls import NAME, ARMS, make_jobs, check_predecessor, job_done
    from p5_repeat_feedback import atomic_json, digest

ROOT = Path(__file__).resolve().parents[1]
REMOTE = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY = ROOT/'experiments/campaigns'/NAME
PREDECESSOR = 'p5_candidate_replication_20260910'
NEW = ('feedback_controls.py', 'collect_feedback_controls.py', 'run_feedback_controls.py',
       'analyze_feedback_controls.py')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o',
       'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', 'mlspace-sr006']


def now():
    return datetime.now(timezone.utc).isoformat()


def prepare():
    source_path = ROOT/'experiments/campaigns/p5_repeat_feedback_20260910/config.json'
    source = json.loads(source_path.read_text())
    files = dict(source['scripts'])
    files.update({name: digest(ROOT/'scripts'/name) for name in
                  (*NEW, 'p5_candidate_replication.py', 'analyze_p5_candidate_replication.py')})
    for name, sha in files.items():
        if digest(ROOT/'scripts'/name) != sha:
            raise ValueError('Dependency changed: '+name)
    config = dict(name=NAME, predecessor=PREDECESSOR, source_config_sha256=digest(source_path),
        scripts=files, runtime=source['runtime'], runtime_hashes=source['runtime_hashes'],
        jobs=make_jobs(source), arms=list(ARMS), max_workers=3, batch_size=4,
        gpu_candidates=list('13502467'), active_hours=48, idle_only=True,
        primary_contrasts=[['fresh_k4','open16'],['fresh_k4','fresh_k1'],
                           ['fresh_continuity_k4','fresh_k4']],
        stage='mechanism_screen_not_confirmatory', automatic_holdout=False,
        screen_branches=120, smoke_branches=15, continuity_lambda=.10,
        smoke_min_complete_cells=3)
    path = DIRECTORY/'config.json'
    if path.exists():
        if json.loads(path.read_text()) != config:
            raise ValueError('Frozen config differs; use a new campaign version')
    else:
        atomic_json(path, config)
    return config


def validate(config):
    for name, sha in config['scripts'].items():
        if digest(ROOT/'scripts'/name) != sha:
            raise ValueError('Dependency mismatch: '+name)
    for name, sha in config['runtime_hashes'].items():
        if digest(name) != sha:
            raise ValueError('Runtime mismatch: '+name)
    if digest(ROOT/'experiments/campaigns/p5_repeat_feedback_20260910/config.json') != config['source_config_sha256']:
        raise ValueError('Source config mismatch')


def detach(flag, filename):
    with (DIRECTORY/(filename+'.log')).open('a') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), flag],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record = dict(pid=child.pid, started_at=now(), config_sha256=digest(DIRECTORY/'config.json'))
    atomic_json(DIRECTORY/(filename+'.json'), record)
    print(json.dumps(record), flush=True)


def install_bundle(root, bundle):
    """Validate the entire allowlisted transfer before atomically installing new files."""
    import base64
    import hashlib
    from pathlib import Path
    root = Path(root).resolve()
    allowed = {'scripts/feedback_controls.py', 'scripts/collect_feedback_controls.py',
        'scripts/run_feedback_controls.py', 'scripts/analyze_feedback_controls.py',
        'experiments/campaigns/feedback_controls_20260910/config.json',
        'experiments/FEEDBACK_CONTROLS_PROTOCOL_20260910.md',
        'experiments/RESEARCH_PRIORITIES_20260910.md'}
    if set(bundle) != allowed:
        raise ValueError('Unexpected transfer manifest')
    decoded = {}
    for name, item in bundle.items():
        path = root/name
        data = base64.b64decode(item['base64'], validate=True)
        if not path.resolve().is_relative_to(root):
            raise ValueError('Transfer path leaves project')
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Transfer checksum mismatch')
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Refusing to overwrite existing server file: '+name)
        decoded[path] = data
    for path, data in decoded.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix+'.upload.tmp')
            temporary.write_bytes(data)
            temporary.replace(path)


def deliver():
    """Only new campaign files are transferred; never overwrite shared runtime code."""
    lock = (DIRECTORY/'delivery.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = dict(status='waiting_ssh', started_at=now(), pid=os.getpid(), attempts=0,
                 remote_compute_confirmed=False, local_machine_must_stay_on=True)
    deadline = time.time()+48*3600
    files = ['scripts/'+name for name in NEW]
    files += ['experiments/campaigns/'+NAME+'/config.json', 'experiments/FEEDBACK_CONTROLS_PROTOCOL_20260910.md',
              'experiments/RESEARCH_PRIORITIES_20260910.md']
    frozen = {name: digest(ROOT/name) for name in files}
    import base64
    import inspect
    import shlex
    bundle = {name: dict(sha256=frozen[name],base64=base64.b64encode((ROOT/name).read_bytes()).decode()) for name in files}
    program = inspect.getsource(install_bundle)+'\nimport json,sys,subprocess\n'
    program += 'install_bundle('+repr(str(REMOTE))+',json.load(sys.stdin))\n'
    program += 'subprocess.run('+repr([str(REMOTE/'.venv-cosmos/bin/python'),
        str(REMOTE/'scripts/run_feedback_controls.py'),'--launch'])+',check=True)\n'
    command = SSH+[shlex.join([str(REMOTE/'.venv-cosmos/bin/python'),'-c',program])]
    def publish(**items):
        state.update(items, updated_at=now())
        atomic_json(DIRECTORY/'delivery_status.json', state)
    while time.time() < deadline:
        if any(digest(ROOT/name) != sha for name, sha in frozen.items()):
            publish(status='blocked_local_files_changed')
            return
        publish(attempts=state['attempts']+1)
        try:
            launched = subprocess.run(command, input=json.dumps(bundle), capture_output=True, text=True, timeout=180)
            if launched.returncode == 255:
                publish(status='waiting_ssh', last_error=launched.stderr[-2000:])
                time.sleep(120)
                continue
            if launched.returncode:
                publish(status='blocked_remote_launch', last_error=launched.stderr[-2000:])
                return
            publish(status='delivered', remote_launch_output=launched.stdout[-2500:],
                    remote_compute_confirmed=False,
                    note='Dispatcher accepted. Check remote sequence_status for GPU execution.')
            return
        except subprocess.TimeoutExpired as error:
            publish(status='waiting_ssh', last_error=str(error))
            time.sleep(120)
    publish(status='delivery_expired')


def execute(config):
    try:
        from scripts.run_libero_experiment_campaign import gpu_is_free
    except ModuleNotFoundError:
        from run_libero_experiment_campaign import gpu_is_free
    lock = (DIRECTORY/'sequence.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = dict(status='waiting_predecessor', pid=os.getpid(), started_at=now(), active={})
    mutex, stop, occupied = threading.RLock(), threading.Event(), set()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    def publish(**items):
        with mutex:
            state.update(items, updated_at=now())
            state['screen_completed_branches'] = sum(1 for p in (DIRECTORY/'screen').glob('*/*.json') if p.stem in ARMS)
            atomic_json(DIRECTORY/'sequence_status.json', state)
    predecessor = ROOT/'experiments/campaigns'/PREDECESSOR
    publish()
    while not stop.is_set():
        path = predecessor/'sequence_status.json'
        prior = json.loads(path.read_text()) if path.exists() else {}
        with (predecessor/'sequence.lock').open('a') as guard:
            free = True
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                free = False
            decision = check_predecessor(prior, free)
        publish(status=decision, predecessor_status=prior)
        if decision == 'ready':
            break
        if decision.startswith('blocked'):
            return
        stop.wait(60)
    if stop.is_set():
        publish(status='stopped')
        return
    validate(config)
    # Analyze existing evidence before spending more GPU time. A partial campaign stays partial.
    with (DIRECTORY/'predecessor_analysis.log').open('a') as log:
        subprocess.run([sys.executable, str(ROOT/'scripts/analyze_p5_candidate_replication.py'),
                        '--campaign', str(predecessor)], cwd=ROOT, stdout=log, stderr=log, check=True)
    deadline_path = DIRECTORY/'execution_budget.json'
    if deadline_path.exists():
        deadline = json.loads(deadline_path.read_text())['deadline_epoch']
    else:
        deadline = time.time()+config['active_hours']*3600
        atomic_json(deadline_path, dict(deadline_epoch=deadline, started_at=now()))
    publish(status='running', deadline_epoch=deadline)

    def phase(jobs):
        pending = [job for job in jobs if not job_done(DIRECTORY,job)]
        def work():
            while not stop.is_set() and time.time() < deadline:
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
                        occupied.discard(candidate)
                if gpu is None:
                    stop.wait(15)
                    continue
                try:
                    with mutex:
                        if not pending:
                            return
                        first = pending[0]
                        batch_jobs = [j for j in pending if j['environment']==first['environment']][:config['batch_size']]
                        for job in batch_jobs:
                            pending.remove(job)
                    validate(config)
                    batch = DIRECTORY/'batches'/f'{time.time_ns()}_gpu{gpu}.json'
                    atomic_json(batch, dict(campaign=str(DIRECTORY), jobs=batch_jobs, deadline_epoch=deadline))
                    env = dict(os.environ, **first['environment'], CUDA_VISIBLE_DEVICES=gpu,
                        COSMOS_REPO=config['runtime'], HF_HUB_OFFLINE='1', WANDB_MODE='offline',
                        OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MLSPACE_ALLOW_GPU0='1' if gpu=='0' else '0',
                        LIBERO_CONFIG_PATH=str(DIRECTORY/'configs'/batch.stem), PYTHONUNBUFFERED='1')
                    command = ['bash','-ec','source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
                        'feedback',str(ROOT/'scripts/cosmos_env_libero_pro.sh'),
                        str(ROOT/'scripts/collect_feedback_controls.py'),str(batch)]
                    with batch.with_suffix('.log').open('a') as log:
                        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log)
                        with mutex:
                            state['active'][gpu] = dict(pid=child.pid, jobs=[j['id'] for j in batch_jobs], batch=str(batch))
                        publish()
                        sent = False
                        while child.poll() is None:
                            if (stop.is_set() or time.time() > deadline) and not sent:
                                child.terminate()
                                sent = True
                            if time.time() > deadline+600:
                                child.kill()
                                child.wait()
                                raise TimeoutError('Owned worker exceeded shutdown grace')
                            time.sleep(5)
                            publish()
                        if child.returncode:
                            raise RuntimeError('Worker failed: '+str(batch.with_suffix('.log')))
                except BaseException:
                    stop.set()
                    raise
                finally:
                    with mutex:
                        occupied.discard(gpu)
                        state['active'].pop(gpu,None)
                    publish()
        with ThreadPoolExecutor(max_workers=config['max_workers']) as executor:
            futures = [executor.submit(work) for _ in range(config['max_workers'])]
            for future in futures:
                future.result()

    try:
        for name in ('smoke','screen'):
            publish(stage=name)
            jobs = [j for j in config['jobs'] if j['phase']==name]
            phase(jobs)
            if not all(job_done(DIRECTORY,j) for j in jobs):
                publish(status='budget_exhausted' if not stop.is_set() else 'stopped')
                return
            if name == 'smoke':
                completed = [j for j in jobs if json.loads((DIRECTORY/name/j['id']/'completed.json').read_text())['status']=='completed']
                if len(completed) < config['smoke_min_complete_cells']:
                    publish(status='blocked_smoke_coverage')
                    return
        subprocess.run([sys.executable, str(ROOT/'scripts/analyze_feedback_controls.py'),
                        '--campaign', str(DIRECTORY)], check=True, cwd=ROOT)
        publish(status='completed', stage='analysis', automatic_holdout=False)
    except BaseException as error:
        publish(status='failed', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    for flag in ('prepare','launch','execute','status','delivery-launch','deliver'):
        group.add_argument('--'+flag, action='store_true')
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if args.status:
        for name in ('delivery_status.json','sequence_status.json','analysis/summary.json'):
            path = DIRECTORY/name
            if path.exists():
                print(name+'\n'+path.read_text())
        return
    config = prepare()
    if args.delivery_launch:
        with (DIRECTORY/'delivery.lock').open('a') as guard:
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Delivery already active')
                return
        detach('--deliver','delivery_launch')
    elif args.deliver:
        deliver()
    elif args.launch or args.execute:
        if ROOT != REMOTE:
            raise ValueError('GPU execution is allowed only in the canonical server project')
        validate(config)
        if args.launch:
            with (DIRECTORY/'sequence.lock').open('a') as guard:
                try:
                    fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    print('Remote dispatcher already active')
                    return
            detach('--execute','launch')
        else:
            execute(config)
    else:
        print(f'Prepared {NAME}: 15 smoke + 120 screen branches; no automatic holdout')


if __name__ == '__main__':
    main()

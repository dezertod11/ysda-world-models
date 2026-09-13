#!/usr/bin/env python3
"""Idle-only, resumable probe verification campaign with a frozen holdout gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
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
    from scripts.probe_repair import NAME,ARMS,PARAMS,make_jobs
    from scripts.p5_repeat_feedback import atomic_json,digest
except ModuleNotFoundError:
    from probe_repair import NAME,ARMS,PARAMS,make_jobs
    from p5_repeat_feedback import atomic_json,digest

ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY=ROOT/'experiments/campaigns'/NAME
NEW=('probe_repair.py','collect_probe_repair.py','run_probe_repair.py','analyze_probe_repair.py')


def prepare():
    import pandas as pd
    source=ROOT/'experiments/campaigns/feedback_controls_20260910/config.json'
    old=json.loads(source.read_text())
    model=ROOT/'experiments/frozen_models/perception_regrasp_20260904'
    jobs=make_jobs(pd.read_csv(model/'calibration_manifest.csv'))
    extra=('collect_online_perception_regrasp.py','collect_recovery_proposals.py','perception_regrasp.py',
           'perception_regrasp_trigger.py','recovery_proposal_utils.py','prepare_libero_pro_position_variant.sh')
    scripts=dict(old['scripts'],**{f:digest(ROOT/'scripts'/f) for f in (*NEW,*extra)})
    artifacts={str(Path('experiments/frozen_models/perception_regrasp_20260904')/f):digest(model/f)
               for f in ('perception_regrasp_localizer.npz','perception_regrasp_heatmap_weights.pt',
                         'perception_regrasp_trigger_v1.json','calibration_manifest.csv')}
    config=dict(name=NAME,jobs=jobs,arms=ARMS,params=PARAMS,scripts=scripts,artifacts=artifacts,
        runtime=old['runtime'],runtime_hashes=old['runtime_hashes'],max_workers=3,batch_size=4,
        gpu_candidates=list('13602457'),hours=12,expected=dict(smoke=24,screen=192,holdout=192),
        localizer=str(REMOTE/'experiments/frozen_models/perception_regrasp_20260904/perception_regrasp_localizer.npz'),
        trigger=str(REMOTE/'experiments/frozen_models/perception_regrasp_20260904/perception_regrasp_trigger_v1.json'),
        source_config_sha256=digest(source),source_config='experiments/campaigns/feedback_controls_20260910/config.json',
        control='P3c_with_physical_fallback',timing=72,conditional_holdout=True,
        tracking_coordinates='opencv',observation_coordinates='opengl',
        technical_predecessor='probe_verify_repair_20260910',technical_fix='convert_only_tracking_rgb_to_camera_coordinates')
    config=json.loads(json.dumps(config))
    path=DIRECTORY/'config.json'
    if path.exists() and json.loads(path.read_text())!=config:
        raise ValueError('Config changed after freeze; use a new campaign')
    if not path.exists(): atomic_json(path,config)
    return config


def validate(config):
    for name,sha in config['scripts'].items():
        if digest(ROOT/'scripts'/name)!=sha: raise ValueError('Changed source '+name)
    for name,sha in config['artifacts'].items():
        if digest(ROOT/name)!=sha: raise ValueError('Changed model '+name)
    for name,sha in config['runtime_hashes'].items():
        if digest(name)!=sha: raise ValueError('Changed runtime '+name)
    if digest(ROOT/config['source_config'])!=config['source_config_sha256']:
        raise ValueError('Changed parent config')


def done(job):
    output=DIRECTORY/job['phase']/job['id']
    if not (output/'completed.json').exists(): return False
    meta=json.loads((output/'prefix.json').read_text())
    if digest(output/'prefix.npz')!=meta['sha256']: raise ValueError('Prefix mismatch')
    for arm in ARMS:
        path=output/(arm+'.json')
        if not path.exists() or not path.with_suffix('.npz').exists() or not path.with_suffix('.mp4').exists(): return False
        row=json.loads(path.read_text())
        if row['job_id']!=job['id'] or row['rollout_seed']!=job['rollout_seed'] or row['prefix_sha256']!=meta['sha256']:
            raise ValueError('Resume integrity mismatch')
        for extension,key in (('.npz','npz_sha256'),('.mp4','video_sha256')):
            if digest(path.with_suffix(extension))!=row[key]:raise ValueError('Changed branch artifact')
    return True


def run(config):
    try: from scripts.run_libero_experiment_campaign import gpu_is_free
    except ModuleNotFoundError: from run_libero_experiment_campaign import gpu_is_free
    lock=(DIRECTORY/'sequence.lock').open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    mutex=threading.RLock(); stopped=threading.Event(); occupied=set()
    signal.signal(signal.SIGTERM,lambda *_:stopped.set()); signal.signal(signal.SIGINT,lambda *_:stopped.set())
    budget=DIRECTORY/'budget.json'
    if not budget.exists(): atomic_json(budget,dict(deadline_epoch=time.time()+config['hours']*3600))
    deadline=json.loads(budget.read_text())['deadline_epoch']
    state=dict(status='running',pid=os.getpid(),active={},deadline_epoch=deadline)
    def publish(**items):
        with mutex:
            state.update(items,updated_at=datetime.now(timezone.utc).isoformat())
            state['completed_branches']={phase:sum(p.stem in ARMS for p in (DIRECTORY/phase).glob('*/*.json')) for phase in config['expected']}
            atomic_json(DIRECTORY/'sequence_status.json',state)
    def phase(jobs):
        pending=[j for j in jobs if not done(j)]
        def worker():
            while not stopped.is_set() and time.time()<deadline:
                with mutex:
                    if not pending:return
                gpu=None
                for g in config['gpu_candidates']:
                    with mutex:
                        if g in occupied:continue
                        occupied.add(g)
                    if gpu_is_free(g): gpu=g;break
                    with mutex:occupied.discard(g)
                if gpu is None:
                    publish(waiting_for_idle_gpu=True);stopped.wait(15);continue
                try:
                    with mutex:
                        if not pending:return
                        level=pending[0]['position_level']
                        selected=[j for j in pending if j['position_level']==level][:config['batch_size']]
                        for j in selected:pending.remove(j)
                    validate(config)
                    batch=DIRECTORY/'batches'/f'{time.time_ns()}_gpu{gpu}.json'
                    atomic_json(batch,dict(campaign=str(DIRECTORY),jobs=selected,deadline_epoch=deadline))
                    variant=ROOT/'.runtime/libero_pro_position'/level
                    env=dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,COSMOS_REPO=config['runtime'],
                        HF_HUB_OFFLINE='1',WANDB_MODE='offline',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',
                        MLSPACE_ALLOW_GPU0='1' if gpu=='0' else '0',PYTHONUNBUFFERED='1',
                        LIBERO_BDDL_FILES_PATH=str(variant/'bddl_files'),LIBERO_INIT_STATES_PATH=str(variant/'init_files'),
                        LIBERO_CONFIG_PATH=str(DIRECTORY/'configs'/batch.stem))
                    command=['bash','-ec','source "$1"; bash "$2" "$3"; source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$4" --batch "$5"',
                        'probe',str(ROOT/'scripts/cosmos_env_libero_pro.sh'),str(ROOT/'scripts/prepare_libero_pro_position_variant.sh'),
                        level,str(ROOT/'scripts/collect_probe_repair.py'),str(batch)]
                    with batch.with_suffix('.log').open('a') as log:
                        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=log)
                        with mutex:state['active'][gpu]=dict(pid=child.pid,jobs=[j['id'] for j in selected],batch=str(batch))
                        publish(waiting_for_idle_gpu=False)
                        stop_at=None
                        while child.poll() is None:
                            if (stopped.is_set() or time.time()>deadline) and stop_at is None:
                                child.terminate();stop_at=time.time()
                            if stop_at is not None and time.time()-stop_at>600:
                                child.kill();child.wait();raise TimeoutError('Owned worker shutdown timeout')
                            time.sleep(5);publish()
                        if child.returncode:raise RuntimeError('Worker failed: '+str(batch.with_suffix('.log')))
                except BaseException:
                    stopped.set();raise
                finally:
                    with mutex:occupied.discard(gpu);state['active'].pop(gpu,None)
                    publish()
        with ThreadPoolExecutor(max_workers=config['max_workers']) as ex:
            futures=[ex.submit(worker) for _ in range(config['max_workers'])]
            for future in futures:future.result()
    try:
        validate(config);publish()
        for name in ('smoke','screen','holdout'):
            publish(stage=name)
            jobs=[j for j in config['jobs'] if j['phase']==name];phase(jobs)
            if not all(done(j) for j in jobs):publish(status='partial');return
            subprocess.run([sys.executable,str(ROOT/'scripts/analyze_probe_repair.py'),'--campaign',str(DIRECTORY),'--phase',name],cwd=ROOT,check=True)
            summary=json.loads((DIRECTORY/'analysis'/name/'summary.json').read_text())
            if name=='smoke' and summary['probe_attempts']==0:
                publish(status='blocked_smoke_no_probes');return
            if name=='screen' and not summary['holdout_gate_pass']:
                publish(status='completed_screen_gate_failed',holdout_started=False);return
        publish(status='completed',holdout_started=True)
    except BaseException as error:
        publish(status='failed',error=repr(error));raise


def main():
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group()
    for name in ('prepare','launch','execute','status'):g.add_argument('--'+name,action='store_true')
    args=parser.parse_args();DIRECTORY.mkdir(parents=True,exist_ok=True)
    if args.status:
        for path in (DIRECTORY/'sequence_status.json',DIRECTORY/'analysis/screen/summary.json',DIRECTORY/'analysis/holdout/summary.json'):
            if path.exists():print(path.read_text())
        return
    config=prepare()
    if args.launch or args.execute:
        if ROOT!=REMOTE:raise ValueError('Only canonical remote project may execute GPU campaign')
        validate(config)
        if args.launch:
            with (DIRECTORY/'sequence.lock').open('a') as guard:
                try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:print('Already active');return
            with (DIRECTORY/'launcher.log').open('a') as log:
                child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--execute'],cwd=ROOT,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
            result=dict(pid=child.pid,config_sha256=digest(DIRECTORY/'config.json'),started_at=datetime.now(timezone.utc).isoformat())
            atomic_json(DIRECTORY/'launch.json',result);print(json.dumps(result))
        else:run(config)
    else:print('Frozen: 24 smoke + 192 screen + conditional 192 holdout branches')


if __name__=='__main__':main()

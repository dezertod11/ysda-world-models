#!/usr/bin/env python3
"""Seven-hour autonomous recovery study, idle-only GPUs and conditional holdout."""
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
    from scripts.grounded_probe import NAME,ARMS,TRAIN_PARAMS,MASK_PARAMS,TRANSFER_CELLS,make_jobs
    from scripts.probe_repair import CELLS
    from scripts.p5_repeat_feedback import atomic_json,digest
except ModuleNotFoundError:
    from grounded_probe import NAME,ARMS,TRAIN_PARAMS,MASK_PARAMS,TRANSFER_CELLS,make_jobs
    from probe_repair import CELLS
    from p5_repeat_feedback import atomic_json,digest

ROOT=Path(__file__).resolve().parents[1]
REMOTE=Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')
DIRECTORY=ROOT/'experiments/campaigns'/NAME
NEW=('grounded_probe.py','train_grounded_probe_mask.py','collect_grounded_probe.py',
     'analyze_grounded_probe.py','run_grounded_probe.py','train_perception_regrasp_heatmap.py')


def prepare():
    import pandas as pd
    source=ROOT/'experiments/campaigns/probe_verify_repair_20260910_v2/config.json'
    old=json.loads(source.read_text());model=ROOT/'experiments/frozen_models/perception_regrasp_20260904'
    config=dict(name=NAME,jobs=make_jobs(pd.read_csv(model/'calibration_manifest.csv'),CELLS,TRANSFER_CELLS),arms=ARMS,
        train_params=TRAIN_PARAMS,mask_params=MASK_PARAMS,
        scripts=dict(old['scripts'],**{f:digest(ROOT/'scripts'/f) for f in NEW}),
        artifacts=old['artifacts'],runtime=old['runtime'],runtime_hashes=old['runtime_hashes'],
        max_workers=7,batch_size=4,gpu_candidates=list('01235674'),
        hours=7,hard_deadline_utc='2026-09-11T05:35:00+00:00',
        localizer=old['localizer'],trigger=old['trigger'],
        calibration_dir=str(REMOTE/'experiments/campaigns/perception_regrasp_heatmap_20260904__calibration'),
        calibration_manifest=str(REMOTE/'experiments/frozen_models/perception_regrasp_20260904/calibration_manifest.csv'),
        calibration_manifest_sha256=digest(model/'calibration_manifest.csv'),
        source_config='experiments/campaigns/probe_verify_repair_20260910_v2/config.json',source_config_sha256=digest(source),
        scientific_primary='candidate_vs_physical_regrasp',training_uses_terminal_labels=False,
        generated_horizon=16,executed_suffix_horizon=8,prefix_t=72,physical_max_t=280,
        prediction_mode='parallel',K=4,denoising_steps=5,
        mask_validation_failure='omit_mask_arms_continue_other_controls_and_delayed_regrasp',
        technical_predecessor='grounded_probe_20260911',technical_fix='select_exact_388_row_heatmap_calibration_archive')
    config=json.loads(json.dumps(config));path=DIRECTORY/'config.json'
    if path.exists() and json.loads(path.read_text())!=config:raise ValueError('Changed frozen configuration')
    if not path.exists():atomic_json(path,config)
    return config


def validate(config,mask=False):
    for name,sha in config['scripts'].items():
        if digest(ROOT/'scripts'/name)!=sha:raise ValueError('Changed source '+name)
    for name,sha in config['artifacts'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed artifact '+name)
    for name,sha in config['runtime_hashes'].items():
        if digest(name)!=sha:raise ValueError('Changed runtime '+name)
    if digest(ROOT/config['source_config'])!=config['source_config_sha256']:raise ValueError('Changed parent')
    if mask:
        frozen=json.loads((DIRECTORY/'mask_model/freeze.json').read_text())
        for name,sha in frozen['sha256'].items():
            if digest(DIRECTORY/'mask_model'/name)!=sha:raise ValueError('Changed mask weights or validation')


def done(job,arms):
    d=DIRECTORY/job['phase']/job['id']
    if not (d/'completed.json').exists():return False
    if json.loads((d/'completed.json').read_text())['arms']!=list(arms):raise ValueError('Arms changed on resume')
    meta=json.loads((d/'prefix.json').read_text())
    if digest(d/'prefix.npz')!=meta['sha256']:raise ValueError('Changed prefix')
    for arm in arms:
        path=d/(arm+'.json')
        if not path.exists():return False
        row=json.loads(path.read_text())
        if row['prefix_sha256']!=meta['sha256'] or row['rollout_seed']!=job['rollout_seed']:raise ValueError('Resume identity')
        for ext,key in (('.npz','npz_sha256'),('.mp4','video_sha256')):
            if digest(path.with_suffix(ext))!=row[key]:raise ValueError('Changed branch artifact')
    return True


def run(config):
    try:from scripts.run_libero_experiment_campaign import gpu_is_free
    except ModuleNotFoundError:from run_libero_experiment_campaign import gpu_is_free
    lock=(DIRECTORY/'sequence.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stopped=threading.Event();mutex=threading.RLock();occupied=set()
    signal.signal(signal.SIGTERM,lambda *_:stopped.set());signal.signal(signal.SIGINT,lambda *_:stopped.set())
    budget=DIRECTORY/'budget.json'
    if not budget.exists():atomic_json(budget,dict(deadline_epoch=min(time.time()+config['hours']*3600,
        datetime.fromisoformat(config['hard_deadline_utc']).timestamp())))
    deadline=json.loads(budget.read_text())['deadline_epoch']
    state=dict(status='running',stage='training_mask',pid=os.getpid(),active={},deadline_epoch=deadline)
    start=time.time()
    def publish(**items):
        with mutex:
            state.update(items,updated_at=datetime.now(timezone.utc).isoformat())
            state['completed_branches']={phase:sum(p.stem in ARMS for p in (DIRECTORY/phase).glob('*/*.json')) for phase in ('smoke','screen','holdout','transfer')}
            state['seconds_until_deadline']=max(0,int(deadline-time.time()))
            n=sum(state['completed_branches'].values())
            if n:
                rate=n/max(1,time.time()-start)
                state['observed_branches_per_hour']=rate*3600
                state['eta_remaining_upper_bound_seconds']=int(max(0,1104-n)/rate)
            atomic_json(DIRECTORY/'sequence_status.json',state)
    def acquire():
        for gpu in config['gpu_candidates']:
            with mutex:
                if gpu in occupied:continue
                occupied.add(gpu)
            claim_dir=ROOT/'.runtime/grounded_gpu_claims';claim_dir.mkdir(parents=True,exist_ok=True)
            handle=(claim_dir/(gpu+'.lock')).open('a')
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                if gpu_is_free(gpu):return gpu,handle
            except BlockingIOError:pass
            handle.close()
            with mutex:occupied.discard(gpu)
        return None,None
    def release(gpu,handle):
        handle.close()
        with mutex:occupied.discard(gpu);state['active'].pop(gpu,None)
        publish()
    def child(command,env,log_path,gpu,label):
        with log_path.open('a') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
            with mutex:state['active'][gpu]=dict(pid=process.pid,jobs=label,log=str(log_path))
            publish(waiting_for_idle_gpu=False);stop_at=None
            while process.poll() is None:
                if (stopped.is_set() or time.time()>deadline) and stop_at is None:
                    process.terminate();stop_at=time.time()
                if stop_at is not None and time.time()-stop_at>120:process.kill();process.wait()
                time.sleep(5);publish()
            return process.returncode
    def environment(gpu):
        return dict(os.environ,CUDA_VISIBLE_DEVICES=gpu,COSMOS_REPO=config['runtime'],HF_HUB_OFFLINE='1',
            WANDB_MODE='offline',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONUNBUFFERED='1',
            MLSPACE_ALLOW_GPU0='1' if gpu=='0' else '0')
    def phase(name,arms):
        jobs=[j for j in config['jobs'] if j['phase']==name]
        pending=[j for j in jobs if not done(j,arms)];attempts={}
        def worker():
            while not stopped.is_set() and time.time()<deadline:
                with mutex:
                    if not pending:return
                gpu,handle=acquire()
                if gpu is None:publish(waiting_for_idle_gpu=True);stopped.wait(15);continue
                try:
                    with mutex:
                        if not pending:return
                        level=pending[0]['position_level']
                        selected=[j for j in pending if j['position_level']==level][:config['batch_size']]
                        for j in selected:pending.remove(j)
                    validate(config,mask=True)
                    batch=DIRECTORY/'batches'/f'{time.time_ns()}_gpu{gpu}.json'
                    atomic_json(batch,dict(campaign=str(DIRECTORY),jobs=selected,arms=arms,deadline_epoch=deadline))
                    variant=ROOT/'.runtime/libero_pro_position'/level
                    env=dict(environment(gpu),LIBERO_BDDL_FILES_PATH=str(variant/'bddl_files'),
                        LIBERO_INIT_STATES_PATH=str(variant/'init_files'),LIBERO_CONFIG_PATH=str(DIRECTORY/'configs'/batch.stem))
                    command=['bash','-ec','source "$1"; bash "$2" "$3"; source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$4" --batch "$5"',
                        'grounded',str(ROOT/'scripts/cosmos_env_libero_pro.sh'),str(ROOT/'scripts/prepare_libero_pro_position_variant.sh'),
                        level,str(ROOT/'scripts/collect_grounded_probe.py'),str(batch)]
                    code=child(command,env,batch.with_suffix('.log'),gpu,[j['id'] for j in selected])
                    if code and not stopped.is_set() and time.time()<deadline:
                        with mutex:
                            for job in selected:
                                attempts[job['id']]=attempts.get(job['id'],0)+1
                                if attempts[job['id']]>1:raise RuntimeError('Worker failed twice; inspect '+str(batch.with_suffix('.log')))
                                pending.append(job)
                            state.setdefault('retry_logs',[]).append(str(batch.with_suffix('.log')))
                except BaseException:stopped.set();raise
                finally:release(gpu,handle)
        with ThreadPoolExecutor(max_workers=config['max_workers']) as pool:
            futures=[pool.submit(worker) for _ in range(config['max_workers'])]
            for future in futures:future.result()
        return all(done(j,arms) for j in jobs)
    try:
        validate(config);publish()
        if not (DIRECTORY/'mask_model/freeze.json').exists():
            gpu=None
            while not stopped.is_set() and time.time()<deadline:
                gpu,handle=acquire()
                if gpu is not None:break
                publish(waiting_for_idle_gpu=True);stopped.wait(15)
            if gpu is None:publish(status='partial');return
            try:
                code=child([sys.executable,str(ROOT/'scripts/train_grounded_probe_mask.py'),'--campaign',str(DIRECTORY)],
                    environment(gpu),DIRECTORY/'mask_training.log',gpu,['mask_training'])
                if code:raise RuntimeError('Mask training did not complete; inspect mask_training.log')
            finally:release(gpu,handle)
        validate(config,mask=True)
        freeze=json.loads((DIRECTORY/'mask_model/freeze.json').read_text())
        arms=list(ARMS) if freeze['validation_gate_pass'] else [a for a in ARMS if not a.startswith('mask_verify')]
        plan_path=DIRECTORY/'phase_plan.json'
        if not plan_path.exists():atomic_json(plan_path,dict(smoke=arms,screen=arms,holdout=[],transfer=[],winner=None,
            mask_enabled=freeze['validation_gate_pass'],mask_freeze_sha256=digest(DIRECTORY/'mask_model/freeze.json')))
        plan=json.loads(plan_path.read_text())
        for name in ('smoke','screen','holdout','transfer'):
            if name=='holdout':
                summary=json.loads((DIRECTORY/'analysis/screen/summary.json').read_text())
                winner=summary.get('winner')
                if not winner:
                    publish(screen_no_go=True,holdout_started=False)
                    continue
                holdout_arms=['continue_h8','physical_regrasp','probe_always_regrasp',winner]
                if winner.startswith('mask_verify'):holdout_arms.insert(3,'probe_verify_repair')
                if plan['holdout'] and plan['holdout']!=holdout_arms:raise ValueError('Holdout selection changed')
                plan.update(holdout=holdout_arms,winner=winner);atomic_json(plan_path,plan)
            if name=='transfer':
                transfer_arms=['continue_h8','physical_regrasp','delayed_regrasp_h8']
                holdout_summary=DIRECTORY/'analysis/holdout/summary.json'
                confirmed=holdout_summary.exists() and json.loads(holdout_summary.read_text()).get('confirmatory_pass',False)
                if confirmed and plan['winner'] not in transfer_arms:transfer_arms.append(plan['winner'])
                if plan['transfer'] and plan['transfer']!=transfer_arms:raise ValueError('Transfer arms changed')
                plan.update(transfer=transfer_arms);atomic_json(plan_path,plan)
            publish(stage=name,holdout_started=bool(plan['holdout']),expected_current_branches=len(plan[name])*sum(j['phase']==name for j in config['jobs']))
            if not phase(name,plan[name]):publish(status='partial');return
            subprocess.run([sys.executable,str(ROOT/'scripts/analyze_grounded_probe.py'),'--campaign',str(DIRECTORY),'--phase',name],check=True,cwd=ROOT)
            if name=='smoke':
                summary=json.loads((DIRECTORY/'analysis/smoke/summary.json').read_text())
                if not summary['complete']:raise ValueError('Incomplete smoke analysis')
        publish(status='completed',holdout_started=bool(plan['holdout']))
    except BaseException as error:publish(status='failed',error=repr(error));raise


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group()
    for name in ('prepare','launch','execute','status'):group.add_argument('--'+name,action='store_true')
    args=parser.parse_args();DIRECTORY.mkdir(parents=True,exist_ok=True)
    if args.status:
        for relative in ('sequence_status.json','mask_model/training_status.json','mask_model/mask.json',
                         'analysis/screen/summary.json','analysis/holdout/summary.json','analysis/transfer/summary.json'):
            path=DIRECTORY/relative
            if path.exists():print(path.read_text())
        return
    config=prepare()
    if args.launch or args.execute:
        if ROOT!=REMOTE:raise ValueError('GPU execution only in canonical server workspace')
        validate(config)
        if args.launch:
            with (DIRECTORY/'sequence.lock').open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:print('Already active');return
            with (DIRECTORY/'launcher.log').open('a') as log:
                process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--execute'],cwd=ROOT,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
            result=dict(pid=process.pid,config_sha256=digest(DIRECTORY/'config.json'),started_at=datetime.now(timezone.utc).isoformat())
            atomic_json(DIRECTORY/'launch.json',result);print(json.dumps(result))
        else:run(config)
    else:print('Prepared mask training, <=48 smoke +384 screen +480 conditional holdout +192 transfer')


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Freeze and execute a bounded saved-action/feedback experiment."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import numpy as np
import pandas as pd

try:
    from scripts.p5_repeat_feedback import atomic_json, check_saved_pool, digest
    from scripts import run_libero_experiment_campaign as legacy
except ModuleNotFoundError:
    from p5_repeat_feedback import atomic_json, check_saved_pool, digest
    import run_libero_experiment_campaign as legacy

ROOT=Path(__file__).resolve().parents[1]
NAME='p5_repeat_feedback_20260910'
SOURCE=ROOT/'experiments/campaigns/p5_boundary_candidates_20260909'
SCRIPTS=('p5_repeat_feedback.py','collect_p5_repeat_feedback.py','run_p5_repeat_feedback_night.py',
         'analyze_p5_repeat_feedback.py','collect_counterfactual_feedback.py','libero_runtime_snapshot.py',
         'counterfactual_feedback_utils.py','libero_resident.py','run_libero_experiment_campaign.py',
         'cosmos_env.sh','cosmos_env_libero_pro.sh')


def prepare(directory, deadline):
    config_path=directory/'config.json'
    source=SOURCE/'p5_analysis/candidate_features_and_outcomes.parquet'
    scripts={name:digest(ROOT/'scripts'/name) for name in SCRIPTS}
    runtime=ROOT/'experiments/campaigns/consensus_references_20260909_valid199/source/cosmos-policy'
    runtime_files=['cosmos_policy/experiments/robot/cosmos_utils.py',
        'cosmos_policy/experiments/robot/libero/uncertainty_comparison.py',
        'cosmos_policy/experiments/robot/libero/uncertainty_metrics.py',
        'cosmos_policy/experiments/robot/libero/safety_signals.py']
    hashes={str(runtime/f):digest(runtime/f) for f in runtime_files}
    if config_path.exists():
        cfg=json.loads(config_path.read_text())
        if cfg['scripts']!=scripts or cfg['source_sha256']!=digest(source) or cfg['runtime_hashes']!=hashes:
            raise ValueError('Frozen experiment changed; use a new protocol, not in-place retuning')
        return cfg
    rows=pd.read_parquet(source)
    old=json.loads((SOURCE/'manifest.json').read_text())
    if old['status']!='completed':raise ValueError('Source pilot incomplete')
    jobs={j['environment']['LIBERO_PRO_VOF_RUN_NAME']:j for j in old['jobs']}
    pools=[]
    for _,g in rows.groupby(['case_id','task_id','init_state_id','query_idx'],sort=True):
        g=g.sort_values('candidate_idx'); first=g.iloc[0]
        if g.candidate_idx.tolist()!=list(range(8)) or not g.terminal_available.all():
            raise ValueError('Source has incomplete pools')
        sidecar=Path(first.sidecar_path)
        with np.load(sidecar,allow_pickle=False) as data:selected=check_saved_pool(data,g.candidate_value.to_numpy())
        job=jobs[Path(first.source_trace).name.removesuffix('__candidate_outcomes.parquet')]
        env={k:v for k,v in job['environment'].items() if k in (
            'LIBERO_BDDL_FILES_PATH','LIBERO_INIT_STATES_PATH','LIBERO_ASSETS_PATH','LIBERO_BENCHMARK_ROOT','LIBERO_PRO_REPO')}
        identity=json.dumps([str(first.suite),env],sort_keys=True)
        pools.append(dict(id=f'pool_{len(pools):02d}',case_id=str(first.case_id),factor='Position' if 'position' in first.case_id else 'Object',
            task_id=int(first.task_id),init_state_id=int(first.init_state_id),query_idx=int(first.query_idx),
            t=int(first.t),suite=str(first.suite),task_description=str(first.task_description),
            rollout_seed=int(first.rollout_seed),sidecar=str(sidecar),sidecar_sha256=digest(sidecar),
            selected=selected,environment=env,identity=identity))
    if len(pools)!=36:raise ValueError('Expected all 36 pools, no outcome filtering')
    smoke=[pools[0]['id'], next(p['id'] for p in pools if p['case_id']=='p5_position_y0.2' and p['task_id']==9 and p['init_state_id']==8 and p['query_idx']==0)]
    cfg=dict(name=NAME,created_at=datetime.now(timezone.utc).isoformat(),deadline_epoch=deadline,
        max_workers=2,batch_size=3,gpu_candidates=list('01234567'),smoke=smoke,pools=pools,
        repeats=3,suffix_offsets=[100000,200000,300000],expected_branches=1080,
        planned_methods=['open16','fresh8','stale8'],source=str(source),source_sha256=digest(source),
        runtime=str(runtime),runtime_hashes=hashes,scripts=scripts,
        development_only=True,primary_comparison='fresh8_minus_stale8',
        secondary_comparison='fresh8_minus_open16_selected',cluster=['task_id','init_state_id'])
    atomic_json(config_path,cfg)
    return cfg


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--deadline-utc',default='2026-09-10T06:35:59+00:00')
    args=parser.parse_args()
    directory=ROOT/'experiments/campaigns'/NAME
    if args.status:
        print((directory/'sequence_status.json').read_text())
        p=directory/'analysis/summary.json'
        if p.exists():print(p.read_text())
        return
    directory.mkdir(parents=True,exist_ok=True)
    lock=(directory/'sequence.lock').open('a'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=prepare(directory,datetime.fromisoformat(args.deadline_utc).timestamp())
    print(f"Frozen: 36 pools, 1080 branches, {cfg['max_workers']} workers; deadline {args.deadline_utc}",flush=True)
    if not args.execute:return
    state=dict(status='running',stage='smoke',pid=os.getpid(),started_at=datetime.now(timezone.utc).isoformat(),
        expected_branches=1080,completed_branches=0,active={},waiting_workers=0,deadline_epoch=cfg['deadline_epoch'])
    mutex=threading.Lock(); occupied=set(); stop=threading.Event()
    def publish():
        with mutex:
            state['updated_at']=datetime.now(timezone.utc).isoformat()
            # Only terminal branch JSON files count, not replay checks or partial artifacts.
            files=list((directory/'runs').glob('*/r*_c*_*.json'))
            state['completed_branches']=len(files)
            atomic_json(directory/'sequence_status.json',state)
    def heartbeat():
        while not stop.wait(10):publish()
    heart=threading.Thread(target=heartbeat,daemon=True); heart.start()
    def finished(pool,smoke):
        sub=directory/('smoke' if smoke else 'runs')/pool['id']
        return len(list(sub.glob('r*_c*_*.json')))==(3 if smoke else 30) and (sub/'completed.json').exists()
    def process(batch,gpu,smoke):
        if any(digest(ROOT/'scripts'/name)!=value for name,value in cfg['scripts'].items()):
            raise ValueError('Executor changed after freeze')
        identifier=f'{time.time_ns()}_gpu{gpu}'
        path=directory/'batches'/(identifier+'.json')
        payload=dict(pools=batch,gpu=gpu,smoke=smoke,deadline_epoch=cfg['deadline_epoch'],
            output=str(directory/('smoke' if smoke else 'runs')))
        atomic_json(path,payload)
        env=dict(os.environ,**batch[0]['environment'],CUDA_VISIBLE_DEVICES=gpu,COSMOS_REPO=cfg['runtime'],
            HF_HUB_OFFLINE='1',WANDB_MODE='offline',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',
            LIBERO_CONFIG_PATH=str(directory/'configs'/identifier),MLSPACE_ALLOW_GPU0='1' if gpu=='0' else '0',
            PYTHONUNBUFFERED='1')
        command=['bash','-ec','source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3"',
            'p5repeat',str(ROOT/'scripts/cosmos_env_libero_pro.sh'),str(ROOT/'scripts/collect_p5_repeat_feedback.py'),str(path)]
        with path.with_suffix('.log').open('a') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            with mutex:state['active'][gpu]=dict(pid=child.pid,batch=str(path),pools=[p['id'] for p in batch])
            publish()
            requested_stop=False
            while child.poll() is None:
                if stop.is_set() and not requested_stop:
                    child.terminate();requested_stop=True
                if time.time()>cfg['deadline_epoch']+600:
                    child.terminate()
                    try:child.wait(timeout=120)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
                    raise TimeoutError('Owned worker exceeded deadline grace')
                time.sleep(2)
        if child.returncode:raise RuntimeError(f'Worker failed: {path.with_suffix(".log")}')
        status=json.loads(path.with_suffix('.status.json').read_text())
        if status['status']=='completed':
            for p in batch:
                sub=Path(payload['output'])/p['id']
                if len(list(sub.glob('r*_c*_*.json')))!=(3 if smoke else 30):
                    raise ValueError('Missing finished branches')
                atomic_json(sub/'completed.json',dict(status='completed',batch=str(path)))
    def run_phase(pools,smoke):
        pending=[p for p in pools if not finished(p,smoke)]
        def work():
            while not stop.is_set() and time.time()<cfg['deadline_epoch']:
                with mutex:
                    if not pending:return
                gpu=None
                for candidate in cfg['gpu_candidates']:
                    with mutex:
                        if candidate in occupied:continue
                        occupied.add(candidate)
                    if legacy.gpu_is_free(candidate):gpu=candidate;break
                    with mutex:occupied.remove(candidate)
                if gpu is None:
                    stop.wait(5);continue
                try:
                    with mutex:
                        if not pending:return
                        identity=pending[0]['identity']
                        batch=[p for p in pending if p['identity']==identity][:1 if smoke else cfg['batch_size']]
                        for p in batch:pending.remove(p)
                    process(batch,gpu,smoke)
                except BaseException:
                    stop.set();raise
                finally:
                    with mutex:
                        occupied.discard(gpu);state['active'].pop(gpu,None)
                    publish()
        with ThreadPoolExecutor(max_workers=cfg['max_workers']) as executor:
            futures=[executor.submit(work) for _ in range(cfg['max_workers'])]
            for future in futures:future.result()
    error=None
    try:
        run_phase([p for p in cfg['pools'] if p['id'] in cfg['smoke']],True)
        if all(finished(p,True) for p in cfg['pools'] if p['id'] in cfg['smoke']):
            state['stage']='repeats_and_feedback';publish()
            run_phase(cfg['pools'],False)
        state['status']='completed' if all(finished(p,False) for p in cfg['pools']) else 'budget_exhausted'
    except BaseException as exc:
        error=exc;state.update(status='failed',error=repr(exc))
    finally:
        stop.set();heart.join();publish()
        command=[sys.executable,str(ROOT/'scripts/analyze_p5_repeat_feedback.py'),'--campaign',str(directory)]
        result=subprocess.run(command,cwd=ROOT)
        if result.returncode:state.update(status='analysis_failed',analysis_returncode=result.returncode)
        state['finished_at']=datetime.now(timezone.utc).isoformat();publish()
    if error:raise error


if __name__=='__main__':main()

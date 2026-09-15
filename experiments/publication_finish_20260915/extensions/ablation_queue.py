#!/usr/bin/env python3
"""After strict main completion, add a matched retreat control before the same deadline."""
import argparse
import copy
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import run_recovery_confirmation as runner
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json
SOURCE=ROOT/'experiments/campaigns/recovery_scoped_runtime_v2_20260915'
DEST=ROOT/'experiments/campaigns/recovery_retreat_runtime_v2_20260915'
SOURCE_SHA='91c8a14d9c0bd1caf50b645f53f9caff49df1d3a4edecf4517b70142d30a9b32'


def validate(config):
    runner.validate(config)
    assert digest(SOURCE/'config.json') == SOURCE_SHA == config['reused_config_sha256']
    assert config['runtime_snapshot_version']==2
    for path,sha in config['versioned_files'].items():
        if digest(ROOT/path)!=sha: raise ValueError('Changed versioned file: '+path)
    for path,sha in config['extension_files'].items():
        if digest(ROOT/path)!=sha: raise ValueError('Changed ablation file: '+path)


def prepare():
    source=json.loads((SOURCE/'config.json').read_text())
    assert digest(SOURCE/'config.json')==SOURCE_SHA
    cfg=copy.deepcopy(source)
    cfg['jobs']=[j for j in cfg['jobs'] if j['phase']=='main']
    from contract import ARMS,PRIMARY
    cfg.update(name=DEST.name,arms=list(ARMS),primary=list(PRIMARY),phase_order=['main'],
               reused_config_sha256=SOURCE_SHA,extension_files={str(p.relative_to(ROOT)):digest(p)
                    for p in HERE.glob('*.py')},
               sampling_scope='Matched snapshot-v2 retreat ablation; three existing arms reused, '
                              'only retreat_requery is newly executed; not new independent baseline evidence')
    path=DEST/'config.json'
    if path.exists():
        assert json.loads(path.read_text())==cfg
    else: atomic_json(path,cfg)
    validate(cfg)
    for job in cfg['jobs']:
        old=SOURCE/'main'/job['id']; new=DEST/'main'/job['id']; new.mkdir(parents=True,exist_ok=True)
        assert json.loads((old/'completed.json').read_text())['status']=='completed'
        names=[f'{arm}{suffix}' for arm in ('baseline_h16','continue_h8','physical_regrasp')
               for suffix in ('.json','.npz','.mp4')]
        names += [f'prefix_{t}{suffix}' for t in (56,72,88) for suffix in ('.json','.npz')]
        for name in names:
            target=new/name
            if not target.exists(): shutil.copy2(old/name,target)
            assert digest(target)==digest(old/name)
    return cfg


class Adapter:
    @staticmethod
    def redirect(cmd):
        paths={str(ROOT/'scripts/collect_recovery_confirmation.py'):str(HERE/'collect.py'),
               str(ROOT/'scripts/analyze_recovery_confirmation.py'):str(HERE/'analyze.py')}
        return [paths.get(x,x) if isinstance(x,str) else x for x in cmd]
    def Popen(self,cmd,*args,**kwargs): return subprocess.Popen(self.redirect(cmd),*args,**kwargs)
    def run(self,cmd,*args,**kwargs): return subprocess.run(self.redirect(cmd),*args,**kwargs)
    def __getattr__(self,name): return getattr(subprocess,name)


def execute(deadline):
    if ROOT!=runner.REMOTE: raise ValueError('Server-only queue')
    with (HERE/'queue.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while time.time()<deadline:
            path=SOURCE/'sequence_status.json'
            state=json.loads(path.read_text()) if path.exists() else {'status':'not_started'}
            atomic_json(HERE/'status.json',dict(status='waiting_for_main_audit',parent=state['status'],deadline_epoch=deadline))
            if state['status']=='completed': break
            if state['status'] in ('failed','partial'):
                atomic_json(HERE/'status.json',dict(status='stopped_parent_not_complete',parent=state['status'])); return
            time.sleep(45)
        if time.time()>=deadline:
            atomic_json(HERE/'status.json',dict(status='deadline_before_ablation')); return
        main=json.loads((SOURCE/'analysis/main/summary.json').read_text())
        assert main['complete'] and main['runtime_snapshot_version']==2 and main['cases']==128
        cfg=prepare()
        from contract import install
        install()
        runner.DIRECTORY=DEST; runner.subprocess=Adapter(); runner.atomic_json=atomic_json
        budget=DEST/'budget.json'
        if not budget.exists(): atomic_json(budget,dict(start_epoch=time.time(),deadline_epoch=deadline))
        else: assert json.loads(budget.read_text())['deadline_epoch']==deadline
        atomic_json(HERE/'status.json',dict(status='running',deadline_epoch=deadline,new_rollouts=128,reused_rollouts=384))
        runner.execute(cfg)
        atomic_json(HERE/'status.json',json.loads((DEST/'sequence_status.json').read_text()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--launch',action='store_true')
    parser.add_argument('--deadline',default='2026-09-16T07:50:00+03:00')
    args=parser.parse_args(); dt=datetime.fromisoformat(args.deadline)
    if dt.tzinfo is None or dt.timestamp()<=time.time(): raise ValueError('Expired/ambiguous deadline')
    if args.launch:
        if ROOT!=runner.REMOTE: raise ValueError('Server only')
        with (HERE/'launcher.log').open('a') as log:
            child=subprocess.Popen([sys.executable,str(HERE/'ablation_queue.py'),'--deadline',args.deadline],
                  cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        info=dict(pid=child.pid,deadline_epoch=dt.timestamp(),started_at=datetime.now(timezone.utc).isoformat())
        atomic_json(HERE/'launch.json',info); print(json.dumps(info))
    else: execute(dt.timestamp())

#!/usr/bin/env python3
"""Fetch committed reports without secrets or model weights, then rebuild the article."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REMOTE='/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP'
SSH='ssh -o IPQoS=none -o GSSAPIAuthentication=no -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=10 -o ServerAliveCountMax=2 -o ControlMaster=auto -o ControlPath=/tmp/p3-codex-recovery-%C -o ControlPersist=600'
CAMPAIGNS=['recovery_scoped_runtime_v2_20260915_smoke','recovery_scoped_runtime_v2_20260915','recovery_retreat_runtime_v2_20260915']


def pull(videos=False):
    for name in CAMPAIGNS:
        remote_path = f'{REMOTE}/experiments/campaigns/{name}/'
        if 'retreat' in name:
            check = subprocess.run([*shlex.split(SSH), 'mlspace-sr006',
                                    'test -d ' + shlex.quote(remote_path)], timeout=60)
            if check.returncode == 1:
                print('Retreat ablation has not started yet.', flush=True)
                continue
            check.check_returncode()
        print('Fetching reports: ' + name, flush=True)
        local=ROOT/'experiments/campaigns'/name; local.mkdir(parents=True,exist_ok=True)
        command=['rsync','-a','--rsync-path=/home/jovyan/.local/bin/rsync','-e',SSH,
                 '--include=*/','--include=*.json','--include=*.csv','--include=*.md','--include=*.png','--include=*.html']
        if videos: command += ['--include=*.mp4']
        command += ['--exclude=*',f'mlspace-sr006:{remote_path}',str(local)+'/']
        subprocess.run(command,cwd=ROOT,timeout=600,check=True)
    subprocess.run([sys.executable,str(HERE/'build.py')],cwd=ROOT,check=True,timeout=600)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--videos',action='store_true')
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--deadline',default='2026-09-16T08:00:00+03:00')
    args=parser.parse_args(); end=datetime.fromisoformat(args.deadline)
    if end.tzinfo is None: raise ValueError('Deadline must include timezone')
    while True:
        try:
            pull(args.videos)
            path=ROOT/'experiments/campaigns/recovery_retreat_runtime_v2_20260915/sequence_status.json'
            if path.exists() and json.loads(path.read_text()).get('status')=='completed': break
        except (RuntimeError,subprocess.SubprocessError) as error:
            print(error,flush=True)
            if not args.watch: raise
        if not args.watch or time.time()>=end.timestamp(): break
        time.sleep(min(300,max(0,end.timestamp()-time.time())))

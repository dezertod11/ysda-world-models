#!/usr/bin/env python3
"""Paired physical-recovery outcomes; preserve held-out labels and strong controls."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.probe_repair import ARMS,validation_gate,validate_probe_pair
    from scripts.p5_repeat_feedback import atomic_json,digest
    from scripts.analyze_feedback_controls import contrast
except ModuleNotFoundError:
    from probe_repair import ARMS,validation_gate,validate_probe_pair
    from p5_repeat_feedback import atomic_json,digest
    from analyze_feedback_controls import contrast


def analyze(directory,phase):
    cfg=json.loads((directory/'config.json').read_text());rows=[]
    jobs=[j for j in cfg['jobs'] if j['phase']==phase]
    missing=[]
    for job in jobs:
        d=directory/phase/job['id']
        if not (d/'completed.json').exists():missing.append(job['id']);continue
        meta=json.loads((d/'prefix.json').read_text())
        if digest(d/'prefix.npz')!=meta['sha256']:raise ValueError('Prefix checksum')
        probe_audits=[]
        for arm in ARMS:
            r=json.loads((d/(arm+'.json')).read_text())
            if r['prefix_sha256']!=meta['sha256'] or r['rollout_seed']!=job['rollout_seed'] or r['arm']!=arm:
                raise ValueError('Pair identity mismatch')
            for extension,key in (('.npz','npz_sha256'),('.mp4','video_sha256')):
                if digest(d/(arm+extension))!=r[key]:raise ValueError('Changed branch artifact')
            with np.load(d/(arm+'.npz'),allow_pickle=False) as z:
                if len(z['executed_actions'])!=r['terminal_final_t']-r['prefix_t']:raise ValueError('Step accounting')
                np.testing.assert_array_equal(z['frame_t'],np.arange(r['prefix_t'],r['terminal_final_t']+1))
                if len(z['frame_t'])!=r['video_frames']:raise ValueError('Frame accounting')
            if 'probe_end_audit' in r['intervention']:
                probe_audits.append(r['intervention']['probe_end_audit'])
            rows.append(r)
        if probe_audits:
            if len(probe_audits)!=2:raise ValueError('Missing paired probe')
            validate_probe_pair(*probe_audits)
    out=directory/'analysis'/phase;out.mkdir(parents=True,exist_ok=True)
    summary=dict(phase=phase,complete=not missing,missing=missing,branches=len(rows),pairs=len(rows)//4)
    if not rows:atomic_json(out/'summary.json',summary);return
    data=pd.DataFrame(rows)
    if data.duplicated(['job_id','arm']).any():raise ValueError('Duplicates')
    wide=data.pivot(index='job_id',columns='arm',values='terminal_success').astype(int)
    data['probe_steps']=data.intervention.map(lambda x:x['probe_steps'])
    data['verification']=data.intervention.map(lambda x:x['verification'])
    data['repair_requested']=data.intervention.map(lambda x:x.get('repair_requested',False))
    data['initial_trigger_passed']=data.intervention.map(lambda x:x['initial_trigger_passed'])
    v=data[data.arm.eq('probe_verify_repair')];full=data[data.arm.eq('physical_regrasp')]
    summary.update(verified_minus_full=float((wide.probe_verify_repair-wide.physical_regrasp).mean()),
        verified_minus_probe=float((wide.probe_verify_repair-wide.probe_only).mean()),
        verified_minus_continue=float((wide.probe_verify_repair-wide.continue_h8).mean()),
        verified_drop_count=int(v.terminal_target_drop_candidate.sum()),full_drop_count=int(full.terminal_target_drop_candidate.sum()),
        probe_attempts=int(v.probe_steps.gt(0).sum()),verification_counts=v.verification.value_counts().to_dict(),
        changed_from_full=int((v.initial_trigger_passed&~v.repair_requested).sum()),
        unseen_calibration_cells=sorted(v.loc[~v.calibration_cell_seen,'cell'].unique()),
        terminal_labels_not_a_deployed_failure_predictor=True)
    summary['holdout_gate_pass']=validation_gate(summary)
    effects=[]
    if not missing:
        for baseline in ('physical_regrasp','probe_only','continue_h8'):
            effects.append(contrast(data,'probe_verify_repair',baseline))
        e=pd.DataFrame(effects);order=e.sort_values('cluster_sign_p').index
        e.loc[order,'holm_p']=np.minimum(1,np.maximum.accumulate(e.loc[order,'cluster_sign_p'].to_numpy()*np.arange(3,0,-1)))
        e.to_csv(out/'paired_effects.csv',index=False);summary['effects']=e.to_dict('records')
        primary=e[e.right.eq('physical_regrasp')].iloc[0]
        summary['confirmatory_pass']=bool(phase=='holdout' and primary.ci_low>0 and primary.holm_p<=.05
            and summary['verified_drop_count']<=summary['full_drop_count'])
    atomic_json(out/'summary.json',summary)
    data.drop(columns=['queries']).to_json(out/'branch_outcomes.json',orient='records',indent=2)
    scores=data.groupby(['cell','calibration_cell_seen','arm']).agg(n=('terminal_success','size'),
        successes=('terminal_success','sum'),sr=('terminal_success','mean'),drop_proxy=('terminal_target_drop_candidate','mean'),
        wrong_proxy=('terminal_wrong_object_interaction_candidate','mean'),final_t=('terminal_final_t','mean'),
        probe_steps=('probe_steps','mean'),trigger_rate=('initial_trigger_passed','mean')).reset_index()
    scores.to_csv(out/'scores.csv',index=False)
    gallery=['<!doctype html><meta charset="utf-8"><title>Probe verify repair</title>',
             '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}video{width:360px;max-width:100%}</style>']
    for name,group in data.groupby('job_id'):
        gallery.append('<h2>'+html.escape(name)+'</h2><div class="row">')
        for arm in ARMS:
            r=group[group.arm.eq(arm)].iloc[0]
            gallery.append(f'<figure><figcaption>{arm}: {bool(r.terminal_success)}, {r.verification}</figcaption><video controls preload="none" src="../../{phase}/{name}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (out/'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(12,5),layout='constrained')
    scores.pivot(index='cell',columns='arm',values='sr').reindex(columns=ARMS).plot.bar(ax=ax)
    ax.set(ylabel='Terminal success rate',ylim=(0,1));fig.savefig(out/'success_rates.png',dpi=160);plt.close(fig)
    (out/'RESULTS.md').write_text('\n'.join(['# Probe/verify/repair '+phase,'',
        f'Complete: {not missing}. {len(rows)} branches. Thresholds frozen; simulator contacts are not online inputs.',
        'Camera tracking can confuse robot and object: do not interpret held/unknown/miss as ground truth.',
        'Control is P3c with physical fallback, not historical rollback behavior. t72 is fixed, not an event trigger.',
        '',scores.to_markdown(index=False),'','![Scores](success_rates.png)','',
        '[Videos](videos.html)','','```json',json.dumps(summary,indent=2),'```'])+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',type=Path,required=True);p.add_argument('--phase',required=True)
    a=p.parse_args();analyze(a.campaign,a.phase)

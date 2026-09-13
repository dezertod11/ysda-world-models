#!/usr/bin/env python3
"""Strict paired analysis and preregistered selection for the grounded screen."""
import argparse
import html
import json
from pathlib import Path
import numpy as np
import pandas as pd

try:
    from scripts.grounded_probe import CANDIDATES
    from scripts.probe_repair import validate_probe_pair
    from scripts.p5_repeat_feedback import atomic_json,digest
    from scripts.analyze_feedback_controls import contrast
except ModuleNotFoundError:
    from grounded_probe import CANDIDATES
    from probe_repair import validate_probe_pair
    from p5_repeat_feedback import atomic_json,digest
    from analyze_feedback_controls import contrast


def select_winner(data):
    wide=data.pivot(index='job_id',columns='arm',values='terminal_success').astype(int)
    counts=data.groupby('arm').terminal_target_drop_candidate.sum()
    queries=data.groupby('arm').query_count.mean()
    decisions=[]
    for candidate in CANDIDATES:
        if candidate not in wide:continue
        delta=float((wide[candidate]-wide.physical_regrasp).mean())
        tests=dict(gain_at_least_5pp=delta>=.05,
            beats_continue=bool((wide[candidate]-wide.continue_h8).mean()>0),
            no_more_drop=bool(counts[candidate]<=counts['physical_regrasp']),
            query_ratio_at_most_1p5=bool(queries[candidate]<=1.5*max(queries['physical_regrasp'],1)))
        if candidate.startswith('mask_verify'):
            tests.update(beats_probe_always=bool((wide[candidate]-wide.probe_always_regrasp).mean()>0),
                not_worse_than_legacy=bool((wide[candidate]-wide.probe_verify_repair).mean()>=0))
            selected=data[data.arm.eq(candidate)]
            tests['at_least_four_skips']=int((selected.initial_trigger_passed&~selected.repair_requested).sum())>=4
        decisions.append(dict(arm=candidate,delta=delta,tests=tests,pass_gate=all(tests.values())))
    eligible=[x for x in decisions if x['pass_gate']]
    winner=max(eligible,key=lambda x:(x['delta'],-CANDIDATES.index(x['arm'])))['arm'] if eligible else None
    return winner,decisions


def analyze(directory,phase):
    cfg=json.loads((directory/'config.json').read_text())
    plan=json.loads((directory/'phase_plan.json').read_text());arms=plan[phase]
    jobs=[j for j in cfg['jobs'] if j['phase']==phase];rows=[];missing=[]
    freeze_sha=digest(directory/'mask_model/freeze.json')
    for job in jobs:
        d=directory/phase/job['id']
        if not (d/'completed.json').exists():missing.append(job['id']);continue
        if json.loads((d/'completed.json').read_text())['arms']!=arms:raise ValueError('Arms changed')
        meta=json.loads((d/'prefix.json').read_text())
        if digest(d/'prefix.npz')!=meta['sha256']:raise ValueError('Changed prefix')
        probes=[]
        for arm in arms:
            row=json.loads((d/(arm+'.json')).read_text())
            for key in ('job_id','rollout_seed','cell','task_id','init_state_id','repeat','phase'):
                if row[key]!=job['id' if key=='job_id' else key]:raise ValueError('Identity mismatch: '+key)
            if row['arm']!=arm or row['prefix_sha256']!=meta['sha256'] or row['mask_freeze_sha256']!=freeze_sha:
                raise ValueError('Frozen identity mismatch')
            for ext,key in (('.npz','npz_sha256'),('.mp4','video_sha256')):
                if digest(d/(arm+ext))!=row[key]:raise ValueError('Changed artifact')
            with np.load(d/(arm+'.npz'),allow_pickle=False) as z:
                if len(z['executed_actions'])!=row['terminal_final_t']-meta['t']:raise ValueError('Physical step accounting')
                np.testing.assert_array_equal(z['frame_t'],np.arange(meta['t'],row['terminal_final_t']+1))
                if len(z['frame_t'])!=row['video_frames']:raise ValueError('Frame accounting')
                if not np.isfinite(z['executed_actions']).all():raise ValueError('Nonfinite action')
            for q,query in enumerate(row['queries'],start=5):
                if query['seeds']!=[job['rollout_seed']+q*1000+i for i in range(4)]:raise ValueError('Suffix query seed accounting')
            inter=row['intervention']
            if 'probe_end_audit' in inter:probes.append(inter['probe_end_audit'])
            row.update(verification=inter['verification'],probe_steps=inter['probe_steps'],query_count=len(row['queries']),
                repair_requested=inter.get('repair_requested',False),initial_trigger_passed=inter['initial_trigger_passed'])
            rows.append(row)
        for other in probes[1:]:validate_probe_pair(probes[0],other)
    out=directory/'analysis'/phase;out.mkdir(parents=True,exist_ok=True)
    summary=dict(phase=phase,complete=not missing,missing=missing,pairs=len(rows)//len(arms),branches=len(rows),arms=arms)
    if not rows:atomic_json(out/'summary.json',summary);return summary
    data=pd.DataFrame(rows)
    scores=data.groupby(['cell','arm']).agg(n=('terminal_success','size'),successes=('terminal_success','sum'),
        sr=('terminal_success','mean'),drop_count=('terminal_target_drop_candidate','sum'),
        queries=('query_count','mean'),repair_rate=('repair_requested','mean'),final_t=('terminal_final_t','mean')).reset_index()
    scores.to_csv(out/'scores.csv',index=False)
    data.drop(columns=['queries']).to_json(out/'branch_outcomes.json',orient='records',indent=2)
    effects=[]
    for candidate in CANDIDATES:
        if candidate not in arms:continue
        for control in ('physical_regrasp','continue_h8','probe_always_regrasp'):
            if control not in arms:continue
            effects.append(contrast(data,candidate,control))
    if phase=='transfer':effects.append(contrast(data,'physical_regrasp','continue_h8'))
    e=pd.DataFrame(effects)
    if len(e):
        order=e.sort_values('cluster_sign_p').index
        e.loc[order,'holm_p']=np.minimum(1,np.maximum.accumulate(e.loc[order,'cluster_sign_p'].to_numpy()*np.arange(len(e),0,-1)))
        e.to_csv(out/'paired_effects.csv',index=False)
    if phase=='screen' and not missing:
        winner,decisions=select_winner(data);summary.update(winner=winner,selection=decisions,holdout_gate_pass=winner is not None)
    if phase=='holdout' and not missing:
        winner=plan['winner'];primary=e[e.left.eq(winner)&e.right.eq('physical_regrasp')].iloc[0]
        d=data.groupby('arm').terminal_target_drop_candidate.sum()
        summary['confirmatory_pass']=bool(primary.ci_low>0 and primary.holm_p<=.05 and d[winner]<=d['physical_regrasp'])
    summary.update(effects=e.to_dict('records'),totals=data.groupby('arm').terminal_success.agg(['sum','count','mean']).reset_index().to_dict('records'))
    atomic_json(out/'summary.json',summary)
    gallery=['<!doctype html><meta charset="utf-8"><title>Grounded recovery</title>',
        '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}video{width:320px;max-width:100%}</style>']
    for case,group in data.groupby('job_id'):
        gallery.append('<h2>'+html.escape(case)+'</h2><div class="row">')
        for arm in arms:
            row=group[group.arm.eq(arm)].iloc[0]
            gallery.append(f'<figure><figcaption>{arm}: {bool(row.terminal_success)} / {row.verification}</figcaption><video controls preload="none" src="../../{phase}/{case}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (out/'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(13,6),layout='constrained')
    scores.pivot(index='cell',columns='arm',values='sr').reindex(columns=arms).plot.bar(ax=ax)
    ax.set(ylabel='Terminal SR',ylim=(0,1));fig.savefig(out/'success_rates.png',dpi=160);plt.close(fig)
    (out/'RESULTS.md').write_text('\n'.join(['# Grounded recovery: '+phase,'',
        'All arms share t72 prefix. Fixed timing, K4/H8 suffix, physical budget 280; not a full benchmark.',
        'Masks use RGB only online. Calibration supervision is simulator-derived; separate group validation.',
        'Primary comparison is against physical regrasp, not just continue. Smoke is technical, not scientific evidence.',
        '',scores.to_markdown(index=False),'','![SR](success_rates.png)','[Videos](videos.html)',
        '','```json',json.dumps(summary,indent=2),'```'])+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',required=True,type=Path);p.add_argument('--phase',required=True)
    args=p.parse_args();analyze(args.campaign,args.phase)

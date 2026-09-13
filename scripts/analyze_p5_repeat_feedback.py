#!/usr/bin/env python3
"""Grouped paired feedback effects and suffix-label stability; no learned selector."""
from __future__ import annotations

import argparse
import html
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.p5_repeat_feedback import atomic_json
except ModuleNotFoundError:
    from p5_repeat_feedback import atomic_json


def paired_effect(rows,left,right):
    values=rows.pivot(index=['pool_id','task_id','init_state_id','repeat'],columns='mode',values='terminal_success')
    if left not in values or right not in values:return None
    paired=values.dropna(subset=[left,right]).reset_index()
    if not len(paired):return None
    paired['delta']=paired[left].astype(int)-paired[right].astype(int)
    clusters=paired.groupby(['task_id','init_state_id']).delta.agg(['sum','count'])
    rng=np.random.default_rng(20260910)
    idx=rng.integers(len(clusters),size=(5000,len(clusters)))
    estimates=clusters['sum'].to_numpy()[idx].sum(1)/clusters['count'].to_numpy()[idx].sum(1)
    observed=abs(paired.delta.sum())
    totals=clusters['sum'].to_numpy()
    if len(clusters)>20:raise ValueError('Exact cluster sign flip limit exceeded')
    p=np.mean([abs(np.dot(signs,totals))>=observed-1e-12 for signs in itertools.product((-1,1),repeat=len(clusters))])
    return dict(method=left,reference=right,pairs=len(paired),task_init_clusters=len(clusters),
        delta_sr=float(paired.delta.mean()),ci95_low=float(np.quantile(estimates,.025)),
        ci95_high=float(np.quantile(estimates,.975)),rescues=int(paired.delta.eq(1).sum()),
        harms=int(paired.delta.eq(-1).sum()),cluster_signflip_p=float(p))


def analyze(directory):
    cfg=json.loads((directory/'config.json').read_text())
    records=[json.loads(p.read_text()) for p in sorted((directory/'runs').glob('*/r*_c*_*.json'))]
    output=directory/'analysis';output.mkdir(exist_ok=True)
    full=len(records)==cfg['expected_branches'] and all((directory/'runs'/p['id']/'completed.json').exists() for p in cfg['pools'])
    summary=dict(status='completed' if full else 'partial',branches=len(records),expected_branches=cfg['expected_branches'],
        development_only=True,full_episode_new_controller_test=False,primary_comparison=cfg['primary_comparison'],
        original_state_action_groups=18,task_init_clusters=10)
    if not records:
        atomic_json(output/'summary.json',summary);return
    data=pd.DataFrame(records)
    if data.duplicated(['pool_id','repeat','candidate_idx','mode']).any():raise ValueError('Duplicate branches')
    if not data.prefix_integrity.eq(True).all() or not data.terminal_available.eq(True).all():raise ValueError('Invalid branches')
    for pool_id,g in data.groupby('pool_id'):
        audit=json.loads((directory/'runs'/pool_id/'replay_audit.json').read_text())
        if not audit['passed']:raise ValueError('Replay audit failed')
        source=next(p for p in cfg['pools'] if p['id']==pool_id)
        if not g.source_sha256.eq(source['sidecar_sha256']).all():raise ValueError('Wrong pool source')
    data.to_parquet(output/'branch_outcomes.parquet',index=False)
    selected=data[data.selected]
    scores=selected.groupby('mode').agg(branches=('terminal_success','size'),successes=('terminal_success','sum'),
        sr=('terminal_success','mean'),drop_proxy=('terminal_target_drop_candidate','sum'),
        wrong_object_proxy=('terminal_wrong_object_interaction_candidate','sum'),
        continuation_queries=('terminal_continuation_queries','mean'),extra_queries=('additional_queries','mean')).reset_index()
    scores.to_csv(output/'selected_candidate_scores.csv',index=False)
    effects=pd.DataFrame([v for v in [paired_effect(selected,'fresh8','stale8'),paired_effect(selected,'fresh8','open16')] if v])
    if len(effects):
        order=effects.sort_values('cluster_signflip_p').index
        effects.loc[order,'holm_p']=np.minimum(1,np.maximum.accumulate(effects.loc[order,'cluster_signflip_p'].to_numpy()*np.arange(len(effects),0,-1)))
    effects.to_csv(output/'paired_effects.csv',index=False)
    base=data[data['mode'].eq('open16')]
    stability=base.groupby(['pool_id','candidate_idx']).agg(repeats=('repeat','nunique'),
        successes=('terminal_success','sum'),estimated_q=('terminal_success','mean'),value=('candidate_value','first')).reset_index()
    stability['label_varies']=stability.successes.gt(0)&stability.successes.lt(stability.repeats)
    stability.to_csv(output/'candidate_suffix_stability.csv',index=False)
    original=pd.read_parquet(cfg['source'])
    old=original[['case_id','task_id','init_state_id','query_idx','candidate_idx','terminal_success']].rename(columns={'terminal_success':'original_success'})
    joined=base.merge(old,on=['case_id','task_id','init_state_id','query_idx','candidate_idx'],validate='many_to_one')
    if len(joined)!=len(base):raise ValueError('Original-label mapping incomplete')
    summary['changed_from_original_fraction']=float(joined.terminal_success.ne(joined.original_success).mean())
    completed=stability[stability.repeats.eq(3)]
    summary['repeated_candidates_complete']=len(completed)
    summary['fraction_candidates_with_variable_label']=float(completed.label_varies.mean()) if len(completed) else None
    opportunities=[]
    for pool,g in stability.groupby('pool_id'):
        if len(g)!=8 or not g.repeats.eq(3).all():continue
        for k in (4,8):
            candidates=g[g.candidate_idx.lt(k)].sort_values('candidate_idx')
            best=candidates.iloc[int(np.argmax(candidates.value.to_numpy()))]
            opportunities.append(dict(pool_id=pool,k=k,max_value_mean_success=float(best.estimated_q),
                empirical_best_mean_success=float(candidates.estimated_q.max()),
                all_measured_fail=bool(candidates.successes.sum()==0)))
    pd.DataFrame(opportunities).to_csv(output/'repeated_selection_opportunity.csv',index=False)
    summary['paired_comparisons']=effects.to_dict('records')
    atomic_json(output/'summary.json',summary)
    gallery=['<!doctype html><meta charset="utf-8"><title>P5 saved-state comparisons</title>',
        '<style>body{font:15px sans-serif;margin:24px}.row{display:flex;flex-wrap:wrap;gap:16px}video{width:400px;max-width:100%}figure{margin:0}h2{font-size:18px}</style>']
    for pool in cfg['pools']:
        videos=selected[selected.pool_id.eq(pool['id'])&selected.repeat.eq(0)]
        if not len(videos):continue
        gallery.append('<h2>'+html.escape(f"{pool['case_id']} task{pool['task_id']} init{pool['init_state_id']} q{pool['query_idx']}; starts at t={pool['t']}")+'</h2><div class="row">')
        for row in videos.sort_values('mode').itertuples():
            if row.video_path and Path(row.video_path).exists():
                gallery.append(f'<figure><figcaption>{row.mode}: success={row.terminal_success}</figcaption><video controls preload="none" src="{html.escape(str(Path(row.video_path).relative_to(directory.parent)),quote=True)}"></video></figure>')
        gallery.append('</div>')
    # HTML lives at campaign root so paths remain portable with the runs directory.
    content='\n'.join(gallery).replace(f'src="{directory.name}/','src="')
    (directory/'videos.html').write_text(content)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ax=scores.set_index('mode').sr.mul(100).plot.bar(color=['#167d8d','#a04459','#617c3e'],rot=0,ylim=(0,100))
    ax.set_ylabel('Snapshot branch success (%)');ax.set_title('Repeated saved-state intervention: development')
    ax.figure.tight_layout();ax.figure.savefig(output/'selected_candidate_success.png',dpi=160);plt.close(ax.figure)
    report=['# P5 suffix repeats and matched feedback','',f"Status: {summary['status']}; {len(records)}/{cfg['expected_branches']} branches.",
        'Fixed development states; not a newly trained P5 head or full closed-loop controller deployment.','',
        scores.to_markdown(index=False),'',effects.to_markdown(index=False),'',
        'Bootstrap and sign flips keep both queries, all suffix repeats and perturbation variants together by task/init.',
        'Partial tables may have unequal support and must not be used as final method rankings.',
        'Fresh/stale use one extra K1 call; stale consumes the aligned second half from the old observation.',
        'All arms continue with the same K1/H16 policy and absolute-time seed schedule after t+16.',
        'The empirical best mean over three suffixes is an optimistic diagnostic, not true optimal Q.',
        'Label variation includes stochastic suffix sampling and residual numerical nondeterminism.',
        '',json.dumps(summary,indent=2),'','[Videos](../videos.html)']
    (output/'RESULTS.md').write_text('\n'.join(report)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--campaign',type=Path,required=True)
    analyze(parser.parse_args().campaign)

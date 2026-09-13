#!/usr/bin/env python3
"""Strict paired, init-clustered mechanism screen; no automatic method promotion."""
import argparse
import html
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.feedback_controls import ARMS, CONTRASTS, job_done
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from feedback_controls import ARMS, CONTRASTS, job_done
    from p5_repeat_feedback import atomic_json, digest


def contrast(data, left, right):
    index = ['cell','init_state_id','repeat']
    wide = data.pivot(index=index, columns='arm', values='terminal_success')
    paired = wide[[left,right]].dropna().astype(int)
    difference = paired[left]-paired[right]
    clusters = difference.groupby(level=['cell','init_state_id']).mean()
    rng = np.random.default_rng(20260910)
    boot = []
    for cell in clusters.index.get_level_values('cell').unique():
        values = clusters.loc[cell].to_numpy()
        boot.append(values[rng.integers(len(values),size=(5000,len(values)))].mean(axis=1))
    draws = np.mean(boot,axis=0)
    # Equal weighting of fixed cells; independent units are init clusters, not suffix repeats.
    weights = np.array([1 / len(clusters.loc[cell]) / len(boot) for cell,_ in clusters.index])
    contributions = clusters.to_numpy()*weights
    effect = float(contributions.sum())
    if len(clusters) <= 16:
        signs = np.asarray(list(itertools.product((-1,1), repeat=len(clusters))))
    else:
        signs = rng.choice((-1,1),size=(100000,len(clusters)))
    p = float(np.mean(np.abs(signs@contributions) >= abs(effect)-1e-12))
    return dict(left=left, right=right, pairs=len(paired), clusters=len(clusters),
        delta=effect, ci_low=float(np.quantile(draws,.025)), ci_high=float(np.quantile(draws,.975)),
        rescues=int(difference.eq(1).sum()), harms=int(difference.eq(-1).sum()), cluster_sign_p=p)


def analyze(directory):
    config = json.loads((directory/'config.json').read_text())
    output = directory/'analysis'
    output.mkdir(exist_ok=True)
    jobs = [j for j in config['jobs'] if j['phase']=='screen']
    rows, skipped, incomplete = [], [], []
    for job in jobs:
        path = directory/'screen'/job['id']
        if not job_done(directory,job):
            incomplete.append(job['id'])
            continue
        marker = json.loads((path/'completed.json').read_text())
        if marker['status']=='skipped':
            skipped.append(dict(job_id=job['id'], reason=marker['reason']))
            continue
        meta = json.loads((path/'pool.json').read_text())
        if digest(path/'pool.npz') != meta['sha256']:
            raise ValueError('Pool hash mismatch')
        for arm in ARMS:
            row = json.loads((path/(arm+'.json')).read_text())
            if row['pool_sha256'] != meta['sha256'] or row['fresh_input_hashes'] != meta['fresh_input_hashes']:
                raise ValueError('Input integrity mismatch')
            if row['arm'] != arm:
                raise ValueError('Wrong arm')
            rows.append(row)
    summary = dict(status='partial' if incomplete else 'completed', planned_branches=120,
        complete_case_branches=len(rows), excluded_before_decision=skipped, incomplete=incomplete,
        screen_only=True, automatic_holdout=False, full_benchmark_score=False,
        inference='stratified init-cluster bootstrap and cluster sign-flip; three-contrast Holm',
        success_before_decision_excluded_not_counted_as_fail=True)
    atomic_json(output/'summary.json',summary)
    if not rows:
        return summary
    data = pd.DataFrame(rows)
    if data.duplicated(['job_id','arm']).any():
        raise ValueError('Duplicate branches')
    data.drop(columns=['suffix_inputs']).to_json(output/'branch_outcomes.json',orient='records',indent=2)
    scores = data.groupby(['cell','arm']).agg(n=('terminal_success','size'),
        successes=('terminal_success','sum'), sr=('terminal_success','mean'),
        drop_proxy=('terminal_target_drop_candidate','mean'),
        final_t=('terminal_final_t','mean'), logical_suffix_candidates=('logical_suffix_candidates','mean'),
        logical_requery_candidates=('logical_requery_candidates','mean')).reset_index()
    scores.to_csv(output/'scores.csv',index=False)
    effects = pd.DataFrame()
    if not incomplete:
        effects = pd.DataFrame([contrast(data,left,right) for left,right in CONTRASTS])
        order = effects.sort_values('cluster_sign_p').index
        effects.loc[order,'holm_p'] = np.minimum(1,np.maximum.accumulate(
            effects.loc[order,'cluster_sign_p'].to_numpy()*np.arange(3,0,-1)))
        effects.to_csv(output/'paired_effects.csv',index=False)
        summary['contrasts'] = effects.to_dict('records')
    atomic_json(output/'summary.json',summary)
    gallery = ['<!doctype html><meta charset="utf-8"><title>Matched feedback controls</title>',
        '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}video{width:370px;max-width:100%}</style>']
    for job, group in data.groupby('job_id'):
        gallery.append('<h2>'+html.escape(job)+'</h2><div class="row">')
        for arm in ARMS:
            row = group[group.arm.eq(arm)].iloc[0]
            gallery.append(f'<figure><figcaption>{arm}: success={bool(row.terminal_success)}</figcaption>'
                f'<video controls preload="none" src="../screen/{job}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (output/'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11,5),layout='constrained')
    scores.pivot(index='cell',columns='arm',values='sr').reindex(columns=ARMS).plot.bar(ax=ax)
    ax.set(ylabel='Conditional terminal success rate',ylim=(0,1),xlabel='Fixed cell')
    ax.tick_params(axis='x',labelrotation=0)
    fig.savefig(output/'success_rates.png',dpi=160)
    plt.close(fig)
    report = ['# Matched feedback controls', '', f'Status: {summary["status"]}; {len(rows)}/120 branches in complete cases.',
        'Mechanism screen, not confirmatory transfer evidence. All prefix and suffix policies use K4/H16.',
        'K1 is candidate zero of the same fresh K4 pool. Shared generation reduces collection cost; logical policy costs differ.',
        'Stale-tail control is not conditioned on the executed first eight actions.',
        'Videos start at t=48 or t=64, not at episode reset. Safety columns are local project proxies.',
        '', scores.to_markdown(index=False), '',
        effects.to_markdown(index=False) if len(effects) else 'Paired inference withheld until all cases finish.',
        '', '![Success](success_rates.png)', '', '[Videos](videos.html)',
        '', 'No controller or coefficient is promoted automatically; inspect harms and plan an independent confirmation.']
    (output/'RESULTS.md').write_text('\n'.join(report)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign',type=Path,required=True)
    print(json.dumps(analyze(parser.parse_args().campaign),indent=2))

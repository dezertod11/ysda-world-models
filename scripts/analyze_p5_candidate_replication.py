#!/usr/bin/env python3
"""Predeclared pair replication; separate exploratory new-pool diagnostics."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from scripts.analyze_p5_repeat_feedback import paired_effect
    from scripts.p5_repeat_feedback import atomic_json, digest
    from scripts.p5_candidate_replication import branch_schedule
except ModuleNotFoundError:
    from analyze_p5_repeat_feedback import paired_effect
    from p5_repeat_feedback import atomic_json, digest
    from p5_candidate_replication import branch_schedule


def split_candidate(outcomes, values, test_repeats):
    train_repeats = [r for r in outcomes.columns if r not in test_repeats]
    means = outcomes[train_repeats].mean(axis=1)
    tied = means.index[means.eq(means.max())]
    return int(values.loc[tied].idxmax())


def analyze(directory):
    config = json.loads((directory/'config.json').read_text())
    output = directory/'analysis'
    output.mkdir(exist_ok=True)
    files = sorted((directory/'runs').glob('*/r*_c*.json'))
    rows = [json.loads(p.read_text()) for p in files]
    excluded = []
    complete_jobs = []
    for job in config['jobs']:
        path = directory/'runs'/job['id']/'completed.json'
        if path.exists():
            marker = json.loads(path.read_text())
            if marker['status'] == 'skipped':
                excluded.append(dict(job_id=job['id'], reason=marker['reason']))
            else:
                complete_jobs.append(job['id'])
    summary = dict(status='completed' if len(complete_jobs)+len(excluded) == 10 else 'partial',
        completed_jobs=complete_jobs, excluded=excluded, branches=len(rows), planned_branches=690,
        conditional_same_state_replication=True, full_episode_new_controller=False,
        neighbor_init_is_not_globally_untouched=True)
    if not rows:
        atomic_json(output/'summary.json', summary)
        return
    data = pd.DataFrame(rows)
    assert not data.duplicated(['job_id', 'repeat', 'candidate_idx']).any()
    assert data.terminal_available.all()
    for job in config['jobs']:
        group = data[data.job_id.eq(job['id'])]
        if group.empty:
            continue
        meta = json.loads((directory/'pools'/f'{job["id"]}.json').read_text())
        assert digest(directory/'pools'/f'{job["id"]}.npz') == meta['sha256']
        assert group.pool_sha256.eq(meta['sha256']).all()
        expected = set(branch_schedule(job))
        actual = set(group[['repeat','candidate_idx','suffix_seed']].itertuples(index=False, name=None))
        assert actual <= expected
        if job['id'] in complete_jobs:
            assert actual == expected
        assert json.loads((directory/'runs'/job['id']/'replay_audit.json').read_text())['passed']
    data.to_parquet(output/'branch_outcomes.parquet', index=False)
    scores = data.groupby(['kind','job_id','candidate_idx','selected']).agg(branches=('terminal_success','size'),
        successes=('terminal_success','sum'), sr=('terminal_success','mean'), value=('candidate_value','first'),
        contact_steps=('local_contact_steps','mean'), local_lift=('local_target_lift_max','mean'),
        local_drop=('local_drop','mean'), terminal_drop=('terminal_target_drop_candidate','mean')).reset_index()
    scores.to_csv(output/'candidate_scores.csv', index=False)
    effects = []
    for job, alternative, baseline in config['primary_pairs']:
        if job not in complete_jobs:
            continue
        group = data[data.job_id.eq(job)].pivot(index='repeat', columns='candidate_idx', values='terminal_success')
        delta = group[alternative].astype(int)-group[baseline].astype(int)
        rescue, harm = int(delta.eq(1).sum()), int(delta.eq(-1).sum())
        rng = np.random.default_rng(20260910)
        samples = delta.to_numpy()[rng.integers(len(delta), size=(5000, len(delta)))].mean(axis=1)
        effects.append(dict(job_id=job, alternative=alternative, baseline=baseline, pairs=len(delta),
            delta=float(delta.mean()), ci_low=float(np.quantile(samples,.025)), ci_high=float(np.quantile(samples,.975)),
            rescues=rescue, harms=harm, p=float(binomtest(rescue,rescue+harm,.5).pvalue) if rescue+harm else 1.0))
    effects = pd.DataFrame(effects)
    if len(effects):
        order = effects.sort_values('p').index
        effects.loc[order, 'holm_p'] = np.minimum(1, np.maximum.accumulate(effects.loc[order, 'p'].to_numpy()*np.arange(3,3-len(effects),-1)))
        effects['conditional_replication_pass'] = effects.delta.ge(.3)&effects.holm_p.le(.05)&effects.pairs.eq(10)
        effects.to_csv(output/'fixed_pair_effects.csv', index=False)
        summary['fixed_pair_effects'] = effects.to_dict('records')
    cv_rows, pools = [], []
    for job_id, group in data[data.kind.eq('neighbor')].groupby('job_id'):
        if job_id not in complete_jobs:
            continue
        matrix = group.pivot(index='candidate_idx', columns='repeat', values='terminal_success').astype(int)
        values = group.groupby('candidate_idx').candidate_value.first().sort_index()
        baseline = int(values.idxmax())
        pools.append(dict(job_id=job_id, max_value_sr=float(matrix.loc[baseline].mean()),
                          same_repeat_best_sr=float(matrix.mean(axis=1).max()),
                          all_measured_fail=not bool(matrix.to_numpy().any())))
        for test in config['neighbor_split']:
            chosen = split_candidate(matrix, values, test)
            for repeat in test:
                for mode, index in [('split_selector',chosen), ('max_value',baseline)]:
                    cv_rows.append(dict(pool_id=job_id, task_id=int(group.task_id.iloc[0]),
                        init_state_id=int(group.init_state_id.iloc[0]), repeat=repeat, mode=mode,
                        candidate_idx=index, terminal_success=int(matrix.loc[index,repeat])))
    if cv_rows:
        cv = pd.DataFrame(cv_rows)
        cv.to_csv(output/'neighbor_split_predictions.csv', index=False)
        summary['neighbor_split_effect'] = paired_effect(cv,'split_selector','max_value')
        pd.DataFrame(pools).to_csv(output/'neighbor_pool_summary.csv', index=False)
    local_cols = ['local_contact_steps','local_target_lift_max','local_drop','local_wrong_object','local_goal_progress_end']
    local_variation = data.groupby(['job_id','candidate_idx'])[local_cols].nunique(dropna=False)
    summary['local_metrics_variable_groups'] = int(local_variation.gt(1).any(axis=1).sum())
    atomic_json(output/'summary.json', summary)
    gallery = ['<!doctype html><meta charset="utf-8"><title>Candidate replication</title>',
        '<style>body{font:15px sans-serif;margin:24px}.row{display:flex;flex-wrap:wrap;gap:16px}video{width:400px;max-width:100%}figure{margin:0}h2{font-size:18px}</style>']
    for (job, repeat), group in data[data.video_path.notna()].groupby(['job_id','repeat']):
        gallery.append(f'<h2>{html.escape(job)}; repeat {repeat}; starts at t=48</h2><div class="row">')
        for row in group.sort_values('candidate_idx').itertuples():
            assert (directory / row.video_path).exists()
            caption = f'candidate {row.candidate_idx}; max-value={row.selected}; success={row.terminal_success}'
            gallery.append(f'<figure><figcaption>{html.escape(caption)}</figcaption><video controls preload="none" src="{html.escape(row.video_path,quote=True)}"></video></figure>')
        gallery.append('</div>')
    (directory/'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1,2, figsize=(10,4), layout='constrained')
    for ax, job in zip(axes, ['repeat_pool_13','repeat_pool_11']):
        subset = scores[scores.job_id.eq(job)]
        ax.bar(subset.candidate_idx.astype(str), subset.sr*100,
               color=['#555f66' if s else '#257f88' for s in subset.selected])
        ax.set(title=job, xlabel='Frozen candidate index', ylabel='Conditional success (%)', ylim=(0,100))
    fig.savefig(output/'fixed_candidate_success.png', dpi=160)
    plt.close(fig)
    report = ['# Conditional candidate replication', '', f'Status: {summary["status"]}; {len(data)}/690 planned branches.',
        'Fixed pairs selected on prior development; new suffix seeds test only conditional replication.',
        'Neighbor pools are a diagnostic, not a deployable selector transfer benchmark. Partial results are not final.',
        '', scores.to_markdown(index=False), '', effects.to_markdown(index=False) if len(effects) else 'Fixed pairs incomplete.',
        '', 'Local contact/lift/goal metrics are measured during [48,64]; terminal outcomes include later continuation.',
        'Simulator signals are retrospective diagnostics, not online policy inputs.', '', '[Videos](../videos.html)',
        '', '```json', json.dumps(summary,indent=2), '```']
    (output/'RESULTS.md').write_text('\n'.join(report)+'\n')
    print(json.dumps(summary,indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    analyze(parser.parse_args().campaign)

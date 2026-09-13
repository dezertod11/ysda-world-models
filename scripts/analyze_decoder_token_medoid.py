#!/usr/bin/env python3
"""Matched outcomes, task-cluster intervals, traces and four-way video gallery."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from scripts.decoder_token_medoid import ARMS
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from decoder_token_medoid import ARMS
    from p5_repeat_feedback import atomic_json, digest


def matched_tables(rows, expected=180):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return dict(complete_pairs=0, expected_pairs=expected, partial=True), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if frame.duplicated(['id', 'arm']).any():
        raise ValueError('Duplicate rollout identity')
    pivot = frame.pivot(index='id', columns='arm', values='terminal_success').reindex(columns=ARMS)
    complete = pivot.dropna().astype(int)
    matched = frame[frame['id'].isin(complete.index)].copy()
    if matched.empty:
        return dict(complete_pairs=0, expected_pairs=expected, partial=True), pd.DataFrame(), pd.DataFrame(), matched
    for name in ('initial_sha256', 'q0_pool_sha256', 'task_description', 'env_seed'):
        if matched.groupby('id')[name].nunique().max() != 1:
            raise ValueError('Paired contract differs: ' + name)
    rates = matched.groupby(['factor', 'arm']).agg(n=('terminal_success', 'size'),
        successes=('terminal_success', 'sum'), micro_sr=('terminal_success', 'mean'),
        mean_steps=('terminal_final_t', 'mean'), mean_seconds=('elapsed_seconds', 'mean'),
        mean_candidate_calls=('candidate_calls_logical', 'mean')).reset_index()
    task_sr = matched.groupby(['factor', 'arm', 'task_id']).terminal_success.mean()
    task_sr = task_sr.groupby(['factor', 'arm']).mean().rename('sr').reset_index()
    rates = rates.merge(task_sr, on=['factor', 'arm'], validate='one_to_one')
    metadata = matched.drop_duplicates('id').set_index('id')[['factor', 'task_id']]
    rng = np.random.default_rng(20260911)
    comparisons = []
    for arm in ARMS:
        if arm == 'max_value':
            continue
        diff = (complete[arm] - complete['max_value']).rename('difference')
        groups = metadata.join(diff)
        taskmeans = groups.groupby(['factor', 'task_id'])['difference'].mean()
        bootstrap = []
        for factor in sorted(groups.factor.unique()):
            values = taskmeans.loc[factor].to_numpy()
            bootstrap.append(rng.choice(values, size=(10000, len(values)), replace=True).mean(1))
        boot = np.mean(bootstrap, axis=0)
        low, high = np.quantile(boot, [.025, .975])
        macro_delta = taskmeans.groupby(level='factor').mean().mean()
        rescue, harm = int((diff == 1).sum()), int((diff == -1).sum())
        p = binomtest(rescue, rescue + harm, .5).pvalue if rescue + harm else 1.
        comparisons.append(dict(arm=arm, paired_n=len(complete), macro_delta=float(macro_delta),
            cluster_ci_low=float(low), cluster_ci_high=float(high), rescue=rescue, harm=harm,
            mcnemar_descriptive_p=float(p)))
    comparisons = pd.DataFrame(comparisons)
    summary = dict(complete_pairs=len(complete), expected_pairs=expected, partial=len(complete) != expected,
        available_rollouts=len(frame), matched_rollouts=len(matched),
        missing_pair_ids=pivot.index[pivot.isna().any(axis=1)].tolist(),
        primary='decoder_medoid_vs_max_value',
        inference='Development transfer; task-cluster bootstrap stratified by factor. Seeds/inits retained within tasks. McNemar is descriptive, repeated seeds are dependent.',
        claim='No confirmatory generalization claim, even for a positive development effect.',
        macro_sr=rates.groupby('arm').sr.mean().to_dict())
    return summary, rates, comparisons, matched


def write_visuals(directory, output, rates, matched, originals):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if rates.empty:
        return
    table = rates.pivot(index='factor', columns='arm', values='sr').reindex(columns=ARMS)
    ax = table.plot.bar(figsize=(10, 4), ylim=(0, 1), rot=0)
    ax.set_ylabel('Success rate')
    ax.set_title('Paired completed configurations only')
    ax.figure.tight_layout()
    ax.figure.savefig(output / 'success_rates.png', dpi=160)
    plt.close(ax.figure)
    by_id = {}
    for row in originals:
        by_id.setdefault(row['id'], {})[row['arm']] = row
    complete_ids = matched.id.drop_duplicates().tolist()
    parts = ['<!doctype html><meta charset="utf-8"><title>Decoder medoid comparison</title>',
             '<style>body{font:14px sans-serif;margin:20px}table{width:100%;table-layout:fixed}td{vertical-align:top}video{width:100%}th{text-align:left}h2{font-size:18px}</style>',
             '<h1>Full rollouts, paired initial states</h1><p>Videos: both cameras, 20 fps, all executed steps. No success-based trimming.</p>']
    for identifier in complete_ids:
        rows = by_id[identifier]
        parts.append(f'<h2>{html.escape(identifier)}</h2><p>{html.escape(rows["first"]["task_description"])}</p><table><tr>')
        for arm in ARMS:
            row = rows[arm]
            parts.append(f'<th>{arm}: {row["terminal_success"]}, {row["terminal_final_t"]} steps</th>')
        parts.append('</tr><tr>')
        for arm in ARMS:
            phase = html.escape(rows[arm]['phase'])
            parts.append(f'<td><video controls preload="none" src="../{phase}/{html.escape(identifier)}/{arm}.mp4"></video></td>')
        parts.append('</tr></table>')
    (output / 'video_comparison.html').write_text('\n'.join(parts), encoding='utf-8')
    # Keep diagnostic trace count bounded; all per-query numbers remain in CSV.
    for identifier in complete_ids[:12]:
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
        for arm, row in by_id[identifier].items():
            q = row['queries']
            for ax, metric in zip(axes, ('value_std', 'action_first_step_l2_std', 'future_proprio_std_mean')):
                ax.plot([x['t'] for x in q], [x['metrics'].get(metric, np.nan) for x in q], '.-', label=arm)
                ax.set_ylabel(metric)
        axes[0].legend()
        axes[0].set_title(identifier + ' (pre-execution query metrics)')
        axes[-1].set_xlabel('Executed action steps before query')
        fig.tight_layout()
        fig.savefig(output / (identifier + '__metrics.png'), dpi=120)
        plt.close(fig)


def analyze(directory, phase='screen'):
    output = directory / 'analysis'
    output.mkdir(exist_ok=True)
    rows, queries, originals = [], [], []
    for path in sorted((directory / phase).glob('*/*.json')):
        if path.stem not in ARMS:
            continue
        row = json.loads(path.read_text())
        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
            if digest(path.with_suffix(ext)) != row[key]:
                raise ValueError('Changed committed artifact ' + str(path))
        if row['video_frames'] != row['terminal_final_t'] + 1:
            raise ValueError('Video is not full-length')
        originals.append(row)
        rows.append({k: v for k, v in row.items() if k != 'queries' and not isinstance(v, (dict, list))})
        for q in row['queries']:
            queries.append(dict(id=row['id'], arm=row['arm'], factor=row['factor'],
                seed_group=row['seed_group'], selected_seed=q['candidate_seeds'][q['index']],
                terminal_success=row['terminal_success'], query=q['query'], t=q['t'], t_after=q['t_after'],
                selected=q['index'], **q['metrics'], **q['prediction_errors']))
    expected = 180 if phase == 'screen' else 1
    summary, rates, comparisons, matched = matched_tables(rows, expected=expected)
    summary['integration_only'] = phase != 'screen'
    if queries:
        qframe = pd.DataFrame(queries)
        frequency = qframe.groupby(['id', 'factor', 'seed_group', 'arm', 'selected']).size().rename('count').reset_index()
        frequency['fraction'] = frequency['count'] / frequency.groupby(['id', 'arm'])['count'].transform('sum')
        frequency.to_csv(output / 'episode_choice_frequencies.csv', index=False)
        qframe[qframe['query'] == 0].groupby(['factor', 'seed_group', 'arm', 'selected']).size().to_csv(output / 'q0_choice_frequencies.csv')
        decoder = qframe[qframe.arm == 'decoder_medoid']
        if not decoder.empty:
            summary['decoder_constant_choice_episode_fraction_descriptive'] = float((decoder.groupby('id').selected.nunique() == 1).mean())
    atomic_json(output / 'summary.json', summary)
    pd.DataFrame(rows).to_csv(output / 'episodes.csv', index=False)
    pd.DataFrame(queries).to_csv(output / 'queries.csv', index=False)
    rates.to_csv(output / 'success_rates.csv', index=False)
    comparisons.to_csv(output / 'paired_comparisons.csv', index=False)
    if not matched.empty:
        matched.groupby(['factor', 'seed_group', 'arm']).terminal_success.agg(['count', 'sum', 'mean']).to_csv(output / 'seed_group_rates.csv')
        matched.groupby(['factor', 'level', 'task_id', 'arm']).terminal_success.agg(['count', 'sum', 'mean']).to_csv(output / 'task_rates.csv')
    write_visuals(directory, output, rates, matched, originals)
    report = ['# Decoder-Token Medoid Transfer Results', '',
        f'Completed paired configurations: **{summary["complete_pairs"]}/{expected}**. Integration only: **{phase != "screen"}**.',
        'All comparisons use only configurations completed by all four strategies. Partial results are provisional.', '',
        '## Protocol', 'K3, generated/executed H16, five denoising evaluations, 280 steps, joint action/future/value. '
        'Object, Environment and Position x0.2/y0.2; all ten Object-suite tasks. '
        'Fixed seed groups (1,999,998), (2,997,996), (3,995,994). '
        'This is an architecture transfer, not a reproduction of GR00T H4 or MIMIC H5.', '',
        '## Success Rates', '```text', rates.to_string(index=False), '```', '',
        '## Paired Effects', '```text', comparisons.to_string(index=False), '```', '',
        'Intervals resample tasks within each factor, retaining repeated seeds/inits together. '
        'McNemar values are descriptive; independent-episode inference is not justified for repeated seeds.', '',
        'No automatic positive-result claim or holdout launch. Check consistency across factors and all three seed groups, '
        'then freeze an independent replication. Development improvement is not publication-ready confirmation.', '',
        'Fixed noise seeds can induce a nearly constant medoid choice. Inspect episode_choice_frequencies.csv '
        'and q0_choice_frequencies.csv; if this persists, compare fixed-candidate baselines before claiming observation-adaptive selection.', '',
        '[Four-way full video gallery](video_comparison.html)',
        '[Per-query metrics](queries.csv)', '[Per-seed results](seed_group_rates.csv)', '']
    (output / 'REPORT.md').write_text('\n'.join(report))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', choices=('screen', 'integration'), default='screen')
    args = parser.parse_args()
    analyze(args.campaign, phase=args.phase)

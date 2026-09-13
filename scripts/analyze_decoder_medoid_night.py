#!/usr/bin/env python3
"""Deadline coverage, fixed-seed confounding and execution-horizon controls."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.decoder_medoid_night import PLAN_FILE, STAGE_ARMS
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from decoder_medoid_night import PLAN_FILE, STAGE_ARMS
    from p5_repeat_feedback import atomic_json, digest

FAMILIES = {
    'seed_controls': ('first', 'max_value', 'action_medoid', 'decoder_medoid', 'fixed_candidate_1', 'fixed_candidate_2'),
    'horizon8': ('max_value', 'decoder_medoid', 'max_value_h8', 'decoder_full_h8', 'decoder_prefix_h8'),
}
CONTRASTS = {
    'seed_controls': (('decoder_medoid', 'fixed_candidate_1'), ('decoder_medoid', 'fixed_candidate_2'),
                      ('fixed_candidate_1', 'first'), ('fixed_candidate_2', 'first')),
    'horizon8': (('decoder_full_h8', 'max_value_h8'), ('decoder_prefix_h8', 'max_value_h8'),
                 ('decoder_prefix_h8', 'decoder_full_h8'), ('max_value_h8', 'max_value'),
                 ('decoder_full_h8', 'decoder_medoid')),
}


def family_tables(rows, family, expected_ids):
    required = FAMILIES[family]
    rows = [r for r in rows if r['id'] in expected_ids and r['arm'] in required]
    frame = pd.DataFrame(rows)
    empty = pd.DataFrame()
    summary = dict(expected_groups=len(expected_ids), complete_groups=0, partial=True, available_rollouts=len(rows))
    if frame.empty:
        return summary, empty, empty, empty
    if frame.duplicated(['id', 'arm']).any():
        raise ValueError('Duplicate identity')
    pivot = frame.pivot(index='id', columns='arm', values='terminal_success').reindex(columns=required)
    complete = pivot.dropna().astype(int)
    matched = frame[frame.id.isin(complete.index)].copy()
    summary.update(complete_groups=len(complete), partial=len(complete) != len(expected_ids),
                   missing_ids=sorted(set(expected_ids) - set(complete.index)))
    if matched.empty:
        return summary, empty, empty, matched
    for name in ('initial_sha256', 'q0_pool_sha256', 'env_seed', 'task_description', 'seed_group'):
        if matched.groupby('id')[name].nunique().max() != 1:
            raise ValueError('Paired contract mismatch: ' + name)
    task_rates = matched.groupby(['factor', 'task_id', 'arm']).terminal_success.mean()
    rates = matched.groupby(['factor', 'arm']).agg(n=('terminal_success', 'size'),
        successes=('terminal_success', 'sum'), micro_sr=('terminal_success', 'mean'),
        mean_steps=('terminal_final_t', 'mean'), mean_seconds=('elapsed_seconds', 'mean'),
        mean_candidate_calls=('candidate_calls_logical', 'mean')).reset_index()
    rates = rates.merge(task_rates.groupby(['factor', 'arm']).mean().rename('task_balanced_sr').reset_index(),
                        on=['factor', 'arm'], validate='one_to_one')
    metadata = matched.drop_duplicates('id').set_index('id')[['factor', 'task_id']]
    rng = np.random.default_rng(20260912)
    comparisons = []
    for method, baseline in CONTRASTS[family]:
        difference = complete[method] - complete[baseline]
        taskmeans = metadata.join(difference.rename('delta')).groupby(['factor', 'task_id']).delta.mean()
        boot = []
        for factor in taskmeans.index.get_level_values('factor').unique():
            values = taskmeans.loc[factor].to_numpy()
            boot.append(rng.choice(values, size=(10000, len(values)), replace=True).mean(1))
        lo, hi = np.quantile(np.mean(boot, axis=0), [.025, .975])
        comparisons.append(dict(method=method, baseline=baseline, paired_n=len(complete),
            macro_delta=float(taskmeans.groupby(level='factor').mean().mean()),
            cluster_ci_low=float(lo), cluster_ci_high=float(hi),
            rescue=int((difference == 1).sum()), harm=int((difference == -1).sum())))
    summary['macro_sr'] = rates.groupby('arm').task_balanced_sr.mean().to_dict()
    return summary, rates, pd.DataFrame(comparisons), matched


def analyze(directory):
    plan = json.loads((directory / PLAN_FILE).read_text())
    output = directory / 'night_analysis'
    output.mkdir(parents=True, exist_ok=True)
    rows, originals, queries = [], [], []
    for stage in ('screen', 'seed_controls', 'horizon8'):
        for path in sorted((directory / stage).glob('*/*.json')):
            if path.stem not in STAGE_ARMS[stage]:
                continue
            row = json.loads(path.read_text())
            for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
                if digest(path.with_suffix(ext)) != row[key]:
                    raise ValueError('Changed committed artifact ' + str(path))
            if row['video_frames'] != row['terminal_final_t'] + 1:
                raise ValueError('Video is not full length')
            originals.append(row)
            rows.append({k: v for k, v in row.items() if k != 'queries' and not isinstance(v, (list, dict))})
            for q in row['queries']:
                queries.append(dict(id=row['id'], arm=row['arm'], factor=row['factor'], seed_group=row['seed_group'],
                    query=q['query'], t=q['t'], t_after=q['t_after'], selected_seed=q['candidate_seeds'][q['index']],
                    selected_original_index=q.get('original_candidate_index', q['index']),
                    terminal_success=row['terminal_success'], **q['metrics'], **q['prediction_errors']))
    pd.DataFrame(rows).to_csv(output / 'episodes.csv', index=False)
    pd.DataFrame(queries).to_csv(output / 'queries.csv', index=False)
    summary = dict(deadline=plan['deadline_moscow'], planned_maximum_rollouts=1440,
        committed_rollouts=len(rows),
        coverage={s: dict(expected=plan['expected_rollouts'][s], committed=sum(r['phase'] == s for r in rows))
                  for s in plan['expected_rollouts']},
        limitations='Development comparisons, not a held-out benchmark. Deadline truncation is not random. '
                    'Only complete matched groups enter each contrast. Cluster intervals do not correct multiple comparisons.',
        families={})
    report = ['# Deadline-Bounded Decoder Medoid Experiments', '',
        f'Deadline: {plan["deadline_moscow"]}. Committed rollouts: {len(rows)}/1440 maximum.', '',
        'The original 720-rollout comparison is unchanged: [base report](../analysis/REPORT.md).', '',
        '## Questions',
        '1. Does hidden consensus outperform a fixed second or third candidate, or merely prefer a noise seed?',
        '2. At generated H16 / executed H8, does full or prefix-weighted hidden consensus outperform max(value)?',
        '3. What is the separate effect of feedback frequency, holding the selector fixed?', '',
        'All arms replay the same saved simulator state, cached initial model observations and common q0 pool. '
        'The selector sees no simulator labels. H8 future-error fields are empty: an H16 prediction must not '
        'be compared to an observation after eight actions. Full videos include the initial frame and every action step.', '',
        '## Coverage', '```json', json.dumps(summary['coverage'], indent=2), '```', '']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for family in FAMILIES:
        ids = {j['id'] for j in plan['jobs'] if j['phase'] == family}
        result, rates, comparisons, matched = family_tables(rows, family, ids)
        summary['families'][family] = result
        rates.to_csv(output / (family + '__rates.csv'), index=False)
        comparisons.to_csv(output / (family + '__paired_comparisons.csv'), index=False)
        if not matched.empty:
            matched.groupby(['factor', 'level', 'task_id', 'seed_group', 'arm']).terminal_success.agg(
                ['count', 'sum', 'mean']).to_csv(output / (family + '__strata.csv'))
            ax = rates.pivot(index='factor', columns='arm', values='task_balanced_sr').plot.bar(
                figsize=(12, 4), rot=0, ylim=(0, 1), title=family + ': complete matched groups only')
            ax.set_ylabel('Task-balanced success rate')
            ax.figure.tight_layout()
            ax.figure.savefig(output / (family + '__success_rates.png'), dpi=160)
            plt.close(ax.figure)
        report += ['## ' + family, f'Complete matched groups: {result["complete_groups"]}/{len(ids)}.', '',
            '```text', rates.to_string(index=False), '```', '', '```text', comparisons.to_string(index=False), '```', '']
    if queries:
        frame = pd.DataFrame(queries)
        frame.groupby(['id', 'arm', 'selected_original_index', 'selected_seed']).size().rename('count').to_csv(
            output / 'candidate_choice_frequencies.csv')
    report += ['## Interpretation',
        'A hidden-medoid gain over the first candidate alone is insufficient evidence of adaptive selection. '
        'Inspect both fixed-candidate controls and all three seed groups. If a fixed candidate matches the medoid, '
        'the parsimonious explanation is seed preference, not observation-dependent consensus.', '',
        'A gain at H8 against H16 mixes selector and execution-frequency effects. Use the H8 max-value control '
        'for a selector claim. A prefix weighting gain is an exploratory Cosmos-specific transfer result.', '',
        summary['limitations'],
        'No positive finding or publication-readiness conclusion is generated automatically. '
        'Require stable direction across factors/tasks/seeds and a separately frozen replication.', '',
        '[All full videos](video_comparison.html) | [Per-query metrics](queries.csv)', '']
    (output / 'REPORT.md').write_text('\n'.join(report))
    atomic_json(output / 'summary.json', summary)
    parts = ['<!doctype html><meta charset="utf-8"><title>Night experiment videos</title>',
        '<style>body{font:14px sans-serif;margin:20px}section{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:420px;max-width:100%}video{width:100%}</style>',
        '<h1>Full paired rollouts</h1><p>20 fps; initial frame and every executed step. Missing arms are not failures.</p>']
    ids = list(dict.fromkeys(r['id'] for r in originals))
    for identifier in ids:
        selected = [r for r in originals if r['id'] == identifier]
        parts += [f'<h2>{html.escape(identifier)}</h2><p>{html.escape(selected[0]["task_description"])}</p><section>']
        for r in selected:
            url = f'../{r["phase"]}/{r["id"]}/{r["arm"]}.mp4'
            caption = f'{r["arm"]}: success={r["terminal_success"]}, steps={r["terminal_final_t"]}'
            parts.append(f'<figure><figcaption>{html.escape(caption)}</figcaption><video controls preload="none" src="{html.escape(url)}"></video></figure>')
        parts.append('</section>')
    (output / 'video_comparison.html').write_text('\n'.join(parts))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', required=True, type=Path)
    analyze(parser.parse_args().campaign)

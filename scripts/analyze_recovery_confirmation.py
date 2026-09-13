#!/usr/bin/env python3
"""Audit matched episodes and report frozen contrasts, including negative results."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.recovery_confirmation import ARMS, PRIMARY, expected_arms, job_done, suffix_query
    from scripts.analyze_feedback_controls import contrast
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from recovery_confirmation import ARMS, PRIMARY, expected_arms, job_done, suffix_query
    from analyze_feedback_controls import contrast
    from p5_repeat_feedback import atomic_json, digest


def holm(values):
    values = np.asarray(values, dtype=float)
    order = np.argsort(values)
    result = np.empty_like(values)
    result[order] = np.minimum(1., np.maximum.accumulate(values[order] * np.arange(len(values), 0, -1)))
    return result


def analyze(directory, phase):
    config = json.loads((directory / 'config.json').read_text())
    jobs = [j for j in config['jobs'] if j['phase'] == phase]
    rows, missing, query_rows = [], [], []
    checks = dict(artifacts=0, exact_replay=0, video_frames=0, selected_actions=0,
                  no_intervention_parity=0, full_prefix_checks=0)
    for job in jobs:
        if not job_done(directory, job, hashes=True):
            missing.append(job['id'])
            continue
        folder = directory / phase / job['id']
        outcomes = {}
        for arm in expected_arms(job):
            path = folder / (arm + '.json')
            row = json.loads(path.read_text())
            if row['arm'] != arm or row['simulator_labels_online'] or row['boundary'] != job['boundary']:
                raise ValueError('Arm identity or online GT violation')
            with np.load(path.with_suffix('.npz'), allow_pickle=False) as arrays:
                start, end = row['video_start_t'], row['terminal_final_t']
                actions = arrays['executed_actions']
                if actions.shape != (end - start, 7) or not np.isfinite(actions).all() or end > 280:
                    raise ValueError('Physical action accounting')
                np.testing.assert_array_equal(arrays['frame_t'], np.arange(start, end + 1))
                if row['video_frames'] != end - start + 1:
                    raise ValueError('Frame accounting')
                for qi, query in enumerate(row['queries']):
                    q = qi if arm == 'baseline_h16' else suffix_query(job['boundary']) + qi
                    if query['seeds'] != [job['rollout_seed'] + q * 1000 + i for i in range(4)]:
                        raise ValueError('Changed candidate noise schedule')
                    if query['index'] != int(np.argmax(query['candidate_values'])):
                        raise ValueError('Wrong max-value candidate')
                    n = min(query['requested_horizon'], end - query['t'])
                    predicted = np.asarray(query['candidate_actions'][query['index']], dtype=np.float32)[:n]
                    np.testing.assert_array_equal(actions[query['t'] - start:query['t'] - start + n], predicted)
                    checks['selected_actions'] += n
                    query_rows.append(dict(job_id=job['id'], arm=arm, boundary=job['boundary'],
                        cell=job['cell'], init_state_id=job['init_state_id'], t=query['t'],
                        terminal_success=row['terminal_success'], **query['metrics']))
                if phase == 'smoke':
                    source = Path(config['replay_source']) / 'screen' / job['source_id'] / (arm + '.npz')
                    with np.load(source, allow_pickle=False) as reference:
                        for key in ('executed_actions', 'final_state', 'signals'):
                            np.testing.assert_array_equal(arrays[key], reference[key], err_msg=f'{job["id"]}: {arm}/{key}')
                    checks['exact_replay'] += 1
                elif arm != 'baseline_h16':
                    source = directory / 'main' / job['case_id'] / f'prefix_{job["boundary"]}.npz'
                    if row['prefix_sha256'] != digest(source):
                        raise ValueError('Changed common prefix')
                    with np.load(source, allow_pickle=False) as prefix:
                        np.testing.assert_array_equal(actions[:row['prefix_t']], prefix['prefix_actions'])
                    checks['full_prefix_checks'] += 1
            if phase == 'smoke':
                import imageio.v2 as imageio
                with imageio.get_reader(path.with_suffix('.mp4')) as reader:
                    count = sum(1 for _ in reader)
                if count != row['video_frames']:
                    raise ValueError('MP4 did not decode to all expected frames')
                checks['video_frames'] += count
            checks['artifacts'] += 1
            d = row['intervention']
            row.update(query_count=len(row['queries']),
                full_regrasp=d.get('regrasp_diagnostics', {}).get('perception_regrasp_executed', False),
                refresh=bool(d.get('refresh_requested', False)),
                logical_candidates=4 * len(row['queries']))
            rows.append(row)
            outcomes[arm] = row
        for arm in ARMS[1:]:
            d = outcomes[arm]['intervention']
            if not d.get('repair_requested', False) and not d.get('refresh_requested', False):
                with np.load(folder / (arm + '.npz'), allow_pickle=False) as left:
                    with np.load(folder / 'continue_h8.npz', allow_pickle=False) as right:
                        np.testing.assert_array_equal(left['executed_actions'], right['executed_actions'])
                        np.testing.assert_array_equal(left['final_state'], right['final_state'])
                checks['no_intervention_parity'] += 1
    out = directory / 'analysis' / phase
    out.mkdir(parents=True, exist_ok=True)
    summary = dict(phase=phase, complete=not missing, missing=missing, cases=len(jobs) - len(missing),
        planned_cases=len(jobs), branches=len(rows), audit=checks, automatic_holdout=False,
        inference_withheld=bool(missing or phase == 'smoke'),
        scope=config['sampling_scope'], transfer_scope=config['transfer_scope'])
    if not rows:
        atomic_json(out / 'summary.json', summary)
        return summary
    data = pd.DataFrame(rows)
    data.drop(columns=['queries']).to_json(out / 'branch_outcomes.json', orient='records', indent=2)
    pd.DataFrame(query_rows).to_csv(out / 'query_metrics.csv', index=False)
    scores = data.groupby(['boundary', 'cohort', 'cell', 'arm']).agg(
        n=('terminal_success', 'size'), successes=('terminal_success', 'sum'),
        sr=('terminal_success', 'mean'), full_regrasp=('full_regrasp', 'sum'),
        refresh=('refresh', 'sum'), final_t=('terminal_final_t', 'mean'),
        candidates=('logical_candidates', 'mean'), suffix_drop_proxy=('terminal_target_drop_candidate', 'sum'))
    scores.to_csv(out / 'cell_scores.csv')
    aggregate = data.groupby(['boundary', 'cohort', 'arm']).agg(
        n=('terminal_success', 'size'), successes=('terminal_success', 'sum'), sr=('terminal_success', 'mean'))
    aggregate.to_csv(out / 'aggregate_scores.csv')
    effects = []
    if not missing and phase != 'smoke':
        for boundary, block in data.groupby('boundary'):
            planned = PRIMARY if phase == 'main' else (
                ('replication', 'physical_regrasp', 'continue_h8'),
                ('transfer', 'physical_regrasp', 'continue_h8'),
                ('all', 'refresh_preserve_only', 'physical_regrasp'))
            for scope, left, right in planned:
                part = block if scope == 'all' else block[block.cohort.eq(scope)]
                effects.append(dict(boundary=int(boundary), scope=scope,
                    family='primary' if phase == 'main' else 'secondary_timing', **contrast(part, left, right)))
    effects = pd.DataFrame(effects)
    if len(effects):
        effects['holm_p'] = holm(effects.cluster_sign_p)
        effects.to_csv(out / 'paired_effects.csv', index=False)
        summary['effects'] = effects.to_dict('records')
    summary['aggregate'] = aggregate.reset_index().to_dict('records')
    atomic_json(out / 'summary.json', summary)
    gallery = ['<!doctype html><meta charset="utf-8"><title>Recovery confirmation</title>',
        '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:360px;max-width:100%}video{width:100%}</style>',
        '<h1>Recovery confirmation</h1><p>Main and timing videos include every action from t=0. Technical replay videos start at t=72. Comparisons are paired within a case.</p>']
    for case, group in data.groupby('job_id', sort=False):
        gallery.append('<h2>' + html.escape(case) + '</h2><div class="row">')
        for _, row in group.iterrows():
            arm = row.arm
            gallery.append(f'<figure><figcaption>{html.escape(arm)}: success={bool(row.terminal_success)}, t={row.terminal_final_t}</figcaption>'
                f'<video controls preload="none" src="../../{phase}/{case}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (out / 'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for boundary, part in data.groupby('boundary'):
        table = part.groupby(['cohort', 'arm']).terminal_success.mean().unstack('arm')
        fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
        table.plot.bar(ax=ax)
        ax.set(ylim=(0, 1), ylabel='Terminal success rate', title=f'Frozen recovery at t={boundary}')
        fig.savefig(out / f'success_rates_t{boundary}.png', dpi=150)
        plt.close(fig)
    report = ['# Recovery confirmation: ' + phase, '', f'Complete: {not missing}. Cases: {summary["cases"]}/{len(jobs)}.',
        '', config['sampling_scope'] + '.', config['transfer_scope'] + '.',
        'Early success is retained in the denominator. Invalid/incomplete jobs are not scored as failures.',
        'Safety proxies in branch rows cover the suffix only; baseline_h16 proxies cover the full episode. Do not compare these as identical safety endpoints.',
        'Timing branches share one uninterrupted H16 reference trajectory and are not independent samples.',
        'No fit or outcome-dependent promotion. No claim of official AR planning or whole-benchmark SR.', '',
        aggregate.to_markdown(), '', effects.to_markdown(index=False) if len(effects) else 'Inference withheld for incomplete/technical data.',
        '', '[All comparison videos](videos.html)', '[Per-query uncertainty](query_metrics.csv)', '[Per-cell scores](cell_scores.csv)']
    (out / 'RESULTS.md').write_text('\n'.join(report) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', choices=('smoke', 'main', 'timing'), required=True)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = analyze(args.campaign, args.phase)
    print(json.dumps(result, indent=2))
    if args.require_complete and not result['complete']:
        raise SystemExit('Incomplete phase')

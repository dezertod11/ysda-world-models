#!/usr/bin/env python3
"""Audit paired support and export factor-macro SR with cluster uncertainty."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

from p3_benchmark import ARMS, FACTORS, CONTRASTS
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json


def audit_case(folder, arms=ARMS, decode=False):
    records, arrays = {}, {}
    for arm in arms:
        path = folder / (arm + '.json')
        row = json.loads(path.read_text())
        if row['arm'] != arm or row['simulator_labels_online']:
            raise ValueError('Arm/online-label contract violation')
        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
            if digest(path.with_suffix(ext)) != row[key]:
                raise ValueError('Committed artifact changed')
        with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
            actions, final = z['executed_actions'].copy(), z['final_state'].copy()
            end = row['final_t']
            if actions.shape != (end, 7) or not np.isfinite(actions).all() or end > 280:
                raise ValueError('Physical action accounting')
            np.testing.assert_array_equal(z['frame_t'], np.arange(end + 1))
        if row['video_frames'] != end + 1:
            raise ValueError('Video frame accounting')
        coverage = np.zeros(end, dtype=int)
        for query in row['queries']:
            k = 1 if arm == 'first_k1' else 4
            seeds = [row['job']['rollout_seed'] + query['query'] * 1000 + i for i in range(k)]
            if query['metadata']['seeds'] != seeds or len(query['candidate_values']) != k:
                raise ValueError('Candidate sample schedule changed')
            if query['selected'] != int(np.argmax(query['candidate_values'])):
                raise ValueError('Wrong candidate selection')
            t, n = query['t'], query['executed_steps']
            np.testing.assert_array_equal(actions[t:t+n],
                np.asarray(query['candidate_actions'][query['selected']], dtype=np.float32)[:n])
            coverage[t:t+n] += 1
        for event in row['events']:
            if event['executed']:
                coverage[event['t']:event['end_t']] += 1
        if not np.all(coverage == 1):
            raise ValueError('Actions omitted or double-counted')
        if decode:
            import imageio.v2 as imageio
            with imageio.get_reader(path.with_suffix('.mp4')) as reader:
                if sum(1 for _ in reader) != end + 1:
                    raise ValueError('Video decode truncated')
        records[arm], arrays[arm] = row, (actions, final)
    if len({r['initial_sha256'] for r in records.values()}) != 1 or len({r['config_sha256'] for r in records.values()}) != 1:
        raise ValueError('Paired arms have different initial state/config')
    for arm in ('h8_at72', 'p3_at72'):
        n = min(72, len(arrays[arm][0]), len(arrays['max_value_h16'][0]))
        np.testing.assert_array_equal(arrays[arm][0][:n], arrays['max_value_h16'][0][:n])
    for arm, control in (('p3_at72', 'h8_at72'), ('p3_event', 'max_value_h16'), ('shadow', 'max_value_h16')):
        if arm not in records:
            continue
        if not any(e['executed'] and e['physical_steps'] for e in records[arm]['events']):
            for a, b in zip(arrays[arm], arrays[control]):
                np.testing.assert_array_equal(a, b, err_msg='No-intervention/shadow parity: ' + arm)
            if records[arm]['success'] != records[control]['success']:
                raise ValueError('No-intervention outcome mismatch')
    return dict(audit_pass=True, full_episode_accounting=True, branches=len(arms),
                passive_shadow_parity='shadow' in arms, videos_decoded=decode)


def paired_effect(data, left, right, repeats=5000):
    keys = ['factor', 'task_id', 'init_state_id', 'id']
    wide = data.pivot(index=keys, columns='arm', values='success')[[left, right]]
    if wide.isna().any().any():
        raise ValueError('Unpaired effect')
    diff = (wide[left].astype(int) - wide[right].astype(int)).rename('delta').reset_index()
    rng = np.random.default_rng(20260914)
    draws, contributions, effects = [], [], []
    for factor in FACTORS:
        part = diff[diff.factor.eq(factor)]
        grouped = part.groupby(['task_id', 'init_state_id']).delta.agg(['sum', 'size'])
        if len(grouped) == 0:
            raise ValueError('Need all three factors')
        indices = rng.integers(len(grouped), size=(repeats, len(grouped)))
        draws.append(grouped['sum'].to_numpy()[indices].sum(1) / grouped['size'].to_numpy()[indices].sum(1))
        contributions.extend((grouped['sum'] / len(part) / 3).tolist())
        effects.append(float(part.delta.mean()))
    observed = float(np.mean(effects))
    boot = np.mean(draws, axis=0)
    contributions = np.asarray(contributions)
    permutations = 20000
    signs = rng.choice((-1, 1), size=(permutations, len(contributions)))
    p = (1 + int((np.abs(signs @ contributions) >= abs(observed) - 1e-12).sum())) / (permutations + 1)
    return dict(method=left, control=right, pairs=len(wide), clusters=len(contributions),
        delta_pp=100 * observed, ci_low_pp=100 * float(np.quantile(boot, .025)),
        ci_high_pp=100 * float(np.quantile(boot, .975)), cluster_sign_p=p,
        rescues=int(diff.delta.eq(1).sum()), harms=int(diff.delta.eq(-1).sum()))


def analyze(directory, verify=True):
    cfg = json.loads((directory / 'config.json').read_text())
    out = directory / 'analysis'
    out.mkdir(parents=True, exist_ok=True)
    rows, query_rows, missing = [], [], []
    for job in cfg['jobs']:
        if job['phase'] != 'main':
            continue
        folder = directory / 'main' / job['id']
        if not (folder / 'completed.json').exists():
            missing.append(job['id'])
            continue
        if verify:
            audit_case(folder)
        for arm in ARMS:
            record = json.loads((folder / (arm + '.json')).read_text())
            if record['config_sha256'] != digest(directory / 'config.json') or record['job'] != job:
                raise ValueError('Foreign episode in current benchmark')
            rows.append(dict(**job, arm=arm, success=bool(record['success']), final_t=record['final_t'],
                query_count=record['model_calls'], logical_candidates=record['logical_candidates'],
                interventions=sum(e['executed'] and e['physical_steps'] > 0 for e in record['events']),
                drop_proxy=bool(record.get('terminal_target_drop_candidate', False)),
                wrong_object_proxy=bool(record['terminal_wrong_object_interaction_candidate'])))
            for query in record['queries']:
                query_rows.append(dict(id=job['id'], factor=job['factor'], arm=arm, t=query['t'],
                    query=query['query'], terminal_success=record['success'],
                    **query['metadata'].get('uncertainty', {}), **query['metrics']))
    complete = not missing
    summary = dict(complete=complete, planned_cases=199, matched_cases=len(rows) // len(ARMS),
        missing=missing, inference_withheld=not complete, config_sha256=digest(directory / 'config.json'),
        support='Same valid199 configurations; fresh paired collection, not untouched evaluation',
        event_method='exploratory; observed miss and frozen localizer; no new training',
        safety_scope='Whole-episode local proxies; not official LIBERO-Safety',
        macro='Equal factor weights; micro weights all 199 episodes equally')
    report = ['# P3: three-factor comparison', '',
        f'Matched cases: {summary["matched_cases"]}/199; complete: {complete}.',
        '', summary['support'] + '.', 'Incomplete/technical runs are excluded, never scored as failures.',
        'P3-at72 is a historical timing control. P3-event is an exploratory observation-triggered method.', '']
    if rows:
        data = pd.DataFrame(rows)
        data.to_csv(out / 'episode_outcomes.csv', index=False)
        pd.DataFrame(query_rows).to_csv(out / 'query_metrics.csv', index=False)
        factors = data.groupby(['arm', 'factor']).agg(n=('success', 'size'), successes=('success', 'sum'),
            sr=('success', 'mean'), queries=('query_count', 'mean'), candidates=('logical_candidates', 'mean'),
            interventions=('interventions', 'mean'), drop_proxy=('drop_proxy', 'mean'),
            wrong_object_proxy=('wrong_object_proxy', 'mean')).reset_index()
        factors.to_csv(out / 'factor_scores.csv', index=False)
        table = factors.pivot(index='arm', columns='factor', values='sr').reindex(index=ARMS, columns=FACTORS) * 100
        table['Macro-SR, %'] = table.mean(axis=1, skipna=False)
        total = data.groupby('arm').success.agg(['sum', 'size'])
        table['Success / N'] = total['sum'].astype(str) + '/' + total['size'].astype(str)
        table.to_csv(out / 'benchmark_table.csv')
        report += [table.to_markdown(floatfmt='.2f'), '']
        summary['scores'] = factors.to_dict('records')
        if complete:
            effects = pd.DataFrame([paired_effect(data, a, b) for a, b in CONTRASTS])
            order = np.argsort(effects.cluster_sign_p.to_numpy())
            adjusted = np.empty(len(effects))
            adjusted[order] = np.minimum(1, np.maximum.accumulate(effects.cluster_sign_p.to_numpy()[order] * np.arange(len(effects), 0, -1)))
            effects['holm_p'] = adjusted
            effects.to_csv(out / 'paired_effects.csv', index=False)
            report += [effects.to_markdown(index=False, floatfmt='.4f'), '']
            summary['effects'] = effects.to_dict('records')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5), layout='constrained')
        table[list(FACTORS)].plot.bar(ax=ax)
        ax.set(ylabel='Success (%)', ylim=(0, 100), title=f'P3 paired transfer: {len(rows)//len(ARMS)}/199 cases')
        ax.tick_params(axis='x', rotation=20)
        fig.savefig(out / 'factor_success_rates.png', dpi=160)
        plt.close(fig)
        page = ['<!doctype html><meta charset="utf-8"><title>P3 matched videos</title>',
            '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:340px}video{width:100%}</style>']
        for key, part in data.groupby('id', sort=False):
            page.append('<h2>' + html.escape(key) + '</h2><div class="row">')
            for _, row in part.iterrows():
                page.append(f'<figure><figcaption>{row.arm}: success={row.success}, t={row.final_t}</figcaption>'
                    f'<video controls preload="none" src="../main/{key}/{row.arm}.mp4"></video></figure>')
            page.append('</div>')
        (out / 'videos.html').write_text('\n'.join(page))
    report += ['[Videos](videos.html)', '[Per-query metrics](query_metrics.csv)',
        '', 'Intervals preserve task/init clusters within each factor, including Position levels together.',
        'Use logical model calls for cost: exact equal-input samples are cached across paired arms.',
        'Outcome labels and prediction errors after a chunk are not pre-failure input features.']
    atomic_json(out / 'summary.json', summary)
    (out / 'RESULTS.md').write_text('\n'.join(report) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--already-audited', action='store_true')
    args = parser.parse_args()
    result = analyze(args.campaign, verify=not args.already_audited)
    print(json.dumps({k: result[k] for k in ('complete', 'matched_cases', 'planned_cases')}))

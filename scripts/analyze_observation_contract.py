#!/usr/bin/env python3
"""Replay and mechanism checks; oracle scores are never deployable evidence."""
import argparse
import html
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

try:
    from scripts.observation_contract import ARMS, REFRESH, ORACLES, CONTRASTS, refresh_allowed
    from scripts.analyze_timing_eligibility import arrays_equal
    from scripts.analyze_feedback_controls import contrast
    from scripts.probe_repair import validate_probe_pair
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from observation_contract import ARMS, REFRESH, ORACLES, CONTRASTS, refresh_allowed
    from analyze_timing_eligibility import arrays_equal
    from analyze_feedback_controls import contrast
    from probe_repair import validate_probe_pair
    from p5_repeat_feedback import atomic_json, digest


def analyze(directory, phase):
    cfg = json.loads((directory / 'config.json').read_text())
    rows, missing = [], []
    audit = dict(old_control_checks=0, eligible_refresh_matches_baseline=0,
                 no_intervention_matches_continue=0, common_probe_checks=0)
    for job in [j for j in cfg['jobs'] if j['phase'] == phase]:
        folder = directory / phase / job['id']
        if not (folder / 'completed.json').exists():
            missing.append(job['id'])
            continue
        if json.loads((folder / 'completed.json').read_text())['arms'] != list(ARMS):
            raise ValueError('Changed arms')
        meta = json.loads((folder / 'prefix.json').read_text())
        if digest(folder / 'prefix.npz') != meta['sha256'] or meta['sha256'] != job['source_hashes']['prefix.npz']:
            raise ValueError('Changed shared prefix')
        with np.load(folder / 'prefix.npz', allow_pickle=False) as z:
            eef = z['obs__robot0_eef_pos'].copy()
            grip = float(z['prefix_actions'][-1, 6])
        group = {}
        for arm in ARMS:
            path = folder / (arm + '.json')
            row = json.loads(path.read_text())
            for key in ('cell', 'phase', 'task_id', 'init_state_id', 'repeat', 'rollout_seed',
                        'source_id', 'prefix_seed', 'suffix_repeat'):
                if row[key] != job[key]:
                    raise ValueError('Changed identity: ' + key)
            if row['job_id'] != job['id'] or row['arm'] != arm or row['prefix_sha256'] != meta['sha256']:
                raise ValueError('Changed branch identity')
            if row['simulator_labels_online'] != (arm in ORACLES) or row['diagnostic_only_simulator_labels'] != (arm not in ORACLES):
                raise ValueError('Incorrect oracle provenance')
            for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
                if digest(path.with_suffix(ext)) != row[key]:
                    raise ValueError('Changed branch artifact')
            with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
                if len(z['executed_actions']) != row['terminal_final_t'] - meta['t']:
                    raise ValueError('Physical step accounting')
                if not np.isfinite(z['executed_actions']).all() or row['terminal_final_t'] > 280:
                    raise ValueError('Invalid actions or budget')
                np.testing.assert_array_equal(z['frame_t'], np.arange(meta['t'], row['terminal_final_t'] + 1))
                if len(z['frame_t']) != row['video_frames']:
                    raise ValueError('Video accounting')
            for q, query in enumerate(row['queries'], start=5):
                if query['seeds'] != [job['rollout_seed'] + q * 1000 + i for i in range(4)]:
                    raise ValueError('Incorrect continuation seeds')
            d = row['intervention']
            expected_refresh = arm in REFRESH and refresh_allowed(SimpleNamespace(**d['initial_gate']), eef, grip)
            if d['refresh_requested'] != expected_refresh or d['previous_gripper'] != grip:
                raise ValueError('Refresh routing or preserved command mismatch')
            row.update(query_count=len(row['queries']), original_eligible=d['initial_t72_trigger_passed'],
                refresh_requested=d['refresh_requested'], full_regrasp=d.get('regrasp_diagnostics', {}).get('perception_regrasp_executed', False),
                intervention_steps=d['regrasp_steps'], oracle=arm in ORACLES)
            rows.append(row)
            group[arm] = row
            if job['suffix_repeat'] == 0 and arm in ARMS[:2]:
                source = directory.parent / Path(cfg['replay_source']).name / job['source_phase'] / job['source_id'] / (arm + '.npz')
                if digest(source) != job['source_hashes'][source.name]:
                    raise ValueError('Changed reference control')
                arrays_equal(path.with_suffix('.npz'), source, ('executed_actions', 'final_state', 'signals'))
                audit['old_control_checks'] += 1
        for arm in REFRESH:
            row = group[arm]
            reference = 'physical_regrasp' if row['original_eligible'] else 'continue_h8'
            if row['original_eligible'] or not row['refresh_requested']:
                arrays_equal(folder / (arm + '.npz'), folder / (reference + '.npz'),
                             ('executed_actions', 'final_state', 'signals'))
                audit['eligible_refresh_matches_baseline' if row['original_eligible'] else 'no_intervention_matches_continue'] += 1
        for left, right in [('refresh_open_only', 'refresh_open_regrasp'),
                            ('refresh_preserve_only', 'refresh_preserve_regrasp')]:
            if group[left]['refresh_requested']:
                a = group[left]['intervention']['regrasp_diagnostics']['probe_end_audit']
                b = group[right]['intervention']['regrasp_diagnostics']['probe_end_audit']
                validate_probe_pair(a, b)
                n = a['t'] - meta['t']
                with np.load(folder / (left + '.npz'), allow_pickle=False) as x:
                    with np.load(folder / (right + '.npz'), allow_pickle=False) as y:
                        np.testing.assert_array_equal(x['executed_actions'][:n], y['executed_actions'][:n])
                audit['common_probe_checks'] += 1
    out = directory / 'analysis' / phase
    out.mkdir(parents=True, exist_ok=True)
    summary = dict(phase=phase, complete=not missing, missing=missing, branches=len(rows),
        paired_suffix_cases=len(rows) // len(ARMS), audit=audit, automatic_holdout=False,
        scope='development and suffix replication on existing states; not independent new-init holdout')
    if not rows:
        atomic_json(out / 'summary.json', summary)
        return summary
    data = pd.DataFrame(rows)
    data.drop(columns=['queries']).to_json(out / 'branch_outcomes.json', orient='records', indent=2)
    aggregate = data.groupby('arm').agg(n=('terminal_success', 'size'), successes=('terminal_success', 'sum'),
        sr=('terminal_success', 'mean'), refresh=('refresh_requested', 'sum'), full=('full_regrasp', 'sum'),
        drop_proxy=('terminal_target_drop_candidate', 'sum'), queries=('query_count', 'mean')).reindex(ARMS)
    aggregate.to_csv(out / 'aggregate_scores.csv')
    data.groupby(['suffix_repeat', 'cell', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(out / 'cell_suffix_scores.csv')
    effects = []
    for scope, part in [('pooled', data)] + [('suffix_' + str(k), v) for k, v in data.groupby('suffix_repeat')]:
        block = pd.DataFrame([dict(scope=scope, oracle_contrast=(a in ORACLES or b in ORACLES), **contrast(part, a, b))
                              for a, b in CONTRASTS])
        order = block.sort_values('cluster_sign_p').index
        block.loc[order, 'holm_p'] = np.minimum(1, np.maximum.accumulate(
            block.loc[order, 'cluster_sign_p'].to_numpy() * np.arange(len(block), 0, -1)))
        effects.append(block)
    effects = pd.concat(effects, ignore_index=True)
    effects.to_csv(out / 'paired_effects.csv', index=False)
    summary.update(aggregate=aggregate.reset_index().to_dict('records'), effects=effects.to_dict('records'),
                   unique_prefixes=data.source_id.nunique(), init_clusters=len(data[['cell', 'init_state_id']].drop_duplicates()))
    if phase == 'screen' and not missing:
        candidate = effects[effects.left.eq(cfg['primary']) & effects.right.eq('physical_regrasp')]
        primary = candidate[candidate.scope.eq('pooled')].iloc[0]
        summary['candidate_for_future_new_init_confirmation'] = bool(primary.delta >= .05 and primary.ci_low > 0
            and primary.holm_p <= .05 and candidate.delta.gt(0).all()
            and aggregate.loc[cfg['primary'], 'drop_proxy'] <= aggregate.loc['physical_regrasp', 'drop_proxy'])
    atomic_json(out / 'summary.json', summary)
    gallery = ['<!doctype html><meta charset="utf-8"><title>Observation contract</title>',
        '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;width:360px;max-width:100%}video{width:100%}</style>',
        '<h1>Observation contract</h1><p>Oracle arms use simulator target poses and are diagnostic only. Videos start at t72.</p>']
    for case, group in data.groupby('job_id'):
        gallery.append('<h2>' + html.escape(case) + '</h2><div class="row">')
        for arm in ARMS:
            row = group[group.arm.eq(arm)].iloc[0]
            label = ('ORACLE: ' if arm in ORACLES else '') + arm
            gallery.append(f'<figure><figcaption>{label}: success={bool(row.terminal_success)}</figcaption>'
                f'<video controls preload="none" src="../../{phase}/{case}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (out / 'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 5), layout='constrained')
    aggregate.sr.plot.barh(ax=ax, color=['#207567'] * 6 + ['#b16d19'] * 2)
    ax.set(xlim=(0, 1), xlabel='Terminal SR', title='Observation contract: orange = privileged diagnostics')
    fig.savefig(out / 'success_rates.png', dpi=160)
    plt.close(fig)
    (out / 'RESULTS.md').write_text('# Observation contract: ' + phase + '\n\n'
        + 'Existing states, not a fresh task/init holdout. Oracle rows use simulator ground truth.\n\n'
        + aggregate.to_markdown() + '\n\n' + effects.to_markdown(index=False)
        + '\n\n![SR](success_rates.png)\n[Videos](videos.html)\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', choices=('smoke', 'screen'), required=True)
    args = parser.parse_args()
    if not analyze(args.campaign, args.phase)['complete']:
        raise SystemExit('Incomplete phase: no promotion')

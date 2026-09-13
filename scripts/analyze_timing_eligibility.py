#!/usr/bin/env python3
"""Strict paired analysis; smoke validates old controls, never tunes the method."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.timing_eligibility import ARMS, DELAYED, CONTRASTS, request_repair
    from scripts.analyze_feedback_controls import contrast
    from scripts.probe_repair import validate_probe_pair
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from timing_eligibility import ARMS, DELAYED, CONTRASTS, request_repair
    from analyze_feedback_controls import contrast
    from probe_repair import validate_probe_pair
    from p5_repeat_feedback import atomic_json, digest


def arrays_equal(left, right, keys):
    with np.load(left, allow_pickle=False) as a:
        with np.load(right, allow_pickle=False) as b:
            for key in keys:
                if not np.array_equal(a[key], b[key], equal_nan=True):
                    raise ValueError(f'Trajectory parity failed: {left} vs {right}: {key}')


def analyze(directory, phase):
    cfg = json.loads((directory / 'config.json').read_text())
    rows, missing = [], []
    audit = dict(source_control_checks=0, equal_decision_path_checks=0, common_delay_checks=0)
    for job in [j for j in cfg['jobs'] if j['phase'] == phase]:
        folder = directory / phase / job['id']
        if not (folder / 'completed.json').exists():
            missing.append(job['id'])
            continue
        if json.loads((folder / 'completed.json').read_text())['arms'] != list(ARMS):
            raise ValueError('Arms changed')
        meta = json.loads((folder / 'prefix.json').read_text())
        if digest(folder / 'prefix.npz') != meta['sha256']:
            raise ValueError('Prefix hash failed')
        group = {}
        for arm in ARMS:
            path = folder / (arm + '.json')
            row = json.loads(path.read_text())
            for key in ('cell', 'phase', 'task_id', 'init_state_id', 'repeat', 'rollout_seed'):
                if row[key] != job[key]:
                    raise ValueError('Branch identity mismatch: ' + key)
            if row['job_id'] != job['id'] or row['arm'] != arm or row['prefix_sha256'] != meta['sha256']:
                raise ValueError('Branch identity mismatch')
            for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
                if digest(path.with_suffix(ext)) != row[key]:
                    raise ValueError('Artifact hash mismatch')
            with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
                if len(z['executed_actions']) != row['terminal_final_t'] - meta['t']:
                    raise ValueError('Physical budget accounting')
                if not np.isfinite(z['executed_actions']).all():
                    raise ValueError('Nonfinite action')
                np.testing.assert_array_equal(z['frame_t'], np.arange(meta['t'], row['terminal_final_t'] + 1))
                if len(z['frame_t']) != row['video_frames']:
                    raise ValueError('Frame accounting')
            for q, query in enumerate(row['queries'], start=5):
                if query['seeds'] != [job['rollout_seed'] + q * 1000 + i for i in range(4)]:
                    raise ValueError('Repeated or incorrect query seeds')
            diag = row['intervention']
            if not row['prefix_success']:
                expected = request_repair(arm, diag['initial_gate']['passed'], diag['fresh_gate']['passed'],
                                          diag['fresh_nonmiss_gate']['passed'], diag['fresh_gate_evaluated_after_success'])
                if expected != diag['repair_requested']:
                    raise ValueError('Gate routing mismatch')
            row.update(query_count=len(row['queries']), original_eligible=diag['initial_t72_trigger_passed'],
                       fresh_eligible=diag.get('fresh_gate', {}).get('passed', False),
                       checked_eligible=diag.get('fresh_nonmiss_gate', {}).get('passed', False),
                       repair_requested=diag['repair_requested'], repair_steps=diag['regrasp_steps'],
                       full_regrasp=diag.get('regrasp_diagnostics', {}).get('perception_regrasp_executed', False),
                       delay_queries=diag['delay_policy_queries'])
            group[arm] = row
            rows.append(row)
            if phase == 'smoke' and arm in ARMS[:3]:
                # Resolve copied remote source paths relative to this checkout for local review.
                source_root = directory.parent / Path(cfg['replay_source']).name
                source = source_root / job['source_phase'] / job['source_id'] / (arm + '.npz')
                if digest(source) != job['source_hashes'][source.name]:
                    raise ValueError('Changed smoke reference')
                arrays_equal(path.with_suffix('.npz'), source, ('executed_actions', 'final_state', 'signals'))
                audit['source_control_checks'] += 1
        ref = group[DELAYED[0]]
        for arm in DELAYED[1:]:
            row = group[arm]
            if ref['delay_queries']:
                validate_probe_pair(ref['intervention']['delay_end_audit'], row['intervention']['delay_end_audit'])
                with np.load(folder / (DELAYED[0] + '.npz'), allow_pickle=False) as a:
                    with np.load(folder / (arm + '.npz'), allow_pickle=False) as b:
                        n = ref['intervention']['delay_end_audit']['t'] - meta['t']
                        np.testing.assert_array_equal(a['executed_actions'][:n], b['executed_actions'][:n])
                audit['common_delay_checks'] += 1
            if ref['repair_requested'] == row['repair_requested']:
                arrays_equal(folder / (DELAYED[0] + '.npz'), folder / (arm + '.npz'),
                             ('executed_actions', 'final_state', 'signals'))
                audit['equal_decision_path_checks'] += 1
        if not group['continue_h8']['original_eligible']:
            for arm in ARMS[1:]:
                arrays_equal(folder / 'continue_h8.npz', folder / (arm + '.npz'),
                             ('executed_actions', 'final_state', 'signals'))
    out = directory / 'analysis' / phase
    out.mkdir(parents=True, exist_ok=True)
    result = dict(phase=phase, complete=not missing, missing=missing, branches=len(rows), pairs=len(rows) // len(ARMS),
                  audit=audit, automatic_holdout=False, full_benchmark=False)
    if not rows:
        atomic_json(out / 'summary.json', result)
        return result
    data = pd.DataFrame(rows)
    data.drop(columns=['queries']).to_json(out / 'branch_outcomes.json', orient='records', indent=2)
    scores = data.groupby(['cell', 'arm']).agg(n=('terminal_success', 'size'), successes=('terminal_success', 'sum'),
        sr=('terminal_success', 'mean'), drop_count=('terminal_target_drop_candidate', 'sum'),
        queries=('query_count', 'mean'), repair_rate=('repair_requested', 'mean')).reset_index()
    scores.to_csv(out / 'scores.csv', index=False)
    data.groupby('arm').agg(n=('terminal_success', 'size'), successes=('terminal_success', 'sum'),
        sr=('terminal_success', 'mean'), eligible_t72=('original_eligible', 'sum'), fresh=('fresh_eligible', 'sum'),
        checked=('checked_eligible', 'sum'), requests=('repair_requested', 'sum'), full=('full_regrasp', 'sum'),
        drop_count=('terminal_target_drop_candidate', 'sum'), queries=('query_count', 'mean')).to_csv(out / 'aggregate_scores.csv')
    effects = pd.DataFrame([contrast(data, left, right) for left, right in CONTRASTS])
    order = effects.sort_values('cluster_sign_p').index
    effects.loc[order, 'holm_p'] = np.minimum(1, np.maximum.accumulate(
        effects.loc[order, 'cluster_sign_p'].to_numpy() * np.arange(len(effects), 0, -1)))
    effects.to_csv(out / 'paired_effects.csv', index=False)
    gates = []
    for row in data.itertuples():
        d = row.intervention
        for when in ('initial_gate', 'fresh_gate', 'fresh_nonmiss_gate'):
            if when in d:
                gates.append(dict(job_id=row.job_id, cell=row.cell, arm=row.arm, when=when,
                                  **{k: v for k, v in d[when].items() if k != 'failed_checks'},
                                  failed_checks=','.join(d[when]['failed_checks'])))
    pd.DataFrame(gates).to_csv(out / 'gate_reasons.csv', index=False)
    result.update(effects=effects.to_dict('records'),
                  totals=data.groupby('arm').terminal_success.agg(['sum', 'count', 'mean']).reset_index().to_dict('records'))
    if phase == 'screen' and not missing:
        primary = effects[effects.left.eq(cfg['primary']) & effects.right.isin(['physical_regrasp', 'delayed_regrasp_h8'])]
        drops = data.groupby('arm').terminal_target_drop_candidate.sum()
        result['candidate_confirmation_worthwhile'] = bool(len(primary) == 2 and primary.ci_low.gt(0).all() and
            primary.holm_p.le(.05).all() and drops[cfg['primary']] <= drops['physical_regrasp'])
    atomic_json(out / 'summary.json', result)
    gallery = ['<!doctype html><meta charset="utf-8"><title>Timing and eligibility</title>',
               '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0}video{width:360px;max-width:100%}</style>']
    for case, group in data.groupby('job_id'):
        gallery.append('<h2>' + html.escape(case) + '</h2><div class="row">')
        for arm in ARMS:
            row = group[group.arm.eq(arm)].iloc[0]
            gallery.append(f'<figure><figcaption>{arm}: success={bool(row.terminal_success)}; repair={bool(row.repair_requested)}</figcaption>'
                           f'<video controls preload="none" src="../../{phase}/{case}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
    (out / 'videos.html').write_text('\n'.join(gallery))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14, 6), layout='constrained')
    scores.pivot(index='cell', columns='arm', values='sr').reindex(columns=ARMS).plot.bar(ax=ax)
    ax.set(ylabel='Terminal SR', ylim=(0, 1), title='Timing and eligibility: ' + phase)
    fig.savefig(out / 'success_rates.png', dpi=160)
    plt.close(fig)
    (out / 'RESULTS.md').write_text('\n'.join(['# Timing and eligibility: ' + phase, '',
        'Shared t72 prefix; K4/H8 suffix; 280 physical steps. Not a full benchmark.',
        'Latched unchecked is a simulator-only diagnostic; all primitive post-retreat guards remain enabled.',
        'Smoke is technical replay, not independent evidence. No automatic holdout or tuning.', '',
        scores.to_markdown(index=False), '', effects.to_markdown(index=False), '',
        '![SR](success_rates.png)', '[Videos](videos.html)', '', '```json', json.dumps(result, indent=2), '```']) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', choices=('smoke', 'screen'), required=True)
    args = parser.parse_args()
    result = analyze(args.campaign, args.phase)
    if not result['complete']:
        raise SystemExit('Incomplete phase: no automatic promotion')

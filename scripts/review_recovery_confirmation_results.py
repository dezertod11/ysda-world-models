#!/usr/bin/env python3
"""Descriptive review of audited recovery cases, with optional offline pose audit.

Never treats interrupted episodes as failures or opens a new GPU campaign.
No inferential statistics are added to an incomplete frozen phase.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.recovery_confirmation import expected_arms
    from scripts.p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from recovery_confirmation import expected_arms
    from p5_repeat_feedback import atomic_json, digest


def paired_counts(data, left, right):
    wide = data.pivot(index='job_id', columns='arm', values='terminal_success')
    if wide[[left, right]].isna().any().any():
        raise ValueError('Use only fully matched cases')
    a, b = wide[left].astype(bool), wide[right].astype(bool)
    return dict(method=left, control=right, n=len(wide), successes_method=int(a.sum()),
                successes_control=int(b.sum()), rescue=int((a & ~b).sum()),
                harm=int((~a & b).sum()), difference_pp=100 * float((a.astype(int) - b.astype(int)).mean()))


def prefix_pose_audit(folder, row):
    """Named object observation, not a guessed index in object_positions."""
    prefix = folder / 'prefix_72.npz'
    if digest(prefix) != row['prefix_sha256']:
        raise ValueError('Prefix changed since branch collection')
    targets = row['terminal_episode_target_objects'].split(',')
    if len(targets) != 1:
        raise ValueError('This audit requires a single named target')
    loc = row['intervention']['initial_localization']
    with np.load(prefix, allow_pickle=False) as arrays:
        true = np.asarray(arrays['obs__' + targets[0].strip() + '_pos'], dtype=float)
        eef = np.asarray(arrays['obs__robot0_eef_pos'], dtype=float)
    predicted = np.asarray([loc.get('perception_world_' + axis, np.nan) for axis in 'xyz'])
    return dict(target_object=targets[0], true_xyz=true.tolist(), predicted_xyz=predicted.tolist(),
                true_target_eef_m=float(np.linalg.norm(true - eef)),
                localization_xy_error_m=float(np.linalg.norm(predicted[:2] - true[:2])),
                localization_xyz_error_m=float(np.linalg.norm(predicted - true)), offline_gt_only=True)


def review(directory, *, prefix_audit=False):
    cfg = json.loads((directory / 'config.json').read_text())
    source = directory / 'analysis/main'
    audit = json.loads((source / 'summary.json').read_text())
    data = pd.read_json(source / 'branch_outcomes.json')
    complete_ids = set(data.job_id)
    if len(complete_ids) != audit['cases'] or len(data) != audit['branches']:
        raise ValueError('Analysis tables and audit summary disagree')
    out = directory / 'analysis/review'
    out.mkdir(parents=True, exist_ok=True)
    remaining = []
    committed = 0
    for job in cfg['jobs']:
        if job['phase'] != 'main':
            continue
        folder = directory / 'main' / job['id']
        missing = [arm for arm in expected_arms(job) if not (folder / (arm + '.json')).exists()]
        committed += len(expected_arms(job)) - len(missing)
        if missing:
            remaining.append(dict(job_id=job['id'], cohort=job['cohort'], cell=job['cell'],
                                  missing_arms=missing, rollout_seed=job['rollout_seed']))
    atomic_json(out / 'remaining_main.json', remaining)
    contrasts = []
    for cohort, block in data.groupby('cohort'):
        for a, b in (('physical_regrasp', 'continue_h8'), ('physical_regrasp', 'baseline_h16'),
                     ('refresh_preserve_only', 'physical_regrasp'), ('continue_h8', 'baseline_h16')):
            contrasts.append(dict(cohort=cohort, **paired_counts(block, a, b)))
    pd.DataFrame(contrasts).to_csv(out / 'descriptive_paired_counts.csv', index=False)
    cells = data.groupby(['cohort', 'cell', 'arm']).agg(
        n=('terminal_success', 'size'), successes=('terminal_success', 'sum'), sr=('terminal_success', 'mean'))
    cells.to_csv(out / 'cell_scores.csv')
    scores = data.groupby(['cohort', 'arm']).agg(n=('terminal_success', 'size'),
        successes=('terminal_success', 'sum'), sr=('terminal_success', 'mean'))
    scores['macro_cell_sr'] = cells.groupby(['cohort', 'arm']).sr.mean()
    scores.to_csv(out / 'cohort_scores.csv')
    detail = []
    for _, row in data[data.arm.eq('physical_regrasp')].iterrows():
        intervention = row.intervention
        gate = intervention.get('initial_gate', {})
        repair = intervention.get('regrasp_diagnostics', {})
        item = dict(job_id=row.job_id, cohort=row.cohort, cell=row.cell, success=bool(row.terminal_success),
            initial_allowed=intervention.get('initial_trigger_passed', False), full_regrasp=bool(row.full_regrasp),
            prefix_success=bool(intervention.get('prefix_success', False)),
            post_retreat_guard=repair.get('perception_guard_pass'),
            failure_proxy=row.terminal_failure_type,
            target_drop_proxy=bool(row.terminal_target_drop_candidate),
            target_lift_m=row.terminal_episode_episode_target_lift_max,
            confidence_pass=gate.get('confidence_pass'), workspace_pass=gate.get('workspace_pass'),
            miss_distance_pass=gate.get('miss_distance_pass'), reach_pass=gate.get('reach_pass'))
        if prefix_audit and not item['prefix_success']:
            item.update(prefix_pose_audit(directory / 'main' / row.job_id, row))
        detail.append(item)
    diagnostic = pd.DataFrame(detail)
    diagnostic.to_json(out / 'diagnostic_rows.json', orient='records', indent=2)
    gates = diagnostic.groupby('cohort').agg(n=('job_id', 'size'), initial_allowed=('initial_allowed', 'sum'),
        full_regrasp=('full_regrasp', 'sum'), confidence_pass=('confidence_pass', 'sum'),
        workspace_pass=('workspace_pass', 'sum'), miss_distance_pass=('miss_distance_pass', 'sum'))
    gates.to_csv(out / 'gate_counts.csv')
    pose = []
    if prefix_audit:
        for cohort, block in diagnostic.groupby('cohort'):
            for name, part in (('all', block), ('initial_allowed', block[block.initial_allowed]),
                               ('full_regrasp', block[block.full_regrasp])):
                error = part.localization_xy_error_m.dropna()
                pose.append(dict(cohort=cohort, subset=name, n=len(part), measured=len(error),
                    median_xy_error_m=float(error.median()), p90_xy_error_m=float(error.quantile(.9)),
                    xy_error_over_5cm=int(error.gt(.05).sum()), xy_error_over_10cm=int(error.gt(.1).sum())))
        pd.DataFrame(pose).to_csv(out / 'offline_localization_error.csv', index=False)
    labels = data[data.arm.ne('baseline_h16')].groupby(['cohort', 'arm', 'terminal_failure_type']).size()
    labels.rename('count').to_csv(out / 'suffix_failure_proxies.csv')
    summary = dict(analysis_complete=audit['complete'], inference_withheld=audit['inference_withheld'],
        fully_matched_cases=len(complete_ids), fully_matched_branches=len(data),
        committed_main_branches=committed, remaining_main_branches=sum(len(r['missing_arms']) for r in remaining),
        partial_case_outcomes_excluded=committed - len(data),
        scores=scores.reset_index().to_dict('records'), paired_descriptive=contrasts,
        gates=gates.reset_index().to_dict('records'), offline_pose=pose,
        source_sha256={name: digest(source / name) for name in ('summary.json', 'branch_outcomes.json')},
        new_event_controller_results=False, no_gpu_experiments_launched=True)
    atomic_json(out / 'summary.json', summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    arms = ['baseline_h16', 'continue_h8', 'physical_regrasp', 'refresh_preserve_only']
    colors = ['#686868', '#267f99', '#378756', '#ba4a68']
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
    for ax, (cohort, block) in zip(axes, scores.groupby(level='cohort')):
        table = block.droplevel('cohort').reindex(arms)
        bars = ax.bar(np.arange(4), table.sr * 100, color=colors)
        ax.bar_label(bars, labels=[f'{int(r.successes)}/{int(r.n)}' for _, r in table.iterrows()], padding=4)
        ax.set(ylim=(0, 100), title=f'{cohort}: complete pairs only', ylabel='Terminal success (%)')
        ax.set_xticks(np.arange(4), ['H16', 'H8 from 72', 'Regrasp', 'Preserve variant'])
    fig.suptitle('Interrupted main phase: descriptive snapshot, not final confirmation')
    fig.savefig(out / 'recovery_snapshot.png', dpi=160)
    plt.close(fig)
    if prefix_audit:
        fig, ax = plt.subplots(figsize=(8, 4), layout='constrained')
        for color, (cohort, block) in zip(colors, diagnostic.groupby('cohort')):
            values = np.sort(block.localization_xy_error_m.dropna().to_numpy()) * 100
            ax.step(values, np.arange(1, len(values) + 1) / len(values), label=f'{cohort} n={len(values)}', color=color)
        ax.set(xlabel='Offline target XY localization error (cm)', ylabel='Empirical CDF',
               title='Named target observation at branch point; not online input')
        ax.legend()
        fig.savefig(out / 'offline_localization_error.png', dpi=160)
        plt.close(fig)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--prefix-audit', action='store_true')
    args = parser.parse_args()
    result = review(args.campaign, prefix_audit=args.prefix_audit)
    print(json.dumps(result, indent=2))

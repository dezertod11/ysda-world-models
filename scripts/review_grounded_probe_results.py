#!/usr/bin/env python3
"""Post-hoc CPU audit; never changes the frozen grounded-probe controller."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_grounded_probe import analyze
    from scripts.analyze_feedback_controls import contrast
    from scripts.grounded_probe import ARMS
    from scripts.p5_repeat_feedback import atomic_json, digest
    from scripts.review_probe_repair_results import target_probe_motion, video_frames
except ModuleNotFoundError:
    from analyze_grounded_probe import analyze
    from analyze_feedback_controls import contrast
    from grounded_probe import ARMS
    from p5_repeat_feedback import atomic_json, digest
    from review_probe_repair_results import target_probe_motion, video_frames


def same_trajectory(directory, phase, case, left, right):
    folder = directory / phase / case
    with np.load(folder / (left + '.npz'), allow_pickle=False) as a:
        with np.load(folder / (right + '.npz'), allow_pickle=False) as b:
            return all(np.array_equal(a[k], b[k], equal_nan=True)
                       for k in ('executed_actions', 'final_state', 'signals'))


def decode_audit(directory, phases):
    import cv2
    videos = frames = 0
    for phase in phases:
        for path in sorted((directory / phase).glob('*/*.mp4')):
            row = json.loads(path.with_suffix('.json').read_text())
            cap = cv2.VideoCapture(str(path))
            decoded = 0
            try:
                if not cap.isOpened():
                    raise ValueError('Unreadable video: ' + str(path))
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if frame.size == 0:
                        raise ValueError('Empty frame: ' + str(path))
                    decoded += 1
            finally:
                cap.release()
            if decoded != row['video_frames']:
                raise ValueError('Decoded video frame mismatch: ' + str(path))
            videos += 1
            frames += decoded
    return dict(videos=videos, frames=frames, all_frame_counts_match=True)


def diagnostics(directory, phase):
    data = pd.read_json(directory / f'analysis/{phase}/branch_outcomes.json')
    for key, getter in {
        'trigger_t72': lambda d: d.get('initial_t72_trigger_passed', d['initial_trigger_passed']),
        'full_primitive': lambda d: d.get('regrasp_diagnostics', {}).get('perception_regrasp_executed', False),
        'repair_steps': lambda d: d['regrasp_steps'],
        'delay_queries': lambda d: d.get('delay_policy_queries', 0),
        'mask_reason': lambda d: d.get('masked', {}).get('reason'),
        'legacy_verdict': lambda d: d.get('legacy_verification'),
    }.items():
        data[key] = data.intervention.map(getter)
    return data


def motion_audit(directory, data):
    motions = []
    chosen = data[data.arm.isin(['probe_verify_repair', 'mask_verify_miss']) & data.probe_steps.gt(0)]
    for row in chosen.itertuples():
        folder = directory / 'screen' / row.job_id
        with np.load(folder / 'prefix.npz', allow_pickle=False) as z:
            prefix = {k: z[k].copy() for k in z.files}
        with np.load(folder / (row.arm + '.npz'), allow_pickle=False) as z:
            delta, eef = target_probe_motion(prefix, z, row.terminal_episode_target_objects, row.probe_steps)
            signals = pd.DataFrame(z['signals'], columns=z['signal_keys']).iloc[:row.probe_steps]
        contact = int(signals.robot_target_contact_count.gt(0).sum())
        mm = float(np.linalg.norm(delta) * 1000)
        motions.append(dict(job_id=row.job_id, cell=row.cell, arm=row.arm, verification=row.verification,
                            target_displacement_mm=mm, eef_displacement_mm=float(np.linalg.norm(eef) * 1000),
                            target_dz_mm=float(delta[2] * 1000), contact_steps=contact,
                            held_static_no_contact=row.verification == 'held' and mm < .1 and contact == 0,
                            success=row.terminal_success, mask_reason=row.mask_reason))
    return pd.DataFrame(motions)


def parity_audit(directory, data):
    counts = dict(no_trigger_case_comparisons=0, equivalent_probe_path_comparisons=0,
                  delayed_no_repair_comparisons=0, conservative_always_bitwise_equal=0)
    for (phase, case), group in data.groupby(['phase', 'job_id']):
        rows = group.set_index('arm')
        if not bool(rows.loc['continue_h8', 'trigger_t72']):
            for arm in rows.index.drop('continue_h8'):
                if not same_trajectory(directory, phase, case, 'continue_h8', arm):
                    raise ValueError(f'No-trigger trajectory mismatch: {phase}/{case}/{arm}')
                counts['no_trigger_case_comparisons'] += 1
        delayed = rows.loc['delayed_regrasp_h8']
        if delayed.delay_queries and not delayed.repair_steps:
            if not same_trajectory(directory, phase, case, 'continue_h8', 'delayed_regrasp_h8'):
                raise ValueError(f'Delayed no-repair trajectory mismatch: {phase}/{case}')
            counts['delayed_no_repair_comparisons'] += 1
        if phase != 'screen':
            continue
        for arm in ('probe_verify_repair', 'mask_verify_miss', 'mask_verify_conservative'):
            row = rows.loc[arm]
            control = 'probe_always_regrasp' if row.repair_requested else 'probe_only'
            if bool(rows.loc[control, 'repair_requested']) != bool(row.repair_requested):
                continue
            if not same_trajectory(directory, phase, case, control, arm):
                raise ValueError(f'Equivalent probe path mismatch: {case}/{arm}/{control}')
            counts['equivalent_probe_path_comparisons'] += 1
        counts['conservative_always_bitwise_equal'] += int(same_trajectory(
            directory, phase, case, 'mask_verify_conservative', 'probe_always_regrasp'))
    return counts


def plots(directory, out, data, motion):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), layout='constrained')
    for ax, phase in zip(axes, ('screen', 'transfer')):
        part = data[data.phase.eq(phase)]
        arms = [a for a in ARMS if a in part.arm.unique()]
        scores = part.groupby('arm').terminal_success.agg(['sum', 'count', 'mean']).reindex(arms)
        ax.barh(np.arange(len(arms)), scores['mean'], color='#278c83')
        ax.set_yticks(np.arange(len(arms)), arms, fontsize=9)
        ax.invert_yaxis()
        for i, row in enumerate(scores.itertuples()):
            ax.text(row.mean + .015, i, f'{row.sum}/{row.count}', va='center', fontsize=9)
        ax.set(xlim=(0, 1), xlabel='Terminal success rate', title=f'{phase}: 48 matched states / 24 init clusters')
    fig.savefig(out / 'aggregate_success.png', dpi=160)
    plt.close(fig)

    screen = data[data.phase.eq('screen')]
    mask = screen[screen.arm.eq('mask_verify_miss') & screen.probe_steps.gt(0)]
    transitions = pd.crosstab(mask.legacy_verdict, mask.verification).reindex(
        index=['held', 'miss', 'unknown'], columns=['held', 'miss', 'unknown'], fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    axes[0].imshow(transitions, cmap='Blues', vmin=0)
    axes[0].set(xticks=range(3), xticklabels=transitions.columns, yticks=range(3),
                yticklabels=transitions.index, xlabel='Mask verdict', ylabel='Legacy verdict',
                title='Same 27 physical probes')
    for i in range(3):
        for j in range(3):
            axes[0].text(j, i, str(transitions.iloc[i, j]), ha='center', va='center',
                         color='white' if transitions.iloc[i, j] > 6 else 'black')
    for arm, marker in [('probe_verify_repair', 'o'), ('mask_verify_miss', 'x')]:
        part = motion[(motion.arm.eq(arm)) & motion.verification.eq('held')]
        axes[1].scatter(part.eef_displacement_mm, part.target_displacement_mm, marker=marker, label=arm)
    axes[1].set(xlabel='EEF displacement (mm)', ylabel='Actual object displacement (mm)',
                title='Held verdict: simulator audit only')
    axes[1].legend(fontsize=8)
    fig.savefig(out / 'verifier_audit.png', dpi=160)
    plt.close(fig)

    selections = []
    for phase, worse, better in [('screen', 'mask_verify_miss', 'mask_verify_conservative'),
                                 ('transfer', 'delayed_regrasp_h8', 'physical_regrasp')]:
        part = data[data.phase.eq(phase)]
        wide = part.pivot(index='job_id', columns='arm', values='terminal_success')
        cases = sorted(wide.index[~wide[worse] & wide[better]])
        if not cases:
            continue
        case = cases[0]
        arms = ['continue_h8', 'physical_regrasp', worse, better]
        arms = list(dict.fromkeys(arms))
        fig, axes = plt.subplots(len(arms), 5, figsize=(13, 2.5 * len(arms)), layout='constrained', squeeze=False)
        for i, arm in enumerate(arms):
            row = part[part.job_id.eq(case) & part.arm.eq(arm)].iloc[0]
            times = [72, 75 if phase == 'screen' else 80, 104, 152, int(row.terminal_final_t)]
            indices = [max(0, min(t, int(row.terminal_final_t)) - int(row.prefix_t)) for t in times]
            frames, n, _ = video_frames(directory / phase / case / (arm + '.mp4'), indices)
            if n != row.video_frames:
                raise ValueError('Storyboard decoded frame mismatch')
            for j, index in enumerate(indices):
                image = frames[index]
                axes[i, j].imshow(image[:, :image.shape[1] // 2])
                axes[i, j].set(xticks=[], yticks=[], title=f't={row.prefix_t + index}')
            axes[i, 0].set_ylabel(f'{arm}\nsuccess={bool(row.terminal_success)}', fontsize=8)
        fig.suptitle(f'{phase}: {case}; first sorted rescue example, not representative evidence')
        name = phase + '_diagnostic_storyboard.png'
        fig.savefig(out / name, dpi=140)
        plt.close(fig)
        selections.append(dict(phase=phase, case=case, worse=worse, better=better, figure=name))
    return selections


def review(directory):
    summaries = {}
    for phase in ('smoke', 'screen', 'transfer'):
        summary = analyze(directory, phase)
        if not summary['complete']:
            raise ValueError('Review requires complete ' + phase)
        summaries[phase] = summary
    out = directory / 'review_20260911'
    out.mkdir(exist_ok=True)
    data = pd.concat([diagnostics(directory, phase) for phase in ('screen', 'transfer')], ignore_index=True)
    motion = motion_audit(directory, data[data.phase.eq('screen')])
    parity = parity_audit(directory, data)
    data.drop(columns=['intervention']).to_csv(out / 'branch_diagnostics.csv', index=False)
    motion.to_csv(out / 'probe_motion_audit.csv', index=False)
    aggregate = data.groupby(['phase', 'arm']).agg(
        n=('terminal_success', 'size'), successes=('terminal_success', 'sum'), sr=('terminal_success', 'mean'),
        t72_eligible=('trigger_t72', 'sum'), effective_trigger=('initial_trigger_passed', 'sum'),
        repair_requests=('repair_requested', 'sum'), full_primitive=('full_primitive', 'sum'),
        drop_proxy_count=('terminal_target_drop_candidate', 'sum'),
        mean_queries=('query_count', 'mean'), mean_final_t=('terminal_final_t', 'mean'),
        mean_branch_seconds=('elapsed_seconds', 'mean')).reset_index()
    aggregate.to_csv(out / 'aggregate_scores.csv', index=False)
    data.groupby(['phase', 'cell', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(out / 'cell_scores.csv')
    effects = [dict(phase='screen', diagnostic_only=True, **contrast(data[data.phase.eq('screen')], left, right))
               for left, right in [('probe_only', 'continue_h8'), ('physical_regrasp', 'continue_h8'),
                                   ('probe_always_regrasp', 'physical_regrasp'),
                                   ('mask_verify_miss', 'probe_verify_repair')]]
    pd.DataFrame(effects).to_csv(out / 'posthoc_effects.csv', index=False)
    screen = data[data.phase.eq('screen')]
    mask = screen[screen.arm.eq('mask_verify_miss') & screen.probe_steps.gt(0)]
    pd.crosstab(mask.legacy_verdict, mask.verification).to_csv(out / 'verdict_transitions.csv')
    mask.groupby(['verification', 'mask_reason']).size().to_csv(out / 'mask_abstention_reasons.csv')
    data[data.arm.eq('delayed_regrasp_h8')].groupby(['phase', 'cell']).agg(
        eligible_t72=('trigger_t72', 'sum'), fresh_trigger=('initial_trigger_passed', 'sum'),
        full_regrasp=('full_primitive', 'sum'), success=('terminal_success', 'sum')).to_csv(out / 'delay_trigger_audit.csv')
    selected = plots(directory, out, data, motion)
    decoded = decode_audit(directory, summaries)
    checked = sum(s['branches'] for s in summaries.values())
    if decoded['videos'] != checked:
        raise ValueError('Incomplete video audit')
    status = json.loads((directory / 'sequence_status.json').read_text())
    launch = json.loads((directory / 'launch.json').read_text())
    if digest(directory / 'config.json') != launch['config_sha256']:
        raise ValueError('Configuration differs from launch')
    result = dict(config_sha256=digest(directory / 'config.json'),
                  status=status['status'], video_decode_audit=decoded,
                  integrity_checked_branches=checked, scientific_screen_branches=summaries['screen']['branches'],
                  transfer_branches=summaries['transfer']['branches'],
                  holdout_started=status['holdout_started'], config_unchanged=True, simulator_diagnostics_posthoc_only=True,
                  bitwise_parity=parity, posthoc_effects=effects, aggregate=aggregate.to_dict('records'),
                  held_audit=motion.groupby('arm').agg(
                      probes=('job_id', 'size'), held=('verification', lambda x: int(x.eq('held').sum())),
                      held_static_no_contact=('held_static_no_contact', 'sum')).reset_index().to_dict('records'),
                  storyboard_selection=selected)
    atomic_json(out / 'summary.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, default=Path(__file__).resolve().parents[1] /
                        'experiments/campaigns/grounded_probe_20260911_v2')
    review(parser.parse_args().campaign)

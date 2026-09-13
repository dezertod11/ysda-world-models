#!/usr/bin/env python3
"""Post-hoc mechanism audit, separate from the frozen timing experiment."""
import argparse
from datetime import datetime
import html
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_timing_eligibility import analyze
    from scripts.p5_repeat_feedback import atomic_json, digest
    from scripts.review_grounded_probe_results import decode_audit, same_trajectory
    from scripts.review_probe_repair_results import video_frames
    from scripts.timing_eligibility import ARMS, DELAYED
except ModuleNotFoundError:
    from analyze_timing_eligibility import analyze
    from p5_repeat_feedback import atomic_json, digest
    from review_grounded_probe_results import decode_audit, same_trajectory
    from review_probe_repair_results import video_frames
    from timing_eligibility import ARMS, DELAYED

LABELS = ['Continue', 'Immediate', 'Delayed fresh', 'Latched checked', 'Latched diagnostic']


def pair_cases(data, left, right):
    wide = data.pivot(index='job_id', columns='arm', values='terminal_success')
    if wide[[left, right]].isna().any().any():
        raise ValueError('Incomplete paired comparison')
    return dict(rescues=sorted(wide.index[wide[left] & ~wide[right]]),
                harms=sorted(wide.index[~wide[left] & wide[right]]))


def gate_partition(data):
    part = data[data.arm.eq('delayed_regrasp_h8') & data.original_eligible]
    counts = dict(initial_eligible=len(part), fresh_pass=0, miss_only_block=0,
                  other_block=0, success_during_delay=0)
    for row in part.itertuples():
        d = row.intervention
        if d['fresh_gate_evaluated_after_success']:
            counts['success_during_delay'] += 1
        elif d['fresh_gate']['passed']:
            counts['fresh_pass'] += 1
        elif d['fresh_nonmiss_gate']['passed']:
            counts['miss_only_block'] += 1
        else:
            counts['other_block'] += 1
    assert sum(v for k, v in counts.items() if k != 'initial_eligible') == len(part)
    return counts


def branch_diagnostics(data):
    result = data.copy()
    for key, getter in {
        'initial_failed_checks': lambda d: ','.join(d['initial_gate']['failed_checks']),
        'fresh_failed_checks': lambda d: ','.join(d['fresh_gate']['failed_checks']),
        'fresh_score': lambda d: d['fresh_localization']['perception_score_range'],
        'score_threshold': lambda d: d['fresh_gate']['score_threshold'],
        'post_retreat_score': lambda d: d.get('regrasp_diagnostics', {}).get('perception_score_range'),
        'post_retreat_failed_checks': lambda d: ','.join(k.removeprefix('perception_guard_')
            for k, v in d.get('regrasp_diagnostics', {}).items()
            if k in ('perception_guard_finite_pass', 'perception_guard_confidence_pass',
                     'perception_guard_workspace_pass', 'perception_guard_reach_pass') and v is False),
    }.items():
        result[key] = result.intervention.map(getter)
    return result


def parity_audit(directory, data):
    counters = dict(no_repair_matches_continue=0, no_initial_trigger_matches_continue=0,
                    checked_fresh_equal_trajectories=0, checked_fresh_equal_outcomes=0)
    for case, part in data.groupby('job_id'):
        rows = part.set_index('arm')
        for arm in ARMS[1:]:
            if not rows.loc[arm, 'repair_requested']:
                if not same_trajectory(directory, 'screen', case, 'continue_h8', arm):
                    raise ValueError(f'No-repair parity failed: {case}/{arm}')
                counters['no_repair_matches_continue'] += 1
                counters['no_initial_trigger_matches_continue'] += int(not rows.loc[arm, 'original_eligible'])
        counters['checked_fresh_equal_trajectories'] += int(same_trajectory(
            directory, 'screen', case, DELAYED[0], DELAYED[1]))
        counters['checked_fresh_equal_outcomes'] += int(
            rows.loc[DELAYED[0], 'terminal_success'] == rows.loc[DELAYED[1], 'terminal_success'])
    return counters


def plot_results(directory, out, data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    agg = data.groupby('arm').agg(n=('terminal_success', 'size'), successes=('terminal_success', 'sum'),
                                requested=('repair_requested', 'sum'), full=('full_regrasp', 'sum')).reindex(ARMS)
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), layout='constrained')
    y = np.arange(len(ARMS))
    axes[0].barh(y, agg.successes / agg.n, color=['#727272', '#207567', '#4669a1', '#b36c19', '#a44265'])
    for i, row in enumerate(agg.itertuples()):
        axes[0].text(row.successes / row.n + .01, i, f'{row.successes}/{row.n}', va='center')
    axes[0].set(xlim=(0, 1), xlabel='Terminal success rate', title='96 paired states, 48 init clusters')
    comparisons = [pair_cases(data, arm, 'physical_regrasp') for arm in ARMS]
    axes[1].barh(y, [len(p['rescues']) for p in comparisons], color='#207567', label='Rescues')
    axes[1].barh(y, [-len(p['harms']) for p in comparisons], color='#a44265', label='Harms')
    axes[1].axvline(0, color='black', linewidth=.8)
    axes[1].set(xlabel='Paired outcome changes', title='Compared with immediate recovery')
    axes[1].legend()
    axes[2].barh(y - .18, agg.requested, height=.35, label='Requested (includes retreat)', color='#4669a1')
    axes[2].barh(y + .18, agg.full, height=.35, label='Passed post-retreat guard', color='#b36c19')
    axes[2].set(xlabel='Branch count', title='Requests are not full recovery')
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.set_yticks(y, LABELS, fontsize=9)
        ax.invert_yaxis()
    fig.savefig(out / 'overview.png', dpi=160)
    plt.close(fig)

    eligible = data[data.arm.eq('delayed_regrasp_h8') & data.original_eligible]
    reasons = eligible.fresh_failed_checks.replace('', 'passed').value_counts()
    fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
    reasons.plot.barh(ax=ax, color='#4669a1')
    ax.set(xlabel='States', title='Fresh gate after the same 8 actions: initially eligible only')
    fig.savefig(out / 'fresh_gate_reasons.png', dpi=160)
    plt.close(fig)

    selections = []
    for left, right, kind in [('delayed_latched_h8', 'delayed_regrasp_h8', 'rescues'),
                              ('delayed_latched_h8', 'delayed_regrasp_h8', 'harms'),
                              ('physical_regrasp', 'continue_h8', 'harms')]:
        cases = pair_cases(data, left, right)[kind]
        if cases:
            selections.append(dict(left=left, right=right, kind=kind, case=cases[0]))
    gallery = ['<!doctype html><meta charset="utf-8"><title>Timing: mechanism examples</title>',
               '<style>body{font:16px sans-serif;margin:24px}.row{display:flex;flex-wrap:wrap;gap:16px}figure{margin:0;width:512px;max-width:100%}video{width:100%}</style>',
               '<h1>Post-hoc mechanism examples</h1><p>First sorted rescue/harm cases, not representative sampling. '
               'Video starts at physical t=72; terminal times differ. All five strategies are shown.</p>']
    for selection in selections:
        case = selection['case']
        fig, axes = plt.subplots(len(ARMS), 6, figsize=(17, 9), layout='constrained', squeeze=False)
        gallery.append('<h2>' + html.escape(f'{case}: {selection["left"]} {selection["kind"]} vs {selection["right"]}') + '</h2><div class="row">')
        for i, arm in enumerate(ARMS):
            row = data[data.job_id.eq(case) & data.arm.eq(arm)].iloc[0]
            times = [72, 80, 83, 104, 160, int(row.terminal_final_t)]
            indices = [max(0, min(t, int(row.terminal_final_t)) - int(row.prefix_t)) for t in times]
            frames, n, _ = video_frames(directory / 'screen' / case / (arm + '.mp4'), indices)
            if n != row.video_frames:
                raise ValueError('Storyboard frame count mismatch')
            for j, index in enumerate(indices):
                axes[i, j].imshow(frames[index])
                axes[i, j].set(xticks=[], yticks=[], title=f't={row.prefix_t + index}' + (' terminal' if j == 5 else ''))
            axes[i, 0].set_ylabel(f'{LABELS[i]}\nsuccess={bool(row.terminal_success)}', fontsize=9)
            gallery.append(f'<figure><figcaption>{arm}: success={bool(row.terminal_success)}, '
                f'request={bool(row.repair_requested)}, full={bool(row.full_regrasp)}</figcaption>'
                f'<video controls preload="none" src="../screen/{case}/{arm}.mp4"></video></figure>')
        gallery.append('</div>')
        fig.suptitle(f'{case}: post-hoc first sorted {selection["kind"]}; final column uses each branch terminal time')
        selection['figure'] = f'{case}_storyboard.png'
        fig.savefig(out / selection['figure'], dpi=130)
        plt.close(fig)
    (out / 'selected_videos.html').write_text('\n'.join(gallery))
    return selections


def review(directory):
    summaries = {phase: analyze(directory, phase) for phase in ('smoke', 'screen')}
    if not all(s['complete'] for s in summaries.values()):
        raise ValueError('Complete phases required')
    launch = json.loads((directory / 'launch.json').read_text())
    status = json.loads((directory / 'sequence_status.json').read_text())
    if digest(directory / 'config.json') != launch['config_sha256'] or status['status'] != 'completed':
        raise ValueError('Changed configuration or incomplete campaign')
    out = directory / 'review_20260911'
    out.mkdir(exist_ok=True)
    data = branch_diagnostics(pd.read_json(directory / 'analysis/screen/branch_outcomes.json'))
    data.drop(columns='intervention').to_csv(out / 'branch_diagnostics.csv', index=False)
    parity = parity_audit(directory, data)
    gates = gate_partition(data)
    pair_rows = []
    for left, right in itertools.combinations(ARMS, 2):
        cases = pair_cases(data, left, right)
        pair_rows.append(dict(left=left, right=right, rescues=len(cases['rescues']), harms=len(cases['harms']),
                              delta=(len(cases['rescues']) - len(cases['harms'])) / data.job_id.nunique()))
    pd.DataFrame(pair_rows).to_csv(out / 'all_pair_counts_descriptive.csv', index=False)
    cancellation = data[data.arm.eq('delayed_regrasp_h8') & data.original_eligible & ~data.repair_requested]
    cancellation.groupby(['cell', 'fresh_failed_checks']).size().to_csv(out / 'cancellation_reasons.csv')
    cancelled_rows = data[data.job_id.isin(cancellation.job_id)]
    cancelled_rows.drop(columns='intervention').to_csv(out / 'cancelled_case_comparisons.csv', index=False)
    data[data.arm.eq('continue_h8')].groupby(['cell', 'initial_failed_checks']).agg(
        n=('job_id', 'size'), successes=('terminal_success', 'sum')).to_csv(out / 'initial_gate_coverage.csv')
    wide = data.pivot(index='job_id', columns='arm', values='terminal_success')
    all_fail = sorted(wide.index[~wide.any(axis=1)])
    data[data.job_id.isin(all_fail)].drop(columns='intervention').to_csv(out / 'all_method_failures.csv', index=False)
    data[data.terminal_target_drop_candidate].drop(columns='intervention').to_csv(out / 'drop_proxy_cases.csv', index=False)
    selections = plot_results(directory, out, data)
    decoded = decode_audit(directory, ('smoke', 'screen'))
    expected = sum(s['branches'] for s in summaries.values())
    if decoded['videos'] != expected:
        raise ValueError('Missing videos')
    aggregate = data.groupby('arm').agg(n=('job_id', 'size'), successes=('terminal_success', 'sum'),
        sr=('terminal_success', 'mean'), requests=('repair_requested', 'sum'), full=('full_regrasp', 'sum'),
        drop_proxies=('terminal_target_drop_candidate', 'sum'), mean_queries=('query_count', 'mean'),
        mean_final_t=('terminal_final_t', 'mean')).reindex(ARMS).reset_index()
    aggregate.to_csv(out / 'aggregate_scores.csv', index=False)
    finished = datetime.fromisoformat(status['updated_at'])
    started = datetime.fromisoformat(launch['started_at'])
    result = dict(config_unchanged=True, config_sha256=launch['config_sha256'],
        status=status['status'], finished_at=status['updated_at'], elapsed_minutes=(finished-started).total_seconds()/60,
        holdout_started=status['holdout_started'], integrity_checked_branches=expected,
        smoke_audit=summaries['smoke']['audit'], screen_audit=summaries['screen']['audit'],
        video_decode_audit=decoded, bitwise_parity=parity, gate_partition=gates,
        aggregate=aggregate.to_dict('records'), all_method_fail_cases=all_fail,
        observed_any_arm_successes=int(wide.any(axis=1).sum()),
        observed_immediate_continue_union=int(wide[['physical_regrasp', 'continue_h8']].any(axis=1).sum()),
        all_method_fail_original_eligible=int(data[data.arm.eq('continue_h8') & data.job_id.isin(all_fail)].original_eligible.sum()),
        candidate_confirmation_worthwhile=summaries['screen']['candidate_confirmation_worthwhile'],
        diagnostic_pairs=pair_rows, storyboard_selection=selections)
    atomic_json(out / 'summary.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, default=Path(__file__).resolve().parents[1] /
                        'experiments/campaigns/timing_eligibility_20260911_v2')
    review(parser.parse_args().campaign)

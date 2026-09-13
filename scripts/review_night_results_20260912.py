#!/usr/bin/env python3
"""CPU-only post-hoc review of the frozen September 12 studies."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_feedback_controls import contrast
    from scripts.p5_repeat_feedback import atomic_json, digest
    from scripts.review_grounded_probe_results import decode_audit
    from scripts.review_probe_repair_results import target_probe_motion, video_frames
    from scripts.decoder_token_medoid import SEED_GROUPS
    from scripts.decoder_medoid_night import STAGE_ARMS
except ModuleNotFoundError:
    from analyze_feedback_controls import contrast
    from p5_repeat_feedback import atomic_json, digest
    from review_grounded_probe_results import decode_audit
    from review_probe_repair_results import target_probe_motion, video_frames
    from decoder_token_medoid import SEED_GROUPS
    from decoder_medoid_night import STAGE_ARMS


def decoder_trace_audit(row, arrays):
    """Check selected actions and fresh RGB without importing a GPU model."""
    actions = arrays['executed_actions']
    end = row['terminal_final_t']
    if actions.shape != (end, 7) or not np.isfinite(actions).all() or not 0 < end <= 280:
        raise ValueError('Invalid action trace')
    np.testing.assert_array_equal(arrays['frame_t'], np.arange(end + 1))
    if row['video_frames'] != end + 1 or row['selector_uses_simulator_labels']:
        raise ValueError('Video/provenance mismatch')
    if row['generated_horizon'] != 16 or row['prediction_mode'] != 'parallel':
        raise ValueError('Changed model protocol')
    arm = row['arm']
    fixed = {'first': 0, 'fixed_candidate_1': 1, 'fixed_candidate_2': 2}.get(arm)
    seeds = list(SEED_GROUPS[row['seed_group']])
    expected_seeds = seeds if fixed is None else [seeds[fixed]]
    t, calls = 0, 0
    for q, query in enumerate(row['queries']):
        key = f'q{q:03d}_'
        n = query['executed']
        if query['query'] != q or query['t'] != t or query['t_after'] != t + n:
            raise ValueError('Query time mismatch')
        if not 0 < n <= row['executed_horizon'] or query['candidate_seeds'] != expected_seeds:
            raise ValueError('Horizon/seed mismatch')
        if query['prediction_error_horizon_aligned'] != (n == 16):
            raise ValueError('Prediction-error alignment mismatch')
        if n != 16 and query['prediction_errors']:
            raise ValueError('H16 prediction compared to an earlier observation')
        index = query['index']
        if fixed is not None:
            chosen = 0
        else:
            diagnostic = query['selectors']
            costs = {'decoder_medoid': 'decoder_costs', 'decoder_full_h8': 'decoder_costs',
                     'decoder_prefix_h8': 'prefix8_diagnostic_costs', 'action_medoid': 'action_costs'}
            chosen = int(np.argmin(diagnostic[costs[arm]])) if arm in costs else int(np.argmax(diagnostic['values']))
        if index != chosen:
            raise ValueError('Stored choice disagrees with selector')
        candidates = arrays[key + 'actions']
        if candidates.shape != (len(expected_seeds), 16, 7) or not np.isfinite(candidates).all():
            raise ValueError('Invalid candidate actions')
        np.testing.assert_array_equal(actions[t:t + n], candidates[index, :n])
        if q:
            for camera in ('external', 'wrist'):
                np.testing.assert_array_equal(arrays[key + 'input_' + camera],
                                              arrays[f'q{q - 1:03d}_actual_' + camera])
        if query['common_q0_pool'] != (q == 0):
            raise ValueError('q0 provenance mismatch')
        t += n
        calls += len(expected_seeds)
    if t != end or calls != row['candidate_calls_logical']:
        raise ValueError('Terminal time/model call mismatch')
    return len(row['queries'])


def selected_videos(directory, output, selections):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    parts = ['<!doctype html><meta charset="utf-8"><title>Selected paired outcomes</title>',
        '<style>body{font:15px sans-serif;margin:20px}.row{display:flex;flex-wrap:wrap;gap:12px}'
        'figure{margin:0;width:480px;max-width:100%}video{width:100%}</style>',
        '<h1>Post-hoc examples, not an unbiased sample</h1>',
        '<p>All recorded steps; observation study starts at t72, decoder study at t0.</p>']
    for number, (label, rows) in enumerate(selections):
        parts += ['<h2>' + html.escape(label) + '</h2><div class="row">']
        fig, axes = plt.subplots(len(rows), 4, figsize=(13, 2.5 * len(rows)), squeeze=False, layout='constrained')
        for i, row in enumerate(rows):
            identifier = row.get('job_id', row.get('id'))
            path = directory / row['phase'] / identifier / (row['arm'] + '.mp4')
            start, end = row.get('prefix_t', 0), int(row['terminal_final_t'])
            times = [min(end, t) for t in ([72, 75, 84, 97] if start else [0, 64, 128, 192])]
            images, count, _ = video_frames(path, [t - start for t in times])
            if count != row['video_frames']:
                raise ValueError('Selected video length mismatch')
            for j, t in enumerate(times):
                axes[i, j].imshow(images[t - start])
                axes[i, j].axis('off')
                axes[i, j].set_title(f"{row['arm']} | t={t} | SR={int(row['terminal_success'])}", fontsize=9)
            src = '../' + str(path.relative_to(directory))
            caption = f"{identifier}: {row['arm']}, success={row['terminal_success']}, t={start}..{end}"
            parts.append(f'<figure><figcaption>{html.escape(caption)}</figcaption>'
                         f'<video controls preload="none" src="{html.escape(src)}"></video></figure>')
        fig.savefig(output / f'example_{number}.png', dpi=140)
        plt.close(fig)
        parts.append('</div>')
    (output / 'selected_videos.html').write_text('\n'.join(parts))


def review_observation(directory, output):
    data = pd.read_json(directory / 'analysis/screen/branch_outcomes.json')
    if len(data) != 1536 or data.duplicated(['job_id', 'arm']).any():
        raise ValueError('Incomplete/duplicate observation study')
    effects = [dict(posthoc=True, **contrast(data, a, b)) for a, b in
               [('refresh_preserve_only', 'physical_regrasp'), ('physical_regrasp', 'continue_h8')]]
    pd.DataFrame(effects).to_csv(output / 'posthoc_contrasts.csv', index=False)
    data.groupby(['cell', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(output / 'cell_scores.csv')
    data.groupby(['suffix_repeat', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(output / 'suffix_scores.csv')
    wide = data.pivot(index='job_id', columns='arm', values='terminal_success')
    better, worse = 'refresh_preserve_only', 'refresh_preserve_regrasp'
    harms = set(wide.index[wide[better] & ~wide[worse]])
    probe_rows = data[data.refresh_requested & data.arm.eq(better)]
    motion, events = [], []
    for row in probe_rows.to_dict('records'):
        folder = directory / 'screen' / row['job_id']
        with np.load(folder / 'prefix.npz', allow_pickle=False) as z:
            prefix = {k: z[k].copy() for k in z.files}
        with np.load(folder / (better + '.npz'), allow_pickle=False) as z:
            steps = row['intervention']['probe_steps']
            target, eef = target_probe_motion(prefix, z, row['terminal_episode_target_objects'], steps)
            signals = pd.DataFrame(z['signals'], columns=z['signal_keys']).iloc[:steps]
        motion.append(dict(job_id=row['job_id'], cell=row['cell'],
            target_displacement_mm=float(np.linalg.norm(target) * 1000), target_dz_mm=float(target[2] * 1000),
            eef_displacement_mm=float(np.linalg.norm(eef) * 1000),
            contact_steps=int(signals.robot_target_contact_count.gt(0).sum()),
            extra_regrasp_harms=row['job_id'] in harms, previous_gripper=row['intervention']['previous_gripper']))
    for row in data[data.job_id.isin(harms) & data.arm.eq(worse)].to_dict('records'):
        drop_t = row['terminal_episode_target_drop_candidate_t']
        end = row['intervention_end_t']
        with np.load(directory / 'screen' / row['job_id'] / (worse + '.npz'), allow_pickle=False) as z:
            actions = z['executed_actions']
            probe_steps = row['intervention']['probe_steps']
            probe_gripper = float(actions[probe_steps - 1, 6])
            next_gripper = float(actions[probe_steps, 6])
            drop_gripper = float(actions[drop_t - row['prefix_t'] - 1, 6]) if drop_t > row['prefix_t'] else None
        events.append(dict(job_id=row['job_id'], cell=row['cell'], drop_t=drop_t,
            intervention_end_t=end, drop_during_intervention=72 < drop_t <= end,
            drop_proxy=row['terminal_target_drop_candidate'], probe_end_gripper=probe_gripper,
            next_gripper=next_gripper, gripper_at_drop=drop_gripper))
    motion = pd.DataFrame(motion)
    motion.to_csv(output / 'probe_motion.csv', index=False)
    pd.DataFrame(events).to_csv(output / 'extra_regrasp_harms.csv', index=False)
    selection = []
    for label, a, b in [('Extra regrasp harm', better, worse),
                        ('Preserved probe rescue', better, 'physical_regrasp')]:
        case = sorted(wide.index[wide[a] & ~wide[b]])[0]
        rows = data[data.job_id.eq(case)].set_index('arm').loc[['physical_regrasp', better, worse]].reset_index()
        selection.append((label, rows.to_dict('records')))
    selected_videos(directory, output, selection)
    return dict(branches=len(data), posthoc_contrasts=effects, probe_cases=len(motion),
        extra_regrasp_harms=len(harms), harms_with_drop_proxy=sum(e['drop_proxy'] for e in events),
        harms_drop_during_intervention=sum(e['drop_during_intervention'] for e in events),
        harmful_regrasp_probe_motion=motion[motion.extra_regrasp_harms].describe().to_dict(),
        scope='Existing prefixes; post-hoc diagnostics, not a new-init confirmation or an official Safety benchmark')


def review_decoder(directory, output):
    episodes, queries, selections = [], [], []
    parents = {}
    count = 0
    for stage, expected in [('screen', 720), ('seed_controls', 360), ('horizon8', 360)]:
        paths = sorted(p for p in (directory / stage).glob('*/*.json') if p.stem in STAGE_ARMS[stage])
        if len(paths) != expected:
            raise ValueError(f'Incomplete {stage}: {len(paths)}/{expected}')
        for path in paths:
            row = json.loads(path.read_text())
            identifier = row['id']
            if identifier not in parents:
                parent = directory / 'screen' / identifier
                start = json.loads((parent / 'start.json').read_text())
                pool = json.loads((parent / 'q0_pool.json').read_text())
                for name, meta in [('start', start), ('q0_pool', pool)]:
                    if digest(parent / (name + '.npz')) != meta['sha256']:
                        raise ValueError('Changed shared parent artifact')
                with np.load(parent / 'q0_pool.npz', allow_pickle=False) as z:
                    pooled = {k: z[k].copy() for k in ('actions', 'values')}
                parents[identifier] = dict(start=start, pool=pool, pooled=pooled)
            parent = parents[identifier]
            if row['initial_sha256'] != parent['start']['sha256'] or row['q0_pool_sha256'] != parent['pool']['sha256']:
                raise ValueError('Changed shared parent reference')
            if row['queries'][0]['input_hashes'] != parent['start']['input_hashes']:
                raise ValueError('Changed initial model input')
            with np.load(path.with_suffix('.npz'), allow_pickle=False) as z:
                count += decoder_trace_audit(row, z)
                fixed = {'first': 0, 'fixed_candidate_1': 1, 'fixed_candidate_2': 2}.get(row['arm'])
                for key, value in parent['pooled'].items():
                    np.testing.assert_array_equal(z['q000_' + key], value if fixed is None else value[[fixed]])
                for camera in ('external', 'wrist'):
                    key = 'q000_input_' + camera
                    if key not in parent:
                        parent[key] = z[key].copy()
                    np.testing.assert_array_equal(z[key], parent[key])
            episodes.append(row)
            for q in row['queries']:
                queries.append(dict(id=row['id'], arm=row['arm'], seed_group=row['seed_group'],
                    index=q.get('original_candidate_index', q['index']),
                    uniform_choice=q['selectors'].get('uniform_diagnostic_index'),
                    prefix_choice=q['selectors'].get('prefix8_diagnostic_index'),
                    full_choice=q['selectors'].get('indices', {}).get('decoder_medoid')))
    data = pd.DataFrame(episodes)
    data.groupby(['phase', 'factor', 'task_id', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(output / 'task_scores.csv')
    data.groupby(['phase', 'seed_group', 'arm']).terminal_success.agg(['sum', 'count', 'mean']).to_csv(output / 'seed_scores.csv')
    choice = pd.DataFrame(queries)
    choice.groupby(['arm', 'seed_group', 'index']).size().rename('queries').to_csv(output / 'choice_counts.csv')
    subset = choice[choice.arm.eq('decoder_medoid')]
    choices_per_episode = subset.groupby('id')['index'].nunique()
    group_choices = subset.groupby(['seed_group', 'index']).size().rename('queries').reset_index()
    group_choices['fraction'] = group_choices.queries / group_choices.groupby('seed_group').queries.transform('sum')
    group_choices.to_csv(output / 'decoder_seed_group_bias.csv', index=False)
    main = data[data.phase.eq('screen')]
    wide = main.pivot(index='id', columns='arm', values='terminal_success')
    for label, a, b in [('Decoder rescue', 'decoder_medoid', 'max_value'),
                        ('Decoder harm', 'max_value', 'decoder_medoid')]:
        case = sorted(wide.index[wide[a] & ~wide[b]])[0]
        selections.append((label, main[main.id.eq(case) & main.arm.isin([a, b])].to_dict('records')))
    selected_videos(directory, output, selections)
    return dict(rollouts=len(data), checked_queries=count, exact_selected_actions=True,
        fresh_rgb_exact_between_queries=True, horizon_alignment_passed=True,
        common_q0_verified_groups=len(parents), decoder_seed_group_bias=group_choices.to_dict('records'),
        constant_decoder_episodes=int(choices_per_episode.eq(1).sum()),
        decoder_episodes=len(choices_per_episode), decoder_choice_counts=subset['index'].value_counts().to_dict(),
        full_vs_prefix_disagreement_fraction=float(subset.full_choice.ne(subset.prefix_choice).mean()),
        full_vs_uniform_disagreement_fraction=float(subset.full_choice.ne(subset.uniform_choice).mean()),
        scope='Development grid, no confirmed gain; post-hoc choice diagnostics are not a new rollout sample')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--kind', choices=('observation', 'decoder'), required=True)
    parser.add_argument('--decode-videos', action='store_true')
    args = parser.parse_args()
    output = args.campaign / 'review_20260912'
    output.mkdir(exist_ok=True)
    result = (review_observation if args.kind == 'observation' else review_decoder)(args.campaign, output)
    if args.decode_videos:
        phases = ('smoke', 'screen') if args.kind == 'observation' else ('screen', 'seed_controls', 'horizon8')
        result['video_audit'] = decode_audit(args.campaign, phases)
    sources = ['analysis/screen/summary.json'] if args.kind == 'observation' else ['analysis/summary.json', 'night_analysis/summary.json']
    result['source_sha256'] = {p: digest(args.campaign / p) for p in sources}
    result['review_script_sha256'] = digest(Path(__file__))
    atomic_json(output / 'summary.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

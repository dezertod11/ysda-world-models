#!/usr/bin/env python3
"""Post-hoc CPU audit; never changes frozen collection or primary analysis."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pandas as pd

try:
    from scripts.analyze_p5_repeat_feedback import paired_effect
    from scripts.p5_repeat_feedback import array_digest, atomic_json, digest, schedule, suffix_seed
except ModuleNotFoundError:
    from analyze_p5_repeat_feedback import paired_effect
    from p5_repeat_feedback import array_digest, atomic_json, digest, schedule, suffix_seed

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = Path('/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP')


def local_path(path):
    path = Path(path)
    return ROOT / path.relative_to(SERVER_ROOT) if path.is_relative_to(SERVER_ROOT) else path


def repeat_selection(outcomes, values):
    """Tie-break only with frozen value, then index; test labels are never used."""
    outcomes = np.asarray(outcomes)
    values = np.asarray(values, dtype=float)
    if outcomes.ndim != 2 or outcomes.shape[1] < 2 or len(values) != len(outcomes):
        raise ValueError('Expected candidate x repeat outcomes and candidate values')
    if not np.isin(outcomes, [0, 1]).all() or not np.isfinite(values).all():
        raise ValueError('Expected binary outcomes and finite values')
    baseline = int(np.argmax(values))
    rows = []
    for held in range(outcomes.shape[1]):
        train = np.delete(outcomes, held, axis=1).mean(axis=1)
        ties = np.flatnonzero(train == train.max())
        chosen = int(ties[np.argmax(values[ties])])
        rows.append(dict(repeat=held, chosen=chosen, baseline=baseline,
                         selected_success=int(outcomes[chosen, held]),
                         baseline_success=int(outcomes[baseline, held])))
    return rows


def audit(directory, config, decode_videos):
    source = local_path(config['source'])
    assert digest(source) == config['source_sha256']
    for name, sha in config['scripts'].items():
        assert digest(ROOT / 'scripts' / name) == sha, name
    files = sorted((directory / 'runs').glob('*/r*_c*_*.json'))
    records = [json.loads(path.read_text()) for path in files]
    assert len(records) == config['expected_branches'] == 1080
    data = pd.DataFrame(records)
    assert not data.duplicated(['pool_id', 'repeat', 'candidate_idx', 'mode']).any()
    assert data.terminal_available.all() and data.prefix_integrity.all()
    endpoint_errors, video_records = [], []
    for pool in config['pools']:
        sub = directory / 'runs' / pool['id']
        assert json.loads((sub / 'completed.json').read_text())['status'] == 'completed'
        rows = data[data.pool_id.eq(pool['id'])]
        actual = set(rows[['repeat', 'candidate_idx', 'mode']].itertuples(index=False, name=None))
        assert actual == set(schedule(pool['selected']))
        assert rows.source_sha256.eq(pool['sidecar_sha256']).all()
        sidecar = local_path(pool['sidecar'])
        assert digest(sidecar) == pool['sidecar_sha256']
        with np.load(sidecar, allow_pickle=False) as saved:
            actions = saved['candidate_actions'].copy()
            endpoints = saved['candidate_endpoint_states'].copy()
        audit_row = json.loads((sub / 'replay_audit.json').read_text())
        assert audit_row['passed'] and max(audit_row['endpoint_errors']) <= 1e-9
        endpoint_errors.extend(audit_row['endpoint_errors'])
        for row in rows.itertuples():
            assert row.selected == (row.candidate_idx == pool['selected'])
            assert row.suffix_seed == suffix_seed(pool['rollout_seed'], row.repeat)
            assert row.policy_task_description == pool['task_description']
            assert row.saved_action_sha256 == array_digest(actions[row.candidate_idx])
            key = f'r{row.repeat}_c{row.candidate_idx}_{row.mode}'
            with np.load(sub / f'{key}.npz', allow_pickle=False) as arrays:
                executed = arrays['executed_actions']
                assert len(executed) == row.terminal_final_t - pool['t']
                np.testing.assert_array_equal(executed[:8], actions[row.candidate_idx, :8])
                if row.mode == 'open16':
                    np.testing.assert_array_equal(executed[:16], actions[row.candidate_idx])
                    np.testing.assert_allclose(arrays['endpoint_state'], endpoints[row.candidate_idx], atol=1e-9, rtol=0)
                else:
                    window = slice(0, 8) if row.mode == 'fresh8' else slice(8, 16)
                    np.testing.assert_array_equal(executed[8:16], arrays['requery_actions'][window])
                if row.video_path:
                    np.testing.assert_array_equal(arrays['frame_t'], np.arange(pool['t'], row.terminal_final_t + 1))
            if row.video_path:
                video = sub / f'{key}.mp4'
                assert video.exists() and row.video_frames == len(executed) + 1
                entry = dict(pool_id=pool['id'], mode=row.mode, path=str(video.relative_to(directory)),
                             expected_frames=row.video_frames)
                if decode_videos:
                    reader = imageio_ffmpeg.read_frames(str(video), pix_fmt='rgb24')
                    metadata = next(reader)
                    frames = 0
                    first = None
                    moving = False
                    for frame in reader:
                        if first is None:
                            first = frame
                        moving |= frame != first
                        frames += 1
                    assert frames == row.video_frames and moving, video
                    assert np.frombuffer(first, dtype=np.uint8).std() > 1, video
                    entry.update(decoded_frames=frames, moving=moving, fps=metadata['fps'])
                video_records.append(entry)
    assert len(video_records) == 108
    frozen = pd.read_parquet(directory / 'analysis/branch_outcomes.parquet')
    keys = ['pool_id', 'repeat', 'candidate_idx', 'mode']
    pd.testing.assert_frame_equal(data.sort_values(keys).reset_index(drop=True)[sorted(data.columns)],
                                  frozen.sort_values(keys).reset_index(drop=True)[sorted(data.columns)])
    return data, dict(branches=len(data), pools=len(config['pools']), source_sha256=digest(source),
                      script_hashes_verified=len(config['scripts']), saved_sidecars_verified=36,
                      replay_endpoints=288, max_replay_error=float(max(endpoint_errors)),
                      video_count=len(video_records), videos_decoded=decode_videos), video_records


def analyze(directory, decode_videos=False):
    config = json.loads((directory / 'config.json').read_text())
    output = directory / 'review_20260910'
    output.mkdir(exist_ok=True)
    data, integrity, videos = audit(directory, config, decode_videos)
    print('Integrity audit passed', flush=True)
    pd.DataFrame(videos).to_csv(output / 'video_integrity.csv', index=False)
    selected = data[data.selected]
    effects = pd.DataFrame([paired_effect(selected, 'fresh8', ref) for ref in ['stale8', 'open16']])
    old = pd.read_csv(directory / 'analysis/paired_effects.csv')
    np.testing.assert_allclose(effects[['delta_sr', 'ci95_low', 'ci95_high', 'cluster_signflip_p']],
                               old[['delta_sr', 'ci95_low', 'ci95_high', 'cluster_signflip_p']])
    splits = []
    for dimension in ['factor', 'case_id', 'task_id', 'query_idx', 'repeat']:
        for level, group in selected.groupby(dimension):
            for mode, arm in group.groupby('mode'):
                splits.append(dict(dimension=dimension, level=level, mode=mode, branches=len(arm),
                                   successes=int(arm.terminal_success.sum()), sr=float(arm.terminal_success.mean())))
    pd.DataFrame(splits).to_csv(output / 'descriptive_splits.csv', index=False)
    query_effects = pd.DataFrame([dict(query_idx=q, **paired_effect(g, 'fresh8', ref))
                                  for q, g in selected.groupby('query_idx') for ref in ['stale8', 'open16']])
    query_effects.to_csv(output / 'exploratory_query_effects.csv', index=False)
    base = data[data['mode'].eq('open16')]
    rows, opportunities, rank_pairs = [], [], []
    original = pd.read_parquet(local_path(config['source']))
    identity = ['case_id', 'task_id', 'init_state_id', 'query_idx', 'candidate_idx']
    joined = base.merge(original[identity + ['terminal_success']].rename(columns={'terminal_success': 'original_success'}),
                       on=identity, validate='many_to_one')
    assert len(joined) == len(base)
    pools = {p['id']: p for p in config['pools']}
    for pool_id, group in base.groupby('pool_id'):
        pool = pools[pool_id]
        outcomes = group.pivot(index='candidate_idx', columns='repeat', values='terminal_success').sort_index().to_numpy(dtype=int)
        values = group.groupby('candidate_idx').candidate_value.first().sort_index().to_numpy()
        assert outcomes.shape == (8, 3)
        old_group = joined[joined.pool_id.eq(pool_id)].groupby('candidate_idx').original_success.first().sort_index()
        for k in (4, 8):
            labels, val = outcomes[:k], values[:k]
            baseline = int(np.argmax(val))
            q = labels.mean(axis=1)
            meta = dict(pool_id=pool_id, k=k, task_id=pool['task_id'], init_state_id=pool['init_state_id'],
                        query_idx=pool['query_idx'], case_id=pool['case_id'])
            opportunities.append(dict(**meta, max_value_sr=q[baseline], empirical_best_sr=q.max(),
                optimistic_gap=q.max() - q[baseline], random_sr=q.mean(),
                all_new_fail=not labels.any(), original_all_fail=not old_group.iloc[:k].any(),
                baseline_idx=baseline, baseline_successes=int(labels[baseline].sum()),
                best_successes=int(labels.sum(axis=1).max())))
            for result in repeat_selection(labels, val):
                rows.append(dict(**meta, **result))
        for i, j in itertools.combinations(range(8), 2):
            diff = outcomes[i].mean() - outcomes[j].mean()
            if diff:
                concordant = .5 if values[i] == values[j] else float(diff * (values[i] - values[j]) > 0)
                rank_pairs.append(dict(pool_id=pool_id, concordant=concordant))
    cv = pd.DataFrame(rows)
    op = pd.DataFrame(opportunities)
    cv.to_csv(output / 'leave_one_suffix_out_predictions.csv', index=False)
    op.to_csv(output / 'pool_opportunities.csv', index=False)
    cv_effects = []
    for k, group in cv.groupby('k'):
        long = pd.concat([group.assign(mode=mode, terminal_success=group[field])
                          for mode, field in [('repeat_selector', 'selected_success'), ('max_value', 'baseline_success')]])
        cv_effects.append(dict(k=int(k), **paired_effect(long, 'repeat_selector', 'max_value')))
    cv_effects = pd.DataFrame(cv_effects)
    cv_effects.to_csv(output / 'leave_one_suffix_out_effects.csv', index=False)
    stability = base.groupby(['pool_id', 'candidate_idx']).terminal_success.sum()
    support = op.groupby('k').agg(pools=('pool_id', 'size'), max_value_sr=('max_value_sr', 'mean'),
        optimistic_best_sr=('empirical_best_sr', 'mean'), optimistic_gap=('optimistic_gap', 'mean'),
        random_sr=('random_sr', 'mean'), all_new_fail=('all_new_fail', 'sum'))
    for k in (4, 8):
        group = cv[cv.k.eq(k)]
        support.loc[k, 'leave_one_suffix_out_sr'] = group.selected_success.mean()
        support.loc[k, 'changed_selection_fraction'] = group.chosen.ne(group.baseline).mean()
    support.to_csv(output / 'selection_summary.csv')
    k8 = op[op.k.eq(8)]
    duration = float(data.elapsed_seconds.sum() / 3600)
    sequence = json.loads((directory / 'sequence_status.json').read_text())
    wall_hours = (datetime.fromisoformat(sequence['finished_at']) - datetime.fromisoformat(sequence['started_at'])).total_seconds() / 3600
    summary = dict(reviewed_at=datetime.now(timezone.utc).isoformat(), status='completed', integrity=integrity,
        frozen_primary_analysis_reproduced=True, new_gpu_runs=False, development_only=True,
        candidate_success_histogram={str(n): int(stability.eq(n).sum()) for n in range(4)},
        changed_labels_from_original=int(joined.terminal_success.ne(joined.original_success).sum()),
        label_comparisons=len(joined), variable_candidates=int(stability.isin([1, 2]).sum()),
        all_fail_pools_original=int(k8.original_all_fail.sum()), all_fail_pools_repeats=int(k8.all_new_fail.sum()),
        original_all_fail_with_new_success=int((k8.original_all_fail & ~k8.all_new_fail).sum()),
        repeats_with_optimistic_gap=int(k8.optimistic_gap.gt(0).sum()),
        value_pair_concordance=float(pd.DataFrame(rank_pairs).concordant.mean()),
        comparable_candidate_pairs=len(rank_pairs), branch_worker_hours=duration, dispatcher_wall_hours=wall_hours,
        primary_effects=old.to_dict('records'), split_repeat_effects=cv_effects.to_dict('records'),
        selection_summary=support.reset_index().to_dict('records'),
        limitations=['10 task/init clusters; 36 development snapshots; no Environment factor',
                     'Three suffixes are not enough to estimate true Q reliably',
                     'Leave-one-suffix-out is post-hoc, privileged, not a deployable learned model',
                     'Snapshot intervention is not an always-H8 complete-episode controller',
                     'RNG variation includes numerical nondeterminism; not calibrated epistemic uncertainty'])
    atomic_json(output / 'summary.json', summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    modes = ['open16', 'stale8', 'fresh8']
    colors = ['#60666b', '#b47b29', '#277f8e']
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.7), layout='constrained')
    for ax, query in zip(axes, [None, 0, 3]):
        sub = selected if query is None else selected[selected.query_idx.eq(query)]
        stats = sub.groupby('mode').terminal_success.agg(['sum', 'size', 'mean']).loc[modes]
        bars = ax.bar(modes, stats['mean'] * 100, color=colors)
        ax.bar_label(bars, [f'{int(r["sum"])}/{int(r["size"])}' for _, r in stats.iterrows()], padding=3)
        ax.set(ylim=(0, 100), ylabel='Snapshot branch success (%)',
               title='All snapshots' if query is None else f'Query {query}: exploratory')
        ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(output / 'feedback_by_query.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout='constrained')
    axes[0].bar(range(4), [int(stability.eq(n).sum()) for n in range(4)], color=['#a95058', '#c09239', '#41898c', '#52734b'])
    axes[0].set(xticks=range(4), xlabel='Successes across 3 suffix seeds', ylabel='Saved action candidates', title='96/288 candidates change label')
    labels = ['Max-value', 'Best on same repeats', 'Held-out suffix selector']
    for idx, (column, color) in enumerate(zip(['max_value_sr', 'optimistic_best_sr', 'leave_one_suffix_out_sr'], colors)):
        axes[1].bar(np.arange(2) + (idx-1)*.24, support[column]*100, width=.24, color=color, label=labels[idx])
    axes[1].set(xticks=np.arange(2), xticklabels=['K4', 'K8'], ylim=(0, 75), ylabel='Snapshot branch success (%)', title='Optimism vs. held-out suffix')
    axes[1].legend(fontsize=8)
    fig.savefig(output / 'suffix_noise_and_selection.png', dpi=170)
    plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, default=ROOT / 'experiments/campaigns/p5_repeat_feedback_20260910')
    parser.add_argument('--decode-videos', action='store_true')
    args = parser.parse_args()
    analyze(args.campaign.resolve(), args.decode_videos)

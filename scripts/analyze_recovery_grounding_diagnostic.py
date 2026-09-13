#!/usr/bin/env python3
"""Descriptive mechanism tables and technical replay/shadow gates."""
import argparse
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

from recovery_grounding_diagnostic import ARMS, SMOKE_CASES
from resume_recovery_confirmation import retry_atomic_json as atomic_json
from p5_repeat_feedback import digest


def analyze(directory):
    cfg = json.loads((directory / 'config.json').read_text())
    output = directory / 'analysis'
    output.mkdir(parents=True, exist_ok=True)
    geometry = []
    for job in cfg['cases']:
        path = directory / 'geometry' / (job['id'] + '.json')
        if path.exists():
            row = json.loads(path.read_text())
            geometry.append(dict(job_id=job['id'], cohort=job['cohort'], cell=job['cell'], **row['views'][0]))
    if geometry:
        pd.DataFrame(geometry).to_csv(output / 'geometry.csv', index=False)
    records, committed = [], 0
    for job in cfg['cases']:
        paths = [directory / 'rollouts' / job['id'] / (arm + '.json') for arm in ARMS]
        committed += sum(path.exists() for path in paths)
        if not all(path.exists() for path in paths):
            continue
        for path in paths:
            row = json.loads(path.read_text())
            for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
                if digest(path.with_suffix(ext)) != row[key]:
                    raise ValueError('Diagnostic artifact hash mismatch')
            intervention = row['intervention']
            records.append(dict(job_id=job['id'], cell=job['cell'], cohort=job['cohort'], arm=row['arm'],
                success=bool(row['terminal_success']), repair_requested=intervention['repair_requested'],
                full_regrasp=intervention['primitive'].get('perception_regrasp_executed', False),
                waypoint_safety_block=bool(intervention['post_guard'] and not intervention['post_guard']['waypoint_safety_pass']),
                primitive_steps=intervention.get('primitive_steps', 0), replay_verified=row['replay_reference_verified']))
    shadow = []
    for job in cfg['cases']:
        if job['id'] not in SMOKE_CASES:
            continue
        stem = f'{job["suite"]}_t{job["task_id"]}_i{job["init_state_id"]}_s{job["rollout_seed"]}'
        paths = [directory / 'shadow' / job['id'] / mode / (stem + '.json') for mode in ('none', 'shadow')]
        if not all(p.exists() for p in paths):
            continue
        rows = [json.loads(p.read_text()) for p in paths]
        with np.load(paths[0].with_suffix('.npz'), allow_pickle=False) as a, np.load(paths[1].with_suffix('.npz'), allow_pickle=False) as b:
            np.testing.assert_array_equal(a['executed_actions'], b['executed_actions'])
        if rows[0]['terminal_success'] != rows[1]['terminal_success'] or any(e['executed'] for e in rows[1]['events']):
            raise ValueError('Shadow changed execution or terminal label')
        shadow.append(dict(job_id=job['id'], action_parity=True, events=len(rows[1]['events']),
                           physical_interventions=0, uncalibrated_technical_smoke_only=True))
    scores, contrasts = [], []
    if records:
        data = pd.DataFrame(records)
        data.to_csv(output / 'matched_outcomes.csv', index=False)
        for cohort, block in data.groupby('cohort'):
            wide = block.pivot(index='job_id', columns='arm', values='success')
            for arm in ARMS:
                scores.append(dict(cohort=cohort, arm=arm, n=len(wide), successes=int(wide[arm].sum()), sr=float(wide[arm].mean())))
            for a, b in ((ARMS[1], ARMS[0]), (ARMS[2], ARMS[1]), (ARMS[3], ARMS[2])):
                contrasts.append(dict(cohort=cohort, method=a, control=b, n=len(wide),
                    rescue=int((wide[a] & ~wide[b]).sum()), harm=int((~wide[a] & wide[b]).sum()),
                    difference_pp=100 * float((wide[a].astype(int) - wide[b].astype(int)).mean())))
        pd.DataFrame(scores).to_csv(output / 'scores.csv', index=False)
        pd.DataFrame(contrasts).to_csv(output / 'paired_descriptive.csv', index=False)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
        for ax, cohort in zip(axes, ('replication', 'transfer')):
            group = [s for s in scores if s['cohort'] == cohort]
            if not group:
                ax.set_title(cohort + ': pending')
                continue
            bars = ax.bar(np.arange(4), [s['sr'] * 100 for s in group], color=['#686868', '#267f99', '#378756', '#ba4a68'])
            ax.bar_label(bars, labels=[f'{s["successes"]}/{s["n"]}' for s in group], padding=4)
            ax.set(ylim=(0, 100), title=cohort, ylabel='Success (%)')
            ax.set_xticks(np.arange(4), ['RGB', 'GT XY\nfixed gate', 'GT XYZ\nfixed gate', 'GT XYZ\nphysical gate'])
        fig.suptitle('Privileged mechanism diagnostic: not deployable method scores')
        fig.savefig(output / 'oracle_diagnostic_sr.png', dpi=160)
        plt.close(fig)
    summary = dict(planned_cases=len(cfg['cases']), geometry_cases=len(geometry),
        committed_outcomes=committed, fully_matched_cases=len(records) // len(ARMS),
        complete=committed == len(cfg['cases']) * len(ARMS), scores=scores, paired_descriptive=contrasts,
        shadow=shadow, diagnostic_only=True, no_inferential_claim=True,
        oracle_not_deployable=True, new_event_sr_claim=False)
    atomic_json(output / 'summary.json', summary)
    text = ['# Grounding diagnostic', '', 'Exploratory privileged diagnostic, not a deployable method or independent holdout.',
        f'Geometry {len(geometry)}/{len(cfg["cases"])}; committed outcomes {committed}/{len(cfg["cases"])*4}; matched cases {len(records)//4}.',
        '', '| Cohort | Arm | Success | SR |', '|---|---|---:|---:|']
    text += [f'| {s["cohort"]} | {s["arm"]} | {s["successes"]}/{s["n"]} | {100*s["sr"]:.2f}% |' for s in scores]
    text += ['', 'Fixed-gate oracle arms retain initial and post-retreat RGB gates, with an explicit physical waypoint safety veto.',
        'Physical-gate oracle changes confidence/workspace eligibility as well as the waypoint; separate coverage diagnostic.',
        'See geometry.csv for pixel detection, backprojection, plane-height and target visibility measurements.',
        'Shadow comparisons check action equality without executed interventions. Thresholds are not calibrated.',
        '', '[Videos](videos.html)']
    (output / 'RESULTS.md').write_text('\n'.join(text) + '\n')
    page = ['<!doctype html><meta charset="utf-8"><title>Grounding diagnostics</title>',
            '<style>body{font:14px sans-serif;margin:20px}.row{display:flex;gap:12px;flex-wrap:wrap}video{width:420px;max-width:100%}figure{margin:8px 0}figcaption{max-width:420px;overflow-wrap:anywhere}</style>',
            '<h1>Privileged grounding diagnostics</h1><p>GT arms are diagnostics, not deployable methods.</p>']
    for job in cfg['cases']:
        page += [f'<h2>{html.escape(job["id"])}</h2><div class="row">']
        for arm in ARMS:
            path = directory / 'rollouts' / job['id'] / (arm + '.json')
            if path.exists():
                row = json.loads(path.read_text())
                page.append(f'<figure><figcaption>{arm}: success={row["terminal_success"]}</figcaption><video controls preload="none" src="../rollouts/{job["id"]}/{arm}.mp4"></video></figure>')
        page.append('</div>')
    (output / 'videos.html').write_text('\n'.join(page))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    analyze(parser.parse_args().campaign)

#!/usr/bin/env python3
"""Offline target-pose audit of the previous campaign, never a policy input."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from observation_contract import gate, refresh_allowed
from p5_repeat_feedback import atomic_json, digest
from perception_regrasp import canonical_object_name


def audit(root, output):
    parent = root / 'experiments/campaigns/timing_eligibility_20260911_v2'
    cfg = json.loads((parent / 'config.json').read_text())
    artifact = json.loads((root / 'experiments/frozen_models/perception_regrasp_20260904/perception_regrasp_trigger_v1.json').read_text())
    rows = []
    for job in cfg['jobs']:
        if job['phase'] != 'screen':
            continue
        folder = parent / 'screen' / job['id']
        previous = json.loads((folder / 'physical_regrasp.json').read_text())
        meta = json.loads((folder / 'prefix.json').read_text())
        if digest(folder / 'prefix.npz') != meta['sha256']:
            raise ValueError('Changed prefix')
        loc = previous['intervention']['initial_localization']
        with np.load(folder / 'prefix.npz', allow_pickle=False) as z:
            target = previous['terminal_episode_target_objects']
            truth = z['obs__' + target + '_pos'].copy()
            eef = z['obs__robot0_eef_pos'].copy()
            grip = float(z['prefix_actions'][-1, 6])
        pred = np.array([loc['perception_world_' + a] for a in 'xyz'])
        original = gate(loc, eef, artifact)
        object_name = canonical_object_name(previous['task_description'])
        oracle = dict(perception_object=object_name,
            perception_score_range=artifact['objects'][object_name]['score_range_lower'],
            **{'perception_world_' + a: float(v) for a, v in zip('xyz', truth)})
        calibrated = gate(oracle, eef, artifact)
        physical = gate(oracle, eef, artifact, physical=True)
        all_failed = not any(json.loads((folder / (a + '.json')).read_text())['terminal_success'] for a in cfg['arms'])
        rows.append(dict(source_id=job['id'], cell=job['cell'], init_state_id=job['init_state_id'],
            repeat=job['repeat'], target=target, error_3d_m=float(np.linalg.norm(pred - truth)),
            eef_z=float(eef[2]), previous_gripper=grip, original_eligible=original.passed,
            refresh_eligible=refresh_allowed(original, eef, grip),
            oracle_calibrated_eligible=calibrated.passed, oracle_physical_eligible=physical.passed,
            true_position_in_calibration_box=calibrated.workspace_pass, all_previous_arms_failed=all_failed,
            prefix_sha256=meta['sha256']))
    data = pd.DataFrame(rows)
    output.mkdir(parents=True, exist_ok=True)
    data.to_csv(output / 'prefix_geometry_audit.csv', index=False)
    cells = data.groupby('cell').agg(prefixes=('source_id', 'size'), median_error_m=('error_3d_m', 'median'),
        learned_eligible=('original_eligible', 'sum'), refresh_eligible=('refresh_eligible', 'sum'),
        oracle_calibrated_eligible=('oracle_calibrated_eligible', 'sum'),
        oracle_physical_eligible=('oracle_physical_eligible', 'sum'),
        all_previous_arms_failed=('all_previous_arms_failed', 'sum'))
    cells.to_csv(output / 'cell_geometry_audit.csv')
    summary = dict(parent_config_sha256=digest(parent / 'config.json'), prefixes=len(data),
        diagnostic_only=True, median_body_origin_error_m=float(data.error_3d_m.median()),
        cells=cells.reset_index().to_dict('records'))
    atomic_json(output / 'summary.json', summary)
    (output / 'README.md').write_text('# Previous-prefix geometry audit\n\n'
        'Post-hoc simulator-label diagnostic, not an online input or new evidence.\n'
        '3D error is relative to the target body origin, not a validated grasp contact point.\n'
        'Oracle eligibility is not oracle success. Physical bounds are not collision/IK certification.\n\n'
        + cells.to_markdown() + '\n')
    print(cells.to_string())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(Path(__file__).resolve().parents[1], args.output)

#!/usr/bin/env python3
"""Calibrate query thresholds on successful development episode GROUP maxima.

This is not a learned failure/benefit head or an OOD coverage guarantee.
Geometric and persistence hyperparameters remain explicit development choices.
"""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path

import numpy as np

try:
    from event_feedback import EventConfig
    from p5_repeat_feedback import atomic_json, digest
except ModuleNotFoundError:
    from scripts.event_feedback import EventConfig
    from scripts.p5_repeat_feedback import atomic_json, digest


FEATURES = {'action_prefix_std': 'action_std_threshold', 'value_std': 'value_std_threshold',
            'overlap_pose_rmse': 'overlap_rmse_threshold'}


def group_id(case):
    # Conservatively keep the same suite/task/init together, even across position levels.
    return f'{case["suite"]}/{case["task_id"]}/{case["init_state_id"]}'


def calibrate(rows, config, alpha=.1):
    if not 0 < alpha < 1:
        raise ValueError('alpha must be in (0, 1)')
    if not rows or any(row['timing'] not in ('none', 'shadow') for row in rows):
        raise ValueError('Use complete non-intervened development episodes')
    groups = {}
    for row in rows:
        if not row['success']:
            continue
        case = row['case']
        values = groups.setdefault(group_id(case), {name: [] for name in FEATURES})
        for query in row['queries']:
            for name in FEATURES:
                value = query['metrics'].get(name)
                if value is not None and math.isfinite(value):
                    values[name].append(float(value))
    parameters, report = asdict(config), {}
    # Bonferroni across features that were actually observed. Missing overlap is not zero.
    observed = [name for name in FEATURES if any(g[name] for g in groups.values())]
    if not observed:
        raise ValueError('No successful development query measurements')
    for name in observed:
        maxima = sorted(max(g[name]) for g in groups.values() if g[name])
        rank = math.ceil((len(maxima) + 1) * (1 - alpha / len(observed)))
        if rank > len(maxima):
            raise ValueError(f'Insufficient independent groups for {name}: {len(maxima)}; increase development data')
        threshold = max(float(maxima[rank - 1]), 1e-8)
        parameters[FEATURES[name]] = threshold
        report[name] = dict(groups=len(maxima), rank=rank, threshold=threshold)
    # H16 shadow has no overlap. Disable its decision contribution until separately calibrated.
    disabled = [name for name in FEATURES if name not in observed]
    for name in disabled:
        parameters[FEATURES[name]] = float(np.finfo(np.float64).max)
    EventConfig(**parameters)
    return parameters, dict(status='development_group_max_calibration', alpha=alpha,
        calibration_groups=sorted({group_id(row['case']) for row in rows}),
        successful_groups=sorted(groups), scores=report, disabled_features=disabled,
        guarantee='none claimed under OOD/dependent task groups; not failure probability',
        unchanged='geometry, persistence, sensor interval, cooldown, intervention budget')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', type=Path, required=True)
    parser.add_argument('--parameters', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--alpha', type=float, default=.1)
    args = parser.parse_args()
    rows, hashes, configurations = [], {}, []
    for run in args.runs:
        cfg = json.loads((run / 'config.json').read_text())
        configuration = {k: cfg[k] for k in
                         ('config', 'samples', 'method', 'scripts', 'runtime_hashes', 'perception_hashes')}
        configurations.append(configuration)
        if cfg['timing'] not in ('none', 'shadow'):
            raise ValueError('Calibration run contains interventions')
        for case in cfg['cases']:
            name = f'{case["suite"]}_t{case["task_id"]}_i{case["init_state_id"]}_s{case["rollout_seed"]}.json'
            path = run / name
            row = json.loads(path.read_text())
            if row['config_sha256'] != digest(run / 'config.json'):
                raise ValueError('Changed calibration run config')
            if any(digest(path.with_suffix(ext)) != row[key] for ext, key in
                   (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256'))):
                raise ValueError('Changed calibration episode')
            hashes[str(path.resolve())] = digest(path)
            rows.append(row)
    if any(c != configurations[0] for c in configurations):
        raise ValueError('Do not pool incompatible monitors or model settings')
    base = EventConfig(**json.loads(args.parameters.read_text()))
    if json.loads(json.dumps(asdict(base))) != configurations[0]['config']:
        raise ValueError('Base parameters differ from observed calibration controller')
    parameters, report = calibrate(rows, base, args.alpha)
    report.update(source_hashes=hashes, source_configuration=configurations[0])
    if args.output.exists() or args.output.with_suffix('.calibration.json').exists():
        raise ValueError('Do not overwrite a frozen calibration')
    atomic_json(args.output, parameters)
    report['parameters_sha256'] = digest(args.output)
    atomic_json(args.output.with_suffix('.calibration.json'), report)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Preserve the original paired analysis; require genuinely new v2 prefixes."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_recovery_confirmation import analyze
from recovery_confirmation import job_done
from resume_recovery_confirmation import retry_atomic_json as atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', choices=('main', 'timing'), required=True)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    config = json.loads((args.campaign / 'config.json').read_text())
    from run import validate
    validate(config)
    checked = 0
    for job in config['jobs']:
        if job['phase'] != args.phase or not job_done(args.campaign, job, hashes=True):
            continue
        path = args.campaign / 'main' / job['case_id'] / f'prefix_{job["boundary"]}.npz'
        with np.load(path, allow_pickle=False) as values:
            if values['runtime_v2__schema_version'].item() != 2:
                raise ValueError('Incomplete legacy runtime snapshot')
            if not np.isfinite(values['runtime_v2__integration_state']).all():
                raise ValueError('Invalid integration state')
        checked += 1
    result = analyze(args.campaign, args.phase)
    result.update(runtime_snapshot_version=2, checked_v2_prefixes=checked,
                  config_sha256=__import__('hashlib').sha256((args.campaign / 'config.json').read_bytes()).hexdigest(),
                  technical_only=config['technical_only'])
    if config['technical_only']:
        result['inference_withheld'] = True
    atomic_json(args.campaign / 'analysis' / args.phase / 'summary.json', result)
    print(json.dumps(result, indent=2))
    if args.require_complete and not result['complete']:
        raise SystemExit('Incomplete phase')


if __name__ == '__main__':
    main()

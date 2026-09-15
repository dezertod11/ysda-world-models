#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))

if __name__ == '__main__':
    from contract import install
    install()
    from analyze_recovery_confirmation import analyze
    from resume_recovery_confirmation import retry_atomic_json as atomic_json
    from ablation_queue import validate
    parser=argparse.ArgumentParser()
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--phase',choices=['main'],required=True)
    parser.add_argument('--require-complete',action='store_true')
    args=parser.parse_args()
    config=json.loads((args.campaign/'config.json').read_text()); validate(config)
    result=analyze(args.campaign,args.phase)
    result.update(runtime_snapshot_version=2, reused_baseline_arms=3,
                  new_arm='retreat_requery', parent_config_sha256=config['reused_config_sha256'])
    atomic_json(args.campaign/'analysis/main/summary.json',result)
    print(json.dumps(result,indent=2))
    if args.require_complete and not result['complete']:
        raise SystemExit('Incomplete ablation')

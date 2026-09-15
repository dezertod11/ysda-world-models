#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'experiments/runtime_replay_v2'))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--batch',type=Path,required=True)
    args=parser.parse_args()
    from ablation_queue import validate
    batch=json.loads(args.batch.read_text())
    validate(json.loads((Path(batch['campaign'])/'config.json').read_text()))
    import runtime_snapshot as v2
    sys.modules['libero_runtime_snapshot']=v2
    sys.modules['scripts.libero_runtime_snapshot']=v2
    from contract import install,install_intervention
    install(); install_intervention()
    import collect_recovery_confirmation
    try:
        collect_recovery_confirmation.main()
    except InterruptedError as error:
        print(error,flush=True)

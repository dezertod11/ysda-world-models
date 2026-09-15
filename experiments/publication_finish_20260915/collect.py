#!/usr/bin/env python3
"""Use the unchanged recovery collector with complete integration snapshots."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'experiments/runtime_replay_v2'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    from run import validate
    validate(json.loads((Path(batch['campaign']) / 'config.json').read_text()))
    import runtime_snapshot as v2
    sys.modules['libero_runtime_snapshot'] = v2
    sys.modules['scripts.libero_runtime_snapshot'] = v2
    import collect_recovery_confirmation
    collect_recovery_confirmation.main()


if __name__ == '__main__':
    try:
        main()
    except InterruptedError as error:
        print(str(error), flush=True)

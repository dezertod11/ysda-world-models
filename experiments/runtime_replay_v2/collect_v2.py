#!/usr/bin/env python3
"""Opt-in v2 snapshot entrypoint; the frozen collector and audit stay unchanged."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    from run_v2 import validate_v2
    validate_v2(json.loads((Path(batch["campaign"]) / "config.json").read_text()))
    # Keep the legacy module object inside v2, but route subsequent imports to v2.
    import runtime_snapshot as v2
    sys.modules["libero_runtime_snapshot"] = v2
    from collect_p3_benchmark import collect
    collect(batch)


if __name__ == "__main__":
    main()

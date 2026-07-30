#!/usr/bin/env python3
"""Wait for a detached LIBERO campaign and run its standard analysis."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def campaign_status(campaign_dir: Path) -> str:
    manifest_path = campaign_dir / "manifest.json"
    if not manifest_path.is_file():
        return "missing"
    return str(json.loads(manifest_path.read_text(encoding="utf-8")).get("status", "missing"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.resolve()
    while True:
        status = campaign_status(campaign_dir)
        print(f"[watch] campaign={campaign_dir.name} status={status}", flush=True)
        if status == "completed":
            break
        if status == "failed":
            print("[watch] campaign failed; analysis was not started", file=sys.stderr)
            return 1
        time.sleep(max(args.poll_seconds, 1.0))

    output_dir = campaign_dir / "analysis" / "full_validation"
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/analyze_libero_8h_validation.py"),
            "--campaign-dir",
            str(campaign_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    if args.summarize:
        subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts/summarize_libero_final_results.py"),
                "--analysis-dir",
                str(output_dir),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
    print(f"[watch] analysis={output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

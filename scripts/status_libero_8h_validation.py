#!/usr/bin/env python3
"""Print compact progress for a running long LIBERO campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def episode_count(path: Path) -> tuple[int, int, int]:
    frame = pd.read_parquet(path)
    if frame.empty:
        return 0, 0, 0
    keys = [column for column in ["pair_id", "rollout_id"] if column in frame]
    episodes = frame.sort_values("query_idx").groupby(keys, dropna=False).first()
    success = episodes["success"]
    if not pd.api.types.is_bool_dtype(success):
        success = success.astype(str).str.lower().isin({"true", "1"})
    return len(episodes), int(success.sum()), int((~success).sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.campaign_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    completed = {path.stem for path in (args.campaign_dir / "completed").glob("*.json")}
    trace_paths = sorted((args.campaign_dir / "runs").glob("*__query_traces.parquet"))
    episodes = successes = failures = 0
    for path in trace_paths:
        try:
            n, good, bad = episode_count(path)
        except Exception:
            continue
        episodes += n
        successes += good
        failures += bad

    jobs = manifest.get("jobs", [])
    print(f"campaign: {args.campaign_dir.name}")
    print(f"manifest status: {manifest.get('status', 'missing')}")
    print(f"completed jobs: {len(completed)} / {len(jobs)}")
    print(f"trace files: {len(trace_paths)}")
    print(f"rollouts: {episodes} ({successes} success, {failures} fail)")
    for job in jobs:
        state = "done" if job["name"] in completed else "running/pending"
        log_path = args.campaign_dir / "logs" / f"{job['name']}.log"
        size = log_path.stat().st_size if log_path.is_file() else 0
        print(f"  GPU {job['gpu']}: {job['name']}: {state}, log={size} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

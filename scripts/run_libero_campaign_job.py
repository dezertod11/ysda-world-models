#!/usr/bin/env python3
"""Resume one campaign job while its parent campaign scheduler is stopped."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.run_libero_experiment_campaign import (
        expand_jobs,
        load_campaign,
        run_job,
    )
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from run_libero_experiment_campaign import expand_jobs, load_campaign, run_job


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--gpu", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    campaign = load_campaign(args.config)
    if args.profile not in campaign["profiles"]:
        raise ValueError(f"Unknown profile: {args.profile}")
    jobs = expand_jobs(
        campaign["profiles"][args.profile], campaign.get("defaults", {})
    )
    matches = [job for job in jobs if str(job["name"]) == args.job]
    if len(matches) != 1:
        available = ", ".join(str(job["name"]) for job in jobs)
        raise ValueError(f"Expected one job {args.job!r}; available: {available}")

    run_dir = PROJECT_ROOT / "experiments" / "campaigns" / args.run_prefix
    result = run_job(
        matches[0],
        args.run_prefix,
        run_dir,
        str(args.gpu),
        bool(args.force),
    )
    print(json.dumps(result, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

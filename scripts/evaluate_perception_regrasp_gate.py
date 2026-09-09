#!/usr/bin/env python3
"""Sequential gate for accelerated perception-regrasp campaigns."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analyze_recovery_proposal_opportunity import clustered_mean_interval, load_outputs


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    branches, _queries = load_outputs(args.campaign_dir.expanduser().resolve())
    frame = branches.loc[branches["proposal"].eq("perception_regrasp_h8")].copy()
    for column in (
        "terminal_success",
        "strict_replay",
        "terminal_episode_target_drop_candidate",
        "terminal_episode_official_safety_violation",
        "source_feedback_drop",
        "source_feedback_safety",
    ):
        frame[column] = frame[column].astype(str).str.lower().isin({"true", "1", "yes"})
    success = frame["terminal_success"].astype(float)
    ci_low, ci_high = clustered_mean_interval(
        frame,
        success,
        repetitions=args.bootstrap_repetitions,
        seed=20260904,
    )
    successful = frame.loc[frame["terminal_success"]]
    cells = successful.assign(
        cell=successful["position_level"].astype(str)
        + "|task"
        + successful["task_id"].astype(int).astype(str)
    )["cell"].nunique()
    metrics = {
        "rows": int(len(frame)),
        "expected_rows": args.expected_states,
        "strict_replay_rate": float(frame["strict_replay"].mean()),
        "successes": int(frame["terminal_success"].sum()),
        "success_rate": float(frame["terminal_success"].mean()),
        "success_ci_low": ci_low,
        "success_ci_high": ci_high,
        "rescued_cells": int(cells),
        "rescued_tasks": int(successful["task_id"].nunique()),
        "drop_rate_delta": float(
            frame["terminal_episode_target_drop_candidate"].mean()
            - frame["source_feedback_drop"].mean()
        ),
        "safety_rate_delta": float(
            frame["terminal_episode_official_safety_violation"].mean()
            - frame["source_feedback_safety"].mean()
        ),
    }
    checks = {
        "complete": metrics["rows"] == args.expected_states,
        "strict_replay": metrics["strict_replay_rate"] >= 0.95,
        "minimum_success_rate": metrics["success_rate"] >= args.min_success_rate,
        "breadth_cells": metrics["rescued_cells"] >= args.min_cells,
        "breadth_tasks": metrics["rescued_tasks"] >= args.min_tasks,
        "drop_delta": metrics["drop_rate_delta"] <= args.max_drop_delta,
        "safety_delta": metrics["safety_rate_delta"] <= args.max_safety_delta,
    }
    if args.require_ci_positive:
        checks["bootstrap_lower_positive"] = metrics["success_ci_low"] > 0.0
    result: dict[str, object] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "campaign_dir": str(args.campaign_dir),
        "metrics": metrics,
        "checks": checks,
        "gate_pass": all(checks.values()),
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.expanduser().resolve().write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-states", type=int, required=True)
    parser.add_argument("--min-success-rate", type=float, required=True)
    parser.add_argument("--min-cells", type=int, required=True)
    parser.add_argument("--min-tasks", type=int, required=True)
    parser.add_argument("--max-drop-delta", type=float, default=0.05)
    parser.add_argument("--max-safety-delta", type=float, default=0.025)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    parser.add_argument("--require-ci-positive", action="store_true")
    args = parser.parse_args()
    return 0 if evaluate(args)["gate_pass"] else 5


if __name__ == "__main__":
    raise SystemExit(main())

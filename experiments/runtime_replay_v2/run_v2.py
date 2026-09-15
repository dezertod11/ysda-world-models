#!/usr/bin/env python3
"""Prepare fresh v2 replicas; launches require an explicit future deadline."""

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/campaigns/p3_benchmark_closure_20260914_v3"
REPORTER = BASE / "analysis_tools/analyze_p3_benchmark.py"
BASE_SHA = "eeb5a2a9590b1b20cc0b26f6b9193a1f22b619abc1eb71c6f696c2dee67f4479"
REPORTER_SHA = "0f1f340023771fd20a7af9229fcf8a5e533fdda7eca2a4b943968e5978891111"
sys.path.insert(0, str(ROOT / "scripts"))
import run_p3_benchmark as runner
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json


def validate_v2(config):
    if config.get("runtime_snapshot_version") != 2:
        raise ValueError("This entrypoint requires a fresh v2 campaign")
    for name, sha in config["runtime_v2_files"].items():
        if digest(ROOT / name) != sha:
            raise ValueError("Frozen v2 source changed: " + name)
    runner.validate(config)
    if digest(REPORTER) != REPORTER_SHA:
        raise ValueError("Reporting copy changed")


def build_config(source, name, seed_offset, files):
    config = copy.deepcopy(source)
    config.update(name=name, runtime_snapshot_version=2, runtime_v2_files=files,
                  parent_config_sha256=BASE_SHA, seed_offset=seed_offset,
                  created_at="2026-09-15", hours=0,
                  deadline_policy="Explicit absolute deadline required at launch; no inherited budget",
                  scope="Fresh v2 integration-state and sensor-cache collection; do not pool with v1. "
                        "Same historical task/init support, not unseen-task holdout. "
                        "Across replicas, verify initial-state hashes; do not assume pure model-noise isolation.")
    for job in config["jobs"]:
        job["rollout_seed"] += seed_offset
    regression = copy.deepcopy(next(j for j in source["jobs"]
                                    if j["phase"] == "main" and j["id"] == "environment__t3_i2"))
    regression.update(id="parity_environment__t3_i2", phase="smoke", rollout_seed=52_320_000)
    config["jobs"].insert(0, regression)
    return config


def prepare():
    if ROOT != runner.REMOTE:
        raise ValueError("Prepare only in the canonical server project")
    if digest(BASE / "config.json") != BASE_SHA:
        raise ValueError("Original scientific config changed")
    source = json.loads((BASE / "config.json").read_text())
    runner.validate(source)
    files = {str(p.relative_to(ROOT)): digest(p) for p in sorted(HERE.glob("*.py"))}
    files[str(REPORTER.relative_to(ROOT))] = REPORTER_SHA
    stages = []
    for index in (0, 1, 2):
        directory = BASE.parent / f"p3_benchmark_runtime_v2_20260915_s{index}"
        config = build_config(source, directory.name, index * 10_000_000, files)
        validate_v2(config)
        path = directory / "config.json"
        if path.exists():
            if json.loads(path.read_text()) != config:
                raise ValueError("Refuse to replace existing v2 config")
        else:
            atomic_json(path, config)
        stages.append(str(directory))
    plan = dict(stages=stages, status="prepared_not_launched", required_deadline=None,
                old_results_immutable=True, no_v1_resume=True, main_per_stage=995,
                smoke_per_stage=18, promotion="Full strict audit; independent of success rate",
                runtime_v2_files=files)
    if not (HERE / "plan.json").exists():
        atomic_json(HERE / "plan.json", plan)
    return plan


def redirected(command):
    result = list(command)
    paths = {
        str(ROOT / "scripts/collect_p3_benchmark.py"): str(HERE / "collect_v2.py"),
        str(ROOT / "scripts/analyze_p3_benchmark.py"): str(REPORTER),
    }
    return [paths.get(word, word) if isinstance(word, str) else word for word in result]


class VersionedSubprocess:
    def run(self, command, *args, **kwargs):
        return subprocess.run(redirected(command), *args, **kwargs)

    def Popen(self, command, *args, **kwargs):
        return subprocess.Popen(redirected(command), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(subprocess, name)


def future_deadline(value):
    if value is None:
        raise ValueError("Specify --deadline with timezone; the previous deadline expired")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.timestamp() <= time.time():
        raise ValueError("Deadline must include timezone and be in the future")
    return parsed.timestamp()


def _execute_locked(deadline):
    if ROOT != runner.REMOTE:
        raise ValueError("Execute only on the canonical server")
    plan = json.loads((HERE / "plan.json").read_text())
    for name in plan["stages"]:
        directory = Path(name)
        validate_v2(json.loads((directory / "config.json").read_text()))
        status = directory / "sequence_status.json"
        if status.exists() and json.loads(status.read_text()).get("status") == "completed":
            continue
        if time.time() >= deadline:
            return
        # A new explicit launch may resume its own v2 results, never v1 artifacts.
        budget = directory / "budget.json"
        if budget.exists():
            previous = json.loads(budget.read_text())
            atomic_json(directory / f"budget_before_{time.time_ns()}.json", previous)
        atomic_json(budget, dict(start_epoch=time.time(), deadline_epoch=deadline))
        runner.subprocess = VersionedSubprocess()
        runner.execute(directory)
        if json.loads(status.read_text()).get("status") != "completed":
            return


def execute(deadline):
    with (HERE / "execution.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _execute_locked(deadline)


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--launch", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--deadline")
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare()))
        return
    deadline = future_deadline(args.deadline)
    if args.execute:
        execute(deadline)
    else:
        if ROOT != runner.REMOTE:
            raise ValueError("Launch only on the canonical server")
        with (HERE / "launcher.log").open("a") as log:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__)), "--execute", "--deadline", args.deadline],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
            )
        result = dict(pid=process.pid, launched_at=datetime.now(timezone.utc).isoformat(),
                      deadline_epoch=deadline)
        atomic_json(HERE / f"launch_{process.pid}.json", result)
        print(json.dumps(result))


if __name__ == "__main__":
    main()

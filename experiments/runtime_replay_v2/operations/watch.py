#!/usr/bin/env python3
"""Read-only CPU reporting for the frozen v2 queue; never launches GPU jobs."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
VERSION = HERE.parent
ROOT = VERSION.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from resume_recovery_confirmation import retry_atomic_json as atomic_json

AUDITOR = ROOT / "experiments/campaigns/p3_benchmark_closure_20260914_v3/operations/publication_audit.py"
AUDITOR_SHA = "515a7a440a8249d229f8209a22ca95e113dc0f7d4e14437a39833b047d43bb85"


def status():
    plan = json.loads((HERE / "plan.json").read_text())
    stages = []
    for name in plan["stages"]:
        directory = Path(name)
        path = directory / "sequence_status.json"
        stage = json.loads(path.read_text()) if path.exists() else {"status": "not_started"}
        stages.append(dict(campaign=directory.name, **stage))
    all_complete = all(s["status"] == "completed" for s in stages)
    failed = any(s["status"] in ("failed", "partial") for s in stages)
    deadline = plan["deadline_epoch"]
    try:
        command = Path(f'/proc/{plan["supervisor_pid"]}/cmdline').read_bytes().split(b"\0")
        alive = str(VERSION / "run_v2.py").encode() in command and b"--execute" in command
    except OSError:
        alive = False
    return dict(checked_at=datetime.now(timezone.utc).isoformat(), stages=stages,
                status="completed" if all_complete else "stopped" if failed or not alive else "running",
                supervisor_alive=alive,
                deadline_epoch=deadline, seconds_until_deadline=max(0, deadline - time.time()),
                matched_main_cases=sum(s.get("matched_cases", 0) for s in stages),
                expected_main_cases=plan.get("expected_main_cases", 199 * len(stages)))


def load_auditor():
    if hashlib.sha256(AUDITOR.read_bytes()).hexdigest() != AUDITOR_SHA:
        raise ValueError("Changed descriptive auditor source")
    spec = importlib.util.spec_from_file_location("v2_descriptive_auditor", AUDITOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OPS = HERE
    return module


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--watch", action="store_true")
    modes.add_argument("--status", action="store_true")
    modes.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(status(), indent=2))
        return
    auditor = load_auditor()
    while True:
        state = status()
        atomic_json(HERE / "run_status.json", state)
        try:
            auditor.audit()
        except Exception as error:
            atomic_json(HERE / "reporting_error.json", dict(error=repr(error), at=time.time()))
            if args.once:
                raise
        if args.once or state["status"] in ("completed", "stopped"):
            break
        if time.time() >= state["deadline_epoch"] + 120:
            break
        time.sleep(120)


if __name__ == "__main__":
    main()

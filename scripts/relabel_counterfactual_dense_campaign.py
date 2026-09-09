#!/usr/bin/env python3
"""Run dense endpoint relabeling for every job in a saved campaign manifest."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--output-campaign", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    source = args.source_campaign.expanduser().resolve()
    output = args.output_campaign.expanduser().resolve()
    run_output = output / "runs"
    log_dir = output / "logs"
    run_output.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))

    def execute(job: dict) -> dict:
        name = str(job["name"])
        run_name = str(job["environment"]["LIBERO_PRO_VOF_RUN_NAME"])
        command = [
            sys.executable,
            str(ROOT / "scripts/relabel_counterfactual_dense.py"),
            "--source-dir",
            str(source / "runs"),
            "--output-dir",
            str(run_output),
            "--run-name",
            run_name,
        ]
        environment = os.environ.copy()
        environment.update({str(key): str(value) for key, value in job["environment"].items()})
        local_python_paths = [str(ROOT / "LIBERO-PRO"), str(ROOT / "cosmos-policy")]
        if environment.get("PYTHONPATH"):
            local_python_paths.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(local_python_paths)
        log_path = log_dir / f"{name}.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        return {"name": name, "run_name": run_name, "returncode": result.returncode}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(execute, manifest["jobs"]))
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_campaign": str(source),
        "status": "completed" if all(row["returncode"] == 0 for row in results) else "failed",
        "jobs": results,
    }
    (output / "manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))
    if payload["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

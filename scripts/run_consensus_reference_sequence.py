#!/usr/bin/env python3
"""Frozen matched reference methods, queued after compact600 without retuning it."""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

try:
    from scripts.run_trajectory_consensus_sequence import atomic_json, utc
except ModuleNotFoundError:
    from run_trajectory_consensus_sequence import atomic_json, utc

ROOT = Path(__file__).resolve().parents[1]
RUN = "consensus_references_20260908"
PARENT = "trajectory_consensus_20260908"
DEPENDENCY = PARENT + "_compact"
METHODS = [
    dict(label="raw_medoid", strategy="trajectory_raw_medoid", candidates=4),
    dict(label="keystone", strategy="keystone_cluster_medoid", candidates=4),
    dict(label="kdpe_endpoint", strategy="trajectory_kdpe_endpoint", candidates=4),
]
GEOMETRY = "cosmos_policy/experiments/robot/libero/trajectory_consensus.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_config(compact):
    jobs = []
    sources = [j for j in compact["profiles"]["compact"]["jobs"] if j["name"].endswith("_max_value")]
    if len(sources) != 120:
        raise ValueError("Expected the compact120-cell max-value reference grid")
    for source in sources:
        for method in METHODS:
            job = copy.deepcopy(source)
            job["name"] = source["name"].removesuffix("_max_value") + "_" + method["label"]
            job["strategy_lambdas"] = method["strategy"] + ":0.0"
            job["uncertainty_seeds"] = "0,1,2,3"
            job["experiment_split"] = "holdout"
            job.pop("source_job_name", None)
            jobs.append(job)
    smoke = []
    for job in jobs:
        if job["name"].startswith("object_t0_"):
            job = copy.deepcopy(job)
            job["init_state_ids"] = "0"
            job["base_seed"] = 71000000
            job["experiment_split"] = "screen"
            smoke.append(job)
    return dict(schema_version=1, defaults=copy.deepcopy(compact["defaults"]), profiles=dict(
        references=dict(description="600 additional matched H16/K4 reference rollouts; no outcome-based shortlist", jobs=jobs),
        smoke=dict(description="Three integration-only reference rollouts", jobs=smoke)))


def prepare(directory):
    parent = directory.parent / PARENT
    dependency = directory.parent / DEPENDENCY
    compact = json.loads((dependency / "config.json").read_text())
    config = build_config(compact)
    path = directory / "config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise ValueError("Refusing to alter an existing reference grid")
    geometry_source = ROOT / "cosmos-policy" / GEOMETRY
    source_hashes = json.loads((parent / "source_sha256.json").read_text())
    frozen = directory / "freeze.json"
    evidence = dict(dependency=DEPENDENCY, compact_config_sha256=sha(dependency / "config.json"),
        original_source_manifest_sha256=sha(parent / "source_sha256.json"),
        geometry_sha256=sha(geometry_source), methods=METHODS, extra_rollouts=600, smoke_rollouts=3,
        selection_uses_terminal_outcomes=False,
        script_sha256={name: sha(ROOT / "scripts" / name) for name in (
            "run_consensus_reference_sequence.py", "analyze_consensus_reference_campaign.py",
            "run_libero_experiment_campaign.py", "analyze_trajectory_consensus_campaign.py")})
    if frozen.exists() and json.loads(frozen.read_text()) != evidence:
        raise ValueError("Reference freeze mismatch")
    source = directory / "source/cosmos-policy/cosmos_policy"
    if not frozen.exists():
        shutil.copytree(parent / "source/cosmos-policy/cosmos_policy", source,
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(geometry_source, directory / "source/cosmos-policy" / GEOMETRY)
    for name, digest in source_hashes.items():
        expected = evidence["geometry_sha256"] if name == GEOMETRY.removeprefix("cosmos_policy/") else digest
        if sha(source / name) != expected:
            raise ValueError(f"Runtime snapshot mismatch: {name}")
    atomic_json(path, config)
    atomic_json(path.with_suffix(".methods.json"), METHODS)
    atomic_json(frozen, evidence)
    return path


def dependency_state(path):
    if not path.exists():
        return "waiting"
    state = json.loads(path.read_text()).get("status")
    if state in {"failed", "superseded", "superseded_draining"}:
        raise RuntimeError(f"Dependency {path.parent.name} is {state}; manual inspection required")
    return "ready" if state == "completed" else "waiting"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--gpus", default="3,4,5,6,7")
    args = parser.parse_args()
    gpus = args.gpus.split(",")
    if len(set(gpus)) != len(gpus) or any(g not in ("3", "4", "5", "6", "7") for g in gpus):
        parser.error("Only unique physical GPUs 3-7 are allowed")
    directory = ROOT / "experiments/campaigns" / RUN
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory / "sequence.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = prepare(directory)
    print(f"Prepared {RUN}: 3 smoke + 600 matched reference rollout", flush=True)
    if not args.execute:
        return
    status_path = directory / "sequence_status.json"
    started = utc()
    if status_path.exists():
        prior = json.loads(status_path.read_text())
        if prior.get("status") == "completed":
            print("Already completed; no new work")
            return
        started = prior.get("started_at", started)
    env = dict(os.environ, COSMOS_REPO=str(directory / "source/cosmos-policy"),
               HF_HUB_OFFLINE="1", WANDB_MODE="offline", PYTHONUNBUFFERED="1")
    stage = "waiting_for_compact"

    def status(state, **extra):
        atomic_json(status_path, dict(run_base=RUN, status=state, stage=stage,
            started_at=started, updated_at=utc(), pid=os.getpid(), gpus=gpus,
            expected_rollouts=600, dependency=DEPENDENCY, **extra))
        (directory / "heartbeat.txt").write_text(f"{utc()} pid={os.getpid()} stage={stage}\n")

    def command(cmd):
        child = subprocess.Popen(list(map(str, cmd)), cwd=ROOT, env=env)
        try:
            while child.poll() is None:
                status("running", child_pid=child.pid)
                time.sleep(15)
        except BaseException:
            child.terminate()
            child.wait()
            raise
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, cmd)

    try:
        while dependency_state(directory.parent / DEPENDENCY / "sequence_status.json") != "ready":
            status("waiting")
            time.sleep(30)
        for phase, name in (("smoke", RUN + "_smoke"), ("references", RUN)):
            stage = phase
            campaign = directory.parent / name
            manifest = campaign / "manifest.json"
            if not manifest.exists() or json.loads(manifest.read_text()).get("status") != "completed":
                command([sys.executable, ROOT / "scripts/run_libero_experiment_campaign.py",
                    "--config", config, "--profile", phase, "--run-prefix", name,
                    "--gpus", args.gpus, "--execute"])
            stage = "validate_" + phase
            command([sys.executable, ROOT / "scripts/analyze_trajectory_consensus_campaign.py", "--campaign", campaign])
        stage = "combined_analysis"
        command([sys.executable, ROOT / "scripts/analyze_consensus_reference_campaign.py",
                 "--compact", directory.parent / DEPENDENCY, "--references", directory])
        status("completed")
    except BaseException as error:
        status("failed", error=repr(error))
        raise


if __name__ == "__main__":
    main()

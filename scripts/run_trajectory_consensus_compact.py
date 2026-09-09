#!/usr/bin/env python3
"""Resource-amended 600-rollout evaluation, reusing outcome-blind full-test subsets."""
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

import numpy as np
import pandas as pd

try:
    from scripts.run_libero_experiment_campaign import _safe_name, build_job, expand_jobs
    from scripts.run_trajectory_consensus_sequence import atomic_json, utc
except ModuleNotFoundError:
    from run_libero_experiment_campaign import _safe_name, build_job, expand_jobs
    from run_trajectory_consensus_sequence import atomic_json, utc

ROOT = Path(__file__).resolve().parents[1]
BASE = "trajectory_consensus_20260908"
RUN = BASE + "_compact"


def compact_config(original):
    jobs = []
    for source in original["profiles"]["full"]["jobs"]:
        job = copy.deepcopy(source)
        is_position = job["kind"] == "pro_position_planning_grid"
        first_init = 1 if is_position else 2
        job["source_job_name"] = job["name"]
        job["name"] = _safe_name(job["name"])
        job["init_state_ids"] = "1" if is_position else "2-6"
        # Collector pair ids restart at zero for a reduced init list.
        job["base_seed"] += first_init * 10000
        job.pop("gpu_slot", None)
        jobs.append(job)
    jobs.sort(key=lambda j: (j["case_id"], int(j["task_ids"]), j["name"]))
    defaults = copy.deepcopy(original["defaults"])
    defaults["dynamic_gpu_queue"] = True
    return dict(schema_version=1, defaults=defaults, profiles=dict(compact=dict(
        description="600 rollouts: three frozen methods, 10 tasks, Object/Environment init2-6 and all Position levels init1",
        jobs=jobs,
    )))


def select_reusable(trace, job):
    parts = list(map(int, job["init_state_ids"].split("-")))
    start, end = parts[0], parts[-1]
    selected = trace[trace.init_state_id.between(start, end)].copy()
    if set(selected.init_state_id) != set(range(start, end + 1)):
        raise ValueError("Reusable source does not contain every requested init")
    if not selected.task_id.eq(int(job["task_ids"])).all() or not selected.suite.eq(job["suites"]).all():
        raise ValueError("Reusable source task/suite mismatch")
    if not selected.case_id.eq(job["case_id"]).all():
        raise ValueError("Reusable case mismatch")
    strategy, weight = job["strategy_lambdas"].split(":")
    if not selected.planning_strategy.eq(strategy).all() or not np.allclose(selected.planning_risk_lambda, float(weight)):
        raise ValueError("Reusable selector mismatch")
    if not selected.num_open_loop_steps.eq(16).all() or not selected.prediction_mode.eq("parallel").all():
        raise ValueError("Reusable execution protocol mismatch")
    if not selected.num_denoising_steps_action.eq(job.get("num_denoising_steps_action", 5)).all():
        raise ValueError("Reusable denoising budget mismatch")
    if not selected.num_samples.eq(len(job["uncertainty_seeds"].split(","))).all():
        raise ValueError("Reusable candidate budget mismatch")
    for init, group in selected.groupby("init_state_id"):
        group = group.sort_values("query_idx")
        seed = job["base_seed"] + (int(init) - start) * 10000
        if not group.rollout_seed.eq(seed).all() or not group.rollout_id.eq(0).all():
            raise ValueError("Reusable rollout seed mismatch")
        if not np.array_equal(group.query_idx, np.arange(len(group))) or not group.num_queries.eq(len(group)).all():
            raise ValueError("Reusable episode incomplete")
        if group.success.nunique() != 1 or group.final_t.nunique() != 1:
            raise ValueError("Conflicting reusable outcomes")
        if group.t.iloc[0] != 0 or group.t_after.iloc[-1] != group.final_t.iloc[0]:
            raise ValueError("Truncated reusable timeline")
        if not np.array_equal(group.t_after.iloc[:-1], group.t.iloc[1:]):
            raise ValueError("Discontinuous reusable timeline")
        if not np.array_equal(group.t_after - group.t, group.executed_steps):
            raise ValueError("Reusable execution length mismatch")
    selected["source_pair_id"] = selected.pair_id
    selected["pair_id"] = selected.init_state_id - start
    return selected


def reuse_completed(config, source_campaign, destination):
    prior = destination / "reuse_manifest.json"
    previous = json.loads(prior.read_text()) if prior.exists() else []
    # Once collection starts, never replace a partially collected job on resume.
    if (destination / "manifest.json").exists():
        return sum(item["episodes"] for item in previous)
    manifest = json.loads((source_campaign / "manifest.json").read_text())
    source_jobs = {j["name"]: j for j in manifest["jobs"]}
    reused = []
    for job in expand_jobs(config["profiles"]["compact"], config["defaults"]):
        _, env, marker = build_job(job, RUN, destination)
        if marker.exists():
            continue
        source = source_jobs[job["source_job_name"]]
        prefix = source["environment"]["LIBERO_PRO_PLANNING_GRID_PREFIX"]
        traces = list((source_campaign / "runs").glob(prefix + "__*__query_traces.parquet"))
        if not traces:
            continue
        if len(traces) != 1:
            raise ValueError("Ambiguous source trace")
        path = traces[0]
        old_run = path.name.removesuffix("__query_traces.parquet")
        if not (path.parent / (old_run + "__completed.json")).exists():
            continue
        selected = select_reusable(pd.read_parquet(path), job)
        token = lambda s: str(s).translate(str.maketrans({",": "_", ":": "_", "/": "_", ".": "p"}))
        strategy, weight = job["strategy_lambdas"].split(":")
        run_name = (f"{env['LIBERO_PRO_PLANNING_GRID_PREFIX']}__{token(job['suites'])}"
                    f"__task{token(job['task_ids'])}__init{token(job['init_state_ids'])}"
                    f"__{strategy}__l{token(weight)}")
        videos = destination / "videos" / env["LIBERO_PRO_PLANNING_GRID_PREFIX"] / run_name
        videos.mkdir(parents=True, exist_ok=True)
        mapping = {}
        for original in selected.video_path.unique():
            original = Path(original)
            if not original.is_file() or original.stat().st_size < 1024:
                raise ValueError(f"Missing source video: {original}")
            target = videos / original.name
            shutil.copy2(original, target)
            mapping[str(original)] = str(target)
        selected["source_video_path"] = selected.video_path
        selected["video_path"] = selected.video_path.map(mapping)
        selected["reused_from_trace"] = str(path)
        output = destination / "runs"
        output.mkdir(exist_ok=True)
        selected.to_parquet(output / (run_name + "__query_traces.parquet"), index=False)
        selected.to_csv(output / (run_name + "__query_traces.csv"), index=False)
        evidence = dict(source=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        init_state_ids=job["init_state_ids"], episodes=int(selected.init_state_id.nunique()))
        atomic_json(output / (run_name + "__reuse.json"), evidence)
        atomic_json(output / (run_name + "__completed.json"), dict(
            run_name=run_name, completed=True, num_query_rows=len(selected),
            num_rollouts=evidence["episodes"], reused=True,
        ))
        marker.parent.mkdir(exist_ok=True)
        now = utc()
        atomic_json(marker, dict(job=job["name"], status="completed", gpu="reused",
                                 started_at=now, finished_at=now, reused=True, evidence=evidence))
        reused.append(dict(job=job["name"], **evidence))
    atomic_json(prior, previous + reused)
    return sum(item["episodes"] for item in previous + reused)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--gpus", default="3,4,5,6,7")
    args = parser.parse_args()
    gpus = args.gpus.split(",")
    if len(set(gpus)) != len(gpus) or any(g not in ("3", "4", "5", "6", "7") for g in gpus):
        parser.error("Choose unique physical GPUs 3-7")
    root = ROOT / "experiments/campaigns"
    source, destination = root / BASE, root / RUN
    destination.mkdir(exist_ok=True)
    lock = (destination / "sequence.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    frozen = json.loads((source / "full_sha256.json").read_text())
    for name, digest in frozen.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Original freeze changed: {name}")
    config = compact_config(json.loads((source / "full_config.json").read_text()))
    config_path = destination / "config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Refusing to change compact settings after creation")
    atomic_json(config_path, config)
    from_method = json.loads((source / "winner.json").read_text())["method"]
    methods = json.loads((source / "full_config.methods.json").read_text())
    atomic_json(config_path.with_suffix(".methods.json"),
                [m for m in methods if m["label"] in ("first", "max_value")] + [from_method])
    reused = reuse_completed(config, root / (BASE + "_full"), destination)
    amendment_path = destination / "amendment.json"
    amendment = dict(
        created_at=utc(), reason="User requested usual-size evaluation and GPUs 3-7",
        original_freeze=frozen, config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        winner=from_method, target_rollouts=600, reused_rollouts=reused,
        subset_rule="Object/Environment init2-6; Position all ten levels init1; all ten tasks",
        selection_uses_outcomes=False,
    )
    if not amendment_path.exists():
        atomic_json(amendment_path, amendment)
    print(f"Prepared 600 rollouts; reused {reused}; new work {600-reused}", flush=True)
    if not args.execute:
        return
    env = dict(os.environ, COSMOS_REPO=str(source / "source/cosmos-policy"),
               HF_HUB_OFFLINE="1", WANDB_MODE="offline", PYTHONUNBUFFERED="1")
    started = utc()
    status_path = destination / "sequence_status.json"
    stage = "compact"

    def status(state, **extra):
        atomic_json(status_path, dict(run_base=RUN, status=state, stage=stage, pid=os.getpid(),
                                     started_at=started, updated_at=utc(), gpus=gpus,
                                     expected_rollouts=600, reused_rollouts=reused, **extra))
        (destination / "heartbeat.txt").write_text(f"{utc()} pid={os.getpid()} stage={stage}\n")

    commands = [
        [sys.executable, ROOT / "scripts/run_libero_experiment_campaign.py", "--config", config_path,
         "--profile", "compact", "--run-prefix", RUN, "--gpus", args.gpus, "--execute"],
        [sys.executable, ROOT / "scripts/analyze_trajectory_consensus_campaign.py", "--campaign", destination],
    ]
    try:
        for stage, command in zip(("compact", "analysis"), commands):
            child = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=env)
            try:
                while child.poll() is None:
                    status("running", child_pid=child.pid)
                    time.sleep(15)
            except BaseException:
                child.terminate()
                child.wait()
                raise
            if child.returncode:
                raise subprocess.CalledProcessError(child.returncode, command)
        status("completed")
    except BaseException as error:
        status("failed", error=repr(error))
        raise


if __name__ == "__main__":
    main()

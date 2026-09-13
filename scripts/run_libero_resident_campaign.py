#!/usr/bin/env python3
"""Idle-admitted, bounded resident batches for existing paired campaign manifests."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

try:
    from scripts import run_libero_experiment_campaign as legacy
    from scripts.libero_resident import CompatibleQueue, atomic_json, compatibility_key, requests_for_job
except ModuleNotFoundError:
    import run_libero_experiment_campaign as legacy
    from libero_resident import CompatibleQueue, atomic_json, compatibility_key, requests_for_job

ROOT = Path(__file__).resolve().parents[1]


def utc():
    return datetime.now(timezone.utc).isoformat()


def batch_payload(jobs, prefix, directory, gpu):
    items, keys = [], set()
    for job in jobs:
        commands, env, marker = legacy.build_job(job, prefix, directory)
        keys.add(compatibility_key(job, env))
        requests = requests_for_job(job, env)
        run_names = [r["run_name"] for r in requests]
        items.append(dict(name=job["name"], requests=requests, marker=str(marker),
            log=str(directory / "logs" / (job["name"] + ".log")),
            analysis_command=[sys.executable, str(ROOT / "scripts/compare_real_planning_strategy_runs.py"),
                "--base-dir", str(directory / "runs"), "--run-names", ",".join(run_names),
                "--output-dir", env["LIBERO_PRO_PLANNING_GRID_ANALYSIS_DIR"]]))
    if len(keys) != 1:
        raise ValueError("A resident batch must have exactly one runtime identity")
    commands, env, _ = legacy.build_job(jobs[0], prefix, directory)
    return dict(schema_version=1, gpu=gpu, compatibility_key=keys.pop(), items=items), commands[:-1], env


def launch_batch(jobs, prefix, directory, gpu, *, cold=False, on_dispatch=None, audit=False):
    payload, preparation, extra_env = batch_payload(jobs, prefix, directory, gpu)
    payload["audit"] = audit
    identifier = f"{time.time_ns()}_gpu{gpu}"
    path = directory / "resident" / (identifier + ".json")
    atomic_json(path, payload)
    env = dict(os.environ, **extra_env, CUDA_VISIBLE_DEVICES=gpu, HF_HUB_OFFLINE="1", WANDB_MODE="offline",
               PYTHONUNBUFFERED="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
    if gpu == "0":
        env["MLSPACE_ALLOW_GPU0"] = "1"
    log_path = path.with_suffix(".log")
    with log_path.open("a", buffering=1) as log:
        for command in preparation:
            subprocess.run(command, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        command = ["bash", "-ec", 'source "$1"; cd "$COSMOS_REPO"; exec "$COSMOS_VENV/bin/python" "$2" --batch "$3" "${@:4}"',
            "resident", str(ROOT / "scripts/cosmos_env_libero_pro.sh"),
            str(ROOT / "scripts/libero_resident_worker.py"), str(path)]
        if cold:
            command.append("--cold")
        child = subprocess.Popen(command, env=env, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        if on_dispatch:
            on_dispatch(jobs, gpu, path, child.pid)
        code = child.wait()
    if code:
        raise RuntimeError(f"Resident worker failed ({code}): {log_path}")
    missing = [i["name"] for i in payload["items"] if not Path(i["marker"]).is_file()]
    if missing:
        raise RuntimeError(f"Resident batch did not finish {missing}: {log_path}")
    return path


def executor_hashes():
    names = ("libero_resident.py", "libero_resident_worker.py", "run_libero_resident_campaign.py")
    return {name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest() for name in names}


def validate_parity(path, config):
    report = json.loads(Path(path).read_text())
    if (report.get("passed") is not True or report.get("executor_sha256") != executor_hashes()
            or report.get("source_config_sha256") != hashlib.sha256(Path(config).read_bytes()).hexdigest()
            or report.get("gate_scope") != "references_action_value_only"
            or report.get("resident_repeat", {}).get("all_metrics_exact") is not True
            or report.get("model_loads") != 1 or report.get("model_hits") != 2):
        raise ValueError("Missing, incompatible or stale resident parity validation")
    runtime = Path(os.environ["COSMOS_REPO"])
    for relative, digest in report["runtime_sha256"].items():
        if hashlib.sha256((runtime / relative).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen runtime differs from parity control")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--gpus", default="2")
    parser.add_argument("--allow-gpu-zero", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--only", default="")
    parser.add_argument("--cold", action="store_true")
    parser.add_argument("--parity-report", type=Path)
    args = parser.parse_args()
    gpus = args.gpus.split(",")
    if len(gpus) != len(set(gpus)) or any(g not in tuple("01234567") for g in gpus):
        raise ValueError("Only unique physical GPUs 0-7 are allowed")
    if "0" in gpus and not args.allow_gpu_zero:
        raise ValueError("GPU0 needs --allow-gpu-zero")
    if not 1 <= args.batch_size <= 32:
        raise ValueError("batch-size must be between 1 and 32")
    cfg = legacy.load_campaign(args.config)
    jobs = legacy.expand_jobs(cfg["profiles"][args.profile], cfg.get("defaults", {}))
    only = set(args.only.split(",")) if args.only else None
    if only:
        jobs = [j for j in jobs if j["name"] in only]
        if {j["name"] for j in jobs} != only:
            raise ValueError("Unknown --only job")
    directory = ROOT / "experiments/campaigns" / legacy._safe_name(args.run_prefix)
    prepared = {}
    for job in jobs:
        legacy.validate_job_inputs(job)
        commands, env, marker = legacy.build_job(job, args.run_prefix, directory)
        prepared[job["name"]] = (commands, env, marker)
        compatibility_key(job, env)
    pending = [j for j in jobs if not prepared[j["name"]][2].is_file()]
    print(f"[resident] pending={len(pending)} completed={len(jobs)-len(pending)} gpus={gpus} batch_size={args.batch_size}", flush=True)
    if not args.execute:
        return
    if args.parity_report is None or args.cold:
        raise ValueError("Production execution requires --parity-report and resident mode")
    validate_parity(args.parity_report, args.config)
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory / "resident.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Refuse simultaneous legacy ownership of this same campaign.
    processes = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    for line in processes.splitlines():
        if "run_libero_experiment_campaign.py" in line and f"--run-prefix {args.run_prefix}" in line:
            raise RuntimeError("Legacy campaign still owns these jobs; drain it before switching")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else dict(
        schema_version=1, profile=args.profile, run_prefix=args.run_prefix, config=str(args.config.resolve()),
        created_at=utc(), jobs=[dict(name=j["name"], kind=j["kind"], gpu=gpus[i % len(gpus)],
            commands=prepared[j["name"]][0], environment=prepared[j["name"]][1],
            completion_marker=str(prepared[j["name"]][2])) for i, j in enumerate(jobs)])
    manifest.update(status="running", executor="resident", resident_started_at=utc(), resident_pid=os.getpid())
    atomic_json(manifest_path, manifest)
    mutex, stop = threading.Lock(), threading.Event()
    queue = CompatibleQueue(pending, lambda j: compatibility_key(j, prepared[j["name"]][1]), args.batch_size)
    state_path = directory / "resident_status.json"
    state = dict(pid=os.getpid(), gpus=gpus, started_at=utc(), active={}, waiting=[], status="running")
    def publish():
        with mutex:
            state["updated_at"] = utc()
            atomic_json(state_path, state)
    def heartbeat():
        while not stop.wait(5):
            publish()
    heart = threading.Thread(target=heartbeat, daemon=True)
    heart.start()
    def dispatch(batch, gpu, path, pid):
        with mutex:
            names = {j["name"] for j in batch}
            state["active"][gpu] = dict(pid=pid, batch=str(path), jobs=list(names))
            state["waiting"] = [g for g in state["waiting"] if g != gpu]
            for entry in manifest["jobs"]:
                if entry["name"] in names:
                    entry.update(gpu=gpu, dispatched_at=utc(), resident_batch=str(path), worker_pid=pid)
            atomic_json(manifest_path, manifest)
        publish()
    def worker(gpu):
        while not stop.is_set() and not queue.empty():
            if not legacy.gpu_is_free(gpu):
                with mutex:
                    if gpu not in state["waiting"]:
                        state["waiting"].append(gpu)
                        print(f"[resident] waiting for free GPU={gpu}", flush=True)
                stop.wait(3)
                continue
            batch = queue.take()
            if not batch:
                return
            try:
                launch_batch(batch, args.run_prefix, directory, gpu, cold=args.cold, on_dispatch=dispatch)
            except BaseException:
                stop.set()
                raise
            finally:
                with mutex:
                    state["active"].pop(gpu, None)
                publish()
    try:
        with ThreadPoolExecutor(max_workers=len(gpus)) as executor:
            futures = [executor.submit(worker, gpu) for gpu in gpus]
            for future in as_completed(futures):
                future.result()
        if any(not prepared[j["name"]][2].is_file() for j in jobs):
            raise RuntimeError("Campaign has unfinished jobs")
        manifest.update(status="completed", finished_at=utc())
        manifest["results"] = [json.loads(prepared[j["name"]][2].read_text()) for j in jobs]
        state["status"] = "completed"
    except BaseException as error:
        manifest.update(status="failed", resident_error=repr(error))
        state.update(status="failed", error=repr(error))
        raise
    finally:
        stop.set()
        heart.join()
        atomic_json(manifest_path, manifest)
        publish()


if __name__ == "__main__":
    main()

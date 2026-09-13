#!/usr/bin/env python3
"""Run a compatible batch through the unmodified frozen collector."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

from libero_resident import AsyncImageIO, CPUQueue, ResidentModel, atomic_json


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--cold", action="store_true", help="Parity control: no model cache or deferred artifacts")
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    from cosmos_policy.experiments.robot.libero import uncertainty_comparison as collector
    cpu = CPUQueue(capacity=2)
    output = sys.stdout
    cache = ResidentModel(collector.get_model)
    audit = []
    original_sample = collector.sample_action_ensemble
    if batch.get("audit"):
        def sampled(*values, **kwargs):
            samples, metrics = original_sample(*values, **kwargs)
            hashes = []
            for sample in samples:
                entry = {}
                for name in ("actions", "value_prediction", "generated_latent"):
                    array = collector._to_numpy_array(sample[name])
                    entry[name] = dict(shape=list(array.shape), dtype=str(array.dtype),
                        sha256=hashlib.sha256(array.tobytes()).hexdigest())
                hashes.append(entry)
            audit.append(hashes)
            return samples, metrics
        collector.sample_action_ensemble = sampled
    if not args.cold:
        collector.get_model = cache
        collector.imageio = AsyncImageIO(collector.imageio, cpu)
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    state_path = args.batch.with_suffix(".status.json")
    state = dict(pid=os.getpid(), status="running", started_at=utc(), collected=[], cold=args.cold)
    cpu_env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MPLBACKEND="Agg")

    def finish(item, pending, started):
        for future in pending:
            future.result()
        with Path(item["log"]).open("a") as log:
            subprocess.run(item["analysis_command"], env=cpu_env, stdout=log, stderr=subprocess.STDOUT, check=True)
        result = dict(job=item["name"], gpu=batch["gpu"], status="completed", started_at=started,
                      finished_at=utc(), log=item["log"], executor="resident", worker_pid=os.getpid())
        atomic_json(item["marker"], result)
        print(f"[resident] completed job={item['name']} gpu={batch['gpu']}", file=output, flush=True)

    try:
        for item in batch["items"]:
            if stopped:
                break
            if Path(item["marker"]).exists():
                continue
            state.update(active_job=item["name"], updated_at=utc(), model_loads=cache.loads, model_hits=cache.hits)
            atomic_json(state_path, state)
            started = utc()
            print(f"[resident] gpu={batch['gpu']} job={item['name']}", flush=True)
            log_path = Path(item["log"])
            log_path.parent.mkdir(parents=True, exist_ok=True)
            pending_start = len(cpu.futures)
            with log_path.open("a", buffering=1) as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                print(f"\n[{started}] GPU={batch['gpu']} resident job={item['name']}", flush=True)
                for request in item["requests"]:
                    audit.clear()
                    kwargs = dict(request)
                    kwargs["suites"] = [v.strip() for v in kwargs["suites"].split(",") if v.strip()]
                    for key in ("task_ids", "init_state_ids"):
                        kwargs[key] = collector.parse_int_list(kwargs[key])
                    kwargs["uncertainty_seeds"] = collector.parse_seed_list(kwargs["uncertainty_seeds"])
                    for key in ("output_dir", "video_dir"):
                        kwargs[key] = Path(kwargs[key])
                    completed = kwargs["output_dir"] / (kwargs["run_name"] + "__completed.json")
                    trace_path = kwargs["output_dir"] / (kwargs["run_name"] + "__query_traces.parquet")
                    # Resume only a fully materialized collector result, including videos.
                    reusable = completed.is_file() and trace_path.is_file()
                    if reusable:
                        trace = collector.pd.read_parquet(trace_path)
                        if kwargs["save_videos"]:
                            if "video_path" not in trace:
                                raise RuntimeError(f"Missing video paths in {trace_path}")
                            for path in trace.video_path.unique():
                                if not Path(str(path)).is_file():
                                    if args.cold:
                                        raise RuntimeError(f"Missing video in cold control: {path}")
                                    collector.imageio.recover(path, fps=kwargs["video_fps"], macro_block_size=1)
                    if not reusable:
                        if trace_path.is_file() and kwargs["save_videos"]:
                            old = collector.pd.read_parquet(trace_path)
                            if "video_path" not in old:
                                raise RuntimeError(f"Missing video paths in {trace_path}")
                            for path in old.video_path.unique():
                                if not Path(str(path)).is_file():
                                    collector.imageio.recover(path, fps=kwargs["video_fps"], macro_block_size=1)
                        trace, trace_path = collector.collect_paired_uncertainty_traces(**kwargs)
                    if batch.get("audit"):
                        atomic_json(kwargs["output_dir"] / (kwargs["run_name"] + "__resident_audit.json"), audit)
                    if "success" in trace and trace.success.nunique() >= 2:
                        command = [sys.executable, "-m", "cosmos_policy.experiments.robot.libero.uncertainty_comparison",
                            "analyze", "--trace-file", str(trace_path), "--output-dir",
                            str(kwargs["output_dir"] / (kwargs["run_name"] + "__analysis"))]
                        cpu.submit(subprocess.run, command, env=cpu_env, check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            pending = cpu.futures[pending_start:]
            cpu.submit(finish, item, pending, started)
            state["collected"].append(item["name"])
            state.update(model_loads=cache.loads, model_hits=cache.hits)
        cpu.close()
        state.update(status="drained" if stopped else "completed", active_job=None, updated_at=utc())
        atomic_json(state_path, state)
    except BaseException as error:
        state.update(status="failed", error=repr(error), updated_at=utc())
        atomic_json(state_path, state)
        cpu.executor.shutdown(wait=True)
        raise


if __name__ == "__main__":
    main()

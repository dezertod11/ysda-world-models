"""Resource-only adapters for the frozen paired LIBERO collector."""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import threading
from concurrent.futures import ThreadPoolExecutor


SUPPORTED_KINDS = {"pro_planning_grid", "pro_position_planning_grid", "pro_environment_planning_grid"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def safe_token(value):
    return str(value).translate(str.maketrans({",": "_", ":": "_", "/": "_", ".": "p"}))


def requests_for_job(job, env):
    """Translate the existing grid environment, retaining its defaults and names."""
    if job["kind"] not in SUPPORTED_KINDS or job.get("record_temporal_overlap", False):
        raise ValueError("Resident mode supports paired planning grids without temporal-overlap hooks")
    prefix = "LIBERO_PRO_PLANNING_GRID_"
    def get(name, default=None):
        return env.get(prefix + name, default)

    result = []
    for item in get("STRATEGY_LAMBDAS").split():
        strategy, coefficient = item.split(":")
        name = (f"{get('PREFIX')}__{safe_token(get('SUITES'))}"
                f"__task{safe_token(get('TASK_IDS'))}__init{safe_token(get('INIT_STATE_IDS'))}"
                f"__{strategy}__l{safe_token(coefficient)}")
        kwargs = dict(suites=get("SUITES"), task_ids=get("TASK_IDS"), init_state_ids=get("INIT_STATE_IDS"),
            max_rollouts_per_init=int(get("MAX_ROLLOUTS_PER_INIT")), min_success=999, min_failed=999,
            base_seed=int(get("BASE_SEED")), uncertainty_seeds=get("UNCERTAINTY_SEEDS"),
            max_timesteps=int(get("MAX_TIMESTEPS")) or None, output_dir=get("OUTPUT_DIR"), run_name=name,
            planning_strategy=strategy, planning_risk_lambda=float(coefficient), resume=True,
            save_videos=env.get("LIBERO_PRO_PAIRED_SAVE_VIDEOS", "0") == "1",
            video_dir=str(Path(env["LIBERO_PRO_PAIRED_VIDEO_DIR"]) / name),
            video_fps=int(env.get("LIBERO_PRO_PAIRED_VIDEO_FPS", "30")),
            collect_safety_signals=env.get("LIBERO_PRO_PAIRED_COLLECT_SAFETY_SIGNALS", "0") == "1",
            record_denoising_trace=env.get("LIBERO_PRO_PAIRED_RECORD_DENOISING_TRACE", "0") == "1",
            collect_prediction_errors=env.get("LIBERO_PRO_PAIRED_NO_PREDICTION_ERRORS", "0") != "1")
        for suffix, name_, convert in [
            ("ROLLOUT_SEED_STEP", "rollout_seed_step", int),
            ("NUM_OPEN_LOOP_STEPS", "num_open_loop_steps", int),
            ("NUM_DENOISING_STEPS_ACTION", "num_denoising_steps_action", int),
            ("PREDICTION_MODE", "prediction_mode", str),
            ("NUM_DENOISING_STEPS_FUTURE_STATE", "num_denoising_steps_future_state", int),
            ("NUM_DENOISING_STEPS_VALUE", "num_denoising_steps_value", int),
            ("NUM_FUTURE_STATE_SAMPLES", "num_future_state_samples", int),
            ("NUM_VALUE_SAMPLES", "num_value_samples", int),
            ("VALUE_ENSEMBLE_AGGREGATION", "value_ensemble_aggregation_scheme", str),
            ("EXPERIMENT_SPLIT", "experiment_split", str), ("CASE_ID", "case_id", str),
            ("ACTION_WEIGHT", "planning_action_weight", float),
            ("DIFFICULTY_THRESHOLD", "planning_difficulty_threshold", float),
            ("VALUE_MARGIN", "planning_value_margin", float),
            ("UNCERTAINTY_MARGIN", "planning_uncertainty_margin", float),
            ("PHASE_FRACTION", "planning_phase_fraction", float),
            ("SHORT_OPEN_LOOP_STEPS", "planning_short_open_loop_steps", int),
            ("SCHEDULED_REQUERY_QUERY_IDX", "planning_scheduled_requery_query_idx", int),
            ("SURROGATE_ERROR_THRESHOLD", "planning_surrogate_error_threshold", float),
            ("FROZEN_RANKER_MODEL", "planning_frozen_ranker_model_path", str),
            ("FROZEN_RANKER_FACTOR", "planning_frozen_ranker_factor", str),
            ("TERMINAL_CRITIC_MODEL", "planning_terminal_critic_model_path", str),
            ("TERMINAL_CRITIC_FACTOR", "planning_terminal_critic_factor", str),
        ]:
            if get(suffix) is not None:
                kwargs[name_] = convert(get(suffix))
        result.append(kwargs)
    if not result:
        raise ValueError("Empty strategy list")
    return result


def compatibility_key(job, env):
    requests = requests_for_job(job, env)
    variable = {"task_ids", "init_state_ids", "max_rollouts_per_init", "base_seed", "run_name",
        "output_dir", "video_dir", "planning_strategy", "planning_risk_lambda", "case_id"}
    identity = {k: v for k, v in requests[0].items() if k not in variable}
    runtime = {k: v for k, v in env.items() if not k.startswith(("LIBERO_PRO_PLANNING_GRID_", "LIBERO_PRO_PAIRED_"))
               and k != "LIBERO_CONFIG_PATH"}
    return hashlib.sha256(json.dumps([identity, runtime], sort_keys=True).encode()).hexdigest()


class CompatibleQueue:
    def __init__(self, jobs, key, batch_size=8):
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.pending = list(jobs)
        self.key = key
        self.batch_size = batch_size
        self.lock = threading.Lock()

    def empty(self):
        with self.lock:
            return not self.pending

    def take(self):
        with self.lock:
            if not self.pending:
                return []
            identity = self.key(self.pending[0])
            selected, remaining = [], []
            for job in self.pending:
                if len(selected) < self.batch_size and self.key(job) == identity:
                    selected.append(job)
                else:
                    remaining.append(job)
            self.pending = remaining
            return selected


class TorchRNG:
    """The cold loader changes RNG and backend flags; replay both on cache hits."""
    def capture(self):
        import numpy as np
        import torch
        return (random.getstate(), np.random.get_state(), torch.get_rng_state().clone(),
                [x.clone() for x in torch.cuda.get_rng_state_all()] if torch.cuda.is_initialized() else [],
                torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark,
                torch.backends.cudnn.allow_tf32, torch.backends.cuda.matmul.allow_tf32,
                torch.are_deterministic_algorithms_enabled(), torch.is_deterministic_algorithms_warn_only_enabled())

    def restore(self, state):
        import numpy as np
        import torch
        python, numpy, cpu, cuda, det, bench, tf32, matmul, algorithms, warn_only = state
        random.setstate(python)
        np.random.set_state(numpy)
        torch.set_rng_state(cpu)
        if cuda:
            torch.cuda.set_rng_state_all(cuda)
        torch.backends.cudnn.deterministic = det
        torch.backends.cudnn.benchmark = bench
        torch.backends.cudnn.allow_tf32 = tf32
        torch.backends.cuda.matmul.allow_tf32 = matmul
        torch.use_deterministic_algorithms(algorithms, warn_only=warn_only)


class ResidentModel:
    def __init__(self, loader, rng=None):
        self.loader, self.rng = loader, rng or TorchRNG()
        self.identity = None
        self.value = None
        self.state = None
        self.loads = 0
        self.hits = 0

    def __call__(self, cfg):
        identity = asdict(cfg)
        for name in ("seed", "task_suite_name"):
            identity.pop(name, None)
        if self.identity is None:
            self.value = self.loader(cfg)
            self.identity = copy.deepcopy(identity)
            self.state = self.rng.capture()
            self.loads += 1
        else:
            if identity != self.identity:
                raise ValueError("Incompatible model configuration in resident batch")
            self.rng.restore(self.state)
            self.hits += 1
        return self.value


class CPUQueue:
    """Bound outstanding artifacts so slow encoding cannot consume unbounded RAM."""
    def __init__(self, capacity=2):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.slots = threading.BoundedSemaphore(capacity)
        self.futures = []

    def submit(self, function, *args, **kwargs):
        for previous in self.futures:
            if previous.done():
                previous.result()
        self.slots.acquire()
        try:
            future = self.executor.submit(function, *args, **kwargs)
        except BaseException:
            self.slots.release()
            raise
        future.add_done_callback(lambda _: self.slots.release())
        self.futures.append(future)
        return future

    def close(self):
        self.executor.shutdown(wait=True)
        for future in self.futures:
            future.result()


class AsyncImageIO:
    """Keep the frozen filename/frame conversion; defer only the encoder writes."""
    def __init__(self, original, cpu):
        self.original, self.cpu = original, cpu

    def __getattr__(self, name):
        return getattr(self.original, name)

    def recover(self, path, **kwargs):
        import numpy as np
        target = Path(path)
        spool = target.with_suffix(".frames.npy")
        if not spool.is_file():
            raise RuntimeError(f"Missing video and frame spool: {target}")
        def encode():
            frames = np.load(spool, mmap_mode="r", allow_pickle=False)
            temporary = target.with_name(target.stem + ".encoding.mp4")
            with self.original.get_writer(temporary, **kwargs) as writer:
                for frame in frames:
                    writer.append_data(frame)
            del frames
            temporary.replace(target)
            spool.unlink()
        return self.cpu.submit(encode)

    def get_writer(self, path, **kwargs):
        owner = self
        class Writer:
            def __enter__(self):
                self.frames = []
                return self

            def append_data(self, frame):
                self.frames.append(frame.copy())

            def __exit__(self, exc_type, exc, tb):
                if exc_type is not None:
                    return False
                import numpy as np
                spool = Path(path).with_suffix(".frames.npy")
                temporary = spool.with_suffix(".tmp")
                with temporary.open("wb") as output:
                    np.save(output, np.asarray(self.frames), allow_pickle=False)
                temporary.replace(spool)
                self.frames.clear()
                owner.recover(path, **kwargs)
        return Writer()

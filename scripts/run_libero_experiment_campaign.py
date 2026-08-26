#!/usr/bin/env python3
"""Plan and run reproducible LIBERO / LIBERO-PRO / LIBERO-Safety campaigns."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "experiments/configs/libero_campaign_v1.json"


def _safe_name(value: str) -> str:
    result = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return result.strip("_") or "job"


def _as_bool_env(value: Any) -> str:
    return "1" if bool(value) else "0"


def load_campaign(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported campaign schema in {path}")
    if not isinstance(data.get("profiles"), dict):
        raise ValueError(f"Campaign has no profiles: {path}")
    return data


def expand_jobs(profile: Mapping[str, Any], defaults: Mapping[str, Any]) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for raw_job in profile.get("jobs", []):
        job = dict(defaults)
        job.update(copy.deepcopy(raw_job))
        if not job.get("enabled", True):
            continue
        if job["kind"] not in {
            "pro_position_sweep",
            "pro_position_planning_sweep",
            "pro_position_counterfactual_feedback_sweep",
        }:
            jobs.append(job)
            continue

        expanded_kind = {
            "pro_position_sweep": "pro_position_paired",
            "pro_position_planning_sweep": "pro_position_planning_grid",
            "pro_position_counterfactual_feedback_sweep": (
                "pro_position_counterfactual_feedback"
            ),
        }[job["kind"]]
        levels = job.pop("position_levels")
        for level_index, level in enumerate(levels):
            expanded = copy.deepcopy(job)
            expanded["kind"] = expanded_kind
            expanded["position_level"] = str(level)
            expanded["name"] = f"{job['name']}_{str(level).replace('.', 'p')}"
            expanded["base_seed"] = int(job["base_seed"]) + level_index * 10000
            jobs.append(expanded)
    return jobs


def _parse_int_spec(value: Any) -> List[int]:
    result: List[int] = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lower, upper = part.split("-", 1)
            result.extend(range(int(lower), int(upper) + 1))
        else:
            result.append(int(part))
    return result


def validate_job_inputs(job: Mapping[str, Any]) -> None:
    kind = str(job["kind"])
    task_ids = _parse_int_spec(job["task_ids"])
    if any(task_id < 0 for task_id in task_ids):
        raise ValueError(f"{job['name']}: task ids must be non-negative")
    experiment_split = str(job.get("experiment_split", "unspecified"))
    valid_splits = {"unspecified", "screen", "calibration", "holdout", "generalization"}
    if experiment_split not in valid_splits:
        raise ValueError(
            f"{job['name']}: invalid experiment_split={experiment_split!r}; "
            f"choose from {sorted(valid_splits)}"
        )

    if kind == "safety_paired":
        commit = os.environ.get(
            "LIBERO_SAFETY_COMMIT",
            "19ec8df23eedfbb9265bafd3e56495fcebfcfcd0",
        )
        repo = PROJECT_ROOT / ".external" / f"LIBERO-Safety-{commit}"
        venv = PROJECT_ROOT / ".venv-cosmos-safety/bin/python"
        if not repo.is_dir() or not venv.is_file():
            raise FileNotFoundError(
                "LIBERO-Safety is not set up. Run scripts/setup_mlspace_libero_safety.sh first."
            )
        if any(task_id >= 15 for task_id in task_ids):
            raise ValueError(f"{job['name']}: LIBERO-Safety flattened task ids are 0..14")
        for suite in str(job["suites"]).split(","):
            suite = suite.strip()
            if not suite:
                continue
            init_root = repo / "libero/libero/init_files" / suite
            if not any(init_root.glob("L*/*.pruned_init")):
                raise FileNotFoundError(
                    f"{job['name']}: LIBERO-Safety suite {suite!r} has no "
                    f"official initial states in pinned commit {commit}"
                )
        return

    if kind not in {
        "pro_paired",
        "pro_position_paired",
        "pro_planning_grid",
        "pro_position_planning_grid",
        "pro_environment_planning_grid",
        "pro_counterfactual_feedback",
        "pro_position_counterfactual_feedback",
        "pro_environment_counterfactual_feedback",
    }:
        raise ValueError(f"{job['name']}: unsupported kind {kind}")

    libero_root = PROJECT_ROOT / "LIBERO-PRO/libero/libero"
    for suite in str(job["suites"]).split(","):
        suite = suite.strip()
        if not suite:
            continue
        if kind in {
            "pro_position_paired",
            "pro_position_planning_grid",
            "pro_position_counterfactual_feedback",
        }:
            source_name = f"libero_object_temp_{job['position_level']}"
        elif kind in {
            "pro_environment_planning_grid",
            "pro_environment_counterfactual_feedback",
        }:
            source_name = suite.removesuffix("_env")
        else:
            source_name = suite
        bddl_dir = libero_root / "bddl_files" / source_name
        init_dir = libero_root / "init_files" / source_name
        if not bddl_dir.is_dir() or not init_dir.is_dir():
            raise FileNotFoundError(
                f"{job['name']}: missing BDDL/init directories for {source_name}"
            )
        num_tasks = len(list(bddl_dir.glob("*.bddl")))
        if task_ids and max(task_ids) >= num_tasks:
            raise ValueError(
                f"{job['name']}: task id {max(task_ids)} but {source_name} has {num_tasks} BDDL tasks"
            )


def _common_pro_paired_env(
    job: Mapping[str, Any],
    run_name: str,
    run_dir: Path,
    config_dir: Path,
) -> Dict[str, str]:
    prefix = "LIBERO_PRO_PAIRED_"
    return {
        "LIBERO_CONFIG_PATH": str(config_dir),
        f"{prefix}RUN_NAME": run_name,
        f"{prefix}SUITES": str(job["suites"]),
        f"{prefix}TASK_IDS": str(job["task_ids"]),
        f"{prefix}INIT_STATE_IDS": str(job["init_state_ids"]),
        f"{prefix}MAX_ROLLOUTS_PER_INIT": str(job["max_rollouts"]),
        f"{prefix}MIN_SUCCESS": str(job["min_success"]),
        f"{prefix}MIN_FAILED": str(job["min_failed"]),
        f"{prefix}BASE_SEED": str(job["base_seed"]),
        f"{prefix}UNCERTAINTY_SEEDS": str(job["uncertainty_seeds"]),
        f"{prefix}ROLLOUT_SEED_STEP": str(job.get("rollout_seed_step", 97)),
        f"{prefix}MAX_TIMESTEPS": str(job["max_timesteps"]),
        f"{prefix}OUTPUT_DIR": str(run_dir / "runs"),
        f"{prefix}SAVE_VIDEOS": _as_bool_env(job["save_videos"]),
        f"{prefix}VIDEO_DIR": str(run_dir / "videos" / run_name),
        f"{prefix}COLLECT_SAFETY_SIGNALS": _as_bool_env(job["collect_safety_signals"]),
        f"{prefix}TERMINATE_ON_SAFETY_VIOLATION": _as_bool_env(
            job.get("terminate_on_safety_violation", False)
        ),
        f"{prefix}RECORD_DENOISING_TRACE": _as_bool_env(job["record_denoising_trace"]),
        f"{prefix}RESUME": "1",
        f"{prefix}NUM_OPEN_LOOP_STEPS": str(job.get("num_open_loop_steps", 16)),
        f"{prefix}NUM_DENOISING_STEPS_ACTION": str(
            job.get("num_denoising_steps_action", 5)
        ),
        f"{prefix}PREDICTION_MODE": str(job.get("prediction_mode", "parallel")),
        f"{prefix}NUM_DENOISING_STEPS_FUTURE_STATE": str(
            job.get("num_denoising_steps_future_state", 1)
        ),
        f"{prefix}NUM_DENOISING_STEPS_VALUE": str(
            job.get("num_denoising_steps_value", 1)
        ),
        f"{prefix}NUM_FUTURE_STATE_SAMPLES": str(
            job.get("num_future_state_samples", 1)
        ),
        f"{prefix}NUM_VALUE_SAMPLES": str(job.get("num_value_samples", 1)),
        f"{prefix}VALUE_ENSEMBLE_AGGREGATION": str(
            job.get("value_ensemble_aggregation", "average")
        ),
        f"{prefix}EXPERIMENT_SPLIT": str(job.get("experiment_split", "unspecified")),
        f"{prefix}CASE_ID": str(job.get("case_id", job["name"])),
        f"{prefix}RECORD_TEMPORAL_OVERLAP": _as_bool_env(
            job.get("record_temporal_overlap", False)
        ),
        f"{prefix}TEMPORAL_OVERLAP_DIR": str(run_dir / "temporal_overlap" / run_name),
        f"{prefix}TEMPORAL_OVERLAP_SEED_MODE": str(
            job.get("temporal_overlap_seed_mode", "independent")
        ),
        f"{prefix}TEMPORAL_OVERLAP_MAX_WINDOW": str(
            job.get("temporal_overlap_max_window", 8)
        ),
        f"{prefix}PLANNING_ACTION_WEIGHT": str(job.get("planning_action_weight", 0.5)),
        f"{prefix}PLANNING_DIFFICULTY_THRESHOLD": str(
            job.get("planning_difficulty_threshold", 0.088588)
        ),
        f"{prefix}PLANNING_VALUE_MARGIN": str(job.get("planning_value_margin", 0.002)),
        f"{prefix}PLANNING_UNCERTAINTY_MARGIN": str(
            job.get("planning_uncertainty_margin", 0.0)
        ),
        f"{prefix}PLANNING_PHASE_FRACTION": str(job.get("planning_phase_fraction", 0.5)),
        f"{prefix}PLANNING_SHORT_OPEN_LOOP_STEPS": str(
            job.get("planning_short_open_loop_steps", 8)
        ),
        f"{prefix}PLANNING_SURROGATE_ERROR_THRESHOLD": str(
            job.get("planning_surrogate_error_threshold", 0.08841767562905925)
        ),
    }


def build_job(
    job: Mapping[str, Any],
    run_prefix: str,
    run_dir: Path,
) -> Tuple[List[List[str]], Dict[str, str], Path]:
    job_name = _safe_name(str(job["name"]))
    run_name = f"{run_prefix}__{job_name}"
    config_dir = run_dir / "configs" / job_name
    completion_marker = run_dir / "completed" / f"{job_name}.json"
    kind = job["kind"]

    if kind in {"pro_paired", "pro_position_paired"}:
        env = _common_pro_paired_env(job, run_name, run_dir, config_dir)
        commands: List[List[str]] = []
        if kind == "pro_position_paired":
            level = str(job["position_level"])
            commands.append(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts/prepare_libero_pro_position_variant.sh"),
                    level,
                ]
            )
            variant_root = PROJECT_ROOT / ".runtime/libero_pro_position" / level
            env["LIBERO_BDDL_FILES_PATH"] = str(variant_root / "bddl_files")
            env["LIBERO_INIT_STATES_PATH"] = str(variant_root / "init_files")
        commands.append(
            ["bash", str(PROJECT_ROOT / "scripts/run_libero_pro_paired_prediction_collect.sh")]
        )
        commands.append(
            [
                str(PROJECT_ROOT / ".venv-cosmos/bin/python"),
                str(PROJECT_ROOT / "scripts/analyze_libero_failure_modes.py"),
                "--trace-file",
                str(run_dir / "runs" / f"{run_name}__query_traces.csv"),
                "--output-dir",
                str(run_dir / "analysis" / run_name / "failure_modes"),
            ]
        )
        return commands, env, completion_marker

    if kind in {
        "pro_planning_grid",
        "pro_position_planning_grid",
        "pro_environment_planning_grid",
    }:
        env = {
            "LIBERO_CONFIG_PATH": str(config_dir),
            "LIBERO_PRO_PLANNING_GRID_PREFIX": run_name,
            "LIBERO_PRO_PLANNING_GRID_SUITES": str(job["suites"]),
            "LIBERO_PRO_PLANNING_GRID_TASK_IDS": str(job["task_ids"]),
            "LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS": str(job["init_state_ids"]),
            "LIBERO_PRO_PLANNING_GRID_MAX_ROLLOUTS_PER_INIT": str(job["max_rollouts"]),
            "LIBERO_PRO_PLANNING_GRID_BASE_SEED": str(job["base_seed"]),
            "LIBERO_PRO_PLANNING_GRID_UNCERTAINTY_SEEDS": str(job["uncertainty_seeds"]),
            "LIBERO_PRO_PLANNING_GRID_ROLLOUT_SEED_STEP": str(
                job.get("rollout_seed_step", 97)
            ),
            "LIBERO_PRO_PLANNING_GRID_MAX_TIMESTEPS": str(job["max_timesteps"]),
            "LIBERO_PRO_PLANNING_GRID_OUTPUT_DIR": str(run_dir / "runs"),
            "LIBERO_PRO_PLANNING_GRID_ANALYSIS_DIR": str(run_dir / "analysis" / run_name),
            "LIBERO_PRO_PLANNING_GRID_STRATEGY_LAMBDAS": str(job["strategy_lambdas"]),
            "LIBERO_PRO_PLANNING_GRID_NUM_OPEN_LOOP_STEPS": str(
                job.get("num_open_loop_steps", 16)
            ),
            "LIBERO_PRO_PLANNING_GRID_NUM_DENOISING_STEPS_ACTION": str(
                job.get("num_denoising_steps_action", 5)
            ),
            "LIBERO_PRO_PLANNING_GRID_PREDICTION_MODE": str(
                job.get("prediction_mode", "parallel")
            ),
            "LIBERO_PRO_PLANNING_GRID_NUM_DENOISING_STEPS_FUTURE_STATE": str(
                job.get("num_denoising_steps_future_state", 1)
            ),
            "LIBERO_PRO_PLANNING_GRID_NUM_DENOISING_STEPS_VALUE": str(
                job.get("num_denoising_steps_value", 1)
            ),
            "LIBERO_PRO_PLANNING_GRID_NUM_FUTURE_STATE_SAMPLES": str(
                job.get("num_future_state_samples", 1)
            ),
            "LIBERO_PRO_PLANNING_GRID_NUM_VALUE_SAMPLES": str(
                job.get("num_value_samples", 1)
            ),
            "LIBERO_PRO_PLANNING_GRID_VALUE_ENSEMBLE_AGGREGATION": str(
                job.get("value_ensemble_aggregation", "average")
            ),
            "LIBERO_PRO_PLANNING_GRID_EXPERIMENT_SPLIT": str(
                job.get("experiment_split", "unspecified")
            ),
            "LIBERO_PRO_PLANNING_GRID_CASE_ID": str(job.get("case_id", job["name"])),
            "LIBERO_PRO_PLANNING_GRID_RECORD_TEMPORAL_OVERLAP": _as_bool_env(
                job.get("record_temporal_overlap", False)
            ),
            "LIBERO_PRO_PLANNING_GRID_TEMPORAL_OVERLAP_DIR": str(
                run_dir / "temporal_overlap" / run_name
            ),
            "LIBERO_PRO_PLANNING_GRID_TEMPORAL_OVERLAP_SEED_MODE": str(
                job.get("temporal_overlap_seed_mode", "independent")
            ),
            "LIBERO_PRO_PLANNING_GRID_TEMPORAL_OVERLAP_MAX_WINDOW": str(
                job.get("temporal_overlap_max_window", 8)
            ),
            "LIBERO_PRO_PLANNING_GRID_ACTION_WEIGHT": str(
                job.get("planning_action_weight", 0.5)
            ),
            "LIBERO_PRO_PLANNING_GRID_DIFFICULTY_THRESHOLD": str(
                job.get("planning_difficulty_threshold", 0.088588)
            ),
            "LIBERO_PRO_PLANNING_GRID_VALUE_MARGIN": str(
                job.get("planning_value_margin", 0.002)
            ),
            "LIBERO_PRO_PLANNING_GRID_UNCERTAINTY_MARGIN": str(
                job.get("planning_uncertainty_margin", 0.0)
            ),
            "LIBERO_PRO_PLANNING_GRID_PHASE_FRACTION": str(
                job.get("planning_phase_fraction", 0.5)
            ),
            "LIBERO_PRO_PLANNING_GRID_SHORT_OPEN_LOOP_STEPS": str(
                job.get("planning_short_open_loop_steps", 8)
            ),
            "LIBERO_PRO_PLANNING_GRID_SURROGATE_ERROR_THRESHOLD": str(
                job.get("planning_surrogate_error_threshold", 0.08841767562905925)
            ),
            "LIBERO_PRO_PAIRED_SAVE_VIDEOS": _as_bool_env(job["save_videos"]),
            "LIBERO_PRO_PAIRED_VIDEO_DIR": str(run_dir / "videos" / run_name),
            "LIBERO_PRO_PAIRED_COLLECT_SAFETY_SIGNALS": _as_bool_env(
                job["collect_safety_signals"]
            ),
            "LIBERO_PRO_PAIRED_RECORD_DENOISING_TRACE": _as_bool_env(
                job["record_denoising_trace"]
            ),
        }
        commands: List[List[str]] = []
        if kind == "pro_position_planning_grid":
            level = str(job["position_level"])
            commands.append(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts/prepare_libero_pro_position_variant.sh"),
                    level,
                ]
            )
            variant_root = PROJECT_ROOT / ".runtime/libero_pro_position" / level
            env["LIBERO_BDDL_FILES_PATH"] = str(variant_root / "bddl_files")
            env["LIBERO_INIT_STATES_PATH"] = str(variant_root / "init_files")
            env["LIBERO_PRO_POSITION_LEVEL"] = level
        elif kind == "pro_environment_planning_grid":
            commands.append(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts/prepare_libero_pro_environment_variant.sh"),
                    str(job.get("environment_num_init_states", 50)),
                    str(job.get("environment_seed", 20260825)),
                ]
            )
            variant_root = PROJECT_ROOT / ".runtime/libero_pro_environment"
            env["LIBERO_BDDL_FILES_PATH"] = str(variant_root / "bddl_files")
            env["LIBERO_INIT_STATES_PATH"] = str(variant_root / "init_files")
        commands.append(
            ["bash", str(PROJECT_ROOT / "scripts/run_libero_pro_planning_strategy_grid.sh")]
        )
        return commands, env, completion_marker

    if kind in {
        "pro_counterfactual_feedback",
        "pro_position_counterfactual_feedback",
        "pro_environment_counterfactual_feedback",
    }:
        env = {
            "LIBERO_CONFIG_PATH": str(config_dir),
            "LIBERO_PRO_VOF_RUN_NAME": run_name,
            "LIBERO_PRO_VOF_SUITES": str(job["suites"]),
            "LIBERO_PRO_VOF_TASK_IDS": str(job["task_ids"]),
            "LIBERO_PRO_VOF_INIT_STATE_IDS": str(job["init_state_ids"]),
            "LIBERO_PRO_VOF_ROLLOUTS_PER_INIT": str(job["rollouts_per_init"]),
            "LIBERO_PRO_VOF_BASE_SEED": str(job["base_seed"]),
            "LIBERO_PRO_VOF_ROLLOUT_SEED_STEP": str(job.get("rollout_seed_step", 97)),
            "LIBERO_PRO_VOF_UNCERTAINTY_SEEDS": str(job["uncertainty_seeds"]),
            "LIBERO_PRO_VOF_MAX_TIMESTEPS": str(job["max_timesteps"]),
            "LIBERO_PRO_VOF_TARGET_DECISION_STATES": str(job["target_decision_states"]),
            "LIBERO_PRO_VOF_PHASE_CAP_FRACTION": str(job.get("phase_cap_fraction", 0.4)),
            "LIBERO_PRO_VOF_TERMINAL_CONTINUATION_FRACTION": str(
                job.get("terminal_continuation_fraction", 0.2)
            ),
            "LIBERO_PRO_VOF_QUERY_COST": str(job.get("query_cost", 0.0)),
            "LIBERO_PRO_VOF_NUM_DENOISING_STEPS_ACTION": str(
                job.get("num_denoising_steps_action", 5)
            ),
            "LIBERO_PRO_VOF_PREDICTION_MODE": str(job.get("prediction_mode", "parallel")),
            "LIBERO_PRO_VOF_NUM_DENOISING_STEPS_FUTURE_STATE": str(
                job.get("num_denoising_steps_future_state", 1)
            ),
            "LIBERO_PRO_VOF_NUM_DENOISING_STEPS_VALUE": str(
                job.get("num_denoising_steps_value", 1)
            ),
            "LIBERO_PRO_VOF_NUM_FUTURE_STATE_SAMPLES": str(
                job.get("num_future_state_samples", 1)
            ),
            "LIBERO_PRO_VOF_NUM_VALUE_SAMPLES": str(job.get("num_value_samples", 1)),
            "LIBERO_PRO_VOF_VALUE_ENSEMBLE_AGGREGATION": str(
                job.get("value_ensemble_aggregation", "average")
            ),
            "LIBERO_PRO_VOF_EXPERIMENT_SPLIT": str(
                job.get("experiment_split", "screen")
            ),
            "LIBERO_PRO_VOF_CASE_ID": str(job.get("case_id", job["name"])),
            "LIBERO_PRO_VOF_OUTPUT_DIR": str(run_dir / "runs"),
            "LIBERO_PRO_VOF_RESUME": "1",
        }
        commands = []
        if kind == "pro_position_counterfactual_feedback":
            level = str(job["position_level"])
            commands.append(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts/prepare_libero_pro_position_variant.sh"),
                    level,
                ]
            )
            variant_root = PROJECT_ROOT / ".runtime/libero_pro_position" / level
            env["LIBERO_BDDL_FILES_PATH"] = str(variant_root / "bddl_files")
            env["LIBERO_INIT_STATES_PATH"] = str(variant_root / "init_files")
            env["LIBERO_PRO_POSITION_LEVEL"] = level
        elif kind == "pro_environment_counterfactual_feedback":
            commands.append(
                [
                    "bash",
                    str(PROJECT_ROOT / "scripts/prepare_libero_pro_environment_variant.sh"),
                    str(job.get("environment_num_init_states", 10)),
                    str(job.get("environment_seed", 20260825)),
                ]
            )
            variant_root = PROJECT_ROOT / ".runtime/libero_pro_environment"
            env["LIBERO_BDDL_FILES_PATH"] = str(variant_root / "bddl_files")
            env["LIBERO_INIT_STATES_PATH"] = str(variant_root / "init_files")
        commands.append(
            [
                "bash",
                str(PROJECT_ROOT / "scripts/run_libero_pro_counterfactual_feedback_collect.sh"),
            ]
        )
        return commands, env, completion_marker

    if kind == "safety_paired":
        prefix = "LIBERO_SAFETY_"
        env = {
            "COSMOS_VENV": str(PROJECT_ROOT / ".venv-cosmos-safety"),
            "LIBERO_CONFIG_PATH": str(config_dir),
            f"{prefix}RUN_NAME": run_name,
            f"{prefix}SUITES": str(job["suites"]),
            f"{prefix}TASK_IDS": str(job["task_ids"]),
            f"{prefix}INIT_STATE_IDS": str(job["init_state_ids"]),
            f"{prefix}MAX_ROLLOUTS_PER_INIT": str(job["max_rollouts"]),
            f"{prefix}MIN_SUCCESS": str(job["min_success"]),
            f"{prefix}MIN_FAILED": str(job["min_failed"]),
            f"{prefix}BASE_SEED": str(job["base_seed"]),
            f"{prefix}UNCERTAINTY_SEEDS": str(job["uncertainty_seeds"]),
            f"{prefix}MAX_TIMESTEPS": str(job["max_timesteps"]),
            f"{prefix}OUTPUT_DIR": str(run_dir / "runs"),
            f"{prefix}SAVE_VIDEOS": _as_bool_env(job["save_videos"]),
            f"{prefix}VIDEO_DIR": str(run_dir / "videos" / run_name),
            f"{prefix}RECORD_DENOISING_TRACE": _as_bool_env(job["record_denoising_trace"]),
            f"{prefix}TERMINATE_ON_VIOLATION": _as_bool_env(
                job.get("terminate_on_safety_violation", True)
            ),
        }
        commands = [
            ["bash", str(PROJECT_ROOT / "scripts/run_libero_safety_paired_prediction_collect.sh")],
            [
                str(PROJECT_ROOT / ".venv-cosmos-safety/bin/python"),
                str(PROJECT_ROOT / "scripts/analyze_libero_failure_modes.py"),
                "--trace-file",
                str(run_dir / "runs" / f"{run_name}__query_traces.csv"),
                "--output-dir",
                str(run_dir / "analysis" / run_name / "failure_modes"),
            ],
        ]
        return commands, env, completion_marker

    raise ValueError(f"Unknown job kind: {kind}")


def format_job_command(commands: Sequence[Sequence[str]], env: Mapping[str, str], gpu: str) -> str:
    env_items = {"CUDA_VISIBLE_DEVICES": gpu, **env}
    prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in sorted(env_items.items()))
    rendered = [prefix + " " + shlex.join(list(command)) for command in commands]
    return "\n".join(rendered)


def run_job(
    job: Mapping[str, Any],
    run_prefix: str,
    run_dir: Path,
    gpu: str,
    force: bool,
) -> Dict[str, Any]:
    commands, extra_env, marker = build_job(job, run_prefix, run_dir)
    job_name = _safe_name(str(job["name"]))
    log_path = run_dir / "logs" / f"{job_name}.log"
    if marker.exists() and not force:
        print(f"[campaign] skip completed job={job_name}")
        return {"job": job_name, "gpu": gpu, "status": "skipped", "marker": str(marker)}

    marker.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(extra_env)
    env["CUDA_VISIBLE_DEVICES"] = gpu
    env.setdefault("HF_HUB_OFFLINE", "1")

    started = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n[{started}] GPU={gpu} job={job_name}\n")
        for command in commands:
            rendered = shlex.join(command)
            print(f"[campaign] gpu={gpu} job={job_name}: {rendered}")
            log_file.write(f"$ {rendered}\n")
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                log_file.write(line)
                if line.startswith(("[collect]", "[paired]", "[grid]", "Saved traces:")):
                    print(f"[{job_name}] {line.rstrip()}")
            return_code = process.wait()
            if return_code != 0:
                print(f"[campaign] FAILED job={job_name}; log={log_path}")
                return {
                    "job": job_name,
                    "gpu": gpu,
                    "status": "failed",
                    "return_code": return_code,
                    "log": str(log_path),
                }

    result = {
        "job": job_name,
        "gpu": gpu,
        "status": "completed",
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "log": str(log_path),
    }
    marker.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[campaign] completed job={job_name} gpu={gpu}")
    return result


def run_gpu_queue(
    jobs: Sequence[Mapping[str, Any]],
    run_prefix: str,
    run_dir: Path,
    gpu: str,
    force: bool,
) -> List[Dict[str, Any]]:
    return [run_job(job, run_prefix, run_dir, gpu, force) for job in jobs]


def partition_jobs(jobs: Sequence[Mapping[str, Any]], gpus: Sequence[str]) -> List[List[Mapping[str, Any]]]:
    buckets: List[List[Mapping[str, Any]]] = [[] for _ in gpus]
    for index, job in enumerate(jobs):
        slot = int(job.get("gpu_slot", index % len(gpus)))
        if slot < 0 or slot >= len(gpus):
            raise ValueError(
                f"{job['name']}: gpu_slot={slot} but only {len(gpus)} GPU slots were provided"
            )
        buckets[slot].append(job)
    return buckets


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", default="")
    parser.add_argument("--list", action="store_true", help="List available profiles")
    parser.add_argument("--execute", action="store_true", help="Run jobs; otherwise only print commands")
    parser.add_argument("--run-prefix", default="")
    parser.add_argument("--gpus", default="2", help="Physical GPU ids, e.g. 2,3,4,5")
    parser.add_argument("--max-parallel", type=int, default=0)
    parser.add_argument("--only", default="", help="Comma-separated expanded job names")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    campaign = load_campaign(args.config)
    profiles = campaign["profiles"]
    if args.list:
        for name, profile in profiles.items():
            print(f"{name}: {profile.get('description', '')}")
        return 0
    if not args.profile or args.profile not in profiles:
        print(f"Choose --profile from: {', '.join(profiles)}", file=sys.stderr)
        return 2

    jobs = expand_jobs(profiles[args.profile], campaign.get("defaults", {}))
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if only:
        jobs = [job for job in jobs if job["name"] in only]
    if not jobs:
        print("No jobs selected.", file=sys.stderr)
        return 2
    for job in jobs:
        if args.execute or job["kind"] != "safety_paired":
            validate_job_inputs(job)

    run_prefix = _safe_name(
        args.run_prefix or f"{args.profile}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    run_dir = PROJECT_ROOT / "experiments/campaigns" / run_prefix
    run_dir.mkdir(parents=True, exist_ok=True)
    gpus = [item.strip() for item in args.gpus.split(",") if item.strip()]
    if not gpus:
        raise ValueError("At least one GPU is required")
    if args.execute and "0" in gpus:
        raise ValueError("Physical GPU 0 is reserved on MLSpace")
    if args.max_parallel > 0:
        gpus = gpus[: args.max_parallel]

    planned_jobs = []
    for index, job in enumerate(jobs):
        slot = int(job.get("gpu_slot", index % len(gpus)))
        if slot < 0 or slot >= len(gpus):
            raise ValueError(
                f"{job['name']}: gpu_slot={slot} but only {len(gpus)} GPU slots were provided"
            )
        gpu = gpus[slot]
        commands, env, marker = build_job(job, run_prefix, run_dir)
        planned_jobs.append(
            {
                "name": job["name"],
                "kind": job["kind"],
                "gpu": gpu,
                "commands": commands,
                "environment": env,
                "completion_marker": str(marker),
            }
        )
        if not args.execute:
            print(f"\n# {job['name']} ({job['kind']}, GPU {gpu})")
            print(format_job_command(commands, env, gpu))

    manifest_path = run_dir / "manifest.json"
    manifest = {
        "schema_version": 1,
        "profile": args.profile,
        "description": profiles[args.profile].get("description", ""),
        "run_prefix": run_prefix,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "config": str(args.config.resolve()),
        "jobs": planned_jobs,
        "status": "planned" if not args.execute else "running",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[campaign] manifest={manifest_path}")
    if not args.execute:
        print("[campaign] dry run only; add --execute to launch")
        return 0

    buckets = partition_jobs(jobs, gpus)
    results: List[Dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(gpus)) as executor:
        futures = [
            executor.submit(run_gpu_queue, bucket, run_prefix, run_dir, gpu, args.force)
            for gpu, bucket in zip(gpus, buckets)
            if bucket
        ]
        for future in concurrent.futures.as_completed(futures):
            results.extend(future.result())

    failed = [result for result in results if result["status"] == "failed"]
    manifest["status"] = "failed" if failed else "completed"
    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["results"] = sorted(results, key=lambda item: item["job"])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[campaign] status={manifest['status']} manifest={manifest_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compare online RGB-triggered regrasp against a shared-prefix LIBERO-PRO baseline."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import imageio.v2 as imageio
import numpy as np
import pandas as pd
from libero.libero import benchmark
from robosuite.utils.camera_utils import (
    get_camera_extrinsic_matrix,
    get_camera_intrinsic_matrix,
)

from cosmos_policy.experiments.robot.cosmos_utils import (
    get_model,
    init_t5_text_embeddings_cache,
    load_dataset_stats,
)
from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
)
from cosmos_policy.experiments.robot.libero.run_libero_eval import (
    prewarm_libero_renderer,
    validate_config,
)
from cosmos_policy.experiments.robot.libero.safety_signals import (
    SafetySignalTracker,
    unwrap_libero_env,
)
from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
    default_policy_config,
    get_task_init_states_compat,
    parse_seed_list,
)
from cosmos_policy.experiments.robot.robot_utils import get_image_resize_size
from cosmos_policy.utils.utils import set_seed_everywhere

from collect_counterfactual_feedback import (
    _sample_candidates,
    _select_max_value,
    _terminal_outcome,
)
from collect_recovery_proposals import (
    _eef_position,
    _execute,
    _frame,
    _run_perception_regrasp,
)
from libero_runtime_snapshot import capture_libero_runtime_state, restore_libero_runtime_state
from perception_regrasp import FrozenPatchLocalizer, localization_record, raw_agentview_image
from perception_regrasp_trigger import (
    INTERVENTION_STRATEGIES,
    evaluate_trigger,
    load_trigger_artifact,
    resolve_intervention_strategy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FrameBuffer:
    def __init__(self, initial: np.ndarray | None = None) -> None:
        self.frames: list[np.ndarray] = []
        if initial is not None:
            self.append_data(initial)

    def append_data(self, frame: np.ndarray) -> None:
        self.frames.append(np.asarray(frame, dtype=np.uint8).copy())


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _parse_ints(value: str) -> tuple[int, ...]:
    result = []
    for item in value.split(","):
        item = item.strip()
        if item:
            result.append(int(item))
    return tuple(result)


def _clone_tracker(tracker: SafetySignalTracker, env: Any) -> SafetySignalTracker:
    clone = object.__new__(SafetySignalTracker)
    for key, value in tracker.__dict__.items():
        if key == "env":
            cloned_value = unwrap_libero_env(env)
        elif key == "object_states":
            # These values own MuJoCo ctypes pointers. The environment object is
            # unchanged by runtime restore, so a shallow mapping copy is correct.
            cloned_value = dict(value)
        else:
            cloned_value = copy.deepcopy(value)
        setattr(clone, key, cloned_value)
    return clone


def _atomic_tables(
    output_dir: Path,
    run_name: str,
    branch_rows: list[dict[str, Any]],
    query_rows: list[dict[str, Any]],
) -> None:
    for stem, rows in (("online_branches", branch_rows), ("query_metrics", query_rows)):
        frame = pd.DataFrame(rows)
        parquet = output_dir / f"{run_name}__{stem}.parquet"
        csv = output_dir / f"{run_name}__{stem}.csv"
        parquet_tmp = parquet.with_name(parquet.stem + ".tmp.parquet")
        csv_tmp = csv.with_name(csv.stem + ".tmp.csv")
        frame.to_parquet(parquet_tmp, index=False)
        frame.to_csv(csv_tmp, index=False)
        os.replace(parquet_tmp, parquet)
        os.replace(csv_tmp, csv)


def _case_columns(row: Any, task_description: str) -> dict[str, Any]:
    result = {
        "case_id": str(row.case_id),
        "split": str(row.split),
        "suite": str(row.suite),
        "position_level": str(row.position_level),
        "task_id": int(row.task_id),
        "init_state_id": int(row.init_state_id),
        "rollout_id": int(row.rollout_id),
        "rollout_seed": int(row.rollout_seed),
        "independent_group": str(row.independent_group),
        "task_description": task_description,
    }
    if hasattr(row, "evaluation_cohort"):
        result["evaluation_cohort"] = str(row.evaluation_cohort)
    return result


def _seeds(rollout_seed: int, query_idx: int, offsets: Sequence[int]) -> tuple[int, ...]:
    return tuple(int(rollout_seed + query_idx * 1000 + offset) for offset in offsets)


def _query_row(
    case: Mapping[str, Any],
    *,
    strategy: str,
    query_idx: int,
    query_t: int,
    seeds: Sequence[int],
    executed_steps: int,
    success: bool,
    metrics: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    result = {
        **case,
        "strategy": strategy,
        "query_idx": query_idx,
        "query_t": query_t,
        "query_seed_values": json.dumps(list(seeds)),
        "executed_steps": executed_steps,
        "success_after_query": bool(success),
    }
    result.update({key: _json_scalar(value) for key, value in metrics.items()})
    result.update({key: _json_scalar(value) for key, value in diagnostics.items()})
    return result


def _localize(
    env: Any,
    obs: Mapping[str, Any],
    localizer: FrozenPatchLocalizer,
    task_description: str,
) -> dict[str, Any]:
    image = raw_agentview_image(obs)
    intrinsic = get_camera_intrinsic_matrix(
        env.sim, "agentview", image.shape[0], image.shape[1]
    )
    camera_to_world = get_camera_extrinsic_matrix(env.sim, "agentview")
    localization = localizer.localize(
        image,
        task_description,
        intrinsic=intrinsic,
        camera_to_world=camera_to_world,
    )
    return dict(localization_record(localization))


def _open_video(
    video_dir: Path,
    case_id: str,
    strategy: str,
    prefix_frames: Sequence[np.ndarray],
    fps: int,
) -> tuple[Any, Path, Path]:
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in case_id)
    final = video_dir / f"{safe}__{strategy}.mp4"
    temporary = video_dir / f"{safe}__{strategy}.partial.mp4"
    temporary.unlink(missing_ok=True)
    writer = imageio.get_writer(temporary, fps=fps, macro_block_size=1)
    for frame in prefix_frames:
        writer.append_data(frame)
    return writer, temporary, final


def _finish_video(writer: Any, temporary: Path, final: Path) -> str:
    writer.close()
    os.replace(temporary, final)
    return str(final.relative_to(PROJECT_ROOT))


def _continue_policy(
    cfg: Any,
    model: Any,
    dataset_stats: Mapping[str, Any],
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    case: Mapping[str, Any],
    task_description: str,
    offsets: Sequence[int],
    *,
    strategy: str,
    absolute_t: int,
    query_idx: int,
    max_t: int,
    resize_size: int,
    execution_horizon: int,
    prediction_mode: str,
    writer: Any | None,
) -> tuple[Mapping[str, Any], bool, int, int, list[dict[str, Any]]]:
    success = bool(env.check_success())
    rows = []
    continuation_queries = 0
    while not success and absolute_t < max_t:
        seeds = _seeds(int(case["rollout_seed"]), query_idx, offsets)
        query_t = absolute_t
        samples, metrics = _sample_candidates(
            cfg,
            model,
            dataset_stats,
            obs,
            task_description,
            seeds,
            resize_size,
            prediction_mode=prediction_mode,
        )
        selected, diagnostics = _select_max_value(samples, open_loop_steps=execution_horizon)
        obs, success, absolute_t, executed = _execute(
            env,
            obs,
            np.asarray(samples[selected]["actions"], dtype=np.float32)[:execution_horizon],
            tracker,
            absolute_t=absolute_t,
            max_t=max_t,
            writer=writer,
            flip_images=cfg.flip_images,
        )
        rows.append(
            _query_row(
                case,
                strategy=strategy,
                query_idx=query_idx,
                query_t=query_t,
                seeds=seeds,
                executed_steps=executed,
                success=success,
                metrics=metrics,
                diagnostics=diagnostics,
            )
        )
        query_idx += 1
        continuation_queries += 1
    return obs, success, absolute_t, continuation_queries, rows


def _outcome_row(
    case: Mapping[str, Any],
    tracker: SafetySignalTracker,
    *,
    strategy: str,
    success: bool,
    final_t: int,
    max_t: int,
    continuation_queries: int,
    prefix_state_sha256: str,
    replay_error: float,
    trigger: Mapping[str, Any],
    localization: Mapping[str, Any],
    primitive_diagnostics: Mapping[str, Any] | None = None,
    primitive_steps: int = 0,
    intervention_applied: bool = False,
    counterfactual_reused: bool = False,
    video_path: str = "",
) -> dict[str, Any]:
    trigger_localization = {
        f"trigger_localization_{key.removeprefix('perception_')}": value
        for key, value in localization.items()
    }
    return {
        **case,
        "strategy": strategy,
        "prefix_state_sha256": prefix_state_sha256,
        "snapshot_replay_max_abs": replay_error,
        "primitive_steps": primitive_steps,
        "intervention_applied": intervention_applied,
        "counterfactual_reused": counterfactual_reused,
        "video_path": video_path,
        **trigger_localization,
        **trigger,
        **(primitive_diagnostics or {}),
        **_terminal_outcome(
            tracker,
            success=success,
            final_t=final_t,
            max_t=max_t,
            continuation_queries=continuation_queries,
        ),
    }


def collect(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = pd.read_parquet(args.manifest.expanduser().resolve())
    manifest = manifest.loc[manifest["position_level"].astype(str).eq(args.position_level)].copy()
    task_ids = set(_parse_ints(args.task_ids))
    if task_ids:
        manifest = manifest.loc[manifest["task_id"].astype(int).isin(task_ids)]
    manifest = manifest.sort_values(
        ["task_id", "init_state_id", "rollout_id"], kind="stable"
    ).reset_index(drop=True)
    if args.max_cases > 0:
        manifest = manifest.head(args.max_cases).copy()
    if manifest.empty:
        raise ValueError(f"No cases for position={args.position_level} tasks={args.task_ids}")
    if manifest["suite"].nunique() != 1:
        raise ValueError("A collector shard must contain one suite")

    strategies = tuple(item.strip() for item in args.trigger_modes.split(",") if item.strip())
    if not strategies or any(
        strategy not in INTERVENTION_STRATEGIES for strategy in strategies
    ):
        raise ValueError(f"Invalid intervention strategies: {strategies}")
    trigger_artifact = load_trigger_artifact(args.trigger_artifact)
    offsets = parse_seed_list(args.uncertainty_seeds)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir / f"{args.run_name}__videos"
    if args.save_videos:
        video_dir.mkdir(parents=True, exist_ok=True)

    branch_path = output_dir / f"{args.run_name}__online_branches.parquet"
    query_path = output_dir / f"{args.run_name}__query_metrics.parquet"
    branch_rows = (
        pd.read_parquet(branch_path).to_dict(orient="records")
        if args.resume and branch_path.exists()
        else []
    )
    query_rows = (
        pd.read_parquet(query_path).to_dict(orient="records")
        if args.resume and query_path.exists()
        else []
    )
    expected_strategies = {"baseline_h8", *strategies}
    completed = {
        case_id
        for case_id, group in pd.DataFrame(branch_rows).groupby("case_id")
        if set(group["strategy"].astype(str)) == expected_strategies
    } if branch_rows else set()

    suite_name = str(manifest.iloc[0]["suite"])
    cfg = default_policy_config(
        suite_name,
        seed=args.base_seed,
        num_open_loop_steps=16,
        num_denoising_steps_action=args.num_denoising_steps_action,
        prediction_mode=args.prediction_mode,
        num_denoising_steps_future_state=args.num_denoising_steps_future_state,
        num_denoising_steps_value=args.num_denoising_steps_value,
        num_future_state_samples=args.num_future_state_samples,
        num_value_samples=args.num_value_samples,
    )
    validate_config(cfg)
    set_seed_everywhere(cfg.seed)
    init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    dataset_stats = load_dataset_stats(cfg.dataset_stats_path)
    prewarm_libero_renderer(cfg)
    model, cosmos_config = get_model(cfg)
    if cfg.chunk_size != cosmos_config.dataloader_train.dataset.chunk_size:
        raise ValueError("checkpoint and evaluation action chunk sizes differ")
    resize_size = get_image_resize_size(cfg.model_family)
    localizer = FrozenPatchLocalizer(args.perception_model, device=args.perception_device)
    task_suite = benchmark.get_benchmark_dict()[suite_name]()

    for task_id, task_cases in manifest.groupby("task_id", sort=True):
        task = task_suite.get_task(int(task_id))
        task_description = str(task.language)
        init_states = get_task_init_states_compat(task_suite, int(task_id), task)
        env, _ = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            for row in task_cases.itertuples(index=False):
                if str(row.case_id) in completed:
                    continue
                if int(row.init_state_id) >= len(init_states):
                    raise ValueError(
                        f"init_state_id={row.init_state_id}, available={len(init_states)}"
                    )
                query_rows = [item for item in query_rows if item.get("case_id") != row.case_id]
                case = _case_columns(row, task_description)
                set_seed_everywhere(int(row.rollout_seed))
                env.reset()
                obs = env.set_init_state(init_states[int(row.init_state_id)])
                for _ in range(10):
                    obs, _reward, done, _info = env.step(get_libero_dummy_action(cfg.model_family))
                    if done:
                        break
                tracker = SafetySignalTracker(env, obs)
                frame_buffer = FrameBuffer(
                    _frame(obs, flip_images=cfg.flip_images) if args.save_videos else None
                )
                prefix_writer = frame_buffer if args.save_videos else None
                success = bool(env.check_success())
                absolute_t = 0
                prefix_query_rows = []
                for query_idx in range(args.trigger_query_idx + 1):
                    if success or absolute_t >= args.max_timesteps:
                        break
                    horizon = (
                        args.trigger_prefix_steps
                        if query_idx == args.trigger_query_idx
                        else args.prefix_horizon
                    )
                    seeds = _seeds(int(row.rollout_seed), query_idx, offsets)
                    query_t = absolute_t
                    samples, metrics = _sample_candidates(
                        cfg,
                        model,
                        dataset_stats,
                        obs,
                        task_description,
                        seeds,
                        resize_size,
                        prediction_mode=args.prediction_mode,
                    )
                    selected, diagnostics = _select_max_value(samples, open_loop_steps=horizon)
                    obs, success, absolute_t, executed = _execute(
                        env,
                        obs,
                        np.asarray(samples[selected]["actions"], dtype=np.float32)[:horizon],
                        tracker,
                        absolute_t=absolute_t,
                        max_t=args.max_timesteps,
                        writer=prefix_writer,
                        flip_images=cfg.flip_images,
                    )
                    prefix_query_rows.append(
                        _query_row(
                            case,
                            strategy="common_prefix",
                            query_idx=query_idx,
                            query_t=query_t,
                            seeds=seeds,
                            executed_steps=executed,
                            success=success,
                            metrics=metrics,
                            diagnostics=diagnostics,
                        )
                    )

                snapshot = capture_libero_runtime_state(env)
                snapshot_hash = hashlib.sha256(
                    np.asarray(snapshot["sim_state"], dtype=np.float64).tobytes()
                ).hexdigest()
                localization: dict[str, Any] = {}
                decisions: dict[str, dict[str, Any]] = {}
                if not success:
                    localization = _localize(env, obs, localizer, task_description)
                    for strategy in strategies:
                        trigger_mode, _primitive = resolve_intervention_strategy(strategy)
                        decisions[strategy] = evaluate_trigger(
                            localization,
                            _eef_position(obs),
                            trigger_artifact,
                            mode=trigger_mode,
                        ).as_dict()

                restored_obs = restore_libero_runtime_state(env, snapshot)
                actual = np.asarray(env.get_sim_state(), dtype=np.float64).reshape(-1)
                expected = np.asarray(snapshot["sim_state"], dtype=np.float64).reshape(-1)
                replay_error = float(np.max(np.abs(actual - expected)))
                if replay_error > args.replay_threshold:
                    raise RuntimeError(f"Snapshot replay error {replay_error:.3e} for {row.case_id}")

                baseline_writer = baseline_tmp = baseline_final = None
                if args.save_videos:
                    baseline_writer, baseline_tmp, baseline_final = _open_video(
                        video_dir,
                        str(row.case_id),
                        "baseline_h8",
                        frame_buffer.frames,
                        args.video_fps,
                    )
                baseline_tracker = _clone_tracker(tracker, env)
                baseline_query_rows: list[dict[str, Any]] = []
                if success:
                    baseline_success, baseline_t, baseline_queries = True, absolute_t, 0
                else:
                    (
                        restored_obs,
                        baseline_success,
                        baseline_t,
                        baseline_queries,
                        baseline_query_rows,
                    ) = _continue_policy(
                        cfg,
                        model,
                        dataset_stats,
                        env,
                        restored_obs,
                        baseline_tracker,
                        case,
                        task_description,
                        offsets,
                        strategy="baseline_h8",
                        absolute_t=absolute_t,
                        query_idx=args.trigger_query_idx + 1,
                        max_t=args.max_timesteps,
                        resize_size=resize_size,
                        execution_horizon=args.continuation_horizon,
                        prediction_mode=args.prediction_mode,
                        writer=baseline_writer,
                    )
                baseline_video = (
                    _finish_video(baseline_writer, baseline_tmp, baseline_final)
                    if baseline_writer is not None
                    else ""
                )
                baseline_row = _outcome_row(
                    case,
                    baseline_tracker,
                    strategy="baseline_h8",
                    success=baseline_success,
                    final_t=baseline_t,
                    max_t=args.max_timesteps,
                    continuation_queries=baseline_queries,
                    prefix_state_sha256=snapshot_hash,
                    replay_error=replay_error,
                    trigger={"trigger_passed": False, "trigger_mode": "baseline"},
                    localization=localization,
                    video_path=baseline_video,
                )
                new_branch_rows = [baseline_row]
                new_query_rows = [*prefix_query_rows, *baseline_query_rows]

                for strategy in strategies:
                    trigger_mode, primitive = resolve_intervention_strategy(strategy)
                    decision = decisions.get(
                        strategy,
                        {"trigger_passed": False, "trigger_mode": trigger_mode},
                    )
                    if success or not bool(decision["trigger_passed"]):
                        copied = dict(baseline_row)
                        copied.update(decision)
                        copied.update(
                            {
                                "strategy": strategy,
                                "counterfactual_reused": True,
                                "intervention_applied": False,
                            }
                        )
                        new_branch_rows.append(copied)
                        continue

                    method_obs = restore_libero_runtime_state(env, snapshot)
                    method_tracker = _clone_tracker(tracker, env)
                    method_writer = method_tmp = method_final = None
                    if args.save_videos:
                        method_writer, method_tmp, method_final = _open_video(
                            video_dir,
                            str(row.case_id),
                            strategy,
                            frame_buffer.frames,
                            args.video_fps,
                        )

                    def validator(
                        localized: Any,
                        eef: np.ndarray,
                        selected_mode: str = trigger_mode,
                    ) -> dict[str, Any]:
                        post = evaluate_trigger(
                            localization_record(localized),
                            eef,
                            trigger_artifact,
                            mode=selected_mode,
                            require_miss=False,
                        )
                        return dict(post.__dict__)

                    (
                        method_obs,
                        method_success,
                        method_t,
                        primitive_steps,
                        primitive_diagnostics,
                    ) = _run_perception_regrasp(
                        env,
                        method_obs,
                        method_tracker,
                        localizer,
                        task_description,
                        absolute_t=absolute_t,
                        max_t=args.max_timesteps,
                        writer=method_writer,
                        flip_images=cfg.flip_images,
                        min_confidence=0.0,
                        localization_validator=validator,
                        stop_after_guard=primitive == "retreat_only",
                    )
                    post_guard_pass = bool(
                        method_success
                        or primitive_diagnostics.get("perception_guard_pass", False)
                    )
                    if not post_guard_pass:
                        if method_writer is not None:
                            method_writer.close()
                            method_tmp.unlink(missing_ok=True)
                        copied = dict(baseline_row)
                        copied.update(decision)
                        copied.update(primitive_diagnostics)
                        copied.update(
                            {
                                "strategy": strategy,
                                "counterfactual_reused": True,
                                "intervention_applied": False,
                                "primitive_steps": 0,
                            }
                        )
                        new_branch_rows.append(copied)
                        continue

                    method_query_rows: list[dict[str, Any]] = []
                    method_queries = 0
                    if not method_success and method_t < args.max_timesteps:
                        (
                            method_obs,
                            method_success,
                            method_t,
                            method_queries,
                            method_query_rows,
                        ) = _continue_policy(
                            cfg,
                            model,
                            dataset_stats,
                            env,
                            method_obs,
                            method_tracker,
                            case,
                            task_description,
                            offsets,
                            strategy=strategy,
                            absolute_t=method_t,
                            query_idx=args.trigger_query_idx + 1,
                            max_t=args.max_timesteps,
                            resize_size=resize_size,
                            execution_horizon=args.continuation_horizon,
                            prediction_mode=args.prediction_mode,
                            writer=method_writer,
                        )
                    method_video = (
                        _finish_video(method_writer, method_tmp, method_final)
                        if method_writer is not None
                        else ""
                    )
                    new_branch_rows.append(
                        _outcome_row(
                            case,
                            method_tracker,
                            strategy=strategy,
                            success=method_success,
                            final_t=method_t,
                            max_t=args.max_timesteps,
                            continuation_queries=method_queries,
                            prefix_state_sha256=snapshot_hash,
                            replay_error=replay_error,
                            trigger=decision,
                            localization=localization,
                            primitive_diagnostics=primitive_diagnostics,
                            primitive_steps=primitive_steps,
                            intervention_applied=True,
                            video_path=method_video,
                        )
                    )
                    new_query_rows.extend(method_query_rows)

                branch_rows.extend(new_branch_rows)
                query_rows.extend(new_query_rows)
                _atomic_tables(output_dir, args.run_name, branch_rows, query_rows)
                completed.add(str(row.case_id))
                outcomes = ", ".join(
                    f"{item['strategy']}={int(bool(item['terminal_success']))}"
                    for item in new_branch_rows
                )
                print(
                    f"[online-regrasp] {len(completed)}/{len(manifest)} {row.case_id} "
                    f"t={absolute_t} {outcomes}",
                    flush=True,
                )
        finally:
            env.close()

    expected_branches = len(manifest) * len(expected_strategies)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_name": args.run_name,
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "cfg": asdict(cfg),
        "cases": len(manifest),
        "expected_branches": expected_branches,
        "completed_branches": len(branch_rows),
    }
    (output_dir / f"{args.run_name}__metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    completion = {
        "run_name": args.run_name,
        "completed": len(branch_rows) == expected_branches,
        "completed_cases": len(completed),
        "expected_cases": len(manifest),
        "completed_branches": len(branch_rows),
        "expected_branches": expected_branches,
    }
    (output_dir / f"{args.run_name}__completed.json").write_text(
        json.dumps(completion, indent=2), encoding="utf-8"
    )
    if not completion["completed"]:
        raise SystemExit(3)
    return pd.DataFrame(branch_rows), pd.DataFrame(query_rows)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--position-level", required=True)
    result.add_argument("--task-ids", default="")
    result.add_argument("--trigger-artifact", type=Path, required=True)
    result.add_argument(
        "--trigger-modes",
        default="workspace_calibrated,global_conservative",
        help="Comma-separated intervention strategy names.",
    )
    result.add_argument("--perception-model", type=Path, required=True)
    result.add_argument("--perception-device", default="cuda")
    result.add_argument("--uncertainty-seeds", default="0,1,2,3")
    result.add_argument("--base-seed", type=int, default=20260904)
    result.add_argument("--max-timesteps", type=int, default=280)
    result.add_argument("--trigger-query-idx", type=int, default=4)
    result.add_argument("--prefix-horizon", type=int, default=16)
    result.add_argument("--trigger-prefix-steps", type=int, default=8)
    result.add_argument("--continuation-horizon", type=int, default=8)
    result.add_argument("--num-denoising-steps-action", type=int, default=5)
    result.add_argument("--prediction-mode", choices=["parallel", "autoregressive"], default="parallel")
    result.add_argument("--num-denoising-steps-future-state", type=int, default=1)
    result.add_argument("--num-denoising-steps-value", type=int, default=1)
    result.add_argument("--num-future-state-samples", type=int, default=1)
    result.add_argument("--num-value-samples", type=int, default=1)
    result.add_argument("--replay-threshold", type=float, default=1e-9)
    result.add_argument("--video-fps", type=int, default=20)
    result.add_argument("--save-videos", action=argparse.BooleanOptionalAction, default=False)
    result.add_argument("--max-cases", type=int, default=0)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--run-name", required=True)
    result.add_argument("--resume", action="store_true")
    return result


if __name__ == "__main__":
    branches, queries = collect(parser().parse_args())
    print(f"[online-regrasp] wrote branches={len(branches)} queries={len(queries)}", flush=True)

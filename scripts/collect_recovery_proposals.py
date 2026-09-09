#!/usr/bin/env python3
"""Replay frozen hard states with deployable and diagnostic recovery proposals."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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
    get_libero_env,
    get_libero_image,
    get_libero_wrist_image,
)
from cosmos_policy.experiments.robot.libero.run_libero_eval import (
    prewarm_libero_renderer,
    validate_config,
)
from cosmos_policy.experiments.robot.libero.safety_signals import SafetySignalTracker
from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
    default_policy_config,
    parse_seed_list,
)
from cosmos_policy.experiments.robot.robot_utils import get_image_resize_size
from cosmos_policy.utils.utils import set_seed_everywhere

from collect_counterfactual_feedback import (
    _sample_candidates,
    _select_max_value,
    _terminal_outcome,
)
from libero_runtime_snapshot import restore_libero_runtime_state, runtime_snapshot_from_arrays
from perception_regrasp import (
    FrozenPatchLocalizer,
    localization_record,
    raw_agentview_image,
)
from recovery_proposal_utils import (
    cartesian_servo_action,
    continuation_seeds,
    parse_proposals,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPLAY_THRESHOLD = 1e-9


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _json_scalar(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _load_sidecar(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        return {key: np.asarray(source[key]).copy() for key in source.files}


def _frame(obs: Mapping[str, Any], *, flip_images: bool) -> np.ndarray:
    agent = np.asarray(get_libero_image(obs, flip_images=flip_images), dtype=np.uint8)
    wrist = np.asarray(get_libero_wrist_image(obs, flip_images=flip_images), dtype=np.uint8)
    if wrist.shape[:2] != agent.shape[:2]:
        return agent
    return np.concatenate([agent, wrist], axis=1)


def _step(
    env: Any,
    obs: Mapping[str, Any],
    action: Sequence[float],
    tracker: SafetySignalTracker,
    *,
    absolute_t: int,
    max_t: int,
    writer: Any | None,
    flip_images: bool,
) -> tuple[Mapping[str, Any], bool, int, bool]:
    if absolute_t >= max_t:
        return obs, bool(env.check_success()), absolute_t, False
    action_array = np.asarray(action, dtype=np.float32)
    obs, _reward, done, info = env.step(action_array.tolist())
    absolute_t += 1
    tracker.observe(obs, action_array, t=absolute_t, info=info, task_success=bool(done))
    if writer is not None:
        writer.append_data(_frame(obs, flip_images=flip_images))
    return obs, bool(done), absolute_t, True


def _execute(
    env: Any,
    obs: Mapping[str, Any],
    actions: Sequence[Sequence[float]],
    tracker: SafetySignalTracker,
    *,
    absolute_t: int,
    max_t: int,
    writer: Any | None,
    flip_images: bool,
) -> tuple[Mapping[str, Any], bool, int, int]:
    success = bool(env.check_success())
    executed = 0
    for action in actions:
        if success or absolute_t >= max_t:
            break
        obs, success, absolute_t, stepped = _step(
            env,
            obs,
            action,
            tracker,
            absolute_t=absolute_t,
            max_t=max_t,
            writer=writer,
            flip_images=flip_images,
        )
        executed += int(stepped)
    return obs, success, absolute_t, executed


def _replay_integrity(
    env: Any,
    payload: Mapping[str, np.ndarray],
    snapshot: Mapping[str, Any],
    *,
    snapshot_t: int,
    flip_images: bool,
) -> float:
    required = {
        "candidate_actions",
        "selected_max_value_idx",
        "feedback_requery_actions",
        "feedback_requery_selected_idx",
        "feedback_endpoint_state",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Sidecar lacks feedback replay arrays: {missing}")
    obs = restore_libero_runtime_state(env, snapshot)
    tracker = SafetySignalTracker(env, obs)
    selected = int(np.asarray(payload["selected_max_value_idx"]).item())
    requery_selected = int(np.asarray(payload["feedback_requery_selected_idx"]).item())
    obs, success, absolute_t, _ = _execute(
        env,
        obs,
        payload["candidate_actions"][selected, :8],
        tracker,
        absolute_t=snapshot_t,
        max_t=snapshot_t + 16,
        writer=None,
        flip_images=flip_images,
    )
    if not success:
        obs, _success, absolute_t, _ = _execute(
            env,
            obs,
            payload["feedback_requery_actions"][requery_selected, :8],
            tracker,
            absolute_t=absolute_t,
            max_t=snapshot_t + 16,
            writer=None,
            flip_images=flip_images,
        )
    actual = np.asarray(env.get_sim_state(), dtype=np.float64)
    expected = np.asarray(payload["feedback_endpoint_state"], dtype=np.float64)
    if actual.shape != expected.shape:
        raise ValueError(f"Replay state shape mismatch: {actual.shape} != {expected.shape}")
    return float(np.max(np.abs(actual - expected)))


def _target_position(tracker: SafetySignalTracker, obs: Mapping[str, Any]) -> np.ndarray:
    positions = tracker._object_positions(obs)
    for name in tracker.target_objects:
        if name in positions:
            return np.asarray(positions[name], dtype=np.float64)[:3]
    raise RuntimeError(f"No target-object position for {tracker.target_objects}")


def _eef_position(obs: Mapping[str, Any]) -> np.ndarray:
    value = np.asarray(obs.get("robot0_eef_pos", []), dtype=np.float64).reshape(-1)
    if value.size < 3 or not np.all(np.isfinite(value[:3])):
        raise RuntimeError("Observation has no finite robot0_eef_pos")
    return value[:3]


def _run_lift_hold(
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    *,
    absolute_t: int,
    max_t: int,
    writer: Any,
    flip_images: bool,
    lift_dz: float,
    primitive_steps: int,
) -> tuple[Mapping[str, Any], bool, int, int]:
    action = np.asarray([0.0, 0.0, lift_dz, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    return _execute(
        env,
        obs,
        np.repeat(action[None, :], primitive_steps, axis=0),
        tracker,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )


def _servo_stage(
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    target_fn: Any,
    *,
    gripper: float,
    steps: int,
    tolerance_m: float,
    absolute_t: int,
    max_t: int,
    writer: Any,
    flip_images: bool,
) -> tuple[Mapping[str, Any], bool, int, int]:
    executed = 0
    success = bool(env.check_success())
    for _ in range(steps):
        if success or absolute_t >= max_t:
            break
        target = np.asarray(target_fn(obs), dtype=np.float64)
        eef = _eef_position(obs)
        if np.linalg.norm(target - eef) <= tolerance_m:
            break
        action = cartesian_servo_action(eef, target, gripper=gripper)
        obs, success, absolute_t, stepped = _step(
            env,
            obs,
            action,
            tracker,
            absolute_t=absolute_t,
            max_t=max_t,
            writer=writer,
            flip_images=flip_images,
        )
        executed += int(stepped)
    return obs, success, absolute_t, executed


def _run_privileged_regrasp(
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    *,
    absolute_t: int,
    max_t: int,
    writer: Any,
    flip_images: bool,
) -> tuple[Mapping[str, Any], bool, int, int]:
    """Diagnostic scripted reset/regrasp using the simulator target pose."""
    total = 0
    success = bool(env.check_success())

    retreat_target = _eef_position(obs) + np.asarray([0.0, 0.0, 0.08])
    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: retreat_target,
        gripper=-1.0,
        steps=3,
        tolerance_m=0.015,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total

    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda current: _target_position(tracker, current) + np.asarray([0.0, 0.0, 0.08]),
        gripper=-1.0,
        steps=7,
        tolerance_m=0.018,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total

    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda current: _target_position(tracker, current) + np.asarray([0.0, 0.0, 0.012]),
        gripper=-1.0,
        steps=6,
        tolerance_m=0.012,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total

    close_actions = np.repeat(
        np.asarray([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]], dtype=np.float32),
        4,
        axis=0,
    )
    obs, success, absolute_t, executed = _execute(
        env,
        obs,
        close_actions,
        tracker,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total

    lift_target = _eef_position(obs) + np.asarray([0.0, 0.0, 0.10])
    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: lift_target,
        gripper=1.0,
        steps=5,
        tolerance_m=0.015,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    return obs, success, absolute_t, total


def _run_perception_regrasp(
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    localizer: FrozenPatchLocalizer,
    task_description: str,
    *,
    absolute_t: int,
    max_t: int,
    writer: Any,
    flip_images: bool,
    min_confidence: float,
    localization_validator: Callable[[Any, np.ndarray], Mapping[str, Any]] | None = None,
    stop_after_guard: bool = False,
) -> tuple[Mapping[str, Any], bool, int, int, dict[str, Any]]:
    """Retreat, localize the named target from RGB, and execute a Cartesian regrasp."""
    total = 0
    success = bool(env.check_success())
    diagnostics: dict[str, Any] = {
        "perception_localization_used": False,
        "perception_regrasp_executed": False,
    }

    retreat_target = _eef_position(obs) + np.asarray([0.0, 0.0, 0.08])
    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: retreat_target,
        gripper=-1.0,
        steps=3,
        tolerance_m=0.015,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total, diagnostics

    # The RGB localizer and MuJoCo camera matrices share the raw sensor orientation.
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
    diagnostics.update(localization_record(localization))
    diagnostics["perception_localization_used"] = True
    diagnostics["perception_confidence_pass"] = bool(
        localization.peak_probability >= min_confidence
    )
    if not diagnostics["perception_confidence_pass"]:
        return obs, success, absolute_t, total, diagnostics

    guard = (
        dict(localization_validator(localization, _eef_position(obs)))
        if localization_validator is not None
        else {"passed": True}
    )
    diagnostics.update({f"perception_guard_{key}": value for key, value in guard.items()})
    diagnostics["perception_guard_pass"] = bool(guard.get("passed", False))
    if not diagnostics["perception_guard_pass"]:
        return obs, success, absolute_t, total, diagnostics
    if stop_after_guard:
        return obs, success, absolute_t, total, diagnostics

    diagnostics["perception_regrasp_executed"] = True
    target_position = np.asarray(localization.world_position, dtype=np.float64)
    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: target_position + np.asarray([0.0, 0.0, 0.08]),
        gripper=-1.0,
        steps=7,
        tolerance_m=0.018,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total, diagnostics

    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: target_position + np.asarray([0.0, 0.0, 0.012]),
        gripper=-1.0,
        steps=6,
        tolerance_m=0.012,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total, diagnostics

    close_actions = np.repeat(
        np.asarray([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]], dtype=np.float32),
        4,
        axis=0,
    )
    obs, success, absolute_t, executed = _execute(
        env,
        obs,
        close_actions,
        tracker,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    if success:
        return obs, success, absolute_t, total, diagnostics

    lift_target = _eef_position(obs) + np.asarray([0.0, 0.0, 0.10])
    obs, success, absolute_t, executed = _servo_stage(
        env,
        obs,
        tracker,
        lambda _obs: lift_target,
        gripper=1.0,
        steps=5,
        tolerance_m=0.015,
        absolute_t=absolute_t,
        max_t=max_t,
        writer=writer,
        flip_images=flip_images,
    )
    total += executed
    return obs, success, absolute_t, total, diagnostics


def _atomic_tables(
    output_dir: Path,
    run_name: str,
    branch_rows: list[dict[str, Any]],
    query_rows: list[dict[str, Any]],
) -> None:
    for stem, rows in (("recovery_branches", branch_rows), ("query_metrics", query_rows)):
        frame = pd.DataFrame(rows)
        parquet = output_dir / f"{run_name}__{stem}.parquet"
        csv = output_dir / f"{run_name}__{stem}.csv"
        temporary_parquet = parquet.with_name(parquet.stem + ".tmp.parquet")
        temporary_csv = csv.with_name(csv.stem + ".tmp.csv")
        frame.to_parquet(temporary_parquet, index=False)
        frame.to_csv(temporary_csv, index=False)
        os.replace(temporary_parquet, parquet)
        os.replace(temporary_csv, csv)


def _source_columns(row: Any) -> dict[str, Any]:
    return {
        "row_uid": str(row.row_uid),
        "snapshot_id": str(row.snapshot_id),
        "source_run": str(row.source_run),
        "position_level": str(row.position_level),
        "suite": str(row.suite),
        "task_id": int(row.task_id),
        "init_state_id": int(row.init_state_id),
        "rollout_id": int(row.rollout_id),
        "rollout_seed": int(row.rollout_seed),
        "query_idx": int(row.query_idx),
        "snapshot_t": int(row.t),
        "phase_at_snapshot": str(row.phase_at_snapshot),
        "task_description": str(row.task_description),
        "independent_group": str(row.independent_group),
        "source_commit_success": _as_bool(row.commit_success),
        "source_feedback_success": _as_bool(row.feedback_success),
        "source_feedback_drop": _as_bool(row.feedback_terminal_episode_target_drop_candidate),
        "source_feedback_wrong": _as_bool(
            row.feedback_terminal_episode_wrong_object_interaction_candidate
        ),
        "source_feedback_safety": _as_bool(
            row.feedback_terminal_episode_official_safety_violation
        ),
        "source_feedback_failure_type": str(row.feedback_terminal_failure_type),
        "source_feedback_final_t": int(row.feedback_terminal_final_t),
    }


def collect(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest_path = args.manifest.expanduser().resolve()
    manifest = pd.read_parquet(manifest_path)
    manifest = manifest.loc[
        manifest["position_level"].astype(str).eq(args.position_level)
        & manifest["task_id"].astype(int).eq(args.task_id)
    ].sort_values(["independent_group", "row_uid"], kind="stable")
    if args.max_states > 0:
        manifest = manifest.head(args.max_states)
    manifest = manifest.reset_index(drop=True)
    if manifest.empty:
        raise ValueError(
            f"No frozen states for position={args.position_level} task={args.task_id}"
        )
    if manifest["commit_success"].astype(bool).any() or manifest["feedback_success"].astype(bool).any():
        raise ValueError("Recovery manifest must contain only commit+feedback failures")

    proposals = parse_proposals(args.proposals)
    uses_perception = any(proposal.primitive == "perception_regrasp" for proposal in proposals)
    if uses_perception and args.perception_model is None:
        raise ValueError("--perception-model is required for perception_regrasp_h8")
    offsets = parse_seed_list(args.uncertainty_seeds)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir / f"{args.run_name}__videos"
    if args.save_videos:
        video_dir.mkdir(parents=True, exist_ok=True)
    branch_path = output_dir / f"{args.run_name}__recovery_branches.parquet"
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
    completed = {(str(row["row_uid"]), str(row["proposal"])) for row in branch_rows}
    expected = len(manifest) * len(proposals)
    if len(completed) >= expected:
        print(f"[recovery] already complete branches={len(completed)}/{expected}", flush=True)
        return pd.DataFrame(branch_rows), pd.DataFrame(query_rows)

    cfg = default_policy_config(
        str(manifest.iloc[0]["suite"]),
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
    localizer = (
        FrozenPatchLocalizer(args.perception_model, device=args.perception_device)
        if uses_perception
        else None
    )

    suite_name = str(manifest.iloc[0]["suite"])
    task_suite = benchmark.get_benchmark_dict()[suite_name]()
    task = task_suite.get_task(args.task_id)
    env, _ = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
    task_description = str(task.language)

    try:
        for state_index, row in enumerate(manifest.itertuples(index=False)):
            sidecar = PROJECT_ROOT / str(row.sidecar_relpath)
            payload = _load_sidecar(sidecar)
            snapshot = runtime_snapshot_from_arrays(payload)
            replay_error = _replay_integrity(
                env,
                payload,
                snapshot,
                snapshot_t=int(row.t),
                flip_images=cfg.flip_images,
            )
            strict_replay = replay_error <= args.replay_threshold
            if not strict_replay and not args.allow_integrity_failures:
                raise RuntimeError(
                    f"Endpoint replay failed row={row.row_uid}: {replay_error:.3e}"
                )
            selected = int(np.asarray(payload["selected_max_value_idx"]).item())
            common_actions = np.asarray(payload["candidate_actions"][selected, :8], dtype=np.float32)

            for proposal in proposals:
                branch_key = (str(row.row_uid), proposal.name)
                if branch_key in completed:
                    continue
                obs = restore_libero_runtime_state(env, snapshot)
                tracker = SafetySignalTracker(env, obs)
                absolute_t = int(row.t)
                branch_queries: list[dict[str, Any]] = []
                safe_uid = f"state{state_index:03d}__{row.snapshot_id}__{proposal.name}"
                final_video = video_dir / f"{safe_uid}.mp4"
                temporary_video = video_dir / f"{safe_uid}.partial.mp4"
                writer = None
                if args.save_videos:
                    if temporary_video.exists():
                        temporary_video.unlink()
                    writer = imageio.get_writer(
                        temporary_video,
                        fps=args.video_fps,
                        macro_block_size=1,
                    )
                    writer.append_data(_frame(obs, flip_images=cfg.flip_images))
                branch_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    obs, success, absolute_t, prefix_steps = _execute(
                        env,
                        obs,
                        common_actions,
                        tracker,
                        absolute_t=absolute_t,
                        max_t=args.max_timesteps,
                        writer=writer,
                        flip_images=cfg.flip_images,
                    )
                    primitive_steps = 0
                    primitive_diagnostics: dict[str, Any] = {}
                    if not success and proposal.primitive == "lift_hold":
                        obs, success, absolute_t, primitive_steps = _run_lift_hold(
                            env,
                            obs,
                            tracker,
                            absolute_t=absolute_t,
                            max_t=args.max_timesteps,
                            writer=writer,
                            flip_images=cfg.flip_images,
                            lift_dz=args.lift_dz,
                            primitive_steps=args.primitive_steps,
                        )
                    elif not success and proposal.primitive == "privileged_regrasp":
                        obs, success, absolute_t, primitive_steps = _run_privileged_regrasp(
                            env,
                            obs,
                            tracker,
                            absolute_t=absolute_t,
                            max_t=args.max_timesteps,
                            writer=writer,
                            flip_images=cfg.flip_images,
                        )
                    elif not success and proposal.primitive == "perception_regrasp":
                        assert localizer is not None
                        (
                            obs,
                            success,
                            absolute_t,
                            primitive_steps,
                            primitive_diagnostics,
                        ) = _run_perception_regrasp(
                            env,
                            obs,
                            tracker,
                            localizer,
                            task_description,
                            absolute_t=absolute_t,
                            max_t=args.max_timesteps,
                            writer=writer,
                            flip_images=cfg.flip_images,
                            min_confidence=args.perception_min_confidence,
                        )

                    continuation_queries = 0
                    while not success and absolute_t < args.max_timesteps:
                        seeds = continuation_seeds(
                            int(row.rollout_seed),
                            proposal.name,
                            absolute_t,
                            offsets,
                        )
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
                        selected_idx, diagnostics = _select_max_value(
                            samples, open_loop_steps=proposal.execution_horizon
                        )
                        obs, success, absolute_t, executed = _execute(
                            env,
                            obs,
                            np.asarray(samples[selected_idx]["actions"])[
                                : proposal.execution_horizon
                            ],
                            tracker,
                            absolute_t=absolute_t,
                            max_t=args.max_timesteps,
                            writer=writer,
                            flip_images=cfg.flip_images,
                        )
                        query_record = {
                            **_source_columns(row),
                            "proposal": proposal.name,
                            "proposal_deployable": proposal.deployable,
                            "branch_query_idx": continuation_queries,
                            "query_t": query_t,
                            "query_seed_values": json.dumps(list(seeds)),
                            "executed_steps": executed,
                            "success_after_query": success,
                        }
                        query_record.update({key: _json_scalar(value) for key, value in metrics.items()})
                        query_record.update(
                            {key: _json_scalar(value) for key, value in diagnostics.items()}
                        )
                        branch_queries.append(query_record)
                        continuation_queries += 1

                    outcome = _terminal_outcome(
                        tracker,
                        success=success,
                        final_t=absolute_t,
                        max_t=args.max_timesteps,
                        continuation_queries=continuation_queries,
                    )
                finally:
                    if writer is not None:
                        writer.close()
                if writer is not None:
                    os.replace(temporary_video, final_video)

                source = _source_columns(row)
                branch_row: dict[str, Any] = {
                    **source,
                    "proposal": proposal.name,
                    "proposal_deployable": proposal.deployable,
                    "proposal_execution_horizon": proposal.execution_horizon,
                    "proposal_primitive": proposal.primitive,
                    "strict_replay": strict_replay,
                    "feedback_endpoint_replay_max_abs": replay_error,
                    "common_prefix_steps": prefix_steps,
                    "primitive_steps": primitive_steps,
                    "continuation_queries": continuation_queries,
                    "branch_executed_steps": absolute_t - int(row.t),
                    "video_num_frames": absolute_t - int(row.t) + 1 if writer is not None else 0,
                    "video_path": str(final_video.relative_to(PROJECT_ROOT)) if writer is not None else "",
                    "branch_started_at": branch_started,
                    "branch_finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    **primitive_diagnostics,
                    **outcome,
                }
                branch_rows.append(branch_row)
                query_rows.extend(branch_queries)
                completed.add(branch_key)
                _atomic_tables(output_dir, args.run_name, branch_rows, query_rows)
                print(
                    f"[recovery] branches={len(completed)}/{expected} "
                    f"cell={args.position_level}/task{args.task_id} proposal={proposal.name} "
                    f"success={success} final_t={absolute_t} replay={replay_error:.3e}",
                    flush=True,
                )
    finally:
        env.close()

    metadata = {
        "schema_version": 1,
        "run_name": args.run_name,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "cfg": asdict(cfg),
        "num_states": len(manifest),
        "num_proposals": len(proposals),
        "expected_branches": expected,
        "completed_branches": len(completed),
    }
    (output_dir / f"{args.run_name}__metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    completion = {
        "run_name": args.run_name,
        "completed": len(completed) == expected,
        "completed_branches": len(completed),
        "expected_branches": expected,
    }
    (output_dir / f"{args.run_name}__completed.json").write_text(
        json.dumps(completion, indent=2), encoding="utf-8"
    )
    if not completion["completed"]:
        raise SystemExit(3)
    return pd.DataFrame(branch_rows), pd.DataFrame(query_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--position-level", required=True)
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument(
        "--proposals",
        default="frequent_requery_h4,lift_hold_h8,privileged_regrasp_h8",
    )
    parser.add_argument("--uncertainty-seeds", default="0,1,2,3")
    parser.add_argument("--base-seed", type=int, default=20260904)
    parser.add_argument("--max-timesteps", type=int, default=280)
    parser.add_argument("--num-denoising-steps-action", type=int, default=5)
    parser.add_argument("--prediction-mode", choices=["parallel", "autoregressive"], default="parallel")
    parser.add_argument("--num-denoising-steps-future-state", type=int, default=1)
    parser.add_argument("--num-denoising-steps-value", type=int, default=1)
    parser.add_argument("--num-future-state-samples", type=int, default=1)
    parser.add_argument("--num-value-samples", type=int, default=1)
    parser.add_argument("--primitive-steps", type=int, default=4)
    parser.add_argument("--lift-dz", type=float, default=0.35)
    parser.add_argument("--replay-threshold", type=float, default=REPLAY_THRESHOLD)
    parser.add_argument("--allow-integrity-failures", action="store_true")
    parser.add_argument("--video-fps", type=int, default=20)
    parser.add_argument("--save-videos", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--perception-model", type=Path)
    parser.add_argument("--perception-device", default="cuda")
    parser.add_argument("--perception-min-confidence", type=float, default=0.0)
    parser.add_argument("--max-states", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.task_id < 0:
        raise ValueError("task-id must be non-negative")
    if args.max_timesteps <= 64:
        raise ValueError("max-timesteps must be greater than the frozen snapshot time")
    if not 0.0 < args.lift_dz <= 1.0:
        raise ValueError("lift-dz must be in (0, 1]")
    branches, queries = collect(args)
    print(f"[recovery] wrote branches={len(branches)} query_rows={len(queries)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

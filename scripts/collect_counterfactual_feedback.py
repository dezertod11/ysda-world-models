#!/usr/bin/env python3
"""Collect exact-state candidate branches and counterfactual feedback pairs.

The collector follows a normal max-value Cosmos Policy rollout. At selected
decision states it freezes the MuJoCo state and evaluates all sampled action
chunks from that exact snapshot. The max-value candidate additionally gets a
matched feedback branch: execute eight actions, observe the real state, query
again, and execute eight actions from the revised chunk.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from libero.libero import benchmark

from cosmos_policy.experiments.robot.cosmos_utils import (
    get_model,
    init_t5_text_embeddings_cache,
    load_dataset_stats,
)
from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
    get_libero_image,
    get_libero_task_description,
    get_libero_wrist_image,
)
from cosmos_policy.experiments.robot.libero.run_libero_eval import (
    get_task_max_steps,
    prepare_observation,
    prewarm_libero_renderer,
    validate_config,
)
from cosmos_policy.experiments.robot.libero.safety_signals import SafetySignalTracker
from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
    default_policy_config,
    get_task_init_states_compat,
    object_state_delta_metrics,
    parse_int_list,
    parse_seed_list,
    prediction_error_metrics_for_query,
    proprio_from_libero_obs,
    select_planning_sample,
)
from cosmos_policy.experiments.robot.libero.uncertainty_metrics import (
    extract_future_proprio_from_sample,
    latent_internal_consistency,
    sample_action_ensemble,
)
from cosmos_policy.experiments.robot.robot_utils import get_image_resize_size
from cosmos_policy.utils.utils import set_seed_everywhere

from counterfactual_feedback_utils import (
    PHASES,
    local_branch_utility,
    prefixed,
    should_run_terminal_continuation,
    terminal_branch_utility,
    value_of_feedback,
)
from libero_runtime_snapshot import (
    capture_libero_runtime_state,
    restore_libero_runtime_state,
    runtime_snapshot_arrays,
)


def _to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    return np.asarray(value)


def _copy_observation(obs: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in obs.items():
        result[key] = value.copy() if hasattr(value, "copy") else value
    return result


def _stack_optional(values: Sequence[Any], *, dtype: Any = np.float32) -> np.ndarray:
    arrays = []
    for value in values:
        if value is None:
            return np.empty((0,), dtype=dtype)
        array = _to_numpy(value).astype(dtype, copy=False)
        if array.ndim > 0 and array.shape[0] == 1:
            array = array[0]
        arrays.append(array)
    if not arrays or len({array.shape for array in arrays}) != 1:
        return np.empty((0,), dtype=dtype)
    return np.stack(arrays)


def _snapshot_key(
    suite: str,
    task_id: int,
    init_state_id: int,
    rollout_id: int,
    query_idx: int,
) -> tuple[str, int, int, int, int]:
    return suite, task_id, init_state_id, rollout_id, query_idx


def _snapshot_id(key: Sequence[Any]) -> str:
    suite, task_id, init_state_id, rollout_id, query_idx = key
    return (
        f"{suite}__task{int(task_id)}__init{int(init_state_id)}"
        f"__rollout{int(rollout_id)}__query{int(query_idx)}"
    )


def _restore_snapshot(env: Any, state: Mapping[str, Any]) -> Mapping[str, Any]:
    return restore_libero_runtime_state(env, state)


def _infer_phase(tracker: SafetySignalTracker) -> str:
    if not tracker.records:
        return "approach"
    latest = tracker.records[-1]
    progress = float(latest.get("goal_progress", np.nan))
    if tracker.successful_release_event_t or (
        np.isfinite(progress)
        and np.isfinite(tracker.initial_goal_progress)
        and progress > tracker.initial_goal_progress
    ):
        return "release"
    distance = float(latest.get("target_eef_distance_min", np.nan))
    if any(tracker.target_was_lifted.values()):
        if np.isfinite(distance) and distance >= tracker.thresholds.released_distance_m:
            return "release"
        return "transport"
    if float(latest.get("robot_target_contact_count", 0.0)) > 0 or (
        np.isfinite(distance) and distance <= 0.08
    ):
        return "grasp"
    return "approach"


def _execute_actions(
    env: Any,
    obs: Mapping[str, Any],
    actions: Iterable[Any],
    tracker: SafetySignalTracker,
    *,
    absolute_t: int,
    max_t: int,
) -> tuple[Mapping[str, Any], bool, int, int]:
    success = False
    executed = 0
    for action in actions:
        if absolute_t >= max_t:
            break
        action_array = np.asarray(action, dtype=np.float32)
        obs, _reward, done, info = env.step(action_array.tolist())
        absolute_t += 1
        executed += 1
        tracker.observe(obs, action_array, t=absolute_t, info=info, task_success=bool(done))
        if done:
            success = True
            break
    return obs, success, absolute_t, executed


def _local_outcome(
    tracker: SafetySignalTracker,
    marker: int,
    obs_start: Mapping[str, Any],
    obs_end: Mapping[str, Any],
    *,
    success: bool,
    executed_steps: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "local_success": bool(success),
        "local_executed_steps": int(executed_steps),
    }
    result.update(tracker.query_summary(marker))
    result.update(object_state_delta_metrics(dict(obs_start), dict(obs_end)))
    result["local_utility_v1"] = local_branch_utility(result)
    return result


def _terminal_outcome(
    tracker: SafetySignalTracker,
    *,
    success: bool,
    final_t: int,
    max_t: int,
    continuation_queries: int,
) -> dict[str, Any]:
    summary = tracker.episode_summary(success=success, final_t=final_t, max_steps=max_t)
    result = {
        "terminal_available": True,
        "terminal_success": bool(success),
        "terminal_final_t": int(final_t),
        "terminal_continuation_queries": int(continuation_queries),
        "terminal_goal_progress_max": float(summary["episode_goal_progress_max"]),
        "terminal_target_drop_candidate": bool(summary["target_drop_candidate"]),
        "terminal_wrong_object_interaction_candidate": bool(
            summary["wrong_object_interaction_candidate"]
        ),
        "terminal_official_safety_violation": bool(summary["official_safety_violation"]),
        "terminal_failure_type": str(summary["failure_type"]),
    }
    result.update(prefixed(summary, "terminal_episode_"))
    result["terminal_utility_v1"] = terminal_branch_utility(result)
    return result


def _sample_candidates(
    cfg: Any,
    model: Any,
    dataset_stats: Mapping[str, Any],
    obs: Mapping[str, Any],
    task_description: str,
    seeds: Sequence[int],
    resize_size: int,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    observation = prepare_observation(obs, resize_size, cfg.flip_images)
    return sample_action_ensemble(
        cfg,
        model,
        dict(dataset_stats),
        observation,
        task_description,
        seeds=seeds,
        num_denoising_steps_action=cfg.num_denoising_steps_action,
        prediction_mode=(
            "autoregressive" if cfg.ar_future_prediction or cfg.ar_value_prediction else "parallel"
        ),
        num_denoising_steps_future_state=cfg.num_denoising_steps_future_state,
        num_denoising_steps_value=cfg.num_denoising_steps_value,
        num_future_state_samples=cfg.num_future_state_predictions_in_ensemble,
        num_value_samples=cfg.num_value_predictions_in_ensemble,
    )


def _select_max_value(samples: Sequence[Mapping[str, Any]], *, open_loop_steps: int) -> tuple[int, dict[str, Any]]:
    return select_planning_sample(
        samples,
        strategy="max_value",
        risk_lambda=0.0,
        open_loop_steps=open_loop_steps,
        short_open_loop_steps=min(8, open_loop_steps),
    )


def _continue_to_terminal(
    cfg: Any,
    model: Any,
    dataset_stats: Mapping[str, Any],
    env: Any,
    obs: Mapping[str, Any],
    tracker: SafetySignalTracker,
    task_description: str,
    uncertainty_seed_offsets: Sequence[int],
    *,
    rollout_seed: int,
    absolute_t: int,
    max_t: int,
    resize_size: int,
) -> tuple[Mapping[str, Any], bool, int, int]:
    success = bool(env.check_success())
    continuation_queries = 0
    while not success and absolute_t < max_t:
        seeds = tuple(
            int(rollout_seed + 10_000_000 + absolute_t * 1000 + offset)
            for offset in uncertainty_seed_offsets
        )
        samples, _metrics = _sample_candidates(
            cfg,
            model,
            dataset_stats,
            obs,
            task_description,
            seeds,
            resize_size,
        )
        selected_idx, _diagnostics = _select_max_value(
            samples, open_loop_steps=cfg.num_open_loop_steps
        )
        obs, success, absolute_t, _executed = _execute_actions(
            env,
            obs,
            samples[selected_idx]["actions"][: cfg.num_open_loop_steps],
            tracker,
            absolute_t=absolute_t,
            max_t=max_t,
        )
        continuation_queries += 1
    return obs, success, absolute_t, continuation_queries


def _run_candidate_branch(
    cfg: Any,
    model: Any,
    dataset_stats: Mapping[str, Any],
    env: Any,
    snapshot_state: Mapping[str, Any],
    sample: Mapping[str, Any],
    task_description: str,
    uncertainty_seed_offsets: Sequence[int],
    *,
    rollout_seed: int,
    snapshot_t: int,
    max_t: int,
    resize_size: int,
    terminal_continuation: bool,
) -> tuple[dict[str, Any], Mapping[str, Any], np.ndarray]:
    obs_start = _restore_snapshot(env, snapshot_state)
    tracker = SafetySignalTracker(env, obs_start)
    marker = tracker.mark_query_start()
    obs_end, success, absolute_t, executed = _execute_actions(
        env,
        obs_start,
        sample["actions"][: cfg.num_open_loop_steps],
        tracker,
        absolute_t=snapshot_t,
        max_t=min(max_t, snapshot_t + cfg.num_open_loop_steps),
    )
    endpoint_state = np.asarray(env.get_sim_state(), dtype=np.float64).copy()
    endpoint_obs = _copy_observation(obs_end)
    outcome = _local_outcome(
        tracker,
        marker,
        obs_start,
        obs_end,
        success=success,
        executed_steps=executed,
    )
    outcome.update(
        prediction_error_metrics_for_query(
            dict(sample),
            dict(obs_start),
            dict(obs_end),
            dict(dataset_stats),
            cfg.flip_images,
            chunk_success=success,
        )
    )
    if terminal_continuation:
        obs_end, success, absolute_t, continuation_queries = _continue_to_terminal(
            cfg,
            model,
            dataset_stats,
            env,
            obs_end,
            tracker,
            task_description,
            uncertainty_seed_offsets,
            rollout_seed=rollout_seed,
            absolute_t=absolute_t,
            max_t=max_t,
            resize_size=resize_size,
        )
        outcome.update(
            _terminal_outcome(
                tracker,
                success=success,
                final_t=absolute_t,
                max_t=max_t,
                continuation_queries=continuation_queries,
            )
        )
    else:
        outcome["terminal_available"] = False
    return outcome, endpoint_obs, endpoint_state


def _run_feedback_branch(
    cfg: Any,
    model: Any,
    dataset_stats: Mapping[str, Any],
    env: Any,
    snapshot_state: Mapping[str, Any],
    selected_sample: Mapping[str, Any],
    task_description: str,
    uncertainty_seed_offsets: Sequence[int],
    *,
    rollout_seed: int,
    query_idx: int,
    snapshot_t: int,
    max_t: int,
    resize_size: int,
    feedback_steps: int,
    terminal_continuation: bool,
) -> tuple[dict[str, Any], Mapping[str, Any], np.ndarray, dict[str, Any]]:
    obs_start = _restore_snapshot(env, snapshot_state)
    tracker = SafetySignalTracker(env, obs_start)
    marker = tracker.mark_query_start()
    obs_mid, success, absolute_t, first_steps = _execute_actions(
        env,
        obs_start,
        selected_sample["actions"][:feedback_steps],
        tracker,
        absolute_t=snapshot_t,
        max_t=min(max_t, snapshot_t + feedback_steps),
    )

    requery_payload: dict[str, Any] = {
        "performed": False,
        "samples": [],
        "metrics": {},
        "diagnostics": {},
        "seeds": (),
        "selected_idx": -1,
    }
    second_steps = 0
    if not success and absolute_t < max_t:
        seeds = tuple(
            int(rollout_seed + 5_000_000 + query_idx * 1000 + offset)
            for offset in uncertainty_seed_offsets
        )
        samples, metrics = _sample_candidates(
            cfg,
            model,
            dataset_stats,
            obs_mid,
            task_description,
            seeds,
            resize_size,
        )
        selected_idx, diagnostics = _select_max_value(
            samples, open_loop_steps=cfg.num_open_loop_steps
        )
        remaining = max(0, cfg.num_open_loop_steps - first_steps)
        obs_mid, success, absolute_t, second_steps = _execute_actions(
            env,
            obs_mid,
            samples[selected_idx]["actions"][:remaining],
            tracker,
            absolute_t=absolute_t,
            max_t=min(max_t, snapshot_t + cfg.num_open_loop_steps),
        )
        requery_payload = {
            "performed": True,
            "samples": samples,
            "metrics": metrics,
            "diagnostics": diagnostics,
            "seeds": seeds,
            "selected_idx": selected_idx,
        }

    endpoint_state = np.asarray(env.get_sim_state(), dtype=np.float64).copy()
    endpoint_obs = _copy_observation(obs_mid)
    outcome = _local_outcome(
        tracker,
        marker,
        obs_start,
        obs_mid,
        success=success,
        executed_steps=first_steps + second_steps,
    )
    outcome["feedback_requery_performed"] = bool(requery_payload["performed"])
    if terminal_continuation:
        obs_mid, success, absolute_t, continuation_queries = _continue_to_terminal(
            cfg,
            model,
            dataset_stats,
            env,
            obs_mid,
            tracker,
            task_description,
            uncertainty_seed_offsets,
            rollout_seed=rollout_seed,
            absolute_t=absolute_t,
            max_t=max_t,
            resize_size=resize_size,
        )
        outcome.update(
            _terminal_outcome(
                tracker,
                success=success,
                final_t=absolute_t,
                max_t=max_t,
                continuation_queries=continuation_queries,
            )
        )
    else:
        outcome["terminal_available"] = False
    return outcome, endpoint_obs, endpoint_state, requery_payload


def _candidate_features(sample: Mapping[str, Any], candidate_idx: int) -> dict[str, Any]:
    actions = np.asarray(sample["actions"], dtype=np.float32)
    result: dict[str, Any] = {
        "candidate_idx": int(candidate_idx),
        "candidate_value": float(sample.get("value_prediction", np.nan)),
        "candidate_first_action_l1": float(np.abs(actions[0]).mean()),
        "candidate_action_chunk_l1": float(np.abs(actions).mean()),
        "candidate_action_chunk_l2": float(np.sqrt(np.mean(actions**2))),
    }
    result.update(latent_internal_consistency(dict(sample)))
    return result


def _sidecar_payload(
    cfg: Any,
    snapshot_state: Mapping[str, Any],
    obs: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    seeds: Sequence[int],
    selected_idx: int,
    candidate_endpoint_states: Sequence[np.ndarray],
    candidate_endpoint_obs: Sequence[Mapping[str, Any]],
    feedback_endpoint_state: np.ndarray,
    feedback_endpoint_obs: Mapping[str, Any],
    requery: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    future_images = [
        sample.get("future_image_predictions", {}).get("future_image") for sample in samples
    ]
    future_wrists = [
        sample.get("future_image_predictions", {}).get("future_wrist_image") for sample in samples
    ]
    future_proprio = [extract_future_proprio_from_sample(dict(sample)) for sample in samples]
    payload = {
        "current_agentview": np.asarray(
            get_libero_image(obs, flip_images=cfg.flip_images), dtype=np.uint8
        ),
        "current_wrist": np.asarray(
            get_libero_wrist_image(obs, flip_images=cfg.flip_images), dtype=np.uint8
        ),
        "current_proprio": np.asarray(proprio_from_libero_obs(dict(obs)), dtype=np.float32),
        "candidate_actions": np.stack(
            [np.asarray(sample["actions"], dtype=np.float32) for sample in samples]
        ),
        "candidate_values": np.asarray(
            [sample.get("value_prediction", np.nan) for sample in samples], dtype=np.float32
        ),
        "candidate_seeds": np.asarray(seeds, dtype=np.int64),
        "selected_max_value_idx": np.asarray(selected_idx, dtype=np.int64),
        "candidate_endpoint_states": np.stack(candidate_endpoint_states),
        "candidate_endpoint_agentview": np.stack(
            [
                np.asarray(get_libero_image(value, flip_images=cfg.flip_images), dtype=np.uint8)
                for value in candidate_endpoint_obs
            ]
        ),
        "candidate_endpoint_wrist": np.stack(
            [
                np.asarray(get_libero_wrist_image(value, flip_images=cfg.flip_images), dtype=np.uint8)
                for value in candidate_endpoint_obs
            ]
        ),
        "candidate_endpoint_proprio": np.stack(
            [np.asarray(proprio_from_libero_obs(dict(value)), dtype=np.float32) for value in candidate_endpoint_obs]
        ),
        "feedback_endpoint_state": np.asarray(feedback_endpoint_state, dtype=np.float64),
        "feedback_endpoint_agentview": np.asarray(
            get_libero_image(feedback_endpoint_obs, flip_images=cfg.flip_images), dtype=np.uint8
        ),
        "feedback_endpoint_wrist": np.asarray(
            get_libero_wrist_image(feedback_endpoint_obs, flip_images=cfg.flip_images), dtype=np.uint8
        ),
        "feedback_endpoint_proprio": np.asarray(
            proprio_from_libero_obs(dict(feedback_endpoint_obs)), dtype=np.float32
        ),
    }
    payload.update(runtime_snapshot_arrays(snapshot_state))
    for key, value in (
        ("candidate_predicted_future_images", _stack_optional(future_images, dtype=np.uint8)),
        ("candidate_predicted_future_wrists", _stack_optional(future_wrists, dtype=np.uint8)),
        ("candidate_predicted_future_proprio", _stack_optional(future_proprio)),
    ):
        if value.size:
            payload[key] = value

    requery_samples = list(requery.get("samples", []))
    if requery_samples:
        payload["feedback_requery_actions"] = np.stack(
            [np.asarray(sample["actions"], dtype=np.float32) for sample in requery_samples]
        )
        payload["feedback_requery_values"] = np.asarray(
            [sample.get("value_prediction", np.nan) for sample in requery_samples], dtype=np.float32
        )
        payload["feedback_requery_seeds"] = np.asarray(requery.get("seeds", ()), dtype=np.int64)
        payload["feedback_requery_selected_idx"] = np.asarray(
            requery.get("selected_idx", -1), dtype=np.int64
        )
    return payload


def _write_tables(
    output_dir: Path,
    run_name: str,
    feedback_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
) -> None:
    feedback = pd.DataFrame(feedback_rows)
    candidates = pd.DataFrame(candidate_rows)
    feedback.to_parquet(output_dir / f"{run_name}__feedback_pairs.parquet", index=False)
    feedback.to_csv(output_dir / f"{run_name}__feedback_pairs.csv", index=False)
    candidates.to_parquet(output_dir / f"{run_name}__candidate_outcomes.parquet", index=False)
    candidates.to_csv(output_dir / f"{run_name}__candidate_outcomes.csv", index=False)


def collect(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sidecar_dir = output_dir / f"{args.run_name}__snapshots"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    feedback_path = output_dir / f"{args.run_name}__feedback_pairs.parquet"
    candidate_path = output_dir / f"{args.run_name}__candidate_outcomes.parquet"
    feedback_rows = (
        pd.read_parquet(feedback_path).to_dict(orient="records")
        if args.resume and feedback_path.exists()
        else []
    )
    candidate_rows = (
        pd.read_parquet(candidate_path).to_dict(orient="records")
        if args.resume and candidate_path.exists()
        else []
    )
    existing_keys = {
        _snapshot_key(
            str(row["suite"]),
            int(row["task_id"]),
            int(row["init_state_id"]),
            int(row["rollout_id"]),
            int(row["query_idx"]),
        )
        for row in feedback_rows
    }
    phase_counts = {phase: 0 for phase in PHASES}
    for row in feedback_rows:
        phase = str(row.get("phase_at_snapshot", "approach"))
        if phase in phase_counts:
            phase_counts[phase] += 1
    phase_cap = int(np.ceil(args.target_decision_states * args.phase_cap_fraction))

    suites = [item.strip() for item in args.suites.split(",") if item.strip()]
    task_ids = parse_int_list(args.task_ids)
    init_state_ids = parse_int_list(args.init_state_ids)
    uncertainty_seed_offsets = parse_seed_list(args.uncertainty_seeds)
    if not suites:
        raise ValueError("at least one suite is required")
    if len(existing_keys) >= args.target_decision_states:
        print(f"[vof] already complete: {len(existing_keys)} snapshots")
        return pd.DataFrame(feedback_rows), pd.DataFrame(candidate_rows)

    cfg = default_policy_config(
        suites[0],
        seed=args.base_seed,
        num_open_loop_steps=args.open_loop_steps,
        num_denoising_steps_action=args.num_denoising_steps_action,
        prediction_mode=args.prediction_mode,
        num_denoising_steps_future_state=args.num_denoising_steps_future_state,
        num_denoising_steps_value=args.num_denoising_steps_value,
        num_future_state_samples=args.num_future_state_samples,
        num_value_samples=args.num_value_samples,
        value_ensemble_aggregation_scheme=args.value_ensemble_aggregation,
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

    episode_counter = 0
    stop = False
    for suite_name in suites:
        if stop:
            break
        cfg.task_suite_name = suite_name
        task_suite = benchmark.get_benchmark_dict()[suite_name]()
        selected_tasks = task_ids or list(range(task_suite.get_num_tasks()))
        for task_id in selected_tasks:
            if stop:
                break
            task = task_suite.get_task(task_id)
            init_states = get_task_init_states_compat(task_suite, task_id, task)
            selected_inits = init_state_ids or list(range(len(init_states)))
            main_env, _ = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
            branch_env, _ = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
            try:
                for init_state_id in selected_inits:
                    if init_state_id >= len(init_states):
                        continue
                    for rollout_id in range(args.rollouts_per_init):
                        if len(existing_keys) >= args.target_decision_states:
                            stop = True
                            break
                        rollout_seed = args.base_seed + episode_counter * args.rollout_seed_step
                        episode_counter += 1
                        main_env.reset()
                        obs = main_env.set_init_state(init_states[init_state_id])
                        for _ in range(10):
                            obs, _reward, done, _info = main_env.step(
                                get_libero_dummy_action(cfg.model_family)
                            )
                            if done:
                                break
                        main_tracker = SafetySignalTracker(main_env, obs)
                        try:
                            max_t = args.max_timesteps or get_task_max_steps(suite_name)
                        except KeyError:
                            max_t = args.max_timesteps or 520
                        t = 0
                        query_idx = 0
                        success = False
                        phases_seen_in_episode: set[str] = set()

                        while not success and t < max_t:
                            seeds = tuple(
                                int(rollout_seed + query_idx * 1000 + offset)
                                for offset in uncertainty_seed_offsets
                            )
                            samples, query_metrics = _sample_candidates(
                                cfg,
                                model,
                                dataset_stats,
                                obs,
                                get_libero_task_description(task, main_env),
                                seeds,
                                resize_size,
                            )
                            selected_idx, planning_diagnostics = _select_max_value(
                                samples, open_loop_steps=cfg.num_open_loop_steps
                            )
                            phase = _infer_phase(main_tracker)
                            key = _snapshot_key(
                                suite_name,
                                task_id,
                                init_state_id,
                                rollout_id,
                                query_idx,
                            )
                            needs_phase = phase_counts.get(phase, 0) < phase_cap
                            collect_snapshot = (
                                key not in existing_keys
                                and phase not in phases_seen_in_episode
                                and needs_phase
                                and len(existing_keys) < args.target_decision_states
                            )
                            branch_bundle: dict[str, Any] | None = None
                            if collect_snapshot:
                                snapshot_state = capture_libero_runtime_state(main_env)
                                snapshot_name = _snapshot_id(key)
                                terminal_continuation = should_run_terminal_continuation(
                                    args.terminal_continuation_fraction,
                                    args.run_name,
                                    *key,
                                )
                                common = {
                                    "snapshot_id": snapshot_name,
                                    "suite": suite_name,
                                    "task_id": int(task_id),
                                    "init_state_id": int(init_state_id),
                                    "rollout_id": int(rollout_id),
                                    "rollout_seed": int(rollout_seed),
                                    "query_idx": int(query_idx),
                                    "t": int(t),
                                    "phase_at_snapshot": phase,
                                    "task_description": get_libero_task_description(task, main_env),
                                    "num_candidates": int(len(samples)),
                                    "open_loop_steps": int(cfg.num_open_loop_steps),
                                    "feedback_steps": int(args.feedback_steps),
                                    "terminal_continuation": bool(terminal_continuation),
                                    "experiment_split": args.experiment_split,
                                    "case_id": args.case_id,
                                }
                                query_features = {**query_metrics, **planning_diagnostics}
                                candidate_bundle = []
                                endpoint_states = []
                                endpoint_obs = []
                                for candidate_idx, sample in enumerate(samples):
                                    outcome, candidate_obs, endpoint_state = _run_candidate_branch(
                                        cfg,
                                        model,
                                        dataset_stats,
                                        branch_env,
                                        snapshot_state,
                                        sample,
                                        common["task_description"],
                                        uncertainty_seed_offsets,
                                        rollout_seed=rollout_seed,
                                        snapshot_t=t,
                                        max_t=max_t,
                                        resize_size=resize_size,
                                        terminal_continuation=terminal_continuation,
                                    )
                                    row = {
                                        **common,
                                        **query_features,
                                        **_candidate_features(sample, candidate_idx),
                                        **outcome,
                                        "candidate_seed": int(seeds[candidate_idx]),
                                        "candidate_is_max_value": bool(candidate_idx == selected_idx),
                                    }
                                    candidate_bundle.append(row)
                                    endpoint_states.append(endpoint_state)
                                    endpoint_obs.append(candidate_obs)

                                feedback_outcome, feedback_obs, feedback_state, requery = _run_feedback_branch(
                                    cfg,
                                    model,
                                    dataset_stats,
                                    branch_env,
                                    snapshot_state,
                                    samples[selected_idx],
                                    common["task_description"],
                                    uncertainty_seed_offsets,
                                    rollout_seed=rollout_seed,
                                    query_idx=query_idx,
                                    snapshot_t=t,
                                    max_t=max_t,
                                    resize_size=resize_size,
                                    feedback_steps=args.feedback_steps,
                                    terminal_continuation=terminal_continuation,
                                )
                                open_outcome = candidate_bundle[selected_idx]
                                feedback_row = {
                                    **common,
                                    **query_features,
                                    "selected_candidate_idx": int(selected_idx),
                                    "selected_candidate_seed": int(seeds[selected_idx]),
                                    **prefixed(
                                        {
                                            key_name: value
                                            for key_name, value in open_outcome.items()
                                            if key_name not in common and key_name not in query_features
                                        },
                                        "open_",
                                    ),
                                    **prefixed(feedback_outcome, "feedback_"),
                                    **prefixed(dict(requery.get("metrics", {})), "feedback_query_"),
                                    **prefixed(dict(requery.get("diagnostics", {})), "feedback_query_"),
                                    "query_cost": float(args.query_cost),
                                    "local_vof": value_of_feedback(
                                        open_outcome,
                                        feedback_outcome,
                                        query_cost=args.query_cost,
                                    ),
                                }
                                if terminal_continuation:
                                    feedback_row["terminal_vof"] = value_of_feedback(
                                        open_outcome,
                                        feedback_outcome,
                                        query_cost=args.query_cost,
                                        terminal=True,
                                    )
                                else:
                                    feedback_row["terminal_vof"] = np.nan

                                sidecar_path = sidecar_dir / f"{snapshot_name}.npz"
                                payload = _sidecar_payload(
                                    cfg,
                                    snapshot_state,
                                    obs,
                                    samples,
                                    seeds,
                                    selected_idx,
                                    endpoint_states,
                                    endpoint_obs,
                                    feedback_state,
                                    feedback_obs,
                                    requery,
                                )
                                np.savez_compressed(sidecar_path, **payload)
                                feedback_row["sidecar_path"] = str(sidecar_path)
                                for row in candidate_bundle:
                                    row["sidecar_path"] = str(sidecar_path)
                                branch_bundle = {
                                    "feedback": feedback_row,
                                    "candidates": candidate_bundle,
                                    "open_endpoint_state": endpoint_states[selected_idx],
                                }

                            marker = main_tracker.mark_query_start()
                            obs, success, t_after, _executed = _execute_actions(
                                main_env,
                                obs,
                                samples[selected_idx]["actions"][: cfg.num_open_loop_steps],
                                main_tracker,
                                absolute_t=t,
                                max_t=max_t,
                            )
                            t = t_after
                            if branch_bundle is not None:
                                replay_state = np.asarray(main_env.get_sim_state(), dtype=np.float64)
                                expected_state = np.asarray(branch_bundle["open_endpoint_state"], dtype=np.float64)
                                replay_error = float(np.max(np.abs(replay_state - expected_state)))
                                branch_bundle["feedback"]["main_open_replay_state_max_abs"] = replay_error
                                for row in branch_bundle["candidates"]:
                                    row["main_open_replay_state_max_abs"] = (
                                        replay_error if row["candidate_is_max_value"] else np.nan
                                    )
                                feedback_rows.append(branch_bundle["feedback"])
                                candidate_rows.extend(branch_bundle["candidates"])
                                existing_keys.add(key)
                                phase_counts[phase] += 1
                                phases_seen_in_episode.add(phase)
                                _write_tables(output_dir, args.run_name, feedback_rows, candidate_rows)
                                print(
                                    f"[vof] snapshots={len(existing_keys)}/{args.target_decision_states} "
                                    f"phase={phase} key={_snapshot_id(key)} replay_max_abs={replay_error:.3e}"
                                )
                            query_idx += 1
            finally:
                main_env.close()
                branch_env.close()

    metadata = {
        "run_name": args.run_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "arguments": vars(args),
        "phase_counts": phase_counts,
        "phase_cap": phase_cap,
        "num_snapshots": len(existing_keys),
        "num_candidate_rows": len(candidate_rows),
        "schema": {
            "feedback_pairs": f"{args.run_name}__feedback_pairs.parquet",
            "candidate_outcomes": f"{args.run_name}__candidate_outcomes.parquet",
            "snapshot_sidecars": f"{args.run_name}__snapshots/*.npz",
        },
        "cfg": asdict(cfg),
    }
    (output_dir / f"{args.run_name}__metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    completed = len(existing_keys) >= args.target_decision_states
    (output_dir / f"{args.run_name}__completed.json").write_text(
        json.dumps(
            {
                "run_name": args.run_name,
                "completed": completed,
                "num_snapshots": len(existing_keys),
                "target_decision_states": args.target_decision_states,
                "phase_counts": phase_counts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return pd.DataFrame(feedback_rows), pd.DataFrame(candidate_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suites", required=True)
    parser.add_argument("--task-ids", default="all")
    parser.add_argument("--init-state-ids", default="all")
    parser.add_argument("--rollouts-per-init", type=int, default=2)
    parser.add_argument("--base-seed", type=int, default=2_600_000)
    parser.add_argument("--rollout-seed-step", type=int, default=97)
    parser.add_argument("--uncertainty-seeds", default="0,1,2,3")
    parser.add_argument("--max-timesteps", type=int, default=280)
    parser.add_argument("--target-decision-states", type=int, default=100)
    parser.add_argument(
        "--phase-cap-fraction",
        type=float,
        default=0.4,
        help="Maximum fraction of collected states assigned to one phase proxy",
    )
    parser.add_argument("--open-loop-steps", type=int, default=16)
    parser.add_argument("--feedback-steps", type=int, default=8)
    parser.add_argument("--terminal-continuation-fraction", type=float, default=0.2)
    parser.add_argument("--query-cost", type=float, default=0.0)
    parser.add_argument("--num-denoising-steps-action", type=int, default=5)
    parser.add_argument("--prediction-mode", choices=["parallel", "autoregressive"], default="parallel")
    parser.add_argument("--num-denoising-steps-future-state", type=int, default=1)
    parser.add_argument("--num-denoising-steps-value", type=int, default=1)
    parser.add_argument("--num-future-state-samples", type=int, default=1)
    parser.add_argument("--num-value-samples", type=int, default=1)
    parser.add_argument(
        "--value-ensemble-aggregation",
        choices=["average", "lcb", "success_vote", "majority_mean"],
        default="average",
    )
    parser.add_argument("--experiment-split", default="screen")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--output-dir", default="experiments/counterfactual_feedback")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.run_name:
        args.run_name = datetime.now().strftime("counterfactual_feedback_%Y%m%d_%H%M%S")
    if args.open_loop_steps != 16 or args.feedback_steps != 8:
        raise ValueError("frozen pilot requires open_loop_steps=16 and feedback_steps=8")
    if args.target_decision_states < 1:
        raise ValueError("target_decision_states must be positive")
    if not 0.25 <= args.phase_cap_fraction <= 1.0:
        raise ValueError("phase_cap_fraction must be in [0.25, 1]")
    feedback, candidates = collect(args)
    print(f"[vof] wrote {len(feedback)} feedback pairs and {len(candidates)} candidate outcomes")
    if len(feedback) < args.target_decision_states:
        print(
            f"[vof] incomplete phase-balanced target: "
            f"{len(feedback)}/{args.target_decision_states} snapshots"
        )
        raise SystemExit(3)


if __name__ == "__main__":
    main()

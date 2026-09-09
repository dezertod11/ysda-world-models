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
    get_future_state_prediction,
    get_model,
    get_value_prediction,
    init_t5_text_embeddings_cache,
    load_dataset_stats,
)
from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
    get_libero_image,
    get_libero_wrist_image,
)
from cosmos_policy.experiments.robot.libero.run_libero_eval import (
    get_task_max_steps,
    prepare_observation,
    prewarm_libero_renderer,
    validate_config,
)
from cosmos_policy.experiments.robot.libero.safety_signals import SafetySignalTracker
from cosmos_policy.experiments.robot.libero.terminal_grounded_critic import (
    terminal_candidate_feature_rows,
)
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
    snapshot_is_scheduled,
    should_run_terminal_continuation,
    should_continue_candidate_to_terminal,
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
    *,
    prediction_mode: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    observation = prepare_observation(obs, resize_size, cfg.flip_images)
    resolved_prediction_mode = prediction_mode or (
        "autoregressive" if cfg.ar_future_prediction or cfg.ar_value_prediction else "parallel"
    )
    sampling_mode = "parallel" if resolved_prediction_mode == "dual" else resolved_prediction_mode
    samples, metrics = sample_action_ensemble(
        cfg,
        model,
        dict(dataset_stats),
        observation,
        task_description,
        seeds=seeds,
        num_denoising_steps_action=cfg.num_denoising_steps_action,
        prediction_mode=sampling_mode,
        num_denoising_steps_future_state=cfg.num_denoising_steps_future_state,
        num_denoising_steps_value=cfg.num_denoising_steps_value,
        num_future_state_samples=cfg.num_future_state_predictions_in_ensemble,
        num_value_samples=cfg.num_value_predictions_in_ensemble,
    )
    if resolved_prediction_mode != "dual":
        return samples, metrics

    autoregressive_values = []
    for sample, seed in zip(samples, seeds):
        indices = sample["latent_indices"]
        future = get_future_state_prediction(
            cfg,
            model=model,
            data_batch=sample["data_batch"],
            generated_latent_with_action=sample["generated_latent"],
            orig_clean_latent_frames=sample["orig_clean_latent_frames"],
            future_proprio_latent_idx=indices["future_proprio_latent_idx"],
            future_wrist_image_latent_idx=indices["future_wrist_image_latent_idx"],
            future_wrist_image2_latent_idx=indices["future_wrist_image2_latent_idx"],
            future_image_latent_idx=indices["future_image_latent_idx"],
            future_image2_latent_idx=indices["future_image2_latent_idx"],
            seed=int(seed),
            randomize_seed=False,
            num_denoising_steps_future_state=cfg.num_denoising_steps_future_state,
            use_ensemble_future_state_predictions=(
                cfg.num_future_state_predictions_in_ensemble > 1
            ),
            num_future_state_predictions_in_ensemble=(
                cfg.num_future_state_predictions_in_ensemble
            ),
            future_state_ensemble_aggregation_scheme=(
                cfg.future_state_ensemble_aggregation_scheme
            ),
        )
        value = get_value_prediction(
            cfg,
            model=model,
            data_batch=sample["data_batch"],
            future_state_samples_list=future["future_state_samples_list"],
            seed=int(seed),
            randomize_seed=False,
            num_denoising_steps_value=cfg.num_denoising_steps_value,
            use_ensemble_value_predictions=cfg.num_value_predictions_in_ensemble > 1,
            num_value_predictions_in_ensemble=cfg.num_value_predictions_in_ensemble,
        )
        sample["parallel_value_prediction"] = float(sample["value_prediction"])
        sample["autoregressive_value_prediction"] = float(value["value_prediction"])
        sample["autoregressive_future_image_predictions"] = future[
            "future_image_predictions"
        ]
        sample["autoregressive_future_state_generated_latent"] = future[
            "future_state_samples_list"
        ][-1]
        if value.get("generated_value_samples"):
            sample["autoregressive_value_generated_latent"] = value[
                "generated_value_samples"
            ][-1]
        sample["prediction_mode"] = "dual"
        autoregressive_values.append(float(value["value_prediction"]))

    ar_values = np.asarray(autoregressive_values, dtype=np.float64)
    metrics.update(
        {
            "autoregressive_value_mean": float(ar_values.mean()),
            "autoregressive_value_std": float(ar_values.std()),
            "autoregressive_value_range": float(np.ptp(ar_values)),
        }
    )
    return samples, metrics


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
    prediction_mode: str | None = None,
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
            prediction_mode=prediction_mode,
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


def _continue_to_horizon(
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
    target_t: int,
    resize_size: int,
    prediction_mode: str | None = None,
) -> tuple[Mapping[str, Any], bool, int, int]:
    """Follow the frozen max-value policy until a matched consequence horizon."""
    success = bool(env.check_success())
    continuation_queries = 0
    while not success and absolute_t < target_t:
        seeds = tuple(
            int(rollout_seed + 8_000_000 + absolute_t * 1000 + offset)
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
            prediction_mode=prediction_mode,
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
            max_t=target_t,
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
    consequence_horizon_steps: int,
    terminal_continuation: bool,
    continuation_prediction_mode: str | None = None,
) -> tuple[
    dict[str, Any],
    Mapping[str, Any],
    np.ndarray,
    Mapping[str, Any],
    np.ndarray,
]:
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
    horizon_obs = endpoint_obs
    horizon_state = endpoint_state
    if consequence_horizon_steps > cfg.num_open_loop_steps:
        target_t = min(max_t, snapshot_t + consequence_horizon_steps)
        obs_end, success, absolute_t, continuation_queries = _continue_to_horizon(
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
            target_t=target_t,
            resize_size=resize_size,
            prediction_mode=continuation_prediction_mode,
        )
        horizon_obs = _copy_observation(obs_end)
        horizon_state = np.asarray(env.get_sim_state(), dtype=np.float64).copy()
        horizon_outcome = _local_outcome(
            tracker,
            marker,
            obs_start,
            obs_end,
            success=success,
            executed_steps=absolute_t - snapshot_t,
        )
        horizon_outcome["continuation_queries"] = int(continuation_queries)
        outcome.update(prefixed(horizon_outcome, "h32_"))
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
            prediction_mode=continuation_prediction_mode,
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
    return outcome, endpoint_obs, endpoint_state, horizon_obs, horizon_state


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
    consequence_horizon_steps: int,
    terminal_continuation: bool,
    continuation_prediction_mode: str | None = None,
    requery_prediction_mode: str | None = None,
) -> tuple[
    dict[str, Any],
    Mapping[str, Any],
    np.ndarray,
    Mapping[str, Any],
    np.ndarray,
    dict[str, Any],
]:
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
            prediction_mode=requery_prediction_mode,
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
    horizon_obs = endpoint_obs
    horizon_state = endpoint_state
    if consequence_horizon_steps > cfg.num_open_loop_steps:
        target_t = min(max_t, snapshot_t + consequence_horizon_steps)
        obs_mid, success, absolute_t, continuation_queries = _continue_to_horizon(
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
            target_t=target_t,
            resize_size=resize_size,
            prediction_mode=continuation_prediction_mode,
        )
        horizon_obs = _copy_observation(obs_mid)
        horizon_state = np.asarray(env.get_sim_state(), dtype=np.float64).copy()
        horizon_outcome = _local_outcome(
            tracker,
            marker,
            obs_start,
            obs_mid,
            success=success,
            executed_steps=absolute_t - snapshot_t,
        )
        horizon_outcome["continuation_queries"] = int(continuation_queries)
        outcome.update(prefixed(horizon_outcome, "h32_"))
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
            prediction_mode=continuation_prediction_mode,
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
    return (
        outcome,
        endpoint_obs,
        endpoint_state,
        horizon_obs,
        horizon_state,
        requery_payload,
    )


def _candidate_features(
    sample: Mapping[str, Any],
    candidate_idx: int,
    feature_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if feature_row is None:
        actions = np.asarray(sample["actions"], dtype=np.float32)
        result: dict[str, Any] = {
            "candidate_value": float(sample.get("value_prediction", np.nan)),
            "candidate_first_action_l1": float(np.abs(actions[0]).mean()),
            "candidate_action_chunk_l1": float(np.abs(actions).mean()),
            "candidate_action_chunk_l2": float(np.sqrt(np.mean(actions**2))),
        }
        result.update(latent_internal_consistency(dict(sample)))
    else:
        result = dict(feature_row)
    if "parallel_value_prediction" in sample:
        result["candidate_parallel_value"] = float(sample["parallel_value_prediction"])
        result["candidate_autoregressive_value"] = float(
            sample["autoregressive_value_prediction"]
        )
        ar_sample = dict(sample)
        ar_sample["future_state_generated_latent"] = sample[
            "autoregressive_future_state_generated_latent"
        ]
        if "autoregressive_value_generated_latent" in sample:
            ar_sample["value_generated_latent"] = sample[
                "autoregressive_value_generated_latent"
            ]
        ar_consistency = latent_internal_consistency(ar_sample)
        for key, value in ar_consistency.items():
            if key.startswith("latent_future_proprio") or key.startswith("latent_value"):
                result[f"autoregressive_{key}"] = value
        future = extract_future_proprio_from_sample(ar_sample)
        if future is not None:
            future_vector = np.asarray(future, dtype=np.float64).reshape(-1, 9).mean(axis=0)
            for dimension, value in enumerate(future_vector):
                result[
                    f"candidate_autoregressive_predicted_future_proprio_d{dimension}"
                ] = float(value)
    result["candidate_idx"] = int(candidate_idx)
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
    candidate_horizon_states: Sequence[np.ndarray],
    candidate_horizon_obs: Sequence[Mapping[str, Any]],
    feedback_endpoint_state: np.ndarray | None,
    feedback_endpoint_obs: Mapping[str, Any] | None,
    feedback_horizon_state: np.ndarray | None,
    feedback_horizon_obs: Mapping[str, Any] | None,
    requery: Mapping[str, Any],
    consequence_horizon_steps: int,
) -> dict[str, np.ndarray]:
    future_images = [
        sample.get("future_image_predictions", {}).get("future_image") for sample in samples
    ]
    future_wrists = [
        sample.get("future_image_predictions", {}).get("future_wrist_image") for sample in samples
    ]
    future_proprio = [extract_future_proprio_from_sample(dict(sample)) for sample in samples]
    autoregressive_future_images = [
        sample.get("autoregressive_future_image_predictions", {}).get("future_image")
        for sample in samples
    ]
    autoregressive_future_wrists = [
        sample.get("autoregressive_future_image_predictions", {}).get(
            "future_wrist_image"
        )
        for sample in samples
    ]
    autoregressive_future_proprio = []
    for sample in samples:
        generated = sample.get("autoregressive_future_state_generated_latent")
        if generated is None:
            autoregressive_future_proprio.append(None)
            continue
        ar_sample = dict(sample)
        ar_sample["future_state_generated_latent"] = generated
        autoregressive_future_proprio.append(
            extract_future_proprio_from_sample(ar_sample)
        )
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
    }
    if feedback_endpoint_state is not None and feedback_endpoint_obs is not None:
        payload.update(
            {
                "feedback_endpoint_state": np.asarray(
                    feedback_endpoint_state, dtype=np.float64
                ),
                "feedback_endpoint_agentview": np.asarray(
                    get_libero_image(feedback_endpoint_obs, flip_images=cfg.flip_images),
                    dtype=np.uint8,
                ),
                "feedback_endpoint_wrist": np.asarray(
                    get_libero_wrist_image(feedback_endpoint_obs, flip_images=cfg.flip_images),
                    dtype=np.uint8,
                ),
                "feedback_endpoint_proprio": np.asarray(
                    proprio_from_libero_obs(dict(feedback_endpoint_obs)),
                    dtype=np.float32,
                ),
            }
        )
    if (
        consequence_horizon_steps > cfg.num_open_loop_steps
        and feedback_horizon_state is not None
        and feedback_horizon_obs is not None
    ):
        payload.update(
            {
                "candidate_h32_endpoint_states": np.stack(candidate_horizon_states),
                "candidate_h32_endpoint_proprio": np.stack(
                    [
                        np.asarray(proprio_from_libero_obs(dict(value)), dtype=np.float32)
                        for value in candidate_horizon_obs
                    ]
                ),
                "feedback_h32_endpoint_state": np.asarray(
                    feedback_horizon_state, dtype=np.float64
                ),
                "feedback_h32_endpoint_proprio": np.asarray(
                    proprio_from_libero_obs(dict(feedback_horizon_obs)), dtype=np.float32
                ),
            }
        )
    payload.update(runtime_snapshot_arrays(snapshot_state))
    for key, value in (
        ("candidate_predicted_future_images", _stack_optional(future_images, dtype=np.uint8)),
        ("candidate_predicted_future_wrists", _stack_optional(future_wrists, dtype=np.uint8)),
        ("candidate_predicted_future_proprio", _stack_optional(future_proprio)),
        (
            "candidate_autoregressive_predicted_future_images",
            _stack_optional(autoregressive_future_images, dtype=np.uint8),
        ),
        (
            "candidate_autoregressive_predicted_future_wrists",
            _stack_optional(autoregressive_future_wrists, dtype=np.uint8),
        ),
        (
            "candidate_autoregressive_predicted_future_proprio",
            _stack_optional(autoregressive_future_proprio),
        ),
    ):
        if value.size:
            payload[key] = value
    if all("autoregressive_value_prediction" in sample for sample in samples):
        payload["candidate_autoregressive_values"] = np.asarray(
            [sample["autoregressive_value_prediction"] for sample in samples],
            dtype=np.float32,
        )

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
    continuation_seed_offsets = (
        uncertainty_seed_offsets[: args.continuation_num_candidates]
        if args.continuation_num_candidates > 0
        else uncertainty_seed_offsets
    )
    continuation_prediction_mode = (
        None
        if args.continuation_prediction_mode == "inherit"
        else args.continuation_prediction_mode
    )
    fixed_query_indices = tuple(sorted(set(parse_int_list(args.snapshot_query_indices))))
    if not suites:
        raise ValueError("at least one suite is required")
    if len(existing_keys) >= args.target_decision_states:
        print(f"[vof] already complete: {len(existing_keys)} snapshots")
        return pd.DataFrame(feedback_rows), pd.DataFrame(candidate_rows)

    config_prediction_mode = (
        "parallel" if args.prediction_mode == "dual" else args.prediction_mode
    )
    cfg = default_policy_config(
        suites[0],
        seed=args.base_seed,
        num_open_loop_steps=args.open_loop_steps,
        num_denoising_steps_action=args.num_denoising_steps_action,
        prediction_mode=config_prediction_mode,
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
                                str(task.language),
                                seeds,
                                resize_size,
                                prediction_mode=args.prediction_mode,
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
                            collect_snapshot = (
                                key not in existing_keys
                                and snapshot_is_scheduled(
                                    args.sampling_mode,
                                    query_idx=query_idx,
                                    phase=phase,
                                    phases_seen_in_episode=phases_seen_in_episode,
                                    phase_count=phase_counts.get(phase, 0),
                                    phase_cap=phase_cap,
                                    fixed_query_indices=fixed_query_indices,
                                )
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
                                    "task_description": str(task.language),
                                    "num_candidates": int(len(samples)),
                                    "open_loop_steps": int(cfg.num_open_loop_steps),
                                    "feedback_steps": int(args.feedback_steps),
                                    "consequence_horizon_steps": int(
                                        args.consequence_horizon_steps
                                    ),
                                    "terminal_continuation": bool(terminal_continuation),
                                    "prediction_mode": args.prediction_mode,
                                    "continuation_prediction_mode": (
                                        continuation_prediction_mode or args.prediction_mode
                                    ),
                                    "experiment_split": args.experiment_split,
                                    "case_id": args.case_id,
                                }
                                query_features = {**query_metrics, **planning_diagnostics}
                                candidate_bundle = []
                                causal_feature_rows = terminal_candidate_feature_rows(samples)
                                endpoint_states = []
                                endpoint_obs = []
                                horizon_states = []
                                horizon_obs = []
                                for candidate_idx, sample in enumerate(samples):
                                    candidate_terminal_continuation = (
                                        should_continue_candidate_to_terminal(
                                            terminal_continuation,
                                            args.terminal_selected_feedback_only,
                                            candidate_idx,
                                            selected_idx,
                                        )
                                    )
                                    (
                                        outcome,
                                        candidate_obs,
                                        endpoint_state,
                                        candidate_horizon_obs,
                                        candidate_horizon_state,
                                    ) = _run_candidate_branch(
                                        cfg,
                                        model,
                                        dataset_stats,
                                        branch_env,
                                        snapshot_state,
                                        sample,
                                        common["task_description"],
                                        continuation_seed_offsets,
                                        rollout_seed=rollout_seed,
                                        snapshot_t=t,
                                        max_t=max_t,
                                        resize_size=resize_size,
                                        consequence_horizon_steps=args.consequence_horizon_steps,
                                        terminal_continuation=(
                                            candidate_terminal_continuation
                                        ),
                                        continuation_prediction_mode=continuation_prediction_mode,
                                    )
                                    row = {
                                        **common,
                                        **query_features,
                                        **_candidate_features(
                                            sample,
                                            candidate_idx,
                                            causal_feature_rows[candidate_idx],
                                        ),
                                        **outcome,
                                        "candidate_seed": int(seeds[candidate_idx]),
                                        "candidate_is_max_value": bool(candidate_idx == selected_idx),
                                        "candidate_terminal_continuation": bool(
                                            candidate_terminal_continuation
                                        ),
                                    }
                                    candidate_bundle.append(row)
                                    endpoint_states.append(endpoint_state)
                                    endpoint_obs.append(candidate_obs)
                                    horizon_states.append(candidate_horizon_state)
                                    horizon_obs.append(candidate_horizon_obs)

                                open_outcome = candidate_bundle[selected_idx]
                                if args.skip_feedback_branch:
                                    feedback_obs = None
                                    feedback_state = None
                                    feedback_horizon_obs = None
                                    feedback_horizon_state = None
                                    requery = {}
                                    feedback_row = {
                                        **common,
                                        **query_features,
                                        "selected_candidate_idx": int(selected_idx),
                                        "selected_candidate_seed": int(seeds[selected_idx]),
                                        "feedback_available": False,
                                        "query_cost": float(args.query_cost),
                                        "local_vof": np.nan,
                                        "terminal_vof": np.nan,
                                    }
                                else:
                                    (
                                        feedback_outcome,
                                        feedback_obs,
                                        feedback_state,
                                        feedback_horizon_obs,
                                        feedback_horizon_state,
                                        requery,
                                    ) = _run_feedback_branch(
                                        cfg,
                                        model,
                                        dataset_stats,
                                        branch_env,
                                        snapshot_state,
                                        samples[selected_idx],
                                        common["task_description"],
                                        continuation_seed_offsets,
                                        rollout_seed=rollout_seed,
                                        query_idx=query_idx,
                                        snapshot_t=t,
                                        max_t=max_t,
                                        resize_size=resize_size,
                                        feedback_steps=args.feedback_steps,
                                        consequence_horizon_steps=args.consequence_horizon_steps,
                                        terminal_continuation=terminal_continuation,
                                        continuation_prediction_mode=continuation_prediction_mode,
                                        requery_prediction_mode=args.prediction_mode,
                                    )
                                    feedback_row = {
                                        **common,
                                        **query_features,
                                        "selected_candidate_idx": int(selected_idx),
                                        "selected_candidate_seed": int(seeds[selected_idx]),
                                        "feedback_available": True,
                                        **prefixed(
                                            {
                                                key_name: value
                                                for key_name, value in open_outcome.items()
                                                if key_name not in common
                                                and key_name not in query_features
                                            },
                                            "open_",
                                        ),
                                        **prefixed(feedback_outcome, "feedback_"),
                                        **prefixed(
                                            dict(requery.get("metrics", {})),
                                            "feedback_query_",
                                        ),
                                        **prefixed(
                                            dict(requery.get("diagnostics", {})),
                                            "feedback_query_",
                                        ),
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
                                    horizon_states,
                                    horizon_obs,
                                    feedback_state,
                                    feedback_obs,
                                    feedback_horizon_state,
                                    feedback_horizon_obs,
                                    requery,
                                    args.consequence_horizon_steps,
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
                            if (
                                args.sampling_mode == "fixed_queries"
                                and fixed_query_indices
                                and query_idx > fixed_query_indices[-1]
                            ):
                                break
            finally:
                main_env.close()
                branch_env.close()

    metadata = {
        "run_name": args.run_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "arguments": vars(args),
        "phase_counts": phase_counts,
        "phase_cap": phase_cap,
        "fixed_query_indices": list(fixed_query_indices),
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
        "--sampling-mode",
        choices=["phase_balanced", "fixed_queries"],
        default="phase_balanced",
        help="Exploratory phase balancing or outcome-independent fixed query indices",
    )
    parser.add_argument(
        "--snapshot-query-indices",
        default="0,3,6,9",
        help="Comma/range specification used only by fixed_queries sampling",
    )
    parser.add_argument(
        "--phase-cap-fraction",
        type=float,
        default=0.4,
        help="Maximum fraction of collected states assigned to one phase proxy",
    )
    parser.add_argument("--open-loop-steps", type=int, default=16)
    parser.add_argument("--feedback-steps", type=int, default=8)
    parser.add_argument(
        "--consequence-horizon-steps",
        type=int,
        choices=[16, 32],
        default=16,
        help="Matched branch horizon; 32 adds one frozen max-value continuation query",
    )
    parser.add_argument("--terminal-continuation-fraction", type=float, default=0.2)
    parser.add_argument(
        "--terminal-selected-feedback-only",
        action="store_true",
        help=(
            "Continue only the selected commit candidate and the separate "
            "feedback branch to terminal; all candidates still reach H16"
        ),
    )
    parser.add_argument(
        "--continuation-num-candidates",
        type=int,
        default=0,
        help="Candidate count for the fixed continuation policy; 0 uses the full initial pool",
    )
    parser.add_argument(
        "--skip-feedback-branch",
        action="store_true",
        help="Collect candidate terminal branches without the separate 8+8 feedback branch",
    )
    parser.add_argument("--query-cost", type=float, default=0.0)
    parser.add_argument("--num-denoising-steps-action", type=int, default=5)
    parser.add_argument(
        "--prediction-mode",
        choices=["parallel", "autoregressive", "dual"],
        default="parallel",
    )
    parser.add_argument(
        "--continuation-prediction-mode",
        choices=["inherit", "parallel", "autoregressive"],
        default="inherit",
        help=(
            "Prediction mode for frozen branch continuation queries; inherit keeps "
            "the candidate-generation mode"
        ),
    )
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
    if args.consequence_horizon_steps < args.open_loop_steps:
        raise ValueError("consequence horizon cannot be shorter than the open-loop chunk")
    if args.target_decision_states < 1:
        raise ValueError("target_decision_states must be positive")
    candidate_count = len(parse_seed_list(args.uncertainty_seeds))
    if not 0 <= args.continuation_num_candidates <= candidate_count:
        raise ValueError(
            "continuation_num_candidates must be 0 or no larger than the initial candidate count"
        )
    fixed_query_indices = parse_int_list(args.snapshot_query_indices)
    if any(index < 0 for index in fixed_query_indices):
        raise ValueError("snapshot query indices must be non-negative")
    if args.sampling_mode == "fixed_queries" and not fixed_query_indices:
        raise ValueError("fixed_queries sampling requires snapshot query indices")
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

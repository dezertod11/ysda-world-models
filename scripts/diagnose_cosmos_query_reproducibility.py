#!/usr/bin/env python3
"""Repeat one Cosmos query on identical LIBERO observations.

The script intentionally keeps all Cosmos imports inside ``main`` so CUDA
determinism flags are configured before a CUDA context is created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np


def _array_digest(values: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(values):
        value = np.asarray(values[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(value.shape).encode("ascii"))
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def configure_torch(mode: str) -> dict[str, object]:
    if mode not in {"default", "warn", "strict"}:
        raise ValueError(f"Unknown deterministic mode: {mode}")
    if mode != "default":
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        os.environ.setdefault("NVIDIA_TF32_OVERRIDE", "0")

    import torch

    if mode != "default":
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.use_deterministic_algorithms(True, warn_only=mode == "warn")
        torch.set_float32_matmul_precision("highest")

    return {
        "mode": mode,
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "deterministic_warn_only": bool(torch.is_deterministic_algorithms_warn_only_enabled()),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cuda_matmul_allow_tf32": bool(torch.backends.cuda.matmul.allow_tf32),
        "cudnn_allow_tf32": bool(torch.backends.cudnn.allow_tf32),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG", ""),
    }


def within_process_diagnostics(
    actions: np.ndarray, values: np.ndarray, selected: np.ndarray
) -> dict[str, object]:
    if actions.ndim < 3 or values.ndim != 3 or selected.ndim != 2:
        raise ValueError("Unexpected diagnostic array shape")
    action_diff = np.max(np.abs(actions - actions[:, :1]), axis=tuple(range(2, actions.ndim)))
    value_diff = np.max(np.abs(values - values[:, :1]), axis=2)
    selected_match = selected == selected[:, :1]
    return {
        "max_action_abs_diff": float(action_diff.max(initial=0.0)),
        "max_value_abs_diff": float(value_diff.max(initial=0.0)),
        "selected_index_match_rate": float(selected_match.mean()),
        "exact": bool(
            np.all(action_diff == 0.0)
            and np.all(value_diff == 0.0)
            and np.all(selected_match)
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="libero_object_object")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--init-state-ids", default="0,16,41")
    parser.add_argument("--base-seed", type=int, default=15_000_000)
    parser.add_argument("--uncertainty-seeds", default="0,1,2,3")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--deterministic-mode", choices=["default", "warn", "strict"], default="default")
    parser.add_argument("--replica-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.repeats < 2:
        raise ValueError("At least two repeats are required")
    torch_settings = configure_torch(args.deterministic_mode)

    from libero.libero import benchmark

    from cosmos_policy.experiments.robot.cosmos_utils import (
        get_model,
        init_t5_text_embeddings_cache,
        load_dataset_stats,
    )
    from cosmos_policy.experiments.robot.libero.libero_utils import (
        get_libero_dummy_action,
        get_libero_env,
        get_libero_task_description,
    )
    from cosmos_policy.experiments.robot.libero.run_libero_eval import (
        prepare_observation,
        prewarm_libero_renderer,
        validate_config,
    )
    from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
        default_policy_config,
        get_task_init_states_compat,
        parse_int_list,
        parse_seed_list,
    )
    from cosmos_policy.experiments.robot.robot_utils import get_image_resize_size
    from cosmos_policy.utils.utils import set_seed_everywhere

    from collect_counterfactual_feedback import _sample_candidates

    init_state_ids = parse_int_list(args.init_state_ids)
    seed_offsets = parse_seed_list(args.uncertainty_seeds)
    cfg = default_policy_config(
        args.suite,
        seed=args.base_seed,
        num_open_loop_steps=16,
        num_denoising_steps_action=5,
        prediction_mode="parallel",
        num_denoising_steps_future_state=1,
        num_denoising_steps_value=1,
        num_future_state_samples=1,
        num_value_samples=1,
        value_ensemble_aggregation_scheme="average",
    )
    validate_config(cfg)
    set_seed_everywhere(cfg.seed)
    init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    dataset_stats = load_dataset_stats(cfg.dataset_stats_path)
    prewarm_libero_renderer(cfg)
    model, cosmos_config = get_model(cfg)
    if cfg.chunk_size != cosmos_config.dataloader_train.dataset.chunk_size:
        raise ValueError("checkpoint and diagnostic action chunk sizes differ")
    resize_size = get_image_resize_size(cfg.model_family)

    task_suite = benchmark.get_benchmark_dict()[args.suite]()
    task = task_suite.get_task(args.task_id)
    init_states = get_task_init_states_compat(task_suite, args.task_id, task)
    env, _ = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
    action_rows = []
    value_rows = []
    selected_rows = []
    observation_hashes = []
    simulator_hashes = []
    candidate_seed_rows = []
    try:
        for position, init_state_id in enumerate(init_state_ids):
            if init_state_id >= len(init_states):
                raise IndexError(f"init state {init_state_id} is unavailable")
            env.reset()
            obs = env.set_init_state(init_states[init_state_id])
            for _ in range(10):
                obs, _reward, done, _info = env.step(get_libero_dummy_action(cfg.model_family))
                if done:
                    break
            prepared = prepare_observation(obs, resize_size, cfg.flip_images)
            observation_hashes.append(_array_digest(prepared))
            simulator_hashes.append(
                hashlib.sha256(
                    np.ascontiguousarray(
                        np.asarray(env.get_sim_state(), dtype=np.float64)
                    ).tobytes()
                ).hexdigest()
            )
            seeds = tuple(
                int(args.base_seed + position * 10_000 + offset)
                for offset in seed_offsets
            )
            candidate_seed_rows.append(seeds)
            repeat_actions = []
            repeat_values = []
            repeat_selected = []
            for _repeat in range(args.repeats):
                samples, _metrics = _sample_candidates(
                    cfg,
                    model,
                    dataset_stats,
                    obs,
                    get_libero_task_description(task, env),
                    seeds,
                    resize_size,
                    prediction_mode="parallel",
                )
                actions = np.stack(
                    [np.asarray(sample["actions"], dtype=np.float32) for sample in samples]
                )
                values = np.asarray(
                    [sample["value_prediction"] for sample in samples], dtype=np.float32
                )
                repeat_actions.append(actions)
                repeat_values.append(values)
                repeat_selected.append(int(np.argmax(values)))
            action_rows.append(np.stack(repeat_actions))
            value_rows.append(np.stack(repeat_values))
            selected_rows.append(np.asarray(repeat_selected, dtype=np.int64))
    finally:
        env.close()

    actions = np.stack(action_rows)
    values = np.stack(value_rows)
    selected = np.stack(selected_rows)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        init_state_ids=np.asarray(init_state_ids, dtype=np.int64),
        candidate_seeds=np.asarray(candidate_seed_rows, dtype=np.int64),
        observation_hashes=np.asarray(observation_hashes),
        simulator_hashes=np.asarray(simulator_hashes),
        actions=actions,
        values=values,
        selected_indices=selected,
    )
    diagnostics = within_process_diagnostics(actions, values, selected)
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "replica_id": args.replica_id,
        "suite": args.suite,
        "task_id": args.task_id,
        "init_state_ids": init_state_ids,
        "base_seed": args.base_seed,
        "candidate_seed_offsets": list(seed_offsets),
        "repeats": args.repeats,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "torch": torch_settings,
        "within_process": diagnostics,
        "npz": str(output),
    }
    output.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

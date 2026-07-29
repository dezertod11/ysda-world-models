#!/usr/bin/env python3
"""Run the E0 denoising-trace sanity check on one real Cosmos Policy query."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from cosmos_policy.experiments.robot.cosmos_utils import (
    get_action,
    get_model,
    init_t5_text_embeddings_cache,
    load_dataset_stats,
)
from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
)
from cosmos_policy.experiments.robot.libero.run_libero_eval import (
    prepare_observation,
    prewarm_libero_renderer,
    validate_config,
)
from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
    default_policy_config,
)
from cosmos_policy.experiments.robot.libero.uncertainty_metrics import (
    summarize_action_ensemble,
)
from cosmos_policy.experiments.robot.libero.vfd_metrics import (
    compute_blockwise_vfd,
    summarize_flow_path_dispersion,
)
from cosmos_policy.experiments.robot.robot_utils import get_image_resize_size
from cosmos_policy.utils.utils import set_seed_everywhere
from libero.libero import benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="libero_spatial_swap")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--seed", type=int, default=195)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/uncertainty/vfd_e0_smoke.json"),
    )
    return parser.parse_args()


def trace_summary(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "num_steps": int(len(trace["sigmas"])),
        "sigmas": np.asarray(trace["sigmas"]).tolist(),
        "blocks": {
            name: list(np.asarray(values).shape)
            for name, values in trace["block_velocities"].items()
        },
        "excluded_terminal_evaluations": int(trace["excluded_terminal_evaluations"]),
    }


def duplicated_model_vfd(
    left_trace: dict[str, Any],
    right_trace: dict[str, Any],
) -> dict[str, float]:
    sigmas = np.stack([left_trace["sigmas"], right_trace["sigmas"]], axis=0)
    cross_evaluated = {}
    common_blocks = set(left_trace["block_velocities"]) & set(right_trace["block_velocities"])
    for block_name in sorted(common_blocks):
        own_paths = np.stack(
            [
                left_trace["block_velocities"][block_name],
                right_trace["block_velocities"][block_name],
            ],
            axis=0,
        )
        cross_evaluated[block_name] = np.repeat(own_paths[:, None], repeats=2, axis=1)
    return compute_blockwise_vfd(cross_evaluated, sigmas)


def main() -> None:
    args = parse_args()
    cfg = default_policy_config(args.suite, seed=args.seed)
    validate_config(cfg)
    set_seed_everywhere(cfg.seed)
    init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    dataset_stats = load_dataset_stats(cfg.dataset_stats_path)
    prewarm_libero_renderer(cfg)
    model, _cosmos_config = get_model(cfg)

    task_suite = benchmark.get_benchmark_dict()[args.suite]()
    task = task_suite.get_task(args.task_id)
    init_states = task_suite.get_task_init_states(args.task_id)
    env, task_description = get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
    try:
        env.reset()
        obs = env.set_init_state(init_states[args.init_state_id])
        for _ in range(10):
            obs, _reward, done, _info = env.step(get_libero_dummy_action(cfg.model_family))
            if done:
                break
        observation = prepare_observation(
            obs,
            get_image_resize_size(cfg.model_family),
            cfg.flip_images,
        )

        baseline = get_action(
            cfg,
            model,
            dataset_stats,
            observation,
            task_description,
            seed=args.seed,
            randomize_seed=False,
            num_denoising_steps_action=cfg.num_denoising_steps_action,
            record_denoising_trace=False,
        )
        traced = get_action(
            cfg,
            model,
            dataset_stats,
            observation,
            task_description,
            seed=args.seed,
            randomize_seed=False,
            num_denoising_steps_action=cfg.num_denoising_steps_action,
            record_denoising_trace=True,
        )
        traced_other_seed = get_action(
            cfg,
            model,
            dataset_stats,
            observation,
            task_description,
            seed=args.seed + 1,
            randomize_seed=False,
            num_denoising_steps_action=cfg.num_denoising_steps_action,
            record_denoising_trace=True,
        )
    finally:
        env.close()

    actions_equal = np.array_equal(
        np.asarray(baseline["actions"]),
        np.asarray(traced["actions"]),
    )
    latent_equal = torch.equal(
        baseline["generated_latent"],
        traced["generated_latent"],
    )
    if not actions_equal or not latent_equal:
        raise AssertionError(
            f"Tracing changed inference output: actions_equal={actions_equal}, latent_equal={latent_equal}"
        )

    trace = traced["denoising_trace"]
    other_trace = traced_other_seed["denoising_trace"]
    identical_path_metrics = summarize_flow_path_dispersion([trace, trace])
    exact_duplicated_vfd = duplicated_model_vfd(trace, other_trace)
    if any(abs(value) > 1e-12 for value in exact_duplicated_vfd.values()):
        raise AssertionError(f"Duplicated-model VFD must be zero, got {exact_duplicated_vfd}")

    ensemble_metrics = summarize_action_ensemble([traced, traced_other_seed])
    flow_path_metrics = {
        key: value
        for key, value in ensemble_metrics.items()
        if key.startswith("flow_path_")
    }
    report = {
        "suite": args.suite,
        "task_id": args.task_id,
        "init_state_id": args.init_state_id,
        "task_description": task_description,
        "seed": args.seed,
        "actions_equal_with_tracing": actions_equal,
        "generated_latent_equal_with_tracing": latent_equal,
        "trace": trace_summary(trace),
        "identical_trace_path_dispersion": identical_path_metrics,
        "duplicated_model_exact_vfd": exact_duplicated_vfd,
        "two_seed_flow_path_dispersion": flow_path_metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"Saved E0 report: {args.output.resolve()}")


if __name__ == "__main__":
    main()

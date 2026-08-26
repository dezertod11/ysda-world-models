#!/usr/bin/env python3
"""Verify exact MuJoCo snapshot replay before counterfactual branching runs."""

from __future__ import annotations

import argparse
import json

import numpy as np
from libero.libero import benchmark

from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
)
from cosmos_policy.experiments.robot.libero.uncertainty_comparison import (
    get_task_init_states_compat,
)
from libero_runtime_snapshot import (
    capture_libero_runtime_state,
    restore_libero_runtime_state,
)


def deterministic_actions(num_steps: int) -> np.ndarray:
    index = np.arange(num_steps, dtype=np.float32)
    actions = np.zeros((num_steps, 7), dtype=np.float32)
    actions[:, 0] = 0.015 * np.sin(index / 3.0)
    actions[:, 1] = 0.012 * np.cos(index / 4.0)
    actions[:, 2] = 0.008 * np.sin(index / 5.0)
    actions[:, 3] = 0.01 * np.cos(index / 3.0)
    actions[:, 6] = -1.0
    return actions


def execute(env, actions):
    obs = None
    for action in actions:
        obs, _reward, done, _info = env.step(action.tolist())
        if done:
            break
    return obs, np.asarray(env.get_sim_state(), dtype=np.float64).copy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="libero_object_object")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--steps", type=int, default=16)
    parser.add_argument("--split-step", type=int, default=8)
    parser.add_argument("--prefix-steps", type=int, default=16)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()

    task_suite = benchmark.get_benchmark_dict()[args.suite]()
    task = task_suite.get_task(args.task_id)
    init_states = get_task_init_states_compat(task_suite, args.task_id, task)
    actions = deterministic_actions(args.steps)
    reference_env, _ = get_libero_env(task, "cosmos", resolution=256)
    branch_env, _ = get_libero_env(task, "cosmos", resolution=256)
    try:
        reference_env.reset()
        reference_env.set_init_state(init_states[args.init_state_id])
        for _ in range(10):
            _obs, _reward, done, _info = reference_env.step(get_libero_dummy_action("cosmos"))
            if done:
                break
        execute(reference_env, deterministic_actions(args.prefix_steps))
        snapshot = capture_libero_runtime_state(reference_env)
        _obs, reference_state = execute(reference_env, actions)

        restore_libero_runtime_state(branch_env, snapshot)
        _obs, replay_state = execute(branch_env, actions)

        restore_libero_runtime_state(branch_env, snapshot)
        execute(branch_env, actions[: args.split_step])
        _obs, split_state = execute(branch_env, actions[args.split_step :])
    finally:
        reference_env.close()
        branch_env.close()

    replay_error = float(np.max(np.abs(reference_state - replay_state)))
    split_error = float(np.max(np.abs(reference_state - split_state)))
    result = {
        "suite": args.suite,
        "task_id": args.task_id,
        "init_state_id": args.init_state_id,
        "steps": args.steps,
        "split_step": args.split_step,
        "prefix_steps": args.prefix_steps,
        "state_size": int(reference_state.size),
        "replay_state_max_abs": replay_error,
        "split_replay_state_max_abs": split_error,
        "tolerance": args.tolerance,
        "passed": replay_error <= args.tolerance and split_error <= args.tolerance,
    }
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

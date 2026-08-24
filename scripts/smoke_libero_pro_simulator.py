#!/usr/bin/env python3
from __future__ import annotations

import argparse

from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
    get_libero_task_description,
)
from libero.libero import benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="libero_spatial_object")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--expected-description", default=None)
    args = parser.parse_args()

    suite_name = args.suite
    suite = benchmark.get_benchmark_dict()[suite_name]()
    task = suite.get_task(args.task_id)
    env, description = get_libero_env(task, "cosmos", resolution=args.resolution)

    try:
        bddl_description = get_libero_task_description(task, env)
        if description != bddl_description:
            raise AssertionError(
                f"Policy instruction {description!r} differs from active BDDL {bddl_description!r}"
            )
        if args.expected_description is not None and description != args.expected_description:
            raise AssertionError(
                f"Expected {args.expected_description!r}, got {description!r}"
            )
        observation = env.reset()
        if observation is None:
            observation = env.get_observation()

        print(f"suite={suite_name}")
        print(f"task_id={args.task_id}")
        print(f"benchmark_task={task.language}")
        print(f"bddl_task={description}")
        print(f"instruction_shift={description != task.language}")
        print(
            "agentview="
            f"{observation['agentview_image'].shape} "
            f"{observation['agentview_image'].dtype}"
        )
        print(
            "wrist="
            f"{observation['robot0_eye_in_hand_image'].shape} "
            f"{observation['robot0_eye_in_hand_image'].dtype}"
        )

        for step_index in range(args.steps):
            observation, reward, done, _info = env.step(
                get_libero_dummy_action("cosmos")
            )
            print(
                f"step={step_index} reward={reward} done={done} "
                f"eef={observation['robot0_eef_pos'].round(3)}"
            )
    finally:
        env.close()


if __name__ == "__main__":
    main()

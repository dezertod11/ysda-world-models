#!/usr/bin/env python3
from __future__ import annotations

from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
)
from libero.libero import benchmark


def main() -> None:
    suite_name = "libero_spatial_object"
    suite = benchmark.get_benchmark_dict()[suite_name]()
    task = suite.get_task(0)
    env, description = get_libero_env(task, "cosmos", resolution=128)

    try:
        observation = env.reset()
        if observation is None:
            observation = env.get_observation()

        print(f"suite={suite_name}")
        print(f"task={description}")
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

        for step_index in range(3):
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

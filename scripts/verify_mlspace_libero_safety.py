#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulator-smoke",
        action="store_true",
        help="Instantiate one Safety task and verify reset, init state, step, and info['cost'].",
    )
    return parser.parse_args()


def run_simulator_smoke(benchmark: object) -> None:
    from cosmos_policy.experiments.robot.libero.libero_utils import (
        get_libero_dummy_action,
        get_libero_env,
    )

    suite = benchmark.get_benchmark_dict()["obstacle_avoidance"]()
    task = suite.get_task(0)
    init_states = suite.get_task_init_states(task.level, task.level_id)
    env, _ = get_libero_env(task, model_family="cosmos", resolution=128)
    try:
        env.reset()
        observation = env.set_init_state(init_states[0])
        observation, _reward, done, info = env.step(get_libero_dummy_action("cosmos"))
    finally:
        env.close()

    if "agentview_image" not in observation:
        raise RuntimeError("Safety smoke observation has no agentview_image")
    if not isinstance(info.get("cost"), dict):
        raise RuntimeError(f"Safety smoke did not return an info['cost'] dictionary: {info}")
    print(
        "simulator_smoke="
        f"suite=obstacle_avoidance,level={task.level},level_id={task.level_id},"
        f"done={bool(done)},cost={info['cost']}"
    )


def main() -> None:
    args = parse_args()
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if "0" in {item.strip() for item in visible_devices.split(",")}:
        raise RuntimeError("Physical GPU 0 must not be used on MLSpace")

    from libero import libero as libero_package
    from libero.libero import benchmark, get_libero_path

    expected_repo = Path(os.environ["LIBERO_SAFETY_REPO"]).resolve()
    imported_libero = Path(libero_package.__file__).resolve()
    if expected_repo not in imported_libero.parents:
        raise RuntimeError(
            f"Expected LIBERO-Safety from {expected_repo}, imported {imported_libero}"
        )

    required_suites = {
        "affordance",
        "human_safety",
        "obstacle_avoidance",
        "obstacle_avoidance_human",
        "reasoning_safety",
    }
    suites = benchmark.get_benchmark_dict()
    missing = required_suites.difference(suites)
    if missing:
        raise RuntimeError(f"Missing LIBERO-Safety suites: {sorted(missing)}")

    for suite_name in sorted(required_suites):
        suite = suites[suite_name]()
        distribution = suite.get_task_distribution_by_level()
        if distribution != {0: 5, 1: 5, 2: 5}:
            raise RuntimeError(f"Unexpected task distribution for {suite_name}: {distribution}")

    for key in ("bddl_files", "init_states", "assets"):
        path = Path(get_libero_path(key))
        if not path.is_dir():
            raise RuntimeError(f"LIBERO-Safety {key} path is missing: {path}")

    print(f"python={os.sys.executable}")
    print(f"libero_safety={imported_libero}")
    print(f"commit={os.environ.get('LIBERO_SAFETY_COMMIT', 'unknown')}")
    print(f"suites={','.join(sorted(required_suites))}")
    print(f"assets={get_libero_path('assets')}")
    if args.simulator_smoke:
        run_simulator_smoke(benchmark)


if __name__ == "__main__":
    main()

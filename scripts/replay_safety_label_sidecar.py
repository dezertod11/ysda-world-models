#!/usr/bin/env python3
"""Replay recorded actions and audit task-aware LIBERO safety labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from libero.libero import benchmark

from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_dummy_action,
    get_libero_env,
)
from cosmos_policy.experiments.robot.libero.safety_signals import SafetySignalTracker


def task_init_states(suite, task_id: int, task):
    try:
        return suite.get_task_init_states(task_id)
    except TypeError:
        return suite.get_task_init_states(int(task.level), int(task.level_id))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--init-state-id", type=int, default=0)
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--expect-success", action="store_true")
    parser.add_argument("--expect-fail", action="store_true")
    parser.add_argument("--expect-drop", action="store_true")
    parser.add_argument("--expect-no-drop", action="store_true")
    parser.add_argument("--expect-successful-release", action="store_true")
    args = parser.parse_args()

    with np.load(args.sidecar, allow_pickle=False) as sidecar:
        actions = np.asarray(sidecar["actual_executed_actions"], dtype=np.float32)

    suite = benchmark.get_benchmark_dict()[args.suite]()
    task = suite.get_task(args.task_id)
    init_states = task_init_states(suite, args.task_id, task)
    env, description = get_libero_env(task, "cosmos", resolution=args.resolution)
    try:
        env.reset()
        observation = env.set_init_state(init_states[args.init_state_id])
        for _ in range(10):
            observation, _reward, done, _info = env.step(
                get_libero_dummy_action("cosmos")
            )
            if done:
                break

        tracker = SafetySignalTracker(env, observation)
        success = False
        final_t = 0
        for final_t, action in enumerate(actions, start=1):
            observation, _reward, done, info = env.step(action.tolist())
            tracker.observe(
                observation,
                action,
                t=final_t,
                info=info,
                task_success=bool(done),
            )
            if done:
                success = True
                break
        summary = tracker.episode_summary(
            success=success,
            final_t=final_t,
            max_steps=len(actions),
        )
        result = {
            "suite": args.suite,
            "task_id": args.task_id,
            "init_state_id": args.init_state_id,
            "task_description": description,
            "recorded_actions": int(len(actions)),
            "executed_actions": int(final_t),
            "success": bool(success),
            **summary,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if args.expect_success and not success:
            raise AssertionError("Recorded successful episode did not replay successfully")
        if args.expect_fail and success:
            raise AssertionError("Recorded failed episode unexpectedly replayed successfully")
        if args.expect_drop and not summary["target_drop_candidate"]:
            raise AssertionError("Expected physical drop was not recorded")
        if args.expect_no_drop and summary["target_drop_candidate"]:
            raise AssertionError("Expected placement was still classified as a drop")
        if args.expect_successful_release and not summary["successful_target_release"]:
            raise AssertionError("Expected placement release was not recorded")
    finally:
        env.close()


if __name__ == "__main__":
    main()

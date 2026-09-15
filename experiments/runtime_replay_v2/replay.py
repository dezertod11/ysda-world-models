#!/usr/bin/env python3
"""CPU-only diagnosis of P3 snapshot replay; never loads the policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "LIBERO-PRO")]
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("MUJOCO_GL", "glfw")
os.environ.setdefault("LIBERO_CONFIG_PATH", str(ROOT / ".runtime/libero_pro"))

import numpy as np

from libero_runtime_snapshot import (
    restore_libero_runtime_state,
    runtime_snapshot_from_arrays,
)


def digest(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def difference(a, b):
    mask = np.any(a != b, axis=1)
    return {
        "exact": bool(np.array_equal(a, b)),
        "first_different_row": int(np.flatnonzero(mask)[0]) if mask.any() else None,
        "max_abs": float(np.max(np.abs(a - b))),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--modes", nargs="+", default=["legacy", "reset_data", "zero_warmstart"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from importlib.metadata import version
    from libero.libero.envs.env_wrapper import ControlEnv

    case = ROOT / "experiments/campaigns/p3_benchmark_seed_replication_20260915_s1/main/environment__t3_i2"
    with np.load(case / "start.npz", allow_pickle=False) as data:
        snapshot = runtime_snapshot_from_arrays(data)
    with np.load(case / "max_value_h16.npz", allow_pickle=False) as data:
        actions = data["executed_actions"][:args.steps].copy()
    bddl = ROOT / ".runtime/trajectory_consensus_20260908_environment/bddl_files/libero_object_env/pick_up_the_bbq_sauce_and_place_it_in_the_basket.bddl"
    env = ControlEnv(
        bddl_file_name=str(bddl), use_camera_obs=False,
        has_offscreen_renderer=False, has_renderer=False,
        camera_heights=256, camera_widths=256,
    )
    report = {
        "versions": {k: version(k) for k in ("robosuite", "mujoco", "numpy")},
        "rendering": False, "policy_inference": False,
        "actions_sha256": digest(actions), "steps": len(actions), "runs": [],
    }
    traces = {}
    try:
        for mode in args.modes:
            reference = None
            for repeat in range(args.repeats):
                started = time.monotonic()
                np.random.seed(52320000 + repeat * 1000)
                if mode in ("reset_data", "zero_warmstart"):
                    env.reset()
                    if mode == "reset_data":
                        env.env.sim.reset()
                    else:
                        env.env.sim.data.qacc_warmstart[:] = 0
                    obs = restore_libero_runtime_state(env, snapshot, reset_env=False)
                else:
                    obs = restore_libero_runtime_state(env, snapshot)
                initial_warmstart = env.env.sim.data.qacc_warmstart.copy()
                states, proprio, goals = [], [], []
                for t in range(len(actions) + 1):
                    states.append(env.get_sim_state().copy())
                    proprio.append(np.concatenate([
                        obs["robot0_eef_pos"], obs["robot0_eef_quat"],
                        obs["robot0_gripper_qpos"],
                    ]))
                    goals.append(bool(env.check_success()))
                    if t < len(actions):
                        obs, _, _, _ = env.step(np.asarray(actions[t], dtype=np.float32).tolist())
                states, proprio = np.asarray(states), np.asarray(proprio)
                run = {
                    "mode": mode, "repeat": repeat,
                    "initial_warmstart_hash": digest(initial_warmstart),
                    "state_hash": digest(states), "proprio_hash": digest(proprio),
                    "first_success_t": next((i for i, v in enumerate(goals) if v), None),
                    "elapsed_s": time.monotonic() - started,
                }
                if reference is not None:
                    run["state_vs_repeat0"] = difference(reference[0], states)
                    run["proprio_vs_repeat0"] = difference(reference[1], proprio)
                else:
                    reference = states, proprio
                traces[f"{mode}_{repeat}_state"] = states
                traces[f"{mode}_{repeat}_proprio"] = proprio
                report["runs"].append(run)
                print(json.dumps(run), flush=True)
                (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        np.savez_compressed(args.output / "traces.npz", **traces)
    finally:
        env.close()


if __name__ == "__main__":
    main()

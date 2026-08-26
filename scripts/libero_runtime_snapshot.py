#!/usr/bin/env python3
"""Capture and restore LIBERO simulator plus controller runtime state."""

from __future__ import annotations

import copy
from typing import Any, Mapping

import numpy as np


MODEL_ARRAYS = (
    "body_pos",
    "body_quat",
    "geom_pos",
    "geom_quat",
    "site_pos",
    "site_quat",
    "eq_data",
)
ENV_ATTRIBUTES = ("timestep", "cur_time", "done")
CONTROLLER_ATTRIBUTES = (
    "goal_pos",
    "goal_ori",
    "initial_joint",
    "initial_ee_pos",
    "initial_ee_ori_mat",
    "relative_ori",
    "ori_ref",
    "kp",
    "kd",
    "damping_ratio",
    "action_scale",
    "action_output_transform",
    "action_input_transform",
    "new_update",
)


def _inner_env(env: Any) -> Any:
    current = env
    visited: set[int] = set()
    while hasattr(current, "env") and id(current) not in visited:
        visited.add(id(current))
        child = getattr(current, "env")
        if child is current:
            break
        current = child
    return current


def _copied_attributes(owner: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {
        name: copy.deepcopy(getattr(owner, name))
        for name in names
        if hasattr(owner, name)
    }


def capture_libero_runtime_state(env: Any) -> dict[str, Any]:
    inner = _inner_env(env)
    sim = inner.sim
    robots = []
    for robot in inner.robots:
        robots.append(
            {
                "controller": _copied_attributes(robot.controller, CONTROLLER_ATTRIBUTES),
                "gripper_current_action": np.asarray(
                    robot.gripper.current_action, dtype=np.float64
                ).copy()
                if getattr(robot, "has_gripper", False)
                else np.empty((0,), dtype=np.float64),
                "torques": copy.deepcopy(getattr(robot, "torques", None)),
            }
        )
    return {
        "sim_state": np.asarray(sim.get_state().flatten(), dtype=np.float64).copy(),
        "sim_ctrl": np.asarray(sim.data.ctrl, dtype=np.float64).copy(),
        "model": {
            name: np.asarray(getattr(sim.model, name), dtype=np.float64).copy()
            for name in MODEL_ARRAYS
            if hasattr(sim.model, name)
        },
        "environment": _copied_attributes(inner, ENV_ATTRIBUTES),
        "robots": robots,
    }


def _restore_attributes(owner: Any, values: Mapping[str, Any]) -> None:
    for name, value in values.items():
        setattr(owner, name, copy.deepcopy(value))


def restore_libero_runtime_state(env: Any, snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    env.reset()
    inner = _inner_env(env)
    sim = inner.sim
    for name, value in snapshot.get("model", {}).items():
        target = getattr(sim.model, name, None)
        if target is not None and np.shape(target) == np.shape(value):
            target[:] = value
    sim.set_state_from_flattened(np.asarray(snapshot["sim_state"], dtype=np.float64))
    if "sim_ctrl" in snapshot and np.shape(sim.data.ctrl) == np.shape(snapshot["sim_ctrl"]):
        sim.data.ctrl[:] = snapshot["sim_ctrl"]
    sim.forward()
    _restore_attributes(inner, snapshot.get("environment", {}))
    for robot, robot_state in zip(inner.robots, snapshot.get("robots", [])):
        _restore_attributes(robot.controller, robot_state.get("controller", {}))
        if getattr(robot, "has_gripper", False):
            robot.gripper.current_action = np.asarray(
                robot_state.get("gripper_current_action", robot.gripper.current_action)
            ).copy()
        robot.torques = copy.deepcopy(robot_state.get("torques"))
    inner._post_process()
    inner._update_observables(force=True)
    return inner._get_observations()


def runtime_snapshot_arrays(snapshot: Mapping[str, Any]) -> dict[str, np.ndarray]:
    """Flatten serializable runtime fields for an NPZ sidecar."""
    result = {
        "sim_state": np.asarray(snapshot["sim_state"], dtype=np.float64),
        "sim_ctrl": np.asarray(snapshot.get("sim_ctrl", []), dtype=np.float64),
    }
    for name, value in snapshot.get("model", {}).items():
        result[f"sim_model__{name}"] = np.asarray(value)
    for name, value in snapshot.get("environment", {}).items():
        result[f"sim_env__{name}"] = np.asarray(value)
    for index, robot in enumerate(snapshot.get("robots", [])):
        result[f"sim_robot{index}__gripper_current_action"] = np.asarray(
            robot.get("gripper_current_action", [])
        )
        for name, value in robot.get("controller", {}).items():
            if value is not None:
                result[f"sim_robot{index}__controller__{name}"] = np.asarray(value)
    return result

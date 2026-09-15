"""Versioned P3 snapshots for robosuite 1.4 OSC without interpolation.

Uses MuJoCo's complete integration state. The frozen v1 module is unchanged.
Legacy snapshots must not be silently upgraded: their warmstart is unavailable.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

import mujoco
import numpy as np

import libero_runtime_snapshot as legacy

SCHEMA = 2
STATE_SPEC = int(mujoco.mjtState.mjSTATE_INTEGRATION)
OBSERVABLE_FIELDS = (
    "_time_since_last_sample", "_current_delay", "_current_observed_value",
    "_sampled", "_sampling_timestep", "_enabled", "_active",
)


def _physics(env):
    sim = legacy._inner_env(env).sim
    return sim.model._model, sim.data._data


def _integration(env):
    model, data = _physics(env)
    state = np.empty(mujoco.mj_stateSize(model, STATE_SPEC), dtype=np.float64)
    mujoco.mj_getState(model, data, state, STATE_SPEC)
    return state


def _check_controllers(env):
    from robosuite.utils.observables import NO_CORRUPTION, NO_DELAY, NO_FILTER
    for sensor in legacy._inner_env(env)._observables.values():
        if (sensor._corrupter is not NO_CORRUPTION or sensor._filter is not NO_FILTER
                or sensor._delayer is not NO_DELAY):
            raise ValueError("Snapshot v2 requires deterministic, unfiltered sensors")
    for robot in legacy._inner_env(env).robots:
        controller = robot.controller
        if type(controller).__name__ != "OperationalSpaceController":
            raise ValueError("Snapshot v2 supports OperationalSpaceController only")
        if any(getattr(controller, name, None) is not None
               for name in ("interpolator_pos", "interpolator_ori")):
            raise ValueError("Snapshot v2 does not support controller interpolation")
        if not bool(controller.new_update):
            raise ValueError("Capture at action boundaries only (controller.new_update=True)")


def capture_libero_runtime_state(env: Any) -> dict[str, Any]:
    _check_controllers(env)
    snapshot = legacy.capture_libero_runtime_state(env)
    inner = legacy._inner_env(env)
    snapshot["observables"] = {
        name: legacy._copied_attributes(sensor, OBSERVABLE_FIELDS)
        for name, sensor in inner._observables.items()
    }
    snapshot["observation_cache"] = copy.deepcopy(inner._obs_cache)
    snapshot.update(schema_version=SCHEMA, mujoco_version=mujoco.__version__,
                    integration_spec=STATE_SPEC, integration_state=_integration(env))
    return snapshot


def _validate(snapshot):
    if snapshot.get("schema_version") != SCHEMA:
        raise ValueError("Snapshot v2 required: recapture; v1 lacks integration/warmstart state")
    if snapshot.get("mujoco_version") != mujoco.__version__:
        raise ValueError("MuJoCo version mismatch")
    if snapshot.get("integration_spec") != STATE_SPEC:
        raise ValueError("MuJoCo integration-state specification mismatch")
    state = np.asarray(snapshot["integration_state"])
    if state.ndim != 1 or not np.isfinite(state).all():
        raise ValueError("Invalid integration state")


def restore_libero_runtime_state(
    env: Any, snapshot: Mapping[str, Any], *,
    reset_env: bool = True, update_observables: bool = True,
) -> Mapping[str, Any]:
    _validate(snapshot)
    model, _ = _physics(env)
    if len(snapshot["integration_state"]) != mujoco.mj_stateSize(model, STATE_SPEC):
        raise ValueError("Snapshot belongs to a different model size")
    if snapshot["observables"].keys() != legacy._inner_env(env)._observables.keys():
        raise ValueError("Snapshot observable set differs from environment")
    legacy.restore_libero_runtime_state(
        env, snapshot, reset_env=reset_env, update_observables=False,
    )
    _check_controllers(env)
    model, data = _physics(env)
    state = np.asarray(snapshot["integration_state"], dtype=np.float64)
    mujoco.mj_setState(model, data, state, STATE_SPEC)
    mujoco.mj_forward(model, data)
    # mj_forward changes qacc_warmstart. Restore inputs after deriving kinematics.
    mujoco.mj_setState(model, data, state, STATE_SPEC)
    np.testing.assert_array_equal(_integration(env), state)
    inner = legacy._inner_env(env)
    for name, values in snapshot["observables"].items():
        legacy._restore_attributes(inner._observables[name], values)
    inner._obs_cache = copy.deepcopy(snapshot["observation_cache"])
    if not update_observables:
        return {}
    # Forced sensor updates advance sampling clocks; return the captured readings.
    obs = inner._get_observations()
    np.testing.assert_array_equal(_integration(env), state)
    return obs


def runtime_snapshot_arrays(snapshot: Mapping[str, Any]) -> dict[str, np.ndarray]:
    _validate(snapshot)
    result = legacy.runtime_snapshot_arrays(snapshot)
    for key in ("schema_version", "mujoco_version", "integration_spec", "integration_state"):
        result[f"runtime_v2__{key}"] = np.asarray(snapshot[key]).copy()
    for i, robot in enumerate(snapshot["robots"]):
        if robot["torques"] is not None:
            result[f"runtime_v2__robot{i}_torques"] = np.asarray(robot["torques"]).copy()
    for name, sensor in snapshot["observables"].items():
        for key, value in sensor.items():
            result[f"observable_v2__{name}__{key}"] = np.asarray(value).copy()
    for key, value in snapshot["observation_cache"].items():
        result[f"obscache_v2__{key}"] = np.asarray(value).copy()
    if any(value.dtype.hasobject for value in result.values()):
        raise ValueError("Snapshot must serialize without pickle/object arrays")
    return result


def runtime_snapshot_from_arrays(values: Mapping[str, Any]) -> dict[str, Any]:
    if "runtime_v2__schema_version" not in values:
        raise ValueError("Snapshot v2 required; do not resume v1 outputs in a v2 campaign")
    snapshot = legacy.runtime_snapshot_from_arrays(values)
    for key in ("schema_version", "mujoco_version", "integration_spec"):
        snapshot[key] = np.asarray(values[f"runtime_v2__{key}"]).item()
    snapshot["integration_state"] = np.asarray(values["runtime_v2__integration_state"]).copy()
    for i, robot in enumerate(snapshot["robots"]):
        key = f"runtime_v2__robot{i}_torques"
        robot["torques"] = copy.deepcopy(values.get(key))
    snapshot["observables"] = {}
    snapshot["observation_cache"] = {}
    for key in values:
        if key.startswith("observable_v2__"):
            _, name, field = key.split("__", 2)
            value = np.asarray(values[key])
            snapshot["observables"].setdefault(name, {})[field] = (
                value.item() if value.ndim == 0 else value.copy()
            )
        elif key.startswith("obscache_v2__"):
            snapshot["observation_cache"][key.removeprefix("obscache_v2__")] = np.asarray(values[key]).copy()
    _validate(snapshot)
    return snapshot

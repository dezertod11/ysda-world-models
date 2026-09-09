#!/usr/bin/env python3
"""Dense task-geometry labels for exact-state LIBERO branches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import numpy as np


@dataclass(frozen=True)
class GoalGeometry:
    goal_pairs: tuple[tuple[str, str, str], ...]
    target_positions: Mapping[str, np.ndarray]
    anchor_positions: Mapping[str, np.ndarray]
    eef_position: Optional[np.ndarray]


def inner_env(env: Any) -> Any:
    current = env
    visited: set[int] = set()
    while hasattr(current, "env") and id(current) not in visited:
        visited.add(id(current))
        child = getattr(current, "env")
        if child is current:
            break
        current = child
    return current


def _finite_xyz(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        return None
    if array.size < 3 or not np.all(np.isfinite(array[:3])):
        return None
    return array[:3].copy()


def observation_from_libero_proprio(proprio: Any) -> dict[str, np.ndarray]:
    """Build the geometry-only observation from Cosmos' 9-D LIBERO proprio."""
    vector = np.asarray(proprio, dtype=np.float64).reshape(-1)
    if vector.size < 5:
        raise ValueError(f"Expected LIBERO proprio with at least 5 values, got {vector.size}")
    return {"robot0_eef_pos": vector[2:5].copy()}


def _named_position(env: Any, name: str, observation: Mapping[str, Any]) -> Optional[np.ndarray]:
    state = (getattr(env, "object_states_dict", {}) or {}).get(name)
    if state is not None and hasattr(state, "get_geom_state"):
        try:
            position = _finite_xyz(state.get_geom_state().get("pos"))
        except (AttributeError, KeyError, TypeError, ValueError):
            position = None
        if position is not None:
            return position
    return _finite_xyz(observation.get(f"{name}_pos"))


def capture_goal_geometry(env: Any, observation: Mapping[str, Any]) -> GoalGeometry:
    base = inner_env(env)
    parsed = getattr(base, "parsed_problem", {}) or {}
    raw_goals = parsed.get("goal_state", []) or []
    pairs: list[tuple[str, str, str]] = []
    targets: dict[str, np.ndarray] = {}
    anchors: dict[str, np.ndarray] = {}
    for state in raw_goals:
        if len(state) < 3:
            continue
        relation, target, anchor = map(str, state[:3])
        target_position = _named_position(base, target, observation)
        anchor_position = _named_position(base, anchor, observation)
        if target_position is None or anchor_position is None:
            continue
        pairs.append((relation.lower(), target, anchor))
        targets[target] = target_position
        anchors[anchor] = anchor_position
    return GoalGeometry(
        goal_pairs=tuple(pairs),
        target_positions=targets,
        anchor_positions=anchors,
        eef_position=_finite_xyz(observation.get("robot0_eef_pos")),
    )


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else float("nan")


def _max(values: list[float]) -> float:
    return float(np.max(values)) if values else float("nan")


def geometry_delta_metrics(start: GoalGeometry, end: GoalGeometry) -> dict[str, float]:
    start_pairs = {(relation, target, anchor) for relation, target, anchor in start.goal_pairs}
    common_pairs = [pair for pair in end.goal_pairs if pair in start_pairs]
    xyz_start: list[float] = []
    xyz_end: list[float] = []
    xy_start: list[float] = []
    xy_end: list[float] = []
    target_lift: list[float] = []
    target_displacement: list[float] = []
    anchor_displacement: list[float] = []
    target_eef_start: list[float] = []
    target_eef_end: list[float] = []

    for _relation, target, anchor in common_pairs:
        target_start = start.target_positions[target]
        target_end = end.target_positions[target]
        anchor_start = start.anchor_positions[anchor]
        anchor_end = end.anchor_positions[anchor]
        xyz_start.append(float(np.linalg.norm(target_start - anchor_start)))
        xyz_end.append(float(np.linalg.norm(target_end - anchor_end)))
        xy_start.append(float(np.linalg.norm(target_start[:2] - anchor_start[:2])))
        xy_end.append(float(np.linalg.norm(target_end[:2] - anchor_end[:2])))
        target_lift.append(float(target_end[2] - target_start[2]))
        target_displacement.append(float(np.linalg.norm(target_end - target_start)))
        anchor_displacement.append(float(np.linalg.norm(anchor_end - anchor_start)))
        if start.eef_position is not None:
            target_eef_start.append(float(np.linalg.norm(target_start - start.eef_position)))
        if end.eef_position is not None:
            target_eef_end.append(float(np.linalg.norm(target_end - end.eef_position)))

    xyz_start_mean = _mean(xyz_start)
    xyz_end_mean = _mean(xyz_end)
    xy_start_mean = _mean(xy_start)
    xy_end_mean = _mean(xy_end)
    eef_start_mean = _mean(target_eef_start)
    eef_end_mean = _mean(target_eef_end)
    return {
        "dense_goal_pair_count": float(len(common_pairs)),
        "dense_target_goal_distance_start_mean": xyz_start_mean,
        "dense_target_goal_distance_end_mean": xyz_end_mean,
        "dense_target_goal_distance_improvement_mean": (
            xyz_start_mean - xyz_end_mean
            if np.isfinite(xyz_start_mean) and np.isfinite(xyz_end_mean)
            else float("nan")
        ),
        "dense_target_goal_xy_distance_start_mean": xy_start_mean,
        "dense_target_goal_xy_distance_end_mean": xy_end_mean,
        "dense_target_goal_xy_distance_improvement_mean": (
            xy_start_mean - xy_end_mean
            if np.isfinite(xy_start_mean) and np.isfinite(xy_end_mean)
            else float("nan")
        ),
        "dense_target_eef_distance_start_mean": eef_start_mean,
        "dense_target_eef_distance_end_mean": eef_end_mean,
        "dense_target_eef_distance_improvement_mean": (
            eef_start_mean - eef_end_mean
            if np.isfinite(eef_start_mean) and np.isfinite(eef_end_mean)
            else float("nan")
        ),
        "dense_target_lift_end_mean": _mean(target_lift),
        "dense_target_displacement_mean": _mean(target_displacement),
        "dense_target_displacement_max": _max(target_displacement),
        "dense_goal_anchor_displacement_mean": _mean(anchor_displacement),
    }


def restore_flat_sim_state(
    env: Any, state: Any, *, update_observables: bool = True
) -> Mapping[str, Any]:
    base = inner_env(env)
    base.sim.set_state_from_flattened(np.asarray(state, dtype=np.float64))
    base.sim.forward()
    if not update_observables:
        return {}
    base._post_process()
    base._update_observables(force=True)
    return base._get_observations()

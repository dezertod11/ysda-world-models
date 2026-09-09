#!/usr/bin/env python3
"""Frozen, observation-only trigger for the online perception regrasp policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

try:
    from perception_regrasp import canonical_object_name
except ModuleNotFoundError:
    from scripts.perception_regrasp import canonical_object_name


TRIGGER_MODES = ("workspace_calibrated", "global_conservative")
INTERVENTION_STRATEGIES = {
    "workspace_calibrated": ("workspace_calibrated", "perception_regrasp"),
    "global_conservative": ("global_conservative", "perception_regrasp"),
    "workspace_retreat_only": ("workspace_calibrated", "retreat_only"),
}


def resolve_intervention_strategy(strategy: str) -> tuple[str, str]:
    """Return the frozen trigger mode and primitive for a named branch."""
    try:
        return INTERVENTION_STRATEGIES[strategy]
    except KeyError as error:
        choices = ", ".join(INTERVENTION_STRATEGIES)
        raise ValueError(
            f"Unknown intervention strategy {strategy!r}; choose from {choices}"
        ) from error


@dataclass(frozen=True)
class TriggerDecision:
    mode: str
    passed: bool
    finite_pass: bool
    confidence_pass: bool
    workspace_pass: bool
    miss_distance_pass: bool
    reach_pass: bool
    estimated_target_eef_distance_m: float
    score_threshold: float

    def as_dict(self, prefix: str = "trigger_") -> dict[str, Any]:
        return {f"{prefix}{key}": value for key, value in self.__dict__.items()}


def load_trigger_artifact(path: str | Path) -> dict[str, Any]:
    artifact = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if int(artifact.get("schema_version", -1)) != 1:
        raise ValueError(f"Unsupported trigger artifact schema: {artifact.get('schema_version')}")
    if not artifact.get("objects"):
        raise ValueError("Trigger artifact has no object calibration")
    return artifact


def _object_config(artifact: Mapping[str, Any], object_name: str) -> Mapping[str, Any]:
    canonical = canonical_object_name(object_name)
    objects = artifact.get("objects", {})
    if canonical not in objects:
        raise KeyError(f"No trigger calibration for object {canonical!r}")
    return objects[canonical]


def evaluate_trigger(
    localization: Mapping[str, Any],
    eef_position: np.ndarray,
    artifact: Mapping[str, Any],
    *,
    mode: str,
    require_miss: bool = True,
) -> TriggerDecision:
    """Evaluate a deployable gate using only RGB localization and robot proprioception."""
    if mode not in TRIGGER_MODES:
        raise ValueError(f"Unknown trigger mode {mode!r}; choose from {TRIGGER_MODES}")

    object_name = canonical_object_name(
        str(localization.get("perception_object", localization.get("object_name", "")))
    )
    config = _object_config(artifact, object_name)
    world = np.asarray(
        [
            localization.get("perception_world_x", np.nan),
            localization.get("perception_world_y", np.nan),
            localization.get("perception_world_z", np.nan),
        ],
        dtype=np.float64,
    )
    eef = np.asarray(eef_position, dtype=np.float64).reshape(-1)[:3]
    score = float(localization.get("perception_score_range", np.nan))
    finite_pass = bool(
        world.shape == (3,)
        and eef.shape == (3,)
        and np.all(np.isfinite(world))
        and np.all(np.isfinite(eef))
        and np.isfinite(score)
    )
    distance = float(np.linalg.norm(world - eef)) if finite_pass else float("nan")

    if mode == "workspace_calibrated":
        score_threshold = float(config["score_range_lower"])
    else:
        score_threshold = float(artifact["global_conservative_score_range"])
    confidence_pass = bool(finite_pass and score >= score_threshold)

    lower = np.asarray(config["workspace_lower_xyz"], dtype=np.float64)
    upper = np.asarray(config["workspace_upper_xyz"], dtype=np.float64)
    workspace_pass = bool(
        finite_pass and lower.shape == (3,) and upper.shape == (3,)
        and np.all(world >= lower) and np.all(world <= upper)
    )
    minimum = float(artifact["minimum_miss_distance_m"])
    maximum = float(artifact["maximum_reach_distance_m"])
    miss_distance_pass = bool(not require_miss or (finite_pass and distance >= minimum))
    reach_pass = bool(finite_pass and distance <= maximum)
    passed = bool(
        finite_pass
        and confidence_pass
        and workspace_pass
        and miss_distance_pass
        and reach_pass
    )
    return TriggerDecision(
        mode=mode,
        passed=passed,
        finite_pass=finite_pass,
        confidence_pass=confidence_pass,
        workspace_pass=workspace_pass,
        miss_distance_pass=miss_distance_pass,
        reach_pass=reach_pass,
        estimated_target_eef_distance_m=distance,
        score_threshold=score_threshold,
    )

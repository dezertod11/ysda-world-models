#!/usr/bin/env python3
"""Frozen observation-only outcome heads for choosing a recovery primitive."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np


ROUTER_STRATEGIES = (
    "baseline_h8",
    "workspace_retreat_only",
    "workspace_calibrated",
)

ROUTER_FEATURES = (
    "trigger_localization_world_x",
    "trigger_localization_world_y",
    "trigger_localization_world_z",
    "trigger_localization_peak_probability",
    "trigger_localization_entropy",
    "trigger_localization_score_range",
    "trigger_estimated_target_eef_distance_m",
)


def load_recovery_router(path: str | Path) -> dict[str, Any]:
    artifact = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if int(artifact.get("schema_version", -1)) != 1:
        raise ValueError(f"Unsupported recovery router schema: {artifact.get('schema_version')}")
    if tuple(artifact.get("features", ())) != ROUTER_FEATURES:
        raise ValueError("Recovery router feature contract does not match runtime")
    if tuple(artifact.get("strategies", ())) != ROUTER_STRATEGIES:
        raise ValueError("Recovery router strategy contract does not match runtime")
    for key in ("feature_medians", "feature_means", "feature_scales", "heads"):
        if key not in artifact:
            raise ValueError(f"Recovery router artifact is missing {key!r}")
    return artifact


def _finite_feature_vector(
    record: Mapping[str, Any], artifact: Mapping[str, Any]
) -> np.ndarray:
    medians = np.asarray(artifact["feature_medians"], dtype=np.float64)
    values = np.asarray([record.get(name, np.nan) for name in ROUTER_FEATURES], dtype=np.float64)
    if medians.shape != values.shape:
        raise ValueError("Recovery router median vector has an invalid shape")
    return np.where(np.isfinite(values), values, medians)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def route_recovery(
    record: Mapping[str, Any], artifact: Mapping[str, Any]
) -> dict[str, Any]:
    """Score all branches using pre-intervention features and select one."""
    values = _finite_feature_vector(record, artifact)
    means = np.asarray(artifact["feature_means"], dtype=np.float64)
    scales = np.asarray(artifact["feature_scales"], dtype=np.float64)
    if means.shape != values.shape or scales.shape != values.shape:
        raise ValueError("Recovery router scaler vectors have invalid shapes")
    if not np.all(np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError("Recovery router scales must be finite and positive")
    standardized = (values - means) / scales

    probabilities: dict[str, float] = {}
    scores: dict[str, float] = {}
    penalty = float(artifact["primitive_cost_lambda"])
    primitive_costs = artifact["primitive_costs"]
    for strategy in ROUTER_STRATEGIES:
        head = artifact["heads"][strategy]
        coefficients = np.asarray(head["coefficients"], dtype=np.float64)
        if coefficients.shape != standardized.shape:
            raise ValueError(f"Invalid coefficient shape for {strategy}")
        logit = float(np.dot(coefficients, standardized) + float(head["intercept"]))
        probability = _sigmoid(logit)
        probabilities[strategy] = probability
        scores[strategy] = probability - penalty * float(primitive_costs[strategy])

    trigger_passed = bool(record.get("trigger_passed", False))
    if trigger_passed:
        selected = max(ROUTER_STRATEGIES, key=lambda name: scores[name])
    else:
        selected = "baseline_h8"
    return {
        "router_selected_strategy": selected,
        "router_trigger_override": not trigger_passed,
        "router_probabilities": probabilities,
        "router_scores": scores,
        "router_feature_values": dict(zip(ROUTER_FEATURES, values.tolist(), strict=True)),
    }


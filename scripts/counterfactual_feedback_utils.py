#!/usr/bin/env python3
"""Pure utilities shared by counterfactual feedback collection and analysis."""

from __future__ import annotations

import hashlib
from typing import Any, Collection, Mapping

import numpy as np


PHASES = ("approach", "grasp", "transport", "release")


def deterministic_unit_interval(*parts: Any) -> float:
    """Map an experiment identity to a stable value in [0, 1)."""
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def should_run_terminal_continuation(fraction: float, *identity: Any) -> bool:
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("terminal continuation fraction must be in [0, 1]")
    return deterministic_unit_interval(*identity) < fraction


def should_continue_candidate_to_terminal(
    terminal_requested: bool,
    selected_feedback_only: bool,
    candidate_idx: int,
    selected_idx: int,
) -> bool:
    """Restrict terminal work to the commit branch when requested.

    The feedback branch is handled separately by the collector. H16 endpoint
    execution remains enabled for every candidate regardless of this decision.
    """
    return bool(
        terminal_requested
        and (not selected_feedback_only or int(candidate_idx) == int(selected_idx))
    )


def snapshot_is_scheduled(
    sampling_mode: str,
    *,
    query_idx: int,
    phase: str,
    phases_seen_in_episode: Collection[str],
    phase_count: int,
    phase_cap: int,
    fixed_query_indices: Collection[int],
) -> bool:
    """Return whether a decision state belongs to the preregistered sample.

    ``phase_balanced`` preserves the exploratory collector behavior. The
    confirmatory ``fixed_queries`` mode depends only on the query index and is
    therefore independent of the realized phase, progress, and branch outcome.
    """
    if sampling_mode == "phase_balanced":
        return phase not in phases_seen_in_episode and phase_count < phase_cap
    if sampling_mode == "fixed_queries":
        return int(query_idx) in {int(value) for value in fixed_query_indices}
    raise ValueError(f"Unknown snapshot sampling mode: {sampling_mode}")


def prefixed(values: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {f"{prefix}{key}": value for key, value in values.items()}


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if np.isfinite(numeric) else default


def local_branch_utility(metrics: Mapping[str, Any]) -> float:
    """Frozen local utility; all constituent labels remain available separately.

    The utility is intentionally simple and bounded. It is a pilot target, not a
    replacement for terminal success or official safety metrics.
    """
    success = float(bool(metrics.get("local_success", False)))
    progress = np.clip(_finite(metrics.get("observed_goal_progress_delta")), -1.0, 1.0)
    target_fraction = np.clip(
        _finite(metrics.get("observed_target_goal_satisfied_fraction_end")),
        0.0,
        1.0,
    )
    drop = float(bool(_finite(metrics.get("observed_target_drop_candidate"))))
    wrong = float(bool(_finite(metrics.get("observed_wrong_object_interaction_candidate"))))
    violation = float(bool(_finite(metrics.get("observed_official_safety_violation"))))
    return float(
        2.0 * success
        + progress
        + 0.25 * target_fraction
        - 1.0 * drop
        - 0.5 * wrong
        - 1.0 * violation
    )


def _scaled_optional(metrics: Mapping[str, Any], name: str, scale: float) -> float | None:
    try:
        value = float(metrics.get(name, np.nan))
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return float(np.clip(value / scale, -1.0, 1.0))


def dense_branch_utility_v2(metrics: Mapping[str, Any], phase: str) -> float:
    """Phase-aware dense consequence utility with separately stored components."""
    goal = _scaled_optional(
        metrics, "dense_target_goal_distance_improvement_mean", 0.25
    )
    eef = _scaled_optional(
        metrics, "dense_target_eef_distance_improvement_mean", 0.10
    )
    lift = _scaled_optional(metrics, "dense_target_lift_end_mean", 0.05)
    phase_weights = {
        "approach": ((goal, 0.5), (eef, 0.5)),
        "grasp": ((goal, 0.25), (eef, 0.25), (lift, 0.5)),
        "transport": ((goal, 0.75), (lift, 0.25)),
        "release": ((goal, 1.0),),
    }.get(str(phase), ((goal, 1.0),))
    available = [(value, weight) for value, weight in phase_weights if value is not None]
    dense_progress = (
        sum(value * weight for value, weight in available)
        / sum(weight for _value, weight in available)
        if available
        else 0.0
    )

    success = float(bool(metrics.get("local_success", False)))
    progress = np.clip(_finite(metrics.get("observed_goal_progress_delta")), -1.0, 1.0)
    drop = float(bool(_finite(metrics.get("observed_target_drop_candidate"))))
    wrong = float(bool(_finite(metrics.get("observed_wrong_object_interaction_candidate"))))
    violation = float(bool(_finite(metrics.get("observed_official_safety_violation"))))
    return float(
        2.0 * success
        + progress
        + dense_progress
        - drop
        - 0.5 * wrong
        - violation
    )


def terminal_branch_utility(metrics: Mapping[str, Any]) -> float:
    """Terminal utility with hard separation of task success and violations."""
    success = float(bool(metrics.get("terminal_success", False)))
    progress = np.clip(_finite(metrics.get("terminal_goal_progress_max")), 0.0, 1.0)
    drop = float(bool(metrics.get("terminal_target_drop_candidate", False)))
    wrong = float(bool(metrics.get("terminal_wrong_object_interaction_candidate", False)))
    violation = float(bool(metrics.get("terminal_official_safety_violation", False)))
    return float(2.0 * success + progress - drop - 0.5 * wrong - violation)


def value_of_feedback(
    open_metrics: Mapping[str, Any],
    feedback_metrics: Mapping[str, Any],
    *,
    query_cost: float = 0.0,
    terminal: bool = False,
) -> float:
    utility = terminal_branch_utility if terminal else local_branch_utility
    return float(utility(feedback_metrics) - utility(open_metrics) - query_cost)

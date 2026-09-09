#!/usr/bin/env python3
"""Pure helpers for the frozen P3 recovery-proposal experiment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


DEVELOPMENT_CELLS: tuple[tuple[str, int], ...] = (
    ("y0.2", 4),
    ("y0.2", 6),
    ("y0.2", 9),
    ("y0.3", 5),
    ("x0.2", 9),
    ("y0.3", 1),
    ("x0.2", 6),
    ("x0.2", 5),
)


@dataclass(frozen=True)
class RecoveryProposal:
    name: str
    execution_horizon: int
    primitive: str
    deployable: bool


RECOVERY_PROPOSALS: tuple[RecoveryProposal, ...] = (
    RecoveryProposal("frequent_requery_h4", 4, "none", True),
    RecoveryProposal("lift_hold_h8", 8, "lift_hold", True),
    RecoveryProposal("perception_regrasp_h8", 8, "perception_regrasp", True),
    RecoveryProposal("privileged_regrasp_h8", 8, "privileged_regrasp", False),
)


def proposal_by_name(name: str) -> RecoveryProposal:
    matches = [proposal for proposal in RECOVERY_PROPOSALS if proposal.name == name]
    if len(matches) != 1:
        available = ", ".join(proposal.name for proposal in RECOVERY_PROPOSALS)
        raise ValueError(f"Unknown recovery proposal {name!r}; choose from {available}")
    return matches[0]


def stable_uint32(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def group_balanced_selection(
    frame: pd.DataFrame,
    *,
    count: int,
    seed: int,
    identity_column: str = "row_uid",
    group_column: str = "independent_group",
) -> pd.DataFrame:
    """Select deterministically in rounds so distinct init groups come first."""
    if count < 1:
        raise ValueError("count must be positive")
    required = {identity_column, group_column}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing selection columns: {sorted(missing)}")
    if frame[identity_column].duplicated().any():
        raise ValueError(f"Duplicate {identity_column} values")
    if len(frame) < count:
        raise ValueError(f"Need {count} rows but only {len(frame)} are available")

    work = frame.copy()
    work["_row_order"] = work[identity_column].map(
        lambda value: stable_uint32("row", seed, value)
    )
    work["_group_order"] = work[group_column].map(
        lambda value: stable_uint32("group", seed, value)
    )
    work = work.sort_values(
        ["_group_order", group_column, "_row_order", identity_column],
        kind="stable",
    )
    work["_round"] = work.groupby(group_column, sort=False).cumcount()
    selected = work.sort_values(
        ["_round", "_group_order", group_column, "_row_order", identity_column],
        kind="stable",
    ).head(count)
    return selected.drop(columns=["_row_order", "_group_order", "_round"])


def parse_proposals(value: str | Iterable[str]) -> tuple[RecoveryProposal, ...]:
    names = (
        [item.strip() for item in value.split(",")]
        if isinstance(value, str)
        else [str(item).strip() for item in value]
    )
    names = [name for name in names if name]
    if not names:
        raise ValueError("At least one recovery proposal is required")
    if len(names) != len(set(names)):
        raise ValueError("Recovery proposals must be unique")
    return tuple(proposal_by_name(name) for name in names)


def cartesian_servo_action(
    eef_position: Sequence[float],
    target_position: Sequence[float],
    *,
    gripper: float,
    controller_step_m: float = 0.05,
) -> np.ndarray:
    """Map a Cartesian target into a clipped LIBERO OSC-pose command."""
    if controller_step_m <= 0:
        raise ValueError("controller_step_m must be positive")
    eef = np.asarray(eef_position, dtype=np.float64).reshape(-1)
    target = np.asarray(target_position, dtype=np.float64).reshape(-1)
    if eef.size < 3 or target.size < 3:
        raise ValueError("eef_position and target_position need three coordinates")
    action = np.zeros(7, dtype=np.float32)
    action[:3] = np.clip((target[:3] - eef[:3]) / controller_step_m, -1.0, 1.0)
    action[-1] = float(np.clip(gripper, -1.0, 1.0))
    return action


def continuation_seeds(
    rollout_seed: int,
    proposal_name: str,
    absolute_t: int,
    offsets: Sequence[int],
) -> tuple[int, ...]:
    branch_offset = stable_uint32("recovery", proposal_name) % 1_000_000
    return tuple(
        int(rollout_seed + 20_000_000 + branch_offset + absolute_t * 1000 + offset)
        for offset in offsets
    )

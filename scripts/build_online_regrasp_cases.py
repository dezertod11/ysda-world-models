#!/usr/bin/env python3
"""Build frozen, disjoint P3c full-episode manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


CELLS = (
    ("x0.2", 5),
    ("x0.2", 6),
    ("x0.2", 9),
    ("y0.2", 4),
    ("y0.2", 6),
    ("y0.2", 9),
    ("y0.3", 1),
    ("y0.3", 5),
)
SCREEN_CELLS = (("x0.2", 5), ("y0.2", 4), ("y0.2", 6))


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return 40_000_000 + int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % 10_000_000


def rows_for_split(split: str) -> list[dict]:
    if split == "screen":
        cells, init_ids, rollout_ids = SCREEN_CELLS, range(25, 27), range(2)
    elif split == "development":
        cells, init_ids, rollout_ids = CELLS, range(27, 32), range(1)
    elif split == "holdout":
        cells, init_ids, rollout_ids = CELLS, range(35, 40), range(1)
    else:
        raise ValueError(split)
    rows = []
    for position_level, task_id in cells:
        for init_state_id in init_ids:
            for rollout_id in rollout_ids:
                case_id = (
                    f"p3c_{split}__{position_level.replace('.', 'p')}__task{task_id}"
                    f"__init{init_state_id}__rollout{rollout_id}"
                )
                rows.append(
                    {
                        "case_id": case_id,
                        "split": split,
                        "suite": "libero_object_temp",
                        "position_level": position_level,
                        "task_id": task_id,
                        "init_state_id": init_state_id,
                        "rollout_id": rollout_id,
                        "rollout_seed": stable_seed(
                            "p3c", split, position_level, task_id, init_state_id, rollout_id
                        ),
                        "independent_group": (
                            f"{position_level}|task{task_id}|init{init_state_id}"
                        ),
                    }
                )
    return rows


def build(output_dir: Path) -> None:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    all_frames = []
    metadata = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    groups_by_split = {}
    for split in ("screen", "development", "holdout"):
        frame = pd.DataFrame(rows_for_split(split))
        frame.to_csv(output_dir / f"{split}_cases.csv", index=False)
        frame.to_parquet(output_dir / f"{split}_cases.parquet", index=False)
        all_frames.append(frame)
        groups_by_split[split] = sorted(frame["independent_group"].unique().tolist())
        metadata[split] = {
            "cases": len(frame),
            "groups": frame["independent_group"].nunique(),
            "cells": frame.groupby(["position_level", "task_id"]).ngroups,
            "init_state_ids": sorted(frame["init_state_id"].unique().tolist()),
        }
    group_sets = {key: set(value) for key, value in groups_by_split.items()}
    for left, right in (("screen", "development"), ("screen", "holdout"), ("development", "holdout")):
        if group_sets[left] & group_sets[right]:
            raise RuntimeError(f"Group leakage between {left} and {right}")
    combined = pd.concat(all_frames, ignore_index=True)
    if combined["case_id"].duplicated().any():
        raise RuntimeError("Duplicate P3c case_id")
    metadata["group_overlap"] = 0
    (output_dir / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    build(parser.parse_args().output_dir)

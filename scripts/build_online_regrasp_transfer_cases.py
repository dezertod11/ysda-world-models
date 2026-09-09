#!/usr/bin/env python3
"""Build frozen P3d new-cell transfer and mechanism-ablation manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPLICATION_CELLS = (
    ("x0.2", 5),
    ("x0.2", 6),
    ("x0.2", 9),
    ("y0.2", 4),
    ("y0.2", 6),
    ("y0.2", 9),
    ("y0.3", 1),
    ("y0.3", 5),
)
NOVEL_CELLS = (
    ("x0.2", 2),
    ("y0.1", 4),
    ("y0.1", 6),
    ("y0.1", 8),
    ("y0.1", 9),
    ("y0.2", 7),
    ("y0.2", 8),
)


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return 50_000_000 + int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % 10_000_000


def rows_for_split(split: str) -> list[dict]:
    if split == "development":
        init_ids = range(40, 45)
    elif split == "holdout":
        init_ids = range(45, 50)
    else:
        raise ValueError(split)

    rows = []
    for cohort, cells in (
        ("replication", REPLICATION_CELLS),
        ("novel_cell", NOVEL_CELLS),
    ):
        for position_level, task_id in cells:
            for init_state_id in init_ids:
                case_id = (
                    f"p3d_{split}__{position_level.replace('.', 'p')}__task{task_id}"
                    f"__init{init_state_id}__rollout0"
                )
                rows.append(
                    {
                        "case_id": case_id,
                        "split": split,
                        "evaluation_cohort": cohort,
                        "suite": "libero_object_temp",
                        "position_level": position_level,
                        "task_id": task_id,
                        "init_state_id": init_state_id,
                        "rollout_id": 0,
                        "rollout_seed": stable_seed(
                            "p3d", split, position_level, task_id, init_state_id
                        ),
                        "independent_group": (
                            f"{position_level}|task{task_id}|init{init_state_id}"
                        ),
                    }
                )
    return rows


def build(output_dir: Path) -> dict:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {}
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "replication_cells": [list(cell) for cell in REPLICATION_CELLS],
        "novel_cells": [list(cell) for cell in NOVEL_CELLS],
    }
    for split in ("development", "holdout"):
        frame = pd.DataFrame(rows_for_split(split)).sort_values(
            ["position_level", "task_id", "init_state_id"], kind="stable"
        )
        frame.to_csv(output_dir / f"{split}_cases.csv", index=False)
        frame.to_parquet(output_dir / f"{split}_cases.parquet", index=False)
        frames[split] = frame
        metadata[split] = {
            "cases": len(frame),
            "groups": int(frame["independent_group"].nunique()),
            "cells": int(frame.groupby(["position_level", "task_id"]).ngroups),
            "replication_cases": int(frame["evaluation_cohort"].eq("replication").sum()),
            "novel_cell_cases": int(frame["evaluation_cohort"].eq("novel_cell").sum()),
            "init_state_ids": sorted(frame["init_state_id"].unique().tolist()),
        }

    development_groups = set(frames["development"]["independent_group"])
    holdout_groups = set(frames["holdout"]["independent_group"])
    overlap = development_groups & holdout_groups
    if overlap:
        raise RuntimeError(f"Development/holdout group leakage: {sorted(overlap)[:3]}")
    if set(REPLICATION_CELLS) & set(NOVEL_CELLS):
        raise RuntimeError("Replication and novel-cell cohorts overlap")
    metadata["group_overlap"] = 0
    (output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2), flush=True)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    build(parser.parse_args().output_dir)

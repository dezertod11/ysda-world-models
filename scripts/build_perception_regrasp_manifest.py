#!/usr/bin/env python3
"""Freeze non-reserve RGB-localizer calibration rows before P3 evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from recovery_proposal_utils import group_balanced_selection
except ModuleNotFoundError:
    from scripts.recovery_proposal_utils import group_balanced_selection


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(args: argparse.Namespace) -> pd.DataFrame:
    source = pd.read_parquet(args.source.expanduser().resolve())
    required = {
        "row_uid",
        "independent_group",
        "position_level",
        "task_id",
        "task_description",
    }
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"source is missing columns: {sorted(missing)}")
    if "suite" not in source:
        source["suite"] = "libero_object_temp"

    exclusion_paths = list(args.exclude)
    if args.reserve is not None:
        exclusion_paths.append(args.reserve)
    if not exclusion_paths:
        raise ValueError("at least one --exclude manifest is required")
    excluded_rows: set[str] = set()
    excluded_groups: set[str] = set()
    for path in exclusion_paths:
        excluded = pd.read_parquet(path.expanduser().resolve())
        excluded_rows.update(excluded["row_uid"].astype(str))
        excluded_groups.update(excluded["independent_group"].astype(str))
    eligible = source.loc[
        ~source["row_uid"].astype(str).isin(excluded_rows)
        & ~source["independent_group"].astype(str).isin(excluded_groups)
    ].copy()
    parts = []
    for cell_index, ((_level, _task_id), cell) in enumerate(
        eligible.groupby(["position_level", "task_id"], sort=True)
    ):
        count = len(cell) if args.per_cell == 0 else min(args.per_cell, len(cell))
        parts.append(
            group_balanced_selection(
                cell,
                count=count,
                seed=args.seed + cell_index,
            )
        )
    result = pd.concat(parts, ignore_index=True).sort_values(
        ["position_level", "task_id", "independent_group", "row_uid"], kind="stable"
    )
    if set(result["row_uid"].astype(str)) & excluded_rows:
        raise RuntimeError("an excluded row leaked into perception calibration")
    if set(result["independent_group"].astype(str)) & excluded_groups:
        raise RuntimeError("an excluded independent group leaked into perception calibration")
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    csv_path = output.with_suffix(".csv")
    result.to_csv(csv_path, index=False)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(args.source),
        "excluded_manifests": [str(path) for path in exclusion_paths],
        "seed": args.seed,
        "per_cell": args.per_cell,
        "rows": len(result),
        "groups": int(result["independent_group"].nunique()),
        "cells": int(result.groupby(["position_level", "task_id"]).ngroups),
        "csv_sha256": _sha256(csv_path),
        "excluded_row_overlap": 0,
        "excluded_group_overlap": 0,
    }
    output.with_name(output.stem + "_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--exclude",
        type=Path,
        action="append",
        default=[],
        help="Manifest whose rows and whole independent groups must be excluded.",
    )
    parser.add_argument(
        "--reserve",
        type=Path,
        help="Deprecated alias for one --exclude manifest.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-cell", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260904)
    args = parser.parse_args()
    if args.per_cell < 0:
        raise ValueError("per-cell must be non-negative (zero keeps every eligible row)")
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

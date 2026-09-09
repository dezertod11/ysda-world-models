#!/usr/bin/env python3
"""Freeze the reserve rows whose independent groups never appear in development."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(args: argparse.Namespace) -> pd.DataFrame:
    reserve = pd.read_parquet(args.reserve.expanduser().resolve())
    development = pd.read_parquet(args.development.expanduser().resolve())
    development_groups = set(development["independent_group"].astype(str))
    result = reserve.loc[
        ~reserve["independent_group"].astype(str).isin(development_groups)
    ].copy()
    result = result.sort_values(
        ["position_level", "task_id", "independent_group", "row_uid"], kind="stable"
    ).reset_index(drop=True)
    if set(result["independent_group"].astype(str)) & development_groups:
        raise RuntimeError("development group leaked into strict reserve")
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    csv_path = output.with_suffix(".csv")
    result.to_csv(csv_path, index=False)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_reserve": str(args.reserve),
        "excluded_development": str(args.development),
        "source_rows": len(reserve),
        "source_groups": int(reserve["independent_group"].nunique()),
        "rows": len(result),
        "groups": int(result["independent_group"].nunique()),
        "cells": int(result.groupby(["position_level", "task_id"]).ngroups),
        "development_group_overlap": 0,
        "csv_sha256": _sha256(csv_path),
    }
    output.with_name(output.stem + "_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reserve", type=Path, required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

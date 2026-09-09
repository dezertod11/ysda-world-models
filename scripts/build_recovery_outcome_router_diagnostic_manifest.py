#!/usr/bin/env python3
"""Select the four frozen P3e mechanism cases for diagnostic video replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DIAGNOSTIC_CASES = {
    "p3d_holdout__x0p2__task2__init47__rollout0": "full_regrasp_harm_1",
    "p3d_holdout__x0p2__task2__init49__rollout0": "full_regrasp_harm_2",
    "p3d_holdout__y0p2__task7__init49__rollout0": "router_oracle_miss_1",
    "p3d_holdout__y0p2__task9__init46__rollout0": "router_oracle_miss_2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(source: Path, output_dir: Path) -> pd.DataFrame:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    frame = pd.read_parquet(source)
    selected = frame.loc[frame["case_id"].astype(str).isin(DIAGNOSTIC_CASES)].copy()
    counts = selected["case_id"].astype(str).value_counts()
    missing = sorted(set(DIAGNOSTIC_CASES) - set(counts.index))
    duplicates = sorted(counts[counts.ne(1)].index.tolist())
    if missing or duplicates:
        raise ValueError(f"Invalid diagnostic selection: {missing=} {duplicates=}")
    selected["diagnostic_role"] = selected["case_id"].map(DIAGNOSTIC_CASES)
    selected["diagnostic_order"] = selected["case_id"].map(
        {case_id: index for index, case_id in enumerate(DIAGNOSTIC_CASES, start=1)}
    )
    selected = selected.sort_values("diagnostic_order", kind="stable").reset_index(
        drop=True
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet = output_dir / "diagnostic_cases.parquet"
    csv = output_dir / "diagnostic_cases.csv"
    selected.to_parquet(parquet, index=False)
    selected.to_csv(csv, index=False)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_manifest": str(source),
        "source_sha256": _sha256(source),
        "rows": len(selected),
        "case_ids": selected["case_id"].astype(str).tolist(),
        "roles": dict(DIAGNOSTIC_CASES),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    selected = build_manifest(args.source, args.output_dir)
    print(
        selected[["diagnostic_role", "case_id", "position_level", "task_id"]].to_string(
            index=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

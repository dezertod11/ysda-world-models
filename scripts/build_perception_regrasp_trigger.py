#!/usr/bin/env python3
"""Freeze an observation-only regrasp trigger from localizer OOF predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(args: argparse.Namespace) -> dict:
    source_path = args.oof_predictions.expanduser().resolve()
    frame = pd.read_csv(source_path)
    required = {
        "object_name",
        "score_range",
        "true_world_x",
        "true_world_y",
        "true_world_z",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"OOF table is missing columns: {sorted(missing)}")

    objects = {}
    for object_name, group in frame.groupby("object_name", sort=True):
        xyz = group[["true_world_x", "true_world_y", "true_world_z"]].to_numpy(
            dtype=np.float64
        )
        lower = np.quantile(xyz, args.workspace_lower_quantile, axis=0)
        upper = np.quantile(xyz, args.workspace_upper_quantile, axis=0)
        lower -= float(args.workspace_margin_m)
        upper += float(args.workspace_margin_m)
        objects[str(object_name)] = {
            "n_oof": int(len(group)),
            "score_range_lower": float(
                group["score_range"].quantile(args.confidence_lower_quantile)
            ),
            "workspace_lower_xyz": lower.tolist(),
            "workspace_upper_xyz": upper.tolist(),
        }

    artifact = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_oof_predictions": str(source_path),
        "source_oof_sha256": sha256(source_path),
        "calibration_policy": {
            "confidence_lower_quantile": args.confidence_lower_quantile,
            "workspace_lower_quantile": args.workspace_lower_quantile,
            "workspace_upper_quantile": args.workspace_upper_quantile,
            "workspace_margin_m": args.workspace_margin_m,
        },
        "global_conservative_score_range": args.global_score_threshold,
        "global_threshold_provenance": (
            "smallest P3b development threshold with >=10% coverage and zero "
            "wrong-object outcomes; prospectively tested only in P3c"
        ),
        "minimum_miss_distance_m": args.minimum_miss_distance_m,
        "maximum_reach_distance_m": args.maximum_reach_distance_m,
        "objects": objects,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    temporary.replace(output)
    print(json.dumps(artifact, indent=2), flush=True)
    return artifact


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--oof-predictions", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--confidence-lower-quantile", type=float, default=0.05)
    result.add_argument("--workspace-lower-quantile", type=float, default=0.01)
    result.add_argument("--workspace-upper-quantile", type=float, default=0.99)
    result.add_argument("--workspace-margin-m", type=float, default=0.06)
    result.add_argument("--global-score-threshold", type=float, default=39.579209327697754)
    result.add_argument("--minimum-miss-distance-m", type=float, default=0.08)
    result.add_argument("--maximum-reach-distance-m", type=float, default=0.50)
    return result


if __name__ == "__main__":
    build(parser().parse_args())

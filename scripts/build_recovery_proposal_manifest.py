#!/usr/bin/env python3
"""Freeze the P3 development and untouched reserve snapshot manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from analyze_signed_vof_new_task_holdout import load_pairs
    from object_contact_vof import resolve_sidecar
    from recovery_proposal_utils import DEVELOPMENT_CELLS, group_balanced_selection
except ModuleNotFoundError:
    from scripts.analyze_signed_vof_new_task_holdout import load_pairs
    from scripts.object_contact_vof import resolve_sidecar
    from scripts.recovery_proposal_utils import DEVELOPMENT_CELLS, group_balanced_selection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = (
    PROJECT_ROOT
    / "experiments/campaigns/object_contact_vof_development_20260903/analysis"
    / "object_contact_development_corpus.parquet"
)
DEFAULT_CAMPAIGNS = (
    PROJECT_ROOT / "experiments/campaigns/signed_vof_new_task_holdout_20260903",
    PROJECT_ROOT / "experiments/campaigns/invariant_cate_reserve_holdout_20260903",
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "experiments/campaigns/recovery_proposal_opportunity_20260904"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_raw(campaign_dirs: list[Path]) -> pd.DataFrame:
    parts = []
    for campaign_dir in campaign_dirs:
        frame = load_pairs(campaign_dir.expanduser().resolve())
        frame["source_campaign"] = campaign_dir.name
        frame["row_uid"] = (
            frame["source_run"].astype(str) + "|" + frame["snapshot_id"].astype(str)
        )
        parts.append(frame)
    result = pd.concat(parts, ignore_index=True)
    if result["row_uid"].duplicated().any():
        raise ValueError("Duplicate raw snapshot identities")
    return result


def build_manifests(
    corpus_path: Path,
    campaign_dirs: list[Path],
    output_dir: Path,
    *,
    per_cell: int,
    seed: int,
) -> dict[str, object]:
    corpus = pd.read_parquet(corpus_path.expanduser().resolve()).copy()
    if corpus["row_uid"].duplicated().any():
        raise ValueError("Duplicate row_uid in source corpus")
    raw = _load_raw(campaign_dirs)
    raw_columns = [
        "row_uid",
        "suite",
        "t",
        "open_loop_steps",
        "feedback_steps",
        "main_open_replay_state_max_abs",
        "open_terminal_failure_type",
        "feedback_terminal_failure_type",
        "open_terminal_final_t",
        "feedback_terminal_final_t",
        "open_terminal_episode_target_drop_candidate",
        "feedback_terminal_episode_target_drop_candidate",
        "open_terminal_episode_wrong_object_interaction_candidate",
        "feedback_terminal_episode_wrong_object_interaction_candidate",
        "open_terminal_episode_official_safety_violation",
        "feedback_terminal_episode_official_safety_violation",
    ]
    missing = sorted(set(raw_columns) - set(raw.columns))
    if missing:
        raise ValueError(f"Raw corpus lacks required fields: {missing}")
    frame = corpus.merge(raw.loc[:, raw_columns], on="row_uid", validate="one_to_one")
    both_fail = frame.loc[
        ~frame["commit_success"].astype(bool) & ~frame["feedback_success"].astype(bool)
    ].copy()

    selected_parts = []
    for cell_index, (level, task_id) in enumerate(DEVELOPMENT_CELLS):
        cell = both_fail.loc[
            both_fail["position_level"].astype(str).eq(level)
            & both_fail["task_id"].astype(int).eq(task_id)
        ].copy()
        chosen = group_balanced_selection(
            cell,
            count=per_cell,
            seed=seed + cell_index * 1009,
        )
        selected_parts.append(chosen)
    selected = pd.concat(selected_parts, ignore_index=True)
    if selected["row_uid"].duplicated().any():
        raise ValueError("Development selection contains duplicate snapshots")

    resolved_sidecars = []
    for value in selected["sidecar_path"].astype(str):
        path = resolve_sidecar(value, PROJECT_ROOT).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        resolved_sidecars.append(str(path.relative_to(PROJECT_ROOT)))
    selected["sidecar_relpath"] = resolved_sidecars
    selected["recovery_split"] = "development"

    reserve = both_fail.loc[~both_fail["row_uid"].isin(selected["row_uid"])].copy()
    reserve_sidecars = []
    for value in reserve["sidecar_path"].astype(str):
        path = resolve_sidecar(value, PROJECT_ROOT).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        reserve_sidecars.append(str(path.relative_to(PROJECT_ROOT)))
    reserve["sidecar_relpath"] = reserve_sidecars
    reserve["recovery_split"] = "untouched_reserve"

    output_dir.mkdir(parents=True, exist_ok=True)
    selected = selected.sort_values(
        ["position_level", "task_id", "independent_group", "row_uid"], kind="stable"
    ).reset_index(drop=True)
    reserve = reserve.sort_values(
        ["position_level", "task_id", "independent_group", "row_uid"], kind="stable"
    ).reset_index(drop=True)
    selected_parquet = output_dir / "frozen_development_manifest.parquet"
    selected_csv = output_dir / "frozen_development_manifest.csv"
    reserve_parquet = output_dir / "frozen_untouched_reserve_manifest.parquet"
    reserve_csv = output_dir / "frozen_untouched_reserve_manifest.csv"
    selected.to_parquet(selected_parquet, index=False)
    selected.to_csv(selected_csv, index=False)
    reserve.to_parquet(reserve_parquet, index=False)
    reserve.to_csv(reserve_csv, index=False)

    counts = (
        selected.groupby(["position_level", "task_id"], sort=True)
        .agg(rows=("row_uid", "size"), groups=("independent_group", "nunique"))
        .reset_index()
        .to_dict(orient="records")
    )
    metadata: dict[str, object] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_corpus": str(corpus_path.resolve().relative_to(PROJECT_ROOT)),
        "source_campaigns": [str(path.resolve().relative_to(PROJECT_ROOT)) for path in campaign_dirs],
        "selection_seed": seed,
        "per_cell": per_cell,
        "cells": [{"position_level": level, "task_id": task} for level, task in DEVELOPMENT_CELLS],
        "development_rows": int(len(selected)),
        "development_groups": int(selected["independent_group"].nunique()),
        "reserve_rows": int(len(reserve)),
        "counts": counts,
        "development_csv_sha256": _sha256(selected_csv),
        "reserve_csv_sha256": _sha256(reserve_csv),
    }
    (output_dir / "frozen_manifest_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--campaign-dir", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--per-cell", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260904)
    args = parser.parse_args()
    campaign_dirs = args.campaign_dir or list(DEFAULT_CAMPAIGNS)
    metadata = build_manifests(
        args.corpus,
        campaign_dirs,
        args.output_dir.expanduser().resolve(),
        per_cell=args.per_cell,
        seed=args.seed,
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

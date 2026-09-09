#!/usr/bin/env python3
"""Build a leakage-safe transition manifest from counterfactual sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FACTOR_BY_SUITE = {
    "libero_object": "ID",
    "libero_object_object": "Object",
    "libero_object_env": "Environment",
    "libero_object_temp": "Position",
}
REQUIRED_SIDECAR_KEYS = (
    "current_agentview",
    "current_wrist",
    "current_proprio",
    "candidate_actions",
    "candidate_values",
    "candidate_endpoint_agentview",
    "candidate_endpoint_wrist",
    "candidate_endpoint_proprio",
    "candidate_predicted_future_images",
    "candidate_predicted_future_wrists",
    "candidate_predicted_future_proprio",
)
PRESERVED_COLUMNS = (
    "snapshot_id",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_id",
    "rollout_seed",
    "query_idx",
    "t",
    "phase_at_snapshot",
    "task_description",
    "open_loop_steps",
    "consequence_horizon_steps",
    "prediction_mode",
    "experiment_split",
    "case_id",
    "num_candidates",
    "action_std_mean",
    "action_std_max",
    "action_first_step_l2_std",
    "action_xyz_std_mean",
    "action_rot_std_mean",
    "action_gripper_std_mean",
    "action_pairwise_l2_mean",
    "value_mean",
    "value_std",
    "value_range",
    "future_proprio_std_mean",
    "future_proprio_std_max",
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_across_seed_std_mean",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_idx",
    "candidate_seed",
    "candidate_value",
    "candidate_is_max_value",
    "candidate_first_action_l1",
    "candidate_action_chunk_l1",
    "candidate_action_chunk_l2",
    "latent_action_copy_std_mean",
    "latent_future_proprio_copy_std_mean",
    "latent_value_element_std_mean",
    "local_success",
    "local_utility_v1",
    "observed_goal_progress_delta",
    "observed_target_lift_max",
    "observed_target_drop_candidate",
    "observed_wrong_object_interaction_candidate",
    "observed_official_safety_violation",
    "prediction_error_future_image_mse",
    "prediction_error_future_wrist_mse",
    "prediction_error_future_proprio_l2",
    "terminal_available",
    "terminal_success",
    "terminal_final_t",
    "terminal_target_drop_candidate",
    "terminal_wrong_object_interaction_candidate",
    "terminal_official_safety_violation",
    "terminal_failure_type",
    "sidecar_path",
    "main_open_replay_state_max_abs",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_sidecar(path: object, project_root: Path = PROJECT_ROOT) -> Path:
    value = str(path)
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    marker = "/experiments/"
    if marker in value:
        candidate = project_root / "experiments" / value.split(marker, 1)[1]
    elif not candidate.is_absolute():
        candidate = project_root / candidate
    if not candidate.is_file():
        raise FileNotFoundError(value)
    return candidate.resolve()


def _stable_fraction(value: str, salt: str) -> float:
    digest = hashlib.sha256(f"{salt}|{value}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def assign_id_splits(
    frame: pd.DataFrame,
    *,
    train_fraction: float,
    calibration_fraction: float,
    salt: str,
) -> pd.Series:
    if train_fraction <= 0 or calibration_fraction <= 0:
        raise ValueError("ID train and calibration fractions must be positive")
    if train_fraction + calibration_fraction >= 1:
        raise ValueError("ID fractions must leave a non-empty test fraction")
    result = pd.Series("ood_test", index=frame.index, dtype="object")
    id_rows = frame.loc[frame["factor"].eq("ID")]
    for _task_id, task in id_rows.groupby("task_id", sort=True):
        groups = sorted(
            task["group_id"].astype(str).unique(),
            key=lambda value: (_stable_fraction(value, salt), value),
        )
        if len(groups) < 5:
            raise ValueError(
                "Each ID task needs at least five independent trajectory groups"
            )
        n_train = max(1, int(np.floor(len(groups) * train_fraction)))
        n_calibration = max(1, int(np.floor(len(groups) * calibration_fraction)))
        if n_train + n_calibration >= len(groups):
            n_train = len(groups) - 2
            n_calibration = 1
        split_by_group = {
            **dict.fromkeys(groups[:n_train], "train"),
            **dict.fromkeys(groups[n_train : n_train + n_calibration], "calibration"),
            **dict.fromkeys(groups[n_train + n_calibration :], "id_test"),
        }
        result.loc[task.index] = task["group_id"].map(split_by_group)
    return result


def _tables(campaign_dirs: Iterable[Path]) -> list[Path]:
    paths: set[Path] = set()
    for directory in campaign_dirs:
        directory = directory.expanduser().resolve()
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        paths.update(directory.rglob("*__candidate_outcomes.parquet"))
    if not paths:
        raise FileNotFoundError(
            "No candidate outcome tables in supplied campaign directories"
        )
    return sorted(paths)


def build_dataset(
    campaign_dirs: Iterable[Path],
    output_dir: Path,
    *,
    train_fraction: float = 0.6,
    calibration_fraction: float = 0.2,
    split_salt: str = "p4-residual-dynamics-v1",
    required_open_loop_steps: int = 16,
) -> pd.DataFrame:
    output_dir = output_dir.expanduser().resolve()
    table_paths = _tables(campaign_dirs)
    records: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    sidecar_cache: dict[Path, tuple[int, bool]] = {}
    skipped = Counter()

    for table_path in table_paths:
        table = pd.read_parquet(table_path)
        if not {"sidecar_path", "candidate_idx", "suite"}.issubset(table):
            skipped["table_schema"] += len(table)
            continue
        for row in table.to_dict(orient="records"):
            suite = str(row.get("suite", ""))
            if suite not in FACTOR_BY_SUITE:
                skipped["suite"] += 1
                continue
            if (
                int(row.get("open_loop_steps", required_open_loop_steps))
                != required_open_loop_steps
            ):
                skipped["horizon"] += 1
                continue
            try:
                sidecar = resolve_sidecar(row["sidecar_path"])
            except FileNotFoundError:
                skipped["missing_sidecar"] += 1
                continue
            candidate_idx = int(row["candidate_idx"])
            key = (str(sidecar), candidate_idx)
            if key in seen:
                skipped["duplicate"] += 1
                continue
            if sidecar not in sidecar_cache:
                try:
                    with np.load(sidecar, allow_pickle=False) as payload:
                        valid = all(name in payload for name in REQUIRED_SIDECAR_KEYS)
                        candidates = (
                            int(np.asarray(payload["candidate_actions"]).shape[0])
                            if valid
                            else 0
                        )
                except (OSError, ValueError, KeyError):
                    valid, candidates = False, 0
                sidecar_cache[sidecar] = (candidates, valid)
            candidates, valid = sidecar_cache[sidecar]
            if not valid or not 0 <= candidate_idx < candidates:
                skipped["invalid_sidecar"] += 1
                continue
            seen.add(key)
            task_id = int(row["task_id"])
            init_state_id = int(row["init_state_id"])
            rollout_id = int(row.get("rollout_id", 0))
            rollout_seed = int(row.get("rollout_seed", 0))
            group_id = (
                f"{suite}|task{task_id}|init{init_state_id}|rollout{rollout_id}"
                f"|seed{rollout_seed}"
            )
            relative = (
                str(sidecar.relative_to(PROJECT_ROOT))
                if sidecar.is_relative_to(PROJECT_ROOT)
                else str(sidecar)
            )
            compact = {
                column: row.get(column) for column in PRESERVED_COLUMNS if column in row
            }
            compact.update(
                {
                    "row_uid": hashlib.sha256(
                        f"{relative}|{candidate_idx}".encode()
                    ).hexdigest(),
                    "factor": FACTOR_BY_SUITE[suite],
                    "group_id": group_id,
                    "snapshot_group": hashlib.sha256(relative.encode()).hexdigest(),
                    "sidecar_path": relative,
                    "candidate_idx": candidate_idx,
                    "source_table": str(table_path),
                }
            )
            records.append(compact)

    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("No valid residual-dynamics transitions were found")
    if frame["row_uid"].duplicated().any():
        raise ValueError("Duplicate row_uid after sidecar deduplication")
    frame["split"] = assign_id_splits(
        frame,
        train_fraction=train_fraction,
        calibration_fraction=calibration_fraction,
        salt=split_salt,
    )
    leakage = frame.groupby("group_id")["split"].nunique()
    if int(leakage.max()) != 1:
        raise RuntimeError("At least one trajectory group crosses dataset splits")
    frame = frame.sort_values(
        ["split", "factor", "task_id", "group_id", "snapshot_group", "candidate_idx"],
        kind="stable",
    ).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    parquet = output_dir / "transition_manifest.parquet"
    csv = output_dir / "transition_manifest.csv"
    frame.to_parquet(parquet, index=False)
    frame.to_csv(csv, index=False)
    counts = (
        frame.groupby(["split", "factor"], dropna=False)
        .agg(
            rows=("row_uid", "size"),
            groups=("group_id", "nunique"),
            snapshots=("snapshot_group", "nunique"),
        )
        .reset_index()
    )
    counts.to_csv(output_dir / "split_counts.csv", index=False)
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "campaign_dirs": [
            str(Path(path).expanduser().resolve()) for path in campaign_dirs
        ],
        "source_tables": len(table_paths),
        "rows": len(frame),
        "groups": int(frame["group_id"].nunique()),
        "snapshots": int(frame["snapshot_group"].nunique()),
        "split_salt": split_salt,
        "train_fraction": train_fraction,
        "calibration_fraction": calibration_fraction,
        "required_open_loop_steps": required_open_loop_steps,
        "skipped": dict(skipped),
        "manifest_sha256": sha256_file(parquet),
    }
    (output_dir / "dataset.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--calibration-fraction", type=float, default=0.2)
    parser.add_argument("--split-salt", default="p4-residual-dynamics-v1")
    parser.add_argument("--required-open-loop-steps", type=int, default=16)
    args = parser.parse_args()
    frame = build_dataset(
        args.campaign_dir,
        args.output_dir,
        train_fraction=args.train_fraction,
        calibration_fraction=args.calibration_fraction,
        split_salt=args.split_salt,
        required_open_loop_steps=args.required_open_loop_steps,
    )
    print(
        frame.groupby(["split", "factor"])
        .agg(rows=("row_uid", "size"), groups=("group_id", "nunique"))
        .to_string()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

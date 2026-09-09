#!/usr/bin/env python3
"""Collect RGB/mask supervision for a frozen perception-backed regrasp head."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import mujoco
import numpy as np
import pandas as pd
from libero.libero import benchmark
from robosuite.utils.camera_utils import (
    get_camera_extrinsic_matrix,
    get_camera_intrinsic_matrix,
    get_camera_transform_matrix,
    project_points_from_world_to_camera,
)

from cosmos_policy.experiments.robot.libero.libero_utils import get_libero_env
from cosmos_policy.experiments.robot.libero.safety_signals import SafetySignalTracker
from libero_runtime_snapshot import restore_libero_runtime_state, runtime_snapshot_from_arrays
from perception_regrasp import canonical_object_name
from recovery_proposal_utils import cartesian_servo_action


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_sidecar(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        return {key: np.asarray(payload[key]).copy() for key in payload.files}


def _target_position(tracker: SafetySignalTracker, obs: Mapping[str, Any]) -> tuple[str, np.ndarray]:
    positions = tracker._object_positions(obs)
    for name in tracker.target_objects:
        if name in positions:
            return name, np.asarray(positions[name], dtype=np.float64)[:3]
    raise RuntimeError(f"target position is unavailable for {tracker.target_objects}")


def _eef_position(obs: Mapping[str, Any]) -> np.ndarray:
    value = np.asarray(obs.get("robot0_eef_pos", []), dtype=np.float64).reshape(-1)
    if value.size < 3:
        raise RuntimeError("robot0_eef_pos is unavailable")
    return value[:3]


def _step_actions(env: Any, actions: Sequence[Sequence[float]]) -> Mapping[str, Any]:
    obs: Mapping[str, Any] | None = None
    for action in actions:
        obs, _reward, done, _info = env.step(np.asarray(action, dtype=np.float32).tolist())
        if done:
            break
    if obs is None:
        raise ValueError("at least one action is required")
    return obs


def _retreat_open(env: Any, obs: Mapping[str, Any]) -> Mapping[str, Any]:
    target = _eef_position(obs) + np.asarray([0.0, 0.0, 0.08])
    for _ in range(3):
        eef = _eef_position(obs)
        if np.linalg.norm(target - eef) <= 0.015:
            break
        action = cartesian_servo_action(eef, target, gripper=-1.0)
        obs, _reward, done, _info = env.step(action.tolist())
        if done:
            break
    return obs


def render_segmentation_compat(sim: Any, camera_name: str, height: int, width: int) -> np.ndarray:
    """Render geom IDs while avoiding the robosuite/NumPy-2 uint8 overflow."""
    context = sim._render_context_offscreen
    camera_id = sim.model.camera_name2id(camera_name)
    context.render(width=width, height=height, camera_id=camera_id, segmentation=True)
    viewport = mujoco.MjrRect(0, 0, width, height)
    encoded = np.empty((height, width, 3), dtype=np.uint8)
    mujoco.mjr_readPixels(rgb=encoded, depth=None, viewport=viewport, con=context.con)
    channels = encoded.astype(np.uint32)
    segment_index = channels[:, :, 0] + channels[:, :, 1] * 256 + channels[:, :, 2] * 65536
    segment_index[segment_index >= context.scn.ngeom + 1] = 0
    ids = np.full((context.scn.ngeom + 1, 2), -1, dtype=np.int32)
    for index in range(context.scn.ngeom):
        geom = context.scn.geoms[index]
        if geom.segid != -1:
            ids[geom.segid + 1, 0] = geom.objtype
            ids[geom.segid + 1, 1] = geom.objid
    return ids[segment_index][::-1]


def _target_geom_ids(sim: Any, instance_name: str) -> list[int]:
    token = instance_name.lower()
    result = []
    for geom_id in range(sim.model.ngeom):
        name = str(sim.model.geom_id2name(geom_id) or "").lower()
        if token in name:
            result.append(geom_id)
    return result


def _portable_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def collect(args: argparse.Namespace) -> pd.DataFrame:
    manifest = pd.read_parquet(args.manifest.expanduser().resolve())
    manifest = manifest.loc[
        manifest["position_level"].astype(str).eq(args.position_level)
        & manifest["task_id"].astype(int).eq(args.task_id)
    ].sort_values(["independent_group", "row_uid"], kind="stable")
    if args.max_states > 0:
        manifest = manifest.head(args.max_states)
    if manifest.empty:
        raise ValueError("calibration shard is empty")

    output_dir = args.output_dir.expanduser().resolve()
    sample_dir = output_dir / f"{args.run_name}__samples"
    sample_dir.mkdir(parents=True, exist_ok=True)
    table_path = output_dir / f"{args.run_name}__calibration.csv"
    rows = pd.read_csv(table_path).to_dict(orient="records") if args.resume and table_path.exists() else []
    completed = {str(row["row_uid"]) for row in rows}

    task_suite = benchmark.get_benchmark_dict()[str(manifest.iloc[0]["suite"])]()
    task = task_suite.get_task(args.task_id)
    env, _ = get_libero_env(task, "cosmos_policy", resolution=args.resolution)
    try:
        for row in manifest.itertuples(index=False):
            if str(row.row_uid) in completed:
                continue
            sidecar_value = getattr(row, "sidecar_relpath", None) or getattr(
                row, "sidecar_path", None
            )
            if not sidecar_value:
                raise ValueError(f"row {row.row_uid} has no sidecar path")
            sidecar = Path(str(sidecar_value))
            if sidecar.is_absolute() and not sidecar.exists() and "/experiments/" in str(sidecar):
                sidecar = PROJECT_ROOT / "experiments" / str(sidecar).split("/experiments/", 1)[1]
            if not sidecar.is_absolute():
                sidecar = PROJECT_ROOT / sidecar
            payload = _load_sidecar(sidecar)
            obs = restore_libero_runtime_state(env, runtime_snapshot_from_arrays(payload))
            selected = int(np.asarray(payload["selected_max_value_idx"]).item())
            obs = _step_actions(env, np.asarray(payload["candidate_actions"])[selected, :8])
            obs = _retreat_open(env, obs)
            tracker = SafetySignalTracker(env, obs)
            instance_name, world_position = _target_position(tracker, obs)
            segmentation = render_segmentation_compat(
                env.sim, "agentview", args.resolution, args.resolution
            )
            geom_ids = _target_geom_ids(env.sim, instance_name)
            target_mask = np.isin(segmentation[:, :, 1], geom_ids)
            image = np.asarray(obs["agentview_image"], dtype=np.uint8)
            intrinsic = get_camera_intrinsic_matrix(
                env.sim, "agentview", args.resolution, args.resolution
            )
            camera_to_world = get_camera_extrinsic_matrix(env.sim, "agentview")
            transform = get_camera_transform_matrix(
                env.sim, "agentview", args.resolution, args.resolution
            )
            projected = project_points_from_world_to_camera(
                world_position[None], transform, args.resolution, args.resolution
            )[0]
            sample_path = sample_dir / f"{row.snapshot_id}.npz"
            np.savez_compressed(
                sample_path,
                image=image,
                target_mask=target_mask.astype(np.uint8),
                target_world_position=world_position,
                target_pixel_rc=projected,
                camera_intrinsic=intrinsic,
                camera_to_world=camera_to_world,
            )
            rows.append(
                {
                    "row_uid": str(row.row_uid),
                    "snapshot_id": str(row.snapshot_id),
                    "independent_group": str(row.independent_group),
                    "position_level": str(row.position_level),
                    "task_id": int(row.task_id),
                    "task_description": str(row.task_description),
                    "object_name": canonical_object_name(instance_name),
                    "visible_pixels": int(target_mask.sum()),
                    "sample_path": _portable_path(sample_path),
                }
            )
            pd.DataFrame(rows).to_csv(table_path, index=False)
            completed.add(str(row.row_uid))
            print(
                f"[perception-calibration] {len(completed)}/{len(manifest)} "
                f"object={instance_name} visible={int(target_mask.sum())}",
                flush=True,
            )
    finally:
        env.close()

    result = pd.DataFrame(rows)
    result.to_parquet(table_path.with_suffix(".parquet"), index=False)
    completion = {
        "run_name": args.run_name,
        "completed": len(completed) == len(manifest),
        "completed_rows": len(completed),
        "expected_rows": len(manifest),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (output_dir / f"{args.run_name}__completed.json").write_text(
        json.dumps(completion, indent=2), encoding="utf-8"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--position-level", required=True)
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--max-states", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    rows = collect(build_parser().parse_args())
    print(f"[perception-calibration] wrote {len(rows)} rows", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

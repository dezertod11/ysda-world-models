#!/usr/bin/env python3
"""Train and group-cross-validate the RGB heatmap regrasp localizer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from perception_regrasp import (
        HEATMAP_LOCALIZER_TYPE,
        build_deeplab_heatmap_model,
        forward_deeplab_heatmap,
        heatmap_depth_features,
        pixel_to_world_plane,
        predict_ridge,
        weighted_ridge,
    )
except ModuleNotFoundError:
    from scripts.perception_regrasp import (
        HEATMAP_LOCALIZER_TYPE,
        build_deeplab_heatmap_model,
        forward_deeplab_heatmap,
        heatmap_depth_features,
        pixel_to_world_plane,
        predict_ridge,
        weighted_ridge,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


def _stable_fold(value: str, folds: int) -> int:
    digest = hashlib.sha256(str(value).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % folds


def _resolve(path: str) -> Path:
    result = Path(path)
    if result.is_absolute() and result.exists():
        return result
    if "/experiments/" in str(result):
        return PROJECT_ROOT / "experiments" / str(result).split("/experiments/", 1)[1]
    return result if result.is_absolute() else PROJECT_ROOT / result


def _load_rows(root: Path, folds: int) -> pd.DataFrame:
    paths = sorted(root.rglob("*__calibration.csv"))
    if not paths:
        raise FileNotFoundError(f"no calibration shards under {root}")
    frame = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    if frame["row_uid"].duplicated().any():
        duplicates = frame.loc[frame["row_uid"].duplicated(), "row_uid"].head().tolist()
        raise ValueError(f"duplicate calibration rows: {duplicates}")
    frame = frame.sort_values(
        ["object_name", "independent_group", "row_uid"], kind="stable"
    ).reset_index(drop=True)
    frame["fold"] = frame["independent_group"].map(
        lambda value: _stable_fold(str(value), folds)
    )
    return frame


def _load_arrays(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    arrays: dict[str, list[np.ndarray]] = {
        "images": [],
        "target_masks": [],
        "true_pixels": [],
        "true_world": [],
        "intrinsics": [],
        "camera_to_world": [],
    }
    for row in frame.itertuples(index=False):
        with np.load(_resolve(str(row.sample_path)), allow_pickle=False) as payload:
            arrays["images"].append(np.asarray(payload["image"], dtype=np.uint8))
            arrays["target_masks"].append(
                np.asarray(payload["target_mask"], dtype=np.bool_)
            )
            arrays["true_pixels"].append(
                np.asarray(payload["target_pixel_rc"], dtype=np.float32)
            )
            arrays["true_world"].append(
                np.asarray(payload["target_world_position"], dtype=np.float32)
            )
            arrays["intrinsics"].append(
                np.asarray(payload["camera_intrinsic"], dtype=np.float64)
            )
            arrays["camera_to_world"].append(
                np.asarray(payload["camera_to_world"], dtype=np.float64)
            )
    return {name: np.stack(values) for name, values in arrays.items()}


def _normalized_images(images: Any, device: str) -> Any:
    import torch

    values = images.to(device=device, dtype=torch.float32, non_blocking=True)
    values = values.permute(0, 3, 1, 2) / 255.0
    mean = torch.as_tensor(IMAGE_MEAN, device=device)[None, :, None, None]
    scale = torch.as_tensor(IMAGE_STD, device=device)[None, :, None, None]
    return (values - mean) / scale


def _train_model(
    frame: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    object_names: list[str],
    *,
    device: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    depth_weight: float,
    seed: int,
) -> Any:
    import torch
    from torch.nn import functional
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_float32_matmul_precision("high")
    object_lookup = {name: index for index, name in enumerate(object_names)}
    object_indices = np.asarray(
        [object_lookup[str(value)] for value in frame["object_name"]], dtype=np.int64
    )
    dataset = TensorDataset(
        torch.from_numpy(arrays["images"][indices]),
        torch.from_numpy(arrays["target_masks"][indices]),
        torch.from_numpy(object_indices[indices]),
        torch.from_numpy(arrays["true_pixels"][indices]),
        torch.from_numpy(arrays["true_world"][indices, 2]),
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
        generator=generator,
    )
    model = build_deeplab_heatmap_model(len(object_names), pretrained=True).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        total_heatmap = 0.0
        total_depth = 0.0
        for images, target_masks, objects, pixels, target_z in loader:
            images = _normalized_images(images, device)
            target_masks = target_masks.to(device, non_blocking=True)
            objects = objects.to(device, non_blocking=True)
            pixels = pixels.to(device, non_blocking=True)
            target_z = target_z.to(device, non_blocking=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                output = forward_deeplab_heatmap(model, images, detach_depth=True)
                batch = torch.arange(len(images), device=device)
                selected = output["out"][batch, objects]
                height, width = selected.shape[-2:]
                target_index = (
                    pixels[:, 0].round().long().clamp(0, height - 1) * width
                    + pixels[:, 1].round().long().clamp(0, width - 1)
                )
                heatmap_loss = functional.cross_entropy(
                    selected.flatten(1), target_index, label_smoothing=0.001
                )
                if "aux" in output:
                    auxiliary = output["aux"][batch, objects]
                    heatmap_loss = heatmap_loss + 0.3 * functional.cross_entropy(
                        auxiliary.flatten(1), target_index, label_smoothing=0.001
                    )
                predicted_global_z = output["depth"][batch, objects].float()
                global_depth_loss = functional.smooth_l1_loss(
                    predicted_global_z, target_z, beta=0.02
                )
                predicted_local_z = output["depth_map"][batch, objects].float()
                expanded_z = target_z[:, None, None].expand_as(predicted_local_z)
                local_depth_loss = functional.smooth_l1_loss(
                    predicted_local_z[target_masks],
                    expanded_z[target_masks],
                    beta=0.02,
                )
                depth_loss = global_depth_loss + 0.25 * local_depth_loss
                loss = heatmap_loss + depth_weight * depth_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total_loss += float(loss.detach()) * len(images)
            total_heatmap += float(heatmap_loss.detach()) * len(images)
            total_depth += float(depth_loss.detach()) * len(images)
        count = len(dataset)
        print(
            f"[heatmap-train] epoch={epoch + 1}/{epochs} rows={count} "
            f"loss={total_loss / count:.5f} heatmap={total_heatmap / count:.5f} "
            f"depth={total_depth / count:.5f}",
            flush=True,
        )
    return model


def _predict(
    model: Any,
    frame: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
    object_names: list[str],
    object_plane_z: dict[str, float],
    depth_bounds: tuple[float, float],
    *,
    device: str,
    batch_size: int,
) -> pd.DataFrame:
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    object_lookup = {name: index for index, name in enumerate(object_names)}
    object_indices = np.asarray(
        [object_lookup[str(value)] for value in frame["object_name"]], dtype=np.int64
    )
    dataset = TensorDataset(
        torch.from_numpy(arrays["images"][indices]),
        torch.from_numpy(object_indices[indices]),
        torch.from_numpy(indices.astype(np.int64)),
    )
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )
    rows: list[dict[str, Any]] = []
    model.eval()
    with torch.inference_mode():
        for images, objects, source_indices in loader:
            images = _normalized_images(images, device)
            objects = objects.to(device, non_blocking=True)
            output = forward_deeplab_heatmap(model, images)
            batch = torch.arange(len(images), device=device)
            selected = output["out"][batch, objects].float()
            height, width = selected.shape[-2:]
            flat = selected.flatten(1)
            best = flat.argmax(dim=1).cpu().numpy()
            neural_z = output["depth"][batch, objects].float().cpu().numpy()
            local_depth_maps = output["depth_map"][batch, objects].float().cpu().numpy()
            probabilities = flat.softmax(dim=1)
            peaks = probabilities.max(dim=1).values.cpu().numpy()
            entropies = (
                -(probabilities * probabilities.clamp_min(1e-12).log()).sum(dim=1)
                / math.log(height * width)
            ).cpu().numpy()
            score_ranges = (
                flat.max(dim=1).values - flat.min(dim=1).values
            ).cpu().numpy()
            for offset, source_index in enumerate(source_indices.numpy()):
                source_index = int(source_index)
                row = frame.iloc[source_index]
                object_name = str(row["object_name"])
                predicted_pixel = np.asarray(
                    [best[offset] // width, best[offset] % width], dtype=np.float64
                )
                true_pixel = arrays["true_pixels"][source_index].astype(np.float64)
                true_world = arrays["true_world"][source_index].astype(np.float64)
                z_neural_global = float(np.clip(neural_z[offset], *depth_bounds))
                z_neural_local = float(
                    np.clip(
                        local_depth_maps[offset, int(predicted_pixel[0]), int(predicted_pixel[1])],
                        *depth_bounds,
                    )
                )
                z_median = float(object_plane_z[object_name])
                world_neural_global = pixel_to_world_plane(
                    predicted_pixel[0],
                    predicted_pixel[1],
                    arrays["intrinsics"][source_index],
                    arrays["camera_to_world"][source_index],
                    z_neural_global,
                )
                world_neural_local = pixel_to_world_plane(
                    predicted_pixel[0],
                    predicted_pixel[1],
                    arrays["intrinsics"][source_index],
                    arrays["camera_to_world"][source_index],
                    z_neural_local,
                )
                world_median = pixel_to_world_plane(
                    predicted_pixel[0],
                    predicted_pixel[1],
                    arrays["intrinsics"][source_index],
                    arrays["camera_to_world"][source_index],
                    z_median,
                )
                rows.append(
                    {
                        "row_uid": str(row["row_uid"]),
                        "independent_group": str(row["independent_group"]),
                        "position_level": str(row["position_level"]),
                        "task_id": int(row["task_id"]),
                        "object_name": object_name,
                        "fold": int(row["fold"]),
                        "true_pixel_row": float(true_pixel[0]),
                        "true_pixel_col": float(true_pixel[1]),
                        "predicted_pixel_row": float(predicted_pixel[0]),
                        "predicted_pixel_col": float(predicted_pixel[1]),
                        "pixel_l2": float(np.linalg.norm(predicted_pixel - true_pixel)),
                        "true_world_x": float(true_world[0]),
                        "true_world_y": float(true_world[1]),
                        "true_world_z": float(true_world[2]),
                        "predicted_z_neural_global": z_neural_global,
                        "predicted_z_neural_local": z_neural_local,
                        "predicted_z_object_median": z_median,
                        "z_abs_neural_global": float(
                            abs(z_neural_global - true_world[2])
                        ),
                        "z_abs_neural_local": float(
                            abs(z_neural_local - true_world[2])
                        ),
                        "z_abs_object_median": float(abs(z_median - true_world[2])),
                        "world_xy_l2_neural_global": float(
                            np.linalg.norm(world_neural_global[:2] - true_world[:2])
                        ),
                        "world_xy_l2_neural_local": float(
                            np.linalg.norm(world_neural_local[:2] - true_world[:2])
                        ),
                        "world_xy_l2_object_median": float(
                            np.linalg.norm(world_median[:2] - true_world[:2])
                        ),
                        "world_xyz_l2_neural_global": float(
                            np.linalg.norm(world_neural_global - true_world)
                        ),
                        "world_xyz_l2_neural_local": float(
                            np.linalg.norm(world_neural_local - true_world)
                        ),
                        "world_xyz_l2_object_median": float(
                            np.linalg.norm(world_median - true_world)
                        ),
                        "peak_probability": float(peaks[offset]),
                        "entropy": float(entropies[offset]),
                        "score_range": float(score_ranges[offset]),
                    }
                )
    return pd.DataFrame(rows)


def _depth_bounds(arrays: dict[str, np.ndarray]) -> tuple[float, float]:
    values = arrays["true_world"][:, 2]
    return (
        float(max(0.0, np.quantile(values, 0.005) - 0.02)),
        float(np.quantile(values, 0.995) + 0.02),
    )


def _standardize(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = features.mean(axis=0).astype(np.float32)
    scale = features.std(axis=0).astype(np.float32)
    scale = np.where(scale < 1e-5, 1.0, scale).astype(np.float32)
    return (features - mean) / scale, mean, scale


def _depth_feature_matrix(
    predictions: pd.DataFrame, object_names: list[str]
) -> np.ndarray:
    lookup = {name: index for index, name in enumerate(object_names)}
    return np.stack(
        [
            heatmap_depth_features(
                float(row.predicted_z_neural_global),
                float(row.predicted_z_neural_local),
                float(row.predicted_pixel_row),
                float(row.predicted_pixel_col),
                256,
                256,
                lookup[str(row.object_name)],
                len(object_names),
            )
            for row in predictions.itertuples(index=False)
        ]
    )


def _errors_for_depth(
    predictions: pd.DataFrame,
    predicted_z: np.ndarray,
    frame: pd.DataFrame,
    arrays: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source_lookup = {
        str(row_uid): index for index, row_uid in enumerate(frame["row_uid"].astype(str))
    }
    xy_errors = []
    xyz_errors = []
    z_errors = []
    for row, plane_z in zip(predictions.itertuples(index=False), predicted_z):
        index = source_lookup[str(row.row_uid)]
        true_world = arrays["true_world"][index].astype(np.float64)
        predicted_world = pixel_to_world_plane(
            float(row.predicted_pixel_row),
            float(row.predicted_pixel_col),
            arrays["intrinsics"][index],
            arrays["camera_to_world"][index],
            float(plane_z),
        )
        xy_errors.append(np.linalg.norm(predicted_world[:2] - true_world[:2]))
        xyz_errors.append(np.linalg.norm(predicted_world - true_world))
        z_errors.append(abs(float(plane_z) - true_world[2]))
    return np.asarray(xy_errors), np.asarray(xyz_errors), np.asarray(z_errors)


def _crossfit_depth_calibrator(
    predictions: pd.DataFrame,
    frame: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    object_names: list[str],
    depth_bounds: tuple[float, float],
    alphas: list[float],
) -> tuple[np.ndarray, float, pd.DataFrame]:
    features = _depth_feature_matrix(predictions, object_names)
    targets = predictions["true_world_z"].to_numpy(dtype=np.float32)
    folds = predictions["fold"].to_numpy(dtype=int)
    candidates = []
    candidate_predictions: dict[float, np.ndarray] = {}
    for alpha in alphas:
        values = np.full(len(predictions), np.nan, dtype=np.float32)
        for fold in sorted(set(folds)):
            train_indices = np.flatnonzero(folds != fold)
            test_indices = np.flatnonzero(folds == fold)
            standardized, mean, scale = _standardize(features[train_indices])
            head = weighted_ridge(
                standardized,
                targets[train_indices],
                alpha=alpha,
                positive_weight=1.0,
            )
            values[test_indices] = predict_ridge(
                (features[test_indices] - mean) / scale, head
            )
        values = np.clip(values, depth_bounds[0], depth_bounds[1])
        xy, _xyz, z = _errors_for_depth(predictions, values, frame, arrays)
        candidates.append(
            {
                "alpha": alpha,
                "median_world_xy_l2": float(np.median(xy)),
                "p90_world_xy_l2": float(np.quantile(xy, 0.9)),
                "median_world_z_abs": float(np.median(z)),
                "p90_world_z_abs": float(np.quantile(z, 0.9)),
            }
        )
        candidate_predictions[alpha] = values
    table = pd.DataFrame(candidates).sort_values(
        ["p90_world_xy_l2", "p90_world_z_abs", "median_world_xy_l2", "alpha"],
        kind="stable",
    )
    best_alpha = float(table.iloc[0]["alpha"])
    return candidate_predictions[best_alpha], best_alpha, table


def _select_object_depth_modes(
    predictions: pd.DataFrame,
    modes: list[str],
    *,
    gate_p90_z_m: float,
) -> tuple[dict[str, str], pd.DataFrame]:
    """Choose a tail-robust depth estimator for each language-known object."""
    rows: list[dict[str, Any]] = []
    selections: dict[str, str] = {}
    for object_name, group in predictions.groupby("object_name", sort=True):
        candidates: list[dict[str, Any]] = []
        for mode in modes:
            candidate = {
                "object_name": str(object_name),
                "rows": len(group),
                "mode": mode,
                "median_world_xy_l2": float(
                    group[f"world_xy_l2_{mode}"].median()
                ),
                "p90_world_xy_l2": float(
                    group[f"world_xy_l2_{mode}"].quantile(0.9)
                ),
                "median_world_z_abs": float(group[f"z_abs_{mode}"].median()),
                "p90_world_z_abs": float(group[f"z_abs_{mode}"].quantile(0.9)),
            }
            candidate["z_gate_eligible"] = bool(
                candidate["p90_world_z_abs"] <= gate_p90_z_m
            )
            candidates.append(candidate)
        eligible = [row for row in candidates if row["z_gate_eligible"]]
        pool = eligible or candidates
        selected = min(
            pool,
            key=lambda row: (
                row["p90_world_xy_l2"],
                row["p90_world_z_abs"],
                row["median_world_xy_l2"],
                row["mode"],
            ),
        )
        selections[str(object_name)] = str(selected["mode"])
        for row in candidates:
            row["selected"] = row["mode"] == selected["mode"]
            row["used_z_gate_fallback"] = not bool(eligible)
            rows.append(row)
    return selections, pd.DataFrame(rows)


def run_fold(args: argparse.Namespace) -> int:
    if args.fold is None or not 0 <= args.fold < args.folds:
        raise ValueError("--fold must identify one cross-validation fold")
    frame = _load_rows(args.calibration_dir.expanduser().resolve(), args.folds)
    arrays = _load_arrays(frame)
    object_names = sorted(frame["object_name"].astype(str).unique())
    train_indices = np.flatnonzero(frame["fold"].to_numpy() != args.fold)
    test_indices = np.flatnonzero(frame["fold"].to_numpy() == args.fold)
    object_plane_z = {
        name: float(
            np.median(
                arrays["true_world"][
                    train_indices[
                        frame.iloc[train_indices]["object_name"].astype(str).eq(name).to_numpy()
                    ],
                    2,
                ]
            )
        )
        for name in object_names
    }
    model = _train_model(
        frame,
        arrays,
        train_indices,
        object_names,
        device=args.device,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        depth_weight=args.depth_weight,
        seed=args.seed + args.fold,
    )
    predictions = _predict(
        model,
        frame,
        arrays,
        test_indices,
        object_names,
        object_plane_z,
        _depth_bounds(arrays),
        device=args.device,
        batch_size=args.batch_size,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(
        args.output_dir / f"heatmap_fold_{args.fold}_predictions.csv", index=False
    )
    fold_summary = {
        "fold": args.fold,
        "train_rows": len(train_indices),
        "test_rows": len(test_indices),
        "median_pixel_l2": float(predictions["pixel_l2"].median()),
        "p90_pixel_l2": float(predictions["pixel_l2"].quantile(0.9)),
    }
    (args.output_dir / f"heatmap_fold_{args.fold}_summary.json").write_text(
        json.dumps(fold_summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(fold_summary, indent=2), flush=True)
    return 0


def finalize(args: argparse.Namespace) -> int:
    import torch

    frame = _load_rows(args.calibration_dir.expanduser().resolve(), args.folds)
    arrays = _load_arrays(frame)
    object_names = sorted(frame["object_name"].astype(str).unique())
    paths = [
        args.output_dir / f"heatmap_fold_{fold}_predictions.csv"
        for fold in range(args.folds)
    ]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing fold predictions: {missing}")
    predictions = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    expected = set(frame["row_uid"].astype(str))
    actual = set(predictions["row_uid"].astype(str))
    if len(predictions) != len(frame) or actual != expected:
        raise ValueError("fold predictions do not cover the calibration rows exactly once")

    depth_bounds = _depth_bounds(arrays)
    stacked_z, depth_calibration_alpha, depth_calibration_table = (
        _crossfit_depth_calibrator(
            predictions,
            frame,
            arrays,
            object_names,
            depth_bounds,
            [0.01, 0.1, 1.0, 10.0, 100.0],
        )
    )
    stacked_xy, stacked_xyz, stacked_z_abs = _errors_for_depth(
        predictions, stacked_z, frame, arrays
    )
    predictions["predicted_z_stacked_ridge"] = stacked_z
    predictions["z_abs_stacked_ridge"] = stacked_z_abs
    predictions["world_xy_l2_stacked_ridge"] = stacked_xy
    predictions["world_xyz_l2_stacked_ridge"] = stacked_xyz
    base_depth_modes = [
        "neural_global",
        "neural_local",
        "object_median",
        "stacked_ridge",
    ]
    object_depth_modes, object_depth_table = _select_object_depth_modes(
        predictions,
        base_depth_modes,
        gate_p90_z_m=args.gate_p90_z_m,
    )
    for metric in ("predicted_z", "z_abs", "world_xy_l2", "world_xyz_l2"):
        predictions[f"{metric}_object_routed"] = [
            row[f"{metric}_{object_depth_modes[str(row['object_name'])]}"]
            for _, row in predictions.iterrows()
        ]
    depth_rows = []
    for mode in (*base_depth_modes, "object_routed"):
        depth_rows.append(
            {
                "mode": mode,
                "median_world_xy_l2": float(
                    predictions[f"world_xy_l2_{mode}"].median()
                ),
                "p90_world_xy_l2": float(
                    predictions[f"world_xy_l2_{mode}"].quantile(0.9)
                ),
                "median_world_z_abs": float(predictions[f"z_abs_{mode}"].median()),
                "p90_world_z_abs": float(
                    predictions[f"z_abs_{mode}"].quantile(0.9)
                ),
            }
        )
    depth_table = pd.DataFrame(depth_rows)
    eligible_depth = depth_table.loc[
        depth_table["p90_world_z_abs"] <= args.gate_p90_z_m
    ]
    selection_table = eligible_depth if not eligible_depth.empty else depth_table
    depth_mode = str(
        selection_table.sort_values(
            ["p90_world_xy_l2", "p90_world_z_abs", "median_world_xy_l2"],
            kind="stable",
        ).iloc[0]["mode"]
    )
    suffix = depth_mode
    predictions["world_xy_l2"] = predictions[f"world_xy_l2_{suffix}"]
    predictions["world_xyz_l2"] = predictions[f"world_xyz_l2_{suffix}"]
    predictions["world_z_abs"] = predictions[f"z_abs_{suffix}"]
    per_object = (
        predictions.groupby("object_name", as_index=False)
        .agg(
            rows=("row_uid", "size"),
            median_pixel_l2=("pixel_l2", "median"),
            p90_pixel_l2=("pixel_l2", lambda values: np.quantile(values, 0.9)),
            median_world_xy_l2=("world_xy_l2", "median"),
            p90_world_xy_l2=("world_xy_l2", lambda values: np.quantile(values, 0.9)),
            median_world_z_abs=("world_z_abs", "median"),
        )
        .sort_values("object_name")
    )
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "localizer_type": HEATMAP_LOCALIZER_TYPE,
        "rows": len(frame),
        "groups": int(frame["independent_group"].nunique()),
        "objects": object_names,
        "folds": args.folds,
        "epochs": args.epochs,
        "full_epochs": args.full_epochs,
        "depth_mode": depth_mode,
        "depth_mode_by_object": object_depth_modes,
        "median_pixel_l2": float(predictions["pixel_l2"].median()),
        "p90_pixel_l2": float(predictions["pixel_l2"].quantile(0.9)),
        "median_world_xy_l2": float(predictions["world_xy_l2"].median()),
        "mean_world_xy_l2": float(predictions["world_xy_l2"].mean()),
        "p90_world_xy_l2": float(predictions["world_xy_l2"].quantile(0.9)),
        "median_world_z_abs": float(predictions["world_z_abs"].median()),
        "p90_world_z_abs": float(predictions["world_z_abs"].quantile(0.9)),
        "median_world_xyz_l2": float(predictions["world_xyz_l2"].median()),
        "depth_calibration_alpha": depth_calibration_alpha,
        "neural_global_depth_p90": float(
            predictions["z_abs_neural_global"].quantile(0.9)
        ),
        "neural_local_depth_p90": float(
            predictions["z_abs_neural_local"].quantile(0.9)
        ),
        "object_median_depth_p90": float(
            predictions["z_abs_object_median"].quantile(0.9)
        ),
        "stacked_ridge_depth_p90": float(
            predictions["z_abs_stacked_ridge"].quantile(0.9)
        ),
    }
    summary["localization_gate_pass"] = bool(
        summary["median_world_xy_l2"] <= args.gate_median_m
        and summary["p90_world_xy_l2"] <= args.gate_p90_m
        and summary["p90_world_z_abs"] <= args.gate_p90_z_m
        and per_object["median_world_xy_l2"].max() <= args.gate_object_median_m
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output_dir / "heatmap_localization_oof_predictions.csv", index=False)
    per_object.to_csv(args.output_dir / "heatmap_localization_per_object.csv", index=False)
    depth_table.to_csv(args.output_dir / "heatmap_depth_mode_selection.csv", index=False)
    depth_calibration_table.to_csv(
        args.output_dir / "heatmap_depth_ridge_selection.csv", index=False
    )
    object_depth_table.to_csv(
        args.output_dir / "heatmap_object_depth_mode_selection.csv", index=False
    )
    (args.output_dir / "heatmap_localization_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    if not summary["localization_gate_pass"]:
        return 4

    all_indices = np.arange(len(frame))
    model = _train_model(
        frame,
        arrays,
        all_indices,
        object_names,
        device=args.device,
        epochs=args.full_epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        depth_weight=args.depth_weight,
        seed=args.seed + 100,
    )
    object_plane_z = {
        name: float(
            np.median(
                arrays["true_world"][
                    frame["object_name"].astype(str).eq(name).to_numpy(), 2
                ]
            )
        )
        for name in object_names
    }
    full_predictions = _predict(
        model,
        frame,
        arrays,
        all_indices,
        object_names,
        object_plane_z,
        depth_bounds,
        device=args.device,
        batch_size=args.batch_size,
    )
    depth_features = _depth_feature_matrix(full_predictions, object_names)
    standardized_depth, depth_mean, depth_scale = _standardize(depth_features)
    depth_calibration_head = weighted_ridge(
        standardized_depth,
        full_predictions["true_world_z"].to_numpy(dtype=np.float32),
        alpha=depth_calibration_alpha,
        positive_weight=1.0,
    )
    weights_filename = "perception_regrasp_heatmap_weights.pt"
    weights_path = args.output_dir / weights_filename
    temporary_weights = weights_path.with_suffix(".tmp.pt")
    torch.save(
        {name: value.detach().cpu() for name, value in model.state_dict().items()},
        temporary_weights,
    )
    os.replace(temporary_weights, weights_path)
    object_plane_z_values = np.asarray(
        [object_plane_z[name] for name in object_names], dtype=np.float32
    )
    metadata = {
        **summary,
        "inputs": "agentview RGB plus task-derived target object name",
        "simulator_pose_at_inference": False,
    }
    np.savez_compressed(
        args.output_dir / args.model_name,
        localizer_type=np.asarray(HEATMAP_LOCALIZER_TYPE),
        object_names=np.asarray(object_names),
        object_plane_z=object_plane_z_values,
        depth_mode=np.asarray(depth_mode),
        depth_mode_by_object=np.asarray(
            [object_depth_modes[name] for name in object_names]
        ),
        depth_bounds=np.asarray(_depth_bounds(arrays), dtype=np.float32),
        depth_calibration_head=depth_calibration_head,
        depth_calibration_mean=depth_mean,
        depth_calibration_scale=depth_scale,
        weights_filename=np.asarray(weights_filename),
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fold", "finalize"), required=True)
    parser.add_argument("--fold", type=int)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--calibration-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="perception_regrasp_localizer.npz")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--full-epochs", type=int, default=14)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--depth-weight", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--gate-median-m", type=float, default=0.025)
    parser.add_argument("--gate-p90-m", type=float, default=0.055)
    parser.add_argument("--gate-p90-z-m", type=float, default=0.06)
    parser.add_argument("--gate-object-median-m", type=float, default=0.04)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.folds < 2:
        raise ValueError("at least two folds are required")
    if args.mode == "fold":
        return run_fold(args)
    return finalize(args)


if __name__ == "__main__":
    raise SystemExit(main())

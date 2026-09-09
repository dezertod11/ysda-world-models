#!/usr/bin/env python3
"""Fit and cross-validate the frozen patch localizer for RGB regrasp."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from perception_regrasp import (
    DEFAULT_ENCODER,
    DEFAULT_RANDOM_FEATURES,
    compose_patch_features,
    depth_summary_features,
    deterministic_projection,
    encode_clip_patches,
    patch_mask_targets,
    pixel_to_world_plane,
    predict_ridge,
    spatial_centroid,
    weighted_ridge,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def _load_rows(root: Path) -> pd.DataFrame:
    paths = sorted(root.rglob("*__calibration.parquet"))
    if not paths:
        raise FileNotFoundError(f"no calibration shards under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    if frame["row_uid"].duplicated().any():
        duplicates = frame.loc[frame["row_uid"].duplicated(), "row_uid"].head().tolist()
        raise ValueError(f"duplicate calibration rows: {duplicates}")
    return frame.sort_values(["object_name", "independent_group", "row_uid"], kind="stable")


def _standardize(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = features.mean(axis=0).astype(np.float32)
    scale = features.std(axis=0).astype(np.float32)
    scale = np.where(scale < 1e-5, 1.0, scale).astype(np.float32)
    return (features - mean) / scale, mean, scale


def _fit_heads(
    frame: pd.DataFrame,
    feature_rows: list[np.ndarray],
    target_rows: list[np.ndarray],
    train_indices: np.ndarray,
    object_names: list[str],
    *,
    alpha: float,
    positive_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    combined = np.concatenate([feature_rows[index] for index in train_indices], axis=0)
    _, mean, scale = _standardize(combined)
    heads = []
    for object_name in object_names:
        indices = [
            int(index)
            for index in train_indices
            if str(frame.iloc[int(index)]["object_name"]) == object_name
        ]
        if not indices:
            raise ValueError(f"no training images for object {object_name!r}")
        features = np.concatenate([feature_rows[index] for index in indices], axis=0)
        targets = np.concatenate([target_rows[index] for index in indices], axis=0)
        heads.append(
            weighted_ridge(
                (features - mean) / scale,
                targets,
                alpha=alpha,
                positive_weight=positive_weight,
            )
        )
    return np.stack(heads), mean, scale


def _fit_depth_head(
    frame: pd.DataFrame,
    feature_rows: list[np.ndarray],
    heads: np.ndarray,
    feature_mean: np.ndarray,
    feature_scale: np.ndarray,
    train_indices: np.ndarray,
    object_names: list[str],
    true_z: np.ndarray,
    *,
    temperature: float,
    random_feature_count: int,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    for index in train_indices:
        object_index = object_names.index(str(frame.iloc[int(index)]["object_name"]))
        scores = predict_ridge(
            (feature_rows[int(index)] - feature_mean) / feature_scale,
            heads[object_index],
        )
        summary = depth_summary_features(
            feature_rows[int(index)],
            scores,
            temperature=temperature,
            random_feature_count=random_feature_count,
        )
        indicator = np.zeros(len(object_names), dtype=np.float32)
        indicator[object_index] = 1.0
        rows.append(np.concatenate([summary, indicator]))
    features = np.stack(rows)
    standardized, mean, scale = _standardize(features)
    head = weighted_ridge(
        standardized,
        true_z[train_indices],
        alpha=alpha,
        positive_weight=1.0,
    )
    return head, mean, scale


def _predict_depth(
    patch_features: np.ndarray,
    segmentation_head: np.ndarray,
    feature_mean: np.ndarray,
    feature_scale: np.ndarray,
    depth_head: np.ndarray,
    depth_mean: np.ndarray,
    depth_scale: np.ndarray,
    *,
    object_index: int,
    object_count: int,
    temperature: float,
    random_feature_count: int,
    bounds: tuple[float, float],
) -> float:
    scores = predict_ridge(
        (patch_features - feature_mean) / feature_scale,
        segmentation_head,
    )
    summary = depth_summary_features(
        patch_features,
        scores,
        temperature=temperature,
        random_feature_count=random_feature_count,
    )
    indicator = np.zeros(object_count, dtype=np.float32)
    indicator[object_index] = 1.0
    features = np.concatenate([summary, indicator])
    value = predict_ridge(
        ((features - depth_mean) / depth_scale)[None], depth_head
    )[0]
    return float(np.clip(value, bounds[0], bounds[1]))


def _evaluate_row(
    row: pd.Series,
    features: np.ndarray,
    head: np.ndarray,
    mean: np.ndarray,
    scale: np.ndarray,
    *,
    temperature: float,
    plane_z: float,
) -> dict[str, Any]:
    sample_path = _resolve(str(row["sample_path"]))
    with np.load(sample_path, allow_pickle=False) as payload:
        image = np.asarray(payload["image"])
        true_pixel = np.asarray(payload["target_pixel_rc"], dtype=np.float64)
        true_world = np.asarray(payload["target_world_position"], dtype=np.float64)
        intrinsic = np.asarray(payload["camera_intrinsic"], dtype=np.float64)
        camera_to_world = np.asarray(payload["camera_to_world"], dtype=np.float64)
    scores = predict_ridge((features - mean) / scale, head)
    side = int(round(math.sqrt(len(scores))))
    center = spatial_centroid(scores, side, temperature)
    scale_to_source = image.shape[0] / 224.0
    predicted_pixel = np.asarray(
        [center["row"] * scale_to_source, center["col"] * scale_to_source]
    )
    predicted_world = pixel_to_world_plane(
        predicted_pixel[0],
        predicted_pixel[1],
        intrinsic,
        camera_to_world,
        plane_z,
    )
    return {
        "row_uid": str(row["row_uid"]),
        "independent_group": str(row["independent_group"]),
        "position_level": str(row["position_level"]),
        "task_id": int(row["task_id"]),
        "object_name": str(row["object_name"]),
        "visible_pixels": int(row["visible_pixels"]),
        "true_pixel_row": float(true_pixel[0]),
        "true_pixel_col": float(true_pixel[1]),
        "predicted_pixel_row": float(predicted_pixel[0]),
        "predicted_pixel_col": float(predicted_pixel[1]),
        "pixel_l2": float(np.linalg.norm(predicted_pixel - true_pixel)),
        "world_xy_l2": float(np.linalg.norm(predicted_world[:2] - true_world[:2])),
        "world_z_abs": float(abs(plane_z - true_world[2])),
        "world_xyz_l2": float(np.linalg.norm(predicted_world - true_world)),
        "peak_probability": center["peak_probability"],
        "entropy": center["entropy"],
        "score_range": center["score_range"],
    }


def train(args: argparse.Namespace) -> tuple[Path, pd.DataFrame, dict[str, Any]]:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    root = args.calibration_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = _load_rows(root)
    frame = frame.loc[frame["visible_pixels"].astype(int) >= args.min_visible_pixels].reset_index(drop=True)
    if frame.empty:
        raise ValueError("all calibration targets are invisible")
    object_names = sorted(frame["object_name"].astype(str).unique())

    print(f"[perception-train] loading {args.encoder} on {args.device}", flush=True)
    model = CLIPModel.from_pretrained(args.encoder, local_files_only=True).to(args.device)
    model.eval()
    processor = CLIPProcessor.from_pretrained(args.encoder, local_files_only=True)
    images = []
    masks = []
    true_z_values = []
    for row in frame.itertuples(index=False):
        with np.load(_resolve(str(row.sample_path)), allow_pickle=False) as payload:
            images.append(np.asarray(payload["image"], dtype=np.uint8))
            masks.append(np.asarray(payload["target_mask"], dtype=np.uint8))
            true_z_values.append(float(np.asarray(payload["target_world_position"])[2]))
    true_z = np.asarray(true_z_values, dtype=np.float64)

    patch_batches = []
    for start in range(0, len(images), args.batch_size):
        stop = min(len(images), start + args.batch_size)
        patch_batches.append(
            encode_clip_patches(model, processor, images[start:stop], device=args.device)
        )
        print(f"[perception-train] encoded {stop}/{len(images)}", flush=True)
    embeddings = np.concatenate(patch_batches, axis=0)
    del model
    if args.device.startswith("cuda"):
        torch.cuda.empty_cache()
    projection = deterministic_projection(
        embeddings.shape[-1], args.random_features, args.projection_seed
    )
    feature_rows = [
        compose_patch_features(embedding, image, projection)
        for embedding, image in zip(embeddings, images)
    ]
    side = int(round(math.sqrt(embeddings.shape[1])))
    target_rows = [patch_mask_targets(mask, side) for mask in masks]
    frame["fold"] = frame["independent_group"].map(
        lambda value: _stable_fold(str(value), args.folds)
    )
    object_plane_z = {
        name: float(np.median(true_z[frame["object_name"].eq(name).to_numpy()]))
        for name in object_names
    }

    cv_models: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for fold in range(args.folds):
        train_indices = np.flatnonzero(frame["fold"].to_numpy() != fold)
        test_indices = np.flatnonzero(frame["fold"].to_numpy() == fold)
        if not len(test_indices):
            continue
        missing = set(object_names) - set(frame.iloc[train_indices]["object_name"].astype(str))
        if missing:
            raise ValueError(f"fold {fold} has no training support for {sorted(missing)}")
        cv_models[fold] = _fit_heads(
            frame,
            feature_rows,
            target_rows,
            train_indices,
            object_names,
            alpha=args.alpha,
            positive_weight=args.positive_weight,
        )

    candidates = [float(value) for value in args.temperatures.split(",")]
    candidate_rows = []
    all_indices = np.arange(len(frame))
    for temperature in candidates:
        pixel_errors = []
        for index in all_indices:
            fold = int(frame.iloc[index]["fold"])
            heads, mean, scale = cv_models[fold]
            object_name = str(frame.iloc[index]["object_name"])
            record = _evaluate_row(
                frame.iloc[index],
                feature_rows[index],
                heads[object_names.index(object_name)],
                mean,
                scale,
                temperature=temperature,
                plane_z=float(true_z[index]),
            )
            pixel_errors.append(record["pixel_l2"])
        candidate_rows.append(
            {
                "temperature": temperature,
                "median_pixel_l2": float(np.median(pixel_errors)),
                "p90_pixel_l2": float(np.quantile(pixel_errors, 0.9)),
            }
        )
    temperature_table = pd.DataFrame(candidate_rows).sort_values(
        ["median_pixel_l2", "p90_pixel_l2", "temperature"], kind="stable"
    )
    temperature = float(temperature_table.iloc[0]["temperature"])

    depth_bounds = (
        float(max(0.0, np.quantile(true_z, 0.005) - 0.02)),
        float(np.quantile(true_z, 0.995) + 0.02),
    )
    cv_depth_models: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for fold, (heads, mean, scale) in cv_models.items():
        train_indices = np.flatnonzero(frame["fold"].to_numpy() != fold)
        cv_depth_models[fold] = _fit_depth_head(
            frame,
            feature_rows,
            heads,
            mean,
            scale,
            train_indices,
            object_names,
            true_z,
            temperature=temperature,
            random_feature_count=args.random_features,
            alpha=args.depth_alpha,
        )

    predictions = []
    for index in all_indices:
        row = frame.iloc[index]
        heads, mean, scale = cv_models[int(row["fold"])]
        object_name = str(row["object_name"])
        object_index = object_names.index(object_name)
        depth_head, depth_mean, depth_scale = cv_depth_models[int(row["fold"])]
        predicted_z = _predict_depth(
            feature_rows[index],
            heads[object_index],
            mean,
            scale,
            depth_head,
            depth_mean,
            depth_scale,
            object_index=object_index,
            object_count=len(object_names),
            temperature=temperature,
            random_feature_count=args.random_features,
            bounds=depth_bounds,
        )
        predictions.append(
            _evaluate_row(
                row,
                feature_rows[index],
                heads[object_index],
                mean,
                scale,
                temperature=temperature,
                plane_z=predicted_z,
            )
        )
    prediction_frame = pd.DataFrame(predictions)
    full_heads, full_mean, full_scale = _fit_heads(
        frame,
        feature_rows,
        target_rows,
        all_indices,
        object_names,
        alpha=args.alpha,
        positive_weight=args.positive_weight,
    )
    full_depth_head, full_depth_mean, full_depth_scale = _fit_depth_head(
        frame,
        feature_rows,
        full_heads,
        full_mean,
        full_scale,
        all_indices,
        object_names,
        true_z,
        temperature=temperature,
        random_feature_count=args.random_features,
        alpha=args.depth_alpha,
    )
    per_object = (
        prediction_frame.groupby("object_name", as_index=False)
        .agg(
            rows=("row_uid", "size"),
            median_world_xy_l2=("world_xy_l2", "median"),
            mean_world_xy_l2=("world_xy_l2", "mean"),
            p90_world_xy_l2=("world_xy_l2", lambda values: np.quantile(values, 0.9)),
            median_pixel_l2=("pixel_l2", "median"),
            median_world_z_abs=("world_z_abs", "median"),
        )
        .sort_values("object_name")
    )
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "encoder": args.encoder,
        "rows": len(frame),
        "objects": object_names,
        "folds": args.folds,
        "alpha": args.alpha,
        "positive_weight": args.positive_weight,
        "depth_alpha": args.depth_alpha,
        "projection_seed": args.projection_seed,
        "random_features": args.random_features,
        "temperature": temperature,
        "median_world_xy_l2": float(prediction_frame["world_xy_l2"].median()),
        "mean_world_xy_l2": float(prediction_frame["world_xy_l2"].mean()),
        "p90_world_xy_l2": float(prediction_frame["world_xy_l2"].quantile(0.9)),
        "median_world_z_abs": float(prediction_frame["world_z_abs"].median()),
        "p90_world_z_abs": float(prediction_frame["world_z_abs"].quantile(0.9)),
        "median_world_xyz_l2": float(prediction_frame["world_xyz_l2"].median()),
        "visible_rate": float((frame["visible_pixels"] > 0).mean()),
    }
    summary["localization_gate_pass"] = bool(
        summary["median_world_xy_l2"] <= args.gate_median_m
        and summary["p90_world_xy_l2"] <= args.gate_p90_m
        and summary["p90_world_z_abs"] <= args.gate_p90_z_m
        and per_object["median_world_xy_l2"].max() <= args.gate_object_median_m
    )
    metadata = {
        **summary,
        "feature_layout": "clip_random_projection+rgb_mean+rgb_std+x+y+x2+y2+xy",
    }
    model_path = output_dir / args.model_name
    np.savez_compressed(
        model_path,
        object_names=np.asarray(object_names),
        projection=projection,
        feature_mean=full_mean,
        feature_scale=full_scale,
        heads=full_heads,
        object_plane_z=np.asarray([object_plane_z[name] for name in object_names]),
        depth_head=full_depth_head,
        depth_feature_mean=full_depth_mean,
        depth_feature_scale=full_depth_scale,
        depth_bounds=np.asarray(depth_bounds),
        temperature=np.asarray(temperature),
        metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
    )
    prediction_frame.to_csv(output_dir / "localization_oof_predictions.csv", index=False)
    per_object.to_csv(output_dir / "localization_per_object.csv", index=False)
    temperature_table.to_csv(output_dir / "localization_temperature_selection.csv", index=False)
    (output_dir / "localization_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return model_path, prediction_frame, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", default="perception_regrasp_localizer.npz")
    parser.add_argument("--encoder", default=DEFAULT_ENCODER)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--random-features", type=int, default=DEFAULT_RANDOM_FEATURES)
    parser.add_argument("--projection-seed", type=int, default=20260904)
    parser.add_argument("--alpha", type=float, default=3.0)
    parser.add_argument("--positive-weight", type=float, default=20.0)
    parser.add_argument("--depth-alpha", type=float, default=3.0)
    parser.add_argument("--temperatures", default="0.03,0.05,0.08,0.12,0.2")
    parser.add_argument("--min-visible-pixels", type=int, default=4)
    parser.add_argument("--gate-median-m", type=float, default=0.025)
    parser.add_argument("--gate-p90-m", type=float, default=0.055)
    parser.add_argument("--gate-p90-z-m", type=float, default=0.06)
    parser.add_argument("--gate-object-median-m", type=float, default=0.04)
    return parser


def main() -> int:
    _path, _predictions, summary = train(build_parser().parse_args())
    return 0 if summary["localization_gate_pass"] else 4


if __name__ == "__main__":
    raise SystemExit(main())

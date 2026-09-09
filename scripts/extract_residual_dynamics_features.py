#!/usr/bin/env python3
"""Encode predicted and realized transition images with a frozen CLIP encoder."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

try:
    from scripts.build_residual_dynamics_dataset import resolve_sidecar, sha256_file
    from scripts.object_contact_vof import MODEL_NAME, _encode_images
except ModuleNotFoundError:
    from build_residual_dynamics_dataset import resolve_sidecar, sha256_file
    from object_contact_vof import MODEL_NAME, _encode_images


ImageEncoder = Callable[[Sequence[np.ndarray]], np.ndarray]


def extract_arrays(
    manifest: pd.DataFrame,
    encode: ImageEncoder,
    *,
    row_batch_size: int = 16,
) -> dict[str, np.ndarray]:
    if row_batch_size < 1:
        raise ValueError("row_batch_size must be positive")
    visual_batches: dict[str, list[np.ndarray]] = {
        "current_visual": [],
        "predicted_visual": [],
        "actual_visual": [],
    }
    numeric: dict[str, list[np.ndarray]] = {
        "current_proprio": [],
        "predicted_proprio": [],
        "actual_proprio": [],
        "actions": [],
        "candidate_value": [],
    }

    for start in range(0, len(manifest), row_batch_size):
        batch = manifest.iloc[start : start + row_batch_size]
        images: list[np.ndarray] = []
        batch_numeric: list[
            tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]
        ] = []
        payload_cache: dict[Path, dict[str, np.ndarray]] = {}
        for row in batch.itertuples(index=False):
            sidecar = resolve_sidecar(row.sidecar_path)
            if sidecar not in payload_cache:
                with np.load(sidecar, allow_pickle=False) as payload:
                    payload_cache[sidecar] = {
                        key: np.asarray(payload[key]) for key in payload.files
                    }
            payload = payload_cache[sidecar]
            index = int(row.candidate_idx)
            images.extend(
                [
                    payload["current_agentview"],
                    payload["candidate_predicted_future_images"][index],
                    payload["candidate_endpoint_agentview"][index],
                    payload["current_wrist"],
                    payload["candidate_predicted_future_wrists"][index],
                    payload["candidate_endpoint_wrist"][index],
                ]
            )
            batch_numeric.append(
                (
                    np.asarray(payload["current_proprio"], dtype=np.float32),
                    np.asarray(
                        payload["candidate_predicted_future_proprio"][index],
                        dtype=np.float32,
                    ),
                    np.asarray(
                        payload["candidate_endpoint_proprio"][index], dtype=np.float32
                    ),
                    np.asarray(payload["candidate_actions"][index], dtype=np.float32),
                    float(payload["candidate_values"][index]),
                )
            )
        embeddings = np.asarray(encode(images), dtype=np.float32)
        if embeddings.ndim != 2 or len(embeddings) != len(images):
            raise ValueError(
                f"Image encoder returned {embeddings.shape} for {len(images)} input images"
            )
        embeddings = embeddings.reshape(len(batch), 6, embeddings.shape[-1])
        visual_batches["current_visual"].append(
            np.concatenate([embeddings[:, 0], embeddings[:, 3]], axis=1)
        )
        visual_batches["predicted_visual"].append(
            np.concatenate([embeddings[:, 1], embeddings[:, 4]], axis=1)
        )
        visual_batches["actual_visual"].append(
            np.concatenate([embeddings[:, 2], embeddings[:, 5]], axis=1)
        )
        for values in batch_numeric:
            for key, value in zip(numeric, values):
                numeric[key].append(np.asarray(value, dtype=np.float32))
        print(
            f"[p4-features] encoded {min(start + len(batch), len(manifest))}/{len(manifest)}",
            flush=True,
        )

    result = {
        key: np.concatenate(values, axis=0).astype(np.float32)
        for key, values in visual_batches.items()
    }
    for key, values in numeric.items():
        result[key] = np.stack(values).astype(np.float32)
    result["row_index"] = np.arange(len(manifest), dtype=np.int64)
    expected = len(manifest)
    for key, value in result.items():
        if len(value) != expected:
            raise RuntimeError(
                f"Feature alignment failed for {key}: {len(value)} != {expected}"
            )
        if np.issubdtype(value.dtype, np.floating) and not np.all(np.isfinite(value)):
            raise ValueError(f"Non-finite values in extracted feature {key}")
    return result


def extract_feature_file(
    manifest_path: Path,
    output_path: Path,
    *,
    model_name: str = MODEL_NAME,
    device: str = "cuda",
    row_batch_size: int = 16,
    local_files_only: bool = True,
) -> dict[str, object]:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    manifest_path = manifest_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    manifest = pd.read_parquet(manifest_path)
    print(f"[p4-features] loading frozen encoder {model_name} on {device}", flush=True)
    model = CLIPModel.from_pretrained(model_name, local_files_only=local_files_only).to(
        device
    )
    model.eval()
    processor = CLIPProcessor.from_pretrained(
        model_name,
        local_files_only=local_files_only,
        use_fast=False,
    )

    def encode(
        images: Sequence[np.ndarray],
        _model: object = model,
        _processor: object = processor,
    ) -> np.ndarray:
        _patches, global_embeddings = _encode_images(
            _model, _processor, list(images), device
        )
        return global_embeddings

    arrays = extract_arrays(manifest, encode, row_batch_size=row_batch_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.stem + ".tmp.npz")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    os.replace(temporary, output_path)
    del model
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "model_name": model_name,
        "device": device,
        "rows": len(manifest),
        "visual_dimension": int(arrays["current_visual"].shape[1]),
        "action_shape": list(arrays["actions"].shape[1:]),
        "feature_sha256": sha256_file(output_path),
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-name", default=MODEL_NAME)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--row-batch-size", type=int, default=16)
    parser.add_argument(
        "--local-files-only", action=argparse.BooleanOptionalAction, default=True
    )
    args = parser.parse_args()
    metadata = extract_feature_file(
        args.manifest,
        args.output,
        model_name=args.model_name,
        device=args.device,
        row_batch_size=args.row_batch_size,
        local_files_only=args.local_files_only,
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Frozen object-conditioned visual features for feedback-value modelling."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


MODEL_NAME = "openai/clip-vit-base-patch32"
LOCALIZATION_TEMPERATURE = 0.07
TARGET_PATTERN = re.compile(
    r"^pick (?:up )?the (.+?) and place it in the basket[.!]?$", re.IGNORECASE
)

SPATIAL_KEYS = (
    "target_global_similarity",
    "goal_global_similarity",
    "target_peak_similarity",
    "target_attention_entropy",
    "target_center_x",
    "target_center_y",
    "target_spread",
    "goal_peak_similarity",
    "goal_attention_entropy",
    "goal_center_x",
    "goal_center_y",
    "goal_spread",
    "relation_distance",
    "relation_overlap",
)

CANDIDATE_KEYS = (
    "target_global_similarity",
    "goal_global_similarity",
    "target_peak_similarity",
    "target_attention_entropy",
    "target_spread",
    "goal_peak_similarity",
    "relation_distance",
    "relation_overlap",
)

RANK_KEYS = (
    "target_global_similarity",
    "target_peak_similarity",
    "relation_distance",
    "relation_overlap",
)


def normalize_rows(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    denominator = np.linalg.norm(values, axis=-1, keepdims=True)
    return values / np.clip(denominator, 1e-12, None)


def parse_target_object(description: str) -> str:
    match = TARGET_PATTERN.match(str(description).strip())
    if not match:
        raise ValueError(f"Cannot parse target object from task: {description!r}")
    return match.group(1).strip().replace("_", " ")


def _softmax(values: np.ndarray, temperature: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    shifted = (values - np.max(values)) / temperature
    weights = np.exp(np.clip(shifted, -80.0, 0.0))
    return weights / np.clip(weights.sum(), 1e-12, None)


def attention_statistics(
    similarity: np.ndarray, *, temperature: float = LOCALIZATION_TEMPERATURE
) -> dict[str, float]:
    similarity = np.asarray(similarity, dtype=np.float64).reshape(-1)
    side = int(round(math.sqrt(len(similarity))))
    if side * side != len(similarity):
        raise ValueError(f"Patch count {len(similarity)} is not a square grid")
    weights = _softmax(similarity, temperature)
    axis = np.linspace(-1.0, 1.0, side)
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    x = float(np.sum(weights * xx.reshape(-1)))
    y = float(np.sum(weights * yy.reshape(-1)))
    spread = float(
        np.sqrt(
            np.sum(
                weights
                * (
                    np.square(xx.reshape(-1) - x)
                    + np.square(yy.reshape(-1) - y)
                )
            )
        )
    )
    entropy = float(-np.sum(weights * np.log(np.clip(weights, 1e-12, None))))
    entropy /= math.log(len(weights)) if len(weights) > 1 else 1.0
    return {
        "peak_similarity": float(np.max(similarity)),
        "attention_entropy": entropy,
        "center_x": x,
        "center_y": y,
        "spread": spread,
        "weights": weights,
    }


def image_relation_statistics(
    patches: np.ndarray,
    global_embedding: np.ndarray,
    target_text: np.ndarray,
    goal_text: np.ndarray,
    *,
    temperature: float = LOCALIZATION_TEMPERATURE,
) -> dict[str, float]:
    patches = normalize_rows(np.asarray(patches, dtype=np.float64))
    global_embedding = normalize_rows(np.asarray(global_embedding).reshape(1, -1))[0]
    target_text = normalize_rows(np.asarray(target_text).reshape(1, -1))[0]
    goal_text = normalize_rows(np.asarray(goal_text).reshape(1, -1))[0]
    target = attention_statistics(patches @ target_text, temperature=temperature)
    goal = attention_statistics(patches @ goal_text, temperature=temperature)
    dx = target["center_x"] - goal["center_x"]
    dy = target["center_y"] - goal["center_y"]
    overlap = float(np.sum(np.sqrt(target["weights"] * goal["weights"])))
    return {
        "target_global_similarity": float(global_embedding @ target_text),
        "goal_global_similarity": float(global_embedding @ goal_text),
        "target_peak_similarity": float(target["peak_similarity"]),
        "target_attention_entropy": float(target["attention_entropy"]),
        "target_center_x": float(target["center_x"]),
        "target_center_y": float(target["center_y"]),
        "target_spread": float(target["spread"]),
        "goal_peak_similarity": float(goal["peak_similarity"]),
        "goal_attention_entropy": float(goal["attention_entropy"]),
        "goal_center_x": float(goal["center_x"]),
        "goal_center_y": float(goal["center_y"]),
        "goal_spread": float(goal["spread"]),
        "relation_distance": float(math.hypot(dx, dy)),
        "relation_overlap": overlap,
    }


def _rank_fraction(values: np.ndarray, selected: int) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) <= 1:
        return 1.0
    order = np.argsort(np.argsort(values, kind="stable"), kind="stable")
    return float(order[selected] / (len(values) - 1))


def _view_record(
    name: str,
    current_patches: np.ndarray,
    future_patches: np.ndarray,
    current_global: np.ndarray,
    future_global: np.ndarray,
    target_text: np.ndarray,
    goal_text: np.ndarray,
    selected: int,
) -> dict[str, float]:
    current = image_relation_statistics(
        current_patches, current_global, target_text, goal_text
    )
    futures = [
        image_relation_statistics(patches, global_embedding, target_text, goal_text)
        for patches, global_embedding in zip(future_patches, future_global)
    ]
    if not 0 <= selected < len(futures):
        raise ValueError(f"Invalid selected candidate {selected} for K={len(futures)}")
    result: dict[str, float] = {}
    for key in SPATIAL_KEYS:
        result[f"f_obj_{name}_current_{key}"] = current[key]
        result[f"f_obj_{name}_selected_delta_{key}"] = futures[selected][key] - current[key]
    for key in CANDIDATE_KEYS:
        deltas = np.asarray([future[key] - current[key] for future in futures])
        result[f"f_obj_{name}_candidate_delta_mean_{key}"] = float(deltas.mean())
        result[f"f_obj_{name}_candidate_delta_std_{key}"] = float(deltas.std())
        result[f"f_obj_{name}_candidate_delta_range_{key}"] = float(np.ptp(deltas))
    for key in RANK_KEYS:
        values = np.asarray([future[key] for future in futures])
        result[f"f_obj_{name}_selected_rank_{key}"] = _rank_fraction(values, selected)
    return result


def object_relation_record(
    *,
    agent_current_patches: np.ndarray,
    agent_future_patches: np.ndarray,
    agent_current_global: np.ndarray,
    agent_future_global: np.ndarray,
    wrist_current_patches: np.ndarray,
    wrist_future_patches: np.ndarray,
    wrist_current_global: np.ndarray,
    wrist_future_global: np.ndarray,
    target_text: np.ndarray,
    goal_text: np.ndarray,
    selected: int,
) -> dict[str, float]:
    result = _view_record(
        "agent",
        agent_current_patches,
        agent_future_patches,
        agent_current_global,
        agent_future_global,
        target_text,
        goal_text,
        selected,
    )
    result.update(
        _view_record(
            "wrist",
            wrist_current_patches,
            wrist_future_patches,
            wrist_current_global,
            wrist_future_global,
            target_text,
            goal_text,
            selected,
        )
    )
    return result


def resolve_sidecar(path: str, project_root: Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    marker = "/experiments/"
    if marker in str(path):
        candidate = project_root / "experiments" / str(path).split(marker, 1)[1]
    if not candidate.exists():
        raise FileNotFoundError(path)
    return candidate


def _encode_images(
    model: Any, processor: Any, arrays: list[np.ndarray], device: str
) -> tuple[np.ndarray, np.ndarray]:
    import torch
    from PIL import Image

    images = [Image.fromarray(np.asarray(array, dtype=np.uint8)) for array in arrays]
    inputs = processor(images=images, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)
    with torch.inference_mode():
        output = model.vision_model(pixel_values=pixel_values)
        patch = model.visual_projection(output.last_hidden_state[:, 1:, :])
        global_embedding = model.visual_projection(output.pooler_output)
        patch = torch.nn.functional.normalize(patch.float(), dim=-1)
        global_embedding = torch.nn.functional.normalize(global_embedding.float(), dim=-1)
    return patch.cpu().numpy(), global_embedding.cpu().numpy()


def _concept_embeddings(
    model: Any, processor: Any, concepts: list[str], device: str
) -> Mapping[str, np.ndarray]:
    import torch

    prompts: list[str] = []
    owners: list[str] = []
    for concept in concepts:
        for prompt in (
            f"a photo of {concept}",
            f"a robot workspace containing {concept}",
            concept,
        ):
            prompts.append(prompt)
            owners.append(concept)
    inputs = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.inference_mode():
        encoded = model.get_text_features(**inputs)
        encoded = torch.nn.functional.normalize(encoded.float(), dim=-1).cpu().numpy()
    result = {}
    for concept in concepts:
        pooled = encoded[np.asarray(owners) == concept].mean(axis=0, keepdims=True)
        result[concept] = normalize_rows(pooled)[0]
    return result


def extract_object_features(
    frame: pd.DataFrame,
    *,
    project_root: Path,
    model_name: str = MODEL_NAME,
    device: str = "cuda",
    row_batch_size: int = 4,
    local_files_only: bool = True,
) -> pd.DataFrame:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    if row_batch_size < 1:
        raise ValueError("row_batch_size must be positive")
    print(f"[object-vof] loading frozen encoder {model_name} on {device}", flush=True)
    model = CLIPModel.from_pretrained(
        model_name, local_files_only=local_files_only
    ).to(device)
    model.eval()
    print("[object-vof] encoder loaded; loading processor", flush=True)
    processor = CLIPProcessor.from_pretrained(
        model_name, local_files_only=local_files_only
    )
    targets = sorted(
        {parse_target_object(value) for value in frame["task_description"].astype(str)}
    )
    print(
        f"[object-vof] encoding {len(targets)} target concepts and basket",
        flush=True,
    )
    concepts = _concept_embeddings(model, processor, targets + ["basket"], device)
    print("[object-vof] text concepts ready", flush=True)

    records: list[dict[str, Any]] = []
    for start in range(0, len(frame), row_batch_size):
        batch = frame.iloc[start : start + row_batch_size]
        arrays: list[np.ndarray] = []
        metadata: list[tuple[pd.Series, int, int, int]] = []
        for _, row in batch.iterrows():
            sidecar = resolve_sidecar(str(row["sidecar_path"]), project_root)
            with np.load(sidecar, allow_pickle=False) as payload:
                selected = int(np.asarray(payload["selected_max_value_idx"]).item())
                future_agent = np.asarray(payload["candidate_predicted_future_images"])
                future_wrist = np.asarray(payload["candidate_predicted_future_wrists"])
                if len(future_agent) != len(future_wrist):
                    raise ValueError(f"Candidate view count mismatch in {sidecar}")
                row_arrays = [
                    np.asarray(payload["current_agentview"]),
                    *future_agent,
                    np.asarray(payload["current_wrist"]),
                    *future_wrist,
                ]
            offset = len(arrays)
            arrays.extend(row_arrays)
            metadata.append((row, selected, offset, len(future_agent)))
        print(
            f"[object-vof] visual batch rows {start}:{start + len(batch)} "
            f"({len(arrays)} images)",
            flush=True,
        )
        patches, globals_ = _encode_images(model, processor, arrays, device)
        for row, selected, offset, candidates in metadata:
            wrist_offset = offset + 1 + candidates
            target = parse_target_object(str(row["task_description"]))
            record = {
                "row_uid": str(row["row_uid"]),
                "target_object": target,
                **object_relation_record(
                    agent_current_patches=patches[offset],
                    agent_future_patches=patches[offset + 1 : offset + 1 + candidates],
                    agent_current_global=globals_[offset],
                    agent_future_global=globals_[offset + 1 : offset + 1 + candidates],
                    wrist_current_patches=patches[wrist_offset],
                    wrist_future_patches=patches[
                        wrist_offset + 1 : wrist_offset + 1 + candidates
                    ],
                    wrist_current_global=globals_[wrist_offset],
                    wrist_future_global=globals_[
                        wrist_offset + 1 : wrist_offset + 1 + candidates
                    ],
                    target_text=concepts[target],
                    goal_text=concepts["basket"],
                    selected=selected,
                ),
            }
            records.append(record)
        done = min(start + len(batch), len(frame))
        print(f"[object-vof] encoded {done}/{len(frame)}", flush=True)
    del model
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    result = pd.DataFrame(records)
    if result["row_uid"].duplicated().any():
        raise ValueError("Duplicate row_uid in extracted visual features")
    return result

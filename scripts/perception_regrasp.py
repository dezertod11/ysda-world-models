#!/usr/bin/env python3
"""Frozen RGB target localizer used by the deployable regrasp proposal."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


DEFAULT_ENCODER = "openai/clip-vit-base-patch16"
DEFAULT_IMAGE_SIZE = 224
DEFAULT_RANDOM_FEATURES = 96
HEATMAP_LOCALIZER_TYPE = "deeplab_heatmap_v2"
TARGET_PATTERN = re.compile(
    r"^pick (?:up )?the (.+?) and place it in the basket[.!]?$", re.IGNORECASE
)


def raw_agentview_image(observation: Mapping[str, Any]) -> np.ndarray:
    """Return RGB pixels in the native orientation used by camera calibration."""
    image = np.asarray(observation["agentview_image"], dtype=np.uint8)
    if image.ndim != 3 or image.shape[-1] != 3:
        raise ValueError(f"agentview_image must be HxWx3, got {image.shape}")
    return image


def canonical_object_name(value: str) -> str:
    """Normalize task text or LIBERO instance names to a stable object label."""
    text = str(value).strip().lower().replace("_", " ")
    match = TARGET_PATTERN.match(text)
    if match:
        text = match.group(1)
    text = re.sub(r"\s+\d+$", "", text)
    return " ".join(text.split())


def deterministic_projection(input_dim: int, output_dim: int, seed: int) -> np.ndarray:
    if input_dim < 1 or output_dim < 1:
        raise ValueError("projection dimensions must be positive")
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(input_dim, output_dim)).astype(np.float32)
    matrix /= np.sqrt(float(output_dim))
    return matrix


def patch_auxiliary_features(image: np.ndarray, grid_side: int) -> np.ndarray:
    """Return RGB moments and normalized coordinates for a square patch grid."""
    from PIL import Image

    if grid_side < 1:
        raise ValueError("grid_side must be positive")
    image = np.asarray(image, dtype=np.uint8)
    resized = np.asarray(
        Image.fromarray(image).resize(
            (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE), resample=Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    ) / 255.0
    if DEFAULT_IMAGE_SIZE % grid_side:
        raise ValueError(f"image size {DEFAULT_IMAGE_SIZE} is not divisible by {grid_side}")
    patch = DEFAULT_IMAGE_SIZE // grid_side
    blocks = resized.reshape(grid_side, patch, grid_side, patch, 3).transpose(0, 2, 1, 3, 4)
    means = blocks.mean(axis=(2, 3)).reshape(-1, 3)
    stds = blocks.std(axis=(2, 3)).reshape(-1, 3)
    axis = np.linspace(-1.0, 1.0, grid_side, dtype=np.float32)
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    coords = np.stack(
        [xx, yy, xx * xx, yy * yy, xx * yy], axis=-1
    ).reshape(-1, 5)
    return np.concatenate([means, stds, coords], axis=1).astype(np.float32)


def patch_mask_targets(mask: np.ndarray, grid_side: int) -> np.ndarray:
    """Convert a pixel mask to visible-area fractions on the encoder patch grid."""
    from PIL import Image

    mask = np.asarray(mask, dtype=np.uint8)
    resized = np.asarray(
        Image.fromarray(mask * 255).resize(
            (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE), resample=Image.Resampling.NEAREST
        ),
        dtype=np.float32,
    ) / 255.0
    patch = DEFAULT_IMAGE_SIZE // grid_side
    return resized.reshape(grid_side, patch, grid_side, patch).mean(axis=(1, 3)).reshape(-1)


def spatial_centroid(scores: Sequence[float], grid_side: int, temperature: float) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if scores.size != grid_side * grid_side:
        raise ValueError("score count does not match patch grid")
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    logits = (scores - np.max(scores)) / temperature
    weights = np.exp(np.clip(logits, -80.0, 0.0))
    weights /= np.clip(weights.sum(), 1e-12, None)
    axis = (np.arange(grid_side, dtype=np.float64) + 0.5) / grid_side
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    row = float(np.sum(weights * yy.reshape(-1)) * DEFAULT_IMAGE_SIZE)
    col = float(np.sum(weights * xx.reshape(-1)) * DEFAULT_IMAGE_SIZE)
    entropy = float(-np.sum(weights * np.log(np.clip(weights, 1e-12, None))))
    entropy /= math.log(len(weights)) if len(weights) > 1 else 1.0
    return {
        "row": row,
        "col": col,
        "peak_probability": float(np.max(weights)),
        "entropy": entropy,
        "score_range": float(np.ptp(scores)),
    }


def pixel_to_world_plane(
    row: float,
    col: float,
    intrinsic: np.ndarray,
    camera_to_world: np.ndarray,
    plane_z: float,
) -> np.ndarray:
    """Intersect an image ray with a horizontal world-space plane."""
    intrinsic = np.asarray(intrinsic, dtype=np.float64)
    camera_to_world = np.asarray(camera_to_world, dtype=np.float64)
    ray_camera = np.linalg.solve(intrinsic, np.asarray([col, row, 1.0]))
    origin = camera_to_world[:3, 3]
    direction = camera_to_world[:3, :3] @ ray_camera
    if abs(direction[2]) < 1e-9:
        raise ValueError("camera ray is parallel to target plane")
    scale = (float(plane_z) - origin[2]) / direction[2]
    if scale <= 0:
        raise ValueError("target plane lies behind camera")
    return origin + scale * direction


def weighted_ridge(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    alpha: float,
    positive_weight: float,
) -> np.ndarray:
    """Fit a small deterministic weighted ridge head, including an intercept."""
    features = np.asarray(features, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.float64).reshape(-1)
    if features.ndim != 2 or len(features) != len(targets):
        raise ValueError("features and targets must have matching rows")
    design = np.concatenate([features, np.ones((len(features), 1))], axis=1)
    weights = 1.0 + np.clip(targets, 0.0, 1.0) * max(0.0, positive_weight - 1.0)
    root = np.sqrt(weights)[:, None]
    weighted_design = design * root
    weighted_targets = targets * root[:, 0]
    penalty = np.eye(design.shape[1], dtype=np.float64) * float(alpha)
    penalty[-1, -1] = 0.0
    return np.linalg.solve(
        weighted_design.T @ weighted_design + penalty,
        weighted_design.T @ weighted_targets,
    ).astype(np.float32)


def predict_ridge(features: np.ndarray, weights: np.ndarray) -> np.ndarray:
    features = np.asarray(features, dtype=np.float32)
    weights = np.asarray(weights, dtype=np.float32).reshape(-1)
    if weights.size != features.shape[1] + 1:
        raise ValueError("ridge head has incompatible feature dimension")
    return features @ weights[:-1] + weights[-1]


def encode_clip_patches(
    model: Any,
    processor: Any,
    images: Sequence[np.ndarray],
    *,
    device: str,
) -> np.ndarray:
    import torch
    from PIL import Image

    pil_images = [Image.fromarray(np.asarray(image, dtype=np.uint8)) for image in images]
    inputs = processor(images=pil_images, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)
    with torch.inference_mode():
        output = model.vision_model(pixel_values=pixel_values)
        patches = model.visual_projection(output.last_hidden_state[:, 1:, :])
        patches = torch.nn.functional.normalize(patches.float(), dim=-1)
    return patches.cpu().numpy().astype(np.float32)


def build_deeplab_heatmap_model(object_count: int, *, pretrained: bool) -> Any:
    """Build the RGB target heatmap and metric-depth network."""
    from torch import nn
    from torchvision.models.segmentation import (
        DeepLabV3_ResNet50_Weights,
        deeplabv3_resnet50,
    )

    weights = DeepLabV3_ResNet50_Weights.DEFAULT if pretrained else None
    model = deeplabv3_resnet50(
        weights=weights,
        weights_backbone=None,
        aux_loss=True,
    )
    model.classifier[-1] = nn.Conv2d(256, object_count, kernel_size=1)
    model.aux_classifier[-1] = nn.Conv2d(256, object_count, kernel_size=1)
    model.depth_head = nn.Sequential(
        nn.Linear(2048, 256),
        nn.ReLU(inplace=True),
        nn.Linear(256, object_count),
    )
    model.depth_classifier = nn.Sequential(
        nn.Conv2d(2048, 256, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(256),
        nn.ReLU(inplace=True),
        nn.Conv2d(256, object_count, kernel_size=1),
    )
    return model


def forward_deeplab_heatmap(
    model: Any, image_tensor: Any, *, detach_depth: bool = False
) -> Mapping[str, Any]:
    """Run the attached heatmap/depth heads without simulator-only inputs."""
    import torch
    from torch.nn import functional as functional

    height, width = image_tensor.shape[-2:]
    features = model.backbone(image_tensor)
    local_depth_features = (
        features["out"].detach() if detach_depth else features["out"]
    )
    output = model.classifier(features["out"])
    result: dict[str, Any] = {
        "out": functional.interpolate(
            output,
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        ),
        "depth": model.depth_head(
            torch.nn.functional.adaptive_avg_pool2d(features["out"], 1).flatten(1)
        ),
        "depth_map": functional.interpolate(
            model.depth_classifier(local_depth_features),
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        ),
    }
    if model.training and model.aux_classifier is not None and "aux" in features:
        auxiliary = model.aux_classifier(features["aux"])
        result["aux"] = functional.interpolate(
            auxiliary,
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        )
    return result


def heatmap_image_tensor(image: np.ndarray, *, device: str) -> Any:
    """Convert one uint8 RGB observation to an ImageNet-normalized tensor."""
    import torch

    value = torch.from_numpy(np.asarray(image, dtype=np.uint8).copy())
    value = value.permute(2, 0, 1).unsqueeze(0).to(device=device, dtype=torch.float32) / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], device=device)[None, :, None, None]
    scale = torch.tensor([0.229, 0.224, 0.225], device=device)[None, :, None, None]
    return (value - mean) / scale


def heatmap_depth_features(
    global_z: float,
    local_z: float,
    row: float,
    col: float,
    height: int,
    width: int,
    object_index: int,
    object_count: int,
) -> np.ndarray:
    """Features shared by cross-fitted metric-depth calibration and inference."""
    row_normalized = float(row) / max(1, height - 1)
    col_normalized = float(col) / max(1, width - 1)
    base = np.asarray(
        [
            global_z,
            local_z,
            row_normalized,
            col_normalized,
            global_z * global_z,
            local_z * local_z,
            global_z * local_z,
            global_z * row_normalized,
            global_z * col_normalized,
            local_z * row_normalized,
            local_z * col_normalized,
            row_normalized * row_normalized,
            col_normalized * col_normalized,
        ],
        dtype=np.float32,
    )
    indicator = np.zeros(object_count, dtype=np.float32)
    indicator[object_index] = 1.0
    return np.concatenate(
        [base, indicator, indicator * global_z, indicator * local_z]
    )


def compose_patch_features(
    patch_embeddings: np.ndarray,
    image: np.ndarray,
    projection: np.ndarray,
) -> np.ndarray:
    patch_embeddings = np.asarray(patch_embeddings, dtype=np.float32)
    side = int(round(math.sqrt(len(patch_embeddings))))
    if side * side != len(patch_embeddings):
        raise ValueError("encoder patch count is not square")
    projected = patch_embeddings @ np.asarray(projection, dtype=np.float32)
    auxiliary = patch_auxiliary_features(image, side)
    return np.concatenate([projected, auxiliary], axis=1)


def depth_summary_features(
    patch_features: np.ndarray,
    scores: Sequence[float],
    *,
    temperature: float,
    random_feature_count: int,
) -> np.ndarray:
    """Compact image/heatmap representation for metric depth regression."""
    patch_features = np.asarray(patch_features, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    side = int(round(math.sqrt(len(scores))))
    if side * side != len(scores) or len(patch_features) != len(scores):
        raise ValueError("depth features require a square aligned patch grid")
    logits = (scores - np.max(scores)) / temperature
    weights = np.exp(np.clip(logits, -80.0, 0.0))
    weights /= np.clip(weights.sum(), 1e-12, None)
    visual = patch_features[:, :random_feature_count]
    pooled_width = min(16, visual.shape[1])
    moment_width = min(8, visual.shape[1])
    pooled = weights @ visual[:, :pooled_width]
    global_mean = visual[:, :moment_width].mean(axis=0)
    global_std = visual[:, :moment_width].std(axis=0)
    axis = (np.arange(side, dtype=np.float64) + 0.5) / side
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    x = float(weights @ xx.reshape(-1))
    y = float(weights @ yy.reshape(-1))
    x_std = float(np.sqrt(weights @ np.square(xx.reshape(-1) - x)))
    y_std = float(np.sqrt(weights @ np.square(yy.reshape(-1) - y)))
    entropy = float(-np.sum(weights * np.log(np.clip(weights, 1e-12, None))))
    entropy /= math.log(len(weights)) if len(weights) > 1 else 1.0
    summary = np.asarray(
        [
            x,
            y,
            x_std,
            y_std,
            float(scores.mean()),
            float(scores.std()),
            float(scores.min()),
            float(scores.max()),
            float(np.ptp(scores)),
            float(weights.max()),
            entropy,
        ],
        dtype=np.float64,
    )
    return np.concatenate([pooled, global_mean, global_std, summary]).astype(np.float32)


@dataclass(frozen=True)
class Localization:
    object_name: str
    pixel_row: float
    pixel_col: float
    world_position: np.ndarray
    peak_probability: float
    entropy: float
    score_range: float


class FrozenPatchLocalizer:
    """Inference-only RGB localizer; simulator state is never an input."""

    def __init__(self, path: Path | str, *, device: str = "cuda") -> None:
        self.path = Path(path).expanduser().resolve()
        with np.load(self.path, allow_pickle=False) as payload:
            self.object_names = [str(value) for value in payload["object_names"].tolist()]
            self.localizer_type = (
                str(np.asarray(payload["localizer_type"]).item())
                if "localizer_type" in payload
                else "clip_patch_ridge_v1"
            )
            self.metadata = json.loads(str(np.asarray(payload["metadata_json"]).item()))
        self.device = device
        if self.localizer_type == HEATMAP_LOCALIZER_TYPE:
            import torch

            with np.load(self.path, allow_pickle=False) as payload:
                self.depth_bounds = np.asarray(payload["depth_bounds"], dtype=np.float64)
                self.object_plane_z = np.asarray(
                    payload["object_plane_z"], dtype=np.float64
                )
                self.depth_mode = str(np.asarray(payload["depth_mode"]).item())
                self.depth_mode_by_object = (
                    [str(value) for value in payload["depth_mode_by_object"].tolist()]
                    if "depth_mode_by_object" in payload
                    else None
                )
                self.depth_calibration_head = (
                    np.asarray(payload["depth_calibration_head"], dtype=np.float32)
                    if "depth_calibration_head" in payload
                    else None
                )
                self.depth_calibration_mean = (
                    np.asarray(payload["depth_calibration_mean"], dtype=np.float32)
                    if "depth_calibration_mean" in payload
                    else None
                )
                self.depth_calibration_scale = (
                    np.asarray(payload["depth_calibration_scale"], dtype=np.float32)
                    if "depth_calibration_scale" in payload
                    else None
                )
                weights_filename = str(np.asarray(payload["weights_filename"]).item())
            self.model = build_deeplab_heatmap_model(
                len(self.object_names), pretrained=False
            ).to(device)
            state = torch.load(
                self.path.with_name(weights_filename),
                map_location=device,
                weights_only=True,
            )
            self.model.load_state_dict(state)
            self.model.eval()
            return

        from transformers import CLIPModel, CLIPProcessor

        with np.load(self.path, allow_pickle=False) as payload:
            self.projection = np.asarray(payload["projection"], dtype=np.float32)
            self.feature_mean = np.asarray(payload["feature_mean"], dtype=np.float32)
            self.feature_scale = np.asarray(payload["feature_scale"], dtype=np.float32)
            self.heads = np.asarray(payload["heads"], dtype=np.float32)
            self.object_plane_z = np.asarray(payload["object_plane_z"], dtype=np.float64)
            self.temperature = float(np.asarray(payload["temperature"]).item())
            self.depth_head = (
                np.asarray(payload["depth_head"], dtype=np.float32)
                if "depth_head" in payload
                else None
            )
            self.depth_feature_mean = (
                np.asarray(payload["depth_feature_mean"], dtype=np.float32)
                if "depth_feature_mean" in payload
                else None
            )
            self.depth_feature_scale = (
                np.asarray(payload["depth_feature_scale"], dtype=np.float32)
                if "depth_feature_scale" in payload
                else None
            )
            self.depth_bounds = (
                np.asarray(payload["depth_bounds"], dtype=np.float64)
                if "depth_bounds" in payload
                else None
            )
        model_name = str(self.metadata.get("encoder", DEFAULT_ENCODER))
        self.model = CLIPModel.from_pretrained(model_name, local_files_only=True).to(device)
        self.model.eval()
        self.processor = CLIPProcessor.from_pretrained(model_name, local_files_only=True)

    @property
    def supported_objects(self) -> tuple[str, ...]:
        return tuple(self.object_names)

    def _object_index(self, description_or_name: str) -> int:
        name = canonical_object_name(description_or_name)
        if name not in self.object_names:
            raise KeyError(f"unsupported perception target {name!r}")
        return self.object_names.index(name)

    def localize(
        self,
        image: np.ndarray,
        description_or_name: str,
        *,
        intrinsic: np.ndarray,
        camera_to_world: np.ndarray,
    ) -> Localization:
        index = self._object_index(description_or_name)
        if self.localizer_type == HEATMAP_LOCALIZER_TYPE:
            return self._localize_heatmap(
                image,
                index,
                intrinsic=intrinsic,
                camera_to_world=camera_to_world,
            )
        patches = encode_clip_patches(
            self.model, self.processor, [image], device=self.device
        )[0]
        raw_features = compose_patch_features(patches, image, self.projection)
        features = (raw_features - self.feature_mean) / self.feature_scale
        scores = predict_ridge(features, self.heads[index])
        side = int(round(math.sqrt(len(scores))))
        center = spatial_centroid(scores, side, self.temperature)
        scale = np.asarray(image).shape[0] / DEFAULT_IMAGE_SIZE
        row = center["row"] * scale
        col = center["col"] * scale
        plane_z = float(self.object_plane_z[index])
        if self.depth_head is not None:
            depth_features = depth_summary_features(
                raw_features,
                scores,
                temperature=self.temperature,
                random_feature_count=self.projection.shape[1],
            )
            object_indicator = np.zeros(len(self.object_names), dtype=np.float32)
            object_indicator[index] = 1.0
            depth_features = np.concatenate([depth_features, object_indicator])
            assert self.depth_feature_mean is not None
            assert self.depth_feature_scale is not None
            plane_z = float(
                predict_ridge(
                    ((depth_features - self.depth_feature_mean) / self.depth_feature_scale)[None],
                    self.depth_head,
                )[0]
            )
            if self.depth_bounds is not None:
                plane_z = float(np.clip(plane_z, self.depth_bounds[0], self.depth_bounds[1]))
        world = pixel_to_world_plane(
            row,
            col,
            intrinsic,
            camera_to_world,
            plane_z,
        )
        return Localization(
            object_name=self.object_names[index],
            pixel_row=float(row),
            pixel_col=float(col),
            world_position=world,
            peak_probability=center["peak_probability"],
            entropy=center["entropy"],
            score_range=center["score_range"],
        )

    def _localize_heatmap(
        self,
        image: np.ndarray,
        object_index: int,
        *,
        intrinsic: np.ndarray,
        camera_to_world: np.ndarray,
    ) -> Localization:
        import torch

        tensor = heatmap_image_tensor(image, device=self.device)
        with torch.inference_mode():
            output = forward_deeplab_heatmap(self.model, tensor)
        scores = output["out"][0, object_index].float().cpu().numpy()
        flat = scores.reshape(-1).astype(np.float64)
        best = int(np.argmax(flat))
        row, col = np.unravel_index(best, scores.shape)
        logits = flat - np.max(flat)
        probabilities = np.exp(np.clip(logits, -80.0, 0.0))
        probabilities /= np.clip(probabilities.sum(), 1e-12, None)
        entropy = float(
            -np.sum(probabilities * np.log(np.clip(probabilities, 1e-12, None)))
            / math.log(len(probabilities))
        )
        global_z = float(output["depth"][0, object_index].float().cpu().item())
        local_z = float(
            output["depth_map"][0, object_index, row, col].float().cpu().item()
        )
        depth_mode = self.depth_mode
        if depth_mode == "object_routed":
            if self.depth_mode_by_object is None:
                raise ValueError("object-routed artifact has no per-object depth modes")
            depth_mode = self.depth_mode_by_object[object_index]
        if depth_mode == "stacked_ridge":
            assert self.depth_calibration_head is not None
            assert self.depth_calibration_mean is not None
            assert self.depth_calibration_scale is not None
            depth_features = heatmap_depth_features(
                global_z,
                local_z,
                row,
                col,
                scores.shape[0],
                scores.shape[1],
                object_index,
                len(self.object_names),
            )
            plane_z = float(
                predict_ridge(
                    (
                        (depth_features - self.depth_calibration_mean)
                        / self.depth_calibration_scale
                    )[None],
                    self.depth_calibration_head,
                )[0]
            )
        elif depth_mode == "neural_local":
            plane_z = local_z
        elif depth_mode == "neural_global":
            plane_z = global_z
        else:
            plane_z = float(self.object_plane_z[object_index])
        plane_z = float(np.clip(plane_z, self.depth_bounds[0], self.depth_bounds[1]))
        world = pixel_to_world_plane(
            float(row),
            float(col),
            intrinsic,
            camera_to_world,
            plane_z,
        )
        return Localization(
            object_name=self.object_names[object_index],
            pixel_row=float(row),
            pixel_col=float(col),
            world_position=world,
            peak_probability=float(np.max(probabilities)),
            entropy=entropy,
            score_range=float(np.ptp(flat)),
        )


def localization_record(localization: Localization) -> Mapping[str, float | str]:
    return {
        "perception_object": localization.object_name,
        "perception_pixel_row": localization.pixel_row,
        "perception_pixel_col": localization.pixel_col,
        "perception_world_x": float(localization.world_position[0]),
        "perception_world_y": float(localization.world_position[1]),
        "perception_world_z": float(localization.world_position[2]),
        "perception_peak_probability": localization.peak_probability,
        "perception_entropy": localization.entropy,
        "perception_score_range": localization.score_range,
    }

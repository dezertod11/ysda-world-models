#!/usr/bin/env python3
"""Independent Gaussian residual-dynamics ensemble used by the P4 screen."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


def _as_float32(value: np.ndarray) -> np.ndarray:
    return np.asarray(value, dtype=np.float32)


def randomized_pca(
    values: np.ndarray,
    n_components: int,
    *,
    seed: int,
    oversamples: int = 8,
    power_iterations: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or len(values) < 2:
        raise ValueError("PCA needs a two-dimensional array with at least two rows")
    components = min(int(n_components), len(values) - 1, values.shape[1])
    if components < 1:
        raise ValueError("PCA component count must be positive")
    mean = values.mean(axis=0)
    centered = values - mean
    projection_size = min(values.shape[1], components + max(0, oversamples))
    rng = np.random.default_rng(seed)
    omega = rng.standard_normal((values.shape[1], projection_size))
    basis, _ = np.linalg.qr(centered @ omega, mode="reduced")
    for _ in range(max(0, power_iterations)):
        basis, _ = np.linalg.qr(centered @ (centered.T @ basis), mode="reduced")
    _left, _singular, right = np.linalg.svd(basis.T @ centered, full_matrices=False)
    return _as_float32(mean), _as_float32(right[:components])


def _standardizer(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(values, dtype=np.float64).mean(axis=0)
    scale = np.asarray(values, dtype=np.float64).std(axis=0)
    scale = np.where(scale < 1e-6, 1.0, scale)
    return _as_float32(mean), _as_float32(scale)


@dataclass
class ResidualPreprocessor:
    input_visual_mean: np.ndarray
    input_visual_components: np.ndarray
    target_visual_mean: np.ndarray
    target_visual_components: np.ndarray
    input_mean: np.ndarray
    input_scale: np.ndarray
    target_mean: np.ndarray
    target_scale: np.ndarray

    @staticmethod
    def _visual_input(
        arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        return np.concatenate(
            [arrays["current_visual"][indices], arrays["predicted_visual"][indices]],
            axis=1,
        )

    @staticmethod
    def _target_visual(
        arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        return arrays["actual_visual"][indices] - arrays["predicted_visual"][indices]

    @staticmethod
    def _nonvisual_input(
        arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        actions = arrays["actions"][indices].reshape(len(indices), -1)
        values = arrays["candidate_value"][indices].reshape(len(indices), 1)
        return np.concatenate(
            [
                arrays["current_proprio"][indices],
                arrays["predicted_proprio"][indices],
                actions,
                values,
            ],
            axis=1,
        )

    @staticmethod
    def _target_proprio(
        arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        return arrays["actual_proprio"][indices] - arrays["predicted_proprio"][indices]

    @classmethod
    def fit(
        cls,
        arrays: Mapping[str, np.ndarray],
        indices: np.ndarray,
        *,
        input_visual_components: int,
        target_visual_components: int,
        seed: int,
    ) -> "ResidualPreprocessor":
        indices = np.asarray(indices, dtype=np.int64)
        input_mean, input_components = randomized_pca(
            cls._visual_input(arrays, indices), input_visual_components, seed=seed
        )
        target_mean, target_components = randomized_pca(
            cls._target_visual(arrays, indices), target_visual_components, seed=seed + 1
        )
        input_visual = (
            cls._visual_input(arrays, indices) - input_mean
        ) @ input_components.T
        target_visual = (
            cls._target_visual(arrays, indices) - target_mean
        ) @ target_components.T
        raw_input = np.concatenate(
            [input_visual, cls._nonvisual_input(arrays, indices)], axis=1
        )
        raw_target = np.concatenate(
            [target_visual, cls._target_proprio(arrays, indices)], axis=1
        )
        feature_mean, feature_scale = _standardizer(raw_input)
        residual_mean, residual_scale = _standardizer(raw_target)
        return cls(
            input_visual_mean=input_mean,
            input_visual_components=input_components,
            target_visual_mean=target_mean,
            target_visual_components=target_components,
            input_mean=feature_mean,
            input_scale=feature_scale,
            target_mean=residual_mean,
            target_scale=residual_scale,
        )

    def transform_input(
        self, arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        indices = np.asarray(indices, dtype=np.int64)
        visual = (
            self._visual_input(arrays, indices) - self.input_visual_mean
        ) @ self.input_visual_components.T
        raw = np.concatenate([visual, self._nonvisual_input(arrays, indices)], axis=1)
        return _as_float32((raw - self.input_mean) / self.input_scale)

    def transform_target(
        self, arrays: Mapping[str, np.ndarray], indices: np.ndarray
    ) -> np.ndarray:
        indices = np.asarray(indices, dtype=np.int64)
        visual = (
            self._target_visual(arrays, indices) - self.target_visual_mean
        ) @ self.target_visual_components.T
        raw = np.concatenate([visual, self._target_proprio(arrays, indices)], axis=1)
        return _as_float32((raw - self.target_mean) / self.target_scale)

    def save(self, path: Path) -> None:
        with path.open("wb") as stream:
            np.savez_compressed(
                stream,
                input_visual_mean=self.input_visual_mean,
                input_visual_components=self.input_visual_components,
                target_visual_mean=self.target_visual_mean,
                target_visual_components=self.target_visual_components,
                input_mean=self.input_mean,
                input_scale=self.input_scale,
                target_mean=self.target_mean,
                target_scale=self.target_scale,
            )

    @classmethod
    def load(cls, path: Path) -> "ResidualPreprocessor":
        with np.load(path, allow_pickle=False) as payload:
            return cls(**{key: np.asarray(payload[key]) for key in payload.files})


def build_gaussian_head(input_dim: int, target_dim: int, hidden_dim: int):
    import torch

    class GaussianResidualHead(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.trunk = torch.nn.Sequential(
                torch.nn.Linear(input_dim, hidden_dim),
                torch.nn.SiLU(),
                torch.nn.Linear(hidden_dim, hidden_dim),
                torch.nn.SiLU(),
            )
            self.mean = torch.nn.Linear(hidden_dim, target_dim)
            self.log_variance = torch.nn.Linear(hidden_dim, target_dim)

        def forward(self, features):
            hidden = self.trunk(features)
            mean = self.mean(hidden)
            log_variance = self.log_variance(hidden).clamp(-8.0, 5.0)
            return mean, log_variance

    return GaussianResidualHead()


def gaussian_nll(mean, log_variance, target):
    import torch

    return (
        0.5
        * (log_variance + torch.square(target - mean) * torch.exp(-log_variance)).mean()
    )


def train_independent_heads(
    features: np.ndarray,
    targets: np.ndarray,
    groups: Sequence[str],
    output_dir: Path,
    *,
    num_heads: int = 5,
    hidden_dim: int = 256,
    epochs: int = 120,
    batch_size: int = 256,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-5,
    seed: int = 20260906,
    device: str = "cuda",
) -> list[dict[str, object]]:
    import torch

    features = _as_float32(features)
    targets = _as_float32(targets)
    groups = np.asarray(groups).astype(str)
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        raise ValueError("Independent bootstrap training needs at least two groups")
    output_dir.mkdir(parents=True, exist_ok=True)
    x_all = torch.from_numpy(features)
    y_all = torch.from_numpy(targets)
    histories: list[dict[str, object]] = []

    for head_index in range(num_heads):
        head_seed = seed + head_index * 1009
        rng = np.random.default_rng(head_seed)
        sampled_groups = rng.choice(
            unique_groups, size=len(unique_groups), replace=True
        )
        train_indices = np.concatenate(
            [np.flatnonzero(groups == group) for group in sampled_groups]
        ).astype(np.int64)
        sampled_set = set(sampled_groups.tolist())
        oob_indices = np.flatnonzero(
            np.asarray([group not in sampled_set for group in groups], dtype=bool)
        )
        torch.manual_seed(head_seed)
        if device.startswith("cuda"):
            torch.cuda.manual_seed_all(head_seed)
        model = build_gaussian_head(features.shape[1], targets.shape[1], hidden_dim).to(
            device
        )
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        final_loss = float("nan")
        model.train()
        for _epoch in range(epochs):
            permutation = rng.permutation(train_indices)
            losses = []
            for start in range(0, len(permutation), batch_size):
                index = permutation[start : start + batch_size]
                batch_x = x_all[index].to(device)
                batch_y = y_all[index].to(device)
                mean, log_variance = model(batch_x)
                loss = gaussian_nll(mean, log_variance, batch_y)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                losses.append(float(loss.detach().cpu()))
            final_loss = float(np.mean(losses))
        model.eval()
        oob_nll = float("nan")
        if len(oob_indices):
            with torch.inference_mode():
                mean, log_variance = model(x_all[oob_indices].to(device))
                oob_nll = float(
                    gaussian_nll(
                        mean, log_variance, y_all[oob_indices].to(device)
                    ).cpu()
                )
        torch.save(model.state_dict(), output_dir / f"head_{head_index}.pt")
        histories.append(
            {
                "head": head_index,
                "seed": head_seed,
                "bootstrap_rows": len(train_indices),
                "bootstrap_unique_groups": len(sampled_set),
                "oob_rows": len(oob_indices),
                "train_nll": final_loss,
                "oob_nll": oob_nll,
                "sampled_groups": sampled_groups.tolist(),
            }
        )
        del model
        if device.startswith("cuda"):
            torch.cuda.empty_cache()
    return histories


def predict_independent_heads(
    features: np.ndarray,
    artifact_dir: Path,
    *,
    device: str = "cuda",
    batch_size: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    import torch

    metadata = json.loads((artifact_dir / "ensemble.json").read_text(encoding="utf-8"))
    x = torch.from_numpy(_as_float32(features))
    means = []
    variances = []
    for head_index in range(int(metadata["num_heads"])):
        model = build_gaussian_head(
            int(metadata["input_dim"]),
            int(metadata["target_dim"]),
            int(metadata["hidden_dim"]),
        ).to(device)
        state = torch.load(
            artifact_dir / f"head_{head_index}.pt",
            map_location=device,
            weights_only=True,
        )
        model.load_state_dict(state)
        model.eval()
        head_mean = []
        head_variance = []
        with torch.inference_mode():
            for start in range(0, len(x), batch_size):
                mean, log_variance = model(x[start : start + batch_size].to(device))
                head_mean.append(mean.float().cpu().numpy())
                head_variance.append(torch.exp(log_variance.float()).cpu().numpy())
        means.append(np.concatenate(head_mean))
        variances.append(np.concatenate(head_variance))
        del model
    return np.stack(means), np.stack(variances)


def _logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + math.log(float(np.exp(values - maximum).sum()))


def jensen_renyi_divergence(means: np.ndarray, variances: np.ndarray) -> np.ndarray:
    """Quadratic Jensen-Renyi divergence for an equally weighted Gaussian mixture."""
    means = np.asarray(means, dtype=np.float64)
    variances = np.asarray(variances, dtype=np.float64)
    if means.shape != variances.shape or means.ndim != 3:
        raise ValueError(
            "Expected means and variances shaped [heads, rows, dimensions]"
        )
    if np.any(variances <= 0):
        raise ValueError("Gaussian variances must be positive")
    heads, rows, dimensions = means.shape
    result = np.empty(rows, dtype=np.float64)
    constant = dimensions * math.log(2.0 * math.pi)
    for row in range(rows):
        pairwise_logs = []
        for left in range(heads):
            for right in range(heads):
                summed = variances[left, row] + variances[right, row]
                delta = means[left, row] - means[right, row]
                pairwise_logs.append(
                    -0.5
                    * (
                        constant
                        + float(np.log(summed).sum())
                        + float(np.square(delta).dot(1.0 / summed))
                    )
                )
        mixture_entropy = -(
            _logsumexp(np.asarray(pairwise_logs)) - 2.0 * math.log(heads)
        )
        component_entropy = (
            0.5 * dimensions * math.log(4.0 * math.pi)
            + 0.5 * np.log(variances[:, row]).sum(axis=1)
        ).mean()
        result[row] = max(0.0, mixture_entropy - component_entropy)
    return result.astype(np.float32)


def uncertainty_scores(
    means: np.ndarray, variances: np.ndarray
) -> dict[str, np.ndarray]:
    aleatoric = variances.mean(axis=0)
    epistemic = means.var(axis=0)
    return {
        "ensemble_aleatoric_mean": aleatoric.mean(axis=1),
        "ensemble_aleatoric_max": aleatoric.max(axis=1),
        "ensemble_epistemic_mean": epistemic.mean(axis=1),
        "ensemble_epistemic_max": epistemic.max(axis=1),
        "ensemble_total_mean": (aleatoric + epistemic).mean(axis=1),
        "ensemble_jrd": jensen_renyi_divergence(means, variances),
    }


def mixture_nll(
    means: np.ndarray, variances: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    means = np.asarray(means, dtype=np.float64)
    variances = np.asarray(variances, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.float64)
    dimensions = targets.shape[1]
    log_probabilities = -0.5 * (
        dimensions * math.log(2.0 * math.pi)
        + np.log(variances).sum(axis=2)
        + (np.square(targets[None] - means) / variances).sum(axis=2)
    )
    maximum = log_probabilities.max(axis=0)
    log_mixture = maximum + np.log(
        np.exp(log_probabilities - maximum[None]).mean(axis=0)
    )
    return (-log_mixture).astype(np.float32)


def conformal_threshold(scores: Sequence[float], alpha: float) -> tuple[float, float]:
    values = np.asarray(scores, dtype=np.float64)
    values = values[np.isfinite(values)]
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    if not len(values):
        raise ValueError("Cannot calibrate an empty score collection")
    level = min(1.0, math.ceil((len(values) + 1) * (1.0 - alpha)) / len(values))
    threshold = float(np.quantile(values, level, method="higher"))
    return threshold, level

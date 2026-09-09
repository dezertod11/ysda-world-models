#!/usr/bin/env python3
"""Reusable P4b training, scoring, and candidate-selection utilities."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

try:
    from scripts.residual_dynamics_ensemble import (
        build_gaussian_head,
        jensen_renyi_divergence,
        mixture_nll,
    )
except ModuleNotFoundError:
    from residual_dynamics_ensemble import (
        build_gaussian_head,
        jensen_renyi_divergence,
        mixture_nll,
    )


RISK_SCORE_NAMES = (
    "epistemic_mean",
    "predicted_mean_residual_rms",
    "mean_plus_epistemic_rms",
    "expected_residual_rms",
    "epistemic_snr",
    "common_covariance_jrd",
    "mc_predictive_mi",
)


def _loss(mean, log_variance, target, mode: str, log_variance_l2: float):
    import torch

    if mode == "mean_mse":
        return torch.square(target - mean).mean()
    if mode != "gaussian_nll":
        raise ValueError(f"Unknown P4b loss mode: {mode}")
    nll = 0.5 * (
        log_variance
        + torch.square(target - mean) * torch.exp(-log_variance)
    ).mean()
    return nll + float(log_variance_l2) * torch.square(log_variance).mean()


def train_early_stopped_heads(
    features: np.ndarray,
    targets: np.ndarray,
    groups: Sequence[str],
    output_dir: Path,
    *,
    loss_mode: str,
    log_variance_l2: float = 0.0,
    num_heads: int = 5,
    hidden_dim: int = 256,
    max_epochs: int = 160,
    min_epochs: int = 12,
    patience: int = 15,
    batch_size: int = 256,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-5,
    seed: int = 20260907,
    device: str = "cuda",
) -> tuple[list[dict[str, object]], list[dict[str, object]], np.ndarray]:
    """Train independent group-bootstrap heads with head-specific OOB stopping."""
    import torch

    features = np.asarray(features, dtype=np.float32)
    targets = np.asarray(targets, dtype=np.float32)
    groups = np.asarray(groups).astype(str)
    unique_groups = np.unique(groups)
    if len(unique_groups) < 5:
        raise ValueError("P4b training needs at least five trajectory groups")
    if loss_mode not in {"gaussian_nll", "mean_mse"}:
        raise ValueError(f"Unsupported loss mode: {loss_mode}")
    output_dir.mkdir(parents=True, exist_ok=True)
    x_all = torch.from_numpy(features)
    y_all = torch.from_numpy(targets)
    summaries: list[dict[str, object]] = []
    histories: list[dict[str, object]] = []
    oob_squared_errors: list[np.ndarray] = []

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
        if not len(oob_indices):
            raise RuntimeError(f"Head {head_index} has no OOB trajectory groups")

        torch.manual_seed(head_seed)
        if device.startswith("cuda"):
            torch.cuda.manual_seed_all(head_seed)
        model = build_gaussian_head(
            features.shape[1], targets.shape[1], hidden_dim
        ).to(device)
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        best_epoch = 0
        best_validation = float("inf")
        best_state = None
        stale_epochs = 0

        for epoch in range(1, max_epochs + 1):
            model.train()
            train_losses = []
            for start in range(0, len(train_indices), batch_size):
                if start == 0:
                    permutation = rng.permutation(train_indices)
                index = permutation[start : start + batch_size]
                batch_x = x_all[index].to(device)
                batch_y = y_all[index].to(device)
                mean, log_variance = model(batch_x)
                loss = _loss(
                    mean,
                    log_variance,
                    batch_y,
                    loss_mode,
                    log_variance_l2,
                )
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                train_losses.append(float(loss.detach().cpu()))

            model.eval()
            with torch.inference_mode():
                validation_mean, validation_log_variance = model(
                    x_all[oob_indices].to(device)
                )
                validation_loss = float(
                    _loss(
                        validation_mean,
                        validation_log_variance,
                        y_all[oob_indices].to(device),
                        loss_mode,
                        log_variance_l2,
                    ).cpu()
                )
            histories.append(
                {
                    "head": head_index,
                    "epoch": epoch,
                    "train_loss": float(np.mean(train_losses)),
                    "oob_loss": validation_loss,
                }
            )
            if validation_loss < best_validation - 1e-5:
                best_validation = validation_loss
                best_epoch = epoch
                best_state = copy.deepcopy(model.state_dict())
                stale_epochs = 0
            else:
                stale_epochs += 1
            if epoch >= min_epochs and stale_epochs >= patience:
                break

        if best_state is None:
            raise RuntimeError(f"Head {head_index} never produced a checkpoint")
        model.load_state_dict(best_state)
        model.eval()
        with torch.inference_mode():
            oob_mean, _oob_log_variance = model(x_all[oob_indices].to(device))
        oob_squared_errors.append(
            np.square(oob_mean.float().cpu().numpy() - targets[oob_indices])
        )
        torch.save(model.state_dict(), output_dir / f"head_{head_index}.pt")
        summaries.append(
            {
                "head": head_index,
                "seed": head_seed,
                "bootstrap_rows": len(train_indices),
                "bootstrap_unique_groups": len(sampled_set),
                "oob_rows": len(oob_indices),
                "best_epoch": best_epoch,
                "best_oob_loss": best_validation,
                "stopped_epoch": epoch,
                "sampled_groups": sampled_groups.tolist(),
            }
        )
        del model
        if device.startswith("cuda"):
            torch.cuda.empty_cache()

    shared_variance = np.clip(
        np.concatenate(oob_squared_errors, axis=0).mean(axis=0), 1e-5, 1e5
    ).astype(np.float32)
    return summaries, histories, shared_variance


def predict_heads(
    features: np.ndarray,
    artifact_dir: Path,
    *,
    device: str = "cuda",
    batch_size: int = 512,
) -> tuple[np.ndarray, np.ndarray]:
    import torch

    metadata = json.loads((artifact_dir / "ensemble.json").read_text())
    values = torch.from_numpy(np.asarray(features, dtype=np.float32))
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
        head_means = []
        head_variances = []
        with torch.inference_mode():
            for start in range(0, len(values), batch_size):
                mean, log_variance = model(
                    values[start : start + batch_size].to(device)
                )
                head_means.append(mean.float().cpu().numpy())
                head_variances.append(
                    torch.exp(log_variance.float()).cpu().numpy()
                )
        means.append(np.concatenate(head_means))
        variances.append(np.concatenate(head_variances))
        del model
    return np.stack(means), np.stack(variances)


def artifact_variances(
    predicted_variances: np.ndarray,
    artifact_dir: Path,
) -> np.ndarray:
    metadata = json.loads((artifact_dir / "ensemble.json").read_text())
    if metadata.get("loss_mode", "gaussian_nll") != "mean_mse":
        return np.asarray(predicted_variances, dtype=np.float32)
    shared = np.load(artifact_dir / "shared_variance.npy", allow_pickle=False)
    shape = np.asarray(predicted_variances).shape
    return np.broadcast_to(shared.reshape(1, 1, -1), shape).copy()


def calibrate_variance_temperature(
    means: np.ndarray,
    variances: np.ndarray,
    targets: np.ndarray,
    calibration_indices: np.ndarray,
    *,
    log10_min: float = -2.0,
    log10_max: float = 4.0,
    grid_size: int = 73,
) -> tuple[float, float]:
    indices = np.asarray(calibration_indices, dtype=np.int64)
    if not len(indices):
        raise ValueError("Variance temperature needs calibration rows")
    temperatures = np.logspace(log10_min, log10_max, grid_size)
    losses = np.asarray(
        [
            mixture_nll(
                means[:, indices],
                variances[:, indices] * temperature,
                targets[indices],
            ).mean()
            for temperature in temperatures
        ]
    )
    best = int(np.nanargmin(losses))
    return float(temperatures[best]), float(losses[best])


def monte_carlo_predictive_mi(
    means: np.ndarray,
    variances: np.ndarray,
    *,
    samples_per_head: int = 32,
    seed: int = 20260907,
    device: str = "cpu",
    batch_size: int = 256,
) -> np.ndarray:
    """Estimate I(ensemble member; residual) with deterministic antithetic draws."""
    import torch

    means_tensor = torch.from_numpy(np.asarray(means, dtype=np.float32)).to(device)
    variance_tensor = torch.from_numpy(
        np.asarray(variances, dtype=np.float32)
    ).to(device)
    heads, rows, dimensions = means_tensor.shape
    if samples_per_head < 2 or samples_per_head % 2:
        raise ValueError("samples_per_head must be a positive even integer")
    generator = torch.Generator(device=device).manual_seed(seed)
    half = torch.randn(
        (samples_per_head // 2, dimensions),
        generator=generator,
        device=device,
    )
    noise = torch.cat([half, -half], dim=0)
    constant = dimensions * math.log(2.0 * math.pi)
    results = []
    for start in range(0, rows, batch_size):
        mean = means_tensor[:, start : start + batch_size]
        variance = variance_tensor[:, start : start + batch_size]
        samples = mean[:, :, None, :] + torch.sqrt(variance)[:, :, None, :] * noise[
            None, None
        ]
        evaluator_mean = mean.permute(1, 0, 2)[None, :, None]
        evaluator_variance = variance.permute(1, 0, 2)[None, :, None]
        delta = samples[:, :, :, None, :] - evaluator_mean
        log_density = -0.5 * (
            constant
            + torch.log(evaluator_variance).sum(dim=-1)
            + torch.square(delta).div(evaluator_variance).sum(dim=-1)
        )
        log_mixture = torch.logsumexp(log_density, dim=-1) - math.log(heads)
        source_indices = torch.arange(heads, device=device)
        source_log_density = log_density[source_indices, :, :, source_indices]
        mutual_information = (source_log_density - log_mixture).mean(dim=(0, 2))
        results.append(mutual_information.float().cpu().numpy())
    return np.concatenate(results)


def residual_risk_scores(
    means: np.ndarray,
    variances: np.ndarray,
    *,
    temperature: float = 1.0,
    mc_samples_per_head: int = 32,
    mc_seed: int = 20260907,
    mc_device: str = "cpu",
) -> dict[str, np.ndarray]:
    means = np.asarray(means, dtype=np.float32)
    variances = np.asarray(variances, dtype=np.float32) * float(temperature)
    mean = means.mean(axis=0)
    epistemic = means.var(axis=0)
    aleatoric = variances.mean(axis=0)
    shared = np.broadcast_to(aleatoric[None], variances.shape)
    return {
        "epistemic_mean": epistemic.mean(axis=1),
        "predicted_mean_residual_rms": np.sqrt(np.mean(np.square(mean), axis=1)),
        "mean_plus_epistemic_rms": np.sqrt(
            np.mean(np.square(mean) + epistemic, axis=1)
        ),
        "expected_residual_rms": np.sqrt(
            np.mean(np.square(mean) + epistemic + aleatoric, axis=1)
        ),
        "epistemic_snr": np.mean(epistemic / np.maximum(aleatoric, 1e-8), axis=1),
        "common_covariance_jrd": jensen_renyi_divergence(means, shared),
        "mc_predictive_mi": monte_carlo_predictive_mi(
            means,
            variances,
            samples_per_head=mc_samples_per_head,
            seed=mc_seed,
            device=mc_device,
        ),
    }


def within_snapshot_score(
    candidate_values: Sequence[float],
    candidate_risk: Sequence[float],
    risk_lambda: float,
) -> np.ndarray:
    values = np.asarray(candidate_values, dtype=np.float64)
    risk = np.asarray(candidate_risk, dtype=np.float64)
    if values.shape != risk.shape or values.ndim != 1:
        raise ValueError("Candidate value and risk vectors must have the same shape")

    def standardize(array: np.ndarray) -> np.ndarray:
        finite = np.isfinite(array)
        if not finite.any():
            return np.zeros_like(array)
        filled = array.copy()
        filled[~finite] = float(np.nanmean(array[finite]))
        scale = float(filled.std())
        return np.zeros_like(filled) if scale < 1e-8 else (filled - filled.mean()) / scale

    value_z = standardize(values)
    log_risk = np.log(np.maximum(risk, 1e-12))
    risk_z = standardize(log_risk)
    return value_z - float(risk_lambda) * risk_z


def select_candidate(
    candidate_values: Sequence[float],
    candidate_risk: Sequence[float],
    risk_lambda: float,
) -> int:
    scores = within_snapshot_score(candidate_values, candidate_risk, risk_lambda)
    values = np.asarray(candidate_values, dtype=np.float64)
    order = np.lexsort((np.arange(len(values)), -values, -scores))
    return int(order[0])


def score_from_artifact(
    input_features: np.ndarray,
    artifact_dir: Path,
    *,
    temperature: float,
    device: str,
    batch_size: int = 512,
    mc_samples_per_head: int = 32,
    mc_seed: int = 20260907,
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    means, predicted_variances = predict_heads(
        input_features, artifact_dir, device=device, batch_size=batch_size
    )
    variances = artifact_variances(predicted_variances, artifact_dir)
    scores = residual_risk_scores(
        means,
        variances,
        temperature=temperature,
        mc_samples_per_head=mc_samples_per_head,
        mc_seed=mc_seed,
        mc_device=device,
    )
    return scores, means, variances


def json_ready(value):
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value

#!/usr/bin/env python3
"""Leakage-safe features and bounded potential-outcome models for feedback routing."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit


CORE_FRAME_FEATURES = (
    "value_mean",
    "value_std",
    "value_range",
    "action_std_mean",
    "action_std_max",
    "action_first_step_l2_std",
    "action_pairwise_l2_mean",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_across_seed_std_mean",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_action_consensus_first_mean",
    "candidate_action_consensus_chunk_mean",
    "planning_predicted_proprio_error",
)

IDENTITY_COLUMNS = (
    "snapshot_id",
    "source_run",
    "sidecar_path",
    "position_level",
    "task_id",
    "init_state_id",
    "rollout_id",
    "rollout_seed",
    "query_idx",
    "task_description",
    "phase_at_snapshot",
)

LABEL_COLUMNS = ("commit_success", "feedback_success", "terminal_effect")

FORBIDDEN_FEATURE_FRAGMENTS = (
    "terminal",
    "success",
    "failure",
    "observed",
    "actual_object",
    "feedback_endpoint",
    "local_utility",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _safe_norm(values: np.ndarray, axis: int | None = None) -> np.ndarray | float:
    result = np.linalg.norm(np.asarray(values, dtype=float), axis=axis)
    return float(result) if np.ndim(result) == 0 else result


def _safe_cosine(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float).reshape(-1)
    right = np.asarray(right, dtype=float).reshape(-1)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return 0.0
    return float(np.dot(left, right) / denominator)


def _segment_features(
    result: dict[str, float], name: str, actions: np.ndarray
) -> None:
    xyz = actions[:, :3]
    rotation = actions[:, 3:6]
    for modality, values in (("xyz", xyz), ("rot", rotation)):
        step_norm = np.linalg.norm(values, axis=1)
        path = float(step_norm.sum())
        result[f"f_action_{name}_{modality}_mean"] = float(step_norm.mean())
        result[f"f_action_{name}_{modality}_std"] = float(step_norm.std())
        result[f"f_action_{name}_{modality}_max"] = float(step_norm.max())
        result[f"f_action_{name}_{modality}_path"] = path
        result[f"f_action_{name}_{modality}_straightness"] = float(
            np.linalg.norm(values.sum(axis=0)) / (path + 1e-8)
        )
    if len(actions) > 1:
        temporal_change = np.linalg.norm(np.diff(actions[:, :6], axis=0), axis=1)
        result[f"f_action_{name}_smoothness_mean"] = float(temporal_change.mean())
        result[f"f_action_{name}_smoothness_max"] = float(temporal_change.max())
    else:
        result[f"f_action_{name}_smoothness_mean"] = 0.0
        result[f"f_action_{name}_smoothness_max"] = 0.0


def _normalized_quaternion(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float).reshape(-1)
    norm = float(np.linalg.norm(values))
    return values / norm if norm > 1e-12 else np.zeros_like(values)


def derive_invariant_sidecar_features(path: Path) -> dict[str, float]:
    """Derive relative features from arrays available before feedback is queried."""
    with np.load(path, allow_pickle=False) as payload:
        selected = int(np.asarray(payload["selected_max_value_idx"]).item())
        actions_all = np.asarray(payload["candidate_actions"], dtype=float)
        values = np.asarray(payload["candidate_values"], dtype=float).reshape(-1)
        predicted_all = np.asarray(
            payload["candidate_predicted_future_proprio"], dtype=float
        )
        current = np.asarray(payload["current_proprio"], dtype=float).reshape(-1)

    if actions_all.ndim != 3 or actions_all.shape[1:] != (16, 7):
        raise ValueError(f"Expected candidate actions [K,16,7], got {actions_all.shape}")
    if predicted_all.ndim != 2 or predicted_all.shape[1] != 9:
        raise ValueError(
            f"Expected candidate future proprio [K,9], got {predicted_all.shape}"
        )
    if current.shape != (9,):
        raise ValueError(f"Expected current proprio [9], got {current.shape}")
    if not 0 <= selected < len(actions_all) or len(values) != len(actions_all):
        raise ValueError(f"Invalid selected candidate {selected} for {path}")

    actions = actions_all[selected]
    predicted = predicted_all[selected]
    result: dict[str, float] = {}
    _segment_features(result, "all", actions)
    _segment_features(result, "prefix", actions[:8])
    _segment_features(result, "tail", actions[8:])

    gripper = actions[:, 6]
    signs = np.sign(gripper)
    result.update(
        {
            "f_action_gripper_first_mode": float(signs[0]),
            "f_action_gripper_query_mode": float(signs[7]),
            "f_action_gripper_tail_first_mode": float(signs[8]),
            "f_action_gripper_last_mode": float(signs[-1]),
            "f_action_gripper_positive_fraction": float(np.mean(gripper > 0)),
            "f_action_gripper_transition_count": float(
                np.sum(signs[1:] != signs[:-1])
            ),
            "f_action_gripper_boundary_change": float(
                abs(gripper[8] - gripper[7])
            ),
            "f_action_boundary_xyz_jump": float(
                np.linalg.norm(actions[8, :3] - actions[7, :3])
            ),
            "f_action_boundary_rot_jump": float(
                np.linalg.norm(actions[8, 3:6] - actions[7, 3:6])
            ),
        }
    )

    # LIBERO proprio order is gripper qpos (2), EEF position (3), quaternion (4).
    gripper_delta = predicted[:2] - current[:2]
    position_delta = predicted[2:5] - current[2:5]
    current_quat = _normalized_quaternion(current[5:9])
    predicted_quat = _normalized_quaternion(predicted[5:9])
    quat_similarity = float(np.clip(abs(np.dot(current_quat, predicted_quat)), 0, 1))
    result.update(
        {
            "f_current_gripper_mean": float(current[:2].mean()),
            "f_current_gripper_spread": float(abs(current[0] - current[1])),
            "f_future_gripper_delta_mean": float(gripper_delta.mean()),
            "f_future_gripper_delta_norm": float(np.linalg.norm(gripper_delta)),
            "f_future_position_delta_norm": float(np.linalg.norm(position_delta)),
            "f_future_position_delta_xy_norm": float(
                np.linalg.norm(position_delta[:2])
            ),
            "f_future_position_delta_z": float(position_delta[2]),
            "f_future_quaternion_angle": float(2 * math.acos(quat_similarity)),
            "f_future_action_xyz_alignment": _safe_cosine(
                actions[:, :3].sum(axis=0), position_delta
            ),
        }
    )

    candidate_positions = predicted_all[:, 2:5]
    position_center = candidate_positions.mean(axis=0)
    candidate_gripper = predicted_all[:, :2]
    reference_quat = _normalized_quaternion(predicted_all[0, 5:9])
    quaternion_distances = []
    for row in predicted_all[:, 5:9]:
        quaternion_distances.append(
            1.0 - abs(float(np.dot(reference_quat, _normalized_quaternion(row))))
        )
    sorted_values = np.sort(values[np.isfinite(values)])
    value_margin = (
        float(sorted_values[-1] - sorted_values[-2])
        if len(sorted_values) >= 2
        else 0.0
    )
    result.update(
        {
            "f_pool_selected_value": float(values[selected]),
            "f_pool_value_margin": value_margin,
            "f_pool_future_position_spread": float(
                np.linalg.norm(candidate_positions - position_center, axis=1).mean()
            ),
            "f_pool_selected_position_deviation": float(
                np.linalg.norm(candidate_positions[selected] - position_center)
            ),
            "f_pool_future_gripper_spread": float(
                np.std(candidate_gripper, axis=0).mean()
            ),
            "f_pool_future_quaternion_dispersion": float(
                np.mean(quaternion_distances)
            ),
            "f_pool_action_across_candidate_std": float(
                np.linalg.norm(np.std(actions_all[:, :, :6], axis=0), axis=1).mean()
            ),
        }
    )
    return result


def context_features(position_level: str) -> dict[str, float]:
    level = str(position_level)
    if len(level) < 2 or level[0] not in {"x", "y"}:
        raise ValueError(f"Unsupported position level: {level!r}")
    magnitude = float(level[1:])
    return {
        "f_context_direction_x": float(level.startswith("x")),
        "f_context_magnitude": magnitude,
        "f_context_level_x0p2": float(level == "x0.2"),
        "f_context_level_y0p1": float(level == "y0.1"),
        "f_context_level_y0p2": float(level == "y0.2"),
        "f_context_level_y0p3": float(level == "y0.3"),
    }


def privileged_phase_features(phase: str) -> dict[str, float]:
    phase = str(phase).lower()
    return {
        "f_priv_phase_approach": float(phase == "approach"),
        "f_priv_phase_grasp": float(phase == "grasp"),
        "f_priv_phase_transport": float(phase == "transport"),
        "f_priv_phase_release": float(phase == "release"),
    }


def validate_feature_names(features: Iterable[str]) -> None:
    for feature in features:
        lowered = str(feature).lower()
        if not lowered.startswith("f_"):
            raise ValueError(f"Model feature lacks the f_ allowlist prefix: {feature}")
        if any(fragment in lowered for fragment in FORBIDDEN_FEATURE_FRAGMENTS):
            raise ValueError(f"Outcome leakage in feature: {feature}")


def feature_families(frame: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    core = sorted(
        column
        for column in frame
        if column.startswith(("f_core_", "f_action_", "f_current_", "f_future_", "f_pool_"))
    )
    context = sorted(column for column in frame if column.startswith("f_context_"))
    phase = sorted(column for column in frame if column.startswith("f_priv_phase_"))
    families = {
        "relative": tuple(core),
        "relative_context": tuple(core + context),
        "privileged_phase_diagnostic": tuple(core + context + phase),
    }
    for features in families.values():
        validate_feature_names(features)
    return families


def build_prequery_dataset(
    source: pd.DataFrame, campaign_dir: Path, *, require_labels: bool = True
) -> pd.DataFrame:
    required = set(IDENTITY_COLUMNS + CORE_FRAME_FEATURES)
    if require_labels:
        required.update(LABEL_COLUMNS)
    missing = sorted(required - set(source.columns))
    if missing:
        raise ValueError(f"Missing source columns: {missing}")
    rows: list[dict[str, Any]] = []
    for row in source.itertuples(index=False):
        record = {column: getattr(row, column) for column in IDENTITY_COLUMNS}
        record.update(
            {
                column: getattr(row, column)
                for column in LABEL_COLUMNS
                if hasattr(row, column)
            }
        )
        record["independent_group"] = (
            f"{row.position_level}|task{int(row.task_id)}|init{int(row.init_state_id)}"
        )
        for feature in CORE_FRAME_FEATURES:
            record[f"f_core_{feature}"] = getattr(row, feature)
        sidecar = (
            campaign_dir
            / "runs"
            / f"{row.source_run}__snapshots"
            / Path(str(row.sidecar_path)).name
        )
        if not sidecar.is_file():
            raise FileNotFoundError(sidecar)
        record.update(derive_invariant_sidecar_features(sidecar))
        record.update(context_features(str(row.position_level)))
        record.update(privileged_phase_features(str(row.phase_at_snapshot)))
        rows.append(record)
    result = pd.DataFrame(rows)
    validate_feature_names(column for column in result if column.startswith("f_"))
    return result


@dataclass(frozen=True)
class RobustScaler:
    median: np.ndarray
    scale: np.ndarray
    active: np.ndarray
    clip: float = 5.0

    def to_payload(self) -> dict[str, Any]:
        return {
            "median": self.median.tolist(),
            "scale": self.scale.tolist(),
            "active": self.active.astype(int).tolist(),
            "clip": float(self.clip),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RobustScaler":
        return cls(
            median=np.asarray(payload["median"], dtype=float),
            scale=np.asarray(payload["scale"], dtype=float),
            active=np.asarray(payload["active"], dtype=bool),
            clip=float(payload["clip"]),
        )


def numeric_matrix(frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    missing = [feature for feature in features if feature not in frame]
    if missing:
        raise ValueError(f"Missing model features: {missing}")
    return frame.loc[:, list(features)].apply(pd.to_numeric, errors="coerce").to_numpy(float)


def fit_robust_scaler(values: np.ndarray, clip: float = 5.0) -> RobustScaler:
    values = np.asarray(values, dtype=float)
    median_all = np.nanmedian(values, axis=0)
    median_all = np.where(np.isfinite(median_all), median_all, 0.0)
    imputed = np.where(np.isfinite(values), values, median_all)
    std = np.std(imputed, axis=0)
    active = std > 1e-10
    if not np.any(active):
        raise ValueError("All model features are constant")
    active_values = imputed[:, active]
    median = median_all[active]
    quartiles = np.quantile(active_values, [0.25, 0.75], axis=0)
    robust_scale = (quartiles[1] - quartiles[0]) / 1.349
    fallback = np.std(active_values, axis=0)
    scale = np.where(robust_scale > 1e-6, robust_scale, fallback)
    scale = np.where(scale > 1e-6, scale, 1.0)
    return RobustScaler(median=median, scale=scale, active=active, clip=clip)


def transform_values(
    values: np.ndarray, scaler: RobustScaler, *, clipped: bool = True
) -> np.ndarray:
    selected = np.asarray(values, dtype=float)[:, scaler.active]
    selected = np.where(np.isfinite(selected), selected, scaler.median)
    standardized = (selected - scaler.median) / scaler.scale
    if clipped:
        standardized = np.clip(standardized, -scaler.clip, scaler.clip)
    return standardized


def fit_binary_logit(
    values: np.ndarray, target: np.ndarray, *, alpha: float
) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    target = np.asarray(target, dtype=float)
    if len(values) != len(target):
        raise ValueError("Feature and target lengths differ")
    if np.all(target == target[0]):
        probability = float((target.sum() + 0.5) / (len(target) + 1.0))
        return {"kind": "constant", "probability": probability}
    design = np.column_stack([np.ones(len(values)), values])

    def objective(weights: np.ndarray) -> tuple[float, np.ndarray]:
        logits = design @ weights
        loss = float(
            np.mean(np.logaddexp(0.0, logits) - target * logits)
            + 0.5 * alpha * np.dot(weights[1:], weights[1:])
        )
        gradient = design.T @ (expit(logits) - target) / len(target)
        gradient[1:] += alpha * weights[1:]
        return loss, gradient

    fitted = minimize(
        objective,
        np.zeros(design.shape[1]),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 500, "ftol": 1e-11},
    )
    if not fitted.success:
        raise RuntimeError(f"Logistic fit failed: {fitted.message}")
    return {"kind": "logit", "coefficients": fitted.x.tolist()}


def predict_binary_logit(model: Mapping[str, Any], values: np.ndarray) -> np.ndarray:
    if model["kind"] == "constant":
        return np.full(len(values), float(model["probability"]), dtype=float)
    coefficients = np.asarray(model["coefficients"], dtype=float)
    design = np.column_stack([np.ones(len(values)), values])
    return expit(design @ coefficients)


def fit_potential_ensemble(
    values: np.ndarray,
    commit: np.ndarray,
    feedback: np.ndarray,
    groups: Sequence[str],
    *,
    alpha: float,
    estimators: int,
    seed: int,
) -> list[dict[str, Any]]:
    values = np.asarray(values, dtype=float)
    commit = np.asarray(commit, dtype=float)
    feedback = np.asarray(feedback, dtype=float)
    groups = np.asarray(groups, dtype=str)
    unique_groups = np.unique(groups)
    if estimators < 1:
        raise ValueError("estimators must be positive")
    rng = np.random.default_rng(seed)
    models = []
    for _ in range(estimators):
        if estimators == 1:
            indices = np.arange(len(values))
        else:
            sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
            indices = np.concatenate([np.flatnonzero(groups == group) for group in sampled_groups])
        models.append(
            {
                "commit": fit_binary_logit(values[indices], commit[indices], alpha=alpha),
                "feedback": fit_binary_logit(
                    values[indices], feedback[indices], alpha=alpha
                ),
            }
        )
    return models


def predict_potential_ensemble(
    models: Sequence[Mapping[str, Any]], values: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    commit = np.stack(
        [predict_binary_logit(model["commit"], values) for model in models], axis=1
    )
    feedback = np.stack(
        [predict_binary_logit(model["feedback"], values) for model in models], axis=1
    )
    treatment = feedback - commit
    return (
        commit.mean(axis=1),
        feedback.mean(axis=1),
        treatment.mean(axis=1),
        treatment.std(axis=1),
    )


def fit_support_reference(
    standardized_values: np.ndarray,
    groups: Sequence[str],
    *,
    quantile: float = 0.99,
    distance_clip: float = 10.0,
) -> dict[str, Any]:
    values = np.clip(np.asarray(standardized_values, dtype=float), -distance_clip, distance_clip)
    groups = np.asarray(groups, dtype=str)
    distances = np.full(len(values), np.inf)
    denominator = math.sqrt(values.shape[1])
    for index in range(len(values)):
        eligible = groups != groups[index]
        if np.any(eligible):
            distances[index] = float(
                np.min(np.linalg.norm(values[eligible] - values[index], axis=1))
                / denominator
            )
    finite = distances[np.isfinite(distances)]
    if not len(finite):
        raise ValueError("Cannot calibrate support distance without independent groups")
    return {
        "train_values": values.tolist(),
        "threshold": float(np.quantile(finite, quantile)),
        "quantile": float(quantile),
        "distance_clip": float(distance_clip),
    }


def support_distance(
    standardized_values: np.ndarray, reference: Mapping[str, Any]
) -> np.ndarray:
    train = np.asarray(reference["train_values"], dtype=float)
    clip = float(reference["distance_clip"])
    test = np.clip(np.asarray(standardized_values, dtype=float), -clip, clip)
    denominator = math.sqrt(train.shape[1])
    result = np.empty(len(test), dtype=float)
    for index, row in enumerate(test):
        result[index] = float(np.min(np.linalg.norm(train - row, axis=1)) / denominator)
    return result


def apply_support_mode(
    mode: str,
    *,
    levels: Sequence[str],
    known_levels: Iterable[str],
    distances: np.ndarray,
    distance_threshold: float | np.ndarray,
) -> np.ndarray:
    level_supported = np.isin(np.asarray(levels, dtype=str), list(known_levels))
    distance_supported = np.asarray(distances, dtype=float) <= np.asarray(
        distance_threshold, dtype=float
    )
    if mode == "none":
        return np.ones(len(level_supported), dtype=bool)
    if mode == "known_level":
        return level_supported
    if mode == "knn_q99":
        return distance_supported
    if mode == "known_level_knn_q99":
        return level_supported & distance_supported
    raise ValueError(f"Unknown support mode: {mode}")


def predict_frozen_cate(
    payload: Mapping[str, Any], frame: pd.DataFrame
) -> pd.DataFrame:
    """Apply a frozen potential-outcome ensemble and its immutable support gate."""
    features = list(payload["features"])
    validate_feature_names(features)
    values = numeric_matrix(frame, features)
    scaler = RobustScaler.from_payload(payload["scaler"])
    model_values = transform_values(values, scaler, clipped=True)
    support_values = transform_values(values, scaler, clipped=False)
    p_commit, p_feedback, cate, cate_std = predict_potential_ensemble(
        payload["models"], model_values
    )
    support = payload["support"]
    distances = support_distance(support_values, support)
    supported = apply_support_mode(
        str(payload["router"]["support_mode"]),
        levels=frame["position_level"].astype(str),
        known_levels=support["known_levels"],
        distances=distances,
        distance_threshold=float(support["threshold"]),
    )
    beta = float(payload["router"]["beta"])
    query_cost = float(payload["router"]["query_cost"])
    score = cate - beta * cate_std
    return pd.DataFrame(
        {
            "predicted_commit_probability": p_commit,
            "predicted_feedback_probability": p_feedback,
            "predicted_cate": cate,
            "predicted_cate_std": cate_std,
            "router_score": score,
            "support_distance": distances,
            "support_threshold": float(support["threshold"]),
            "supported": supported,
            "router_query": supported & (score > query_cost),
        },
        index=frame.index,
    )

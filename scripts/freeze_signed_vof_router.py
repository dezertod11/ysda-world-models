#!/usr/bin/env python3
"""Freeze the development signed-VoF ridge router for prospective evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

try:
    from analyze_signed_vof_router import (
        MODEL_SPECS,
        _numeric_matrix,
        fit_ridge_model,
        predict_ridge_model,
        validate_feature_manifest,
    )
except ModuleNotFoundError:
    from scripts.analyze_signed_vof_router import (
        MODEL_SPECS,
        _numeric_matrix,
        fit_ridge_model,
        predict_ridge_model,
        validate_feature_manifest,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = (
    PROJECT_ROOT
    / "experiments/campaigns/object_q4_position_direction_holdout_20260902"
    / "analysis/signed_vof_router_development/signed_vof_dataset.parquet"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "experiments/frozen_models/signed_vof_pre_state_action_a10_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _absolute_threshold(scores: np.ndarray, query_rate: float) -> tuple[float, str, int]:
    finite = np.sort(scores[np.isfinite(scores)])
    if not len(finite):
        raise ValueError("No finite calibration scores")
    count = min(len(finite), max(1, int(math.ceil(len(finite) * query_rate))))
    selected_minimum = float(finite[-count])
    if count == len(finite):
        return float(np.nextafter(finite[0], -np.inf)), ">", count
    rejected_maximum = float(finite[-count - 1])
    if selected_minimum > rejected_maximum:
        return (selected_minimum + rejected_maximum) / 2.0, ">", count
    return selected_minimum, ">=", int(np.sum(finite >= selected_minimum))


def predict_frozen_payload(
    payload: Mapping[str, Any], frame: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return predicted signed VoF, predictive std, and frozen router score."""
    features = list(payload["active_features"])
    missing = [feature for feature in features if feature not in frame]
    if missing:
        raise ValueError(f"Missing frozen-router features: {missing}")
    values = frame.loc[:, features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    median = np.asarray(payload["preprocessing"]["impute_median"], dtype=float)
    mean = np.asarray(payload["preprocessing"]["mean"], dtype=float)
    scale = np.asarray(payload["preprocessing"]["scale"], dtype=float)
    values = np.where(np.isfinite(values), values, median)
    standardized = (values - mean) / scale
    design = np.column_stack([np.ones(len(standardized)), standardized])
    coefficients = np.asarray(payload["ridge"]["coefficients"], dtype=float)
    covariance = np.asarray(payload["ridge"]["covariance"], dtype=float)
    predicted_mean = design @ coefficients
    leverage = np.einsum("ij,jk,ik->i", design, covariance, design)
    predicted_std = float(payload["ridge"]["residual_scale"]) * np.sqrt(
        np.maximum(1.0 + leverage, 0.0)
    )
    score = predicted_mean - float(payload["router"]["beta"]) * predicted_std
    return predicted_mean, predicted_std, score


def select_with_frozen_threshold(payload: Mapping[str, Any], scores: np.ndarray) -> np.ndarray:
    threshold = float(payload["router"]["absolute_score_threshold"])
    operator = str(payload["router"]["threshold_operator"])
    if operator == ">":
        return np.isfinite(scores) & (scores > threshold)
    if operator == ">=":
        return np.isfinite(scores) & (scores >= threshold)
    raise ValueError(f"Unsupported threshold operator: {operator}")


def freeze_router(
    dataset_path: Path,
    *,
    model_name: str,
    beta: float,
    query_rate: float,
    query_cost: float,
) -> dict[str, Any]:
    validate_feature_manifest()
    specs = {spec.name: spec for spec in MODEL_SPECS}
    if model_name not in specs:
        raise ValueError(f"Unknown model {model_name!r}; choose from {sorted(specs)}")
    spec = specs[model_name]
    if spec.stage != "pre":
        raise ValueError("Only a pre-query router can be frozen for selective querying")

    frame = pd.read_parquet(dataset_path)
    values = _numeric_matrix(frame, spec.features)
    target = pd.to_numeric(frame["terminal_effect"], errors="raise").to_numpy(float)
    model = fit_ridge_model(values, target, alpha=spec.alpha)
    predicted_mean, predicted_std = predict_ridge_model(model, values)
    scores = predicted_mean - beta * predicted_std
    threshold, operator, expected_selected = _absolute_threshold(scores, query_rate)
    active_features = [spec.features[index] for index in model.active]

    payload: dict[str, Any] = {
        "schema_version": 1,
        "model_name": "signed_vof_pre_state_action_a10_v1",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "target": "feedback_terminal_success_minus_commit_terminal_success",
        "availability": "pre_query_q4",
        "training_source": str(dataset_path.resolve()),
        "training_source_sha256": _sha256(dataset_path),
        "training_rows": int(len(frame)),
        "training_groups": int(frame["independent_group"].nunique()),
        "training_cohorts": sorted(frame["cohort"].astype(str).unique().tolist()),
        "development_model_spec": model_name,
        "all_requested_features": list(spec.features),
        "active_features": active_features,
        "alpha": float(spec.alpha),
        "preprocessing": {
            "impute_median": model.median.tolist(),
            "mean": model.mean.tolist(),
            "scale": model.scale.tolist(),
        },
        "ridge": {
            "coefficients": model.coefficients.tolist(),
            "covariance": model.covariance.tolist(),
            "residual_scale": float(model.residual_scale),
        },
        "router": {
            "score": "predicted_vof_mean - beta * predicted_vof_std",
            "beta": float(beta),
            "query_cost": float(query_cost),
            "target_query_rate": float(query_rate),
            "absolute_score_threshold": float(threshold),
            "threshold_operator": operator,
            "calibration_selected": int(expected_selected),
            "calibration_rows": int(len(frame)),
        },
    }
    reproduced_mean, reproduced_std, reproduced_score = predict_frozen_payload(payload, frame)
    if not np.allclose(reproduced_mean, predicted_mean, rtol=0.0, atol=1e-12):
        raise AssertionError("Frozen mean predictions do not reproduce fitted model")
    if not np.allclose(reproduced_std, predicted_std, rtol=0.0, atol=1e-12):
        raise AssertionError("Frozen uncertainty does not reproduce fitted model")
    selected = select_with_frozen_threshold(payload, reproduced_score)
    effect = target * selected.astype(float)
    payload["calibration_description"] = {
        "selected": int(selected.sum()),
        "rescues": int(np.sum(selected & (target > 0))),
        "harms": int(np.sum(selected & (target < 0))),
        "neutral": int(np.sum(selected & (target == 0))),
        "raw_success_delta": float(effect.mean()),
        "query_cost_adjusted_delta": float(
            effect.mean() - query_cost * selected.mean()
        ),
        "warning": "Descriptive fit-set values only; not prospective evidence.",
    }
    payload["frozen_payload_sha256"] = _payload_sha256(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default="pre_state_action_a10")
    parser.add_argument("--beta", type=float, default=0.0)
    parser.add_argument("--query-rate", type=float, default=0.40)
    parser.add_argument("--query-cost", type=float, default=0.025)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = freeze_router(
        args.dataset,
        model_name=args.model,
        beta=args.beta,
        query_rate=args.query_rate,
        query_cost=args.query_cost,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen router: {args.output}")
    print(json.dumps(payload["router"], indent=2))
    print(json.dumps(payload["calibration_description"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

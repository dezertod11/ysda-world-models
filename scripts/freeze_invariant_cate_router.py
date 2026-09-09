#!/usr/bin/env python3
"""Freeze the selected bounded, support-aware CATE router."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from invariant_cate_router import (
        feature_families,
        fit_potential_ensemble,
        fit_robust_scaler,
        fit_support_reference,
        numeric_matrix,
        payload_sha256,
        predict_frozen_cate,
        sha256_file,
        transform_values,
    )
except ModuleNotFoundError:
    from scripts.invariant_cate_router import (
        feature_families,
        fit_potential_ensemble,
        fit_robust_scaler,
        fit_support_reference,
        numeric_matrix,
        payload_sha256,
        predict_frozen_cate,
        sha256_file,
        transform_values,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANALYSIS = (
    PROJECT_ROOT
    / "experiments/campaigns/signed_vof_new_task_holdout_20260903"
    / "analysis/invariant_cate_development"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "experiments/frozen_models/invariant_cate_relative_a01_v1.json"
)


def freeze_router(
    dataset_path: Path,
    decision_path: Path,
    *,
    estimators: int,
    seed: int,
) -> dict[str, object]:
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if not decision.get("fast_gate_pass"):
        raise ValueError("Development gate did not authorize freezing")
    selected = decision["selected"]
    family = str(selected["family"])
    if family.startswith("privileged_"):
        raise ValueError("Privileged diagnostic family cannot be frozen")
    frame = pd.read_parquet(dataset_path)
    features = list(feature_families(frame)[family])
    matrix = numeric_matrix(frame, features)
    scaler = fit_robust_scaler(matrix)
    model_values = transform_values(matrix, scaler, clipped=True)
    support_values = transform_values(matrix, scaler, clipped=False)
    groups = frame["independent_group"].astype(str).to_numpy()
    alpha = float(selected["alpha"])
    models = fit_potential_ensemble(
        model_values,
        frame["commit_success"].astype(int).to_numpy(),
        frame["feedback_success"].astype(int).to_numpy(),
        groups,
        alpha=alpha,
        estimators=estimators,
        seed=seed,
    )
    support = fit_support_reference(support_values, groups)
    support["known_levels"] = sorted(frame["position_level"].astype(str).unique())
    payload: dict[str, object] = {
        "schema_version": 1,
        "model_name": "invariant_cate_relative_a01_v1",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "availability": "pre_query_q4",
        "training_source": str(dataset_path.resolve()),
        "training_source_sha256": sha256_file(dataset_path),
        "development_decision": str(decision_path.resolve()),
        "development_decision_sha256": sha256_file(decision_path),
        "training_rows": int(len(frame)),
        "training_groups": int(frame["independent_group"].nunique()),
        "training_tasks": sorted(frame["task_id"].astype(int).unique().tolist()),
        "training_levels": sorted(frame["position_level"].astype(str).unique()),
        "potential_outcomes": {
            "commit": "P(terminal_success | commit old H16, x)",
            "feedback": "P(terminal_success | old H8, real observation, re-query H8, x)",
            "cate": "p_feedback - p_commit",
        },
        "feature_family": family,
        "features": features,
        "active_features": [
            feature for feature, active in zip(features, scaler.active) if active
        ],
        "alpha": alpha,
        "scaler": scaler.to_payload(),
        "ensemble": {
            "kind": "independent_bounded_logistic_heads",
            "estimators": int(estimators),
            "bootstrap_unit": "position_level_task_init_state",
            "seed": int(seed),
        },
        "models": models,
        "support": support,
        "router": {
            "score": "mean(p_feedback - p_commit) - beta * std(p_feedback - p_commit)",
            "beta": float(selected["beta"]),
            "support_mode": str(selected["support_mode"]),
            "query_cost": 0.025,
            "decision": "supported and score > query_cost",
        },
        "development_metrics": decision["selected_metrics"],
        "warning": "Frozen after development outcomes, before reserve holdout feedback outcomes.",
    }
    predictions = predict_frozen_cate(payload, frame)
    effect = frame["terminal_effect"].to_numpy(float)
    query = predictions["router_query"].to_numpy(bool)
    payload["fit_set_description"] = {
        "query_rate": float(query.mean()),
        "support_rate": float(predictions["supported"].mean()),
        "rescues": int(np.sum(query & (effect > 0))),
        "harms": int(np.sum(query & (effect < 0))),
        "adjusted_gain": float(np.mean(query * effect - 0.025 * query)),
        "warning": "Descriptive fit-set result only.",
    }
    payload["frozen_payload_sha256"] = payload_sha256(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=DEFAULT_ANALYSIS / "invariant_cate_dataset.parquet"
    )
    parser.add_argument(
        "--decision", type=Path, default=DEFAULT_ANALYSIS / "decision.json"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--estimators", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args()
    payload = freeze_router(
        args.dataset.expanduser().resolve(),
        args.decision.expanduser().resolve(),
        estimators=args.estimators,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen router: {args.output}")
    print(json.dumps(payload["router"], indent=2))
    print(json.dumps(payload["fit_set_description"], indent=2))
    print(f"Payload sha256: {payload['frozen_payload_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

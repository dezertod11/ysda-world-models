#!/usr/bin/env python3
"""Fit and validate the causal future-proprio error surrogate used online."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = (
    PROJECT_ROOT
    / "experiments/campaigns/libero_full_validation_20260724/analysis/full_validation/all_query_traces.parquet"
)
DEFAULT_TEST = (
    PROJECT_ROOT
    / "experiments/campaigns/denoise10_replication_20260730/analysis/full_validation/all_query_traces.parquet"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments/models/future_proprio_error_surrogate_v1.json"
FEATURES = [
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "candidate_value_mean",
    "future_proprio_std_mean",
]
TARGET = "prediction_error_future_proprio_l2"
EPISODE_KEYS = ["suite", "task_id", "init_state_id", "rollout_seed"]


def binary_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    labels = np.asarray(labels, dtype=bool)
    ranks = rankdata(np.asarray(scores, dtype=float))
    positives = int(labels.sum())
    negatives = int(len(labels) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    return float(
        (ranks[labels].sum() - positives * (positives + 1) / 2.0)
        / (positives * negatives)
    )


def load_max_value(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame = frame.loc[frame["planning_strategy"].eq("max_value")].copy()
    for column in FEATURES + [TARGET]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def log_design(frame: pd.DataFrame, medians: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    values = frame[FEATURES].to_numpy(dtype=float)
    logs = np.full_like(values, np.nan, dtype=float)
    valid = np.isfinite(values) & (values > 0.0)
    logs[valid] = np.log(np.clip(values[valid], 1e-10, None))
    if medians is None:
        medians = np.nanmedian(logs, axis=0)
    missing = ~np.isfinite(logs)
    logs[missing] = np.broadcast_to(medians, logs.shape)[missing]
    return logs, medians


def case_controlled_spearman(frame: pd.DataFrame, predictions: np.ndarray) -> float:
    predicted_ranks = pd.Series(predictions, index=frame.index).groupby(frame["case_id"]).rank()
    target_ranks = frame[TARGET].groupby(frame["case_id"]).rank()
    predicted_centered = predicted_ranks - predicted_ranks.groupby(frame["case_id"]).transform("mean")
    target_centered = target_ranks - target_ranks.groupby(frame["case_id"]).transform("mean")
    return float(spearmanr(predicted_centered, target_centered).statistic)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ridge", type=float, default=100.0)
    args = parser.parse_args()

    train = load_max_value(args.train)
    test = load_max_value(args.test)
    train_logs, medians = log_design(train)
    test_logs, _ = log_design(test, medians)
    train_target = np.log(np.clip(train[TARGET].to_numpy(dtype=float), 1e-10, None))
    test_target = np.log(np.clip(test[TARGET].to_numpy(dtype=float), 1e-10, None))
    train_valid = np.isfinite(train_target)
    test_valid = np.isfinite(test_target)
    train = train.loc[train_valid].copy()
    test = test.loc[test_valid].copy()
    train_logs = train_logs[train_valid]
    test_logs = test_logs[test_valid]
    train_target = train_target[train_valid]
    test_target = test_target[test_valid]

    means = train_logs.mean(axis=0)
    stds = train_logs.std(axis=0)
    stds[stds < 1e-8] = 1.0
    train_normalized = (train_logs - means) / stds
    test_normalized = (test_logs - means) / stds
    train_matrix = np.column_stack([np.ones(len(train_normalized)), train_normalized])
    test_matrix = np.column_stack([np.ones(len(test_normalized)), test_normalized])
    regularizer = np.eye(train_matrix.shape[1]) * float(args.ridge)
    regularizer[0, 0] = 0.0
    weights = np.linalg.solve(
        train_matrix.T @ train_matrix + regularizer,
        train_matrix.T @ train_target,
    )
    train_predictions = train_matrix @ weights
    test_predictions = test_matrix @ weights

    high_error = test.groupby("case_id")[TARGET].transform(
        lambda values: values >= values.quantile(0.75)
    )
    train_keys = set(map(tuple, train[EPISODE_KEYS].drop_duplicates().to_numpy()))
    test_keys = set(map(tuple, test[EPISODE_KEYS].drop_duplicates().to_numpy()))
    thresholds = {
        str(quantile): float(np.exp(np.quantile(train_predictions, quantile)))
        for quantile in (0.60, 0.75, 0.90)
    }
    artifact = {
        "schema_version": 1,
        "model_id": "future_proprio_error_surrogate_v1",
        "target": TARGET,
        "training_strategy": "max_value",
        "ridge_lambda": float(args.ridge),
        "features": FEATURES,
        "feature_transform": "log(max(x, 1e-10)), median imputation, train z-score",
        "feature_log_medians": medians.tolist(),
        "feature_log_means": means.tolist(),
        "feature_log_stds": stds.tolist(),
        "intercept": float(weights[0]),
        "coefficients": weights[1:].tolist(),
        "thresholds_by_train_prediction_quantile": thresholds,
        "train": {
            "path": str(args.train.relative_to(PROJECT_ROOT)),
            "queries": int(len(train)),
            "episodes": int(len(train_keys)),
        },
        "test": {
            "path": str(args.test.relative_to(PROJECT_ROOT)),
            "queries": int(len(test)),
            "episodes": int(len(test_keys)),
            "episode_key_overlap_with_train": int(len(train_keys & test_keys)),
            "spearman": float(spearmanr(test_predictions, test_target).statistic),
            "case_controlled_spearman": case_controlled_spearman(test, test_predictions),
            "case_relative_top_quartile_error_auc": binary_auc(
                high_error.to_numpy(dtype=bool), test_predictions
            ),
            "alarm_rates": {
                quantile: float((np.exp(test_predictions) >= threshold).mean())
                for quantile, threshold in thresholds.items()
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()

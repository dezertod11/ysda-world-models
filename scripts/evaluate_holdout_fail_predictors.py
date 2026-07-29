#!/usr/bin/env python3
"""Evaluate fail-risk rules trained on one uncertainty run against a holdout run."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_fail_prediction_from_online_metrics import auc_for_scores, best_threshold_metrics


def _first_existing(df: pd.DataFrame, *names: str) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _z(values: pd.Series, train_values: pd.Series) -> np.ndarray:
    mean = float(np.nanmean(train_values.to_numpy(dtype=float)))
    std = float(np.nanstd(train_values.to_numpy(dtype=float)))
    if not np.isfinite(std) or std < 1e-12:
        std = 1.0
    return (values.to_numpy(dtype=float) - mean) / std


def _risk_scores_with_train_stats(train: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    value_parts: list[np.ndarray] = []
    for col in [
        _first_existing(df, "value_std__mean", "value_std"),
        _first_existing(df, "value_range__mean", "value_range"),
        _first_existing(
            df,
            "latent_value_element_std_mean_mean_over_samples__mean",
            "latent_value_element_std_mean_mean_over_samples",
        ),
    ]:
        if col and col in train.columns:
            value_parts.append(-_z(df[col], train[col]))
    value_mean_col = _first_existing(df, "value_mean__mean", "value_mean")
    if value_mean_col and value_mean_col in train.columns:
        value_parts.append(-0.5 * _z(df[value_mean_col], train[value_mean_col]))
    out["risk_overconfidence_value"] = np.mean(value_parts, axis=0) if value_parts else np.nan

    action_parts: list[np.ndarray] = []
    for col in [
        _first_existing(df, "action_first_step_l2_std__mean", "action_first_step_l2_std"),
        _first_existing(
            df,
            "latent_action_first_step_copy_l2_std_mean_over_samples__mean",
            "latent_action_first_step_copy_l2_std_mean_over_samples",
        ),
    ]:
        if col and col in train.columns:
            action_parts.append(-_z(df[col], train[col]))
    out["risk_overconfidence_action"] = np.mean(action_parts, axis=0) if action_parts else np.nan

    classic_parts: list[np.ndarray] = []
    for col in [
        _first_existing(df, "value_std__mean", "value_std"),
        _first_existing(df, "value_range__mean", "value_range"),
        _first_existing(df, "action_first_step_l2_std__mean", "action_first_step_l2_std"),
        _first_existing(df, "future_image_pixel_std_mean__mean", "future_image_pixel_std_mean"),
    ]:
        if col and col in train.columns:
            classic_parts.append(_z(df[col], train[col]))
    out["risk_classic_high_uncertainty"] = np.mean(classic_parts, axis=0) if classic_parts else np.nan
    return out


def _metrics_at_threshold(y: np.ndarray, score: np.ndarray, threshold: float) -> dict[str, float]:
    y = np.asarray(y).astype(bool)
    score = np.asarray(score).astype(float)
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    pred = score >= threshold
    tp = int(np.sum(pred & y))
    tn = int(np.sum(~pred & ~y))
    fp = int(np.sum(pred & ~y))
    fn = int(np.sum(~pred & y))
    tpr = tp / (tp + fn) if tp + fn else np.nan
    tnr = tn / (tn + fp) if tn + fp else np.nan
    return {
        "threshold": float(threshold),
        "accuracy": float((tp + tn) / len(y)) if len(y) else np.nan,
        "balanced_accuracy": float(np.nanmean([tpr, tnr])),
        "tpr": float(tpr),
        "tnr": float(tnr),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def _evaluate_fixed_scores(
    train_scores: pd.DataFrame,
    test_scores: pd.DataFrame,
    y_train: np.ndarray,
    y_test: np.ndarray,
    score_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    pred_rows = []
    for score_col in score_cols:
        train_score = train_scores[score_col].to_numpy(dtype=float)
        test_score = test_scores[score_col].to_numpy(dtype=float)
        threshold = best_threshold_metrics(y_train, train_score)["threshold"]
        train_fixed = _metrics_at_threshold(y_train, train_score, threshold)
        test_fixed = _metrics_at_threshold(y_test, test_score, threshold)
        rows.append(
            {
                "model": score_col,
                "train_auc": auc_for_scores(y_train, train_score),
                "test_auc": auc_for_scores(y_test, test_score),
                **{f"train_{k}": v for k, v in train_fixed.items()},
                **{f"test_{k}": v for k, v in test_fixed.items()},
            }
        )
        pred_rows.append(
            pd.DataFrame(
                {
                    "model": score_col,
                    "score": test_score,
                    "threshold": threshold,
                    "pred_fail": test_score >= threshold,
                    "fail": y_test.astype(bool),
                }
            )
        )
    return pd.DataFrame(rows), pd.concat(pred_rows, ignore_index=True)


def _topk_score(
    train: pd.DataFrame,
    test: pd.DataFrame,
    feature_auc: pd.DataFrame,
    k: int,
) -> tuple[np.ndarray, np.ndarray, str]:
    selected = feature_auc.head(k)
    train_parts: list[np.ndarray] = []
    test_parts: list[np.ndarray] = []
    details = []
    for _, row in selected.iterrows():
        col = row["metric"]
        if col not in train.columns or col not in test.columns:
            continue
        sign = 1.0 if row["best_direction"] == "higher->fail" else -1.0
        train_parts.append(sign * _z(train[col], train[col]))
        test_parts.append(sign * _z(test[col], train[col]))
        details.append(f"{col}:{row['best_direction']}")
    if not train_parts:
        return np.full(len(train), np.nan), np.full(len(test), np.nan), ""
    return np.mean(train_parts, axis=0), np.mean(test_parts, axis=0), "; ".join(details)


def _plot_holdout_scores(predictions: pd.DataFrame, output_path: Path) -> None:
    models = predictions["model"].unique()
    fig, axes = plt.subplots(len(models), 1, figsize=(9, 3.2 * len(models)), squeeze=False)
    for ax, model in zip(axes.ravel(), models):
        sub = predictions[predictions["model"] == model]
        success = sub[~sub["fail"]]["score"]
        fail = sub[sub["fail"]]["score"]
        ax.hist(success, bins=8, alpha=0.65, label="success", color="#2374ab")
        ax.hist(fail, bins=8, alpha=0.65, label="fail", color="#c23b22")
        ax.axvline(float(sub["threshold"].iloc[0]), color="black", linestyle="--", label="train threshold")
        ax.set_title(model)
        ax.grid(alpha=0.2)
        ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-analysis-dir", type=Path, required=True)
    parser.add_argument("--test-analysis-dir", type=Path, required=True)
    parser.add_argument("--max-query", type=int, default=6)
    args = parser.parse_args()

    train_features = pd.read_csv(args.train_analysis_dir / f"episode_online_features_until_query{args.max_query}.csv")
    test_features = pd.read_csv(args.test_analysis_dir / f"episode_online_features_until_query{args.max_query}.csv")
    train_feature_auc = pd.read_csv(args.train_analysis_dir / f"episode_online_feature_auc_until_query{args.max_query}.csv")

    y_train = train_features["fail"].astype(int).to_numpy()
    y_test = test_features["fail"].astype(int).to_numpy()

    train_scores = _risk_scores_with_train_stats(train_features, train_features)
    test_scores = _risk_scores_with_train_stats(train_features, test_features)

    score_cols = [
        "risk_overconfidence_value",
        "risk_overconfidence_action",
        "risk_classic_high_uncertainty",
    ]
    rows, predictions = _evaluate_fixed_scores(train_scores, test_scores, y_train, y_test, score_cols)

    for k in [1, 3, 5, 8]:
        train_score, test_score, details = _topk_score(train_features, test_features, train_feature_auc, k)
        threshold = best_threshold_metrics(y_train, train_score)["threshold"]
        train_fixed = _metrics_at_threshold(y_train, train_score, threshold)
        test_fixed = _metrics_at_threshold(y_test, test_score, threshold)
        model = f"train_top{k}_online_features"
        rows = pd.concat(
            [
                rows,
                pd.DataFrame(
                    [
                        {
                            "model": model,
                            "selected_features": details,
                            "train_auc": auc_for_scores(y_train, train_score),
                            "test_auc": auc_for_scores(y_test, test_score),
                            **{f"train_{key}": val for key, val in train_fixed.items()},
                            **{f"test_{key}": val for key, val in test_fixed.items()},
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        predictions = pd.concat(
            [
                predictions,
                pd.DataFrame(
                    {
                        "model": model,
                        "score": test_score,
                        "threshold": threshold,
                        "pred_fail": test_score >= threshold,
                        "fail": y_test.astype(bool),
                    }
                ),
            ],
            ignore_index=True,
        )

    meta_cols = [col for col in ["rollout_seed", "source_run"] if col in test_features.columns]
    if meta_cols:
        meta = test_features[meta_cols].reset_index(drop=True)
        predictions = predictions.join(pd.concat([meta] * predictions["model"].nunique(), ignore_index=True))

    output_dir = args.test_analysis_dir / "holdout_fail_predictor_eval"
    output_dir.mkdir(parents=True, exist_ok=True)
    rows.to_csv(output_dir / "holdout_predictor_scores.csv", index=False)
    predictions.to_csv(output_dir / "holdout_predictions_by_episode.csv", index=False)
    _plot_holdout_scores(predictions, output_dir / "holdout_score_histograms.png")

    print("Holdout predictor scores:")
    display_cols = [
        "model",
        "train_auc",
        "test_auc",
        "train_balanced_accuracy",
        "test_balanced_accuracy",
        "test_tpr",
        "test_tnr",
        "test_tp",
        "test_tn",
        "test_fp",
        "test_fn",
    ]
    print(rows[display_cols].to_string(index=False))
    print(f"\nWrote {output_dir}")


if __name__ == "__main__":
    main()

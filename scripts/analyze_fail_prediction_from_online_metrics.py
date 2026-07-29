#!/usr/bin/env python3
"""Evaluate simple fail predictors from online Cosmos Policy uncertainty metrics.

The script intentionally separates online metrics (available at query time) from
post-hoc prediction-error metrics that require observing the future.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ONLINE_EXCLUDE_PREFIXES = (
    "prediction_error_",
    "actual_",
    "video_",
)
ONLINE_EXCLUDE_COLUMNS = {
    "suite",
    "task_id",
    "episode_id",
    "pair_id",
    "rollout_id",
    "rollout_seed",
    "init_state_id",
    "base_seed",
    "query_idx",
    "t",
    "t_after",
    "executed_steps",
    "intervention_steps",
    "intervention_start_t",
    "intervention_end_t",
    "intervention_start_query",
    "intervention_end_query",
    "num_samples",
    "num_queries",
    "final_t",
    "final_success",
    "chunk_success",
    "success",
    "fail",
}


def auc_for_scores(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    pos = score[y == 1]
    neg = score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    wins = 0.0
    for p in pos:
        wins += np.sum(p > neg) + 0.5 * np.sum(p == neg)
    return float(wins / (len(pos) * len(neg)))


def best_threshold_metrics(y: np.ndarray, score: np.ndarray) -> dict[str, float]:
    y = np.asarray(y).astype(bool)
    score = np.asarray(score).astype(float)
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    thresholds = np.unique(score)
    best = {
        "threshold": np.nan,
        "accuracy": -np.inf,
        "balanced_accuracy": -np.inf,
        "tpr": np.nan,
        "tnr": np.nan,
    }
    for thr in thresholds:
        pred = score >= thr
        tp = np.sum(pred & y)
        tn = np.sum(~pred & ~y)
        fp = np.sum(pred & ~y)
        fn = np.sum(~pred & y)
        tpr = tp / (tp + fn) if tp + fn else np.nan
        tnr = tn / (tn + fp) if tn + fp else np.nan
        acc = (tp + tn) / len(y)
        bal = np.nanmean([tpr, tnr])
        if bal > best["balanced_accuracy"]:
            best.update(
                threshold=float(thr),
                accuracy=float(acc),
                balanced_accuracy=float(bal),
                tpr=float(tpr),
                tnr=float(tnr),
            )
    return best


def zscore(values: np.ndarray, mean: float | None = None, std: float | None = None) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if mean is None:
        mean = float(np.nanmean(values))
    if std is None:
        std = float(np.nanstd(values))
    if not np.isfinite(std) or std < 1e-12:
        std = 1.0
    return (values - mean) / std


def online_metric_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for col in df.columns:
        if col in ONLINE_EXCLUDE_COLUMNS:
            continue
        if col in {"task_description", "intervention_mode", "video_path"}:
            continue
        if col.startswith(ONLINE_EXCLUDE_PREFIXES):
            continue
        if pd.api.types.is_numeric_dtype(df[col]) and not df[col].isna().all():
            cols.append(col)
    return cols


def oriented_auc_table(df: pd.DataFrame, metrics: list[str], y_col: str = "fail") -> pd.DataFrame:
    rows = []
    y = df[y_col].astype(int).to_numpy()
    for metric in metrics:
        vals = df[metric].to_numpy(dtype=float)
        auc_high = auc_for_scores(y, vals)
        auc_low = auc_for_scores(y, -vals)
        direction = "higher->fail" if auc_high >= auc_low else "lower->fail"
        score = vals if auc_high >= auc_low else -vals
        threshold = best_threshold_metrics(y, score)
        rows.append(
            {
                "metric": metric,
                "auc_higher_is_fail": auc_high,
                "auc_lower_is_fail": auc_low,
                "best_auc": max(auc_high, auc_low),
                "best_direction": direction,
                "fail_mean": float(df[df[y_col]][metric].mean()),
                "success_mean": float(df[~df[y_col]][metric].mean()),
                **{f"best_{k}": v for k, v in threshold.items()},
            }
        )
    return pd.DataFrame(rows).sort_values("best_auc", ascending=False)


def make_query_auc_table(query_df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []
    for q, sub in query_df.groupby("query_idx"):
        table = oriented_auc_table(sub, metrics)
        table.insert(0, "query_idx", q)
        rows.append(table)
    return pd.concat(rows, ignore_index=True)


def episode_features_up_to_query(query_df: pd.DataFrame, metrics: list[str], max_query: int) -> pd.DataFrame:
    sub = query_df[query_df["query_idx"] <= max_query].copy()
    keys = ["rollout_seed", "source_run"] if "source_run" in sub.columns else ["rollout_seed"]
    records = []
    for key, group in sub.groupby(keys, dropna=False):
        record = {}
        if isinstance(key, tuple):
            for k, v in zip(keys, key):
                record[k] = v
        else:
            record[keys[0]] = key
        record["fail"] = not bool(group["success"].iloc[-1])
        record["success"] = bool(group["success"].iloc[-1])
        record["max_query"] = max_query
        for metric in metrics:
            values = group[metric].dropna()
            if len(values) == 0:
                continue
            record[f"{metric}__last"] = float(values.iloc[-1])
            record[f"{metric}__mean"] = float(values.mean())
            record[f"{metric}__max"] = float(values.max())
            record[f"{metric}__min"] = float(values.min())
        records.append(record)
    return pd.DataFrame(records)


def loo_topk_oriented_score(features: pd.DataFrame, feature_cols: list[str], k: int = 5) -> pd.DataFrame:
    """Leave-one-episode-out score using top-k univariate train AUC features."""
    preds = []
    y_all = features["fail"].astype(int).to_numpy()
    for idx in range(len(features)):
        train = features.drop(features.index[idx]).reset_index(drop=True)
        test = features.iloc[[idx]].copy()
        train_table = oriented_auc_table(train[["fail"] + feature_cols], feature_cols)
        selected = train_table.head(k)
        score = 0.0
        details = []
        for _, row in selected.iterrows():
            col = row["metric"]
            train_vals = train[col].to_numpy(dtype=float)
            val = float(test[col].iloc[0])
            mean = float(np.nanmean(train_vals))
            std = float(np.nanstd(train_vals))
            z = float(zscore(np.array([val]), mean, std)[0])
            sign = 1.0 if row["best_direction"] == "higher->fail" else -1.0
            score += sign * z
            details.append(f"{col}:{row['best_direction']}")
        preds.append(
            {
                "row_idx": int(idx),
                "rollout_seed": int(test["rollout_seed"].iloc[0]),
                "fail": bool(test["fail"].iloc[0]),
                "score": float(score / max(len(selected), 1)),
                "selected_features": "; ".join(details),
            }
        )
    pred_df = pd.DataFrame(preds)
    pred_df["loo_auc"] = auc_for_scores(y_all, pred_df["score"].to_numpy())
    pred_df["k"] = k
    return pred_df


def add_handcrafted_scores(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    def first_existing(*names: str) -> str | None:
        for name in names:
            if name in result.columns:
                return name
        return None

    base_cols = [
        first_existing("value_mean__mean", "value_mean"),
        first_existing("value_std__mean", "value_std"),
        first_existing("value_range__mean", "value_range"),
        first_existing("action_first_step_l2_std__mean", "action_first_step_l2_std"),
        first_existing(
            "latent_value_element_std_mean_mean_over_samples__mean",
            "latent_value_element_std_mean_mean_over_samples",
        ),
        first_existing(
            "latent_action_first_step_copy_l2_std_mean_over_samples__mean",
            "latent_action_first_step_copy_l2_std_mean_over_samples",
        ),
        first_existing("future_image_pixel_std_mean__mean", "future_image_pixel_std_mean"),
        first_existing("future_wrist_pixel_std_mean__mean", "future_wrist_pixel_std_mean"),
    ]
    for col in [c for c in base_cols if c is not None]:
        result[f"z_{col}"] = zscore(result[col].to_numpy(dtype=float))

    # On this dataset fail tends to be overconfident: lower value uncertainty is risky.
    parts = []
    for raw_col in [
        first_existing("value_std__mean", "value_std"),
        first_existing("value_range__mean", "value_range"),
        first_existing(
            "latent_value_element_std_mean_mean_over_samples__mean",
            "latent_value_element_std_mean_mean_over_samples",
        ),
    ]:
        z_col = f"z_{raw_col}" if raw_col else None
        if z_col in result:
            parts.append(-result[z_col])
    raw_value_mean = first_existing("value_mean__mean", "value_mean")
    z_value_mean = f"z_{raw_value_mean}" if raw_value_mean else None
    if z_value_mean in result:
        parts.append(-0.5 * result[z_value_mean])
    result["risk_overconfidence_value"] = np.mean(parts, axis=0) if parts else np.nan

    parts = []
    for raw_col in [
        first_existing("action_first_step_l2_std__mean", "action_first_step_l2_std"),
        first_existing(
            "latent_action_first_step_copy_l2_std_mean_over_samples__mean",
            "latent_action_first_step_copy_l2_std_mean_over_samples",
        ),
    ]:
        z_col = f"z_{raw_col}" if raw_col else None
        if z_col in result:
            parts.append(-result[z_col])
    result["risk_overconfidence_action"] = np.mean(parts, axis=0) if parts else np.nan

    classic_parts = []
    for raw_col in [
        first_existing("value_std__mean", "value_std"),
        first_existing("value_range__mean", "value_range"),
        first_existing("action_first_step_l2_std__mean", "action_first_step_l2_std"),
        first_existing("future_image_pixel_std_mean__mean", "future_image_pixel_std_mean"),
    ]:
        z_col = f"z_{raw_col}" if raw_col else None
        if z_col in result:
            classic_parts.append(result[z_col])
    result["risk_classic_high_uncertainty"] = np.mean(classic_parts, axis=0) if classic_parts else np.nan
    return result


def plot_query_auc(query_auc: pd.DataFrame, output_path: Path, metrics: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    for metric in metrics:
        sub = query_auc[query_auc["metric"] == metric].sort_values("query_idx")
        if sub.empty:
            continue
        ax.plot(sub["query_idx"], sub["best_auc"], marker="o", label=metric)
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1)
    ax.set_xlabel("query_idx")
    ax.set_ylabel("best AUC for fail prediction")
    ax.set_title("How early online metrics separate fail from success")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_score_hist(score_df: pd.DataFrame, score_col: str, output_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fail = score_df[score_df["fail"]][score_col].dropna()
    success = score_df[~score_df["fail"]][score_col].dropna()
    ax.hist(success, bins=12, alpha=0.65, label="success", color="#2374ab")
    ax.hist(fail, bins=12, alpha=0.65, label="fail", color="#c23b22")
    auc = auc_for_scores(score_df["fail"].astype(int).to_numpy(), score_df[score_col].to_numpy())
    ax.set_title(f"{title} (AUC={auc:.3f})")
    ax.set_xlabel(score_col)
    ax.set_ylabel("episodes")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--max-query", type=int, default=6)
    args = parser.parse_args()

    analysis_dir = args.analysis_dir
    query_path = analysis_dir / "selected_query_metrics_truncated_to_success.csv"
    query_df = pd.read_csv(query_path)
    query_df["fail"] = ~query_df["success"].astype(bool)
    metrics = online_metric_columns(query_df)

    query_auc = make_query_auc_table(query_df, metrics)
    query_auc.to_csv(analysis_dir / "online_metric_auc_by_query.csv", index=False)

    top_metrics = (
        query_auc.groupby("metric")["best_auc"].max().sort_values(ascending=False).head(10).index.tolist()
    )
    plot_query_auc(query_auc, analysis_dir / "online_metric_auc_by_query.png", top_metrics)

    ep_features = episode_features_up_to_query(query_df, metrics, args.max_query)
    ep_features = add_handcrafted_scores(ep_features)
    ep_features.to_csv(analysis_dir / f"episode_online_features_until_query{args.max_query}.csv", index=False)

    feature_cols = [
        col
        for col in ep_features.columns
        if col not in {"source_run", "rollout_seed", "fail", "success", "max_query"}
        and not col.startswith("z_")
        and not col.startswith("risk_")
        and pd.api.types.is_numeric_dtype(ep_features[col])
        and not ep_features[col].isna().all()
    ]
    feature_auc = oriented_auc_table(ep_features[["fail"] + feature_cols], feature_cols)
    feature_auc.to_csv(analysis_dir / f"episode_online_feature_auc_until_query{args.max_query}.csv", index=False)

    loo_rows = []
    for k in [1, 3, 5, 8]:
        loo_rows.append(loo_topk_oriented_score(ep_features, feature_cols, k=k))
    loo = pd.concat(loo_rows, ignore_index=True)
    loo.to_csv(analysis_dir / f"loo_topk_online_fail_predictor_until_query{args.max_query}.csv", index=False)

    score_rows = []
    for score_col in [
        "risk_overconfidence_value",
        "risk_overconfidence_action",
        "risk_classic_high_uncertainty",
    ]:
        if score_col in ep_features.columns:
            y = ep_features["fail"].astype(int).to_numpy()
            score = ep_features[score_col].to_numpy()
            row = {"score": score_col, "auc": auc_for_scores(y, score)}
            row.update(best_threshold_metrics(y, score))
            score_rows.append(row)
            plot_score_hist(
                ep_features,
                score_col,
                analysis_dir / f"{score_col}_hist.png",
                score_col.replace("_", " "),
            )
    handcrafted = pd.DataFrame(score_rows).sort_values("auc", ascending=False)
    handcrafted.to_csv(analysis_dir / f"handcrafted_risk_scores_until_query{args.max_query}.csv", index=False)

    readme = analysis_dir / "fail_prediction_notes.md"
    readme.write_text(
        "\n".join(
            [
                "# Fail prediction from online metrics",
                "",
                f"Common online horizon: queries `0..{args.max_query}`.",
                "",
                "Generated files:",
                "- `online_metric_auc_by_query.csv` / `.png`",
                f"- `episode_online_features_until_query{args.max_query}.csv`",
                f"- `episode_online_feature_auc_until_query{args.max_query}.csv`",
                f"- `loo_topk_online_fail_predictor_until_query{args.max_query}.csv`",
                f"- `handcrafted_risk_scores_until_query{args.max_query}.csv`",
                "- `risk_overconfidence_value_hist.png`",
                "- `risk_overconfidence_action_hist.png`",
                "- `risk_classic_high_uncertainty_hist.png`",
                "",
                "Notes:",
                "- Online metrics exclude `prediction_error_*`, `actual_*`, `video_*`, `final_t`, and other leakage.",
                "- `prediction_error_*` is useful for analysis/training a proxy, but not directly available before executing a chunk.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print("Top query-level online metrics:")
    print(query_auc.sort_values("best_auc", ascending=False).head(20).to_string(index=False))
    print("\nTop episode online features:")
    print(feature_auc.head(20).to_string(index=False))
    print("\nHandcrafted scores:")
    print(handcrafted.to_string(index=False))
    print("\nLOO top-k summary:")
    print(loo.groupby("k")["loo_auc"].first().reset_index().to_string(index=False))


if __name__ == "__main__":
    main()

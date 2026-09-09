#!/usr/bin/env python3
"""Evaluate P4 ensemble uncertainty, conformal routing, and an offline hard filter."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

try:
    from scripts.residual_dynamics_ensemble import (
        ResidualPreprocessor,
        conformal_threshold,
        mixture_nll,
        predict_independent_heads,
        uncertainty_scores,
    )
except ModuleNotFoundError:
    from residual_dynamics_ensemble import (
        ResidualPreprocessor,
        conformal_threshold,
        mixture_nll,
        predict_independent_heads,
        uncertainty_scores,
    )


ENSEMBLE_SCORES = (
    "ensemble_jrd",
    "ensemble_epistemic_mean",
    "ensemble_epistemic_max",
    "ensemble_aleatoric_mean",
    "ensemble_aleatoric_max",
    "ensemble_total_mean",
)
BASELINE_SCORES = (
    "value_std",
    "value_range",
    "action_std_mean",
    "action_first_step_l2_std",
    "action_pairwise_l2_mean",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_across_seed_std_mean",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
)


def roc_auc(labels: Sequence[bool], scores: Sequence[float]) -> float:
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=np.float64)
    finite = np.isfinite(scores)
    labels, scores = labels[finite], scores[finite]
    positive = int(labels.sum())
    negative = int((~labels).sum())
    if not positive or not negative:
        return float("nan")
    ranks = pd.Series(scores).rank(method="average").to_numpy()
    return float(
        (ranks[labels].sum() - positive * (positive + 1) / 2) / (positive * negative)
    )


def average_precision(labels: Sequence[bool], scores: Sequence[float]) -> float:
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=np.float64)
    finite = np.isfinite(scores)
    labels, scores = labels[finite], scores[finite]
    positives = int(labels.sum())
    if not positives:
        return float("nan")
    order = np.argsort(-scores, kind="stable")
    sorted_labels = labels[order]
    precision = np.cumsum(sorted_labels) / np.arange(1, len(sorted_labels) + 1)
    return float(precision[sorted_labels].sum() / positives)


def balanced_average_precision(
    labels: Sequence[bool], scores: Sequence[float]
) -> float:
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=np.float64)
    finite = np.isfinite(scores)
    labels, scores = labels[finite], scores[finite]
    positive = int(labels.sum())
    negative = int((~labels).sum())
    if not positive or not negative:
        return float("nan")
    weights = np.where(labels, 0.5 / positive, 0.5 / negative)
    order = np.argsort(-scores, kind="stable")
    sorted_labels = labels[order]
    sorted_weights = weights[order]
    true_positive = np.cumsum(sorted_weights * sorted_labels)
    total = np.cumsum(sorted_weights)
    precision = true_positive / np.clip(total, 1e-12, None)
    return float((precision[sorted_labels] * sorted_weights[sorted_labels]).sum() / 0.5)


def _bootstrap_interval(
    negative: np.ndarray,
    positive: np.ndarray,
    metric,
    *,
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        sampled_negative = rng.choice(negative, size=len(negative), replace=True)
        sampled_positive = rng.choice(positive, size=len(positive), replace=True)
        scores = np.concatenate([sampled_negative, sampled_positive])
        labels = np.concatenate(
            [
                np.zeros(len(sampled_negative), dtype=bool),
                np.ones(len(sampled_positive), dtype=bool),
            ]
        )
        estimates.append(metric(labels, scores))
    return tuple(np.quantile(estimates, [0.025, 0.975]).astype(float))


def score_candidates(
    manifest: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    artifact_dir: Path,
    *,
    device: str,
    batch_size: int,
) -> pd.DataFrame:
    preprocessor = ResidualPreprocessor.load(artifact_dir / "preprocessing.npz")
    indices = np.arange(len(manifest), dtype=np.int64)
    inputs = preprocessor.transform_input(arrays, indices)
    targets = preprocessor.transform_target(arrays, indices)
    means, variances = predict_independent_heads(
        inputs, artifact_dir, device=device, batch_size=batch_size
    )
    result = manifest.copy()
    for name, values in uncertainty_scores(means, variances).items():
        result[name] = values
    result["ensemble_mixture_nll"] = mixture_nll(means, variances, targets)
    result["ensemble_mean_residual_error"] = np.sqrt(
        np.mean(np.square(means.mean(axis=0) - targets), axis=1)
    )
    result["target_standardized_residual_rms"] = np.sqrt(
        np.mean(np.square(targets), axis=1)
    )
    result["cosmos_visual_residual_rms"] = np.sqrt(
        np.mean(np.square(arrays["actual_visual"] - arrays["predicted_visual"]), axis=1)
    )
    result["cosmos_proprio_residual_l2"] = np.linalg.norm(
        arrays["actual_proprio"] - arrays["predicted_proprio"], axis=1
    )
    return result


def trajectory_scores(
    candidates: pd.DataFrame, score_columns: Iterable[str]
) -> pd.DataFrame:
    columns = [column for column in score_columns if column in candidates]
    identity = ["group_id", "split", "factor", "suite", "task_id"]
    aggregations = {column: "max" for column in columns}
    aggregations.update(
        {
            "cosmos_visual_residual_rms": "max",
            "cosmos_proprio_residual_l2": "max",
            "target_standardized_residual_rms": "max",
            "ensemble_mean_residual_error": "max",
        }
    )
    return candidates.groupby(identity, as_index=False, dropna=False).agg(aggregations)


def detection_table(
    groups: pd.DataFrame,
    score_columns: Sequence[str],
    *,
    bootstrap_repetitions: int,
    seed: int,
) -> pd.DataFrame:
    id_test = groups.loc[groups["split"].eq("id_test")]
    records = []
    factors = sorted(groups.loc[groups["split"].eq("ood_test"), "factor"].unique())
    for metric_index, metric in enumerate(score_columns):
        if metric not in groups:
            continue
        negative = id_test[metric].to_numpy(dtype=float)
        for factor_index, factor in enumerate([*factors, "All OOD"]):
            positive_rows = groups.loc[groups["split"].eq("ood_test")]
            if factor != "All OOD":
                positive_rows = positive_rows.loc[positive_rows["factor"].eq(factor)]
            positive = positive_rows[metric].to_numpy(dtype=float)
            finite_negative = negative[np.isfinite(negative)]
            finite_positive = positive[np.isfinite(positive)]
            if not len(finite_negative) or not len(finite_positive):
                continue
            scores = np.concatenate([finite_negative, finite_positive])
            labels = np.concatenate(
                [
                    np.zeros(len(finite_negative), dtype=bool),
                    np.ones(len(finite_positive), dtype=bool),
                ]
            )
            auc = roc_auc(labels, scores)
            ap = average_precision(labels, scores)
            balanced_ap = balanced_average_precision(labels, scores)
            auc_low, auc_high = _bootstrap_interval(
                finite_negative,
                finite_positive,
                roc_auc,
                repetitions=bootstrap_repetitions,
                seed=seed + metric_index * 101 + factor_index,
            )
            ap_low, ap_high = _bootstrap_interval(
                finite_negative,
                finite_positive,
                average_precision,
                repetitions=bootstrap_repetitions,
                seed=seed + 10000 + metric_index * 101 + factor_index,
            )
            balanced_ap_low, balanced_ap_high = _bootstrap_interval(
                finite_negative,
                finite_positive,
                balanced_average_precision,
                repetitions=bootstrap_repetitions,
                seed=seed + 20000 + metric_index * 101 + factor_index,
            )
            records.append(
                {
                    "metric": metric,
                    "factor": factor,
                    "roc_auc": auc,
                    "roc_auc_ci_low": auc_low,
                    "roc_auc_ci_high": auc_high,
                    "average_precision": ap,
                    "average_precision_ci_low": ap_low,
                    "average_precision_ci_high": ap_high,
                    "balanced_average_precision": balanced_ap,
                    "balanced_average_precision_ci_low": balanced_ap_low,
                    "balanced_average_precision_ci_high": balanced_ap_high,
                    "id_groups": len(finite_negative),
                    "ood_groups": len(finite_positive),
                }
            )
    return pd.DataFrame(records)


def correlation_table(
    candidates: pd.DataFrame, score_columns: Sequence[str]
) -> pd.DataFrame:
    heldout = candidates.loc[candidates["split"].isin(["id_test", "ood_test"])]
    targets = (
        "target_standardized_residual_rms",
        "cosmos_visual_residual_rms",
        "cosmos_proprio_residual_l2",
        "ensemble_mean_residual_error",
    )
    records = []
    for metric in score_columns:
        if metric not in heldout:
            continue
        for target in targets:
            pair = heldout[[metric, target]].replace([np.inf, -np.inf], np.nan).dropna()
            rho = (
                float(pair[metric].rank().corr(pair[target].rank()))
                if len(pair) > 2
                else np.nan
            )
            records.append(
                {
                    "metric": metric,
                    "target": target,
                    "spearman_rho": rho,
                    "rows": len(pair),
                }
            )
    return pd.DataFrame(records)


def failure_detection_table(
    candidates: pd.DataFrame, score_columns: Sequence[str]
) -> pd.DataFrame:
    if "terminal_available" not in candidates or "terminal_success" not in candidates:
        return pd.DataFrame()
    terminal = candidates.loc[
        candidates["split"].eq("ood_test")
        & candidates["terminal_available"].fillna(False).astype(bool)
    ].copy()
    terminal["failure"] = ~terminal["terminal_success"].fillna(False).astype(bool)
    records = []
    for metric in score_columns:
        if metric not in terminal:
            continue
        for factor, rows in terminal.groupby("factor"):
            labels = rows["failure"].to_numpy(dtype=bool)
            if labels.min() == labels.max():
                continue
            records.append(
                {
                    "metric": metric,
                    "factor": factor,
                    "roc_auc": roc_auc(labels, rows[metric]),
                    "average_precision": average_precision(labels, rows[metric]),
                    "rows": len(rows),
                    "failures": int(labels.sum()),
                }
            )
    return pd.DataFrame(records)


def offline_hard_filter(candidates: pd.DataFrame, threshold: float) -> pd.DataFrame:
    records = []
    required = {"candidate_value", "local_utility_v1", "local_success"}
    if not required.issubset(candidates):
        return pd.DataFrame()
    for snapshot, rows in candidates.loc[candidates["split"].eq("ood_test")].groupby(
        "snapshot_group", sort=False
    ):
        rows = rows.loc[
            np.isfinite(pd.to_numeric(rows["candidate_value"], errors="coerce"))
        ]
        if rows.empty:
            continue
        baseline = rows.loc[rows["candidate_value"].astype(float).idxmax()]
        feasible = rows.loc[rows["ensemble_jrd"].astype(float).le(threshold)]
        all_rejected = feasible.empty
        selected = (
            baseline
            if all_rejected
            else feasible.loc[feasible["candidate_value"].astype(float).idxmax()]
        )
        oracle = rows.loc[rows["local_utility_v1"].astype(float).idxmax()]
        records.append(
            {
                "snapshot_group": snapshot,
                "factor": str(rows.iloc[0]["factor"]),
                "group_id": str(rows.iloc[0]["group_id"]),
                "all_rejected": all_rejected,
                "selection_changed": int(selected["candidate_idx"])
                != int(baseline["candidate_idx"]),
                "baseline_candidate_idx": int(baseline["candidate_idx"]),
                "filtered_candidate_idx": int(selected["candidate_idx"]),
                "baseline_value": float(baseline["candidate_value"]),
                "filtered_value": float(selected["candidate_value"]),
                "baseline_jrd": float(baseline["ensemble_jrd"]),
                "filtered_jrd": float(selected["ensemble_jrd"]),
                "baseline_local_utility": float(baseline["local_utility_v1"]),
                "filtered_local_utility": float(selected["local_utility_v1"]),
                "oracle_local_utility": float(oracle["local_utility_v1"]),
                "baseline_local_success": bool(baseline["local_success"]),
                "filtered_local_success": bool(selected["local_success"]),
            }
        )
    return pd.DataFrame(records)


def _write_plots(
    output_dir: Path,
    groups: pd.DataFrame,
    detection: pd.DataFrame,
    candidates: pd.DataFrame,
    hard_filter: pd.DataFrame,
) -> None:
    primary = detection.loc[
        detection["scope"].eq("matched_query")
        & detection["factor"].eq("All OOD")
        & detection["metric"].isin([*ENSEMBLE_SCORES, *BASELINE_SCORES])
    ].sort_values("balanced_average_precision", ascending=False)
    fig, axis = plt.subplots(figsize=(11, 5))
    axis.barh(primary["metric"], primary["balanced_average_precision"], color="#2f6f6d")
    axis.invert_yaxis()
    axis.set(xlabel="Class-balanced AP: ID test vs all LIBERO-PRO", xlim=(0, 1))
    fig.tight_layout()
    fig.savefig(output_dir / "ood_detection_average_precision.png", dpi=180)
    plt.close(fig)

    factors = ["ID", "Environment", "Object", "Position"]
    values = [
        groups.loc[groups["factor"].eq(factor), "ensemble_jrd"].dropna()
        for factor in factors
    ]
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.boxplot(values, tick_labels=factors, showfliers=False)
    axis.set(ylabel="Trajectory-max Jensen-Renyi divergence")
    fig.tight_layout()
    fig.savefig(output_dir / "jrd_group_distributions.png", dpi=180)
    plt.close(fig)

    heldout = candidates.loc[candidates["split"].isin(["id_test", "ood_test"])]
    fig, axis = plt.subplots(figsize=(7, 5))
    for factor, rows in heldout.groupby("factor"):
        axis.scatter(
            rows["ensemble_jrd"],
            rows["target_standardized_residual_rms"],
            s=10,
            alpha=0.35,
            label=factor,
        )
    axis.set(xlabel="JRD", ylabel="Realized standardized Cosmos residual RMS")
    axis.legend(frameon=False, ncols=2)
    fig.tight_layout()
    fig.savefig(output_dir / "jrd_vs_realized_residual.png", dpi=180)
    plt.close(fig)

    if not hard_filter.empty:
        summary = hard_filter.groupby("factor")[
            ["baseline_local_utility", "filtered_local_utility"]
        ].mean()
        axis = summary.plot(kind="bar", figsize=(8, 5), color=["#7c8797", "#c9503d"])
        axis.set(ylabel="Mean local utility", xlabel="")
        axis.tick_params(axis="x", rotation=0)
        axis.get_figure().tight_layout()
        axis.get_figure().savefig(
            output_dir / "offline_hard_filter_utility.png", dpi=180
        )
        plt.close(axis.get_figure())


def analyze(args: argparse.Namespace) -> dict[str, object]:
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_parquet(args.manifest.expanduser().resolve())
    with np.load(args.features.expanduser().resolve(), allow_pickle=False) as payload:
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    candidates = score_candidates(
        manifest,
        arrays,
        args.artifact_dir.expanduser().resolve(),
        device=args.device,
        batch_size=args.batch_size,
    )
    available_scores = [
        score for score in [*ENSEMBLE_SCORES, *BASELINE_SCORES] if score in candidates
    ]
    all_groups = trajectory_scores(candidates, available_scores)
    if "query_idx" in candidates:
        id_query_support = sorted(
            candidates.loc[candidates["factor"].eq("ID"), "query_idx"]
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )
        matched_candidates = candidates.loc[
            candidates["factor"].eq("ID")
            | candidates["query_idx"].fillna(-1).astype(int).isin(id_query_support)
        ].copy()
    else:
        id_query_support = []
        matched_candidates = candidates.copy()
    groups = trajectory_scores(matched_candidates, available_scores)
    calibration = groups.loc[groups["split"].eq("calibration"), "ensemble_jrd"]
    threshold, conformal_level = conformal_threshold(calibration, args.alpha)
    id_test = groups.loc[groups["split"].eq("id_test")]
    id_fpr = float(id_test["ensemble_jrd"].gt(threshold).mean())
    conformal_records = []
    for scope, scoped_groups in (
        ("matched_query", groups),
        ("all_queries", all_groups),
    ):
        scoped_id = scoped_groups.loc[scoped_groups["split"].eq("id_test")]
        conformal_records.append(
            {
                "scope": scope,
                "factor": "ID test",
                "groups": len(scoped_id),
                "threshold": threshold,
                "alarm_rate": float(scoped_id["ensemble_jrd"].gt(threshold).mean()),
            }
        )
        for factor, rows in scoped_groups.loc[
            scoped_groups["split"].eq("ood_test")
        ].groupby("factor"):
            conformal_records.append(
                {
                    "scope": scope,
                    "factor": factor,
                    "groups": len(rows),
                    "threshold": threshold,
                    "alarm_rate": float(rows["ensemble_jrd"].gt(threshold).mean()),
                }
            )
    conformal = pd.DataFrame(conformal_records)
    matched_detection = detection_table(
        groups,
        available_scores,
        bootstrap_repetitions=args.bootstrap_repetitions,
        seed=args.seed,
    )
    matched_detection.insert(0, "scope", "matched_query")
    all_detection = detection_table(
        all_groups,
        available_scores,
        bootstrap_repetitions=args.bootstrap_repetitions,
        seed=args.seed + 50000,
    )
    all_detection.insert(0, "scope", "all_queries")
    detection = pd.concat([matched_detection, all_detection], ignore_index=True)
    correlation_frames = []
    for scope, candidate_rows, group_rows in (
        ("matched_query", matched_candidates, groups),
        ("all_queries", candidates, all_groups),
    ):
        for unit, rows in (("candidate", candidate_rows), ("trajectory", group_rows)):
            frame = correlation_table(rows, available_scores)
            frame.insert(0, "unit", unit)
            frame.insert(0, "scope", scope)
            correlation_frames.append(frame)
    correlations = pd.concat(correlation_frames, ignore_index=True)
    matched_failures = failure_detection_table(matched_candidates, available_scores)
    matched_failures.insert(0, "scope", "matched_query")
    all_failures = failure_detection_table(candidates, available_scores)
    all_failures.insert(0, "scope", "all_queries")
    failures = pd.concat([matched_failures, all_failures], ignore_index=True)
    hard_filter = offline_hard_filter(matched_candidates, threshold)
    all_hard_filter = offline_hard_filter(candidates, threshold)

    candidates.to_parquet(output_dir / "candidate_scores.parquet", index=False)
    groups.to_csv(output_dir / "trajectory_scores.csv", index=False)
    all_groups.to_csv(output_dir / "trajectory_scores_all_queries.csv", index=False)
    detection.to_csv(output_dir / "ood_detection_metrics.csv", index=False)
    correlations.to_csv(output_dir / "prediction_error_correlations.csv", index=False)
    failures.to_csv(output_dir / "terminal_failure_detection.csv", index=False)
    conformal.to_csv(output_dir / "conformal_alarm_rates.csv", index=False)
    hard_filter.to_csv(output_dir / "offline_hard_filter.csv", index=False)
    all_hard_filter.to_csv(
        output_dir / "offline_hard_filter_all_queries.csv", index=False
    )

    all_ood = detection.loc[
        detection["scope"].eq("matched_query") & detection["factor"].eq("All OOD")
    ]
    jrd_ap = float(
        all_ood.loc[
            all_ood["metric"].eq("ensemble_jrd"), "balanced_average_precision"
        ].iloc[0]
    )
    baseline = all_ood.loc[all_ood["metric"].isin(BASELINE_SCORES)]
    best_baseline_ap = float(baseline["balanced_average_precision"].max())
    best_baseline_metric = str(
        baseline.loc[baseline["balanced_average_precision"].idxmax(), "metric"]
    )
    jrd_rho_rows = correlations.loc[
        correlations["scope"].eq("matched_query")
        & correlations["unit"].eq("trajectory")
        & correlations["metric"].eq("ensemble_jrd")
        & correlations["target"].eq("target_standardized_residual_rms")
    ]
    jrd_error_rho = float(jrd_rho_rows["spearman_rho"].iloc[0])
    gate_components = {
        "id_fpr_pass": id_fpr <= args.max_id_fpr,
        "ood_ap_pass": jrd_ap
        >= max(args.min_jrd_ap, best_baseline_ap + args.min_ap_gain),
        "prediction_error_rho_pass": jrd_error_rho >= args.min_error_rho,
    }
    gate_pass = all(gate_components.values())
    filter_summary = {}
    if not hard_filter.empty:
        filter_summary = {
            "snapshots": len(hard_filter),
            "selection_change_rate": float(hard_filter["selection_changed"].mean()),
            "all_rejected_rate": float(hard_filter["all_rejected"].mean()),
            "mean_local_utility_delta": float(
                (
                    hard_filter["filtered_local_utility"]
                    - hard_filter["baseline_local_utility"]
                ).mean()
            ),
            "local_success_delta": float(
                hard_filter["filtered_local_success"].mean()
                - hard_filter["baseline_local_success"].mean()
            ),
        }
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "complete": True,
        "rows": len(candidates),
        "trajectory_groups_matched_query": len(groups),
        "trajectory_groups_all_queries": len(all_groups),
        "id_query_support": id_query_support,
        "matched_query_ood_rows": int(
            matched_candidates["split"].astype(str).eq("ood_test").sum()
        ),
        "split_rows": candidates["split"].value_counts().sort_index().to_dict(),
        "factor_rows": candidates["factor"].value_counts().sort_index().to_dict(),
        "alpha": args.alpha,
        "conformal_level": conformal_level,
        "calibration_groups": len(calibration),
        "global_jrd_threshold": threshold,
        "id_test_fpr": id_fpr,
        "jrd_all_ood_balanced_average_precision": jrd_ap,
        "best_baseline_all_ood_balanced_average_precision": best_baseline_ap,
        "best_baseline_metric": best_baseline_metric,
        "jrd_trajectory_prediction_error_spearman": jrd_error_rho,
        "gate_components": gate_components,
        "offline_gate_pass": gate_pass,
        "offline_hard_filter": filter_summary,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    _write_plots(output_dir, groups, detection, candidates, hard_filter)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--features", type=Path, required=True)
    result.add_argument("--artifact-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--device", default="cuda")
    result.add_argument("--batch-size", type=int, default=512)
    result.add_argument("--alpha", type=float, default=0.1)
    result.add_argument("--max-id-fpr", type=float, default=0.15)
    result.add_argument("--min-jrd-ap", type=float, default=0.65)
    result.add_argument("--min-ap-gain", type=float, default=0.03)
    result.add_argument("--min-error-rho", type=float, default=0.2)
    result.add_argument("--bootstrap-repetitions", type=int, default=1000)
    result.add_argument("--seed", type=int, default=20260906)
    return result


def main() -> int:
    summary = analyze(parser().parse_args())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

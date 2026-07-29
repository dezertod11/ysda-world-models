#!/usr/bin/env python3
"""Analyze the long LIBERO uncertainty/planning campaign without test leakage."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EPISODE_KEYS = [
    "source_run",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_seed",
]
CONFIG_COLUMNS = [
    "case_id",
    "experiment_split",
    "planning_strategy",
    "planning_risk_lambda",
    "planning_action_weight",
    "prediction_mode",
    "num_samples",
    "num_open_loop_steps",
    "num_denoising_steps_action",
    "num_denoising_steps_future_state",
    "num_denoising_steps_value",
    "num_future_state_samples",
    "num_value_samples",
]
ONLINE_METRIC_CANDIDATES = [
    "action_std_mean",
    "action_std_max",
    "action_first_step_l2_std",
    "action_xyz_std_mean",
    "action_rot_std_mean",
    "action_gripper_std_mean",
    "action_pairwise_l2_mean",
    "value_mean",
    "value_std",
    "value_range",
    "future_proprio_std_mean",
    "future_proprio_std_max",
    "future_image_pixel_std_mean",
    "future_image_pixel_std_p95",
    "future_wrist_pixel_std_mean",
    "future_wrist_pixel_std_p95",
    "latent_action_across_seed_std_mean",
    "latent_action_across_seed_std_p95",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_value_std",
    "candidate_value_range",
    "candidate_action_internal_consistency_mean",
    "candidate_action_internal_consistency_std",
    "candidate_action_chunk_consistency_mean",
    "candidate_action_chunk_consistency_std",
    "candidate_value_internal_consistency_mean",
    "candidate_value_internal_consistency_std",
]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def load_campaign_traces(campaign_dir: Path) -> pd.DataFrame:
    run_dir = campaign_dir / "runs"
    paths = sorted(run_dir.glob("*__query_traces.parquet"))
    if not paths:
        paths = sorted(run_dir.glob("*__query_traces.csv"))
    frames = []
    for path in paths:
        frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["source_run"] = path.name.split("__query_traces", 1)[0]
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No query traces found under {run_dir}")
    traces = pd.concat(frames, ignore_index=True, sort=False)
    traces["success"] = parse_bool(traces["success"])
    traces["fail"] = ~traces["success"]
    for column, default in [
        ("case_id", ""),
        ("experiment_split", "unspecified"),
        ("planning_strategy", "first"),
        ("planning_risk_lambda", 0.0),
        ("planning_action_weight", 0.5),
        ("prediction_mode", "parallel"),
    ]:
        if column not in traces:
            traces[column] = default
    return traces


def first_per_episode(traces: pd.DataFrame) -> pd.DataFrame:
    ordered = traces.sort_values(EPISODE_KEYS + ["query_idx"])
    first = ordered.groupby(EPISODE_KEYS, dropna=False).first().reset_index()
    first["fail"] = ~parse_bool(first["success"])
    return first


def auc_score(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"y": np.asarray(labels, dtype=bool), "s": scores}).dropna()
    positives = int(frame["y"].sum())
    negatives = len(frame) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = frame["s"].rank(method="average")
    rank_sum = float(ranks[frame["y"]].sum())
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"y": np.asarray(labels, dtype=bool), "s": scores}).dropna()
    positives = int(frame["y"].sum())
    if positives == 0:
        return float("nan")
    frame = frame.sort_values("s", ascending=False)
    tp = frame["y"].astype(int).cumsum()
    precision = tp / np.arange(1, len(frame) + 1)
    return float(precision[frame["y"]].sum() / positives)


def classification_metrics(labels: Sequence[bool], predicted: Sequence[bool]) -> dict[str, float]:
    y = np.asarray(labels, dtype=bool)
    pred = np.asarray(predicted, dtype=bool)
    tp = int(np.sum(y & pred))
    fn = int(np.sum(y & ~pred))
    tn = int(np.sum(~y & ~pred))
    fp = int(np.sum(~y & pred))
    tpr = tp / (tp + fn) if tp + fn else float("nan")
    tnr = tn / (tn + fp) if tn + fp else float("nan")
    return {
        "accuracy": float(np.mean(y == pred)) if len(y) else float("nan"),
        "balanced_accuracy": 0.5 * (tpr + tnr),
        "tpr": tpr,
        "tnr": tnr,
        "fpr": 1.0 - tnr,
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
    }


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return float("nan"), float("nan")
    p = successes / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return center - half, center + half


def online_metrics(traces: pd.DataFrame) -> list[str]:
    metrics = []
    for column in ONLINE_METRIC_CANDIDATES:
        if column in traces and pd.api.types.is_numeric_dtype(traces[column]):
            if traces[column].notna().any() and traces[column].nunique(dropna=True) > 1:
                metrics.append(column)
    metrics.extend(
        sorted(
            column
            for column in traces
            if column.startswith("flow_")
            and pd.api.types.is_numeric_dtype(traces[column])
            and traces[column].notna().any()
        )
    )
    return list(dict.fromkeys(metrics))


def add_temporal_features(
    traces: pd.DataFrame,
    metrics: Sequence[str],
    windows: Sequence[int],
) -> tuple[pd.DataFrame, list[str]]:
    traces = traces.sort_values(EPISODE_KEYS + ["query_idx"]).copy()
    groups = traces.groupby(EPISODE_KEYS, dropna=False, sort=False)
    feature_names: list[str] = []
    for metric in metrics:
        values = pd.to_numeric(traces[metric], errors="coerce")
        traces[f"{metric}__current"] = values
        traces[f"{metric}__cummax"] = groups[metric].cummax()
        traces[f"{metric}__jump"] = groups[metric].diff().fillna(0.0)
        feature_names.extend(
            [f"{metric}__current", f"{metric}__cummax", f"{metric}__jump"]
        )
        for window in windows:
            rolling = (
                groups[metric]
                .rolling(window=window, min_periods=1)
                .agg(["max", "mean"])
                .reset_index(level=EPISODE_KEYS, drop=True)
                .sort_index()
            )
            max_name = f"{metric}__rollmax{window}"
            mean_name = f"{metric}__rollmean{window}"
            traces[max_name] = rolling["max"]
            traces[mean_name] = rolling["mean"]
            feature_names.extend([max_name, mean_name])
    return traces, feature_names


def episode_scores(
    temporal: pd.DataFrame,
    feature: str,
    max_query: int | None,
) -> pd.DataFrame:
    frame = temporal if max_query is None else temporal.loc[temporal["query_idx"] <= max_query]
    if frame.empty:
        return pd.DataFrame()
    group_columns = EPISODE_KEYS + [column for column in CONFIG_COLUMNS if column in frame]
    episode = (
        frame.groupby(group_columns, dropna=False)
        .agg(
            score=(feature, "max"),
            success=("success", "first"),
            final_t=("final_t", "first"),
            num_observed_queries=("query_idx", "size"),
        )
        .reset_index()
    )
    episode["fail"] = ~parse_bool(episode["success"])
    return episode


def conformal_upper_threshold(success_scores: Sequence[float], alpha: float) -> float:
    scores = np.sort(np.asarray(pd.Series(success_scores).dropna(), dtype=float))
    if len(scores) == 0:
        return float("nan")
    rank = min(len(scores), int(math.ceil((len(scores) + 1) * (1 - alpha))))
    return float(scores[rank - 1])


def detector_sweep(
    temporal: pd.DataFrame,
    features: Sequence[str],
    horizons: Sequence[int | None],
    alphas: Sequence[float],
) -> pd.DataFrame:
    rows = []
    for feature in features:
        for horizon in horizons:
            episodes = episode_scores(temporal, feature, horizon)
            if episodes.empty:
                continue
            config_group = [
                "case_id",
                "planning_strategy",
                "planning_risk_lambda",
                "planning_action_weight",
                "prediction_mode",
                "num_samples",
                "num_open_loop_steps",
            ]
            for keys, group in episodes.groupby(config_group, dropna=False):
                calibration = group.loc[group["experiment_split"] == "calibration"]
                holdout = group.loc[group["experiment_split"] == "holdout"]
                if calibration["fail"].nunique() < 2 or holdout["fail"].nunique() < 2:
                    continue
                calibration_auc = auc_score(calibration["fail"], calibration["score"])
                holdout_auc = auc_score(holdout["fail"], holdout["score"])
                holdout_ap = average_precision(holdout["fail"], holdout["score"])
                calibration_success = calibration.loc[~calibration["fail"], "score"]
                for alpha in alphas:
                    threshold = conformal_upper_threshold(calibration_success, alpha)
                    metrics = classification_metrics(
                        holdout["fail"], holdout["score"].ge(threshold)
                    )
                    row = dict(zip(config_group, keys if isinstance(keys, tuple) else (keys,)))
                    row.update(
                        {
                            "feature": feature,
                            "max_query": -1 if horizon is None else horizon,
                            "alpha": alpha,
                            "threshold": threshold,
                            "calibration_auc": calibration_auc,
                            "holdout_auc": holdout_auc,
                            "holdout_auprc": holdout_ap,
                            "calibration_episodes": len(calibration),
                            "calibration_success": int((~calibration["fail"]).sum()),
                            "holdout_episodes": len(holdout),
                            "holdout_fail": int(holdout["fail"].sum()),
                            **metrics,
                        }
                    )
                    rows.append(row)
    return pd.DataFrame(rows)


def planning_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        column
        for column in CONFIG_COLUMNS
        if column in episodes and column != "experiment_split"
    ]
    group_columns.insert(1, "experiment_split")
    rows = []
    for keys, group in episodes.groupby(group_columns, dropna=False):
        successes = int(group["success"].sum())
        low, high = wilson_interval(successes, len(group))
        row = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,)))
        row.update(
            {
                "episodes": len(group),
                "successes": successes,
                "success_rate": successes / len(group),
                "wilson_low": low,
                "wilson_high": high,
                "mean_final_t": float(group["final_t"].mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def paired_planning_comparison(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    comparison_columns = [
        "case_id",
        "experiment_split",
        "prediction_mode",
        "num_samples",
        "num_open_loop_steps",
        "num_denoising_steps_action",
    ]
    for keys, group in episodes.groupby(comparison_columns, dropna=False):
        baseline = group.loc[group["planning_strategy"] == "max_value"].copy()
        if baseline.empty:
            continue
        baseline = baseline.drop_duplicates("rollout_seed").set_index("rollout_seed")
        strategy_columns = [
            "planning_strategy",
            "planning_risk_lambda",
            "planning_action_weight",
        ]
        for strategy_keys, strategy in group.groupby(strategy_columns, dropna=False):
            if strategy_keys[0] == "max_value":
                continue
            strategy = strategy.drop_duplicates("rollout_seed").set_index("rollout_seed")
            shared = baseline.index.intersection(strategy.index)
            if len(shared) == 0:
                continue
            base_success = parse_bool(baseline.loc[shared, "success"])
            strategy_success = parse_bool(strategy.loc[shared, "success"])
            row = dict(zip(comparison_columns, keys if isinstance(keys, tuple) else (keys,)))
            row.update(dict(zip(strategy_columns, strategy_keys)))
            row.update(
                {
                    "paired_rollouts": len(shared),
                    "baseline_success_rate": float(base_success.mean()),
                    "strategy_success_rate": float(strategy_success.mean()),
                    "delta_success_rate": float(strategy_success.mean() - base_success.mean()),
                    "wins": int((strategy_success & ~base_success).sum()),
                    "losses": int((~strategy_success & base_success).sum()),
                    "ties": int((strategy_success == base_success).sum()),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def select_on_calibration(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    calibration = summary.loc[summary["experiment_split"] == "calibration"].copy()
    holdout = summary.loc[summary["experiment_split"] == "holdout"].copy()
    if calibration.empty or holdout.empty:
        return pd.DataFrame()
    setting_columns = [
        "case_id",
        "prediction_mode",
        "num_samples",
        "num_open_loop_steps",
        "num_denoising_steps_action",
    ]
    method_columns = [
        "planning_strategy",
        "planning_risk_lambda",
        "planning_action_weight",
    ]
    selected = (
        calibration.sort_values(
            setting_columns + ["success_rate", "mean_final_t"],
            ascending=[True] * len(setting_columns) + [False, True],
        )
        .groupby(setting_columns, dropna=False)
        .first()
        .reset_index()
    )
    selected = selected[setting_columns + method_columns].rename(
        columns={column: f"selected_{column}" for column in method_columns}
    )
    result = holdout.merge(selected, on=setting_columns, how="inner")
    mask = np.ones(len(result), dtype=bool)
    for column in method_columns:
        mask &= result[column].eq(result[f"selected_{column}"])
    return result.loc[mask].copy()


def save_plots(
    planning: pd.DataFrame,
    detector: pd.DataFrame,
    output_dir: Path,
) -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    if not planning.empty:
        holdout = planning.loc[planning["experiment_split"].isin(["holdout", "generalization"])]
        if not holdout.empty:
            labels = (
                holdout["case_id"].astype(str)
                + "\n"
                + holdout["planning_strategy"].astype(str)
                + " lambda="
                + holdout["planning_risk_lambda"].astype(str)
            )
            order = np.argsort(holdout["success_rate"].to_numpy())
            fig, axis = plt.subplots(figsize=(11, max(5, len(holdout) * 0.18)))
            axis.barh(labels.iloc[order], holdout["success_rate"].iloc[order], color="#2f6f8f")
            axis.set_xlim(0, 1)
            axis.set_xlabel("Success rate")
            axis.set_title("Holdout/generalization planning results")
            fig.tight_layout()
            fig.savefig(plot_dir / "planning_success_rates.png", dpi=180)
            plt.close(fig)
    if not detector.empty:
        eligible = detector.loc[
            detector["max_query"].between(0, 5)
            & detector["alpha"].eq(0.1)
        ].copy()
        best = eligible.sort_values(
            ["calibration_auc", "feature", "max_query"],
            ascending=[False, True, True],
        ).head(25)
        labels = (
            best["feature"].str.replace("__", " / ", regex=False)
            + " q<="
            + best["max_query"].astype(str)
        )
        fig, axis = plt.subplots(figsize=(10, 8))
        axis.barh(labels.iloc[::-1], best["holdout_auc"].iloc[::-1], color="#a55233")
        axis.axvline(0.5, color="black", linewidth=1, linestyle="--")
        axis.set_xlim(0, 1)
        axis.set_xlabel("Holdout AUROC")
        axis.set_title("Detector variants selected by calibration AUROC")
        fig.tight_layout()
        fig.savefig(plot_dir / "detector_holdout_auc.png", dpi=180)
        plt.close(fig)


def write_readme(
    output_dir: Path,
    traces: pd.DataFrame,
    episodes: pd.DataFrame,
    planning: pd.DataFrame,
    paired: pd.DataFrame,
    detector: pd.DataFrame,
    selected: pd.DataFrame,
) -> None:
    if detector.empty:
        best_detector = pd.DataFrame()
    else:
        # Keep the automatic ranking pre-failure and calibration-only.  Holdout
        # metrics are displayed after selection, never used as a tie-breaker.
        eligible_detector = detector.loc[
            detector["max_query"].between(0, 5)
            & detector["alpha"].eq(0.1)
        ].copy()
        best_detector = eligible_detector.sort_values(
            ["calibration_auc", "feature", "max_query"],
            ascending=[False, True, True],
        ).head(10)
    best_planning = (
        planning.loc[planning["experiment_split"].isin(["holdout", "generalization"])]
        .sort_values("success_rate", ascending=False)
        .head(15)
        if not planning.empty
        else pd.DataFrame()
    )
    lines = [
        "# Eight-hour LIBERO validation analysis",
        "",
        f"- Query rows: {len(traces)}",
        f"- Episodes: {len(episodes)}",
        f"- Successes / failures: {int(episodes['success'].sum())} / {int((~episodes['success']).sum())}",
        f"- Cases: {episodes['case_id'].nunique()}",
        "",
        "This is an automatically generated inventory, not the final scientific",
        "interpretation. The detector sweep contains many correlated variants.",
        "The table below is restricted to q<=5 and alpha=0.1, and is ranked only",
        "by calibration AUROC. Holdout metrics are never used for selection.",
        "",
        "## Best holdout/generalization planning rows",
        "",
        best_planning.to_markdown(index=False) if not best_planning.empty else "Not available yet.",
        "",
        "## Paired gains over max(value)",
        "",
        (
            paired.sort_values(["delta_success_rate", "wins"], ascending=False)
            .head(15)
            .to_markdown(index=False)
            if not paired.empty
            else "Not available yet."
        ),
        "",
        "## Exploratory pre-failure detector variants ranked on calibration",
        "",
        best_detector.to_markdown(index=False) if not best_detector.empty else "Not available yet.",
        "",
        "## Frozen calibration selections evaluated on holdout",
        "",
        selected.to_markdown(index=False) if not selected.empty else "Not available yet.",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def parse_optional_ints(value: str) -> list[int | None]:
    result: list[int | None] = []
    for item in value.split(","):
        item = item.strip().lower()
        result.append(None if item in {"all", "none", "-1"} else int(item))
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--windows", default="2,3,4,6")
    parser.add_argument("--max-queries", default="0,1,2,3,5,7,10,all")
    parser.add_argument("--alphas", default="0.05,0.1,0.2")
    args = parser.parse_args(argv)

    output_dir = args.output_dir or (args.campaign_dir / "analysis" / "full_validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    traces = load_campaign_traces(args.campaign_dir)
    metrics = online_metrics(traces)
    temporal, temporal_features = add_temporal_features(
        traces,
        metrics,
        [int(item) for item in args.windows.split(",") if item],
    )
    episodes = first_per_episode(traces)
    detector = detector_sweep(
        temporal,
        temporal_features,
        parse_optional_ints(args.max_queries),
        [float(item) for item in args.alphas.split(",") if item],
    )
    planning = planning_summary(episodes)
    paired = paired_planning_comparison(episodes)
    selected = select_on_calibration(planning)

    traces.to_parquet(output_dir / "all_query_traces.parquet", index=False)
    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    planning.to_csv(output_dir / "planning_strategy_summary.csv", index=False)
    paired.to_csv(output_dir / "paired_vs_max_value.csv", index=False)
    detector.to_csv(output_dir / "temporal_conformal_detector_sweep.csv", index=False)
    selected.to_csv(output_dir / "selected_on_calibration_holdout_results.csv", index=False)
    save_plots(planning, detector, output_dir)
    write_readme(output_dir, traces, episodes, planning, paired, detector, selected)
    summary = {
        "query_rows": len(traces),
        "episodes": len(episodes),
        "successes": int(episodes["success"].sum()),
        "failures": int((~episodes["success"]).sum()),
        "online_metrics": metrics,
        "temporal_feature_count": len(temporal_features),
        "detector_variants": len(detector),
        "planning_rows": len(planning),
        "paired_comparisons": len(paired),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

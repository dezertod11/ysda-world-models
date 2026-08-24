#!/usr/bin/env python3
"""Evaluate temporal action-overlap alarms on a completed LIBERO campaign."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OVERLAP_METRICS = [
    "overlap_selected_rmse",
    "overlap_selected_all_rmse",
    "overlap_first_l2",
    "overlap_xyz_rmse",
    "overlap_rot_rmse",
    "overlap_gripper_mismatch",
    "overlap_cosine_distance",
    "overlap_direction_reversal_rate",
    "overlap_support_min",
    "overlap_switch_gap",
    "overlap_set_chamfer",
    "overlap_energy_distance",
    "overlap_mmd2_median",
    "overlap_shift",
    "overlap_coupled_mean",
]

ONLINE_BASELINES = [
    "action_first_step_l2_std",
    "action_std_mean",
    "value_std",
    "value_range",
    "future_proprio_std_mean",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_action_internal_consistency_mean",
    "candidate_value_internal_consistency_mean",
    "risk_negative_value_mean",
    "risk_negative_selected_value",
    "previous_prediction_error_future_proprio_l2",
]

EPISODE_COLUMNS = [
    "source_run",
    "suite",
    "task_id",
    "init_state_id",
    "pair_id",
    "rollout_id",
    "rollout_seed",
]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def auc_score(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    positives = int(frame["label"].sum())
    negatives = len(frame) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = frame["score"].rank(method="average")
    rank_sum = float(ranks[frame["label"]].sum())
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: Sequence[bool], scores: Sequence[float]) -> float:
    frame = pd.DataFrame({"label": labels, "score": scores}).dropna()
    positives = int(frame["label"].sum())
    if positives == 0:
        return float("nan")
    thresholds = (
        frame.groupby("score", sort=False)["label"]
        .agg(["sum", "count"])
        .sort_index(ascending=False)
    )
    true_positives = thresholds["sum"].cumsum()
    predicted_positives = thresholds["count"].cumsum()
    precision = true_positives / predicted_positives
    recall_increment = thresholds["sum"] / positives
    return float((precision * recall_increment).sum())


def conformal_upper_threshold(success_scores: Sequence[float], alpha: float) -> float:
    scores = np.sort(np.asarray(pd.Series(success_scores).dropna(), dtype=float))
    if len(scores) == 0:
        return float("nan")
    rank = min(len(scores), int(math.ceil((len(scores) + 1) * (1 - alpha))))
    return float(scores[rank - 1])


def classification_metrics(
    labels: Sequence[bool], predictions: Sequence[bool]
) -> dict[str, float]:
    labels_array = np.asarray(labels, dtype=bool)
    predictions_array = np.asarray(predictions, dtype=bool)
    tp = int(np.sum(labels_array & predictions_array))
    fn = int(np.sum(labels_array & ~predictions_array))
    tn = int(np.sum(~labels_array & ~predictions_array))
    fp = int(np.sum(~labels_array & predictions_array))
    tpr = tp / (tp + fn) if tp + fn else float("nan")
    tnr = tn / (tn + fp) if tn + fp else float("nan")
    return {
        "balanced_accuracy": 0.5 * (tpr + tnr),
        "tpr": tpr,
        "tnr": tnr,
        "fpr": 1.0 - tnr if np.isfinite(tnr) else float("nan"),
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
    }


def empirical_anomaly_probability(
    calibration_scores: Sequence[float], test_scores: Sequence[float]
) -> np.ndarray:
    calibration = np.sort(
        np.asarray(pd.Series(calibration_scores).dropna(), dtype=float)
    )
    test = np.asarray(test_scores, dtype=float)
    if len(calibration) == 0:
        return np.full(test.shape, np.nan, dtype=float)
    return (np.searchsorted(calibration, test, side="right") + 1) / (
        len(calibration) + 1
    )


def _source_run(path: Path) -> str:
    suffix = "__query_traces.parquet"
    return path.name[: -len(suffix)] if path.name.endswith(suffix) else path.stem


def load_campaign_traces(campaign_dir: Path) -> tuple[pd.DataFrame, list[Path]]:
    run_dir = campaign_dir / "runs"
    paths = sorted(run_dir.rglob("*__query_traces.parquet"))
    if not paths:
        paths = sorted(campaign_dir.rglob("*__query_traces.parquet"))
    if not paths:
        aggregate = campaign_dir / "analysis" / "temporal_overlap" / "all_query_traces.parquet"
        if not aggregate.is_file():
            raise FileNotFoundError(f"No query trace parquet files under {campaign_dir}")
        frame = pd.read_parquet(aggregate)
        if "source_trace" not in frame:
            frame["source_trace"] = str(aggregate)
        if "source_run" not in frame:
            frame["source_run"] = "aggregate"
        return frame, [aggregate]

    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frame["source_run"] = _source_run(path)
        frames.append(frame)
    traces = pd.concat(frames, ignore_index=True, sort=False)
    return traces, paths


def prepare_traces(traces: pd.DataFrame) -> pd.DataFrame:
    frame = traces.copy()
    if "overlap_valid" not in frame:
        raise ValueError(
            "Trace has no overlap_valid column; collector did not record temporal overlap"
        )
    frame["overlap_valid"] = parse_bool(frame["overlap_valid"])
    frame["success"] = parse_bool(frame["success"])
    if "temporal_overlap_seed_mode" not in frame:
        frame["temporal_overlap_seed_mode"] = "unspecified"
    if "pre_critical_event_query" in frame:
        frame["pre_critical_event_query"] = parse_bool(
            frame["pre_critical_event_query"]
        )
    else:
        event_t = (
            pd.to_numeric(frame["critical_event_t"], errors="coerce").fillna(-1)
            if "critical_event_t" in frame
            else pd.Series(-1, index=frame.index, dtype=float)
        )
        frame["pre_critical_event_query"] = event_t.lt(0) | frame["t"].lt(event_t)

    available_episode_columns = [
        column for column in EPISODE_COLUMNS if column in frame
    ]
    frame["episode_uid"] = (
        frame[available_episode_columns].astype(str).agg("|".join, axis=1)
    )
    frame = frame.sort_values(["episode_uid", "query_idx"]).reset_index(drop=True)
    if "value_mean" in frame:
        frame["risk_negative_value_mean"] = -pd.to_numeric(
            frame["value_mean"], errors="coerce"
        )
    if "selected_value" in frame:
        frame["risk_negative_selected_value"] = -pd.to_numeric(
            frame["selected_value"], errors="coerce"
        )
    if "prediction_error_future_proprio_l2" in frame:
        frame["previous_prediction_error_future_proprio_l2"] = frame.groupby(
            "episode_uid", sort=False
        )["prediction_error_future_proprio_l2"].shift(1)
    return frame


def metric_columns(frame: pd.DataFrame) -> list[str]:
    return [
        metric
        for metric in OVERLAP_METRICS + ONLINE_BASELINES
        if metric in frame
        and pd.to_numeric(frame[metric], errors="coerce").notna().any()
    ]


def nominal_calibration_rows(
    frame: pd.DataFrame, seed_mode: str | None = None
) -> tuple[pd.DataFrame, str]:
    eligible = frame.loc[frame["overlap_valid"] & frame["pre_critical_event_query"]]
    if seed_mode is not None:
        eligible = eligible.loc[eligible["temporal_overlap_seed_mode"].eq(seed_mode)]
    calibration = eligible.loc[
        eligible["experiment_split"].eq("calibration") & eligible["success"]
    ]
    if len(calibration):
        return calibration, "successful calibration split"
    fallback = eligible.loc[eligible["success"]]
    return fallback, "fallback: all successful episodes"


def holdout_rows(frame: pd.DataFrame, seed_mode: str | None = None) -> pd.DataFrame:
    eligible = frame.loc[frame["overlap_valid"] & frame["pre_critical_event_query"]]
    if seed_mode is not None:
        eligible = eligible.loc[eligible["temporal_overlap_seed_mode"].eq(seed_mode)]
    holdout = eligible.loc[
        eligible["experiment_split"].isin(["holdout", "generalization"])
    ]
    return (
        holdout
        if len(holdout)
        else eligible.loc[~eligible["experiment_split"].eq("calibration")]
    )


def detector_table(
    frame: pd.DataFrame,
    metrics: Iterable[str],
    horizons: Sequence[int],
    alpha: float,
) -> pd.DataFrame:
    rows = []
    seed_modes = frame["temporal_overlap_seed_mode"].dropna().astype(str).unique()
    for seed_mode in seed_modes:
        calibration, calibration_source = nominal_calibration_rows(frame, seed_mode)
        holdout = holdout_rows(frame, seed_mode)
        for metric in metrics:
            calibration_scores = pd.to_numeric(
                calibration[metric], errors="coerce"
            ).dropna()
            threshold = conformal_upper_threshold(calibration_scores, alpha)
            for horizon in horizons:
                label_column = f"critical_event_within_{horizon}"
                if label_column not in holdout:
                    continue
                test = holdout.assign(
                    _score=pd.to_numeric(holdout[metric], errors="coerce"),
                    _label=parse_bool(holdout[label_column]),
                ).dropna(subset=["_score"])
                probabilities = empirical_anomaly_probability(
                    calibration_scores, test["_score"]
                )
                labels = test["_label"].to_numpy(dtype=bool)
                classification = classification_metrics(
                    labels, test["_score"].gt(threshold)
                )
                rows.append(
                    {
                        "seed_mode": seed_mode,
                        "metric": metric,
                        "metric_family": "overlap"
                        if metric.startswith("overlap_")
                        else "baseline",
                        "horizon": horizon,
                        "alpha": alpha,
                        "calibration_source": calibration_source,
                        "calibration_queries": int(len(calibration_scores)),
                        "holdout_queries": int(len(test)),
                        "positive_queries": int(labels.sum()),
                        "negative_queries": int((~labels).sum()),
                        "prevalence": float(labels.mean())
                        if len(labels)
                        else float("nan"),
                        "threshold": threshold,
                        "auroc": auc_score(labels, test["_score"]),
                        "auprc": average_precision(labels, test["_score"]),
                        "ecdf_anomaly_brier": (
                            float(
                                np.mean(np.square(probabilities - labels.astype(float)))
                            )
                            if len(labels)
                            else float("nan")
                        ),
                        **classification,
                    }
                )
    return pd.DataFrame(rows)


def event_detection_table(
    frame: pd.DataFrame,
    detector: pd.DataFrame,
    metrics: Iterable[str],
    horizons: Sequence[int],
) -> pd.DataFrame:
    rows = []
    for seed_mode in detector["seed_mode"].dropna().astype(str).unique():
        holdout = holdout_rows(frame, seed_mode)
        for metric in metrics:
            for horizon in horizons:
                selected = detector.loc[
                    detector["seed_mode"].eq(seed_mode)
                    & detector["metric"].eq(metric)
                    & detector["horizon"].eq(horizon)
                ]
                if selected.empty:
                    continue
                threshold = float(selected["threshold"].iloc[0])
                event_episodes = holdout.loc[holdout["critical_event_t"].ge(0)].groupby(
                    "episode_uid", sort=False
                )
                leads = []
                eligible_events = 0
                for _episode_uid, episode in event_episodes:
                    event_t = int(episode["critical_event_t"].iloc[0])
                    window = episode.loc[
                        episode["steps_to_first_critical_event"].gt(0)
                        & episode["steps_to_first_critical_event"].le(horizon)
                    ].copy()
                    window["_score"] = pd.to_numeric(window[metric], errors="coerce")
                    window = window.dropna(subset=["_score"])
                    if window.empty:
                        continue
                    eligible_events += 1
                    alarms = window.loc[window["_score"].gt(threshold)]
                    if len(alarms):
                        first_alarm_t = int(alarms["t"].min())
                        leads.append(event_t - first_alarm_t)

                no_event = holdout.loc[holdout["critical_event_t"].lt(0)].copy()
                no_event["_score"] = pd.to_numeric(no_event[metric], errors="coerce")
                episode_false_alarms = []
                for _episode_uid, episode in no_event.dropna(subset=["_score"]).groupby(
                    "episode_uid", sort=False
                ):
                    episode_false_alarms.append(
                        bool(episode["_score"].gt(threshold).any())
                    )

                rows.append(
                    {
                        "seed_mode": seed_mode,
                        "metric": metric,
                        "metric_family": "overlap"
                        if metric.startswith("overlap_")
                        else "baseline",
                        "horizon": horizon,
                        "threshold": threshold,
                        "eligible_event_episodes": eligible_events,
                        "detected_event_episodes": len(leads),
                        "event_detection_rate": len(leads) / eligible_events
                        if eligible_events
                        else float("nan"),
                        "median_lead_steps": float(np.median(leads))
                        if leads
                        else float("nan"),
                        "mean_lead_steps": float(np.mean(leads))
                        if leads
                        else float("nan"),
                        "no_event_episodes": len(episode_false_alarms),
                        "false_alarm_episode_rate": (
                            float(np.mean(episode_false_alarms))
                            if episode_false_alarms
                            else float("nan")
                        ),
                    }
                )
    return pd.DataFrame(rows)


def episode_table(frame: pd.DataFrame, metrics: Iterable[str]) -> pd.DataFrame:
    rows = []
    for seed_mode in frame["temporal_overlap_seed_mode"].dropna().astype(str).unique():
        holdout = holdout_rows(frame, seed_mode)
        for metric in metrics:
            grouped = holdout.assign(
                _score=pd.to_numeric(holdout[metric], errors="coerce")
            ).groupby("episode_uid", sort=False)
            episodes = grouped.agg(
                score_max=("_score", "max"),
                score_mean=("_score", "mean"),
                success=("success", "first"),
                case_id=("case_id", "first"),
                suite=("suite", "first"),
            ).dropna(subset=["score_max"])
            labels = ~episodes["success"].astype(bool)
            rows.append(
                {
                    "seed_mode": seed_mode,
                    "metric": metric,
                    "metric_family": "overlap"
                    if metric.startswith("overlap_")
                    else "baseline",
                    "holdout_episodes": len(episodes),
                    "failed_episodes": int(labels.sum()),
                    "successful_episodes": int((~labels).sum()),
                    "max_auroc_terminal_fail": auc_score(labels, episodes["score_max"]),
                    "max_auprc_terminal_fail": average_precision(
                        labels, episodes["score_max"]
                    ),
                    "mean_auroc_terminal_fail": auc_score(
                        labels, episodes["score_mean"]
                    ),
                    "mean_auprc_terminal_fail": average_precision(
                        labels, episodes["score_mean"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def case_table(
    frame: pd.DataFrame, metrics: Iterable[str], horizon: int
) -> pd.DataFrame:
    label_column = f"critical_event_within_{horizon}"
    rows = []
    for seed_mode in frame["temporal_overlap_seed_mode"].dropna().astype(str).unique():
        holdout = holdout_rows(frame, seed_mode)
        for case_id, case in holdout.groupby("case_id", dropna=False):
            labels = parse_bool(case[label_column])
            for metric in metrics:
                scores = pd.to_numeric(case[metric], errors="coerce")
                valid = scores.notna()
                rows.append(
                    {
                        "seed_mode": seed_mode,
                        "case_id": case_id,
                        "suite": case["suite"].iloc[0],
                        "metric": metric,
                        "horizon": horizon,
                        "queries": int(valid.sum()),
                        "positive_queries": int(labels[valid].sum()),
                        "auroc": auc_score(labels[valid], scores[valid]),
                        "auprc": average_precision(labels[valid], scores[valid]),
                    }
                )
    return pd.DataFrame(rows)


def make_plots(
    detector: pd.DataFrame, frame: pd.DataFrame, output_dir: Path
) -> list[Path]:
    paths = []
    preferred_mode = (
        "independent"
        if "independent" in set(detector["seed_mode"])
        else detector["seed_mode"].iloc[0]
    )
    focus = (
        detector.loc[
            detector["horizon"].eq(16) & detector["seed_mode"].eq(preferred_mode)
        ]
        .sort_values("auprc", ascending=False)
        .head(12)
    )
    if len(focus):
        figure, axes = plt.subplots(1, 2, figsize=(14, 5))
        colors = [
            "#2b6f77" if family == "overlap" else "#c46b3c"
            for family in focus["metric_family"]
        ]
        axes[0].barh(focus["metric"], focus["auprc"], color=colors)
        axes[0].invert_yaxis()
        axes[0].set_xlabel("AUPRC (event within 16 steps)")
        axes[0].axvline(
            float(focus["prevalence"].iloc[0]),
            color="black",
            linestyle="--",
            linewidth=1,
        )
        axes[1].barh(focus["metric"], focus["auroc"], color=colors)
        axes[1].invert_yaxis()
        axes[1].set_xlabel("AUROC (event within 16 steps)")
        axes[1].axvline(0.5, color="black", linestyle="--", linewidth=1)
        figure.tight_layout()
        path = output_dir / "metric_comparison_h16.png"
        figure.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(figure)
        paths.append(path)

    overlap = [metric for metric in focus["metric"] if metric.startswith("overlap_")][
        :4
    ]
    test = holdout_rows(frame, preferred_mode)
    if overlap and "critical_event_within_16" in test:
        labels = parse_bool(test["critical_event_within_16"])
        figure, axes = plt.subplots(
            len(overlap), 1, figsize=(11, 2.8 * len(overlap)), squeeze=False
        )
        for axis, metric in zip(axes[:, 0], overlap):
            negative = pd.to_numeric(
                test.loc[~labels, metric], errors="coerce"
            ).dropna()
            positive = pd.to_numeric(test.loc[labels, metric], errors="coerce").dropna()
            axis.boxplot(
                [negative, positive],
                tick_labels=["no event <=16", "event <=16"],
                vert=False,
                showfliers=False,
            )
            axis.set_title(metric)
        figure.tight_layout()
        path = output_dir / "top_overlap_event_distributions_h16.png"
        figure.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(figure)
        paths.append(path)
    return paths


def write_report(
    output_dir: Path,
    traces: pd.DataFrame,
    trace_paths: Sequence[Path],
    detector: pd.DataFrame,
    event_detection: pd.DataFrame,
    episodes: pd.DataFrame,
    calibration_source: str,
) -> Path:
    h16 = detector.loc[detector["horizon"].eq(16)].sort_values("auprc", ascending=False)
    best = h16.iloc[0].to_dict() if len(h16) else {}
    best_overlap_rows = h16.loc[h16["metric_family"].eq("overlap")]
    best_overlap = best_overlap_rows.iloc[0].to_dict() if len(best_overlap_rows) else {}
    best_by_seed_mode = {}
    for seed_mode, rows in h16.groupby("seed_mode", sort=False):
        best_by_seed_mode[str(seed_mode)] = rows.iloc[0].to_dict()
    event_episodes = int(
        traces.loc[traces["critical_event_t"].ge(0), "episode_uid"].nunique()
        if "critical_event_t" in traces
        else 0
    )
    summary = {
        "trace_files": len(trace_paths),
        "query_rows": int(len(traces)),
        "episodes": int(traces["episode_uid"].nunique()),
        "event_episodes": event_episodes,
        "calibration_source": calibration_source,
        "best_h16": best,
        "best_overlap_h16": best_overlap,
        "best_h16_by_seed_mode": best_by_seed_mode,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    lines = [
        "# Temporal overlap: passive detection results",
        "",
        f"- Trace files: {len(trace_paths)}",
        f"- Episodes: {summary['episodes']}",
        f"- Query rows: {summary['query_rows']}",
        f"- Episodes with a collector-labeled critical event: {event_episodes}",
        f"- Threshold calibration: {calibration_source}",
        "",
        "## Main readout",
        "",
    ]
    if best_by_seed_mode:
        lines.extend(
            [
                "| Seed mode | Best H=16 metric | AUPRC | Prevalence | AUROC | TPR | FPR |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for seed_mode, row in best_by_seed_mode.items():
            lines.append(
                f"| {seed_mode} | `{row['metric']}` | {row['auprc']:.3f} | "
                f"{row['prevalence']:.3f} | {row['auroc']:.3f} | "
                f"{row['tpr']:.3f} | {row['fpr']:.3f} |"
            )
        lines.append("")
    lines.extend(
        [
            "Average precision is computed over unique score thresholds, so tied scores "
            "cannot gain from source-row ordering.",
            "",
            "This is a passive detector experiment: overlap scores did not alter candidate selection or execution.",
            "Post-event queries are excluded. Terminal timeout/fail separation is reported only as a secondary endpoint.",
            "Collector event labels are heuristic and require a task-semantic audit before the table can be interpreted as failure prediction.",
            "A causal planning claim requires a later frozen-threshold paired intervention run.",
            "",
            "## Outputs",
            "",
            "- `query_detector_metrics.csv`: query-level early-warning metrics for R=8/16/32.",
            "- `event_detection_metrics.csv`: event detection rate, lead time, and episode false alarms.",
            "- `episode_terminal_metrics.csv`: secondary terminal success/fail separation.",
            "- `case_metrics_h16.csv`: per-case transfer diagnostics.",
        ]
    )
    report_path = output_dir / "README.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def analyze_campaign(
    campaign_dir: Path,
    output_dir: Path,
    horizons: Sequence[int] = (8, 16, 32),
    alpha: float = 0.05,
) -> dict[str, Path]:
    traces, trace_paths = load_campaign_traces(campaign_dir)
    traces = prepare_traces(traces)
    metrics = metric_columns(traces)
    if not any(metric.startswith("overlap_") for metric in metrics):
        raise ValueError("No finite temporal overlap metric was found")
    output_dir.mkdir(parents=True, exist_ok=True)

    detector = detector_table(traces, metrics, horizons, alpha)
    event_detection = event_detection_table(traces, detector, metrics, horizons)
    episodes = episode_table(traces, metrics)
    cases = case_table(traces, metrics, horizon=16)
    calibration, calibration_source = nominal_calibration_rows(traces)

    paths = {
        "all_query_traces": output_dir / "all_query_traces.parquet",
        "query_detector_metrics": output_dir / "query_detector_metrics.csv",
        "event_detection_metrics": output_dir / "event_detection_metrics.csv",
        "episode_terminal_metrics": output_dir / "episode_terminal_metrics.csv",
        "case_metrics_h16": output_dir / "case_metrics_h16.csv",
    }
    traces.to_parquet(paths["all_query_traces"], index=False)
    detector.to_csv(paths["query_detector_metrics"], index=False)
    event_detection.to_csv(paths["event_detection_metrics"], index=False)
    episodes.to_csv(paths["episode_terminal_metrics"], index=False)
    cases.to_csv(paths["case_metrics_h16"], index=False)
    for plot_path in make_plots(detector, traces, output_dir):
        paths[plot_path.stem] = plot_path
    paths["report"] = write_report(
        output_dir,
        traces,
        trace_paths,
        detector,
        event_detection,
        episodes,
        calibration_source,
    )
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--horizons", default="8,16,32")
    parser.add_argument("--alpha", type=float, default=0.05)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not 0 < args.alpha < 1:
        raise ValueError("--alpha must be in (0, 1)")
    horizons = tuple(int(value) for value in args.horizons.split(",") if value.strip())
    output_dir = args.output_dir or (
        args.campaign_dir / "analysis" / "temporal_overlap"
    )
    paths = analyze_campaign(args.campaign_dir, output_dir, horizons, args.alpha)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

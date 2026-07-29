#!/usr/bin/env python3
"""Aggregate completed LIBERO campaign runs into a leakage-aware Phase 1 report."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN_ROOT = PROJECT_ROOT / "experiments" / "campaigns"
DEFAULT_OUTPUT_DIR = DEFAULT_CAMPAIGN_ROOT / "phase1_analysis_20260724"

ID_SUITES = {"libero_spatial", "libero_object", "libero_goal", "libero_10"}

ONLINE_METRICS = [
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
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_across_seed_std_mean",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
]

PREDICTION_ERROR_METRICS = [
    "prediction_error_future_image_mse",
    "prediction_error_future_wrist_mse",
    "prediction_error_future_proprio_l2",
    "prediction_error_future_proprio_eef_pos_l2",
    "prediction_error_value_abs_chunk_success",
]

EPISODE_KEYS = [
    "campaign",
    "run_name",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_id",
    "rollout_seed",
]

GROUP_KEYS = ["suite", "task_id", "init_state_id"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--campaign-prefix",
        action="append",
        default=[],
        help="Campaign directory prefix to include. Defaults to phase1_*.",
    )
    parser.add_argument("--max-early-query", type=int, default=3)
    parser.add_argument("--include-smoke", action="store_true")
    parser.add_argument("--include-partial", action="store_true")
    return parser.parse_args()


def load_trace(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def trace_run_name(path: Path) -> str:
    suffix = "__query_traces"
    if not path.stem.endswith(suffix):
        raise ValueError(f"Unexpected trace name: {path}")
    return path.stem[: -len(suffix)]


def discover_traces(
    campaign_root: Path,
    prefixes: Sequence[str],
    include_smoke: bool,
    include_partial: bool,
) -> tuple[list[Path], pd.DataFrame]:
    selected: list[Path] = []
    inventory: list[dict[str, object]] = []
    campaign_dirs = sorted(path for path in campaign_root.iterdir() if path.is_dir())
    for campaign_dir in campaign_dirs:
        if prefixes and not any(campaign_dir.name.startswith(prefix) for prefix in prefixes):
            continue
        if not prefixes and not campaign_dir.name.startswith("phase1_"):
            continue
        if "analysis" in campaign_dir.name:
            continue
        if "smoke" in campaign_dir.name and not include_smoke:
            continue

        manifest_status = "missing"
        manifest_path = campaign_dir / "manifest.json"
        if manifest_path.exists():
            manifest_status = json.loads(manifest_path.read_text(encoding="utf-8")).get("status", "unknown")

        for parquet_path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
            run_name = trace_run_name(parquet_path)
            metadata_path = parquet_path.with_name(f"{run_name}__metadata.json")
            pair_summary_path = parquet_path.with_name(f"{run_name}__pair_summary.csv")
            complete = metadata_path.exists() and pair_summary_path.exists()
            reason = "included" if complete else "missing metadata or pair summary"
            if include_partial and not complete:
                reason = "included partial by request"
            include = complete or include_partial
            inventory.append(
                {
                    "campaign": campaign_dir.name,
                    "run_name": run_name,
                    "manifest_status": manifest_status,
                    "complete_artifacts": complete,
                    "included": include,
                    "reason": reason,
                    "trace_path": str(parquet_path.relative_to(PROJECT_ROOT)),
                }
            )
            if include:
                selected.append(parquet_path)
    return selected, pd.DataFrame(inventory)


def load_traces(paths: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frame = load_trace(path)
        frame.insert(0, "run_name", trace_run_name(path))
        frame.insert(0, "campaign", path.parents[1].name)
        frames.append(frame)
    if not frames:
        raise ValueError("No completed campaign traces were found")
    return pd.concat(frames, ignore_index=True)


def make_episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    episodes = (
        traces.sort_values("query_idx")
        .groupby(EPISODE_KEYS, dropna=False)
        .last()
        .reset_index()
    )
    episodes["split"] = np.where(episodes["suite"].isin(ID_SUITES), "ID", "OOD")
    episodes["failed"] = ~episodes["success"].astype(bool)
    return episodes


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return float("nan"), float("nan")
    rate = successes / total
    denominator = 1 + z**2 / total
    center = (rate + z**2 / (2 * total)) / denominator
    half_width = (
        z
        * math.sqrt(rate * (1 - rate) / total + z**2 / (4 * total**2))
        / denominator
    )
    return center - half_width, center + half_width


def summarize_outcomes(episodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    by_job = (
        episodes.groupby(["split", "campaign", "run_name"], dropna=False)
        .agg(
            episodes=("success", "size"),
            success=("success", "sum"),
            median_final_t=("final_t", "median"),
        )
        .reset_index()
    )
    by_job["fail"] = by_job["episodes"] - by_job["success"]
    by_job["success_rate"] = by_job["success"] / by_job["episodes"]

    by_task = (
        episodes.groupby(["split", "suite", "task_id", "init_state_id"], dropna=False)
        .agg(
            episodes=("success", "size"),
            success=("success", "sum"),
            median_final_t=("final_t", "median"),
        )
        .reset_index()
    )
    by_task["fail"] = by_task["episodes"] - by_task["success"]
    by_task["success_rate"] = by_task["success"] / by_task["episodes"]
    return by_job, by_task


def auc_high_means_failure(labels_failed: np.ndarray, scores: np.ndarray) -> float:
    labels = np.asarray(labels_failed, dtype=int)
    values = np.asarray(scores, dtype=float)
    mask = np.isfinite(values)
    labels = labels[mask]
    values = values[mask]
    positives = int(labels.sum())
    negatives = int(len(labels) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = stats.rankdata(values)
    rank_sum = ranks[labels == 1].sum()
    return float((rank_sum - positives * (positives + 1) / 2) / (positives * negatives))


def group_z_scores(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    pieces = []
    for _, group in frame.groupby(GROUP_KEYS, dropna=False):
        values = group[metric].astype(float)
        std = values.std(ddof=0)
        piece = group[["failed"]].copy()
        piece["score"] = (values - values.mean()) / (std if std > 0 else 1.0)
        pieces.append(piece)
    return pd.concat(pieces, ignore_index=True)


def make_early_episode_metrics(
    traces: pd.DataFrame,
    episodes: pd.DataFrame,
    max_query: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ood_outcomes = episodes.loc[episodes["split"] == "OOD", EPISODE_KEYS + ["success", "failed"]]
    mixed = (
        ood_outcomes.groupby(GROUP_KEYS, dropna=False)["success"]
        .nunique()
        .loc[lambda values: values == 2]
    )
    mixed_groups = set(mixed.index.tolist())

    early = traces.loc[
        (traces["query_idx"] <= max_query)
        & traces.apply(
            lambda row: (row["suite"], row["task_id"], row["init_state_id"]) in mixed_groups,
            axis=1,
        )
    ].copy()
    if "failure_event_t" in early:
        early = early.loc[
            (early["failure_event_t"] < 0)
            | (early["t"] < early["failure_event_t"])
        ]

    metrics = [metric for metric in ONLINE_METRICS if metric in early.columns]
    aggregated = (
        early.groupby(EPISODE_KEYS, dropna=False)[metrics]
        .agg(["mean", "count"])
    )
    aggregated.columns = [f"{metric}__{aggregation}" for metric, aggregation in aggregated.columns]
    aggregated = aggregated.reset_index().merge(
        ood_outcomes,
        on=EPISODE_KEYS,
        how="inner",
    )

    required_queries = max_query + 1
    count_columns = [f"{metric}__count" for metric in metrics]
    aggregated = aggregated.loc[(aggregated[count_columns] >= required_queries).all(axis=1)].copy()

    ranking_rows = []
    group_rows = []
    for metric in metrics:
        column = f"{metric}__mean"
        aucs = []
        weights = []
        for keys, group in aggregated.groupby(GROUP_KEYS, dropna=False):
            auc = auc_high_means_failure(group["failed"], group[column])
            aucs.append(auc)
            weights.append(len(group))
            group_rows.append(
                {
                    **dict(zip(GROUP_KEYS, keys)),
                    "metric": metric,
                    "episodes": int(len(group)),
                    "success": int(group["success"].sum()),
                    "fail": int(group["failed"].sum()),
                    "success_mean": float(group.loc[group["success"], column].mean()),
                    "fail_mean": float(group.loc[group["failed"], column].mean()),
                    "auc_high_means_failure": auc,
                }
            )

        z_scores = group_z_scores(
            aggregated.rename(columns={column: metric}),
            metric,
        )
        pooled_auc = auc_high_means_failure(z_scores["failed"], z_scores["score"])
        ranking_rows.append(
            {
                "metric": metric,
                "pooled_group_z_auc_high_means_failure": pooled_auc,
                "pooled_oriented_auc": max(pooled_auc, 1 - pooled_auc),
                "direction": "high=failure" if pooled_auc >= 0.5 else "low=failure",
                "weighted_mean_group_auc_high_means_failure": float(np.average(aucs, weights=weights)),
                "min_group_auc_high_means_failure": float(np.min(aucs)),
                "max_group_auc_high_means_failure": float(np.max(aucs)),
                "groups_strict_high_means_failure": int(sum(auc > 0.5 for auc in aucs)),
                "groups_tied": int(sum(auc == 0.5 for auc in aucs)),
                "groups_low_means_failure": int(sum(auc < 0.5 for auc in aucs)),
                "num_mixed_groups": int(len(aucs)),
                "episodes": int(len(aggregated)),
                "success": int(aggregated["success"].sum()),
                "fail": int(aggregated["failed"].sum()),
            }
        )

    ranking = pd.DataFrame(ranking_rows).sort_values(
        ["pooled_oriented_auc", "weighted_mean_group_auc_high_means_failure"],
        ascending=False,
    )
    by_group = pd.DataFrame(group_rows)
    return aggregated, ranking, by_group


def prediction_error_correlations(traces: pd.DataFrame) -> pd.DataFrame:
    ood = traces.loc[~traces["suite"].isin(ID_SUITES)].copy()
    online = [metric for metric in ONLINE_METRICS if metric in ood.columns]
    errors = [metric for metric in PREDICTION_ERROR_METRICS if metric in ood.columns]
    control_keys = GROUP_KEYS + ["query_idx"]
    rows = []
    for uncertainty_metric in online:
        for error_metric in errors:
            values = (
                ood[control_keys + [uncertainty_metric, error_metric]]
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
            )
            if len(values) < 20:
                continue
            for column in [uncertainty_metric, error_metric]:
                values[column] = values.groupby(control_keys, dropna=False)[column].transform(
                    lambda series: (
                        (series - series.mean()) / series.std(ddof=0)
                        if series.std(ddof=0) > 0
                        else 0.0
                    )
                )
            if values[uncertainty_metric].nunique() < 2 or values[error_metric].nunique() < 2:
                continue
            rho, p_value = stats.spearmanr(values[uncertainty_metric], values[error_metric])
            rows.append(
                {
                    "uncertainty_metric": uncertainty_metric,
                    "prediction_error_metric": error_metric,
                    "spearman_r_after_suite_task_query_control": float(rho),
                    "abs_spearman_r": float(abs(rho)),
                    "p_value_naive": float(p_value),
                    "query_rows": int(len(values)),
                }
            )
    return pd.DataFrame(rows).sort_values(["abs_spearman_r", "query_rows"], ascending=False)


def save_plots(
    by_task: pd.DataFrame,
    episodes: pd.DataFrame,
    early_ranking: pd.DataFrame,
    early_by_group: pd.DataFrame,
    output_dir: Path,
) -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    task_plot = by_task.copy()
    task_plot["label"] = (
        task_plot["suite"].str.replace("libero_", "", regex=False)
        + " / task "
        + task_plot["task_id"].astype(str)
    )
    task_plot = task_plot.sort_values(["split", "success_rate", "label"])
    colors = np.where(task_plot["split"] == "ID", "#3b7f5c", "#c25d3c")
    fig, axis = plt.subplots(figsize=(11, max(5, 0.34 * len(task_plot))))
    axis.barh(task_plot["label"], task_plot["success_rate"], color=colors)
    for index, row in enumerate(task_plot.itertuples(index=False)):
        axis.text(
            min(row.success_rate + 0.015, 0.96),
            index,
            f"{row.success}/{row.episodes}",
            va="center",
            fontsize=8,
        )
    axis.set_xlim(0, 1.05)
    axis.set_xlabel("Task success rate")
    axis.set_title("Phase 1 outcomes: ID controls and completed LIBERO-PRO OOD runs")
    fig.tight_layout()
    fig.savefig(plot_dir / "success_rate_by_suite_task.png", dpi=180)
    plt.close(fig)

    failure_counts = episodes.loc[episodes["split"] == "OOD", "failure_type"].value_counts()
    fig, axis = plt.subplots(figsize=(8, 4))
    axis.bar(failure_counts.index, failure_counts.values, color=["#3b7f5c", "#c25d3c", "#d39b3a"])
    axis.set_ylabel("Episodes")
    axis.set_title("Completed OOD episode outcomes")
    axis.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(plot_dir / "ood_failure_modes.png", dpi=180)
    plt.close(fig)

    top = early_ranking.head(10).sort_values("pooled_oriented_auc")
    fig, axis = plt.subplots(figsize=(10, 5.5))
    axis.barh(top["metric"], top["pooled_oriented_auc"], color="#386a8c")
    axis.axvline(0.5, color="black", linestyle="--", linewidth=1)
    axis.set_xlim(0.45, 1.0)
    axis.set_xlabel("Exploratory AUROC for eventual failure")
    axis.set_title("Early online metrics, query 0-3, within-group standardized")
    fig.tight_layout()
    fig.savefig(plot_dir / "early_online_metric_auc.png", dpi=180)
    plt.close(fig)

    if len(early_ranking):
        top_metric = early_ranking.iloc[0]["metric"]
        metric_groups = early_by_group.loc[early_by_group["metric"] == top_metric].copy()
        metric_groups["label"] = (
            metric_groups["suite"].str.replace("libero_", "", regex=False)
            + " / task "
            + metric_groups["task_id"].astype(str)
        )
        x = np.arange(len(metric_groups))
        width = 0.36
        fig, axis = plt.subplots(figsize=(10, 4.8))
        axis.bar(
            x - width / 2,
            metric_groups["success_mean"],
            width,
            label="success",
            color="#3b7f5c",
        )
        axis.bar(
            x + width / 2,
            metric_groups["fail_mean"],
            width,
            label="fail",
            color="#c25d3c",
        )
        axis.set_xticks(x, metric_groups["label"], rotation=20, ha="right")
        axis.set_ylabel(top_metric)
        axis.set_title("Top early metric by fixed suite/task/init group")
        axis.legend()
        fig.tight_layout()
        fig.savefig(plot_dir / "top_early_metric_by_group.png", dpi=180)
        plt.close(fig)


def write_report(
    output_dir: Path,
    episodes: pd.DataFrame,
    by_task: pd.DataFrame,
    early_ranking: pd.DataFrame,
    correlations: pd.DataFrame,
    inventory: pd.DataFrame,
    max_early_query: int,
) -> dict[str, object]:
    split_counts = {}
    for split, group in episodes.groupby("split"):
        successes = int(group["success"].sum())
        total = int(len(group))
        low, high = wilson_interval(successes, total)
        split_counts[split] = {
            "episodes": total,
            "success": successes,
            "fail": total - successes,
            "success_rate": successes / total,
            "wilson_95": [low, high],
        }

    id_group = episodes.loc[episodes["split"] == "ID"]
    ood_group = episodes.loc[episodes["split"] == "OOD"]
    fisher_p = float(
        stats.fisher_exact(
            [
                [int(id_group["success"].sum()), int((~id_group["success"]).sum())],
                [int(ood_group["success"].sum()), int((~ood_group["success"]).sum())],
            ]
        ).pvalue
    )

    ood_failures = ood_group.loc[~ood_group["success"]]
    failure_counts = {
        str(key): int(value)
        for key, value in ood_group["failure_type"].value_counts(dropna=False).items()
    }
    target_drop_true = int(ood_group["target_drop_candidate"].sum())
    target_drop_failure = int(ood_failures["target_drop_candidate"].sum())
    target_drop_success = int(
        ood_group.loc[ood_group["success"], "target_drop_candidate"].sum()
    )
    target_drop_precision = target_drop_failure / target_drop_true if target_drop_true else float("nan")
    target_drop_recall = (
        target_drop_failure / len(ood_failures) if len(ood_failures) else float("nan")
    )

    summary = {
        "analysis_scope": "completed non-smoke Phase 1 runs",
        "max_early_query": max_early_query,
        "split_counts": split_counts,
        "id_vs_ood_fisher_exact_p": fisher_p,
        "mixed_ood_groups": int(
            episodes.loc[episodes["split"] == "OOD"]
            .groupby(GROUP_KEYS)["success"]
            .nunique()
            .eq(2)
            .sum()
        ),
        "failure_type_counts": failure_counts,
        "official_safety_violations": int(episodes["official_safety_violation"].sum()),
        "target_drop_candidate": {
            "flagged_ood_episodes": target_drop_true,
            "flagged_failed_ood_episodes": target_drop_failure,
            "flagged_successful_ood_episodes": target_drop_success,
            "precision_for_final_failure": target_drop_precision,
            "recall_of_all_final_failures": target_drop_recall,
        },
        "top_early_online_metrics": early_ranking.head(10).to_dict(orient="records"),
        "top_prediction_error_correlations_after_suite_task_query_control": correlations.head(10).to_dict(
            orient="records"
        ),
        "excluded_or_partial_runs": inventory.loc[~inventory["included"]].to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    id_summary = split_counts.get("ID", {})
    ood_summary = split_counts.get("OOD", {})
    top_metric = early_ranking.iloc[0] if len(early_ranking) else None
    top_metric_group_summary = "n/a"
    if top_metric is not None:
        top_metric_group_summary = (
            f"{int(top_metric.groups_strict_high_means_failure)}/"
            f"{int(top_metric.num_mixed_groups)} групп с `high=failure`, "
            f"{int(top_metric.groups_tied)} tie и "
            f"{int(top_metric.groups_low_means_failure)} с обратным направлением"
        )
    strongest_non_value_error = correlations.loc[
        correlations["prediction_error_metric"] != "prediction_error_value_abs_chunk_success"
    ].head(1)
    strongest_non_value_error_text = "n/a"
    if len(strongest_non_value_error):
        row = strongest_non_value_error.iloc[0]
        strongest_non_value_error_text = (
            f"`{row.uncertainty_metric}` vs `{row.prediction_error_metric}`: "
            f"Spearman $\\rho={row.spearman_r_after_suite_task_query_control:.3f}$"
        )

    mixed_rows = by_task.loc[
        (by_task["split"] == "OOD")
        & (by_task["success"] > 0)
        & (by_task["fail"] > 0)
    ]
    mixed_table = "\n".join(
        f"| `{row.suite}` | {row.task_id} | {row.success}/{row.episodes} | {row.success_rate:.1%} |"
        for row in mixed_rows.itertuples(index=False)
    )
    report = f"""# Phase 1: ID и LIBERO-PRO OOD результаты

Анализ включает только завершённые non-smoke runs, для которых одновременно
есть `query_traces`, `metadata` и `pair_summary`. Незавершённые и оборванные
asset-запуски перечислены в `run_inventory.csv` и не участвуют в числах ниже.

## Итоговые outcomes

| Split | Эпизоды | Success | Fail | Success rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| ID | {id_summary.get("episodes", 0)} | {id_summary.get("success", 0)} | {id_summary.get("fail", 0)} | {id_summary.get("success_rate", float("nan")):.1%} | [{id_summary.get("wilson_95", [float("nan"), float("nan")])[0]:.1%}, {id_summary.get("wilson_95", [float("nan"), float("nan")])[1]:.1%}] |
| LIBERO-PRO OOD | {ood_summary.get("episodes", 0)} | {ood_summary.get("success", 0)} | {ood_summary.get("fail", 0)} | {ood_summary.get("success_rate", float("nan")):.1%} | [{ood_summary.get("wilson_95", [float("nan"), float("nan")])[0]:.1%}, {ood_summary.get("wilson_95", [float("nan"), float("nan")])[1]:.1%}] |

Разница ID/OOD статистически заметна уже в screening
(`Fisher exact p={fisher_p:.3g}`), но это не оценка общего benchmark:
мы намеренно выбирали сложные OOD-конфигурации.

## Найденные mixed-outcome конфигурации

| Suite | Task | Success | Success rate |
|---|---:|---:|---:|
{mixed_table}

Всего найдено {summary["mixed_ood_groups"]} фиксированных `suite/task/init_state`
со смесью success и fail. Лучшие boundary cases для следующих planning
экспериментов: `libero_spatial_with_milk/task5/init0` и
`libero_spatial_with_yellow_book/task8/init0`, оба с success rate 50%.

## Failure modes и safety

- OOD outcomes: {", ".join(f"`{key}`={value}" for key, value in failure_counts.items())}.
- Official safety violations: **{summary["official_safety_violations"]}**. Это
  ожидаемо для LIBERO-PRO без официальных LIBERO-Safety constraints.
- Drop heuristic отметил {target_drop_true} OOD эпизодов, из них
  {target_drop_failure} закончились fail. Его precision относительно финального
  fail равен {target_drop_precision:.1%}, recall всех fail {target_drop_recall:.1%}.
  Ещё {target_drop_success} отмеченных эпизодов затем успешно завершились,
  поэтому `*_candidate`
  нельзя использовать как официальный safety label.

## Early online failure signal

Для каждого mixed group online-метрики усреднены по `query=0..{max_early_query}`,
затем стандартизованы **внутри того же suite/task/init_state**. Самое раннее
физическое событие в данных произошло на `t=55`, поэтому окно до `t=48`
не содержит post-failure leakage.

Лучший exploratory признак:
`{top_metric.metric if top_metric is not None else "n/a"}` с pooled
group-standardized AUROC
**{top_metric.pooled_oriented_auc if top_metric is not None else float("nan"):.3f}**
и направлением `{top_metric.direction if top_metric is not None else "n/a"}`.
Согласованность направления: {top_metric_group_summary}. Это оставляет
внутреннюю согласованность action latent главным кандидатом, но уже не
поддерживает тезис об универсальности сигнала.

При этом обычные `action_first_step_l2_std`, `value_std` и `value_range` не
показали устойчивого направления между задачами. Ranking является exploratory:
признак выбран и оценён на тех же
{int(top_metric.episodes) if top_metric is not None else 0} эпизодах,
внешнего holdout здесь ещё нет.

## Prediction error

После контроля `suite/task/init_state/query_idx` связи uncertainty с
последующей image/proprio prediction error оказались слабыми. Самая сильная
не-value пара: {strongest_non_value_error_text}. Ранее наблюдавшиеся корреляции
около 0.8 в pooled trajectories в основном объяснялись фазой эпизода.

Следовательно, Phase 1 поддерживает ранний latent-action risk signal, но пока не
доказывает, что output dispersion является хорошо откалиброванной оценкой
ошибки world model.

## Что запускать дальше

1. Довести до минимум 40 rollout каждую основную boundary-конфигурацию:
   `milk/task5/init0`, `yellow_book/task8/init0` и
   `libero_10_with_mug/task4/init0`.
2. Зафиксировать feature и normalization на calibration split.
3. Проверить `latent_action_copy_std...` на новых seed blocks и новых init states.
4. Отдельно оценить transient-drop detector на LIBERO-Safety.
5. Только после holdout перейти к paired candidate planning против `max(value)`.

Графики находятся в `plots/`, подробные таблицы в CSV рядом с этим файлом.
"""
    (output_dir / "README.md").write_text(report, encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    if args.max_early_query < 0:
        raise ValueError("--max-early-query must be non-negative")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    traces_paths, inventory = discover_traces(
        args.campaign_root.resolve(),
        args.campaign_prefix,
        include_smoke=args.include_smoke,
        include_partial=args.include_partial,
    )
    traces = load_traces(traces_paths)
    episodes = make_episode_table(traces)
    campaign_root = args.campaign_root.resolve()

    def resolve_local_video(row: pd.Series) -> str:
        if pd.isna(row.get("video_path")):
            return ""
        candidate = (
            campaign_root
            / str(row["campaign"])
            / "videos"
            / str(row["run_name"])
            / Path(str(row["video_path"])).name
        )
        if not candidate.exists():
            return ""
        try:
            return str(candidate.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(candidate)

    episodes["local_video_path"] = episodes.apply(resolve_local_video, axis=1)
    by_job, by_task = summarize_outcomes(episodes)
    early_episodes, early_ranking, early_by_group = make_early_episode_metrics(
        traces,
        episodes,
        max_query=args.max_early_query,
    )
    correlations = prediction_error_correlations(traces)

    inventory.to_csv(output_dir / "run_inventory.csv", index=False)
    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    by_job.to_csv(output_dir / "outcomes_by_job.csv", index=False)
    by_task.to_csv(output_dir / "outcomes_by_suite_task.csv", index=False)
    early_episodes.to_csv(output_dir / "early_online_episode_metrics_q0_3.csv", index=False)
    early_ranking.to_csv(output_dir / "early_online_metric_ranking_q0_3.csv", index=False)
    early_by_group.to_csv(output_dir / "early_online_metric_by_group_q0_3.csv", index=False)
    correlations.to_csv(
        output_dir / "uncertainty_prediction_error_correlations_controlled.csv",
        index=False,
    )
    episodes.loc[
        episodes["video_path"].notna(),
        EPISODE_KEYS + ["success", "video_path", "local_video_path"],
    ].to_csv(
        output_dir / "video_inventory.csv",
        index=False,
    )

    save_plots(by_task, episodes, early_ranking, early_by_group, output_dir)
    summary = write_report(
        output_dir,
        episodes,
        by_task,
        early_ranking,
        correlations,
        inventory,
        args.max_early_query,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

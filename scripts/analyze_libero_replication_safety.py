#!/usr/bin/env python3
"""Analyze the denoise-10 planning replication and LIBERO-Safety transfer."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRO_DIR = (
    PROJECT_ROOT
    / "experiments/campaigns/denoise10_replication_20260730/analysis/full_validation"
)
DEFAULT_SAFETY_DIR = (
    PROJECT_ROOT
    / "experiments/campaigns/safety_physical_20260730/analysis/full_validation"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "experiments/campaigns/replication_safety_analysis_20260813"
)

PAIR_KEYS = ["case_id", "suite", "task_id", "init_state_id", "rollout_seed"]
SAFETY_KEYS = [
    "source_run",
    "suite",
    "task_id",
    "init_state_id",
    "rollout_seed",
    "pair_id",
    "rollout_id",
]
ONLINE_METRICS = [
    "value_mean",
    "value_std",
    "value_range",
    "action_first_step_l2_std",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "future_proprio_std_mean",
]
METRIC_LABELS = {
    "value_mean": "mean value",
    "value_std": "value std",
    "value_range": "value range",
    "action_first_step_l2_std": "first-action sample std",
    "latent_action_first_step_copy_l2_std_mean_over_samples": "latent first-action copy std",
    "latent_action_copy_std_mean_mean_over_samples": "latent action-copy std",
    "latent_value_element_std_mean_mean_over_samples": "latent value-element std",
    "future_proprio_std_mean": "future-proprio sample std",
}
CASE_LABELS = {
    "milk_task5_init0_denoise10_replication": "Milk",
    "yellow_task8_init0_denoise10_replication": "Yellow book",
    "long_mug_task4_init0_denoise10_replication": "Long mug",
}


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


def exact_mcnemar_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return float("nan"), float("nan")
    proportion = successes / total
    denominator = 1.0 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total + z**2 / (4 * total**2)
        )
        / denominator
    )
    return center - margin, center + margin


def bootstrap_delta_ci(
    groups: Iterable[np.ndarray],
    *,
    seed: int,
    samples: int,
) -> tuple[float, float]:
    arrays = [np.asarray(group, dtype=float) for group in groups]
    rng = np.random.default_rng(seed)
    values = np.empty(samples, dtype=float)
    for index in range(samples):
        draw = [array[rng.integers(0, len(array), len(array))] for array in arrays]
        values[index] = float(np.concatenate(draw).mean())
    lower, upper = np.quantile(values, [0.025, 0.975])
    return float(lower), float(upper)


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "Нет данных."
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        rendered = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                rendered.append("" if not np.isfinite(value) else f"{value:.3f}")
            else:
                rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def planning_analysis(
    episodes: pd.DataFrame,
    traces: pd.DataFrame,
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, pd.DataFrame | dict[str, float | int]]:
    episodes = episodes.copy()
    episodes["success"] = parse_bool(episodes["success"])
    wide = episodes.pivot_table(
        index=PAIR_KEYS,
        columns="planning_strategy",
        values="success",
        aggfunc="first",
    ).reset_index()
    required = ["max_value", "uncertainty_penalty_action"]
    if wide[required].isna().any().any():
        raise ValueError("Planning campaign is not fully paired")
    wide["delta"] = (
        wide["uncertainty_penalty_action"].astype(int) - wide["max_value"].astype(int)
    )

    rows = []
    for case_id, group in wide.groupby("case_id", sort=True):
        wins = int(group["delta"].eq(1).sum())
        losses = int(group["delta"].eq(-1).sum())
        ci_low, ci_high = bootstrap_delta_ci(
            [group["delta"].to_numpy()],
            seed=seed,
            samples=bootstrap_samples,
        )
        rows.append(
            {
                "case_id": case_id,
                "case": CASE_LABELS.get(case_id, case_id),
                "paired_rollouts": len(group),
                "baseline_successes": int(group["max_value"].sum()),
                "risk_successes": int(group["uncertainty_penalty_action"].sum()),
                "baseline_success_rate": float(group["max_value"].mean()),
                "risk_success_rate": float(group["uncertainty_penalty_action"].mean()),
                "delta_success_rate": float(group["delta"].mean()),
                "delta_ci_low": ci_low,
                "delta_ci_high": ci_high,
                "wins": wins,
                "losses": losses,
                "ties": int(group["delta"].eq(0).sum()),
                "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
            }
        )
    case_results = pd.DataFrame(rows).sort_values("case")

    wins = int(wide["delta"].eq(1).sum())
    losses = int(wide["delta"].eq(-1).sum())
    ci_low, ci_high = bootstrap_delta_ci(
        [group["delta"].to_numpy() for _, group in wide.groupby("case_id")],
        seed=seed + 1,
        samples=bootstrap_samples,
    )
    pooled = {
        "paired_rollouts": int(len(wide)),
        "baseline_successes": int(wide["max_value"].sum()),
        "risk_successes": int(wide["uncertainty_penalty_action"].sum()),
        "baseline_success_rate": float(wide["max_value"].mean()),
        "risk_success_rate": float(wide["uncertainty_penalty_action"].mean()),
        "delta_success_rate": float(wide["delta"].mean()),
        "delta_ci_low": ci_low,
        "delta_ci_high": ci_high,
        "wins": wins,
        "losses": losses,
        "ties": int(wide["delta"].eq(0).sum()),
        "mcnemar_exact_p": exact_mcnemar_p(wins, losses),
    }

    risk_traces = traces.loc[
        traces["planning_strategy"].eq("uncertainty_penalty_action")
    ].copy()
    risk_traces["reranked"] = risk_traces["selected_sample_idx"].ne(
        risk_traces["max_value_sample_idx"]
    )
    risk_traces["selected_value_gap"] = (
        risk_traces["selected_value"] - risk_traces["max_value"]
    )
    selection = (
        risk_traces.groupby("case_id", dropna=False)
        .agg(
            queries=("query_idx", "size"),
            reranked_queries=("reranked", "sum"),
            rerank_rate=("reranked", "mean"),
            selected_value_gap_mean=("selected_value_gap", "mean"),
            selected_risk_z_mean=("selected_risk", "mean"),
        )
        .reset_index()
    )
    selection.insert(
        1,
        "case",
        selection["case_id"].map(CASE_LABELS).fillna(selection["case_id"]),
    )
    pooled_selection = pd.DataFrame(
        [
            {
                "case_id": "pooled",
                "case": "Pooled",
                "queries": len(risk_traces),
                "reranked_queries": int(risk_traces["reranked"].sum()),
                "rerank_rate": float(risk_traces["reranked"].mean()),
                "selected_value_gap_mean": float(risk_traces["selected_value_gap"].mean()),
                "selected_risk_z_mean": float(risk_traces["selected_risk"].mean()),
            }
        ]
    )
    selection = pd.concat([selection, pooled_selection], ignore_index=True)

    baseline_query = traces.loc[
        traces["planning_strategy"].eq("max_value") & traces["query_idx"].le(3)
    ]
    available_metrics = [metric for metric in ONLINE_METRICS if metric in baseline_query]
    early = (
        baseline_query.groupby(PAIR_KEYS, dropna=False)[available_metrics]
        .mean()
        .reset_index()
    )
    outcomes = episodes.loc[
        episodes["planning_strategy"].eq("max_value"), PAIR_KEYS + ["success"]
    ]
    early = outcomes.merge(early, on=PAIR_KEYS, how="inner")
    early["fail"] = ~early["success"]
    predictor_rows = []
    for metric in available_metrics:
        controlled = early.groupby("case_id")[metric].transform(
            lambda values: (values - values.mean()) / (values.std(ddof=0) + 1e-12)
        )
        case_aucs = [
            auc_score(group["fail"], group[metric])
            for _, group in early.groupby("case_id")
        ]
        raw_auc = auc_score(early["fail"], early[metric])
        controlled_auc = auc_score(early["fail"], controlled)
        predictor_rows.append(
            {
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "episodes": len(early),
                "raw_auc_high_predicts_fail": raw_auc,
                "case_controlled_auc_high_predicts_fail": controlled_auc,
                "case_controlled_oriented_auc": max(controlled_auc, 1.0 - controlled_auc),
                "case_auc_min": float(np.nanmin(case_aucs)),
                "case_auc_max": float(np.nanmax(case_aucs)),
            }
        )
    predictors = pd.DataFrame(predictor_rows).sort_values(
        "case_controlled_oriented_auc", ascending=False
    )
    return {
        "pairs": wide,
        "case_results": case_results,
        "pooled": pooled,
        "selection": selection,
        "predictors": predictors,
    }


def safety_analysis(episodes: pd.DataFrame, traces: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    episodes = episodes.copy()
    for column in [
        "success",
        "safe_task_success",
        "official_safety_violation",
        "target_drop_candidate",
        "wrong_object_interaction_candidate",
        "kinematic_deadlock_candidate",
    ]:
        episodes[column] = parse_bool(episodes[column])

    aggregations = {
        "episodes": ("success", "size"),
        "successes": ("success", "sum"),
        "safe_successes": ("safe_task_success", "sum"),
        "violations": ("official_safety_violation", "sum"),
        "mean_final_t": ("final_t", "mean"),
        "mean_goal_progress": ("episode_goal_progress_max", "mean"),
        "mean_target_lift": ("episode_target_lift_max", "mean"),
        "mean_eef_path": ("episode_eef_path_length", "mean"),
    }
    level_results = (
        episodes.groupby(
            ["suite", "task_level", "task_id", "task_description"], dropna=False
        )
        .agg(**aggregations)
        .reset_index()
    )
    level_results["success_rate"] = level_results["successes"] / level_results["episodes"]
    level_results["safe_success_rate"] = (
        level_results["safe_successes"] / level_results["episodes"]
    )
    level_results["violation_rate"] = level_results["violations"] / level_results["episodes"]
    level_results[["violation_ci_low", "violation_ci_high"]] = level_results.apply(
        lambda row: wilson_interval(int(row["violations"]), int(row["episodes"])),
        axis=1,
        result_type="expand",
    )

    suite_results = (
        episodes.groupby("suite", dropna=False)
        .agg(
            **aggregations,
            drop_candidates=("target_drop_candidate", "sum"),
            wrong_object_candidates=("wrong_object_interaction_candidate", "sum"),
            deadlock_candidates=("kinematic_deadlock_candidate", "sum"),
        )
        .reset_index()
    )
    suite_results["success_rate"] = suite_results["successes"] / suite_results["episodes"]
    suite_results["safe_success_rate"] = suite_results["safe_successes"] / suite_results["episodes"]
    suite_results["violation_rate"] = suite_results["violations"] / suite_results["episodes"]
    suite_results[["violation_ci_low", "violation_ci_high"]] = suite_results.apply(
        lambda row: wilson_interval(int(row["violations"]), int(row["episodes"])),
        axis=1,
        result_type="expand",
    )

    value_summary = (
        traces.groupby("suite", dropna=False)
        .agg(
            queries=("query_idx", "size"),
            mean_value=("value_mean", "mean"),
            value_p90=("value_mean", lambda values: values.quantile(0.9)),
            fraction_value_gt_0_9=("value_mean", lambda values: values.gt(0.9).mean()),
            fraction_value_gt_0_99=("value_mean", lambda values: values.gt(0.99).mean()),
            mean_value_std=("value_std", "mean"),
            mean_action_uncertainty=(
                "latent_action_first_step_copy_l2_std_mean_over_samples",
                "mean",
            ),
            mean_future_image_mse=("prediction_error_future_image_mse", "mean"),
            mean_future_proprio_l2=("prediction_error_future_proprio_l2", "mean"),
            official_cost_sum=("observed_official_safety_cost_sum", "sum"),
        )
        .reset_index()
    )

    violations = episodes.loc[episodes["official_safety_violation"]].copy()
    if not violations.empty:
        violations["video_file"] = violations["video_path"].map(
            lambda value: Path(str(value)).name
        )
    violation_columns = [
        "suite",
        "task_level",
        "task_id",
        "rollout_seed",
        "official_safety_violation_t",
        "official_safety_cost_types",
        "final_t",
        "failure_type",
        "video_file",
        "video_num_frames",
    ]
    violations = violations.reindex(columns=violation_columns)

    available_metrics = [metric for metric in ONLINE_METRICS if metric in traces]
    early = (
        traces.loc[traces["query_idx"].le(3)]
        .groupby(SAFETY_KEYS, dropna=False)[available_metrics]
        .mean()
        .reset_index()
    )
    labels = episodes[SAFETY_KEYS + ["official_safety_violation"]]
    early = labels.merge(early, on=SAFETY_KEYS, how="inner")
    predictor_rows = []
    obstacle = early.loc[early["suite"].eq("obstacle_avoidance")]
    for metric in available_metrics:
        all_auc = auc_score(early["official_safety_violation"], early[metric])
        obstacle_auc = auc_score(obstacle["official_safety_violation"], obstacle[metric])
        predictor_rows.append(
            {
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "positive_episodes": int(early["official_safety_violation"].sum()),
                "all_suites_auc_high_predicts_violation": all_auc,
                "obstacle_only_auc_high_predicts_violation": obstacle_auc,
                "obstacle_only_oriented_auc": max(obstacle_auc, 1.0 - obstacle_auc),
                "obstacle_only_direction": "high" if obstacle_auc >= 0.5 else "low",
            }
        )
    predictors = pd.DataFrame(predictor_rows).sort_values(
        "obstacle_only_oriented_auc", ascending=False
    )

    failure_types = (
        episodes.groupby(["suite", "task_level", "failure_type"], dropna=False)
        .size()
        .rename("episodes")
        .reset_index()
    )
    video_summary = {
        "unique_videos": int(episodes["video_path"].nunique()),
        "videos_with_expected_frame_count": int(
            episodes["video_num_frames"].eq(episodes["video_expected_frames"]).sum()
        ),
        "min_video_frames": int(episodes["video_num_frames"].min()),
        "max_video_frames": int(episodes["video_num_frames"].max()),
    }
    return {
        "level_results": level_results,
        "suite_results": suite_results,
        "value_summary": value_summary,
        "violations": violations,
        "predictors": predictors,
        "failure_types": failure_types,
        "video_summary": video_summary,
    }


def save_plots(planning: dict, safety: dict, output_dir: Path) -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    cases = planning["case_results"].copy()
    pooled = planning["pooled"]
    labels = list(cases["case"]) + ["Pooled"]
    baseline = list(cases["baseline_success_rate"]) + [pooled["baseline_success_rate"]]
    risk = list(cases["risk_success_rate"]) + [pooled["risk_success_rate"]]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 4.8))
    left = ax.bar(x - width / 2, baseline, width, label="max(value)", color="#3B6EA8")
    right = ax.bar(
        x + width / 2,
        risk,
        width,
        label="value - action uncertainty",
        color="#D66B4D",
    )
    ax.bar_label(left, fmt="%.2f", padding=3, fontsize=9)
    ax.bar_label(right, fmt="%.2f", padding=3, fontsize=9)
    ax.set_ylabel("Success rate")
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x, labels)
    ax.legend(frameon=False, ncol=2)
    ax.set_title("Denoise-10 paired planning replication")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "planning_replication_success.png", dpi=180)
    plt.close(fig)

    predictors = planning["predictors"].sort_values(
        "case_controlled_oriented_auc", ascending=True
    )
    y = np.arange(len(predictors))
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(
        y - 0.18,
        predictors["raw_auc_high_predicts_fail"],
        height=0.34,
        label="Raw pooled AUROC",
        color="#3B6EA8",
    )
    ax.barh(
        y + 0.18,
        predictors["case_controlled_oriented_auc"],
        height=0.34,
        label="Case-controlled oriented AUROC",
        color="#D6A84D",
    )
    ax.axvline(0.5, color="#333333", linewidth=1, linestyle="--")
    ax.set_yticks(y, predictors["label"])
    ax.set_xlim(0.3, 0.85)
    ax.set_xlabel("AUROC")
    ax.set_title("Early q=0..3 online failure predictors")
    ax.legend(frameon=False)
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "planning_early_predictor_auc.png", dpi=180)
    plt.close(fig)

    suites = safety["suite_results"].copy()
    suites["ordinary_failures"] = suites["episodes"] - suites["violations"] - suites["successes"]
    x = np.arange(len(suites))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, suites["ordinary_failures"], label="Task fail, no official violation", color="#8A96A3")
    ax.bar(
        x,
        suites["violations"],
        bottom=suites["ordinary_failures"],
        label="Official safety violation",
        color="#C94C4C",
    )
    ax.bar(
        x,
        suites["successes"],
        bottom=suites["ordinary_failures"] + suites["violations"],
        label="Task success",
        color="#3B8C6E",
    )
    ax.set_xticks(x, suites["suite"], rotation=15, ha="right")
    ax.set_ylabel("Episodes")
    ax.set_title("LIBERO-Safety outcomes (36 episodes per suite)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "safety_outcomes.png", dpi=180)
    plt.close(fig)

    values = safety["value_summary"].copy()
    x = np.arange(len(values))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, values["mean_value"], width, label="Mean predicted value", color="#3B6EA8")
    ax.bar(
        x + width / 2,
        values["fraction_value_gt_0_9"],
        width,
        label="Fraction of queries with value > 0.9",
        color="#D66B4D",
    )
    ax.set_xticks(x, values["suite"], rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_title("Value overconfidence under zero-shot Safety transfer")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "safety_value_overconfidence.png", dpi=180)
    plt.close(fig)


def write_report(planning: dict, safety: dict, output_dir: Path) -> None:
    cases = planning["case_results"].copy()
    case_table = cases[
        [
            "case",
            "paired_rollouts",
            "baseline_success_rate",
            "risk_success_rate",
            "delta_success_rate",
            "wins",
            "losses",
            "ties",
            "mcnemar_exact_p",
        ]
    ].copy()
    pooled = planning["pooled"]
    safety_episodes = int(safety["suite_results"]["episodes"].sum())
    safety_successes = int(safety["suite_results"]["successes"].sum())
    safety_violations = int(safety["suite_results"]["violations"].sum())
    success_ci = wilson_interval(safety_successes, safety_episodes)
    violation_ci = wilson_interval(safety_violations, safety_episodes)
    predictor_table = planning["predictors"].head(5)[
        [
            "label",
            "raw_auc_high_predicts_fail",
            "case_controlled_auc_high_predicts_fail",
            "case_controlled_oriented_auc",
        ]
    ]
    safety_table = safety["suite_results"][
        [
            "suite",
            "episodes",
            "successes",
            "safe_successes",
            "violations",
            "violation_rate",
            "wrong_object_candidates",
            "drop_candidates",
        ]
    ]
    value_table = safety["value_summary"][
        [
            "suite",
            "mean_value",
            "fraction_value_gt_0_9",
            "fraction_value_gt_0_99",
            "mean_value_std",
        ]
    ]
    lines = [
        "# LIBERO denoise-10 replication и LIBERO-Safety",
        "",
        "Дата анализа: 13 августа 2026 года.",
        "",
        "## Короткий итог",
        "",
        (
            f"На 100 paired seeds стратегия `value - action uncertainty` получила "
            f"{pooled['risk_successes']}/100 success против {pooled['baseline_successes']}/100 "
            f"у `max(value)`: delta **{100 * pooled['delta_success_rate']:+.1f} п.п.** "
            f"(stratified paired bootstrap 95% CI "
            f"[{100 * pooled['delta_ci_low']:+.1f}; {100 * pooled['delta_ci_high']:+.1f}] п.п.; "
            f"McNemar exact p={pooled['mcnemar_exact_p']:.3f})."
        ),
        "",
        (
            "Это promising, но не подтверждённое улучшение: 14 baseline failures были "
            "исправлены, 10 baseline successes были потеряны, а 76 outcomes совпали. "
            "Эффект меняет знак между задачами."
        ),
        "",
        (
            f"В LIBERO-Safety получено {safety_successes}/{safety_episodes} task success "
            f"(95% Wilson upper bound {100 * success_ci[1]:.1f}%) и "
            f"{safety_violations}/{safety_episodes} official violations "
            f"({100 * safety_violations / safety_episodes:.1f}%, 95% CI "
            f"[{100 * violation_ci[0]:.1f}; {100 * violation_ci[1]:.1f}]%). "
            "Низкая violation rate здесь не означает безопасную полезную policy: safe success тоже равен нулю."
        ),
        "",
        "## 1. Paired planning replication",
        "",
        "Фиксированная формула:",
        "",
        r"\[n^*=\arg\max_n\left[z(V_n)-z(u^{A,\mathrm{first}}_n)\right],\qquad N=4,\ H=16,\ D_A=10.\]",
        "",
        markdown_table(case_table),
        "",
        "![Planning success](plots/planning_replication_success.png)",
        "",
        "Стратегия улучшила milk и yellow-book, но ухудшила long-mug. Поэтому один "
        "глобальный коэффициент не является универсальным planning rule.",
        "",
        "### Что реально изменил penalty",
        "",
        markdown_table(
            planning["selection"][["case", "queries", "rerank_rate", "selected_value_gap_mean"]]
        ),
        "",
        "Penalty выбрал не max-value candidate в 42.9% query. Средняя потеря raw value "
        "при этом мала, но накопленные действия изменили outcome только в 24% paired seeds.",
        "",
        "## 2. Можно ли заранее предсказать task failure",
        "",
        markdown_table(predictor_table),
        "",
        "![Early predictors](plots/planning_early_predictor_auc.png)",
        "",
        "Raw pooled AUROC завышен различиями между задачами. Например, latent first-action "
        "copy std имеет raw AUROC около 0.77, но после z-нормализации внутри каждого case "
        "остаётся около 0.59. Следовательно, это пока слабый task-conditioned сигнал, а не "
        "универсальный fail detector.",
        "",
        "`prediction_error_*` сюда намеренно не включены: они становятся известны только "
        "после исполнения chunk и не могут выбирать действие в текущем query.",
        "",
        "## 3. LIBERO-Safety zero-shot transfer",
        "",
        markdown_table(safety_table),
        "",
        "![Safety outcomes](plots/safety_outcomes.png)",
        "",
        "Все четыре official violations имеют тип `checkcontact` и произошли только в "
        "`obstacle_avoidance`: два на L1 и два на L2. Четыре positive examples слишком "
        "малы для надёжного обучения или сравнения safety detector.",
        "",
        "Exploratory-анализ `q=0..3` не поддерживает простую гипотезу «больше "
        "uncertainty — больше риска»: внутри `obstacle_avoidance` низкий "
        "first-action sample std отделяет четыре violations с oriented AUROC 0.906. "
        "При четырёх positives это лишь указание на возможные confidently-wrong "
        "действия, а не валидированный detector.",
        "",
        "Четыре полных видео до момента автоматической остановки лежат в "
        "[`final_results_media/safety_violations_20260730`](../../final_results_media/safety_violations_20260730/README.md).",
        "",
        "### Value overconfidence",
        "",
        markdown_table(value_table),
        "",
        "![Safety value](plots/safety_value_overconfidence.png)",
        "",
        "Самый сильный результат Safety-части — не детекция collision, а некалиброванный "
        "value. На `affordance` средний value равен примерно 0.91 и 79% query имеют "
        "value > 0.9 при 0/36 success. Малый `value_std` не защищает от согласованной "
        "ошибки всех samples.",
        "",
        "## 4. Выводы",
        "",
        "1. Action uncertainty полезна как дополнительный ranking signal, но фиксированный penalty не переносится одинаково между tasks.",
        "2. Denoise-10 pilot частично реплицирован по направлению pooled effect (+4 п.п.), но статистически не подтверждён.",
        "3. Следующий метод должен быть task/phase-aware или gated: сохранять max(value) по умолчанию и включать penalty только при калиброванном trigger.",
        "4. Для fail detector обязательна case-controlled оценка; pooled AUROC без такого контроля вводит в заблуждение.",
        "5. LIBERO-Safety показывает severe zero-shot task failure и value overconfidence. Violation rate надо всегда сообщать вместе с safe success.",
        "6. Для проверки uncertainty-aware safety planning нужны дополнительные rollouts на `obstacle_avoidance` L1/L2 и paired baseline/risk-aware strategies; текущих четырёх violations недостаточно.",
        "",
        "## Артефакты",
        "",
        "- `pro_case_results.csv` — paired outcomes и exact tests по задачам;",
        "- `pro_pooled_result.csv` — pooled confirmatory result;",
        "- `pro_early_fail_predictors.csv` — raw и case-controlled AUROC;",
        "- `safety_suite_level_results.csv` — task/safety outcomes L0-L2;",
        "- `safety_violation_episodes.csv` — четыре official violations и видео;",
        "- `safety_early_violation_predictors.csv` — exploratory, только 4 positives.",
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pro-analysis-dir", type=Path, default=DEFAULT_PRO_DIR)
    parser.add_argument("--safety-analysis-dir", type=Path, default=DEFAULT_SAFETY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-samples", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260813)
    args = parser.parse_args()

    pro_episodes = pd.read_csv(args.pro_analysis_dir / "episode_outcomes.csv")
    pro_traces = pd.read_parquet(args.pro_analysis_dir / "all_query_traces.parquet")
    safety_episodes = pd.read_csv(args.safety_analysis_dir / "episode_outcomes.csv")
    safety_traces = pd.read_parquet(args.safety_analysis_dir / "all_query_traces.parquet")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    planning = planning_analysis(
        pro_episodes,
        pro_traces,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    safety = safety_analysis(safety_episodes, safety_traces)

    planning["case_results"].to_csv(output_dir / "pro_case_results.csv", index=False)
    pd.DataFrame([planning["pooled"]]).to_csv(
        output_dir / "pro_pooled_result.csv", index=False
    )
    planning["selection"].to_csv(output_dir / "pro_selection_behavior.csv", index=False)
    planning["predictors"].to_csv(output_dir / "pro_early_fail_predictors.csv", index=False)
    planning["pairs"].to_csv(output_dir / "pro_paired_seed_outcomes.csv", index=False)
    safety["suite_results"].to_csv(output_dir / "safety_suite_results.csv", index=False)
    safety["level_results"].to_csv(output_dir / "safety_suite_level_results.csv", index=False)
    safety["value_summary"].to_csv(output_dir / "safety_value_summary.csv", index=False)
    safety["violations"].to_csv(output_dir / "safety_violation_episodes.csv", index=False)
    safety["predictors"].to_csv(
        output_dir / "safety_early_violation_predictors.csv", index=False
    )
    safety["failure_types"].to_csv(output_dir / "safety_failure_types.csv", index=False)

    save_plots(planning, safety, output_dir)
    write_report(planning, safety, output_dir)
    safety_episode_count = int(safety["suite_results"]["episodes"].sum())
    safety_success_count = int(safety["suite_results"]["successes"].sum())
    safety_violation_count = int(safety["suite_results"]["violations"].sum())
    safety_success_ci = wilson_interval(safety_success_count, safety_episode_count)
    safety_violation_ci = wilson_interval(safety_violation_count, safety_episode_count)
    summary = {
        "planning": planning["pooled"],
        "safety": {
            "episodes": safety_episode_count,
            "successes": safety_success_count,
            "safe_successes": int(safety["suite_results"]["safe_successes"].sum()),
            "success_rate_ci_low": safety_success_ci[0],
            "success_rate_ci_high": safety_success_ci[1],
            "official_violations": safety_violation_count,
            "official_violation_rate": safety_violation_count / safety_episode_count,
            "official_violation_rate_ci_low": safety_violation_ci[0],
            "official_violation_rate_ci_high": safety_violation_ci[1],
            **safety["video_summary"],
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"Analysis: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

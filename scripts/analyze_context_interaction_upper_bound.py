#!/usr/bin/env python3
"""Privileged context-interaction upper bound for query-4 feedback value."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_object_contact_vof_development import model_feature_families
    from analyze_signed_vof_new_task_holdout import clustered_interval
    from invariant_cate_router import (
        fit_robust_scaler,
        numeric_matrix,
        transform_values,
        validate_feature_names,
    )
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_object_contact_vof_development import model_feature_families
    from scripts.analyze_signed_vof_new_task_holdout import clustered_interval
    from scripts.invariant_cate_router import (
        fit_robust_scaler,
        numeric_matrix,
        transform_values,
        validate_feature_names,
    )


ALPHAS = (0.01, 0.1, 1.0, 10.0)
BUDGETS = (0.10, 0.20, 0.30)
PRIMARY_BUDGET = 0.20
QUERY_COST = 0.025
TRANSFER_SCHEMES = ("leave_one_task", "leave_one_level", "leave_one_cell")
ALL_SCHEMES = TRANSFER_SCHEMES + ("within_cell_grouped5",)
TARGET_VARIANTS = (
    "direct_success",
    "direct_terminal_utility",
    "direct_grounded",
    "ridge_potential_success",
)
EXPECTED_ROWS = 640

# Chosen from physical meaning before fitting this upper bound, not from outcome
# correlation. They cover boundary continuity, grasp state, candidate dispersion
# and predicted motion without expanding all 80 relative variables.
CORE_DYNAMIC_FEATURES = (
    "f_action_boundary_xyz_jump",
    "f_action_gripper_boundary_change",
    "f_action_gripper_transition_count",
    "f_action_prefix_xyz_path",
    "f_action_tail_xyz_path",
    "f_action_tail_xyz_straightness",
    "f_core_action_first_step_l2_std",
    "f_core_action_pairwise_l2_mean",
    "f_core_future_proprio_std_mean",
    "f_core_latent_action_across_seed_std_mean",
    "f_core_latent_future_proprio_across_seed_std_mean",
    "f_core_latent_value_across_seed_std_mean",
    "f_core_planning_predicted_proprio_error",
    "f_core_value_range",
    "f_current_gripper_mean",
    "f_future_gripper_delta_norm",
    "f_future_position_delta_norm",
    "f_future_position_delta_z",
    "f_pool_future_position_spread",
    "f_pool_selected_position_deviation",
    "f_pool_selected_value",
    "f_pool_value_margin",
)

OBJECT_SLOPE_FEATURES = (
    "f_obj_agent_current_target_global_similarity",
    "f_obj_agent_current_goal_global_similarity",
    "f_obj_agent_selected_delta_target_global_similarity",
    "f_obj_agent_selected_delta_goal_global_similarity",
    "f_obj_agent_selected_rank_target_global_similarity",
    "f_obj_agent_candidate_delta_std_target_global_similarity",
    "f_obj_agent_candidate_delta_range_target_global_similarity",
    "f_obj_wrist_current_target_global_similarity",
    "f_obj_wrist_current_goal_global_similarity",
    "f_obj_wrist_selected_delta_target_global_similarity",
    "f_obj_wrist_selected_delta_goal_global_similarity",
    "f_obj_wrist_selected_rank_target_global_similarity",
    "f_obj_wrist_candidate_delta_std_target_global_similarity",
    "f_obj_wrist_candidate_delta_range_target_global_similarity",
)

INTERACTION_FAMILIES = (
    "oracle_context_only",
    "relative_oracle_interactions",
    "relative_oracle_dynamic_slopes",
    "relative_object_oracle_dynamic_slopes",
)


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _product_name(left: str, right: str, prefix: str) -> str:
    return f"{prefix}_{_slug(left.removeprefix('f_'))}__{_slug(right.removeprefix('f_'))}"


def append_context_interactions(
    source: pd.DataFrame,
) -> tuple[pd.DataFrame, Mapping[str, tuple[str, ...]]]:
    """Create the frozen oracle context basis and context-specific slopes."""

    required = {
        "task_id",
        "position_level",
        "phase_at_snapshot",
        "cell_key",
        "f_context_direction_x",
        "f_context_magnitude",
    }
    missing = sorted(required - set(source.columns))
    if missing:
        raise ValueError(f"Missing context columns: {missing}")

    base_columns: dict[str, pd.Series] = {}
    task_columns: list[str] = []
    for task_id in sorted(source["task_id"].astype(int).unique()):
        name = f"f_oracle_task_{task_id}"
        base_columns[name] = source["task_id"].astype(int).eq(task_id).astype(float)
        task_columns.append(name)

    level_columns: list[str] = []
    for level in sorted(source["position_level"].astype(str).unique()):
        name = f"f_oracle_level_{_slug(level)}"
        base_columns[name] = source["position_level"].astype(str).eq(level).astype(float)
        level_columns.append(name)

    phase_columns: list[str] = []
    for phase in ("approach", "grasp", "transport"):
        name = f"f_oracle_phase_{phase}"
        base_columns[name] = (
            source["phase_at_snapshot"].astype(str).str.lower().eq(phase).astype(float)
        )
        phase_columns.append(name)

    direction = "f_oracle_direction_x"
    magnitude = "f_oracle_magnitude"
    base_columns[direction] = pd.to_numeric(
        source["f_context_direction_x"], errors="coerce"
    )
    base_columns[magnitude] = pd.to_numeric(
        source["f_context_magnitude"], errors="coerce"
    )
    frame = pd.concat([source.copy(), pd.DataFrame(base_columns)], axis=1)
    z_columns = [direction, magnitude, *phase_columns]
    additive = [*task_columns, *level_columns, *z_columns]

    pairwise = list(additive)
    pair_columns: dict[str, pd.Series] = {}

    def add_pair(left: str, right: str, names: list[str]) -> None:
        name = _product_name(left, right, "f_oracle_cross")
        if name not in pair_columns:
            pair_columns[name] = pd.to_numeric(
                frame[left], errors="coerce"
            ) * pd.to_numeric(frame[right], errors="coerce")
        names.append(name)

    for task in task_columns:
        for context in z_columns:
            add_pair(task, context, pairwise)
    for level in level_columns:
        for phase in phase_columns:
            add_pair(level, phase, pairwise)
    add_pair(direction, magnitude, pairwise)
    for phase in phase_columns:
        add_pair(direction, phase, pairwise)
        add_pair(magnitude, phase, pairwise)

    for cell in sorted(source["cell_key"].astype(str).unique()):
        name = f"f_oracle_cell_{_slug(cell)}"
        pair_columns[name] = source["cell_key"].astype(str).eq(cell).astype(float)
        pairwise.append(name)
    frame = pd.concat([frame, pd.DataFrame(pair_columns)], axis=1)

    dynamic_slopes: list[str] = []
    missing_dynamic = sorted(set(CORE_DYNAMIC_FEATURES) - set(frame.columns))
    if missing_dynamic:
        raise ValueError(f"Missing frozen dynamic features: {missing_dynamic}")
    missing_object = sorted(set(OBJECT_SLOPE_FEATURES) - set(frame.columns))
    if missing_object:
        raise ValueError(f"Missing frozen object features: {missing_object}")
    slope_columns: dict[str, pd.Series] = {}

    def add_slope(left: str, right: str, names: list[str]) -> None:
        name = _product_name(left, right, "f_oracle_slope")
        if name not in slope_columns:
            slope_columns[name] = pd.to_numeric(
                frame[left], errors="coerce"
            ) * pd.to_numeric(frame[right], errors="coerce")
        names.append(name)

    for feature in CORE_DYNAMIC_FEATURES:
        for context in z_columns:
            add_slope(feature, context, dynamic_slopes)

    object_slopes: list[str] = []
    for feature in OBJECT_SLOPE_FEATURES:
        for context in z_columns:
            add_slope(feature, context, object_slopes)
    frame = pd.concat([frame, pd.DataFrame(slope_columns)], axis=1)

    groups = {
        "additive": tuple(dict.fromkeys(additive)),
        "pairwise": tuple(dict.fromkeys(pairwise)),
        "dynamic_slopes": tuple(dict.fromkeys(dynamic_slopes)),
        "object_slopes": tuple(dict.fromkeys(object_slopes)),
        "z": tuple(z_columns),
    }
    for names in groups.values():
        validate_feature_names(names)
    return frame, groups


def upper_bound_feature_families(
    frame: pd.DataFrame, context: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    base = model_feature_families(frame)
    relative = list(base["relative"][0])
    object_global = [
        column
        for column in base["relative_object_global"][0]
        if column.startswith("f_obj_")
    ]
    pairwise = list(context["pairwise"])
    families = {
        "relative_control": tuple(relative),
        "oracle_context_only": tuple(pairwise),
        "relative_oracle_additive": tuple(relative + list(context["additive"])),
        "relative_oracle_interactions": tuple(relative + pairwise),
        "relative_oracle_dynamic_slopes": tuple(
            relative + pairwise + list(context["dynamic_slopes"])
        ),
        "relative_object_oracle_dynamic_slopes": tuple(
            relative
            + object_global
            + pairwise
            + list(context["dynamic_slopes"])
            + list(context["object_slopes"])
        ),
    }
    result = {name: tuple(dict.fromkeys(features)) for name, features in families.items()}
    for features in result.values():
        validate_feature_names(features)
    return result


def within_cell_grouped_folds(frame: pd.DataFrame, folds: int = 5) -> pd.Series:
    if folds < 2:
        raise ValueError("folds must be at least two")
    assignments: dict[str, str] = {}
    groups = frame[["cell_key", "independent_group"]].drop_duplicates()
    for cell, part in groups.groupby("cell_key", sort=True):
        names = sorted(part["independent_group"].astype(str))
        if len(names) < folds:
            raise ValueError(f"Cell {cell} has only {len(names)} independent groups")
        for index, name in enumerate(names):
            assignments[name] = f"fold{index % folds}"
    labels = frame["independent_group"].astype(str).map(assignments)
    if labels.isna().any():
        raise ValueError("Missing grouped fold assignment")
    return labels


def fold_labels(frame: pd.DataFrame, scheme: str) -> pd.Series:
    if scheme == "leave_one_task":
        return "task" + frame["task_id"].astype(int).astype(str)
    if scheme == "leave_one_level":
        return frame["position_level"].astype(str)
    if scheme == "leave_one_cell":
        return frame["cell_key"].astype(str)
    if scheme == "within_cell_grouped5":
        return within_cell_grouped_folds(frame)
    raise ValueError(f"Unknown split scheme: {scheme}")


def ridge_path_predict(
    train: np.ndarray,
    target: np.ndarray,
    test: np.ndarray,
    alphas: Sequence[float] = ALPHAS,
) -> dict[float, np.ndarray]:
    """Fit an intercept plus a ridge path using one symmetric decomposition."""

    train = np.asarray(train, dtype=float)
    target = np.asarray(target, dtype=float)
    test = np.asarray(test, dtype=float)
    if target.ndim == 1:
        target = target[:, None]
    if len(train) != len(target):
        raise ValueError("Feature and target lengths differ")
    x_mean = train.mean(axis=0)
    y_mean = target.mean(axis=0)
    x_centered = train - x_mean
    y_centered = target - y_mean

    if train.shape[1] <= len(train):
        gram = x_centered.T @ x_centered
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        rhs = eigenvectors.T @ (x_centered.T @ y_centered)

        def weights(alpha: float) -> np.ndarray:
            return eigenvectors @ (rhs / (np.maximum(eigenvalues, 0.0)[:, None] + alpha))

    else:
        gram = x_centered @ x_centered.T
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        rhs = eigenvectors.T @ y_centered

        def weights(alpha: float) -> np.ndarray:
            dual = eigenvectors @ (
                rhs / (np.maximum(eigenvalues, 0.0)[:, None] + alpha)
            )
            return x_centered.T @ dual

    return {
        float(alpha): y_mean + (test - x_mean) @ weights(float(alpha))
        for alpha in alphas
    }


def cross_fitted_scores(
    frame: pd.DataFrame,
    features: Sequence[str],
    scheme: str,
) -> dict[tuple[str, float], np.ndarray]:
    matrix = numeric_matrix(frame, features)
    labels = fold_labels(frame, scheme)
    target_names = [
        "direct_success",
        "direct_terminal_utility",
        "direct_grounded",
        "commit_success",
        "feedback_success",
    ]
    targets = frame[target_names].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(targets).all():
        raise ValueError("Upper-bound targets contain non-finite values")
    predictions = {
        (target, float(alpha)): np.full(len(frame), np.nan)
        for target in TARGET_VARIANTS
        for alpha in ALPHAS
    }
    for fold in sorted(labels.unique()):
        test_mask = labels.eq(fold).to_numpy()
        train_mask = ~test_mask
        scaler = fit_robust_scaler(matrix[train_mask])
        x_train = transform_values(matrix[train_mask], scaler)
        x_test = transform_values(matrix[test_mask], scaler)
        path = ridge_path_predict(x_train, targets[train_mask], x_test)
        for alpha, values in path.items():
            predictions[("direct_success", alpha)][test_mask] = values[:, 0]
            predictions[("direct_terminal_utility", alpha)][test_mask] = values[:, 1]
            predictions[("direct_grounded", alpha)][test_mask] = values[:, 2]
            commit = np.clip(values[:, 3], 0.0, 1.0)
            feedback = np.clip(values[:, 4], 0.0, 1.0)
            predictions[("ridge_potential_success", alpha)][test_mask] = (
                feedback - commit
            )
    for key, values in predictions.items():
        if not np.isfinite(values).all():
            raise ValueError(f"Non-finite OOF predictions for {scheme}/{key}")
    return predictions


def _safe_spearman(target: np.ndarray, score: np.ndarray) -> float:
    target = np.asarray(target, dtype=float)
    score = np.asarray(score, dtype=float)
    if len(target) < 3 or np.ptp(target) <= 1e-12 or np.ptp(score) <= 1e-12:
        return float("nan")
    return float(spearmanr(target, score).statistic)


def top_budget_mask(score: np.ndarray, budget: float) -> np.ndarray:
    count = max(1, int(math.ceil(len(score) * float(budget))))
    order = np.argsort(np.asarray(score, dtype=float), kind="stable")
    selected = np.zeros(len(score), dtype=bool)
    selected[order[-count:]] = True
    return selected


def evaluate_score(
    frame: pd.DataFrame, score: np.ndarray, budget: float
) -> tuple[dict[str, Any], np.ndarray, pd.DataFrame]:
    effect = frame["terminal_effect"].to_numpy(float)
    query = top_budget_mask(score, budget)
    contribution = query.astype(float) * (effect - QUERY_COST)
    discordant = effect != 0
    auc = (
        float(binary_auc(effect[discordant] > 0, np.asarray(score)[discordant]))
        if discordant.any()
        else float("nan")
    )
    cell_gain = []
    for indices in frame.groupby("cell_key", sort=True).indices.values():
        cell_gain.append(float(contribution[np.asarray(indices, dtype=int)].mean()))

    order = np.argsort(np.asarray(score), kind="stable")
    bins = np.empty(len(frame), dtype=int)
    for quintile, indices in enumerate(np.array_split(order, 5)):
        bins[indices] = quintile
    quintiles = (
        pd.DataFrame({"quintile": bins, "effect": effect, "score": score})
        .groupby("quintile", sort=True)
        .agg(states=("effect", "size"), mean_effect=("effect", "mean"), mean_score=("score", "mean"))
        .reset_index()
    )
    row = {
        "budget": float(budget),
        "query_rate": float(query.mean()),
        "raw_gain": float(np.mean(query * effect)),
        "adjusted_gain": float(contribution.mean()),
        "rescues": int(np.sum(query & (effect > 0))),
        "harms": int(np.sum(query & (effect < 0))),
        "rescue_vs_harm_auc": auc,
        "effect_spearman": _safe_spearman(effect, score),
        "worst_cell_adjusted_gain": float(min(cell_gain)),
        "quintile_monotonic_rho": _safe_spearman(
            quintiles["quintile"].to_numpy(float),
            quintiles["mean_effect"].to_numpy(float),
        ),
        "quintile_top_minus_bottom": float(
            quintiles.iloc[-1]["mean_effect"] - quintiles.iloc[0]["mean_effect"]
        ),
    }
    return row, query, quintiles


def combine_primary_results(results: pd.DataFrame) -> pd.DataFrame:
    keys = ["family", "feature_count", "target_variant", "alpha"]
    metrics = [
        "adjusted_gain",
        "raw_gain",
        "rescues",
        "harms",
        "rescue_vs_harm_auc",
        "effect_spearman",
        "worst_cell_adjusted_gain",
        "quintile_monotonic_rho",
        "quintile_top_minus_bottom",
    ]
    primary = results.loc[np.isclose(results["budget"], PRIMARY_BUDGET)]
    merged: pd.DataFrame | None = None
    for scheme in ALL_SCHEMES:
        part = primary.loc[primary["scheme"].eq(scheme), keys + metrics].copy()
        part = part.rename(
            columns={metric: f"{scheme}__{metric}" for metric in metrics}
        )
        merged = part if merged is None else merged.merge(part, on=keys, validate="one_to_one")
    assert merged is not None
    merged["min_transfer_adjusted_gain"] = merged[
        [f"{scheme}__adjusted_gain" for scheme in TRANSFER_SCHEMES]
    ].min(axis=1)
    merged["min_transfer_auc"] = merged[
        [f"{scheme}__rescue_vs_harm_auc" for scheme in TRANSFER_SCHEMES]
    ].min(axis=1)
    merged["min_transfer_worst_cell"] = merged[
        [f"{scheme}__worst_cell_adjusted_gain" for scheme in TRANSFER_SCHEMES]
    ].min(axis=1)
    merged["min_transfer_monotonic_rho"] = merged[
        [f"{scheme}__quintile_monotonic_rho" for scheme in TRANSFER_SCHEMES]
    ].min(axis=1)
    return merged.sort_values(
        ["min_transfer_adjusted_gain", "min_transfer_auc", "min_transfer_monotonic_rho"],
        ascending=False,
    ).reset_index(drop=True)


def _row_payload(row: pd.Series) -> dict[str, Any]:
    payload = row.to_dict()
    return {
        str(key): (value.item() if isinstance(value, np.generic) else value)
        for key, value in payload.items()
    }


def select_and_decide(combined: pd.DataFrame) -> dict[str, Any]:
    control = combined.loc[combined["family"].eq("relative_control")].iloc[0]
    context = combined.loc[combined["family"].isin(INTERACTION_FAMILIES)].iloc[0]
    checks = {
        "improves_relative_worst_transfer": float(context["min_transfer_adjusted_gain"])
        > float(control["min_transfer_adjusted_gain"]),
        "positive_adjusted_gain_all_transfer_splits": all(
            float(context[f"{scheme}__adjusted_gain"]) > 0
            for scheme in TRANSFER_SCHEMES
        ),
        "nonnegative_worst_cell_all_transfer_splits": all(
            float(context[f"{scheme}__worst_cell_adjusted_gain"]) >= 0
            for scheme in TRANSFER_SCHEMES
        ),
        "monotonic_quintiles_all_transfer_splits": all(
            float(context[f"{scheme}__quintile_monotonic_rho"]) >= 0.5
            for scheme in TRANSFER_SCHEMES
        ),
        "auc_at_least_0p60_all_transfer_splits": all(
            float(context[f"{scheme}__rescue_vs_harm_auc"]) >= 0.60
            for scheme in TRANSFER_SCHEMES
        ),
        "positive_within_cell_grouped_gain": float(
            context["within_cell_grouped5__adjusted_gain"]
        )
        > 0,
    }
    passed = all(checks.values())
    return {
        "relative_control": _row_payload(control),
        "best_interaction_upper_bound": _row_payload(context),
        "checks": checks,
        "gate_passed": passed,
        "decision": (
            "build_observable_context_estimator" if passed else "pivot_to_recovery_abstention"
        ),
        "warning": "Exploratory non-deployable analysis on opened outcomes.",
    }


def cluster_intervals(
    frame: pd.DataFrame,
    scores: Mapping[tuple[str, str, float, str], np.ndarray],
    decision: Mapping[str, Any],
    *,
    repetitions: int,
) -> pd.DataFrame:
    configs = {
        "relative_control": decision["relative_control"],
        "best_interaction_upper_bound": decision["best_interaction_upper_bound"],
    }
    rows = []
    effect = frame["terminal_effect"].to_numpy(float)
    control_contributions: dict[str, np.ndarray] = {}
    for role, config in configs.items():
        for scheme in ALL_SCHEMES:
            key = (
                str(config["family"]),
                str(config["target_variant"]),
                float(config["alpha"]),
                scheme,
            )
            query = top_budget_mask(scores[key], PRIMARY_BUDGET)
            contribution = query.astype(float) * (effect - QUERY_COST)
            low, high = clustered_interval(
                frame, contribution, repetitions=repetitions, seed=8100 + len(rows)
            )
            row = {
                "role": role,
                "scheme": scheme,
                "adjusted_gain": float(contribution.mean()),
                "ci_low": low,
                "ci_high": high,
            }
            if role == "relative_control":
                control_contributions[scheme] = contribution
                row.update(
                    {
                        "gain_vs_relative": 0.0,
                        "gain_vs_relative_ci_low": 0.0,
                        "gain_vs_relative_ci_high": 0.0,
                    }
                )
            else:
                difference = contribution - control_contributions[scheme]
                diff_low, diff_high = clustered_interval(
                    frame,
                    difference,
                    repetitions=repetitions,
                    seed=9100 + len(rows),
                )
                row.update(
                    {
                        "gain_vs_relative": float(difference.mean()),
                        "gain_vs_relative_ci_low": diff_low,
                        "gain_vs_relative_ci_high": diff_high,
                    }
                )
            rows.append(row)
    return pd.DataFrame(rows)


def run_analysis(
    frame: pd.DataFrame, *, bootstrap_repetitions: int
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    enriched, context = append_context_interactions(frame)
    families = upper_bound_feature_families(enriched, context)
    result_rows: list[dict[str, Any]] = []
    prediction_rows: list[pd.DataFrame] = []
    quintile_rows: list[pd.DataFrame] = []
    score_map: dict[tuple[str, str, float, str], np.ndarray] = {}

    for family, features in families.items():
        print(f"[P2d] family={family} features={len(features)}", flush=True)
        for scheme in ALL_SCHEMES:
            print(f"[P2d]   scheme={scheme}", flush=True)
            predictions = cross_fitted_scores(enriched, features, scheme)
            for (target_variant, alpha), score in predictions.items():
                score_key = (family, target_variant, float(alpha), scheme)
                score_map[score_key] = score
                long = pd.DataFrame(
                    {
                        "row_uid": enriched["row_uid"].astype(str),
                        "family": family,
                        "feature_count": len(features),
                        "target_variant": target_variant,
                        "alpha": float(alpha),
                        "scheme": scheme,
                        "score": score,
                        "terminal_effect": enriched["terminal_effect"].to_numpy(int),
                    }
                )
                for budget in BUDGETS:
                    metrics, query, quintiles = evaluate_score(enriched, score, budget)
                    result_rows.append(
                        {
                            "family": family,
                            "feature_count": len(features),
                            "target_variant": target_variant,
                            "alpha": float(alpha),
                            "scheme": scheme,
                            **metrics,
                        }
                    )
                    long[f"query_{int(100 * budget)}"] = query
                    quintiles = quintiles.assign(
                        family=family,
                        feature_count=len(features),
                        target_variant=target_variant,
                        alpha=float(alpha),
                        scheme=scheme,
                        budget=float(budget),
                    )
                    quintile_rows.append(quintiles)
                prediction_rows.append(long)

    results = pd.DataFrame(result_rows)
    combined = combine_primary_results(results)
    decision = select_and_decide(combined)
    intervals = cluster_intervals(
        enriched,
        score_map,
        decision,
        repetitions=bootstrap_repetitions,
    )
    predictions = pd.concat(prediction_rows, ignore_index=True)
    quintiles = pd.concat(quintile_rows, ignore_index=True)
    return results, combined, predictions, quintiles, intervals, decision


def _config_label(config: Mapping[str, Any]) -> str:
    return f"{config['family']} / {config['target_variant']} / a={config['alpha']:g}"


def plot_summary(
    combined: pd.DataFrame,
    results: pd.DataFrame,
    quintiles: pd.DataFrame,
    decision: Mapping[str, Any],
    output: Path,
) -> None:
    control = decision["relative_control"]
    context = decision["best_interaction_upper_bound"]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)

    top = combined.head(10).iloc[::-1]
    labels = [
        f"{row.family}\n{row.target_variant}, a={row.alpha:g}"
        for row in top.itertuples(index=False)
    ]
    axes[0, 0].barh(labels, 100 * top["min_transfer_adjusted_gain"], color="#356f95")
    axes[0, 0].axvline(0, color="black", linewidth=0.8)
    axes[0, 0].set_xlabel("Worst transfer adjusted gain (pp)")
    axes[0, 0].set_title("Model ranking at 20% query budget")

    x = np.arange(len(ALL_SCHEMES))
    for offset, (label, config, color) in enumerate(
        (("relative", control, "#7b8794"), ("context upper bound", context, "#bb4d3f"))
    ):
        values = [100 * float(config[f"{scheme}__adjusted_gain"]) for scheme in ALL_SCHEMES]
        axes[0, 1].bar(x + (offset - 0.5) * 0.34, values, 0.34, label=label, color=color)
    axes[0, 1].axhline(0, color="black", linewidth=0.8)
    axes[0, 1].set_xticks(x, ["task", "level", "cell", "within-cell"])
    axes[0, 1].set_ylabel("Adjusted gain (pp)")
    axes[0, 1].set_title("Transfer versus interpolation")
    axes[0, 1].legend()

    selected_q = quintiles.loc[
        quintiles["family"].eq(context["family"])
        & quintiles["target_variant"].eq(context["target_variant"])
        & np.isclose(quintiles["alpha"], float(context["alpha"]))
        & np.isclose(quintiles["budget"], PRIMARY_BUDGET)
    ]
    for scheme, group in selected_q.groupby("scheme", sort=True):
        axes[1, 0].plot(group["quintile"], group["mean_effect"], marker="o", label=scheme)
    axes[1, 0].axhline(0, color="black", linewidth=0.8)
    axes[1, 0].set_xlabel("Predicted-score quintile")
    axes[1, 0].set_ylabel("Observed mean feedback effect")
    axes[1, 0].set_title("Upper-bound score calibration")
    axes[1, 0].legend(fontsize=8)

    sensitivity = results.loc[
        results["family"].eq(context["family"])
        & results["target_variant"].eq(context["target_variant"])
        & np.isclose(results["alpha"], float(context["alpha"]))
    ]
    for scheme, group in sensitivity.groupby("scheme", sort=True):
        axes[1, 1].plot(
            100 * group["budget"],
            100 * group["adjusted_gain"],
            marker="o",
            label=scheme,
        )
    axes[1, 1].axhline(0, color="black", linewidth=0.8)
    axes[1, 1].set_xlabel("Query budget (%)")
    axes[1, 1].set_ylabel("Adjusted gain (pp)")
    axes[1, 1].set_title("Budget sensitivity")
    axes[1, 1].legend(fontsize=8)

    fig.suptitle("Privileged context-interaction VoF upper bound", fontsize=15)
    fig.savefig(output, dpi=170)
    plt.close(fig)


def _markdown_table(frame: pd.DataFrame) -> str:
    try:
        return frame.to_markdown(index=False)
    except ImportError:
        return frame.to_csv(index=False)


def write_outputs(
    frame: pd.DataFrame,
    output_dir: Path,
    results: pd.DataFrame,
    combined: pd.DataFrame,
    predictions: pd.DataFrame,
    quintiles: pd.DataFrame,
    intervals: pd.DataFrame,
    decision: Mapping[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_dir / "all_model_results.csv", index=False)
    combined.to_csv(output_dir / "combined_model_ranking.csv", index=False)
    predictions.to_parquet(output_dir / "all_oof_predictions.parquet", index=False)
    quintiles.to_csv(output_dir / "score_quintiles.csv", index=False)
    intervals.to_csv(output_dir / "policy_cluster_intervals.csv", index=False)
    (output_dir / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    plot_summary(
        combined,
        results,
        quintiles,
        decision,
        output_dir / "context_interaction_upper_bound.png",
    )

    control = decision["relative_control"]
    context = decision["best_interaction_upper_bound"]
    comparison_rows = []
    interval_lookup = intervals.set_index(["role", "scheme"])
    for role, config in (("relative_control", control), ("best_interaction_upper_bound", context)):
        for scheme in ALL_SCHEMES:
            interval = interval_lookup.loc[(role, scheme)]
            comparison_rows.append(
                {
                    "role": role,
                    "scheme": scheme,
                    "adjusted_gain_pp": 100 * float(config[f"{scheme}__adjusted_gain"]),
                    "95% CI pp": (
                        f"[{100 * interval['ci_low']:+.2f}; {100 * interval['ci_high']:+.2f}]"
                    ),
                    "rescues": int(config[f"{scheme}__rescues"]),
                    "harms": int(config[f"{scheme}__harms"]),
                    "AUROC": float(config[f"{scheme}__rescue_vs_harm_auc"]),
                }
            )
    top_columns = [
        "family",
        "feature_count",
        "target_variant",
        "alpha",
        "min_transfer_adjusted_gain",
        "min_transfer_auc",
        "min_transfer_worst_cell",
        "min_transfer_monotonic_rho",
        "within_cell_grouped5__adjusted_gain",
    ]
    checks = "\n".join(
        f"- `{name}`: {'PASS' if passed else 'FAIL'}"
        for name, passed in decision["checks"].items()
    )
    report = f"""# Privileged context-interaction VoF upper bound

> Exploratory non-deployable analysis on previously opened outcomes.

- Rows / independent groups / cells: **{len(frame)} / {frame['independent_group'].nunique()} / {frame['cell_key'].nunique()}**.
- Commit / feedback SR: **{100 * frame['commit_success'].mean():.1f}% / {100 * frame['feedback_success'].mean():.1f}%**.
- Relative control: `{_config_label(control)}`.
- Best interaction upper bound: `{_config_label(context)}`.
- Relative worst-transfer adjusted gain: **{100 * control['min_transfer_adjusted_gain']:+.2f} pp**.
- Context worst-transfer adjusted gain: **{100 * context['min_transfer_adjusted_gain']:+.2f} pp**.
- Gate: **{'PASS' if decision['gate_passed'] else 'FAIL'}**.
- Decision: `{decision['decision']}`.

## Gate checks

{checks}

## Primary comparison

{_markdown_table(pd.DataFrame(comparison_rows))}

## Top configurations

{_markdown_table(combined.loc[:, top_columns].head(20))}

## Interpretation boundary

Task, perturbation level and privileged phase are supplied to this diagnostic.
The within-cell split measures interpolation only. Leave-one-task, level and
cell remain the decision splits. No row in this report is a confirmatory or
deployable planner result.
"""
    (output_dir / "RESULTS.md").write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "experiments/campaigns/object_contact_vof_development_20260903/analysis/"
            "object_contact_development_corpus.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "experiments/campaigns/context_interaction_upper_bound_20260903/analysis"
        ),
    )
    parser.add_argument("--expected-rows", type=int, default=EXPECTED_ROWS)
    parser.add_argument("--bootstrap-repetitions", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_parquet(args.input.expanduser().resolve())
    if len(frame) != args.expected_rows:
        raise ValueError(f"Expected {args.expected_rows} rows, found {len(frame)}")
    if frame["row_uid"].duplicated().any():
        raise ValueError("Duplicate row_uid in P2d corpus")
    outputs = run_analysis(frame, bootstrap_repetitions=args.bootstrap_repetitions)
    write_outputs(frame, args.output_dir.expanduser().resolve(), *outputs)
    decision = outputs[-1]
    print(
        f"[P2d] gate={'PASS' if decision['gate_passed'] else 'FAIL'} "
        f"decision={decision['decision']}",
        flush=True,
    )


if __name__ == "__main__":
    main()

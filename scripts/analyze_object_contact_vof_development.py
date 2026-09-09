#!/usr/bin/env python3
"""Grouped development screen for object-conditioned value of feedback."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_signed_vof_new_task_holdout import clustered_interval, load_pairs
    from invariant_cate_router import (
        build_prequery_dataset,
        feature_families as invariant_feature_families,
        fit_binary_logit,
        fit_potential_ensemble,
        fit_robust_scaler,
        numeric_matrix,
        predict_binary_logit,
        predict_potential_ensemble,
        transform_values,
        validate_feature_names,
    )
    from object_contact_vof import MODEL_NAME, extract_object_features
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_signed_vof_new_task_holdout import clustered_interval, load_pairs
    from scripts.invariant_cate_router import (
        build_prequery_dataset,
        feature_families as invariant_feature_families,
        fit_binary_logit,
        fit_potential_ensemble,
        fit_robust_scaler,
        numeric_matrix,
        predict_binary_logit,
        predict_potential_ensemble,
        transform_values,
        validate_feature_names,
    )
    from scripts.object_contact_vof import MODEL_NAME, extract_object_features


QUERY_COST = 0.025
BUDGET = 0.20
ALPHAS = (0.01, 0.1, 1.0, 10.0)
SCHEMES = ("leave_one_task", "leave_one_level", "leave_one_cell")
DIRECT_TARGETS = (
    "direct_success",
    "direct_terminal_utility",
    "direct_grounded",
)
AUX_LOGIT_ALPHA = 0.1
DEFAULT_EXPECTED_ROWS = 640


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _label_columns(raw: pd.DataFrame) -> pd.DataFrame:
    labels = pd.DataFrame(index=raw.index)
    labels["commit_drop"] = _as_bool(
        raw["open_terminal_episode_target_drop_candidate"]
    ).astype(int)
    labels["feedback_drop"] = _as_bool(
        raw["feedback_terminal_episode_target_drop_candidate"]
    ).astype(int)
    labels["commit_wrong"] = _as_bool(
        raw["open_terminal_episode_wrong_object_interaction_candidate"]
    ).astype(int)
    labels["feedback_wrong"] = _as_bool(
        raw["feedback_terminal_episode_wrong_object_interaction_candidate"]
    ).astype(int)
    labels["commit_deadlock"] = _as_bool(
        raw["open_terminal_episode_kinematic_deadlock_candidate"]
    ).astype(int)
    labels["feedback_deadlock"] = _as_bool(
        raw["feedback_terminal_episode_kinematic_deadlock_candidate"]
    ).astype(int)
    labels["commit_target_lift"] = _numeric(raw["open_observed_target_lift_max"])
    labels["feedback_target_lift"] = _numeric(
        raw["feedback_observed_target_lift_max"]
    )
    labels["commit_target_eef_distance"] = _numeric(
        raw["open_observed_target_eef_distance_min"]
    )
    labels["feedback_target_eef_distance"] = _numeric(
        raw["feedback_observed_target_eef_distance_min"]
    )
    labels["commit_target_contact_count"] = _numeric(
        raw["open_observed_robot_target_contact_count_sum"]
    )
    labels["feedback_target_contact_count"] = _numeric(
        raw["feedback_observed_robot_target_contact_count_sum"]
    )
    labels["commit_target_contact"] = labels["commit_target_contact_count"].gt(0).astype(int)
    labels["feedback_target_contact"] = labels[
        "feedback_target_contact_count"
    ].gt(0).astype(int)
    labels["terminal_utility_delta"] = _numeric(
        raw["feedback_terminal_utility_v1"]
    ) - _numeric(raw["open_terminal_utility_v1"])
    labels["drop_delta"] = labels["feedback_drop"] - labels["commit_drop"]
    labels["wrong_delta"] = labels["feedback_wrong"] - labels["commit_wrong"]
    labels["deadlock_delta"] = labels["feedback_deadlock"] - labels["commit_deadlock"]
    labels["lift_advantage"] = (
        labels["feedback_target_lift"] - labels["commit_target_lift"]
    )
    labels["distance_advantage"] = (
        labels["commit_target_eef_distance"]
        - labels["feedback_target_eef_distance"]
    )
    return labels


def load_development_corpus(campaign_dirs: Sequence[Path]) -> pd.DataFrame:
    parts = []
    for campaign_dir in campaign_dirs:
        campaign_dir = campaign_dir.expanduser().resolve()
        raw = load_pairs(campaign_dir)
        raw = raw.loc[raw["strict_integrity"].astype(bool)].reset_index(drop=True)
        base = build_prequery_dataset(raw, campaign_dir).reset_index(drop=True)
        labels = _label_columns(raw).reset_index(drop=True)
        if len(base) != len(labels):
            raise ValueError(f"Feature/label row mismatch for {campaign_dir}")
        base = pd.concat([base, labels], axis=1)
        base["campaign"] = campaign_dir.name
        base["row_uid"] = (
            base["source_run"].astype(str) + "|" + base["snapshot_id"].astype(str)
        )
        parts.append(base)
    result = pd.concat(parts, ignore_index=True)
    if result["row_uid"].duplicated().any():
        duplicates = result.loc[result["row_uid"].duplicated(), "row_uid"].tolist()
        raise ValueError(f"Duplicate development identities: {duplicates[:3]}")
    result["cell_key"] = (
        result["position_level"].astype(str)
        + "|task"
        + result["task_id"].astype(int).astype(str)
    )
    result["direct_success"] = result["terminal_effect"].astype(float)
    result["direct_terminal_utility"] = result["terminal_utility_delta"] / 3.5
    result["direct_grounded"] = (
        result["terminal_effect"].astype(float)
        - 0.25 * result["drop_delta"]
        - 0.125 * result["wrong_delta"]
        - 0.125 * result["deadlock_delta"]
        + 0.10 * np.tanh(result["lift_advantage"] / 0.025)
        + 0.10 * np.tanh(result["distance_advantage"] / 0.03)
    )
    return result


def model_feature_families(
    frame: pd.DataFrame,
) -> dict[str, tuple[tuple[str, ...], bool]]:
    invariant = invariant_feature_families(frame)
    relative = list(invariant["relative"])
    context = sorted(column for column in frame if column.startswith("f_context_"))
    object_all = sorted(column for column in frame if column.startswith("f_obj_"))
    object_global = sorted(
        column for column in object_all if "global_similarity" in column
    )
    if not object_all or not object_global:
        raise ValueError("Object-conditioned features are missing")
    families = {
        "relative": (tuple(relative), True),
        "relative_object_global": (tuple(relative + object_global), True),
        "relative_object_spatial": (tuple(relative + object_all), True),
        "object_spatial_only": (tuple(object_all), True),
        "relative_object_spatial_context_diagnostic": (
            tuple(relative + object_all + context),
            False,
        ),
    }
    for features, _deployable in families.values():
        validate_feature_names(features)
    return families


def fold_labels(frame: pd.DataFrame, scheme: str) -> pd.Series:
    if scheme == "leave_one_task":
        return "task" + frame["task_id"].astype(int).astype(str)
    if scheme == "leave_one_level":
        return frame["position_level"].astype(str)
    if scheme == "leave_one_cell":
        return frame["cell_key"].astype(str)
    raise ValueError(f"Unknown split scheme: {scheme}")


def _ridge_predict(
    train: np.ndarray,
    target: np.ndarray,
    test: np.ndarray,
    *,
    alpha: float,
) -> np.ndarray:
    design = np.column_stack([np.ones(len(train)), train])
    test_design = np.column_stack([np.ones(len(test)), test])
    penalty = np.eye(design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    weights = np.linalg.pinv(design.T @ design + penalty) @ design.T @ target
    return test_design @ weights


def cross_fitted_ridge(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: str,
    *,
    scheme: str,
    alpha: float,
) -> np.ndarray:
    matrix = numeric_matrix(frame, features)
    labels = fold_labels(frame, scheme)
    y = _numeric(frame[target]).to_numpy(float)
    prediction = np.full(len(frame), np.nan)
    for fold in sorted(labels.unique()):
        test = labels.eq(fold).to_numpy()
        train = ~test
        scaler = fit_robust_scaler(matrix[train])
        x_train = transform_values(matrix[train], scaler)
        x_test = transform_values(matrix[test], scaler)
        finite = np.isfinite(y[train])
        if not np.any(finite):
            raise ValueError(f"No finite target values for {target}/{fold}")
        prediction[test] = _ridge_predict(
            x_train[finite], y[train][finite], x_test, alpha=alpha
        )
    if not np.isfinite(prediction).all():
        raise ValueError(f"Non-finite OOF predictions for {target}/{scheme}")
    return prediction


def cross_fitted_potential(
    frame: pd.DataFrame,
    features: Sequence[str],
    *,
    scheme: str,
    alpha: float,
) -> np.ndarray:
    matrix = numeric_matrix(frame, features)
    labels = fold_labels(frame, scheme)
    commit = frame["commit_success"].astype(int).to_numpy()
    feedback = frame["feedback_success"].astype(int).to_numpy()
    prediction = np.full(len(frame), np.nan)
    for fold in sorted(labels.unique()):
        test = labels.eq(fold).to_numpy()
        train = ~test
        scaler = fit_robust_scaler(matrix[train])
        x_train = transform_values(matrix[train], scaler)
        x_test = transform_values(matrix[test], scaler)
        models = fit_potential_ensemble(
            x_train,
            commit[train],
            feedback[train],
            frame.loc[train, "independent_group"].astype(str),
            alpha=alpha,
            estimators=1,
            seed=0,
        )
        _p_commit, _p_feedback, effect, _std = predict_potential_ensemble(
            models, x_test
        )
        prediction[test] = effect
    if not np.isfinite(prediction).all():
        raise ValueError(f"Non-finite potential OOF predictions for {scheme}")
    return prediction


def cross_fitted_binary(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: str,
    *,
    scheme: str,
    alpha: float = AUX_LOGIT_ALPHA,
) -> np.ndarray:
    matrix = numeric_matrix(frame, features)
    labels = fold_labels(frame, scheme)
    y = frame[target].astype(int).to_numpy()
    prediction = np.full(len(frame), np.nan)
    for fold in sorted(labels.unique()):
        test = labels.eq(fold).to_numpy()
        train = ~test
        scaler = fit_robust_scaler(matrix[train])
        x_train = transform_values(matrix[train], scaler)
        x_test = transform_values(matrix[test], scaler)
        model = fit_binary_logit(x_train, y[train], alpha=alpha)
        prediction[test] = predict_binary_logit(model, x_test)
    if not np.isfinite(prediction).all():
        raise ValueError(f"Non-finite binary OOF predictions for {target}/{scheme}")
    return prediction


def _safe_spearman(target: np.ndarray, prediction: np.ndarray) -> float:
    target = np.asarray(target, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    finite = np.isfinite(target) & np.isfinite(prediction)
    if finite.sum() < 3 or np.ptp(target[finite]) <= 1e-12:
        return float("nan")
    return float(spearmanr(target[finite], prediction[finite]).statistic)


def _rescue_harm_auc(effect: np.ndarray, score: np.ndarray) -> float:
    effect = np.asarray(effect, dtype=float)
    discordant = effect != 0
    if not np.any(discordant):
        return float("nan")
    return float(binary_auc(effect[discordant] > 0, np.asarray(score)[discordant]))


def top_budget_mask(score: np.ndarray, budget: float = BUDGET) -> np.ndarray:
    score = np.asarray(score, dtype=float)
    count = max(1, int(math.ceil(len(score) * budget)))
    order = np.argsort(score, kind="stable")
    selected = np.zeros(len(score), dtype=bool)
    selected[order[-count:]] = True
    return selected


def score_quintiles(effect: np.ndarray, score: np.ndarray) -> pd.DataFrame:
    effect = np.asarray(effect, dtype=float)
    score = np.asarray(score, dtype=float)
    order = np.argsort(score, kind="stable")
    bins = np.empty(len(score), dtype=int)
    for quintile, indices in enumerate(np.array_split(order, 5)):
        bins[indices] = quintile
    return pd.DataFrame({"quintile": bins, "effect": effect, "score": score}).groupby(
        "quintile", sort=True
    ).agg(states=("effect", "size"), mean_effect=("effect", "mean"), mean_score=("score", "mean")).reset_index()


def evaluate_ranking(
    frame: pd.DataFrame, score: np.ndarray
) -> tuple[dict[str, Any], np.ndarray, pd.DataFrame]:
    effect = frame["terminal_effect"].to_numpy(float)
    query = top_budget_mask(score)
    contribution = query * (effect - QUERY_COST)
    cell_values = []
    for indices in frame.groupby("cell_key", sort=True).groups.values():
        cell_values.append(float(np.mean(contribution[np.asarray(indices, dtype=int)])))
    quintiles = score_quintiles(effect, score)
    row = {
        "query_rate": float(query.mean()),
        "raw_gain": float(np.mean(query * effect)),
        "adjusted_gain": float(contribution.mean()),
        "rescues": int(np.sum(query & (effect > 0))),
        "harms": int(np.sum(query & (effect < 0))),
        "rescue_vs_harm_auc": _rescue_harm_auc(effect, score),
        "effect_spearman": _safe_spearman(effect, score),
        "worst_cell_adjusted_gain": float(min(cell_values)),
        "quintile_monotonic_rho": _safe_spearman(
            quintiles["quintile"].to_numpy(float),
            quintiles["mean_effect"].to_numpy(float),
        ),
        "quintile_top_minus_bottom": float(
            quintiles.iloc[-1]["mean_effect"] - quintiles.iloc[0]["mean_effect"]
        ),
    }
    return row, query, quintiles


def combine_schemes(results: pd.DataFrame) -> pd.DataFrame:
    keys = ["family", "deployable", "feature_count", "target_variant", "alpha"]
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
    merged: pd.DataFrame | None = None
    for scheme in SCHEMES:
        part = results.loc[results["scheme"].eq(scheme), keys + metrics].copy()
        part = part.rename(
            columns={metric: f"{scheme}__{metric}" for metric in metrics}
        )
        merged = part if merged is None else merged.merge(part, on=keys, validate="one_to_one")
    assert merged is not None
    merged["min_adjusted_gain"] = merged[
        [f"{scheme}__adjusted_gain" for scheme in SCHEMES]
    ].min(axis=1)
    merged["min_auc"] = merged[
        [f"{scheme}__rescue_vs_harm_auc" for scheme in SCHEMES]
    ].min(axis=1)
    merged["min_worst_cell"] = merged[
        [f"{scheme}__worst_cell_adjusted_gain" for scheme in SCHEMES]
    ].min(axis=1)
    merged["min_monotonic_rho"] = merged[
        [f"{scheme}__quintile_monotonic_rho" for scheme in SCHEMES]
    ].min(axis=1)
    return merged.sort_values(
        ["deployable", "min_adjusted_gain", "min_auc", "min_monotonic_rho"],
        ascending=False,
    ).reset_index(drop=True)


CONTINUOUS_AUX_TARGETS = (
    "commit_target_lift",
    "feedback_target_lift",
    "lift_advantage",
    "commit_target_eef_distance",
    "feedback_target_eef_distance",
    "distance_advantage",
    "commit_target_contact_count",
    "feedback_target_contact_count",
)

BINARY_AUX_TARGETS = (
    "commit_target_contact",
    "feedback_target_contact",
    "commit_drop",
    "feedback_drop",
    "commit_wrong",
    "feedback_wrong",
    "commit_deadlock",
    "feedback_deadlock",
)


def evaluate_auxiliary_heads(
    frame: pd.DataFrame,
    configurations: Sequence[tuple[str, Sequence[str], float]],
) -> pd.DataFrame:
    rows = []
    for family, features, alpha in configurations:
        for scheme in SCHEMES:
            for target in CONTINUOUS_AUX_TARGETS:
                prediction = cross_fitted_ridge(
                    frame, features, target, scheme=scheme, alpha=alpha
                )
                observed = _numeric(frame[target]).to_numpy(float)
                rows.append(
                    {
                        "family": family,
                        "scheme": scheme,
                        "target": target,
                        "kind": "continuous",
                        "positives": np.nan,
                        "negatives": np.nan,
                        "spearman": _safe_spearman(observed, prediction),
                        "auc": np.nan,
                        "rmse": float(np.sqrt(np.mean(np.square(observed - prediction)))),
                    }
                )
            for target in BINARY_AUX_TARGETS:
                prediction = cross_fitted_binary(
                    frame, features, target, scheme=scheme
                )
                observed = frame[target].astype(int).to_numpy()
                positives = int(observed.sum())
                negatives = int(len(observed) - positives)
                auc = (
                    float(binary_auc(observed.astype(bool), prediction))
                    if positives and negatives
                    else float("nan")
                )
                rows.append(
                    {
                        "family": family,
                        "scheme": scheme,
                        "target": target,
                        "kind": "binary",
                        "positives": positives,
                        "negatives": negatives,
                        "spearman": np.nan,
                        "auc": auc,
                        "rmse": float(np.sqrt(np.mean(np.square(observed - prediction)))),
                    }
                )
    return pd.DataFrame(rows)


def _prediction_for_configuration(
    predictions: pd.DataFrame, configuration: pd.Series, scheme: str
) -> pd.DataFrame:
    return predictions.loc[
        predictions["family"].eq(str(configuration["family"]))
        & predictions["target_variant"].eq(str(configuration["target_variant"]))
        & np.isclose(predictions["alpha"], float(configuration["alpha"]))
        & predictions["scheme"].eq(scheme)
    ].copy()


def policy_intervals(
    frame: pd.DataFrame,
    predictions: pd.DataFrame,
    object_best: pd.Series,
    relative_best: pd.Series,
) -> pd.DataFrame:
    rows = []
    for scheme_index, scheme in enumerate(SCHEMES):
        relative = _prediction_for_configuration(predictions, relative_best, scheme)
        object_part = _prediction_for_configuration(predictions, object_best, scheme)
        if relative["row_uid"].tolist() != object_part["row_uid"].tolist():
            raise ValueError(f"Prediction row order mismatch for {scheme}")
        relative_contribution = relative["query"].to_numpy(float) * (
            relative["terminal_effect"].to_numpy(float) - QUERY_COST
        )
        object_contribution = object_part["query"].to_numpy(float) * (
            object_part["terminal_effect"].to_numpy(float) - QUERY_COST
        )
        relative_ci = clustered_interval(
            frame,
            relative_contribution,
            repetitions=10_000,
            seed=20260930 + scheme_index,
        )
        object_ci = clustered_interval(
            frame,
            object_contribution,
            repetitions=10_000,
            seed=20260940 + scheme_index,
        )
        difference = object_contribution - relative_contribution
        difference_ci = clustered_interval(
            frame,
            difference,
            repetitions=10_000,
            seed=20260950 + scheme_index,
        )
        rows.extend(
            [
                {
                    "role": "relative_control",
                    "scheme": scheme,
                    "adjusted_gain": float(relative_contribution.mean()),
                    "ci_low": relative_ci[0],
                    "ci_high": relative_ci[1],
                    "gain_vs_relative": 0.0,
                    "gain_vs_relative_ci_low": 0.0,
                    "gain_vs_relative_ci_high": 0.0,
                },
                {
                    "role": "best_object_candidate",
                    "scheme": scheme,
                    "adjusted_gain": float(object_contribution.mean()),
                    "ci_low": object_ci[0],
                    "ci_high": object_ci[1],
                    "gain_vs_relative": float(difference.mean()),
                    "gain_vs_relative_ci_low": difference_ci[0],
                    "gain_vs_relative_ci_high": difference_ci[1],
                },
            ]
        )
    return pd.DataFrame(rows)


def run_screen(
    frame: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    families = model_feature_families(frame)
    result_rows = []
    prediction_parts = []
    quintile_parts = []
    identity = [
        "row_uid",
        "campaign",
        "position_level",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "terminal_effect",
        "cell_key",
    ]
    for family, (features, deployable) in families.items():
        for alpha in ALPHAS:
            for scheme in SCHEMES:
                for target_variant in DIRECT_TARGETS:
                    score = cross_fitted_ridge(
                        frame,
                        features,
                        target_variant,
                        scheme=scheme,
                        alpha=alpha,
                    )
                    row, query, quintiles = evaluate_ranking(frame, score)
                    result_rows.append(
                        {
                            "family": family,
                            "deployable": deployable,
                            "feature_count": len(features),
                            "target_variant": target_variant,
                            "alpha": alpha,
                            "scheme": scheme,
                            **row,
                        }
                    )
                    prediction = frame[identity].copy()
                    prediction["family"] = family
                    prediction["target_variant"] = target_variant
                    prediction["alpha"] = alpha
                    prediction["scheme"] = scheme
                    prediction["score"] = score
                    prediction["query"] = query
                    prediction_parts.append(prediction)
                    quintiles["family"] = family
                    quintiles["target_variant"] = target_variant
                    quintiles["alpha"] = alpha
                    quintiles["scheme"] = scheme
                    quintile_parts.append(quintiles)
                score = cross_fitted_potential(
                    frame, features, scheme=scheme, alpha=alpha
                )
                row, query, quintiles = evaluate_ranking(frame, score)
                result_rows.append(
                    {
                        "family": family,
                        "deployable": deployable,
                        "feature_count": len(features),
                        "target_variant": "potential_success",
                        "alpha": alpha,
                        "scheme": scheme,
                        **row,
                    }
                )
                prediction = frame[identity].copy()
                prediction["family"] = family
                prediction["target_variant"] = "potential_success"
                prediction["alpha"] = alpha
                prediction["scheme"] = scheme
                prediction["score"] = score
                prediction["query"] = query
                prediction_parts.append(prediction)
                quintiles["family"] = family
                quintiles["target_variant"] = "potential_success"
                quintiles["alpha"] = alpha
                quintiles["scheme"] = scheme
                quintile_parts.append(quintiles)
            print(
                f"[object-vof] evaluated {family} alpha={alpha:g}", flush=True
            )
    results = pd.DataFrame(result_rows)
    combined = combine_schemes(results)
    predictions = pd.concat(prediction_parts, ignore_index=True)
    quintiles = pd.concat(quintile_parts, ignore_index=True)

    selected = combined.loc[combined["deployable"].astype(bool)].iloc[0]
    object_best = combined.loc[
        combined["deployable"].astype(bool)
        & combined["family"].astype(str).str.contains("object")
    ].iloc[0]
    relative_best = combined.loc[combined["family"].eq("relative")].iloc[0]
    family_best = (
        combined.loc[combined["deployable"].astype(bool)]
        .groupby("family", sort=False)
        .head(1)
    )
    auxiliary_configurations = [
        (
            str(row.family),
            families[str(row.family)][0],
            float(row.alpha),
        )
        for row in family_best.itertuples(index=False)
    ]
    auxiliary = evaluate_auxiliary_heads(
        frame,
        auxiliary_configurations,
    ).drop_duplicates(["family", "scheme", "target"])
    intervals = policy_intervals(frame, predictions, object_best, relative_best)

    task_aux = auxiliary.loc[
        auxiliary["family"].eq(str(object_best["family"]))
        & auxiliary["scheme"].eq("leave_one_task")
    ]
    continuous_required = task_aux.loc[
        task_aux["target"].isin(
            {"commit_target_lift", "commit_target_eef_distance"}
        )
    ]
    event_required = task_aux.loc[
        task_aux["target"].isin(
            {
                "commit_drop",
                "feedback_drop",
                "commit_wrong",
                "feedback_wrong",
                "commit_deadlock",
                "feedback_deadlock",
            }
        )
        & task_aux["positives"].gt(0)
        & task_aux["negatives"].gt(0)
    ]
    checks = {
        "selected_is_object_conditioned": "object" in str(selected["family"]),
        "object_improves_relative_worst_split": float(object_best["min_adjusted_gain"])
        > float(relative_best["min_adjusted_gain"]),
        "object_positive_adjusted_uplift_all_splits": all(
            float(object_best[f"{scheme}__adjusted_gain"]) > 0
            for scheme in SCHEMES
        ),
        "object_nonnegative_worst_cell_all_splits": all(
            float(object_best[f"{scheme}__worst_cell_adjusted_gain"]) >= 0
            for scheme in SCHEMES
        ),
        "object_monotonic_quintiles_all_splits": all(
            float(object_best[f"{scheme}__quintile_monotonic_rho"]) >= 0.5
            for scheme in SCHEMES
        ),
        "task_transfer_continuous_grounding": len(continuous_required) == 2
        and bool(continuous_required["spearman"].ge(0.4).all()),
        "task_transfer_terminal_event_auc": len(event_required) > 0
        and bool(event_required["auc"].ge(0.75).all()),
    }
    decision = {
        "selected": {
            key: (
                bool(value)
                if isinstance(value, (bool, np.bool_))
                else int(value)
                if isinstance(value, (int, np.integer))
                else float(value)
                if isinstance(value, (float, np.floating))
                else value
            )
            for key, value in selected.items()
        },
        "best_object_candidate": {
            key: (
                bool(value)
                if isinstance(value, (bool, np.bool_))
                else int(value)
                if isinstance(value, (int, np.integer))
                else float(value)
                if isinstance(value, (float, np.floating))
                else value
            )
            for key, value in object_best.items()
        },
        "relative_control": {
            key: (
                bool(value)
                if isinstance(value, (bool, np.bool_))
                else int(value)
                if isinstance(value, (int, np.integer))
                else float(value)
                if isinstance(value, (float, np.floating))
                else value
            )
            for key, value in relative_best.items()
        },
        "checks": checks,
        "gate_passed": bool(all(checks.values())),
        "decision": (
            "freeze_for_new_untouched_holdout"
            if all(checks.values())
            else "do_not_collect_new_holdout"
        ),
        "warning": "Exploratory development selection on previously opened outcomes.",
    }
    return results, combined, predictions, quintiles, auxiliary, intervals, decision


def _plot_results(
    frame: pd.DataFrame,
    combined: pd.DataFrame,
    predictions: pd.DataFrame,
    quintiles: pd.DataFrame,
    auxiliary: pd.DataFrame,
    decision: dict[str, Any],
    output: Path,
) -> None:
    selected = decision["best_object_candidate"]
    top = combined.loc[combined["deployable"].astype(bool)].head(12).iloc[::-1]
    labels = [
        f"{row.family}/{row.target_variant}/a{row.alpha:g}"
        for row in top.itertuples(index=False)
    ]
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    axes[0, 0].barh(labels, 100 * top["min_adjusted_gain"], color="#2f6f9f")
    axes[0, 0].axvline(0, color="black", linewidth=0.8)
    axes[0, 0].set_xlabel("Worst-split adjusted uplift at 20% (pp)")
    axes[0, 0].set_title("Deployable model ranking")

    selected_quintiles = quintiles.loc[
        quintiles["family"].eq(selected["family"])
        & quintiles["target_variant"].eq(selected["target_variant"])
        & np.isclose(quintiles["alpha"], float(selected["alpha"]))
    ]
    for scheme, group in selected_quintiles.groupby("scheme", sort=True):
        axes[0, 1].plot(
            group["quintile"], group["mean_effect"], marker="o", label=scheme
        )
    axes[0, 1].axhline(0, color="black", linewidth=0.8)
    axes[0, 1].set_xlabel("Predicted score quintile")
    axes[0, 1].set_ylabel("Observed feedback effect")
    axes[0, 1].set_title("Cross-fitted score calibration")
    axes[0, 1].legend(fontsize=8)

    task_aux = auxiliary.loc[auxiliary["scheme"].eq("leave_one_task")].copy()
    task_aux["metric"] = np.where(
        task_aux["kind"].eq("binary"), task_aux["auc"], task_aux["spearman"]
    )
    pivot = task_aux.pivot(index="target", columns="family", values="metric")
    pivot.plot.bar(ax=axes[1, 0], width=0.75)
    axes[1, 0].axhline(0.5, color="black", linewidth=0.8, linestyle="--")
    axes[1, 0].set_ylabel("AUROC (binary) / Spearman (continuous)")
    axes[1, 0].set_title("Leave-one-task auxiliary grounding")
    axes[1, 0].tick_params(axis="x", labelrotation=70, labelsize=7)

    selected_prediction = predictions.loc[
        predictions["family"].eq(selected["family"])
        & predictions["target_variant"].eq(selected["target_variant"])
        & np.isclose(predictions["alpha"], float(selected["alpha"]))
        & predictions["scheme"].eq("leave_one_cell")
    ].copy()
    selected_prediction["contribution"] = selected_prediction["query"].astype(float) * (
        selected_prediction["terminal_effect"] - QUERY_COST
    )
    cells = selected_prediction.groupby("cell_key", sort=True).agg(
        observed_effect=("terminal_effect", "mean"),
        adjusted_router_gain=("contribution", "mean"),
    )
    x = np.arange(len(cells))
    axes[1, 1].bar(x - 0.2, 100 * cells["observed_effect"], 0.4, label="always re-query raw")
    axes[1, 1].bar(x + 0.2, 100 * cells["adjusted_router_gain"], 0.4, label="router adjusted")
    axes[1, 1].axhline(0, color="black", linewidth=0.8)
    axes[1, 1].set_xticks(x, cells.index, rotation=70, ha="right", fontsize=7)
    axes[1, 1].set_ylabel("Gain (pp)")
    axes[1, 1].set_title("Leave-one-cell transfer")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("Object-conditioned value-of-feedback development screen")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def write_outputs(
    output_dir: Path,
    frame: pd.DataFrame,
    features: pd.DataFrame,
    results: pd.DataFrame,
    combined: pd.DataFrame,
    predictions: pd.DataFrame,
    quintiles: pd.DataFrame,
    auxiliary: pd.DataFrame,
    intervals: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_dir / "object_contact_development_corpus.parquet", index=False)
    features.to_parquet(output_dir / "object_contact_features.parquet", index=False)
    results.to_csv(output_dir / "all_model_results.csv", index=False)
    combined.to_csv(output_dir / "combined_model_ranking.csv", index=False)
    predictions.to_parquet(output_dir / "all_oof_predictions.parquet", index=False)
    quintiles.to_csv(output_dir / "score_quintiles.csv", index=False)
    auxiliary.to_csv(output_dir / "auxiliary_head_metrics.csv", index=False)
    intervals.to_csv(output_dir / "policy_cluster_intervals.csv", index=False)
    (output_dir / "decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    _plot_results(
        frame,
        combined,
        predictions,
        quintiles,
        auxiliary,
        decision,
        output_dir / "object_contact_vof_development.png",
    )
    selected = decision["selected"]
    object_best = decision["best_object_candidate"]
    relative = decision["relative_control"]
    lines = [
        "# Object/contact-conditioned VoF: development results",
        "",
        "> Exploratory development screen on previously opened outcomes. This is not a confirmatory holdout.",
        "",
        f"- Rows / independent groups / cells: **{len(frame)} / {frame['independent_group'].nunique()} / {frame['cell_key'].nunique()}**.",
        f"- Commit / feedback SR: **{100 * frame['commit_success'].mean():.1f}% / {100 * frame['feedback_success'].mean():.1f}%**.",
        f"- Rescues / harms: **{int((frame['terminal_effect'] > 0).sum())} / {int((frame['terminal_effect'] < 0).sum())}**.",
        f"- Overall selected: `{selected['family']}`, `{selected['target_variant']}`, alpha={selected['alpha']:g}.",
        f"- Overall selected worst-split adjusted uplift: **{100 * selected['min_adjusted_gain']:+.2f} pp**.",
        f"- Best object candidate: `{object_best['family']}`, `{object_best['target_variant']}`, alpha={object_best['alpha']:g}.",
        f"- Best object worst-split adjusted uplift: **{100 * object_best['min_adjusted_gain']:+.2f} pp**.",
        f"- Relative-control worst-split adjusted uplift: **{100 * relative['min_adjusted_gain']:+.2f} pp**.",
        f"- Development gate: **{'PASS' if decision['gate_passed'] else 'FAIL'}**.",
        f"- Decision: `{decision['decision']}`.",
        "",
        "## Gate checks",
        "",
    ]
    lines.extend(
        f"- `{name}`: {'PASS' if passed else 'FAIL'}"
        for name, passed in decision["checks"].items()
    )
    lines.extend(
        [
            "",
            "## Top deployable configurations",
            "",
            combined.loc[combined["deployable"].astype(bool)].head(20).to_markdown(index=False),
            "",
            "## Leave-one-task grounding diagnostics",
            "",
            auxiliary.loc[auxiliary["scheme"].eq("leave_one_task")].to_markdown(index=False),
            "",
            "## Cluster-bootstrap policy intervals",
            "",
            intervals.to_markdown(index=False),
            "",
            "Privileged contact, pose and terminal event fields were used only as supervision and evaluation labels.",
        ]
    )
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--row-batch-size", type=int, default=4)
    parser.add_argument("--expected-rows", type=int, default=DEFAULT_EXPECTED_ROWS)
    parser.add_argument("--reuse-object-features", action="store_true")
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = load_development_corpus(args.campaign_dir)
    if len(corpus) != args.expected_rows:
        raise ValueError(f"Expected {args.expected_rows} rows, found {len(corpus)}")
    feature_path = output_dir / "object_contact_features.parquet"
    if args.reuse_object_features and feature_path.exists():
        object_features = pd.read_parquet(feature_path)
    else:
        object_features = extract_object_features(
            corpus,
            project_root=args.project_root.expanduser().resolve(),
            model_name=args.model,
            device=args.device,
            row_batch_size=args.row_batch_size,
            local_files_only=not args.allow_model_download,
        )
        object_features.to_parquet(feature_path, index=False)
    if set(object_features["row_uid"]) != set(corpus["row_uid"]):
        raise ValueError("Object feature identities do not match the development corpus")
    frame = corpus.merge(object_features, on="row_uid", validate="one_to_one")
    results, combined, predictions, quintiles, auxiliary, intervals, decision = run_screen(
        frame
    )
    write_outputs(
        output_dir,
        frame,
        object_features,
        results,
        combined,
        predictions,
        quintiles,
        auxiliary,
        intervals,
        decision,
    )
    print(json.dumps(decision, indent=2))
    print(f"Results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

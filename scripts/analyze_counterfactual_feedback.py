#!/usr/bin/env python3
"""Analyze counterfactual feedback uplift and exact-state candidate ranking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from counterfactual_feedback_utils import deterministic_unit_interval
except ModuleNotFoundError:  # Imported as scripts.analyze_counterfactual_feedback in tests.
    from scripts.counterfactual_feedback_utils import deterministic_unit_interval


VOF_FEATURES = (
    "value_mean",
    "value_std",
    "value_range",
    "action_std_mean",
    "action_std_max",
    "action_first_step_l2_std",
    "action_pairwise_l2_mean",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_across_seed_std_mean",
    "latent_future_proprio_across_seed_std_mean",
    "latent_value_across_seed_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
    "candidate_action_consensus_first_mean",
    "candidate_action_consensus_chunk_mean",
    "planning_predicted_proprio_error",
)

VOF_TARGETS = (
    "local_vof",
    "dense_vof_v2",
    "h32_dense_vof_v2",
    "terminal_vof",
)

CANDIDATE_UTILITIES = (
    "local_utility_v1",
    "dense_utility_v2",
    "h32_dense_utility_v2",
    "terminal_utility_v1",
)

CANDIDATE_RANK_FEATURES = (
    "candidate_value",
    "candidate_first_action_l1",
    "candidate_action_chunk_l1",
    "candidate_action_chunk_l2",
    "latent_action_copy_std_mean",
    "latent_action_copy_std_max",
    "latent_action_first_step_copy_l2_std",
    "latent_future_proprio_copy_std_mean",
    "latent_future_proprio_copy_std_max",
    "latent_value_element_std_mean",
    "latent_value_element_std_max",
)

REPLAY_INTEGRITY_THRESHOLD = 1e-9


def _factor(frame: pd.DataFrame) -> pd.Series:
    case = frame.get("case_id", pd.Series("", index=frame.index)).astype(str)
    suite = frame.get("suite", pd.Series("", index=frame.index)).astype(str)
    result = pd.Series("Object", index=frame.index, dtype=object)
    result.loc[case.str.contains("position", case=False) | suite.str.contains("temp")] = "Position"
    result.loc[case.str.contains("environment", case=False) | suite.str.contains("env")] = "Environment"
    return result


def _read_preferred(paths: Iterable[Path]) -> pd.DataFrame:
    selected: dict[str, Path] = {}
    for path in paths:
        identity = path.with_suffix("").name
        current = selected.get(identity)
        if current is None or path.suffix == ".parquet":
            selected[identity] = path
    frames = []
    for path in sorted(selected.values()):
        frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        frame["source_file"] = str(path)
        source_run = path.with_suffix("").name
        for suffix in ("__feedback_pairs", "__candidate_outcomes"):
            if source_run.endswith(suffix):
                source_run = source_run[: -len(suffix)]
                break
        frame["source_run"] = source_run
        if "snapshot_id" in frame:
            # Position perturbation jobs reuse suite/task/init/query identifiers.
            # Keep states from different source runs distinct during pooled analysis.
            frame["analysis_snapshot_id"] = (
                frame["source_run"].astype(str) + "::" + frame["snapshot_id"].astype(str)
            )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_campaign(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_dir = campaign_dir / "runs" if (campaign_dir / "runs").is_dir() else campaign_dir
    feedback = _read_preferred(
        list(run_dir.glob("*__feedback_pairs.parquet"))
        + list(run_dir.glob("*__feedback_pairs.csv"))
    )
    candidates = _read_preferred(
        list(run_dir.glob("*__candidate_outcomes.parquet"))
        + list(run_dir.glob("*__candidate_outcomes.csv"))
    )
    for frame in (feedback, candidates):
        if len(frame):
            frame["factor"] = _factor(frame)
    return feedback, candidates


def binary_auc(labels: Sequence[bool], scores: Sequence[float]) -> float:
    labels_array = np.asarray(labels, dtype=bool)
    scores_array = np.asarray(scores, dtype=float)
    valid = np.isfinite(scores_array)
    labels_array = labels_array[valid]
    scores_array = scores_array[valid]
    positives = int(labels_array.sum())
    negatives = int((~labels_array).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(scores_array).rank(method="average").to_numpy()
    return float((ranks[labels_array].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def _group_keys(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["suite"].astype(str)
        + "|"
        + frame["task_id"].astype(str)
        + "|"
        + frame["init_state_id"].astype(str)
    )


def _group_folds(frame: pd.DataFrame, folds: int = 5) -> np.ndarray:
    keys = _group_keys(frame)
    unique_keys = sorted(
        keys.unique(), key=lambda key: deterministic_unit_interval("vof-fold", key)
    )
    active_folds = max(1, min(folds, len(unique_keys)))
    assignment = {key: index % active_folds for index, key in enumerate(unique_keys)}
    return keys.map(assignment).to_numpy(dtype=int)


def grouped_category_mean_predictions(
    frame: pd.DataFrame,
    target: str,
    categories: Sequence[str] = ("factor", "phase_at_snapshot"),
    *,
    folds: int = 5,
) -> np.ndarray:
    """OOF lookup baseline using only known perturbation family and policy phase."""
    predictions = np.full(len(frame), np.nan, dtype=float)
    target_values = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
    fold_ids = _group_folds(frame, folds=folds)
    columns = [column for column in categories if column in frame]
    for fold in range(folds):
        test = (fold_ids == fold) & np.isfinite(target_values)
        train = (fold_ids != fold) & np.isfinite(target_values)
        if train.sum() == 0 or test.sum() == 0:
            continue
        train_frame = frame.loc[train, columns].copy()
        train_frame["__target"] = target_values[train]
        means = train_frame.groupby(columns, dropna=False)["__target"].mean()
        fallback = float(np.mean(target_values[train]))
        test_frame = frame.loc[test, columns]
        if columns:
            predictions[test] = [
                float(means.get(tuple(row), fallback))
                if len(columns) > 1
                else float(means.get(row[0], fallback))
                for row in test_frame.itertuples(index=False, name=None)
            ]
        else:
            predictions[test] = fallback
    return predictions


def grouped_ridge_predictions(
    frame: pd.DataFrame,
    target: str,
    features: Sequence[str] = VOF_FEATURES,
    *,
    alpha: float = 1.0,
    folds: int = 5,
) -> tuple[np.ndarray, list[str]]:
    columns = [column for column in features if column in frame and frame[column].notna().any()]
    predictions = np.full(len(frame), np.nan, dtype=float)
    if not columns or len(frame) < 10:
        return predictions, columns
    values = frame[columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    target_values = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
    fold_ids = _group_folds(frame, folds=folds)
    for fold in range(folds):
        test = (fold_ids == fold) & np.isfinite(target_values)
        train = (fold_ids != fold) & np.isfinite(target_values)
        if train.sum() < len(columns) + 2 or test.sum() == 0:
            continue
        median = np.nanmedian(values[train], axis=0)
        median = np.where(np.isfinite(median), median, 0.0)
        x_train = np.where(np.isfinite(values[train]), values[train], median)
        x_test = np.where(np.isfinite(values[test]), values[test], median)
        mean = x_train.mean(axis=0)
        std = x_train.std(axis=0)
        std[std < 1e-8] = 1.0
        x_train = (x_train - mean) / std
        x_test = (x_test - mean) / std
        x_train = np.column_stack([np.ones(len(x_train)), x_train])
        x_test = np.column_stack([np.ones(len(x_test)), x_test])
        penalty = np.eye(x_train.shape[1]) * alpha
        penalty[0, 0] = 0.0
        coefficients = np.linalg.pinv(x_train.T @ x_train + penalty) @ x_train.T @ target_values[train]
        predictions[test] = x_test @ coefficients
    return predictions, columns


def grouped_candidate_ridge_predictions(
    frame: pd.DataFrame,
    target: str,
    features: Sequence[str] = CANDIDATE_RANK_FEATURES,
    *,
    alpha: float = 1.0,
    folds: int = 5,
) -> tuple[np.ndarray, list[str]]:
    """Predict within-snapshot candidate utility with task/init grouped OOF folds."""
    columns = [column for column in features if column in frame and frame[column].notna().any()]
    predictions = np.full(len(frame), np.nan, dtype=float)
    if not columns or len(frame) < 20:
        return predictions, columns
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in frame else "snapshot_id"
    )
    values = frame[columns].apply(pd.to_numeric, errors="coerce")
    values = values.groupby(frame[snapshot_column]).transform(_within_group_z).to_numpy(dtype=float)
    target_values = pd.to_numeric(frame[target], errors="coerce")
    centered_target = (
        target_values - target_values.groupby(frame[snapshot_column]).transform("mean")
    ).to_numpy(dtype=float)
    fold_ids = _group_folds(frame, folds=folds)
    for fold in range(folds):
        test = (fold_ids == fold) & np.isfinite(centered_target)
        train = (fold_ids != fold) & np.isfinite(centered_target)
        if train.sum() < len(columns) + 2 or test.sum() == 0:
            continue
        median = np.nanmedian(values[train], axis=0)
        median = np.where(np.isfinite(median), median, 0.0)
        x_train = np.where(np.isfinite(values[train]), values[train], median)
        x_test = np.where(np.isfinite(values[test]), values[test], median)
        mean = x_train.mean(axis=0)
        std = x_train.std(axis=0)
        std[std < 1e-8] = 1.0
        x_train = (x_train - mean) / std
        x_test = (x_test - mean) / std
        penalty = np.eye(x_train.shape[1]) * alpha
        coefficients = np.linalg.pinv(x_train.T @ x_train + penalty) @ x_train.T @ centered_target[train]
        predictions[test] = x_test @ coefficients
    return predictions, columns


def factor_grouped_candidate_ridge_predictions(
    frame: pd.DataFrame, target: str
) -> tuple[np.ndarray, dict[str, list[str]]]:
    predictions = np.full(len(frame), np.nan, dtype=float)
    feature_map: dict[str, list[str]] = {}
    for factor, index in frame.groupby("factor", sort=False).groups.items():
        positions = frame.index.get_indexer(index)
        scoped = frame.loc[index].reset_index(drop=True)
        scores, columns = grouped_candidate_ridge_predictions(scoped, target)
        predictions[positions] = scores
        feature_map[str(factor)] = columns
    return predictions, feature_map


def _random_scores(frame: pd.DataFrame, label: str) -> np.ndarray:
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in frame else "snapshot_id"
    )
    return np.asarray(
        [deterministic_unit_interval(label, value) for value in frame[snapshot_column].astype(str)],
        dtype=float,
    )


def budget_table(
    frame: pd.DataFrame,
    target: str,
    prediction: np.ndarray,
    extra_scores: dict[str, Sequence[float]] | None = None,
) -> pd.DataFrame:
    target_values = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(target_values) & np.isfinite(prediction)
    if not valid.any():
        return pd.DataFrame()
    scoped = frame.loc[valid].reset_index(drop=True)
    y = target_values[valid]
    ridge = prediction[valid]
    methods: dict[str, np.ndarray] = {
        "grouped_oof_ridge": ridge,
        "random": _random_scores(scoped, f"{target}-random"),
        "oracle": y.copy(),
    }
    for name, scores in (extra_scores or {}).items():
        values = np.asarray(scores, dtype=float)
        if len(values) != len(frame):
            raise ValueError(f"{name}: expected {len(frame)} scores, got {len(values)}")
        methods[name] = values[valid]
    for column in ("value_range", "action_first_step_l2_std", "planning_predicted_proprio_error"):
        if column in scoped:
            methods[column] = pd.to_numeric(scoped[column], errors="coerce").to_numpy(dtype=float)

    rows = []
    for method, scores in methods.items():
        finite_scores = np.where(np.isfinite(scores), scores, -np.inf)
        for budget in (0.10, 0.20, 0.30):
            count = max(1, int(np.ceil(len(y) * budget)))
            selected = np.argsort(finite_scores, kind="stable")[-count:]
            rows.append(
                {
                    "target": target,
                    "method": method,
                    "budget": budget,
                    "states": len(y),
                    "selected": count,
                    "mean_vof_selected": float(y[selected].mean()),
                    "uplift_per_decision": float(y[selected].sum() / len(y)),
                    "positive_rate_selected": float((y[selected] > 0).mean()),
                    "positive_vof_auc": binary_auc(y > 0, scores),
                }
            )
    return pd.DataFrame(rows)


def vof_analysis(feedback: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries = []
    for target in VOF_TARGETS:
        if target not in feedback:
            continue
        values = pd.to_numeric(feedback[target], errors="coerce")
        for (factor, phase), group in feedback.assign(_target=values).groupby(
            ["factor", "phase_at_snapshot"], dropna=False
        ):
            valid = group["_target"].dropna()
            if len(valid):
                summaries.append(
                    {
                        "target": target,
                        "factor": factor,
                        "phase": phase,
                        "states": len(valid),
                        "mean_vof": float(valid.mean()),
                        "median_vof": float(valid.median()),
                        "positive_rate": float((valid > 0).mean()),
                        "negative_rate": float((valid < 0).mean()),
                    }
                )

    predictions = []
    budgets = []
    for target in VOF_TARGETS:
        if target not in feedback or pd.to_numeric(feedback[target], errors="coerce").notna().sum() < 10:
            continue
        prediction, columns = grouped_ridge_predictions(feedback, target)
        phase_prediction = grouped_category_mean_predictions(feedback, target)
        target_values = pd.to_numeric(feedback[target], errors="coerce").to_numpy(dtype=float)
        for model, score, feature_text in (
            ("grouped_oof_ridge", prediction, ",".join(columns)),
            ("factor_phase_oof_mean", phase_prediction, "factor,phase_at_snapshot"),
        ):
            valid = np.isfinite(score) & np.isfinite(target_values)
            target_valid = np.isfinite(target_values)
            group_keys = _group_keys(feedback)
            predictions.append(
                {
                    "target": target,
                    "model": model,
                    "states": int(valid.sum()),
                    "available_groups": int(group_keys[target_valid].nunique()),
                    "evaluated_groups": int(group_keys[valid].nunique()),
                    "features": feature_text,
                    "mae": float(np.mean(np.abs(score[valid] - target_values[valid])))
                    if valid.any()
                    else np.nan,
                    "correlation": float(np.corrcoef(score[valid], target_values[valid])[0, 1])
                    if valid.sum() >= 2
                    and np.std(score[valid]) > 0
                    and np.std(target_values[valid]) > 0
                    else np.nan,
                    "sign_accuracy": float(
                        ((score[valid] > 0) == (target_values[valid] > 0)).mean()
                    )
                    if valid.any()
                    else np.nan,
                    "positive_vof_auc": binary_auc(target_values[valid] > 0, score[valid]),
                }
            )
        budget = budget_table(
            feedback,
            target,
            prediction,
            extra_scores={"factor_phase_oof_mean": phase_prediction},
        )
        if len(budget):
            budgets.append(budget)
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(predictions),
        pd.concat(budgets, ignore_index=True) if budgets else pd.DataFrame(),
    )


def factor_vof_analysis(feedback: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    predictor_frames = []
    budget_frames = []
    for factor, scoped in feedback.groupby("factor", sort=False):
        _summaries, predictors, budgets = vof_analysis(scoped.reset_index(drop=True))
        if len(predictors):
            predictors.insert(0, "factor", factor)
            predictor_frames.append(predictors)
        if len(budgets):
            budgets.insert(0, "factor", factor)
            budget_frames.append(budgets)
    return (
        pd.concat(predictor_frames, ignore_index=True) if predictor_frames else pd.DataFrame(),
        pd.concat(budget_frames, ignore_index=True) if budget_frames else pd.DataFrame(),
    )


def _within_group_z(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    std = numeric.std(ddof=0)
    if not np.isfinite(std) or std < 1e-8:
        return pd.Series(0.0, index=values.index)
    return (numeric - numeric.mean()) / std


def candidate_ranking(
    candidates: pd.DataFrame,
    utility: str,
    extra_scores: dict[str, Sequence[float]] | None = None,
) -> pd.DataFrame:
    scoped = candidates.loc[pd.to_numeric(candidates[utility], errors="coerce").notna()].copy()
    score_columns: dict[str, str] = {}
    for name, scores in (extra_scores or {}).items():
        values = np.asarray(scores, dtype=float)
        if len(values) != len(candidates):
            raise ValueError(f"{name}: expected {len(candidates)} scores, got {len(values)}")
        column = f"__candidate_score__{name}"
        scoped[column] = pd.Series(values, index=candidates.index).loc[scoped.index]
        score_columns[name] = column
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in scoped else "snapshot_id"
    )
    rows = []
    for snapshot_id, group in scoped.groupby(snapshot_column, sort=False):
        actual = pd.to_numeric(group[utility], errors="coerce").to_numpy(dtype=float)
        if len(actual) < 2 or not np.isfinite(actual).all():
            continue
        value = pd.to_numeric(group["candidate_value"], errors="coerce").to_numpy(dtype=float)
        internal_column = "latent_action_first_step_copy_l2_std"
        if internal_column in group:
            composite = _within_group_z(group["candidate_value"]).to_numpy() - _within_group_z(
                group[internal_column]
            ).to_numpy()
        else:
            composite = value.copy()
        random_score = np.asarray(
            [
                deterministic_unit_interval("candidate-random", snapshot_id, candidate_idx)
                for candidate_idx in group["candidate_idx"]
            ]
        )
        selectors = {
            "cosmos_value": value,
            "value_minus_internal_action": composite,
            "random": random_score,
            "oracle": actual,
        }
        for name, column in score_columns.items():
            selectors[name] = pd.to_numeric(group[column], errors="coerce").to_numpy(dtype=float)
        best = float(actual.max())
        best_indices = set(np.flatnonzero(np.isclose(actual, best)).tolist())
        for method, score in selectors.items():
            if not np.isfinite(score).any():
                continue
            selected = int(np.nanargmax(score))
            rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "factor": group["factor"].iloc[0],
                    "phase": group["phase_at_snapshot"].iloc[0],
                    "utility": utility,
                    "method": method,
                    "selected_candidate_idx": int(group.iloc[selected]["candidate_idx"]),
                    "selected_utility": float(actual[selected]),
                    "oracle_utility": best,
                    "regret": float(best - actual[selected]),
                    "top1_correct": bool(selected in best_indices),
                }
            )
    outcomes = pd.DataFrame(rows)
    if outcomes.empty:
        return outcomes
    return (
        outcomes.groupby(["utility", "method", "factor"], dropna=False)
        .agg(
            snapshots=("snapshot_id", "count"),
            mean_selected_utility=("selected_utility", "mean"),
            mean_regret=("regret", "mean"),
            top1_accuracy=("top1_correct", "mean"),
        )
        .reset_index()
    )


def candidate_analysis(
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking_frames = []
    model_rows = []
    for utility in CANDIDATE_UTILITIES:
        if utility not in candidates:
            continue
        pooled_score, pooled_features = grouped_candidate_ridge_predictions(candidates, utility)
        factor_score, factor_features = factor_grouped_candidate_ridge_predictions(
            candidates, utility
        )
        extra_scores = {
            "grouped_oof_candidate_ridge": pooled_score,
            "factor_oof_candidate_ridge": factor_score,
        }
        result = candidate_ranking(candidates, utility, extra_scores=extra_scores)
        if len(result):
            ranking_frames.append(result)
        target = pd.to_numeric(candidates[utility], errors="coerce")
        snapshot_column = (
            "analysis_snapshot_id"
            if "analysis_snapshot_id" in candidates
            else "snapshot_id"
        )
        centered = target - target.groupby(candidates[snapshot_column]).transform("mean")
        for method, score, features in (
            ("grouped_oof_candidate_ridge", pooled_score, pooled_features),
            (
                "factor_oof_candidate_ridge",
                factor_score,
                sorted({value for values in factor_features.values() for value in values}),
            ),
        ):
            valid = np.isfinite(score) & np.isfinite(centered.to_numpy(dtype=float))
            model_rows.append(
                {
                    "utility": utility,
                    "method": method,
                    "candidate_rows": int(valid.sum()),
                    "features": ",".join(features),
                    "centered_utility_correlation": (
                        float(np.corrcoef(score[valid], centered.to_numpy(dtype=float)[valid])[0, 1])
                        if valid.sum() >= 2
                        and np.std(score[valid]) > 0
                        and np.std(centered.to_numpy(dtype=float)[valid]) > 0
                        else np.nan
                    ),
                }
            )
    return (
        pd.concat(ranking_frames, ignore_index=True) if ranking_frames else pd.DataFrame(),
        pd.DataFrame(model_rows),
    )


def strict_integrity_subset(
    feedback: pd.DataFrame, candidates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in feedback else "snapshot_id"
    )
    candidate_snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in candidates else "snapshot_id"
    )
    replay_error = pd.to_numeric(
        feedback.get("main_open_replay_state_max_abs", pd.Series(np.nan, index=feedback.index)),
        errors="coerce",
    )
    valid_feedback = feedback.loc[
        replay_error.notna() & replay_error.le(REPLAY_INTEGRITY_THRESHOLD)
    ].copy()
    valid_snapshots = set(valid_feedback[snapshot_column].astype(str))
    valid_candidates = candidates.loc[
        candidates[candidate_snapshot_column].astype(str).isin(valid_snapshots)
    ].copy()
    return valid_feedback.reset_index(drop=True), valid_candidates.reset_index(drop=True)


def horizon_comparison(
    feedback: pd.DataFrame, candidates: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    vof_rows = []
    if {"dense_vof_v2", "h32_dense_vof_v2"}.issubset(feedback.columns):
        scopes = [("All", feedback), *feedback.groupby("factor", sort=False)]
        for factor, scoped in scopes:
            h16 = pd.to_numeric(scoped["dense_vof_v2"], errors="coerce").to_numpy()
            h32 = pd.to_numeric(scoped["h32_dense_vof_v2"], errors="coerce").to_numpy()
            valid = np.isfinite(h16) & np.isfinite(h32)
            vof_rows.append(
                {
                    "factor": factor,
                    "states": int(valid.sum()),
                    "h16_mean_vof": float(h16[valid].mean()) if valid.any() else np.nan,
                    "h32_mean_vof": float(h32[valid].mean()) if valid.any() else np.nan,
                    "h16_positive_rate": float((h16[valid] > 0).mean())
                    if valid.any()
                    else np.nan,
                    "h32_positive_rate": float((h32[valid] > 0).mean())
                    if valid.any()
                    else np.nan,
                    "sign_agreement": float(((h16[valid] > 0) == (h32[valid] > 0)).mean())
                    if valid.any()
                    else np.nan,
                    "correlation": (
                        float(np.corrcoef(h16[valid], h32[valid])[0, 1])
                        if valid.sum() >= 2
                        and np.std(h16[valid]) > 0
                        and np.std(h32[valid]) > 0
                        else np.nan
                    ),
                }
            )

    candidate_rows = []
    if {"dense_utility_v2", "h32_dense_utility_v2"}.issubset(candidates.columns):
        snapshot_column = (
            "analysis_snapshot_id"
            if "analysis_snapshot_id" in candidates
            else "snapshot_id"
        )
        for factor, scoped in [("All", candidates), *candidates.groupby("factor", sort=False)]:
            grouped = scoped.groupby(snapshot_column)
            h16_varies = grouped["dense_utility_v2"].nunique(dropna=True).gt(1)
            h32_varies = grouped["h32_dense_utility_v2"].nunique(dropna=True).gt(1)
            h16_ranges = grouped["dense_utility_v2"].agg(
                lambda values: pd.to_numeric(values, errors="coerce").max()
                - pd.to_numeric(values, errors="coerce").min()
            )
            h32_ranges = grouped["h32_dense_utility_v2"].agg(
                lambda values: pd.to_numeric(values, errors="coerce").max()
                - pd.to_numeric(values, errors="coerce").min()
            )
            common = h16_varies.index.intersection(h32_varies.index)
            candidate_rows.append(
                {
                    "factor": factor,
                    "snapshots": int(len(common)),
                    "h16_non_tied": int(h16_varies.loc[common].sum()),
                    "h32_non_tied": int(h32_varies.loc[common].sum()),
                    "both_non_tied": int(
                        (h16_varies.loc[common] & h32_varies.loc[common]).sum()
                    ),
                    "h16_utility_range_mean": float(h16_ranges.loc[common].mean()),
                    "h32_utility_range_mean": float(h32_ranges.loc[common].mean()),
                    "h16_utility_range_median": float(h16_ranges.loc[common].median()),
                    "h32_utility_range_median": float(h32_ranges.loc[common].median()),
                }
            )
    return pd.DataFrame(vof_rows), pd.DataFrame(candidate_rows)


def make_horizon_plot(feedback: pd.DataFrame, output_dir: Path) -> None:
    if not {"dense_vof_v2", "h32_dense_vof_v2"}.issubset(feedback.columns):
        return
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    colors = {"Object": "#2d6a4f", "Environment": "#d97706", "Position": "#2563eb"}
    plotted = False
    for factor, group in feedback.groupby("factor", sort=False):
        x = pd.to_numeric(group["dense_vof_v2"], errors="coerce")
        y = pd.to_numeric(group["h32_dense_vof_v2"], errors="coerce")
        valid = x.notna() & y.notna()
        if valid.any():
            ax.scatter(x[valid], y[valid], s=28, alpha=0.75, label=factor, color=colors.get(factor))
            plotted = True
    if not plotted:
        plt.close(fig)
        return
    lower, upper = ax.get_xlim()
    y_lower, y_upper = ax.get_ylim()
    lower = min(lower, y_lower)
    upper = max(upper, y_upper)
    ax.plot([lower, upper], [lower, upper], color="black", linewidth=1, linestyle="--")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.axvline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("dense VoF at H16")
    ax.set_ylabel("dense VoF at H32")
    ax.set_title("Matched consequence horizon")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "dense_vof_h16_h32_scatter.png", dpi=180)
    plt.close(fig)


def make_plots(budgets: pd.DataFrame, ranking: pd.DataFrame, output_dir: Path) -> None:
    if len(budgets):
        for target, group in budgets.groupby("target"):
            fig, ax = plt.subplots(figsize=(8, 4.8))
            for method, values in group.groupby("method"):
                values = values.sort_values("budget")
                ax.plot(values["budget"], values["uplift_per_decision"], marker="o", label=method)
            ax.axhline(0, color="black", linewidth=1)
            ax.set_xlabel("intervention budget")
            ax.set_ylabel("realized VoF per decision")
            ax.set_title(f"Value of Feedback routing: {target}")
            ax.grid(alpha=0.25)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(output_dir / f"{target}_uplift_at_budget.png", dpi=180)
            plt.close(fig)
    if len(ranking):
        macro = ranking.groupby(["utility", "method"], as_index=False)["mean_regret"].mean()
        for utility, group in macro.groupby("utility"):
            fig, ax = plt.subplots(figsize=(7.5, 4.5))
            ax.bar(group["method"], group["mean_regret"], color="#2d6a4f")
            ax.set_ylabel("factor-macro mean regret")
            ax.set_title(f"Exact-state candidate ranking: {utility}")
            ax.tick_params(axis="x", rotation=20)
            ax.grid(axis="y", alpha=0.25)
            fig.tight_layout()
            fig.savefig(output_dir / f"{utility}_candidate_regret.png", dpi=180)
            plt.close(fig)


def write_report(
    feedback: pd.DataFrame,
    candidates: pd.DataFrame,
    summaries: pd.DataFrame,
    predictors: pd.DataFrame,
    budgets: pd.DataFrame,
    ranking: pd.DataFrame,
    factor_predictors: pd.DataFrame,
    factor_budgets: pd.DataFrame,
    candidate_models: pd.DataFrame,
    strict_feedback: pd.DataFrame,
    strict_predictors: pd.DataFrame,
    strict_budgets: pd.DataFrame,
    strict_ranking: pd.DataFrame,
    horizon_vof: pd.DataFrame,
    horizon_candidates: pd.DataFrame,
    output_dir: Path,
) -> None:
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in feedback else "snapshot_id"
    )
    candidate_snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in candidates else "snapshot_id"
    )
    terminal_states = int(pd.to_numeric(feedback.get("terminal_vof"), errors="coerce").notna().sum())
    replay_error = pd.to_numeric(
        feedback.get("main_open_replay_state_max_abs", pd.Series(dtype=float)), errors="coerce"
    )
    replay_failures = int((replay_error > 1e-9).sum())

    varying_candidate_states: dict[str, int] = {}
    for utility in CANDIDATE_UTILITIES:
        if utility not in candidates:
            continue
        variation = (
            candidates.assign(_utility=pd.to_numeric(candidates[utility], errors="coerce"))
            .groupby(candidate_snapshot_column)["_utility"]
            .nunique(dropna=True)
        )
        varying_candidate_states[utility] = int((variation > 1).sum())

    support_lines = []
    for target in VOF_TARGETS:
        if target not in feedback:
            continue
        values = pd.to_numeric(feedback[target], errors="coerce")
        support_lines.append(
            f"- `{target}` support: **{int((values > 0).sum())} positive / "
            f"{int((values < 0).sum())} negative / {int((values == 0).sum())} zero**."
        )
    variation_text = ", ".join(
        f"`{utility}`={count}" for utility, count in varying_candidate_states.items()
    ) or "none"
    focused_factor_budgets = factor_budgets.loc[
        factor_budgets.get("target", pd.Series(dtype=str)).eq("dense_vof_v2")
        & factor_budgets.get("method", pd.Series(dtype=str)).isin(
            [
                "grouped_oof_ridge",
                "factor_phase_oof_mean",
                "random",
                "planning_predicted_proprio_error",
            ]
        )
    ] if len(factor_budgets) else pd.DataFrame()
    focused_strict_budgets = strict_budgets.loc[
        strict_budgets.get("target", pd.Series(dtype=str)).eq("dense_vof_v2")
        & strict_budgets.get("method", pd.Series(dtype=str)).isin(
            [
                "grouped_oof_ridge",
                "factor_phase_oof_mean",
                "random",
                "planning_predicted_proprio_error",
            ]
        )
    ] if len(strict_budgets) else pd.DataFrame()

    lines = [
        "# Counterfactual feedback and grounded candidate pilot",
        "",
        f"- Collected snapshot rows: **{len(feedback)}**; unique pooled states: "
        f"**{feedback[snapshot_column].nunique()}**.",
        f"- Candidate branch outcomes: **{len(candidates)}**.",
        f"- Snapshots with terminal continuation: **{terminal_states}**.",
        f"- Maximum main/open replay state error: **{replay_error.max():.3e}**."
        if replay_error.notna().any()
        else "- Replay integrity has no available values.",
        f"- Replay integrity failures at the preregistered `1e-9` threshold: "
        f"**{replay_failures}/{replay_error.notna().sum()}**.",
        *support_lines,
        f"- Candidate states with non-tied utility: {variation_text}.",
        "",
        "## VoF by factor and phase",
        "",
        summaries.to_markdown(index=False) if len(summaries) else "No VoF rows.",
        "",
        "## Grouped out-of-fold predictor",
        "",
        predictors.to_markdown(index=False) if len(predictors) else "Insufficient data.",
        "",
        "## Factor-wise grouped out-of-fold predictor",
        "",
        factor_predictors.to_markdown(index=False)
        if len(factor_predictors)
        else "Insufficient data.",
        "",
        "### Dense VoF uplift by factor",
        "",
        focused_factor_budgets.to_markdown(index=False)
        if len(focused_factor_budgets)
        else "Insufficient data.",
        "",
        "## Uplift at fixed query budget",
        "",
        budgets.to_markdown(index=False) if len(budgets) else "Insufficient data.",
        "",
        "## Exact-state candidate ranking",
        "",
        ranking.to_markdown(index=False) if len(ranking) else "Insufficient data.",
        "",
        "### Candidate OOF model diagnostics",
        "",
        candidate_models.to_markdown(index=False)
        if len(candidate_models)
        else "Insufficient data.",
        "",
        "## Strict replay-integrity sensitivity",
        "",
        f"- States satisfying `main_open_replay_state_max_abs <= {REPLAY_INTEGRITY_THRESHOLD:g}`: "
        f"**{len(strict_feedback)}/{len(feedback)}**.",
        "",
        strict_predictors.to_markdown(index=False)
        if len(strict_predictors)
        else "Insufficient data.",
        "",
        focused_strict_budgets.to_markdown(index=False)
        if len(focused_strict_budgets)
        else "Insufficient data.",
        "",
        strict_ranking.to_markdown(index=False)
        if len(strict_ranking)
        else "Insufficient data.",
        "",
        "## Matched H16/H32 consequence horizon",
        "",
        horizon_vof.to_markdown(index=False)
        if len(horizon_vof)
        else "No matched H32 labels in this campaign.",
        "",
        horizon_candidates.to_markdown(index=False)
        if len(horizon_candidates)
        else "No matched H32 candidate labels in this campaign.",
        "",
        "## Interpretation rules",
        "",
        "- P1 passes the pilot gate only if grouped OOF routing beats deterministic random routing at matched budget.",
        "- P2 passes only if a non-oracle ranker reduces held-out regret relative to Cosmos value on every OOD factor.",
        "- Local utility is a mechanism label; terminal success/safety continuation is the stronger endpoint.",
        "- An apparently high AUROC is not confirmatory when positive/negative support is sparse or confined to different factors.",
        "- States above the replay-integrity threshold are reported and excluded in the strict sensitivity section.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "counterfactual_feedback")
    output_dir.mkdir(parents=True, exist_ok=True)
    feedback, candidates = load_campaign(campaign_dir)
    if feedback.empty or candidates.empty:
        raise FileNotFoundError(f"No counterfactual feedback tables under {campaign_dir / 'runs'}")

    summaries, predictors, budgets = vof_analysis(feedback)
    factor_predictors, factor_budgets = factor_vof_analysis(feedback)
    ranking, candidate_models = candidate_analysis(candidates)
    strict_feedback, strict_candidates = strict_integrity_subset(feedback, candidates)
    strict_summaries, strict_predictors, strict_budgets = vof_analysis(strict_feedback)
    strict_factor_predictors, strict_factor_budgets = factor_vof_analysis(strict_feedback)
    strict_ranking, strict_candidate_models = candidate_analysis(strict_candidates)
    horizon_vof, horizon_candidates = horizon_comparison(feedback, candidates)

    feedback.to_parquet(output_dir / "feedback_pairs_all.parquet", index=False)
    candidates.to_parquet(output_dir / "candidate_outcomes_all.parquet", index=False)
    summaries.to_csv(output_dir / "vof_by_factor_phase.csv", index=False)
    predictors.to_csv(output_dir / "vof_oof_predictors.csv", index=False)
    budgets.to_csv(output_dir / "vof_uplift_at_budget.csv", index=False)
    factor_predictors.to_csv(output_dir / "vof_factor_oof_predictors.csv", index=False)
    factor_budgets.to_csv(output_dir / "vof_factor_uplift_at_budget.csv", index=False)
    ranking.to_csv(output_dir / "candidate_ranking_summary.csv", index=False)
    candidate_models.to_csv(output_dir / "candidate_oof_predictors.csv", index=False)
    strict_feedback.to_parquet(output_dir / "strict_feedback_pairs_all.parquet", index=False)
    strict_candidates.to_parquet(output_dir / "strict_candidate_outcomes_all.parquet", index=False)
    strict_summaries.to_csv(output_dir / "strict_vof_by_factor_phase.csv", index=False)
    strict_predictors.to_csv(output_dir / "strict_vof_oof_predictors.csv", index=False)
    strict_budgets.to_csv(output_dir / "strict_vof_uplift_at_budget.csv", index=False)
    strict_factor_predictors.to_csv(
        output_dir / "strict_vof_factor_oof_predictors.csv", index=False
    )
    strict_factor_budgets.to_csv(
        output_dir / "strict_vof_factor_uplift_at_budget.csv", index=False
    )
    strict_ranking.to_csv(output_dir / "strict_candidate_ranking_summary.csv", index=False)
    strict_candidate_models.to_csv(
        output_dir / "strict_candidate_oof_predictors.csv", index=False
    )
    horizon_vof.to_csv(output_dir / "horizon_vof_comparison.csv", index=False)
    horizon_candidates.to_csv(
        output_dir / "horizon_candidate_support.csv", index=False
    )
    make_plots(budgets, ranking, output_dir)
    make_horizon_plot(feedback, output_dir)
    write_report(
        feedback,
        candidates,
        summaries,
        predictors,
        budgets,
        ranking,
        factor_predictors,
        factor_budgets,
        candidate_models,
        strict_feedback,
        strict_predictors,
        strict_budgets,
        strict_ranking,
        horizon_vof,
        horizon_candidates,
        output_dir,
    )
    summary = {
        "snapshots": int(len(feedback)),
        "unique_analysis_snapshots": int(
            feedback[
                "analysis_snapshot_id" if "analysis_snapshot_id" in feedback else "snapshot_id"
            ].nunique()
        ),
        "candidate_outcomes": int(len(candidates)),
        "terminal_snapshots": int(pd.to_numeric(feedback.get("terminal_vof"), errors="coerce").notna().sum()),
        "replay_integrity_failures_1e_9": int(
            (
                pd.to_numeric(
                    feedback.get("main_open_replay_state_max_abs", pd.Series(dtype=float)),
                    errors="coerce",
                )
                > 1e-9
            ).sum()
        ),
        "strict_integrity_snapshots": int(len(strict_feedback)),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

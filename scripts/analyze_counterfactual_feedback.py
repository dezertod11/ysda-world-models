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


def _group_folds(frame: pd.DataFrame, folds: int = 5) -> np.ndarray:
    keys = (
        frame["suite"].astype(str)
        + "|"
        + frame["task_id"].astype(str)
        + "|"
        + frame["init_state_id"].astype(str)
    )
    return np.asarray(
        [int(deterministic_unit_interval("vof-fold", key) * folds) % folds for key in keys],
        dtype=int,
    )


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


def _random_scores(frame: pd.DataFrame, label: str) -> np.ndarray:
    return np.asarray(
        [deterministic_unit_interval(label, value) for value in frame["snapshot_id"].astype(str)],
        dtype=float,
    )


def budget_table(frame: pd.DataFrame, target: str, prediction: np.ndarray) -> pd.DataFrame:
    target_values = pd.to_numeric(frame[target], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(target_values)
    scoped = frame.loc[valid].reset_index(drop=True)
    y = target_values[valid]
    ridge = prediction[valid]
    methods: dict[str, np.ndarray] = {
        "grouped_oof_ridge": ridge,
        "random": _random_scores(scoped, f"{target}-random"),
        "oracle": y.copy(),
    }
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
    for target in ("local_vof", "terminal_vof"):
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
    for target in ("local_vof", "terminal_vof"):
        if target not in feedback or pd.to_numeric(feedback[target], errors="coerce").notna().sum() < 10:
            continue
        prediction, columns = grouped_ridge_predictions(feedback, target)
        target_values = pd.to_numeric(feedback[target], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(prediction) & np.isfinite(target_values)
        predictions.append(
            {
                "target": target,
                "states": int(valid.sum()),
                "features": ",".join(columns),
                "mae": float(np.mean(np.abs(prediction[valid] - target_values[valid]))) if valid.any() else np.nan,
                "correlation": float(np.corrcoef(prediction[valid], target_values[valid])[0, 1])
                if valid.sum() >= 2 and np.std(prediction[valid]) > 0 and np.std(target_values[valid]) > 0
                else np.nan,
                "sign_accuracy": float(((prediction[valid] > 0) == (target_values[valid] > 0)).mean())
                if valid.any()
                else np.nan,
                "positive_vof_auc": binary_auc(target_values[valid] > 0, prediction[valid]),
            }
        )
        budgets.append(budget_table(feedback, target, prediction))
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(predictions),
        pd.concat(budgets, ignore_index=True) if budgets else pd.DataFrame(),
    )


def _within_group_z(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    std = numeric.std(ddof=0)
    if not np.isfinite(std) or std < 1e-8:
        return pd.Series(0.0, index=values.index)
    return (numeric - numeric.mean()) / std


def candidate_ranking(candidates: pd.DataFrame, utility: str) -> pd.DataFrame:
    scoped = candidates.loc[pd.to_numeric(candidates[utility], errors="coerce").notna()].copy()
    rows = []
    for snapshot_id, group in scoped.groupby("snapshot_id", sort=False):
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
        best = float(actual.max())
        best_indices = set(np.flatnonzero(np.isclose(actual, best)).tolist())
        for method, score in selectors.items():
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
    output_dir: Path,
) -> None:
    terminal_states = int(pd.to_numeric(feedback.get("terminal_vof"), errors="coerce").notna().sum())
    replay_error = pd.to_numeric(
        feedback.get("main_open_replay_state_max_abs", pd.Series(dtype=float)), errors="coerce"
    )
    lines = [
        "# Counterfactual feedback and grounded candidate pilot",
        "",
        f"- Exact-state snapshots: **{len(feedback)}**.",
        f"- Candidate branch outcomes: **{len(candidates)}**.",
        f"- Snapshots with terminal continuation: **{terminal_states}**.",
        f"- Maximum main/open replay state error: **{replay_error.max():.3e}**."
        if replay_error.notna().any()
        else "- Replay integrity has no available values.",
        "",
        "## VoF by factor and phase",
        "",
        summaries.to_markdown(index=False) if len(summaries) else "No VoF rows.",
        "",
        "## Grouped out-of-fold predictor",
        "",
        predictors.to_markdown(index=False) if len(predictors) else "Insufficient data.",
        "",
        "## Uplift at fixed query budget",
        "",
        budgets.to_markdown(index=False) if len(budgets) else "Insufficient data.",
        "",
        "## Exact-state candidate ranking",
        "",
        ranking.to_markdown(index=False) if len(ranking) else "Insufficient data.",
        "",
        "## Interpretation rules",
        "",
        "- P1 passes the pilot gate only if grouped OOF routing beats deterministic random routing at matched budget.",
        "- P2 passes only if a non-oracle ranker reduces held-out regret relative to Cosmos value on every OOD factor.",
        "- Local utility is a mechanism label; terminal success/safety continuation is the stronger endpoint.",
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
    ranking_frames = []
    for utility in ("local_utility_v1", "terminal_utility_v1"):
        if utility in candidates:
            result = candidate_ranking(candidates, utility)
            if len(result):
                ranking_frames.append(result)
    ranking = pd.concat(ranking_frames, ignore_index=True) if ranking_frames else pd.DataFrame()

    feedback.to_parquet(output_dir / "feedback_pairs_all.parquet", index=False)
    candidates.to_parquet(output_dir / "candidate_outcomes_all.parquet", index=False)
    summaries.to_csv(output_dir / "vof_by_factor_phase.csv", index=False)
    predictors.to_csv(output_dir / "vof_oof_predictors.csv", index=False)
    budgets.to_csv(output_dir / "vof_uplift_at_budget.csv", index=False)
    ranking.to_csv(output_dir / "candidate_ranking_summary.csv", index=False)
    make_plots(budgets, ranking, output_dir)
    write_report(feedback, candidates, summaries, predictors, budgets, ranking, output_dir)
    summary = {
        "snapshots": int(len(feedback)),
        "candidate_outcomes": int(len(candidates)),
        "terminal_snapshots": int(pd.to_numeric(feedback.get("terminal_vof"), errors="coerce").notna().sum()),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

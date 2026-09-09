#!/usr/bin/env python3
"""Grouped development screen for a support-aware invariant CATE router."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_signed_vof_new_task_holdout import clustered_interval
    from invariant_cate_router import (
        apply_support_mode,
        build_prequery_dataset,
        feature_families,
        fit_potential_ensemble,
        fit_robust_scaler,
        fit_support_reference,
        numeric_matrix,
        predict_potential_ensemble,
        support_distance,
        transform_values,
    )
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_signed_vof_new_task_holdout import clustered_interval
    from scripts.invariant_cate_router import (
        apply_support_mode,
        build_prequery_dataset,
        feature_families,
        fit_potential_ensemble,
        fit_robust_scaler,
        fit_support_reference,
        numeric_matrix,
        predict_potential_ensemble,
        support_distance,
        transform_values,
    )


QUERY_COST = 0.025
ALPHAS = (0.001, 0.01, 0.1)
BETAS = (0.0, 0.5, 1.0)
SUPPORT_MODES = ("none", "known_level", "knn_q99", "known_level_knn_q99")
SCHEMES = ("leave_one_cell", "leave_one_task")
DEFAULT_ESTIMATORS = 12
DEFAULT_SEED = 20260905


def _fold_labels(frame: pd.DataFrame, scheme: str) -> pd.Series:
    if scheme == "leave_one_task":
        return "task" + frame["task_id"].astype(int).astype(str)
    if scheme == "leave_one_cell":
        return frame["position_level"].astype(str) + "|task" + frame[
            "task_id"
        ].astype(int).astype(str)
    raise ValueError(f"Unknown split scheme: {scheme}")


def _stable_fold_seed(base: int, *parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(__import__("hashlib").sha256(payload).digest()[:4], "big") ^ base


def cross_fitted_predictions(
    frame: pd.DataFrame,
    features: Sequence[str],
    *,
    scheme: str,
    alpha: float,
    estimators: int,
    seed: int,
) -> pd.DataFrame:
    matrix = numeric_matrix(frame, features)
    labels = _fold_labels(frame, scheme)
    commit = frame["commit_success"].astype(int).to_numpy()
    feedback = frame["feedback_success"].astype(int).to_numpy()
    output = pd.DataFrame(index=frame.index)
    for fold in sorted(labels.unique()):
        test = labels.eq(fold).to_numpy()
        train = ~test
        scaler = fit_robust_scaler(matrix[train])
        train_model = transform_values(matrix[train], scaler, clipped=True)
        test_model = transform_values(matrix[test], scaler, clipped=True)
        train_support = transform_values(matrix[train], scaler, clipped=False)
        test_support = transform_values(matrix[test], scaler, clipped=False)
        models = fit_potential_ensemble(
            train_model,
            commit[train],
            feedback[train],
            frame.loc[train, "independent_group"].astype(str).to_numpy(),
            alpha=alpha,
            estimators=estimators,
            seed=_stable_fold_seed(seed, scheme, fold, alpha, len(features)),
        )
        p_commit, p_feedback, tau, tau_std = predict_potential_ensemble(
            models, test_model
        )
        support = fit_support_reference(
            train_support,
            frame.loc[train, "independent_group"].astype(str).to_numpy(),
        )
        indices = frame.index[test]
        output.loc[indices, "predicted_commit_probability"] = p_commit
        output.loc[indices, "predicted_feedback_probability"] = p_feedback
        output.loc[indices, "predicted_cate"] = tau
        output.loc[indices, "predicted_cate_std"] = tau_std
        output.loc[indices, "support_distance"] = support_distance(
            test_support, support
        )
        output.loc[indices, "support_threshold"] = float(support["threshold"])
        output.loc[indices, "known_level"] = frame.loc[test, "position_level"].isin(
            frame.loc[train, "position_level"].astype(str).unique()
        ).to_numpy()
        output.loc[indices, "outer_fold"] = fold
    return output


def _auc(effect: np.ndarray, score: np.ndarray) -> float:
    discordant = effect != 0
    if not np.any(discordant):
        return float("nan")
    return float(binary_auc(effect[discordant] > 0, score[discordant]))


def evaluate_policy(
    frame: pd.DataFrame,
    prediction: pd.DataFrame,
    *,
    beta: float,
    support_mode: str,
    query_cost: float = QUERY_COST,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    score = prediction["predicted_cate"].to_numpy(float) - beta * prediction[
        "predicted_cate_std"
    ].to_numpy(float)
    supported = apply_support_mode(
        support_mode,
        levels=frame["position_level"].astype(str),
        known_levels=frame.loc[prediction["known_level"].astype(bool), "position_level"].astype(str).unique(),
        distances=prediction["support_distance"].to_numpy(float),
        distance_threshold=prediction["support_threshold"].to_numpy(float),
    )
    # known_level is fold-specific; preserve it instead of reconstructing a global set.
    if support_mode in {"known_level", "known_level_knn_q99"}:
        supported &= prediction["known_level"].astype(bool).to_numpy()
    query = supported & (score > query_cost)
    effect = frame["terminal_effect"].to_numpy(float)
    contribution = query.astype(float) * effect - query_cost * query.astype(float)
    cell_adjusted = []
    for indices in frame.groupby(["position_level", "task_id"], sort=True).groups.values():
        cell_adjusted.append(float(np.mean(contribution[np.asarray(indices, dtype=int)])))
    effective_score = np.where(supported, score, -1e6)
    row = {
        "beta": float(beta),
        "support_mode": support_mode,
        "query_rate": float(query.mean()),
        "support_rate": float(supported.mean()),
        "raw_gain": float(np.mean(query * effect)),
        "adjusted_gain": float(contribution.mean()),
        "rescues": int(np.sum(query & (effect > 0))),
        "harms": int(np.sum(query & (effect < 0))),
        "rescue_vs_harm_auc": _auc(effect, effective_score),
        "worst_cell_adjusted_gain": float(min(cell_adjusted)),
    }
    return row, query, contribution


def _combine_schemes(results: pd.DataFrame) -> pd.DataFrame:
    keys = ["family", "deployable", "alpha", "beta", "support_mode"]
    metrics = [
        "query_rate",
        "support_rate",
        "raw_gain",
        "adjusted_gain",
        "rescues",
        "harms",
        "rescue_vs_harm_auc",
        "worst_cell_adjusted_gain",
    ]
    parts = []
    for scheme in SCHEMES:
        selected = results.loc[results["scheme"].eq(scheme), keys + metrics].copy()
        selected = selected.rename(columns={metric: f"{scheme}__{metric}" for metric in metrics})
        parts.append(selected)
    combined = parts[0].merge(parts[1], on=keys, validate="one_to_one")
    combined["min_adjusted_gain"] = combined[
        [f"{scheme}__adjusted_gain" for scheme in SCHEMES]
    ].min(axis=1)
    combined["max_query_rate"] = combined[
        [f"{scheme}__query_rate" for scheme in SCHEMES]
    ].max(axis=1)
    combined["min_auc"] = combined[
        [f"{scheme}__rescue_vs_harm_auc" for scheme in SCHEMES]
    ].min(axis=1)
    combined["min_worst_cell"] = combined[
        [f"{scheme}__worst_cell_adjusted_gain" for scheme in SCHEMES]
    ].min(axis=1)
    always_adjusted = float(results.attrs["always_adjusted_gain"])
    combined["beats_always_requery_both"] = combined["min_adjusted_gain"] > always_adjusted
    combined["fast_gate"] = (
        combined["deployable"].astype(bool)
        & combined["beats_always_requery_both"]
        & combined["max_query_rate"].le(0.60)
        & combined["min_auc"].ge(0.55)
        & combined["min_worst_cell"].ge(-0.05)
    )
    return combined.sort_values(
        ["fast_gate", "min_adjusted_gain", "min_auc"], ascending=False
    ).reset_index(drop=True)


def _plot(combined: pd.DataFrame, selected_predictions: pd.DataFrame, output: Path) -> None:
    top = combined.head(16).iloc[::-1]
    labels = [
        f"{row.family}/a{row.alpha:g}/b{row.beta:g}/{row.support_mode}"
        for row in top.itertuples(index=False)
    ]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    axes[0].barh(labels, 100 * top["min_adjusted_gain"], color="#2368a2")
    axes[0].axvline(100 * (0.07083333333333333 - QUERY_COST), color="black", linestyle="--", label="always re-query")
    axes[0].set_xlabel("Worst split adjusted gain (pp)")
    axes[0].legend()
    for scheme, marker, color in (("leave_one_cell", "o", "#9b2c2c"), ("leave_one_task", "s", "#27845c")):
        part = selected_predictions.loc[selected_predictions["scheme"].eq(scheme)]
        axes[1].scatter(
            part["effective_score"],
            part["terminal_effect"],
            alpha=0.65,
            marker=marker,
            color=color,
            label=scheme,
        )
    axes[1].axvline(QUERY_COST, color="black", linestyle="--", label="query cost")
    axes[1].set_xlabel("Cross-fitted CATE LCB after support gate")
    axes[1].set_ylabel("Observed feedback effect")
    axes[1].set_yticks([-1, 0, 1])
    axes[1].legend()
    fig.suptitle("Invariant CATE development screen")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--estimators", type=int, default=DEFAULT_ESTIMATORS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source = pd.read_parquet(args.predictions)
    dataset = build_prequery_dataset(source, args.campaign_dir.expanduser().resolve())
    dataset.to_parquet(output_dir / "invariant_cate_dataset.parquet", index=False)
    families = feature_families(dataset)

    result_rows = []
    prediction_parts = []
    for family, features in families.items():
        deployable = not family.startswith("privileged_")
        for alpha in ALPHAS:
            for scheme in SCHEMES:
                prediction = cross_fitted_predictions(
                    dataset,
                    features,
                    scheme=scheme,
                    alpha=alpha,
                    estimators=args.estimators,
                    seed=args.seed,
                )
                prediction = pd.concat(
                    [dataset[list(IDENTITY_FOR_OUTPUT)].reset_index(drop=True), prediction.reset_index(drop=True)],
                    axis=1,
                )
                prediction["family"] = family
                prediction["deployable"] = deployable
                prediction["alpha"] = alpha
                prediction["scheme"] = scheme
                prediction_parts.append(prediction)
                for beta in BETAS:
                    for support_mode in SUPPORT_MODES:
                        row, _query, _contribution = evaluate_policy(
                            dataset,
                            prediction,
                            beta=beta,
                            support_mode=support_mode,
                        )
                        result_rows.append(
                            {
                                "family": family,
                                "deployable": deployable,
                                "alpha": alpha,
                                "scheme": scheme,
                                **row,
                            }
                        )

    results = pd.DataFrame(result_rows)
    effect = dataset["terminal_effect"].to_numpy(float)
    always_adjusted = float(np.mean(effect - QUERY_COST))
    results.attrs["always_adjusted_gain"] = always_adjusted
    combined = _combine_schemes(results)
    predictions = pd.concat(prediction_parts, ignore_index=True)
    selected = combined.iloc[0].to_dict()
    selected_key = {
        key: selected[key]
        for key in ("family", "alpha", "beta", "support_mode")
    }
    selected_parts = []
    scheme_intervals = []
    for scheme in SCHEMES:
        part = predictions.loc[
            predictions["family"].eq(selected["family"])
            & predictions["alpha"].eq(float(selected["alpha"]))
            & predictions["scheme"].eq(scheme)
        ].copy()
        score = part["predicted_cate"].to_numpy(float) - float(selected["beta"]) * part[
            "predicted_cate_std"
        ].to_numpy(float)
        supported = np.ones(len(part), dtype=bool)
        if selected["support_mode"] in {"known_level", "known_level_knn_q99"}:
            supported &= part["known_level"].astype(bool).to_numpy()
        if selected["support_mode"] in {"knn_q99", "known_level_knn_q99"}:
            supported &= part["support_distance"].to_numpy(float) <= part[
                "support_threshold"
            ].to_numpy(float)
        query = supported & (score > QUERY_COST)
        contribution = query * part["terminal_effect"].to_numpy(float) - QUERY_COST * query
        part["supported"] = supported
        part["effective_score"] = np.where(supported, score, -1e6)
        part["query"] = query
        part["adjusted_contribution"] = contribution
        selected_parts.append(part)
        ci = clustered_interval(
            dataset,
            contribution,
            repetitions=10_000,
            seed=args.seed + (1 if scheme == "leave_one_task" else 0),
        )
        always_difference = contribution - (effect - QUERY_COST)
        versus_always_ci = clustered_interval(
            dataset,
            always_difference,
            repetitions=10_000,
            seed=args.seed + (11 if scheme == "leave_one_task" else 10),
        )
        scheme_intervals.append(
            {
                "scheme": scheme,
                "adjusted_gain": float(contribution.mean()),
                "adjusted_ci_low": ci[0],
                "adjusted_ci_high": ci[1],
                "gain_vs_always_requery": float(always_difference.mean()),
                "gain_vs_always_ci_low": versus_always_ci[0],
                "gain_vs_always_ci_high": versus_always_ci[1],
            }
        )

    selected_predictions = pd.concat(selected_parts, ignore_index=True)
    results.to_csv(output_dir / "all_policy_results.csv", index=False)
    combined.to_csv(output_dir / "combined_model_ranking.csv", index=False)
    predictions.to_parquet(output_dir / "all_cross_fitted_predictions.parquet", index=False)
    selected_predictions.to_parquet(output_dir / "selected_cross_fitted_predictions.parquet", index=False)
    pd.DataFrame(scheme_intervals).to_csv(output_dir / "selected_intervals.csv", index=False)
    decision = {
        "development_rows": len(dataset),
        "independent_groups": int(dataset["independent_group"].nunique()),
        "available_rescues": int(np.sum(effect > 0)),
        "available_harms": int(np.sum(effect < 0)),
        "always_requery_adjusted_gain": always_adjusted,
        "selected": selected_key,
        "selected_metrics": {
            key: (bool(value) if isinstance(value, (bool, np.bool_)) else float(value) if isinstance(value, (float, np.floating)) else int(value) if isinstance(value, (int, np.integer)) else value)
            for key, value in selected.items()
            if key not in {"family", "support_mode"}
        },
        "fast_gate_pass": bool(selected["fast_gate"]),
        "decision": "freeze_for_untouched_reserve" if selected["fast_gate"] else "do_not_collect_new_holdout",
        "warning": "Development model selection only; not confirmatory evidence.",
    }
    (output_dir / "decision.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    _plot(combined, selected_predictions, output_dir / "invariant_cate_development.png")
    lines = [
        "# Support-aware invariant CATE development screen",
        "",
        f"- Rows / independent groups: {len(dataset)} / {dataset['independent_group'].nunique()}.",
        f"- Available rescues / harms: {np.sum(effect > 0)} / {np.sum(effect < 0)}.",
        f"- Always-requery adjusted gain: {100 * always_adjusted:+.1f} pp.",
        f"- Selected development configuration: `{selected_key}`.",
        f"- Fast gate: **{'PASS' if decision['fast_gate_pass'] else 'FAIL'}**.",
        f"- Decision: `{decision['decision']}`.",
        "",
        "## Selected grouped intervals",
        "",
        pd.DataFrame(scheme_intervals).to_markdown(index=False),
        "",
        "## Top configurations",
        "",
        combined.head(20).to_markdown(index=False),
        "",
        "This is a development search. Privileged phase features are diagnostic only and cannot be selected for deployment.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2))
    print(f"Results: {output_dir}")
    return 0


IDENTITY_FOR_OUTPUT = (
    "snapshot_id",
    "source_run",
    "position_level",
    "task_id",
    "init_state_id",
    "rollout_id",
    "rollout_seed",
    "phase_at_snapshot",
    "commit_success",
    "feedback_success",
    "terminal_effect",
    "independent_group",
)


if __name__ == "__main__":
    raise SystemExit(main())

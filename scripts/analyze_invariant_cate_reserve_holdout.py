#!/usr/bin/env python3
"""Evaluate the frozen invariant-CATE router on the untouched reserve holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_signed_vof_new_task_holdout import (
        clustered_interval,
        load_pairs,
        policy_row,
    )
    from invariant_cate_router import build_prequery_dataset, predict_frozen_cate
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_signed_vof_new_task_holdout import (
        clustered_interval,
        load_pairs,
        policy_row,
    )
    from scripts.invariant_cate_router import build_prequery_dataset, predict_frozen_cate


def _interval(
    frame: pd.DataFrame, values: np.ndarray, manifest: dict[str, object], offset: int
) -> tuple[float, float]:
    return clustered_interval(
        frame,
        values,
        repetitions=int(manifest["bootstrap_repetitions"]),
        seed=int(manifest["bootstrap_seed"]) + offset,
    )


def _summarize_group(
    frame: pd.DataFrame, columns: list[str], query_cost: float
) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(columns, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        query = group["router_query"].to_numpy(bool)
        router = policy_row(group, query, query_cost)
        always = policy_row(group, np.ones(len(group), dtype=bool), query_cost)
        row = dict(zip(columns, keys))
        row.update(
            {
                "states": len(group),
                "commit_sr": float(group["commit_success"].mean()),
                "feedback_sr": float(group["feedback_success"].mean()),
                "router_sr": router["policy_success_rate"],
                "query_rate": router["query_rate"],
                "support_rate": float(group["supported"].mean()),
                "rescues": router["rescues"],
                "harms": router["harms"],
                "raw_gain": router["raw_success_delta"],
                "adjusted_gain": router["adjusted_success_delta"],
                "always_requery_adjusted_gain": always["adjusted_success_delta"],
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _potential_outcome_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for branch, outcome_column, prediction_column in (
        ("commit", "commit_success", "predicted_commit_probability"),
        ("feedback", "feedback_success", "predicted_feedback_probability"),
    ):
        outcome = frame[outcome_column].to_numpy(bool)
        prediction = frame[prediction_column].to_numpy(float)
        rows.append(
            {
                "branch": branch,
                "states": len(frame),
                "observed_success_rate": float(outcome.mean()),
                "mean_predicted_probability": float(prediction.mean()),
                "calibration_bias": float(prediction.mean() - outcome.mean()),
                "brier_score": float(np.mean(np.square(prediction - outcome))),
                "auroc": float(binary_auc(outcome, prediction)),
            }
        )
    return pd.DataFrame(rows)


def _posthoc_policy_sensitivity(
    frame: pd.DataFrame,
    effect: np.ndarray,
    query_cost: float,
    manifest: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    supported = frame["supported"].to_numpy(bool)
    cate = frame["predicted_cate"].to_numpy(float)
    cate_std = frame["predicted_cate_std"].to_numpy(float)

    beta_rows = []
    for index, beta in enumerate((0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0)):
        query = supported & ((cate - beta * cate_std) > query_cost)
        adjusted = query * effect - query_cost * query
        ci_low, ci_high = _interval(frame, adjusted, manifest, 100 + index)
        row = policy_row(frame, query, query_cost)
        beta_rows.append(
            {
                "beta": beta,
                **row,
                "adjusted_ci_low": ci_low,
                "adjusted_ci_high": ci_high,
                "status": "posthoc_diagnostic_only",
            }
        )

    threshold_rows = []
    for index, threshold in enumerate(
        (-0.1, 0.0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)
    ):
        query = supported & (cate > threshold)
        adjusted = query * effect - query_cost * query
        ci_low, ci_high = _interval(frame, adjusted, manifest, 200 + index)
        row = policy_row(frame, query, query_cost)
        threshold_rows.append(
            {
                "threshold": threshold,
                **row,
                "adjusted_ci_low": ci_low,
                "adjusted_ci_high": ci_high,
                "status": "posthoc_diagnostic_only",
            }
        )
    return pd.DataFrame(beta_rows), pd.DataFrame(threshold_rows)


def _effect_score_deciles(frame: pd.DataFrame) -> pd.DataFrame:
    ranked = frame.copy()
    ranked["score_decile"] = pd.qcut(
        ranked["predicted_cate"], 10, labels=False, duplicates="drop"
    )
    rows = []
    for decile, group in ranked.groupby("score_decile", sort=True):
        effect = group["terminal_effect"].to_numpy(float)
        rows.append(
            {
                "score_decile": int(decile),
                "states": len(group),
                "score_min": float(group["predicted_cate"].min()),
                "score_mean": float(group["predicted_cate"].mean()),
                "score_max": float(group["predicted_cate"].max()),
                "observed_effect": float(effect.mean()),
                "rescues": int(np.sum(effect > 0)),
                "harms": int(np.sum(effect < 0)),
            }
        )
    return pd.DataFrame(rows)


def _plot(
    policies: pd.DataFrame, cells: pd.DataFrame, frame: pd.DataFrame, output: Path
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    axes[0, 0].bar(
        policies["policy"], policies["policy_success_rate"], color=["#777", "#277da1", "#43aa8b", "#f9c74f"]
    )
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_ylabel("Terminal success rate")
    axes[0, 0].tick_params(axis="x", rotation=20)

    labels = [f"{row.position_level}/t{row.task_id}" for row in cells.itertuples(index=False)]
    x = np.arange(len(cells))
    axes[0, 1].bar(x - 0.18, cells["adjusted_gain"], 0.36, label="frozen CATE")
    axes[0, 1].bar(x + 0.18, cells["always_requery_adjusted_gain"], 0.36, label="always re-query")
    axes[0, 1].axhline(0, color="black", linewidth=0.8)
    axes[0, 1].set_xticks(x, labels, rotation=35, ha="right")
    axes[0, 1].set_ylabel("Cost-adjusted gain")
    axes[0, 1].legend()

    groups = [
        frame.loc[frame["terminal_effect"].eq(effect), "router_score"]
        for effect in (-1, 0, 1)
    ]
    axes[1, 0].boxplot(groups, tick_labels=["harm", "neutral", "rescue"], showfliers=False)
    axes[1, 0].axhline(0.025, color="black", linestyle="--", label="query cost")
    axes[1, 0].set_ylabel("Frozen CATE score")
    axes[1, 0].legend()

    colors = np.where(frame["router_query"], "#277da1", "#aaaaaa")
    axes[1, 1].scatter(
        frame["support_distance"], frame["router_score"], c=colors, alpha=0.65
    )
    axes[1, 1].axvline(
        float(frame["support_threshold"].iloc[0]), color="black", linestyle="--"
    )
    axes[1, 1].axhline(0.025, color="black", linestyle=":")
    axes[1, 1].set_xlabel("KNN support distance")
    axes[1, 1].set_ylabel("Frozen CATE score")
    fig.suptitle("Prospective invariant-CATE reserve holdout")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def _plot_posthoc_diagnostics(
    calibration: pd.DataFrame,
    beta_sensitivity: pd.DataFrame,
    deciles: pd.DataFrame,
    output: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))

    x = np.arange(len(calibration))
    axes[0].bar(
        x - 0.18,
        calibration["observed_success_rate"],
        0.36,
        label="observed",
    )
    axes[0].bar(
        x + 0.18,
        calibration["mean_predicted_probability"],
        0.36,
        label="predicted",
    )
    axes[0].set_xticks(x, calibration["branch"])
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Success probability")
    axes[0].set_title("Potential-outcome calibration")
    axes[0].legend()

    axes[1].errorbar(
        beta_sensitivity["beta"],
        beta_sensitivity["adjusted_success_delta"],
        yerr=np.vstack(
            [
                beta_sensitivity["adjusted_success_delta"]
                - beta_sensitivity["adjusted_ci_low"],
                beta_sensitivity["adjusted_ci_high"]
                - beta_sensitivity["adjusted_success_delta"],
            ]
        ),
        marker="o",
        capsize=3,
    )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xlabel(r"Post-hoc epistemic penalty $\beta$")
    axes[1].set_ylabel("Cost-adjusted gain")
    axes[1].set_title("Sensitivity at frozen threshold")

    axes[2].plot(
        deciles["score_decile"],
        deciles["score_mean"],
        marker="o",
        label="predicted CATE",
    )
    axes[2].plot(
        deciles["score_decile"],
        deciles["observed_effect"],
        marker="o",
        label="observed effect",
    )
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_xlabel("Frozen-score decile")
    axes[2].set_ylabel("Effect")
    axes[2].set_title("Treatment-effect calibration")
    axes[2].legend()

    fig.suptitle("Post-hoc diagnostics (not confirmatory evidence)")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    router_path = Path(str(manifest["frozen_router"]))
    if not router_path.is_absolute():
        router_path = Path(__file__).resolve().parents[1] / router_path
    router = json.loads(router_path.read_text(encoding="utf-8"))

    all_pairs = load_pairs(campaign_dir)
    strict_source = all_pairs.loc[all_pairs["strict_integrity"]].reset_index(drop=True)
    strict = build_prequery_dataset(strict_source, campaign_dir)
    predictions = predict_frozen_cate(router, strict)
    strict = pd.concat([strict.reset_index(drop=True), predictions.reset_index(drop=True)], axis=1)
    query = strict["router_query"].to_numpy(bool)
    effect = strict["terminal_effect"].to_numpy(float)
    cost = float(manifest["query_cost"])
    strict["router_success"] = np.where(
        query, strict["feedback_success"], strict["commit_success"]
    ).astype(bool)

    policies = []
    for name, mask in (
        ("always_commit", np.zeros(len(strict), dtype=bool)),
        ("always_requery", np.ones(len(strict), dtype=bool)),
        ("frozen_invariant_cate", query),
        ("oracle_query", effect > 0),
    ):
        policies.append({"policy": name, **policy_row(strict, mask, cost)})
    policy_summary = pd.DataFrame(policies)
    router_row = policy_summary.loc[
        policy_summary["policy"].eq("frozen_invariant_cate")
    ].iloc[0]

    adjusted = query * effect - cost * query
    raw = query * effect
    always_adjusted = effect - cost
    versus_always = adjusted - always_adjusted
    raw_ci = _interval(strict, raw, manifest, 0)
    adjusted_ci = _interval(strict, adjusted, manifest, 1)
    versus_always_ci = _interval(strict, versus_always, manifest, 2)
    rescues = int(np.sum(query & (effect > 0)))
    harms = int(np.sum(query & (effect < 0)))
    mcnemar_p = (
        float(binomtest(min(rescues, harms), rescues + harms, 0.5).pvalue)
        if rescues + harms
        else 1.0
    )
    discordant = effect != 0
    auc = float(
        binary_auc(
            effect[discordant] > 0,
            np.where(strict.loc[discordant, "supported"], strict.loc[discordant, "router_score"], -1e6),
        )
    )

    cell_summary = _summarize_group(strict, ["position_level", "task_id"], cost)
    task_summary = _summarize_group(strict, ["task_id"], cost)
    potential_outcome_metrics = _potential_outcome_metrics(strict)
    beta_sensitivity, threshold_sensitivity = _posthoc_policy_sensitivity(
        strict, effect, cost, manifest
    )
    score_deciles = _effect_score_deciles(strict)
    novel_tasks = set(int(value) for value in manifest["novel_tasks"])
    novel = task_summary.loc[task_summary["task_id"].astype(int).isin(novel_tasks)]
    novel_macro = float(novel["adjusted_gain"].mean()) if len(novel) else float("nan")
    checks = {
        "strict_integrity_at_least_380": len(strict) >= int(manifest["minimum_strict_pairs"]),
        "raw_router_delta_positive": float(raw.mean()) > 0.0,
        "adjusted_cluster_ci_lower_positive": adjusted_ci[0] > 0.0,
        "query_rate_at_most_60pct": float(query.mean()) <= float(manifest["maximum_query_rate"]),
        "novel_task_macro_adjusted_nonnegative": novel_macro >= 0.0,
    }
    efficacy_pass = bool(all(checks.values()))
    strong_superiority = bool(versus_always_ci[0] > 0.0)
    decision = (
        "strong_promote_invariant_cate"
        if efficacy_pass and strong_superiority
        else "promote_budgeted_invariant_cate"
        if efficacy_pass
        else "do_not_promote_invariant_cate"
    )
    gate = {
        "expected_pairs": int(manifest["target_pairs"]),
        "all_pairs": len(all_pairs),
        "strict_pairs": len(strict),
        "router": router_row.to_dict(),
        "raw_cluster_ci": list(raw_ci),
        "adjusted_cluster_ci": list(adjusted_ci),
        "router_minus_always_requery_adjusted": float(versus_always.mean()),
        "router_minus_always_requery_adjusted_ci": list(versus_always_ci),
        "novel_task_macro_adjusted_gain": novel_macro,
        "rescue_vs_harm_auc": auc,
        "exact_mcnemar_pvalue": mcnemar_p,
        "checks": checks,
        "efficacy_pass": efficacy_pass,
        "strong_superiority_pass": strong_superiority,
        "decision": decision,
    }

    strict.to_parquet(output_dir / "strict_predictions.parquet", index=False)
    strict.to_csv(output_dir / "strict_predictions.csv", index=False)
    policy_summary.to_csv(output_dir / "policy_summary.csv", index=False)
    cell_summary.to_csv(output_dir / "cell_summary.csv", index=False)
    task_summary.to_csv(output_dir / "task_summary.csv", index=False)
    potential_outcome_metrics.to_csv(
        output_dir / "potential_outcome_calibration.csv", index=False
    )
    beta_sensitivity.to_csv(output_dir / "posthoc_beta_sensitivity.csv", index=False)
    threshold_sensitivity.to_csv(
        output_dir / "posthoc_threshold_sensitivity.csv", index=False
    )
    score_deciles.to_csv(output_dir / "effect_score_deciles.csv", index=False)
    (output_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    _plot(policy_summary, cell_summary, strict, output_dir / "invariant_cate_holdout.png")
    _plot_posthoc_diagnostics(
        potential_outcome_metrics,
        beta_sensitivity,
        score_deciles,
        output_dir / "invariant_cate_posthoc_diagnostics.png",
    )
    lines = [
        "# Frozen invariant-CATE reserve holdout",
        "",
        f"- Integrity: {len(strict)}/{manifest['target_pairs']} strict pairs.",
        f"- Commit/router SR: {100 * router_row['commit_success_rate']:.1f}% / {100 * router_row['policy_success_rate']:.1f}%.",
        f"- Query/support rate: {100 * query.mean():.1f}% / {100 * strict['supported'].mean():.1f}%.",
        f"- Raw gain: {100 * raw.mean():+.1f} pp, CI [{100 * raw_ci[0]:+.1f}, {100 * raw_ci[1]:+.1f}].",
        f"- Adjusted gain: {100 * adjusted.mean():+.1f} pp, CI [{100 * adjusted_ci[0]:+.1f}, {100 * adjusted_ci[1]:+.1f}].",
        f"- Router minus always-requery adjusted: {100 * versus_always.mean():+.1f} pp, CI [{100 * versus_always_ci[0]:+.1f}, {100 * versus_always_ci[1]:+.1f}].",
        f"- Selected rescues / harms: {rescues} / {harms}; AUROC {auc:.3f}; McNemar p={mcnemar_p:.6g}.",
        f"- Novel-task macro adjusted gain: {100 * novel_macro:+.1f} pp.",
        f"- Efficacy / strong-superiority gates: **{'PASS' if efficacy_pass else 'FAIL'}** / **{'PASS' if strong_superiority else 'FAIL'}**.",
        f"- Decision: `{decision}`.",
        "",
        "## Policies",
        "",
        policy_summary.to_markdown(index=False),
        "",
        "## Cells",
        "",
        cell_summary.to_markdown(index=False),
        "",
        "## Tasks",
        "",
        task_summary.to_markdown(index=False),
        "",
        "## Post-hoc diagnostics",
        "",
        "These diagnostics were computed after opening holdout outcomes. They explain failure modes but cannot be used as confirmatory model selection.",
        "",
        "### Potential-outcome calibration",
        "",
        potential_outcome_metrics.to_markdown(index=False),
        "",
        "### Epistemic-penalty sensitivity",
        "",
        beta_sensitivity.to_markdown(index=False),
        "",
        "### Frozen-score deciles",
        "",
        score_deciles.to_markdown(index=False),
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(gate, indent=2, default=lambda value: value.item() if isinstance(value, np.generic) else value))
    print(f"Results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

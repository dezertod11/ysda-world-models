#!/usr/bin/env python3
"""Diagnose score transfer and covariate shift after the signed-VoF holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_signed_vof_new_task_holdout import clustered_interval
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_signed_vof_new_task_holdout import clustered_interval


DEFAULT_COST = 0.025


def standardized_shift(
    frame: pd.DataFrame, payload: dict[str, object]
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    features = list(payload["active_features"])
    values = frame.loc[:, features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    preprocessing = payload["preprocessing"]
    median = np.asarray(preprocessing["impute_median"], dtype=float)
    mean = np.asarray(preprocessing["mean"], dtype=float)
    scale = np.asarray(preprocessing["scale"], dtype=float)
    values = np.where(np.isfinite(values), values, median)
    z = (values - mean) / scale
    coefficients = np.asarray(payload["ridge"]["coefficients"], dtype=float)[1:]
    return z, z * coefficients, features


def _policy_contrast(
    frame: pd.DataFrame,
    query: np.ndarray,
    *,
    cost: float,
    seed: int,
) -> dict[str, object]:
    effect = frame["terminal_effect"].to_numpy(float)
    query = np.asarray(query, dtype=bool)
    raw = query.astype(float) * effect
    adjusted = raw - cost * query.astype(float)
    raw_ci = clustered_interval(frame, raw, repetitions=10_000, seed=seed)
    adjusted_ci = clustered_interval(
        frame, adjusted, repetitions=10_000, seed=seed + 1
    )
    return {
        "query_rate": float(query.mean()),
        "raw_delta": float(raw.mean()),
        "raw_ci_low": raw_ci[0],
        "raw_ci_high": raw_ci[1],
        "adjusted_delta": float(adjusted.mean()),
        "adjusted_ci_low": adjusted_ci[0],
        "adjusted_ci_high": adjusted_ci[1],
        "rescues": int(np.sum(query & (effect > 0))),
        "harms": int(np.sum(query & (effect < 0))),
    }


def _cell_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (level, task_id), group in frame.groupby(["position_level", "task_id"], sort=True):
        effect = group["terminal_effect"].to_numpy(float)
        query = group["router_query"].to_numpy(bool)
        discordant = effect != 0
        rows.append(
            {
                "position_level": level,
                "task_id": int(task_id),
                "states": len(group),
                "commit_sr": float(group["commit_success"].mean()),
                "always_requery_sr": float(group["feedback_success"].mean()),
                "router_sr": float(group["router_success"].mean()),
                "always_requery_delta": float(effect.mean()),
                "router_delta": float(np.mean(query * effect)),
                "router_query_rate": float(query.mean()),
                "available_rescues": int(np.sum(effect > 0)),
                "available_harms": int(np.sum(effect < 0)),
                "selected_rescues": int(np.sum(query & (effect > 0))),
                "selected_harms": int(np.sum(query & (effect < 0))),
                "rescue_recall": float(np.mean(query[effect > 0])) if np.any(effect > 0) else float("nan"),
                "harm_avoidance": float(np.mean(~query[effect < 0])) if np.any(effect < 0) else float("nan"),
                "rescue_vs_harm_auc": binary_auc(effect[discordant] > 0, group.loc[discordant, "router_score"]),
                "score_median": float(group["router_score"].median()),
                "max_abs_train_z_median": float(group["max_abs_train_z"].median()),
                "max_abs_train_z_max": float(group["max_abs_train_z"].max()),
            }
        )
    return pd.DataFrame(rows)


def _plot(frame: pd.DataFrame, cells: pd.DataFrame, output: Path) -> None:
    labels = [f"{row.position_level}/t{row.task_id}" for row in cells.itertuples(index=False)]
    x = np.arange(len(cells))
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    width = 0.25
    axes[0, 0].bar(x - width, cells["commit_sr"], width, label="commit")
    axes[0, 0].bar(x, cells["always_requery_sr"], width, label="always requery")
    axes[0, 0].bar(x + width, cells["router_sr"], width, label="frozen router")
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].set_ylabel("Terminal success rate")
    axes[0, 0].legend(fontsize=9)

    axes[0, 1].bar(x - 0.18, cells["always_requery_delta"], 0.36, label="always requery")
    axes[0, 1].bar(x + 0.18, cells["router_delta"], 0.36, label="frozen router")
    axes[0, 1].axhline(0, color="black", linewidth=0.8)
    axes[0, 1].set_ylabel("Success delta vs commit")
    axes[0, 1].legend(fontsize=9)

    groups = [
        frame.loc[frame["terminal_effect"].eq(value), "router_score"].clip(-7, 7)
        for value in (-1, 0, 1)
    ]
    axes[1, 0].boxplot(groups, tick_labels=["harm (-1)", "neutral (0)", "rescue (+1)"], showfliers=False)
    axes[1, 0].axhline(float(frame["router_threshold"].iloc[0]), color="black", linestyle="--", label="frozen threshold")
    axes[1, 0].set_ylabel("Router score, clipped to [-7, 7]")
    axes[1, 0].legend(fontsize=9)

    z_groups = [
        frame.loc[
            frame["position_level"].eq(row.position_level) & frame["task_id"].eq(row.task_id),
            "max_abs_train_z",
        ]
        for row in cells.itertuples(index=False)
    ]
    axes[1, 1].boxplot(z_groups, tick_labels=labels, showfliers=False)
    axes[1, 1].set_yscale("log")
    axes[1, 1].axhline(5, color="black", linestyle="--", linewidth=0.8)
    axes[1, 1].set_ylabel("Largest |training z| per state (log scale)")

    for axis in axes.flat:
        if axis in (axes[0, 0], axes[0, 1]):
            axis.set_xticks(x, labels, rotation=30, ha="right")
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("Frozen signed-VoF transfer: causal opportunity but severe covariate shift")
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--query-cost", type=float, default=DEFAULT_COST)
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(args.predictions).copy()
    payload = json.loads(args.model.read_text(encoding="utf-8"))
    z, contributions, features = standardized_shift(frame, payload)
    frame["max_abs_train_z"] = np.max(np.abs(z), axis=1)
    frame["features_abs_z_gt5"] = np.sum(np.abs(z) > 5, axis=1)
    frame["features_abs_z_gt10"] = np.sum(np.abs(z) > 10, axis=1)

    feature_shift = pd.DataFrame(
        {
            "feature": features,
            "holdout_abs_z_median": np.median(np.abs(z), axis=0),
            "holdout_abs_z_p95": np.quantile(np.abs(z), 0.95, axis=0),
            "holdout_abs_z_max": np.max(np.abs(z), axis=0),
            "mean_abs_score_contribution": np.mean(np.abs(contributions), axis=0),
            "max_abs_score_contribution": np.max(np.abs(contributions), axis=0),
        }
    ).sort_values("max_abs_score_contribution", ascending=False)
    cells = _cell_diagnostics(frame)

    router_query = frame["router_query"].to_numpy(bool)
    contrasts = [
        {"policy": "always_commit", **_policy_contrast(frame, np.zeros(len(frame), bool), cost=args.query_cost, seed=20260910)},
        {"policy": "always_requery", **_policy_contrast(frame, np.ones(len(frame), bool), cost=args.query_cost, seed=20260920)},
        {"policy": "frozen_router", **_policy_contrast(frame, router_query, cost=args.query_cost, seed=20260930)},
    ]
    effect = frame["terminal_effect"].to_numpy(float)
    router_minus_always = router_query.astype(float) * effect - effect
    router_minus_always_adjusted = router_minus_always + args.query_cost * (~router_query)
    pairwise = {
        "router_minus_always_requery_raw": float(router_minus_always.mean()),
        "router_minus_always_requery_raw_ci": list(clustered_interval(frame, router_minus_always, repetitions=10_000, seed=20260940)),
        "router_minus_always_requery_adjusted": float(router_minus_always_adjusted.mean()),
        "router_minus_always_requery_adjusted_ci": list(clustered_interval(frame, router_minus_always_adjusted, repetitions=10_000, seed=20260941)),
    }
    cost_curve = []
    for cost in (0.0, 0.01, 0.025, 0.05, 0.075, 0.10):
        for name, query in (("always_requery", np.ones(len(frame), bool)), ("frozen_router", router_query)):
            cost_curve.append(
                {
                    "query_cost": cost,
                    "policy": name,
                    "query_rate": float(query.mean()),
                    "adjusted_delta": float(np.mean(query * effect - cost * query)),
                }
            )

    frame.to_parquet(output_dir / "shift_annotated_predictions.parquet", index=False)
    cells.to_csv(output_dir / "cell_router_diagnostics.csv", index=False)
    feature_shift.to_csv(output_dir / "feature_shift_summary.csv", index=False)
    pd.DataFrame(contrasts).to_csv(output_dir / "policy_contrast_intervals.csv", index=False)
    pd.DataFrame(cost_curve).to_csv(output_dir / "query_cost_sensitivity.csv", index=False)
    (output_dir / "router_vs_always_requery.json").write_text(json.dumps(pairwise, indent=2) + "\n", encoding="utf-8")
    _plot(frame, cells, output_dir / "signed_vof_transfer_diagnostics.png")

    row_z = frame["max_abs_train_z"]
    lines = [
        "# Signed-VoF holdout transfer diagnosis",
        "",
        f"Every holdout state is outside the task-0 feature support at |z|>5. The median row-wise maximum is {row_z.median():.1f}, the 95th percentile is {row_z.quantile(.95):.1f}, and the maximum is {row_z.max():.1f}.",
        "",
        "## Policy contrasts",
        "",
        pd.DataFrame(contrasts).to_markdown(index=False),
        "",
        f"Frozen routing is {100 * pairwise['router_minus_always_requery_raw']:+.1f} pp below always-requery before cost, with cluster CI [{100 * pairwise['router_minus_always_requery_raw_ci'][0]:+.1f}, {100 * pairwise['router_minus_always_requery_raw_ci'][1]:+.1f}].",
        "",
        "## Cell diagnostics",
        "",
        cells.to_markdown(index=False),
        "",
        "## Largest transfer shifts",
        "",
        feature_shift.head(12).to_markdown(index=False),
        "",
        "The task-0 linear score is therefore not transportable. Absolute gripper/action and proprio coordinates with tiny development variance produce unbounded extrapolation. Any support clipping or cell exclusion evaluated on these outcomes is post-hoc and cannot rescue the failed confirmatory claim.",
    ]
    (output_dir / "DIAGNOSTICS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Diagnostics: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline proxy evaluation for risk-aware Cosmos Policy planning.

The real planner ranks several candidate action chunks generated from the same
current state. Our logs do not yet store full candidate chunks, so this script
uses a conservative proxy: for each task/init/query it treats stochastic rollout
rows as candidate alternatives and asks which ranking rule would put a successful
trajectory first.

Scores are calibrated within the current candidate set, not by a global
threshold. This matches the planning use case: choose the best candidate among
alternatives, even when the absolute risk scale shifts between tasks/runs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_LAMBDAS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]


def _first_existing(df: pd.DataFrame, *names: str) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _candidate_z(group: pd.DataFrame, col: str | None) -> np.ndarray | None:
    if not col or col not in group.columns:
        return None
    values = group[col].to_numpy(dtype=float)
    mean = float(np.nanmean(values))
    std = float(np.nanstd(values))
    if not np.isfinite(std) or std < 1e-12:
        std = 1.0
    z = (values - mean) / std
    z[~np.isfinite(z)] = 0.0
    return z


def _mean_parts(parts: list[np.ndarray | None], n: int) -> np.ndarray:
    valid = [p for p in parts if p is not None]
    if not valid:
        return np.zeros(n, dtype=float)
    return np.mean(valid, axis=0)


def _risk_components(group: pd.DataFrame) -> pd.DataFrame:
    n = len(group)
    value_col = _first_existing(group, "value_mean", "prediction_value_executed_sample")
    value_z = _candidate_z(group, value_col)
    if value_z is None:
        value_z = np.zeros(n, dtype=float)

    value_std_z = _candidate_z(group, "value_std")
    value_range_z = _candidate_z(group, "value_range")
    latent_value_z = _candidate_z(group, "latent_value_element_std_mean_mean_over_samples")
    action_first_z = _candidate_z(group, "action_first_step_l2_std")
    latent_action_first_z = _candidate_z(group, "latent_action_first_step_copy_l2_std_mean_over_samples")
    future_image_z = _candidate_z(group, "future_image_pixel_std_mean")
    future_wrist_z = _candidate_z(group, "future_wrist_pixel_std_mean")

    risk_value_overconfidence = _mean_parts(
        [
            -value_std_z if value_std_z is not None else None,
            -value_range_z if value_range_z is not None else None,
            -latent_value_z if latent_value_z is not None else None,
            -0.5 * value_z,
        ],
        n,
    )
    risk_action_overconfidence = _mean_parts(
        [
            -action_first_z if action_first_z is not None else None,
            -latent_action_first_z if latent_action_first_z is not None else None,
        ],
        n,
    )
    risk_classic_high_uncertainty = _mean_parts(
        [value_std_z, value_range_z, action_first_z, future_image_z, future_wrist_z],
        n,
    )

    return pd.DataFrame(
        {
            "value_z": value_z,
            "risk_overconfidence_value": risk_value_overconfidence,
            "risk_overconfidence_action": risk_action_overconfidence,
            "risk_classic_high_uncertainty": risk_classic_high_uncertainty,
            "risk_combined_overconfidence": 0.5 * risk_value_overconfidence + 0.5 * risk_action_overconfidence,
        },
        index=group.index,
    )


def _group_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for col in ["source_run", "suite", "task_id", "init_state_id", "query_idx"]:
        if col in df.columns:
            cols.append(col)
    if "query_idx" not in cols:
        raise ValueError("Input must contain query_idx.")
    return cols


def score_candidates(df: pd.DataFrame, lambdas: list[float]) -> pd.DataFrame:
    frames = []
    group_cols = _group_columns(df)
    for group_key, group in df.groupby(group_cols, dropna=False):
        if len(group) < 2:
            continue
        if "success" not in group.columns:
            raise ValueError("Input must contain success labels for offline evaluation.")
        if group["success"].nunique(dropna=True) < 2:
            continue

        components = _risk_components(group)
        enriched = pd.concat([group.reset_index(drop=True), components.reset_index(drop=True)], axis=1)

        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        group_meta = dict(zip(group_cols, group_key))

        for risk_name in [
            "risk_overconfidence_value",
            "risk_overconfidence_action",
            "risk_combined_overconfidence",
            "risk_classic_high_uncertainty",
        ]:
            for lam in lambdas:
                score = enriched["value_z"].to_numpy(dtype=float) - lam * enriched[risk_name].to_numpy(dtype=float)
                winner_idx = int(np.nanargmax(score))
                winner = enriched.iloc[winner_idx]
                frames.append(
                    {
                        **group_meta,
                        "ranker": f"value_minus_{lam:g}x_{risk_name}",
                        "lambda": lam,
                        "risk_name": risk_name,
                        "num_candidates": len(enriched),
                        "num_success_candidates": int(enriched["success"].sum()),
                        "oracle_success_available": bool(enriched["success"].any()),
                        "chosen_rollout_seed": winner.get("rollout_seed", np.nan),
                        "chosen_rollout_id": winner.get("rollout_id", np.nan),
                        "chosen_success": bool(winner["success"]),
                        "chosen_value_z": float(winner["value_z"]),
                        "chosen_risk": float(winner[risk_name]),
                        "chosen_rank_score": float(score[winner_idx]),
                    }
                )
    return pd.DataFrame(frames)


def summarize_rankers(choice_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ranker, risk_name, lam), group in choice_df.groupby(["ranker", "risk_name", "lambda"], dropna=False):
        rows.append(
            {
                "ranker": ranker,
                "risk_name": risk_name,
                "lambda": lam,
                "num_candidate_sets": len(group),
                "success_rate_top1": float(group["chosen_success"].mean()),
                "oracle_success_available_rate": float(group["oracle_success_available"].mean()),
                "avg_candidates": float(group["num_candidates"].mean()),
                "avg_success_candidates": float(group["num_success_candidates"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    return summary.sort_values(["success_rate_top1", "lambda"], ascending=[False, True])


def plot_summary(summary: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for risk_name, sub in summary.groupby("risk_name"):
        sub = sub.sort_values("lambda")
        ax.plot(sub["lambda"], sub["success_rate_top1"], marker="o", label=risk_name)
    if not summary.empty:
        oracle = float(summary["oracle_success_available_rate"].max())
        ax.axhline(oracle, color="black", linestyle=":", linewidth=1.2, label="oracle success available")
    ax.set_xlabel("lambda")
    ax.set_ylabel("top-1 chosen success rate")
    ax.set_title("Offline proxy: risk-aware candidate ranking")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="Query metrics CSV.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-query", type=int, default=None)
    parser.add_argument("--lambdas", type=str, default=",".join(str(v) for v in DEFAULT_LAMBDAS))
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if args.max_query is not None:
        df = df[df["query_idx"] <= args.max_query].copy()

    lambdas = [float(x) for x in args.lambdas.split(",") if x.strip()]
    choices = score_candidates(df, lambdas)
    if choices.empty:
        raise SystemExit("No mixed success/fail candidate sets found.")

    summary = summarize_rankers(choices)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    choices.to_csv(args.output_dir / "planning_ranker_choices.csv", index=False)
    summary.to_csv(args.output_dir / "planning_ranker_summary.csv", index=False)
    plot_summary(summary, args.output_dir / "planning_ranker_success_rate_by_lambda.png")

    print("Top planning rankers:")
    print(summary.head(20).to_string(index=False))
    print(f"\nWrote {args.output_dir}")


if __name__ == "__main__":
    main()

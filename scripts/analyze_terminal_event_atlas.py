#!/usr/bin/env python3
"""Analyze terminal rescue/harm labels from exact-state commit-vs-requery branches."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import (
        VOF_FEATURES,
        binary_auc,
        grouped_category_mean_predictions,
        grouped_ridge_predictions,
        load_campaign,
    )
    from counterfactual_feedback_utils import deterministic_unit_interval
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import (
        VOF_FEATURES,
        binary_auc,
        grouped_category_mean_predictions,
        grouped_ridge_predictions,
        load_campaign,
    )
    from scripts.counterfactual_feedback_utils import deterministic_unit_interval


REPLAY_INTEGRITY_THRESHOLD = 1e-9
DEFAULT_BUDGETS = (0.05, 0.075, 0.10, 0.20)


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "yes"})


def prepare_terminal_frame(feedback: pd.DataFrame) -> pd.DataFrame:
    required = {"open_terminal_success", "feedback_terminal_success"}
    missing = sorted(required - set(feedback.columns))
    if missing:
        raise ValueError(f"Missing terminal columns: {missing}")

    frame = feedback.copy()
    frame["open_success"] = _as_bool(frame["open_terminal_success"])
    frame["feedback_success"] = _as_bool(frame["feedback_terminal_success"])
    frame["terminal_effect"] = (
        frame["feedback_success"].astype(int) - frame["open_success"].astype(int)
    )
    frame["rescue"] = frame["terminal_effect"].eq(1)
    frame["harm"] = frame["terminal_effect"].eq(-1)
    frame["both_success"] = frame["open_success"] & frame["feedback_success"]
    frame["both_fail"] = ~frame["open_success"] & ~frame["feedback_success"]
    frame["terminal_outcome"] = "both_fail"
    frame.loc[frame["both_success"], "terminal_outcome"] = "both_success"
    frame.loc[frame["rescue"], "terminal_outcome"] = "rescue"
    frame.loc[frame["harm"], "terminal_outcome"] = "harm"
    replay_error = pd.to_numeric(
        frame.get("main_open_replay_state_max_abs", pd.Series(np.nan, index=frame.index)),
        errors="coerce",
    )
    frame["strict_integrity"] = replay_error.le(REPLAY_INTEGRITY_THRESHOLD)
    frame["query_cost_numeric"] = pd.to_numeric(
        frame.get("query_cost", pd.Series(0.0, index=frame.index)), errors="coerce"
    ).fillna(0.0)
    frame["terminal_effect_after_cost"] = (
        frame["terminal_effect"] - frame["query_cost_numeric"]
    )
    snapshot_column = (
        "analysis_snapshot_id" if "analysis_snapshot_id" in frame else "snapshot_id"
    )
    frame["analysis_state_key"] = frame[snapshot_column].astype(str)
    frame["independent_group"] = (
        frame.get("source_run", pd.Series("", index=frame.index)).astype(str)
        + "|"
        + frame["suite"].astype(str)
        + "|"
        + frame["task_id"].astype(str)
        + "|"
        + frame["init_state_id"].astype(str)
    )
    return frame


def _binomial_discordance_pvalue(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return float("nan")
    tail = min(rescues, harms)
    probability = sum(math.comb(discordant, index) for index in range(tail + 1))
    return float(min(1.0, 2.0 * probability / (2**discordant)))


def _cluster_bootstrap_delta(
    frame: pd.DataFrame, *, seed: int = 20260901, repetitions: int = 5000
) -> tuple[float, float]:
    grouped = frame.groupby("independent_group")["terminal_effect"].agg(["sum", "size"])
    if grouped.empty:
        return float("nan"), float("nan")
    values = grouped[["sum", "size"]].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(repetitions, len(values)))
    sampled = values[draws]
    deltas = sampled[:, :, 0].sum(axis=1) / sampled[:, :, 1].sum(axis=1)
    return tuple(float(value) for value in np.quantile(deltas, [0.025, 0.975]))


def summarize_terminal_effect(
    frame: pd.DataFrame, group_columns: Sequence[str]
) -> pd.DataFrame:
    rows = []
    grouped: Iterable[tuple[object, pd.DataFrame]]
    if group_columns:
        grouped = frame.groupby(list(group_columns), dropna=False, sort=True)
    else:
        grouped = [((), frame)]
    for key, group in grouped:
        keys = key if isinstance(key, tuple) else (key,)
        rescues = int(group["rescue"].sum())
        harms = int(group["harm"].sum())
        ci_low, ci_high = _cluster_bootstrap_delta(group)
        row = dict(zip(group_columns, keys))
        row.update(
            {
                "states": int(len(group)),
                "independent_groups": int(group["independent_group"].nunique()),
                "open_success_rate": float(group["open_success"].mean()),
                "feedback_success_rate": float(group["feedback_success"].mean()),
                "success_delta": float(group["terminal_effect"].mean()),
                "success_delta_ci_low": ci_low,
                "success_delta_ci_high": ci_high,
                "rescues": rescues,
                "harms": harms,
                "net_rescues": rescues - harms,
                "discordance_rate": float((group["terminal_effect"] != 0).mean()),
                "both_success": int(group["both_success"].sum()),
                "both_fail": int(group["both_fail"].sum()),
                "mean_query_cost": float(group["query_cost_numeric"].mean()),
                "always_requery_adjusted_delta": float(
                    group["terminal_effect_after_cost"].mean()
                ),
                "discordance_pvalue": _binomial_discordance_pvalue(rescues, harms),
                "strict_integrity_states": int(group["strict_integrity"].sum()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def metric_diagnostics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    discordant = frame["terminal_effect"].ne(0)
    for feature in VOF_FEATURES:
        if feature not in frame:
            continue
        values = pd.to_numeric(frame[feature], errors="coerce")
        if values.notna().sum() < 10 or values.nunique(dropna=True) < 2:
            continue
        rescue_auc = binary_auc(frame["rescue"], values)
        discordant_auc = binary_auc(frame.loc[discordant, "rescue"], values[discordant])
        correlation = values.corr(frame["terminal_effect"], method="spearman")
        orientation_source = discordant_auc if np.isfinite(discordant_auc) else rescue_auc
        direction = "high" if orientation_source >= 0.5 else "low"
        rows.append(
            {
                "feature": feature,
                "available_states": int(values.notna().sum()),
                "spearman_terminal_effect": float(correlation),
                "rescue_vs_all_auc": float(rescue_auc),
                "rescue_vs_harm_auc": float(discordant_auc),
                "exploratory_direction": direction,
                "oriented_rescue_vs_harm_auc": float(
                    max(discordant_auc, 1.0 - discordant_auc)
                ),
            }
        )
    result = pd.DataFrame(rows)
    if len(result):
        result = result.sort_values(
            ["oriented_rescue_vs_harm_auc", "rescue_vs_all_auc"], ascending=False
        )
    return result


def _budget_row(
    frame: pd.DataFrame,
    scores: np.ndarray,
    *,
    method: str,
    budget: float,
) -> dict[str, object] | None:
    valid = np.isfinite(scores)
    if valid.sum() == 0:
        return None
    candidates = np.flatnonzero(valid)
    selected_count = max(1, int(math.ceil(len(frame) * budget)))
    selected_count = min(selected_count, len(candidates))
    order = candidates[np.argsort(scores[candidates], kind="mergesort")]
    selected = order[-selected_count:]
    chosen = frame.iloc[selected]
    return {
        "method": method,
        "budget": float(budget),
        "states": int(len(frame)),
        "selected": int(selected_count),
        "selected_rescues": int(chosen["rescue"].sum()),
        "selected_harms": int(chosen["harm"].sum()),
        "selected_rescue_rate": float(chosen["rescue"].mean()),
        "selected_harm_rate": float(chosen["harm"].mean()),
        "raw_success_delta": float(chosen["terminal_effect"].sum() / len(frame)),
        "adjusted_terminal_delta": float(
            chosen["terminal_effect_after_cost"].sum() / len(frame)
        ),
    }


def budget_analysis(
    frame: pd.DataFrame,
    diagnostics: pd.DataFrame,
    budgets: Sequence[float] = DEFAULT_BUDGETS,
) -> pd.DataFrame:
    ridge, _features = grouped_ridge_predictions(frame, "terminal_effect")
    phase_mean = grouped_category_mean_predictions(frame, "terminal_effect")
    random_scores = np.asarray(
        [
            deterministic_unit_interval("terminal-event-random", key)
            for key in frame["analysis_state_key"]
        ],
        dtype=float,
    )
    scores: dict[str, np.ndarray] = {
        "oracle": frame["terminal_effect"].to_numpy(dtype=float),
        "deterministic_random": random_scores,
        "grouped_oof_ridge": ridge,
        "factor_phase_oof_mean": phase_mean,
    }
    for row in diagnostics.head(8).itertuples(index=False):
        values = pd.to_numeric(frame[row.feature], errors="coerce").to_numpy(dtype=float)
        if row.exploratory_direction == "low":
            values = -values
        scores[f"exploratory_{row.feature}"] = values

    rows = []
    for method, method_scores in scores.items():
        for budget in budgets:
            row = _budget_row(frame, method_scores, method=method, budget=budget)
            if row is not None:
                rows.append(row)
    return pd.DataFrame(rows)


def event_transition_summary(frame: pd.DataFrame) -> pd.DataFrame:
    discordant = frame.loc[frame["terminal_effect"].ne(0)].copy()
    columns = [
        "factor",
        "terminal_outcome",
        "open_terminal_failure_type",
        "feedback_terminal_failure_type",
    ]
    available = [column for column in columns if column in discordant]
    if len(available) < 3:
        return pd.DataFrame()
    return (
        discordant.groupby(available, dropna=False)
        .size()
        .rename("states")
        .reset_index()
        .sort_values("states", ascending=False)
    )


def make_plots(
    factor_phase: pd.DataFrame, budgets: pd.DataFrame, output_dir: Path
) -> None:
    if len(factor_phase):
        plot = factor_phase.copy()
        plot["cell"] = plot["factor"].astype(str) + " / " + plot["phase_at_snapshot"].astype(str)
        fig, ax = plt.subplots(figsize=(10, 5.5))
        colors = ["#2d6a4f" if value >= 0 else "#b23a48" for value in plot["success_delta"]]
        ax.barh(plot["cell"], 100 * plot["success_delta"], color=colors)
        ax.axvline(0, color="black", linewidth=1)
        ax.set_xlabel("feedback minus commit terminal success, percentage points")
        ax.set_title("Exact-state terminal effect by LIBERO-PRO factor and phase")
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_dir / "terminal_effect_by_factor_phase.png", dpi=180)
        plt.close(fig)

    if len(budgets):
        focused = budgets.loc[
            budgets["method"].isin(
                ["oracle", "deterministic_random", "grouped_oof_ridge", "factor_phase_oof_mean"]
            )
        ]
        fig, ax = plt.subplots(figsize=(8, 5))
        for method, group in focused.groupby("method"):
            ax.plot(
                100 * group["budget"],
                100 * group["adjusted_terminal_delta"],
                marker="o",
                label=method,
            )
        ax.axhline(0, color="black", linewidth=1)
        ax.set_xlabel("requery budget, percent of states")
        ax.set_ylabel("compute-adjusted terminal gain, percentage points")
        ax.set_title("Terminal-aligned selective requery")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(output_dir / "terminal_budget_uplift.png", dpi=180)
        plt.close(fig)


def write_report(
    frame: pd.DataFrame,
    overall: pd.DataFrame,
    factor: pd.DataFrame,
    factor_phase: pd.DataFrame,
    diagnostics: pd.DataFrame,
    budgets: pd.DataFrame,
    transitions: pd.DataFrame,
    output_dir: Path,
) -> None:
    replay_error = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    top_budgets = budgets.loc[
        budgets["method"].ne("oracle") & budgets["budget"].isin([0.05, 0.075, 0.10])
    ].sort_values(["budget", "adjusted_terminal_delta"], ascending=[True, False])
    lines = [
        "# Terminal event atlas",
        "",
        f"- Exact-state pairs: **{len(frame)}** across **{frame['independent_group'].nunique()}** independent task/init groups.",
        f"- Rescue / harm: **{int(frame['rescue'].sum())} / {int(frame['harm'].sum())}**.",
        f"- Strict replay integrity: **{int(frame['strict_integrity'].sum())}/{len(frame)}** at `{REPLAY_INTEGRITY_THRESHOLD:g}`.",
        f"- Maximum replay error: **{replay_error.max():.3e}**.",
        "",
        "## Overall paired result",
        "",
        overall.to_markdown(index=False),
        "",
        "## By perturbation factor",
        "",
        factor.to_markdown(index=False),
        "",
        "## By factor and policy phase",
        "",
        factor_phase.to_markdown(index=False),
        "",
        "## Online metric diagnostics",
        "",
        diagnostics.head(20).to_markdown(index=False),
        "",
        "Directions marked exploratory are selected on this development sample and are not confirmatory.",
        "",
        "## Selective requery at low budgets",
        "",
        top_budgets.to_markdown(index=False),
        "",
        "## Discordant failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant transitions.",
        "",
        "## Interpretation",
        "",
        "- `terminal_effect=+1` is a rescue, `-1` is a harm, and `0` leaves terminal success unchanged.",
        "- Dense/local progress is auxiliary; deployment decisions are evaluated on terminal effect and query cost.",
        "- A selector advances only after grouped task/init holdout has positive adjusted terminal gain.",
        "- Cells with replay error above the threshold require strict-subset sensitivity analysis.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "terminal_event_atlas")
    output_dir.mkdir(parents=True, exist_ok=True)
    feedback, _candidates = load_campaign(campaign_dir)
    if feedback.empty:
        raise FileNotFoundError(f"No feedback pairs under {campaign_dir / 'runs'}")

    frame = prepare_terminal_frame(feedback)
    overall = summarize_terminal_effect(frame, ())
    factor = summarize_terminal_effect(frame, ("factor",))
    phase = summarize_terminal_effect(frame, ("phase_at_snapshot",))
    factor_phase = summarize_terminal_effect(frame, ("factor", "phase_at_snapshot"))
    task = summarize_terminal_effect(frame, ("factor", "task_id"))
    query = summarize_terminal_effect(frame, ("factor", "query_idx"))
    strict_factor = summarize_terminal_effect(
        frame.loc[frame["strict_integrity"]], ("factor",)
    )
    diagnostics = metric_diagnostics(frame)
    budgets = budget_analysis(frame, diagnostics)
    transitions = event_transition_summary(frame)

    frame.to_parquet(output_dir / "terminal_event_pairs.parquet", index=False)
    overall.to_csv(output_dir / "overall_summary.csv", index=False)
    factor.to_csv(output_dir / "factor_summary.csv", index=False)
    phase.to_csv(output_dir / "phase_summary.csv", index=False)
    factor_phase.to_csv(output_dir / "factor_phase_summary.csv", index=False)
    task.to_csv(output_dir / "task_summary.csv", index=False)
    query.to_csv(output_dir / "query_summary.csv", index=False)
    strict_factor.to_csv(output_dir / "strict_factor_summary.csv", index=False)
    diagnostics.to_csv(output_dir / "online_metric_diagnostics.csv", index=False)
    budgets.to_csv(output_dir / "terminal_budget_uplift.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    make_plots(factor_phase, budgets, output_dir)
    write_report(
        frame,
        overall,
        factor,
        factor_phase,
        diagnostics,
        budgets,
        transitions,
        output_dir,
    )

    summary = {
        "states": int(len(frame)),
        "independent_groups": int(frame["independent_group"].nunique()),
        "rescues": int(frame["rescue"].sum()),
        "harms": int(frame["harm"].sum()),
        "net_rescues": int(frame["terminal_effect"].sum()),
        "open_success_rate": float(frame["open_success"].mean()),
        "feedback_success_rate": float(frame["feedback_success"].mean()),
        "strict_integrity_states": int(frame["strict_integrity"].sum()),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

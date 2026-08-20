#!/usr/bin/env python3
"""Analyze the matched 2x2 candidate-selection x feedback-horizon experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_adaptive_planning_campaign import (
    PAIR_KEYS,
    episode_table,
    exact_mcnemar_p,
    load_traces,
)


STRATEGIES = {
    "baseline": "max_value",
    "selection_only": "action_l1",
    "horizon_only": "horizon_only_l1_h8",
    "combined": "requery_l1_h8",
}

EFFECTS: Mapping[str, tuple[tuple[str, float], ...]] = {
    "selection_at_full_horizon": (("selection_only", 1.0), ("baseline", -1.0)),
    "horizon_with_max_value": (("horizon_only", 1.0), ("baseline", -1.0)),
    "horizon_with_risk_selection": (("combined", 1.0), ("selection_only", -1.0)),
    "selection_at_adaptive_horizon": (("combined", 1.0), ("horizon_only", -1.0)),
    "combined_vs_baseline": (("combined", 1.0), ("baseline", -1.0)),
    "factorial_interaction": (
        ("combined", 1.0),
        ("selection_only", -1.0),
        ("horizon_only", -1.0),
        ("baseline", 1.0),
    ),
}


def build_seed_table(
    episodes: pd.DataFrame,
    strategies: Mapping[str, str] = STRATEGIES,
) -> pd.DataFrame:
    """Return one complete matched row per case/init/seed."""
    selected = episodes.loc[episodes["strategy_id"].isin(strategies.values())].copy()
    duplicates = selected.duplicated(PAIR_KEYS + ["strategy_id"], keep=False)
    if duplicates.any():
        example = selected.loc[duplicates, PAIR_KEYS + ["strategy_id"]].head()
        raise ValueError(f"Duplicate strategy executions for matched keys:\n{example}")

    success = selected.pivot(index=PAIR_KEYS, columns="strategy_id", values="success")
    queries = selected.pivot(
        index=PAIR_KEYS, columns="strategy_id", values="num_queries_observed"
    )
    missing = sorted(set(strategies.values()) - set(success.columns))
    if missing:
        raise ValueError(f"Missing required strategies: {missing}")

    complete = success[list(strategies.values())].notna().all(axis=1)
    success = success.loc[complete]
    queries = queries.reindex(success.index)
    if success.empty:
        raise ValueError("No complete four-strategy matched seeds")

    result = success.reset_index()[PAIR_KEYS].copy()
    for role, strategy_id in strategies.items():
        result[f"success__{role}"] = success[strategy_id].astype(int).to_numpy()
        result[f"queries__{role}"] = pd.to_numeric(
            queries[strategy_id], errors="coerce"
        ).to_numpy()
    return add_effect_columns(result)


def add_effect_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for effect, terms in EFFECTS.items():
        result[f"effect__{effect}"] = sum(
            coefficient * result[f"success__{role}"] for role, coefficient in terms
        )
    return result


def stratified_ci(
    frame: pd.DataFrame,
    column: str,
    *,
    samples: int = 20000,
    seed: int = 20260820,
) -> tuple[float, float]:
    groups = [
        group[column].to_numpy(dtype=float)
        for _, group in frame.groupby("case_id", sort=True)
    ]
    rng = np.random.default_rng(seed)
    estimates = np.empty(samples, dtype=float)
    for index in range(samples):
        draws = [values[rng.integers(0, len(values), len(values))] for values in groups]
        estimates[index] = np.concatenate(draws).mean()
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def effect_summary(seed_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for effect in EFFECTS:
        column = f"effect__{effect}"
        values = seed_table[column].astype(float)
        low, high = stratified_ci(seed_table, column)
        simple_contrast = bool(values.isin([-1.0, 0.0, 1.0]).all()) and effect != "factorial_interaction"
        wins = int(values.eq(1.0).sum()) if simple_contrast else None
        losses = int(values.eq(-1.0).sum()) if simple_contrast else None
        rows.append(
            {
                "effect": effect,
                "paired_rollouts": len(values),
                "mean_effect": float(values.mean()),
                "ci_low": low,
                "ci_high": high,
                "wins": wins,
                "losses": losses,
                "ties": int(values.eq(0.0).sum()) if simple_contrast else None,
                "mcnemar_exact_p": (
                    exact_mcnemar_p(wins, losses)
                    if simple_contrast and wins is not None and losses is not None
                    else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows)


def effect_summary_by_case(seed_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for case_id, group in seed_table.groupby("case_id", sort=True):
        for effect in EFFECTS:
            values = group[f"effect__{effect}"].astype(float)
            rows.append(
                {
                    "case_id": case_id,
                    "effect": effect,
                    "paired_rollouts": len(values),
                    "mean_effect": float(values.mean()),
                }
            )
    return pd.DataFrame(rows)


def strategy_summary(seed_table: pd.DataFrame) -> pd.DataFrame:
    baseline_queries = seed_table["queries__baseline"].mean()
    rows = []
    for role, strategy_id in STRATEGIES.items():
        rows.append(
            {
                "role": role,
                "strategy_id": strategy_id,
                "rollouts": len(seed_table),
                "successes": int(seed_table[f"success__{role}"].sum()),
                "success_rate": float(seed_table[f"success__{role}"].mean()),
                "mean_queries": float(seed_table[f"queries__{role}"].mean()),
                "query_count_ratio_vs_baseline": float(
                    seed_table[f"queries__{role}"].mean() / baseline_queries
                ),
            }
        )
    return pd.DataFrame(rows)


def save_plots(
    strategies: pd.DataFrame,
    effects: pd.DataFrame,
    output_dir: Path,
) -> None:
    plots = output_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    colors = ["#4a5568", "#2b6cb0", "#c05621", "#2f855a"]
    axes[0].bar(strategies["role"], strategies["success_rate"], color=colors)
    axes[0].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("Success rate")
    axes[0].tick_params(axis="x", rotation=20)
    axes[1].bar(
        strategies["role"], strategies["query_count_ratio_vs_baseline"], color=colors
    )
    axes[1].axhline(1.0, color="black", linewidth=1)
    axes[1].set_ylabel("Query count / baseline")
    axes[1].tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(plots / "factorial_strategy_success_cost.png", dpi=180)
    plt.close(fig)

    ordered = effects.copy()
    lower = ordered["mean_effect"] - ordered["ci_low"]
    upper = ordered["ci_high"] - ordered["mean_effect"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(
        ordered["effect"],
        ordered["mean_effect"],
        xerr=np.vstack([lower.clip(lower=0), upper.clip(lower=0)]),
        color="#2b6cb0",
        error_kw={"ecolor": "#1a202c", "capsize": 3},
    )
    ax.axvline(0.0, color="black", linewidth=1)
    ax.set_xlabel("Paired success-rate effect")
    fig.tight_layout()
    fig.savefig(plots / "factorial_effects.png", dpi=180)
    plt.close(fig)


def write_report(
    output_dir: Path,
    strategies: pd.DataFrame,
    effects: pd.DataFrame,
    by_case: pd.DataFrame,
) -> None:
    lookup = effects.set_index("effect")
    selection = lookup.loc["selection_at_full_horizon"]
    horizon = lookup.loc["horizon_with_max_value"]
    combined = lookup.loc["combined_vs_baseline"]
    interaction = lookup.loc["factorial_interaction"]
    lines = [
        "# Candidate selection x feedback horizon",
        "",
        "Matched 2x2 experiment on identical task, initial state, and rollout seed.",
        "",
        "- baseline: max(value), execute 16 actions",
        "- selection only: risk-aware candidate, execute 16 actions",
        "- horizon only: max(value) candidate, but execute 8 actions on disagreement",
        "- combined: risk-aware candidate and execute 8 actions on disagreement",
        "",
        "## Main causal contrasts",
        "",
        f"- Selection alone: {100 * selection['mean_effect']:+.1f} pp "
        f"(95% CI {100 * selection['ci_low']:+.1f} to {100 * selection['ci_high']:+.1f}).",
        f"- Adaptive feedback alone: {100 * horizon['mean_effect']:+.1f} pp "
        f"(95% CI {100 * horizon['ci_low']:+.1f} to {100 * horizon['ci_high']:+.1f}).",
        f"- Combined policy: {100 * combined['mean_effect']:+.1f} pp "
        f"(95% CI {100 * combined['ci_low']:+.1f} to {100 * combined['ci_high']:+.1f}).",
        f"- Factorial interaction: {100 * interaction['mean_effect']:+.1f} pp "
        f"(95% CI {100 * interaction['ci_low']:+.1f} to {100 * interaction['ci_high']:+.1f}).",
        "",
        "The interaction is exploratory; simple pairwise contrasts use exact McNemar tests,",
        "and all intervals use a case-stratified paired bootstrap.",
        "",
        "![Strategy success and query cost](plots/factorial_strategy_success_cost.png)",
        "",
        "![Factorial effects](plots/factorial_effects.png)",
        "",
        "## Strategy summary",
        "",
        strategies.to_markdown(index=False),
        "",
        "## Pooled effects",
        "",
        effects.to_markdown(index=False),
        "",
        "## Effects by case",
        "",
        by_case.to_markdown(index=False),
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    campaign_dir = args.campaign_dir.resolve()
    output_dir = (
        args.output_dir or campaign_dir / "analysis" / "selection_horizon_factorial"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    episodes = episode_table(load_traces([campaign_dir]))
    seeds = build_seed_table(episodes)
    effects = effect_summary(seeds)
    by_case = effect_summary_by_case(seeds)
    strategies = strategy_summary(seeds)

    seeds.to_csv(output_dir / "factorial_seed_outcomes.csv", index=False)
    effects.to_csv(output_dir / "factorial_effects_pooled.csv", index=False)
    by_case.to_csv(output_dir / "factorial_effects_by_case.csv", index=False)
    strategies.to_csv(output_dir / "factorial_strategy_summary.csv", index=False)
    save_plots(strategies, effects, output_dir)
    write_report(output_dir, strategies, effects, by_case)
    summary = {
        "campaign": campaign_dir.name,
        "complete_matched_seeds": len(seeds),
        "cases": int(seeds["case_id"].nunique()),
        "strategies": STRATEGIES,
        "effects": json.loads(effects.to_json(orient="records")),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(effects.to_string(index=False))
    print(f"[factorial] report={output_dir / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Evaluate the preregistered K16 terminal proposal-opportunity screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import (
        add_advantage_target,
        opportunity_table,
        read_candidates,
        validate_candidate_sets,
    )
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from terminal_grounded_critic import (
        add_advantage_target,
        opportunity_table,
        read_candidates,
        validate_candidate_sets,
    )


DEFAULT_SEED = 20260830
DEFAULT_BOOTSTRAP_SAMPLES = 5000


def _grouped_bootstrap_interval(
    states: pd.DataFrame,
    *,
    samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, float]:
    """Bootstrap state-mean SR metrics by independent task/init clusters."""
    grouped = (
        states.groupby("independent_group", as_index=False)
        .agg(
            states=("analysis_snapshot_id", "size"),
            maxv_successes=("maxv_success", "sum"),
            oracle_successes=("oracle_success", "sum"),
        )
        .reset_index(drop=True)
    )
    if grouped.empty:
        raise ValueError("Cannot bootstrap an empty state table")

    counts = grouped["states"].to_numpy(dtype=float)
    maxv = grouped["maxv_successes"].to_numpy(dtype=float)
    oracle = grouped["oracle_successes"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(grouped), size=(samples, len(grouped)))
    sampled_count = counts[draws].sum(axis=1)
    sampled_maxv = maxv[draws].sum(axis=1) / sampled_count
    sampled_oracle = oracle[draws].sum(axis=1) / sampled_count
    sampled_gap_pp = 100.0 * (sampled_oracle - sampled_maxv)

    def interval(values: np.ndarray) -> tuple[float, float]:
        low, high = np.quantile(values, [0.025, 0.975])
        return float(low), float(high)

    maxv_low, maxv_high = interval(sampled_maxv)
    oracle_low, oracle_high = interval(sampled_oracle)
    gap_low, gap_high = interval(sampled_gap_pp)
    return {
        "maxv_sr_ci_low": maxv_low,
        "maxv_sr_ci_high": maxv_high,
        "oracle_sr_ci_low": oracle_low,
        "oracle_sr_ci_high": oracle_high,
        "oracle_gap_pp_ci_low": gap_low,
        "oracle_gap_pp_ci_high": gap_high,
    }


def _summarize_rows(
    states: pd.DataFrame,
    keys: Iterable[str],
    *,
    bootstrap_samples: int,
    seed: int,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    keys = list(keys)
    grouper: str | list[str] = keys[0] if len(keys) == 1 else keys
    for group_values, group in states.groupby(grouper, dropna=False, sort=True):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        record = dict(zip(keys, group_values))
        maxv_sr = float(group["maxv_success"].mean())
        oracle_sr = float(group["oracle_success"].mean())
        record.update(
            {
                "states": int(len(group)),
                "independent_groups": int(group["independent_group"].nunique()),
                "candidates_min": int(group["candidates"].min()),
                "candidates_max": int(group["candidates"].max()),
                "heterogeneous_states": int(group["outcome_heterogeneous"].sum()),
                "success_rescues": int(group["success_rescue"].sum()),
                "all_candidates_fail": int(group["all_candidates_fail"].sum()),
                "all_candidates_succeed": int(group["all_candidates_succeed"].sum()),
                "maxv_sr": maxv_sr,
                "oracle_sr": oracle_sr,
                "oracle_gap_pp": 100.0 * (oracle_sr - maxv_sr),
                "maxv_utility": float(group["maxv_utility"].mean()),
                "oracle_utility": float(group["oracle_utility"].mean()),
            }
        )
        record.update(
            _grouped_bootstrap_interval(
                group,
                samples=bootstrap_samples,
                seed=seed + len(records),
            )
        )
        record["selector_gate_pass"] = bool(
            record["success_rescues"] > 0 and record["oracle_gap_pp"] >= 5.0
        )
        records.append(record)
    return pd.DataFrame.from_records(records)


def _historical_budget_summary(states: pd.DataFrame) -> pd.DataFrame:
    result = (
        states.groupby(["campaign", "factor", "candidates"], as_index=False)
        .agg(
            states=("analysis_snapshot_id", "size"),
            independent_groups=("independent_group", "nunique"),
            heterogeneous_states=("outcome_heterogeneous", "sum"),
            success_rescues=("success_rescue", "sum"),
            all_candidates_fail=("all_candidates_fail", "sum"),
            maxv_sr=("maxv_success", "mean"),
            oracle_sr=("oracle_success", "mean"),
        )
        .reset_index(drop=True)
    )
    result["oracle_gap_pp"] = 100.0 * (result["oracle_sr"] - result["maxv_sr"])
    return result.sort_values(["factor", "candidates", "campaign"]).reset_index(drop=True)


def _nested_budget_states(
    candidate_files: Iterable[Path], budgets: tuple[int, ...] = (4, 8, 16)
) -> pd.DataFrame:
    candidates = read_candidates(list(candidate_files), require_features=False)
    full_count = validate_candidate_sets(candidates)
    if full_count < max(budgets):
        raise ValueError(
            f"Nested K{max(budgets)} analysis requires at least {max(budgets)} "
            f"candidates per state, found {full_count}"
        )
    expected_indices = set(range(full_count))
    observed_indices = candidates.groupby("analysis_snapshot_id")["candidate_idx"].agg(
        lambda values: set(int(value) for value in values)
    )
    if not observed_indices.map(lambda values: values == expected_indices).all():
        raise ValueError("Candidate indices must be contiguous and start at zero")

    parts: list[pd.DataFrame] = []
    for budget in budgets:
        subset = candidates.loc[candidates["candidate_idx"].lt(budget)].copy()
        validate_candidate_sets(subset)
        subset = add_advantage_target(subset)
        states = opportunity_table(subset)
        states["all_candidates_fail"] = ~states["oracle_success"]
        states["all_candidates_succeed"] = (
            states["maxv_success"] & ~states["outcome_heterogeneous"]
        )
        states["budget"] = int(budget)
        parts.append(states)
    return pd.concat(parts, ignore_index=True)


def _plot_summary(
    factor_summary: pd.DataFrame,
    nested_budget_summary: pd.DataFrame,
    destination: Path,
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    x = np.arange(len(factor_summary))
    width = 0.36
    axes[0].bar(x - width / 2, factor_summary["maxv_sr"], width, label="max(value)")
    axes[0].bar(x + width / 2, factor_summary["oracle_sr"], width, label="oracle in pool")
    axes[0].set_xticks(x, factor_summary["factor"])
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Terminal success rate")
    axes[0].set_title("K16 opportunity")
    axes[0].legend(loc="lower right")
    axes[0].grid(axis="y", alpha=0.25)

    bottom = np.zeros(len(factor_summary), dtype=float)
    for column, label in (
        ("all_candidates_fail", "all fail"),
        ("heterogeneous_states", "mixed"),
        ("all_candidates_succeed", "all succeed"),
    ):
        fraction = factor_summary[column].to_numpy(dtype=float) / factor_summary[
            "states"
        ].to_numpy(dtype=float)
        axes[1].bar(x, fraction, bottom=bottom, label=label)
        bottom += fraction
    axes[1].set_xticks(x, factor_summary["factor"])
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_ylabel("Fraction of exact-state pools")
    axes[1].set_title("Candidate-pool composition")
    axes[1].legend(loc="best")
    axes[1].grid(axis="y", alpha=0.25)

    for factor, group in nested_budget_summary.groupby("factor", sort=True):
        group = group.sort_values("budget")
        axes[2].plot(
            group["budget"],
            group["oracle_gap_pp"],
            marker="o",
            linewidth=1.8,
            label=factor,
        )
    axes[2].axhline(5.0, color="black", linestyle="--", linewidth=1.0, label="gate 5 pp")
    axes[2].set_xlabel("Candidates K")
    axes[2].set_ylabel("Oracle gap, pp")
    axes[2].set_xticks(sorted(nested_budget_summary["budget"].unique()))
    axes[2].set_title("Paired nested proposal budgets")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="best")

    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def _format_report_table(table: pd.DataFrame) -> pd.DataFrame:
    shown = table.copy()
    for column in ("maxv_sr", "oracle_sr"):
        if column in shown:
            shown[column] = (100.0 * shown[column]).map(lambda value: f"{value:.1f}%")
    for column in (
        "oracle_gap_pp",
        "oracle_gap_pp_ci_low",
        "oracle_gap_pp_ci_high",
    ):
        if column in shown:
            shown[column] = shown[column].map(lambda value: f"{value:.1f}")
    if "selector_gate_pass" in shown:
        shown["selector_gate_pass"] = shown["selector_gate_pass"].map(
            {True: "PASS", False: "FAIL"}
        )
    return shown


def _write_report(
    output_dir: Path,
    campaign: str,
    factor_summary: pd.DataFrame,
    cell_summary: pd.DataFrame,
    nested_budget_summary: pd.DataFrame,
    hard_factor_hypothesis: bool,
) -> None:
    factor_columns = [
        "factor",
        "states",
        "independent_groups",
        "heterogeneous_states",
        "success_rescues",
        "all_candidates_fail",
        "all_candidates_succeed",
        "maxv_sr",
        "oracle_sr",
        "oracle_gap_pp",
        "oracle_gap_pp_ci_low",
        "oracle_gap_pp_ci_high",
        "selector_gate_pass",
    ]
    cell_columns = [
        "factor",
        "case_id",
        "suite",
        "task_id",
        "query_idx",
        "states",
        "heterogeneous_states",
        "success_rescues",
        "all_candidates_fail",
        "maxv_sr",
        "oracle_sr",
        "oracle_gap_pp",
        "selector_gate_pass",
    ]
    nested_columns = [
        "factor",
        "budget",
        "states",
        "heterogeneous_states",
        "success_rescues",
        "all_candidates_fail",
        "maxv_sr",
        "oracle_sr",
        "oracle_gap_pp",
    ]
    passed = factor_summary.loc[factor_summary["selector_gate_pass"], "factor"].tolist()
    failed = factor_summary.loc[~factor_summary["selector_gate_pass"], "factor"].tolist()
    routing_lines: list[str] = []
    if passed:
        routing_lines.extend(
            [
                f"- Selector gate прошли: {', '.join(passed)}.",
                "- Для этих факторов следующий test: action-conditioned",
                "  autoregressive `action -> future -> value` на сохранённых",
                "  candidates, затем frozen closed-loop проверка.",
            ]
        )
    if failed:
        routing_lines.extend(
            [
                f"- Selector gate не прошли: {', '.join(failed)}.",
                "- Для них запрещён очередной retuning score: нужны новые",
                "  proposals, ранний feedback/requery или recovery policy.",
            ]
        )

    lines = [
        "# K16 proposal-opportunity screen: results",
        "",
        f"Campaign: `{campaign}`.",
        "",
        "Анализ следует зафиксированному до сбора протоколу",
        "`experiments/PROPOSAL_OPPORTUNITY_K16_PROTOCOL_20260830.md`.",
        "Candidate labels не использовались для выбора cells, seeds или gate.",
        "",
        "## Основной вопрос",
        "",
        "Проверяется наличие успешной альтернативы внутри K16 pool, а не качество",
        "нового selector. `Oracle gap = SR_oracle - SR_maxV`; selector разрешён",
        "только при хотя бы одном rescue и point estimate gap не менее 5 п.п.",
        "95% интервалы рассчитаны cluster bootstrap по `task/init_state`.",
        "",
        "## Factor-level result",
        "",
        _format_report_table(factor_summary[factor_columns]).to_markdown(index=False),
        "",
        "## Task/query diagnostics",
        "",
        _format_report_table(cell_summary[cell_columns]).to_markdown(index=False),
        "",
        "## Paired nested K4/K8/K16",
        "",
        "Первые 4 и 8 candidate seeds каждого K16 pool образуют вложенные",
        "proposal sets. Поэтому эта таблица сравнивает candidate budget на тех же",
        "exact states; в отличие от исторических кампаний это paired evidence.",
        "",
        _format_report_table(nested_budget_summary[nested_columns]).to_markdown(
            index=False
        ),
        "",
        "## Решение",
        "",
        (
            "Гипотеза о появлении terminal candidate choice хотя бы в одном "
            "Environment/Position factor: **SUPPORTED**."
            if hard_factor_hypothesis
            else "Гипотеза о появлении terminal candidate choice в Environment/Position: **NOT SUPPORTED**."
        ),
        "",
        *routing_lines,
        "",
        "Отдельный historical CSV оставлен только для контекста: старые K4/K8",
        "кампании имеют другие init states и не заменяют paired nested comparison.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(
    atlas_dir: Path,
    campaign: str,
    output_dir: Path,
    candidate_files: Iterable[Path],
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    states = pd.read_csv(atlas_dir / "opportunity_states.csv")
    selected = states.loc[states["campaign"].eq(campaign)].copy()
    if selected.empty:
        campaigns = ", ".join(sorted(states["campaign"].astype(str).unique()))
        raise ValueError(f"Campaign {campaign!r} absent from atlas; found: {campaigns}")

    factor_summary = _summarize_rows(
        selected,
        ["factor"],
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    cell_summary = _summarize_rows(
        selected,
        [
            "factor",
            "case_id",
            "suite",
            "task_id",
            "task_description",
            "query_idx",
        ],
        bootstrap_samples=bootstrap_samples,
        seed=seed + 1000,
    )
    historical = _historical_budget_summary(states)
    nested_states = _nested_budget_states(candidate_files)
    nested_budget_summary = _summarize_rows(
        nested_states,
        ["factor", "budget"],
        bootstrap_samples=bootstrap_samples,
        seed=seed + 2000,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    factor_summary.to_csv(output_dir / "factor_summary.csv", index=False)
    cell_summary.to_csv(output_dir / "task_query_summary.csv", index=False)
    historical.to_csv(output_dir / "historical_candidate_budget_summary.csv", index=False)
    nested_budget_summary.to_csv(output_dir / "nested_budget_summary.csv", index=False)
    _plot_summary(
        factor_summary,
        nested_budget_summary,
        output_dir / "k16_opportunity_summary.png",
    )

    hard = factor_summary.loc[factor_summary["factor"].isin(["Environment", "Position"])]
    hard_factor_hypothesis = bool(
        (hard["success_rescues"].gt(0) & hard["oracle_gap_pp"].gt(0.0)).any()
    )
    _write_report(
        output_dir,
        campaign,
        factor_summary,
        cell_summary,
        nested_budget_summary,
        hard_factor_hypothesis,
    )
    summary = {
        "campaign": campaign,
        "states": int(len(selected)),
        "independent_groups": int(selected["independent_group"].nunique()),
        "candidate_branches": int(selected["candidates"].sum()),
        "hard_factor_hypothesis_supported": hard_factor_hypothesis,
        "selector_eligible_factors": factor_summary.loc[
            factor_summary["selector_gate_pass"], "factor"
        ].tolist(),
        "factor_results": factor_summary.to_dict(orient="records"),
        "nested_budget_results": nested_budget_summary.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas-dir", type=Path, required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    print(
        json.dumps(
            analyze(
                args.atlas_dir,
                args.campaign,
                args.output_dir,
                args.candidate_files,
                bootstrap_samples=args.bootstrap_samples,
                seed=args.seed,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Diagnose within-state value misranking in terminal candidate pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import read_candidates, validate_candidate_sets
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from terminal_grounded_critic import read_candidates, validate_candidate_sets


def _as_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).lower() in {"1", "true", "yes"}


def _pairwise_accuracy(success_values: np.ndarray, failure_values: np.ndarray) -> float:
    differences = success_values[:, None] - failure_values[None, :]
    return float(np.mean((differences > 0).astype(float) + 0.5 * (differences == 0)))


def _selected(group: pd.DataFrame, budget: int) -> pd.Series:
    scoped = group.loc[group["candidate_idx"].lt(budget)]
    return scoped.loc[scoped["candidate_value"].idxmax()]


def state_diagnostics(candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for snapshot, group in candidates.groupby("analysis_snapshot_id", sort=False):
        group = group.sort_values("candidate_idx").copy()
        successes = group.loc[group["terminal_success_bool"]]
        failures = group.loc[~group["terminal_success_bool"]]
        top = group.loc[group["candidate_value"].idxmax()]
        row: dict[str, object] = {
            "analysis_snapshot_id": snapshot,
            "factor": str(group["factor"].iloc[0]),
            "case_id": str(group.get("case_id", pd.Series("unknown")).iloc[0]),
            "suite": str(group["suite"].iloc[0]),
            "task_id": int(group["task_id"].iloc[0]),
            "task_description": str(group["task_description"].iloc[0]),
            "init_state_id": int(group["init_state_id"].iloc[0]),
            "query_idx": int(group["query_idx"].iloc[0]),
            "phase": str(group.get("phase_at_snapshot", pd.Series("unknown")).iloc[0]),
            "candidates": int(len(group)),
            "successful_candidates": int(len(successes)),
            "outcome_heterogeneous": bool(not successes.empty and not failures.empty),
            "all_candidates_fail": bool(successes.empty),
            "all_candidates_succeed": bool(failures.empty),
            "successful_candidate_indices": json.dumps(
                successes["candidate_idx"].astype(int).tolist()
            ),
            "successful_candidate_seeds": json.dumps(
                successes.get("candidate_seed", successes["candidate_idx"])
                .astype(int)
                .tolist()
            ),
            "top_candidate_idx": int(top["candidate_idx"]),
            "top_candidate_seed": int(top.get("candidate_seed", top["candidate_idx"])),
            "top_candidate_value": float(top["candidate_value"]),
            "top_candidate_success": bool(top["terminal_success_bool"]),
            "top_candidate_failure_type": str(top.get("terminal_failure_type", "unknown")),
            "top_candidate_drop": _as_bool(
                top.get("terminal_target_drop_candidate", False)
            ),
            "top_candidate_wrong_object": _as_bool(
                top.get("terminal_wrong_object_interaction_candidate", False)
            ),
            "top_candidate_safety_violation": _as_bool(
                top.get("terminal_official_safety_violation", False)
            ),
        }
        if successes.empty:
            row.update(
                {
                    "best_success_candidate_idx": np.nan,
                    "best_success_candidate_seed": np.nan,
                    "best_success_value": np.nan,
                    "top_over_best_success_margin": np.nan,
                }
            )
        else:
            best_success = successes.loc[successes["candidate_value"].idxmax()]
            row.update(
                {
                    "best_success_candidate_idx": int(best_success["candidate_idx"]),
                    "best_success_candidate_seed": int(
                        best_success.get("candidate_seed", best_success["candidate_idx"])
                    ),
                    "best_success_value": float(best_success["candidate_value"]),
                    "top_over_best_success_margin": float(
                        top["candidate_value"] - best_success["candidate_value"]
                    ),
                }
            )
        row["within_state_value_pairwise_accuracy"] = (
            _pairwise_accuracy(
                successes["candidate_value"].to_numpy(dtype=float),
                failures["candidate_value"].to_numpy(dtype=float),
            )
            if row["outcome_heterogeneous"]
            else np.nan
        )

        for budget in (4, 8, 16):
            scoped = group.loc[group["candidate_idx"].lt(budget)]
            selected = _selected(group, budget)
            row[f"k{budget}_selected_idx"] = int(selected["candidate_idx"])
            row[f"k{budget}_selected_value"] = float(selected["candidate_value"])
            row[f"k{budget}_selected_success"] = bool(
                selected["terminal_success_bool"]
            )
            row[f"k{budget}_oracle_success"] = bool(
                scoped["terminal_success_bool"].any()
            )
        row["k4_to_k8_oracle_gain"] = bool(
            not row["k4_oracle_success"] and row["k8_oracle_success"]
        )
        row["k8_to_k16_oracle_gain"] = bool(
            not row["k8_oracle_success"] and row["k16_oracle_success"]
        )
        row["k4_to_k8_greedy_harm"] = bool(
            row["k4_selected_success"] and not row["k8_selected_success"]
        )
        row["k4_to_k8_greedy_rescue"] = bool(
            not row["k4_selected_success"] and row["k8_selected_success"]
        )
        row["k8_to_k16_greedy_harm"] = bool(
            row["k8_selected_success"] and not row["k16_selected_success"]
        )
        row["k8_to_k16_greedy_rescue"] = bool(
            not row["k8_selected_success"] and row["k16_selected_success"]
        )
        rows.append(row)
    return pd.DataFrame.from_records(rows)


def summarize(states: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    grouper: str | list[str] = keys[0] if len(keys) == 1 else list(keys)
    for values, group in states.groupby(grouper, dropna=False, sort=True):
        if not isinstance(values, tuple):
            values = (values,)
        heterogeneous = group.loc[group["outcome_heterogeneous"]]
        rescues = heterogeneous.loc[~heterogeneous["top_candidate_success"]]
        row = dict(zip(keys, values))
        row.update(
            {
                "states": int(len(group)),
                "heterogeneous_states": int(len(heterogeneous)),
                "all_candidates_fail": int(group["all_candidates_fail"].sum()),
                "top1_success_on_heterogeneous": (
                    float(heterogeneous["top_candidate_success"].mean())
                    if not heterogeneous.empty
                    else np.nan
                ),
                "within_state_pairwise_accuracy": (
                    float(
                        heterogeneous["within_state_value_pairwise_accuracy"].mean()
                    )
                    if not heterogeneous.empty
                    else np.nan
                ),
                "misranked_rescues": int(len(rescues)),
                "misranking_margin_mean": (
                    float(rescues["top_over_best_success_margin"].mean())
                    if not rescues.empty
                    else np.nan
                ),
                "misranking_margin_max": (
                    float(rescues["top_over_best_success_margin"].max())
                    if not rescues.empty
                    else np.nan
                ),
                "k4_to_k8_oracle_gains": int(group["k4_to_k8_oracle_gain"].sum()),
                "k8_to_k16_oracle_gains": int(group["k8_to_k16_oracle_gain"].sum()),
                "k4_to_k8_greedy_harms": int(group["k4_to_k8_greedy_harm"].sum()),
                "k4_to_k8_greedy_rescues": int(
                    group["k4_to_k8_greedy_rescue"].sum()
                ),
                "k8_to_k16_greedy_harms": int(
                    group["k8_to_k16_greedy_harm"].sum()
                ),
                "k8_to_k16_greedy_rescues": int(
                    group["k8_to_k16_greedy_rescue"].sum()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame.from_records(rows)


def _plot(summary: pd.DataFrame, states: pd.DataFrame, destination: Path) -> None:
    shown = summary.loc[summary["heterogeneous_states"].gt(0)].copy()
    labels = [
        f"{row.factor}\n{row.case_id}\nq{int(row.query_idx)}"
        for row in shown.itertuples()
    ]
    x = np.arange(len(shown))
    figure, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    width = 0.36
    axes[0].bar(
        x - width / 2,
        shown["top1_success_on_heterogeneous"],
        width,
        label="top-1 max(value)",
    )
    axes[0].bar(
        x + width / 2,
        shown["within_state_pairwise_accuracy"],
        width,
        label="success-vs-fail pairwise",
    )
    axes[0].axhline(0.5, color="black", linestyle="--", linewidth=1)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Ranking accuracy")
    axes[0].set_title("Cosmos value ranking inside mixed pools")
    axes[0].legend(loc="best")
    axes[0].grid(axis="y", alpha=0.25)

    rescues = states.loc[
        states["outcome_heterogeneous"] & ~states["top_candidate_success"]
    ].copy()
    rescue_labels = [
        f"{row.factor}:{row.case_id}:i{int(row.init_state_id)}:q{int(row.query_idx)}"
        for row in rescues.itertuples()
    ]
    positions = np.arange(len(rescues))
    axes[1].barh(positions, rescues["top_over_best_success_margin"])
    axes[1].set_yticks(positions, rescue_labels)
    axes[1].set_xlabel("V(top failing) - V(best successful)")
    axes[1].set_title("Value overestimation margin on rescues")
    axes[1].grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(destination, dpi=180)
    plt.close(figure)


def analyze(candidate_files: Sequence[Path], output_dir: Path) -> dict[str, object]:
    candidates = read_candidates(candidate_files, require_features=False)
    count = validate_candidate_sets(candidates)
    states = state_diagnostics(candidates)
    summary = summarize(states, ["factor", "case_id", "query_idx"])
    output_dir.mkdir(parents=True, exist_ok=True)
    states.to_csv(output_dir / "value_ranking_states.csv", index=False)
    summary.to_csv(output_dir / "value_ranking_summary.csv", index=False)
    _plot(summary, states, output_dir / "value_ranking_diagnostics.png")

    heterogeneous = states.loc[states["outcome_heterogeneous"]]
    rescues = heterogeneous.loc[~heterogeneous["top_candidate_success"]]
    payload = {
        "candidate_tables": len(candidate_files),
        "candidate_count": count,
        "states": int(len(states)),
        "heterogeneous_states": int(len(heterogeneous)),
        "misranked_rescues": int(len(rescues)),
        "top1_success_on_heterogeneous": (
            float(heterogeneous["top_candidate_success"].mean())
            if not heterogeneous.empty
            else None
        ),
        "within_state_pairwise_accuracy": (
            float(heterogeneous["within_state_value_pairwise_accuracy"].mean())
            if not heterogeneous.empty
            else None
        ),
        "misranking_margin_median": (
            float(rescues["top_over_best_success_margin"].median())
            if not rescues.empty
            else None
        ),
        "misranking_margin_max": (
            float(rescues["top_over_best_success_margin"].max())
            if not rescues.empty
            else None
        ),
        "k4_to_k8_oracle_gains": int(states["k4_to_k8_oracle_gain"].sum()),
        "k8_to_k16_oracle_gains": int(states["k8_to_k16_oracle_gain"].sum()),
        "k4_to_k8_greedy_harms": int(states["k4_to_k8_greedy_harm"].sum()),
        "k8_to_k16_greedy_harms": int(states["k8_to_k16_greedy_harm"].sum()),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate value-ranking diagnostics",
        "",
        "Анализ выполнен только после завершения K16 campaign. Он сравнивает",
        "predicted value с terminal success внутри одного exact-state pool.",
        "",
        "## Summary",
        "",
        f"- Mixed outcome pools: {payload['heterogeneous_states']}/{payload['states']}.",
        f"- Failing top-1 при наличии success: {payload['misranked_rescues']}.",
        f"- Top-1 accuracy на mixed pools: {payload['top1_success_on_heterogeneous']:.3f}.",
        f"- Mean within-state pairwise accuracy: {payload['within_state_pairwise_accuracy']:.3f}.",
        f"- Median positive misranking margin: {payload['misranking_margin_median']:.6f}.",
        f"- Maximum positive misranking margin: {payload['misranking_margin_max']:.6f}.",
        "",
        "## By perturbation and query",
        "",
        summary.to_markdown(index=False),
        "",
        "## Interpretation",
        "",
        "Ненулевой oracle gap вызван value misranking, а не отсутствием хорошего",
        "action во всех mixed pools. Небольшой абсолютный value margin делает",
        "жадный argmax чувствительным к добавлению stochastic proposals. Поэтому",
        "следующий evaluator должен быть action-conditioned и calibrated по",
        "within-state advantage; увеличение K сверх точки насыщения не является",
        "самостоятельным решением.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.candidate_files, args.output_dir), indent=2))


if __name__ == "__main__":
    main()

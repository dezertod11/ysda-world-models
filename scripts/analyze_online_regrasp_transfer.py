#!/usr/bin/env python3
"""Analyze the frozen P3d new-cell transfer and mechanism ablation."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DIAGNOSTICS = (
    "terminal_target_drop_candidate",
    "terminal_wrong_object_interaction_candidate",
    "terminal_official_safety_violation",
)


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _load(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted(campaign_dir.rglob("*__online_branches.parquet"))
    if not paths:
        raise FileNotFoundError(f"No online branch tables under {campaign_dir}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame = frame.drop_duplicates(["case_id", "strategy"], keep="last")
    for column in (
        "terminal_success",
        "trigger_passed",
        "intervention_applied",
        "counterfactual_reused",
        *DIAGNOSTICS,
    ):
        frame[column] = _as_bool(frame[column]).astype(int)
    return frame


def _bootstrap_mean(
    pair: pd.DataFrame,
    *,
    cluster_columns: list[str],
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    grouped = pair.groupby(cluster_columns, as_index=False)["success_delta"].mean()
    values = grouped["success_delta"].to_numpy(dtype=float)
    if not len(values):
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(repetitions, len(values)))
    estimates = values[indices].mean(axis=1)
    return tuple(float(value) for value in np.quantile(estimates, [0.025, 0.975]))


def _mcnemar_exact(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if not discordant:
        return 1.0
    extreme = max(rescues, harms)
    tail = sum(math.comb(discordant, value) for value in range(extreme, discordant + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def _pair_method(
    baseline: pd.DataFrame,
    method_frame: pd.DataFrame,
    method: str,
) -> pd.DataFrame:
    common = baseline.index.intersection(method_frame.index)
    pair = pd.DataFrame(
        {
            "case_id": common,
            "evaluation_cohort": baseline.loc[common, "evaluation_cohort"].to_numpy(),
            "independent_group": baseline.loc[common, "independent_group"].to_numpy(),
            "position_level": baseline.loc[common, "position_level"].to_numpy(),
            "task_id": baseline.loc[common, "task_id"].to_numpy(dtype=int),
            "init_state_id": baseline.loc[common, "init_state_id"].to_numpy(dtype=int),
            "baseline_success": baseline.loc[common, "terminal_success"].to_numpy(dtype=int),
            "method_success": method_frame.loc[common, "terminal_success"].to_numpy(dtype=int),
            "baseline_final_t": baseline.loc[common, "terminal_final_t"].to_numpy(dtype=int),
            "method_final_t": method_frame.loc[common, "terminal_final_t"].to_numpy(dtype=int),
            "trigger_passed": method_frame.loc[common, "trigger_passed"].to_numpy(dtype=int),
            "intervention_applied": method_frame.loc[
                common, "intervention_applied"
            ].to_numpy(dtype=int),
            "counterfactual_reused": method_frame.loc[
                common, "counterfactual_reused"
            ].to_numpy(dtype=int),
            "primitive_steps": method_frame.loc[common, "primitive_steps"].to_numpy(dtype=int),
        }
    )
    for diagnostic in DIAGNOSTICS:
        short = diagnostic.removeprefix("terminal_")
        pair[f"baseline_{short}"] = baseline.loc[common, diagnostic].to_numpy(dtype=int)
        pair[f"method_{short}"] = method_frame.loc[common, diagnostic].to_numpy(dtype=int)
    pair["method"] = method
    pair["success_delta"] = pair["method_success"] - pair["baseline_success"]
    pair["rescued"] = (pair["success_delta"] == 1).astype(int)
    pair["harmed"] = (pair["success_delta"] == -1).astype(int)
    return pair


def _summarize(
    pair: pd.DataFrame,
    *,
    method: str,
    cohort: str,
    repetitions: int,
    seed: int,
) -> dict:
    subset = pair if cohort == "all" else pair.loc[pair["evaluation_cohort"] == cohort]
    group_ci = _bootstrap_mean(
        subset,
        cluster_columns=["independent_group"],
        repetitions=repetitions,
        seed=seed,
    )
    cell_ci = _bootstrap_mean(
        subset,
        cluster_columns=["position_level", "task_id"],
        repetitions=repetitions,
        seed=seed + 1,
    )
    both_success = (subset["baseline_success"] == 1) & (subset["method_success"] == 1)
    result = {
        "method": method,
        "cohort": cohort,
        "n_cases": len(subset),
        "n_groups": int(subset["independent_group"].nunique()),
        "n_cells": int(subset.groupby(["position_level", "task_id"]).ngroups),
        "baseline_successes": int(subset["baseline_success"].sum()),
        "method_successes": int(subset["method_success"].sum()),
        "baseline_sr": float(subset["baseline_success"].mean()),
        "method_sr": float(subset["method_success"].mean()),
        "paired_sr_delta": float(subset["success_delta"].mean()),
        "group_ci_low": group_ci[0],
        "group_ci_high": group_ci[1],
        "cell_macro_ci_low": cell_ci[0],
        "cell_macro_ci_high": cell_ci[1],
        "rescues": int(subset["rescued"].sum()),
        "harms": int(subset["harmed"].sum()),
        "mcnemar_exact_p": _mcnemar_exact(
            int(subset["rescued"].sum()), int(subset["harmed"].sum())
        ),
        "triggered": int(subset["trigger_passed"].sum()),
        "interventions": int(subset["intervention_applied"].sum()),
        "trigger_rate": float(subset["trigger_passed"].mean()),
        "intervention_rate": float(subset["intervention_applied"].mean()),
        "mean_primitive_steps": float(subset["primitive_steps"].mean()),
        "mean_final_t_delta": float(
            (subset["method_final_t"] - subset["baseline_final_t"]).mean()
        ),
        "both_success_cases": int(both_success.sum()),
        "mean_time_delta_both_success": float(
            (subset.loc[both_success, "method_final_t"]
            - subset.loc[both_success, "baseline_final_t"]).mean()
        )
        if both_success.any()
        else float("nan"),
    }
    for diagnostic in DIAGNOSTICS:
        short = diagnostic.removeprefix("terminal_")
        result[f"{short}_delta"] = float(
            subset[f"method_{short}"].mean() - subset[f"baseline_{short}"].mean()
        )
    return result


def _fallback_integrity(pair: pd.DataFrame) -> bool:
    reused = pair.loc[pair["counterfactual_reused"] == 1]
    if reused.empty:
        return True
    columns = ["success", "final_t", *(item.removeprefix("terminal_") for item in DIAGNOSTICS)]
    return all(
        bool((reused[f"baseline_{column}"] == reused[f"method_{column}"]).all())
        for column in columns
    )


def analyze(args: argparse.Namespace) -> dict:
    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = _load(campaign_dir)
    expected = [item.strip() for item in args.expected_strategies.split(",") if item.strip()]
    observed = sorted(frame["strategy"].unique())
    if set(observed) != set(expected):
        raise ValueError(f"Observed strategies {observed}, expected {expected}")
    counts = frame.groupby("case_id")["strategy"].nunique()
    complete_cases = int((counts == len(expected)).sum())
    complete = bool(
        complete_cases == args.expected_cases and len(frame) == args.expected_cases * len(expected)
    )
    exact_replay = bool((frame["snapshot_replay_max_abs"] <= args.replay_threshold).all())

    baseline = frame.loc[frame["strategy"] == "baseline_h8"].set_index("case_id")
    pairs = []
    summaries = []
    for method_index, method in enumerate(item for item in expected if item != "baseline_h8"):
        method_frame = frame.loc[frame["strategy"] == method].set_index("case_id")
        pair = _pair_method(baseline, method_frame, method)
        pairs.append(pair)
        for cohort_index, cohort in enumerate(("all", "replication", "novel_cell")):
            summaries.append(
                _summarize(
                    pair,
                    method=method,
                    cohort=cohort,
                    repetitions=args.bootstrap_repetitions,
                    seed=args.seed + 10 * method_index + 2 * cohort_index,
                )
            )

    pair_frame = pd.concat(pairs, ignore_index=True)
    summary_frame = pd.DataFrame(summaries)
    fallback_integrity = all(_fallback_integrity(pair) for pair in pairs)
    novel = summary_frame.loc[summary_frame["cohort"] == "novel_cell"].sort_values(
        [
            "paired_sr_delta",
            "harms",
            "wrong_object_interaction_candidate_delta",
            "mean_primitive_steps",
        ],
        ascending=[False, True, True, True],
        kind="stable",
    )
    selected_method = str(novel.iloc[0]["method"])
    selected_novel = novel.iloc[0]
    selected_replication = summary_frame.loc[
        (summary_frame["method"] == selected_method)
        & (summary_frame["cohort"] == "replication")
    ].iloc[0]
    gate = bool(
        complete
        and exact_replay
        and fallback_integrity
        and int(selected_novel["interventions"]) >= args.min_interventions
        and float(selected_novel["paired_sr_delta"]) > 0.0
        and float(selected_novel["group_ci_low"]) >= 0.0
        and int(selected_novel["rescues"]) > int(selected_novel["harms"])
        and float(selected_novel["target_drop_candidate_delta"]) <= args.max_drop_delta
        and float(selected_novel["wrong_object_interaction_candidate_delta"])
        <= args.max_wrong_delta
        and float(selected_novel["official_safety_violation_delta"]) <= 0.0
        and float(selected_replication["paired_sr_delta"]) >= 0.0
        and int(selected_replication["rescues"]) >= int(selected_replication["harms"])
    )

    cell_frame = (
        pair_frame.groupby(
            ["method", "evaluation_cohort", "position_level", "task_id"], as_index=False
        )
        .agg(
            n_cases=("case_id", "size"),
            baseline_sr=("baseline_success", "mean"),
            method_sr=("method_success", "mean"),
            paired_sr_delta=("success_delta", "mean"),
            rescues=("rescued", "sum"),
            harms=("harmed", "sum"),
            trigger_rate=("trigger_passed", "mean"),
            intervention_rate=("intervention_applied", "mean"),
        )
        .sort_values(["method", "evaluation_cohort", "position_level", "task_id"])
    )
    frame.to_parquet(output_dir / "online_branches.parquet", index=False)
    frame.to_csv(output_dir / "online_branches.csv", index=False)
    pair_frame.to_csv(output_dir / "paired_cases.csv", index=False)
    summary_frame.to_csv(output_dir / "cohort_method_summary.csv", index=False)
    cell_frame.to_csv(output_dir / "cell_summary.csv", index=False)
    (output_dir / "selected_method.txt").write_text(selected_method + "\n", encoding="utf-8")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    cohorts = ["replication", "novel_cell"]
    methods = [item for item in expected if item != "baseline_h8"]
    x = np.arange(len(cohorts))
    width = 0.8 / (len(methods) + 1)
    baseline_sr = [
        float(summary_frame.loc[summary_frame["cohort"] == cohort, "baseline_sr"].iloc[0])
        for cohort in cohorts
    ]
    axes[0].bar(x - len(methods) * width / 2, baseline_sr, width, label="baseline_h8")
    for method_index, method in enumerate(methods):
        rows = summary_frame.loc[
            (summary_frame["method"] == method) & summary_frame["cohort"].isin(cohorts)
        ].set_index("cohort")
        axes[0].bar(
            x + (method_index + 1 - len(methods) / 2) * width,
            [rows.loc[cohort, "method_sr"] for cohort in cohorts],
            width,
            label=method,
        )
    axes[0].set_xticks(x, cohorts)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Success rate")
    axes[0].legend(fontsize=8)

    delta_rows = summary_frame.loc[summary_frame["cohort"].isin(cohorts)].copy()
    labels = [f"{row.method}\n{row.cohort}" for row in delta_rows.itertuples()]
    centers = delta_rows["paired_sr_delta"].to_numpy()
    lower = centers - delta_rows["group_ci_low"].to_numpy()
    upper = delta_rows["group_ci_high"].to_numpy() - centers
    axes[1].errorbar(
        np.arange(len(delta_rows)), centers, yerr=np.vstack([lower, upper]), fmt="o", capsize=4
    )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xticks(np.arange(len(labels)), labels, rotation=25, ha="right")
    axes[1].set_ylabel("Paired SR delta")

    chosen_cells = cell_frame.loc[cell_frame["method"] == selected_method]
    cell_labels = [
        f"{row.position_level}/t{row.task_id}" for row in chosen_cells.itertuples()
    ]
    colors = [
        "#2f6f9f" if cohort == "replication" else "#d47f2f"
        for cohort in chosen_cells["evaluation_cohort"]
    ]
    axes[2].bar(np.arange(len(chosen_cells)), chosen_cells["paired_sr_delta"], color=colors)
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_xticks(np.arange(len(cell_labels)), cell_labels, rotation=55, ha="right")
    axes[2].set_ylabel(f"{selected_method} SR delta")
    fig.tight_layout()
    fig.savefig(output_dir / "online_regrasp_transfer_summary.png", dpi=180)
    plt.close(fig)

    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phase": args.phase,
        "campaign_dir": str(campaign_dir),
        "expected_cases": args.expected_cases,
        "complete_cases": complete_cases,
        "rows": len(frame),
        "exact_replay": exact_replay,
        "fallback_integrity": fallback_integrity,
        "selected_method": selected_method,
        "gate_pass": gate,
        "methods": summary_frame.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    markdown = [
        f"# P3d {args.phase} transfer and ablation",
        "",
        f"- Complete cases: **{complete_cases}/{args.expected_cases}**.",
        f"- Exact snapshot replay: **{exact_replay}**.",
        f"- Counterfactual fallback integrity: **{fallback_integrity}**.",
        f"- Selected method: **{selected_method}**.",
        f"- Gate: **{'PASS' if gate else 'NO-GO'}**.",
        "",
        summary_frame.to_markdown(index=False),
        "",
        "The new-cell cohort contains Position cells absent from P3c. The RGB trigger",
        "and both primitives are frozen before these outcomes are observed.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    if args.require_gate and not gate:
        raise SystemExit(2)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--campaign-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--phase", choices=["development", "holdout"], required=True)
    result.add_argument("--expected-cases", type=int, required=True)
    result.add_argument(
        "--expected-strategies",
        default="baseline_h8,workspace_calibrated,workspace_retreat_only",
    )
    result.add_argument("--bootstrap-repetitions", type=int, default=10000)
    result.add_argument("--seed", type=int, default=20260905)
    result.add_argument("--replay-threshold", type=float, default=1e-9)
    result.add_argument("--min-interventions", type=int, default=5)
    result.add_argument("--max-drop-delta", type=float, default=0.05)
    result.add_argument("--max-wrong-delta", type=float, default=0.05)
    result.add_argument("--require-gate", action="store_true")
    return result


if __name__ == "__main__":
    analyze(parser().parse_args())

#!/usr/bin/env python3
"""Analyze the frozen real-observation H8/H16 re-query holdout."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest


METHOD_ORDER = ["maxV-H16", "maxV-H8", "maxV-gripper-H8/H16"]
FACTOR_ORDER = ["Object", "Position", "Environment"]
COMPUTE_COSTS = (0.01, 0.025, 0.05)
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260830


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin({"1", "true", "yes"})


def method_from_row(row: pd.Series) -> str:
    strategy = str(row["planning_strategy"])
    if strategy == "max_value_gripper_requery":
        return "maxV-gripper-H8/H16"
    if strategy == "max_value" and int(row["num_open_loop_steps"]) == 8:
        return "maxV-H8"
    if strategy == "max_value" and int(row["num_open_loop_steps"]) == 16:
        return "maxV-H16"
    raise ValueError(
        f"Unexpected planning method: strategy={strategy!r}, "
        f"num_open_loop_steps={row['num_open_loop_steps']!r}"
    )


def factor_from_case(case_id: str) -> str:
    normalized = str(case_id).lower()
    if "environment" in normalized:
        return "Environment"
    if "position" in normalized:
        return "Position"
    if "object" in normalized:
        return "Object"
    raise ValueError(f"Cannot infer factor from case_id={case_id!r}")


def _first_bool(group: pd.DataFrame, column: str) -> bool:
    if column not in group:
        return False
    return bool(parse_bool(group[column]).iloc[0])


def load_query_traces(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not paths:
        raise FileNotFoundError(f"No query traces under {campaign_dir / 'runs'}")
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frames.append(frame)
    traces = pd.concat(frames, ignore_index=True)
    required = {
        "case_id",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "query_idx",
        "planning_strategy",
        "num_open_loop_steps",
        "success",
        "final_t",
    }
    missing = sorted(required - set(traces.columns))
    if missing:
        raise ValueError(f"Query traces miss required columns: {missing}")
    traces["method"] = traces.apply(method_from_row, axis=1)
    traces["factor"] = traces["case_id"].map(factor_from_case)
    traces["success"] = parse_bool(traces["success"])
    for column in (
        "planning_requery_triggered",
        "planning_gripper_transition_detected",
        "max_value_selected",
    ):
        if column not in traces:
            traces[column] = False
        traces[column] = parse_bool(traces[column])
    return traces


def aggregate_episodes(traces: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "method",
        "factor",
        "case_id",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
    ]
    rows: list[dict[str, object]] = []
    for values, group in traces.groupby(keys, sort=True, dropna=False):
        record = dict(zip(keys, values))
        final_t = int(pd.to_numeric(group["final_t"], errors="coerce").max())
        query_count = int(group["query_idx"].nunique())
        h16_reference_queries = max(1, int(math.ceil(final_t / 16.0)))
        success = bool(group["success"].iloc[0])
        record.update(
            {
                "success": success,
                "final_t": final_t,
                "query_count": query_count,
                "h16_reference_queries": h16_reference_queries,
                "query_multiplier": query_count / h16_reference_queries,
                "requery_count": int(group["planning_requery_triggered"].sum()),
                "trigger_rate": float(group["planning_requery_triggered"].mean()),
                "max_value_selected_rate": float(group["max_value_selected"].mean()),
                "timeout": bool((not success) and final_t >= 280),
                "time_to_success": float(final_t) if success else np.nan,
                "target_drop_candidate": _first_bool(group, "target_drop_candidate"),
                "wrong_object_interaction": _first_bool(
                    group, "wrong_object_interaction_candidate"
                ),
                "official_safety_violation": _first_bool(
                    group, "official_safety_violation"
                ),
            }
        )
        rows.append(record)
    episodes = pd.DataFrame(rows)
    episodes["state_key"] = (
        episodes["factor"].astype(str)
        + "|"
        + episodes["suite"].astype(str)
        + "|task"
        + episodes["task_id"].astype(int).astype(str)
        + "|init"
        + episodes["init_state_id"].astype(int).astype(str)
        + "|seed"
        + episodes["rollout_seed"].astype(int).astype(str)
    )
    return episodes


def validate_integrity(episodes: pd.DataFrame, traces: pd.DataFrame) -> dict[str, object]:
    counts = episodes.groupby("method")["state_key"].nunique().to_dict()
    expected_counts = {method: 40 for method in METHOD_ORDER}
    state_sets = {
        method: set(episodes.loc[episodes["method"].eq(method), "state_key"])
        for method in METHOD_ORDER
    }
    common_states = set.intersection(*state_sets.values()) if state_sets else set()
    adaptive = traces.loc[traces["method"].eq("maxV-gripper-H8/H16")]
    integrity = {
        "expected_episode_counts": expected_counts,
        "observed_episode_counts": {key: int(value) for key, value in counts.items()},
        "paired_state_count": len(common_states),
        "all_methods_have_40_states": counts == expected_counts,
        "identical_state_sets": all(states == common_states for states in state_sets.values()),
        "adaptive_always_selected_max_value": bool(adaptive["max_value_selected"].all()),
        "adaptive_trigger_matches_diagnostic": bool(
            (
                adaptive["planning_requery_triggered"]
                == adaptive["planning_gripper_transition_detected"]
            ).all()
        ),
        "split_values": sorted(traces.get("experiment_split", pd.Series()).dropna().unique().tolist()),
    }
    integrity["passed"] = bool(
        integrity["all_methods_have_40_states"]
        and integrity["identical_state_sets"]
        and integrity["adaptive_always_selected_max_value"]
        and integrity["adaptive_trigger_matches_diagnostic"]
        and integrity["split_values"] == ["holdout"]
    )
    if not integrity["passed"]:
        raise ValueError(f"Holdout integrity failed: {json.dumps(integrity, indent=2)}")
    return integrity


def _stratified_bootstrap_means(
    frame: pd.DataFrame,
    value_column: str,
    *,
    factor_column: str = "factor",
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    factors = [
        frame.loc[frame[factor_column].eq(factor), value_column].to_numpy(dtype=float)
        for factor in FACTOR_ORDER
        if frame[factor_column].eq(factor).any()
    ]
    results = np.empty(samples, dtype=float)
    for index in range(samples):
        draws = [rng.choice(values, size=len(values), replace=True) for values in factors]
        results[index] = float(np.concatenate(draws).mean())
    return results


def _ci(values: Iterable[float]) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=float)
    return float(np.quantile(array, 0.025)), float(np.quantile(array, 0.975))


def summarize_methods(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHOD_ORDER:
        scoped = episodes.loc[episodes["method"].eq(method)]
        sr_boot = _stratified_bootstrap_means(scoped, "success")
        ci_low, ci_high = _ci(sr_boot)
        rows.append(
            {
                "method": method,
                "states": len(scoped),
                "successes": int(scoped["success"].sum()),
                "success_rate": float(scoped["success"].mean()),
                "success_ci_low": ci_low,
                "success_ci_high": ci_high,
                "mean_queries": float(scoped["query_count"].mean()),
                "mean_query_multiplier": float(scoped["query_multiplier"].mean()),
                "mean_final_t": float(scoped["final_t"].mean()),
                "timeout_rate": float(scoped["timeout"].mean()),
                "drop_rate": float(scoped["target_drop_candidate"].mean()),
                "wrong_object_rate": float(scoped["wrong_object_interaction"].mean()),
                "safety_violation_rate": float(scoped["official_safety_violation"].mean()),
                "requery_count": int(scoped["requery_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize_factors(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor in FACTOR_ORDER:
        for method in METHOD_ORDER:
            scoped = episodes.loc[
                episodes["factor"].eq(factor) & episodes["method"].eq(method)
            ]
            bootstrap = _stratified_bootstrap_means(scoped, "success")
            ci_low, ci_high = _ci(bootstrap)
            rows.append(
                {
                    "factor": factor,
                    "method": method,
                    "states": len(scoped),
                    "successes": int(scoped["success"].sum()),
                    "success_rate": float(scoped["success"].mean()),
                    "success_ci_low": ci_low,
                    "success_ci_high": ci_high,
                    "mean_queries": float(scoped["query_count"].mean()),
                    "mean_query_multiplier": float(scoped["query_multiplier"].mean()),
                    "requery_count": int(scoped["requery_count"].sum()),
                }
            )
    return pd.DataFrame(rows)


def paired_contrasts(episodes: pd.DataFrame) -> pd.DataFrame:
    baseline = episodes.loc[episodes["method"].eq("maxV-H16")].set_index("state_key")
    rows = []
    for method in METHOD_ORDER[1:]:
        candidate = episodes.loc[episodes["method"].eq(method)].set_index("state_key")
        common = baseline.index.intersection(candidate.index)
        paired = pd.DataFrame(
            {
                "factor": baseline.loc[common, "factor"],
                "baseline": baseline.loc[common, "success"].astype(float),
                "method": candidate.loc[common, "success"].astype(float),
            }
        )
        paired["delta"] = paired["method"] - paired["baseline"]
        rescues = int(((paired["baseline"] == 0) & (paired["method"] == 1)).sum())
        harms = int(((paired["baseline"] == 1) & (paired["method"] == 0)).sum())
        discordant = rescues + harms
        p_value = float(binomtest(rescues, discordant, 0.5).pvalue) if discordant else 1.0
        bootstrap = _stratified_bootstrap_means(paired, "delta")
        ci_low, ci_high = _ci(bootstrap)
        rows.append(
            {
                "method": method,
                "paired_states": len(paired),
                "delta_success_rate": float(paired["delta"].mean()),
                "delta_ci_low": ci_low,
                "delta_ci_high": ci_high,
                "rescues": rescues,
                "harms": harms,
                "mcnemar_exact_p": p_value,
            }
        )
    return pd.DataFrame(rows)


def factor_contrasts(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor in FACTOR_ORDER:
        scoped = episodes.loc[episodes["factor"].eq(factor)]
        baseline = scoped.loc[scoped["method"].eq("maxV-H16")].set_index("state_key")
        for method in METHOD_ORDER[1:]:
            candidate = scoped.loc[scoped["method"].eq(method)].set_index("state_key")
            common = baseline.index.intersection(candidate.index)
            delta = (
                candidate.loc[common, "success"].astype(int)
                - baseline.loc[common, "success"].astype(int)
            )
            rows.append(
                {
                    "factor": factor,
                    "method": method,
                    "states": len(common),
                    "delta_success_states": int(delta.sum()),
                    "delta_success_rate": float(delta.mean()),
                    "rescues": int((delta == 1).sum()),
                    "harms": int((delta == -1).sum()),
                }
            )
    return pd.DataFrame(rows)


def compute_utilities(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cost in COMPUTE_COSTS:
        for method in METHOD_ORDER:
            scoped = episodes.loc[episodes["method"].eq(method)]
            utility = scoped["success"].astype(float) - cost * (
                scoped["query_multiplier"] - 1.0
            )
            rows.append(
                {
                    "query_cost": cost,
                    "method": method,
                    "mean_utility": float(utility.mean()),
                }
            )
    return pd.DataFrame(rows)


def evaluate_gates(
    method_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    factor_delta: pd.DataFrame,
    utilities: pd.DataFrame,
) -> dict[str, object]:
    adaptive = contrasts.set_index("method").loc["maxV-gripper-H8/H16"]
    fixed = contrasts.set_index("method").loc["maxV-H8"]
    method_index = method_summary.set_index("method")
    adaptive_factor = factor_delta.loc[
        factor_delta["method"].eq("maxV-gripper-H8/H16")
    ]
    utility_025 = utilities.loc[utilities["query_cost"].eq(0.025)].set_index("method")
    adaptive_checks = {
        "at_least_two_rescues": int(adaptive["rescues"]) >= 2,
        "rescues_exceed_harms": int(adaptive["rescues"]) > int(adaptive["harms"]),
        "pooled_sr_not_lower": float(adaptive["delta_success_rate"]) >= 0.0,
        "no_factor_loses_more_than_one": bool(
            (adaptive_factor["delta_success_states"] >= -1).all()
        ),
        "query_multiplier_20pct_below_fixed_h8": float(
            method_index.loc["maxV-gripper-H8/H16", "mean_query_multiplier"]
        )
        <= 0.8 * float(method_index.loc["maxV-H8", "mean_query_multiplier"]),
        "utility_0025_above_h16": float(
            utility_025.loc["maxV-gripper-H8/H16", "mean_utility"]
        )
        > float(utility_025.loc["maxV-H16", "mean_utility"]),
    }
    fixed_checks = {
        "rescues_exceed_harms": int(fixed["rescues"]) > int(fixed["harms"]),
        "positive_pooled_sr_delta": float(fixed["delta_success_rate"]) > 0.0,
    }
    return {
        "adaptive_checks": adaptive_checks,
        "adaptive_gate_passed": all(adaptive_checks.values()),
        "fixed_h8_mechanism_checks": fixed_checks,
        "fixed_h8_mechanism_supported": all(fixed_checks.values()),
    }


def make_plots(
    episodes: pd.DataFrame,
    method_summary: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    colors = ["#4C78A8", "#E45756", "#59A14F"]
    x = np.arange(len(METHOD_ORDER))
    ordered = method_summary.set_index("method").loc[METHOD_ORDER]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    sr = ordered["success_rate"].to_numpy()
    yerr = np.vstack(
        [
            sr - ordered["success_ci_low"].to_numpy(),
            ordered["success_ci_high"].to_numpy() - sr,
        ]
    )
    axes[0].bar(x, sr, color=colors, yerr=yerr, capsize=4)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Success rate")
    axes[0].set_xticks(x, METHOD_ORDER, rotation=15, ha="right")
    axes[0].set_title("Untouched hard-cell holdout")
    axes[1].bar(x, ordered["mean_query_multiplier"], color=colors)
    axes[1].axhline(1.0, color="black", linewidth=1, linestyle="--")
    axes[1].set_ylabel("Query multiplier vs H16 schedule")
    axes[1].set_xticks(x, METHOD_ORDER, rotation=15, ha="right")
    axes[1].set_title("Policy-query cost")
    fig.tight_layout()
    comparison_path = output_dir / "success_compute_comparison.png"
    fig.savefig(comparison_path, dpi=180)
    plt.close(fig)

    matrix = episodes.pivot(index="state_key", columns="method", values="success")
    matrix = matrix.loc[:, METHOD_ORDER]
    factor_rank = {factor: index for index, factor in enumerate(FACTOR_ORDER)}
    order = sorted(
        matrix.index,
        key=lambda key: (factor_rank[str(key).split("|", 1)[0]], key),
    )
    matrix = matrix.loc[order]
    fig, axis = plt.subplots(figsize=(7.5, max(6, len(matrix) * 0.18)))
    axis.imshow(matrix.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    axis.set_xticks(np.arange(len(METHOD_ORDER)), METHOD_ORDER, rotation=20, ha="right")
    axis.set_yticks(np.arange(len(matrix)), matrix.index, fontsize=6)
    axis.set_title("Paired terminal outcomes (red=fail, green=success)")
    fig.tight_layout()
    outcome_path = output_dir / "paired_outcome_matrix.png"
    fig.savefig(outcome_path, dpi=180)
    plt.close(fig)
    return [comparison_path, outcome_path]


def _percent_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result:
            result[column] = result[column].map(lambda value: f"{100 * value:.1f}%")
    return result


def write_report(
    output_dir: Path,
    integrity: dict[str, object],
    method_summary: pd.DataFrame,
    factor_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    factor_delta: pd.DataFrame,
    utilities: pd.DataFrame,
    gates: dict[str, object],
) -> Path:
    methods_display = _percent_columns(
        method_summary,
        ["success_rate", "success_ci_low", "success_ci_high", "timeout_rate", "drop_rate"],
    )
    factors_display = _percent_columns(
        factor_summary,
        ["success_rate", "success_ci_low", "success_ci_high"],
    )
    contrasts_display = _percent_columns(
        contrasts, ["delta_success_rate", "delta_ci_low", "delta_ci_high"]
    )
    lines = [
        "# Real-observation re-query: holdout results",
        "",
        "## Integrity",
        "",
        f"- Paired states: **{integrity['paired_state_count']}**.",
        f"- Complete and identical method splits: **{integrity['passed']}**.",
        "- Adaptive max-value candidate fidelity: "
        f"**{integrity['adaptive_always_selected_max_value']}**.",
        "",
        "## Primary result",
        "",
        methods_display.to_markdown(index=False),
        "",
        "## Factor results",
        "",
        factors_display.to_markdown(index=False),
        "",
        "## Paired contrasts versus maxV-H16",
        "",
        contrasts_display.to_markdown(index=False),
        "",
        "## Per-factor paired deltas",
        "",
        factor_delta.to_markdown(index=False),
        "",
        "## Compute-adjusted utility",
        "",
        utilities.to_markdown(index=False),
        "",
        "## Preregistered gates",
        "",
        f"- Adaptive gate: **{'PASS' if gates['adaptive_gate_passed'] else 'FAIL'}**.",
    ]
    for name, passed in gates["adaptive_checks"].items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "- Fixed H8 mechanism: "
            f"**{'SUPPORTED' if gates['fixed_h8_mechanism_supported'] else 'NOT SUPPORTED'}**.",
            "",
            "## Decision rule",
            "",
            "A failed adaptive gate closes this exact gripper-transition controller; "
            "the holdout is not used for threshold tuning. Fixed H8 is a causal "
            "feedback control and is interpreted jointly with its query multiplier.",
            "",
            "## Figures",
            "",
            "- `success_compute_comparison.png`",
            "- `paired_outcome_matrix.png`",
            "",
        ]
    )
    path = output_dir / "RESULTS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def analyze(campaign_dir: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    traces = load_query_traces(campaign_dir)
    episodes = aggregate_episodes(traces)
    integrity = validate_integrity(episodes, traces)
    method_summary = summarize_methods(episodes)
    factor_summary = summarize_factors(episodes)
    contrasts = paired_contrasts(episodes)
    factor_delta = factor_contrasts(episodes)
    utilities = compute_utilities(episodes)
    gates = evaluate_gates(method_summary, contrasts, factor_delta, utilities)

    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    method_summary.to_csv(output_dir / "method_summary.csv", index=False)
    factor_summary.to_csv(output_dir / "factor_summary.csv", index=False)
    contrasts.to_csv(output_dir / "paired_contrasts.csv", index=False)
    factor_delta.to_csv(output_dir / "factor_contrasts.csv", index=False)
    utilities.to_csv(output_dir / "compute_utilities.csv", index=False)
    plot_paths = make_plots(episodes, method_summary, output_dir)
    report_path = write_report(
        output_dir,
        integrity,
        method_summary,
        factor_summary,
        contrasts,
        factor_delta,
        utilities,
        gates,
    )
    summary = {
        "campaign_dir": str(campaign_dir),
        "integrity": integrity,
        "gates": gates,
        "method_summary": method_summary.to_dict(orient="records"),
        "paired_contrasts": contrasts.to_dict(orient="records"),
        "report": str(report_path),
        "plots": [str(path) for path in plot_paths],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "real_observation_requery"
    summary = analyze(args.campaign_dir, output_dir)
    print(json.dumps(summary["gates"], indent=2))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()


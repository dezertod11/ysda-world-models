#!/usr/bin/env python3
"""Analyze the frozen factor-routed real-observation re-query transfer."""

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
    from analyze_real_observation_requery import (
        COMPUTE_COSTS,
        FACTOR_ORDER,
        _ci,
        _stratified_bootstrap_means,
        aggregate_episodes,
        load_query_traces,
    )
except ModuleNotFoundError:
    from scripts.analyze_real_observation_requery import (
        COMPUTE_COSTS,
        FACTOR_ORDER,
        _ci,
        _stratified_bootstrap_means,
        aggregate_episodes,
        load_query_traces,
    )


BASELINE = "maxV-H16"
ADAPTIVE = "maxV-gripper-H8/H16"
ROUTED = "factor-routed-H16/adaptive"
METHOD_ORDER = [BASELINE, ADAPTIVE, ROUTED]
EXPECTED_TASKS = {
    "Object": {1, 2, 3},
    "Position": {1, 2, 3},
    "Environment": {1, 3, 4},
}


def _json_default(value: object) -> object:
    """Convert NumPy/Pandas scalar values used in summaries to JSON types."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def validate_transfer_integrity(
    episodes: pd.DataFrame, traces: pd.DataFrame
) -> dict[str, object]:
    direct_methods = [BASELINE, ADAPTIVE]
    counts = episodes.groupby("method")["state_key"].nunique().to_dict()
    state_sets = {
        method: set(episodes.loc[episodes["method"].eq(method), "state_key"])
        for method in direct_methods
    }
    common = state_sets[BASELINE] & state_sets[ADAPTIVE]
    factor_counts = (
        episodes.groupby(["method", "factor"])["state_key"].nunique().to_dict()
    )
    observed_tasks = {
        factor: set(
            episodes.loc[episodes["factor"].eq(factor), "task_id"].astype(int).unique()
        )
        for factor in FACTOR_ORDER
    }
    adaptive_traces = traces.loc[traces["method"].eq(ADAPTIVE)]
    integrity = {
        "observed_episode_counts": {key: int(value) for key, value in counts.items()},
        "both_methods_have_90_states": counts == {BASELINE: 90, ADAPTIVE: 90},
        "identical_state_sets": state_sets[BASELINE] == state_sets[ADAPTIVE],
        "paired_state_count": len(common),
        "factor_counts_are_30": all(
            factor_counts.get((method, factor), 0) == 30
            for method in direct_methods
            for factor in FACTOR_ORDER
        ),
        "observed_tasks": {
            factor: sorted(tasks) for factor, tasks in observed_tasks.items()
        },
        "expected_tasks_match": observed_tasks == EXPECTED_TASKS,
        "init_states_are_40_49": set(episodes["init_state_id"].astype(int))
        == set(range(40, 50)),
        "adaptive_always_selected_max_value": bool(
            adaptive_traces["max_value_selected"].all()
        ),
        "adaptive_trigger_matches_diagnostic": bool(
            (
                adaptive_traces["planning_requery_triggered"]
                == adaptive_traces["planning_gripper_transition_detected"]
            ).all()
        ),
        "split_values": sorted(
            traces.get("experiment_split", pd.Series(dtype=str)).dropna().unique().tolist()
        ),
    }
    integrity["passed"] = bool(
        integrity["both_methods_have_90_states"]
        and integrity["identical_state_sets"]
        and integrity["factor_counts_are_30"]
        and integrity["expected_tasks_match"]
        and integrity["init_states_are_40_49"]
        and integrity["adaptive_always_selected_max_value"]
        and integrity["adaptive_trigger_matches_diagnostic"]
        and integrity["split_values"] == ["generalization"]
    )
    if not integrity["passed"]:
        raise ValueError(f"Transfer integrity failed: {json.dumps(integrity, indent=2)}")
    return integrity


def build_factor_route(episodes: pd.DataFrame) -> pd.DataFrame:
    baseline = episodes.loc[episodes["method"].eq(BASELINE)].set_index("state_key")
    adaptive = episodes.loc[episodes["method"].eq(ADAPTIVE)].set_index("state_key")
    if set(baseline.index) != set(adaptive.index):
        raise ValueError("Cannot route non-identical baseline/adaptive state sets")
    route = baseline.copy()
    adaptive_keys = route.index[route["factor"].isin(["Position", "Environment"])]
    outcome_columns = [
        "success",
        "final_t",
        "query_count",
        "h16_reference_queries",
        "query_multiplier",
        "requery_count",
        "trigger_rate",
        "max_value_selected_rate",
        "timeout",
        "time_to_success",
        "target_drop_candidate",
        "wrong_object_interaction",
        "official_safety_violation",
    ]
    route.loc[adaptive_keys, outcome_columns] = adaptive.loc[
        adaptive_keys, outcome_columns
    ].to_numpy()
    route["routed_source_method"] = BASELINE
    route.loc[adaptive_keys, "routed_source_method"] = ADAPTIVE
    route["method"] = ROUTED
    return route.reset_index()


def summarize_methods(all_episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHOD_ORDER:
        scoped = all_episodes.loc[all_episodes["method"].eq(method)]
        bootstrap = _stratified_bootstrap_means(scoped, "success")
        ci_low, ci_high = _ci(bootstrap)
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
                "timeout_rate": float(scoped["timeout"].mean()),
                "drop_rate": float(scoped["target_drop_candidate"].mean()),
                "wrong_object_rate": float(scoped["wrong_object_interaction"].mean()),
                "safety_violation_rate": float(
                    scoped["official_safety_violation"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def summarize_factors(all_episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for factor in FACTOR_ORDER:
        for method in METHOD_ORDER:
            scoped = all_episodes.loc[
                all_episodes["factor"].eq(factor)
                & all_episodes["method"].eq(method)
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
                    "mean_query_multiplier": float(scoped["query_multiplier"].mean()),
                }
            )
    return pd.DataFrame(rows)


def paired_contrast(
    all_episodes: pd.DataFrame, method: str
) -> tuple[dict[str, object], pd.DataFrame]:
    baseline = all_episodes.loc[all_episodes["method"].eq(BASELINE)].set_index(
        "state_key"
    )
    candidate = all_episodes.loc[all_episodes["method"].eq(method)].set_index(
        "state_key"
    )
    common = baseline.index.intersection(candidate.index)
    paired = pd.DataFrame(
        {
            "state_key": common,
            "factor": baseline.loc[common, "factor"].to_numpy(),
            "baseline_success": baseline.loc[common, "success"].astype(int).to_numpy(),
            "method_success": candidate.loc[common, "success"].astype(int).to_numpy(),
        }
    )
    paired["delta"] = paired["method_success"] - paired["baseline_success"]
    rescues = int((paired["delta"] == 1).sum())
    harms = int((paired["delta"] == -1).sum())
    discordant = rescues + harms
    bootstrap = _stratified_bootstrap_means(paired, "delta")
    ci_low, ci_high = _ci(bootstrap)
    summary = {
        "method": method,
        "paired_states": len(paired),
        "delta_success_rate": float(paired["delta"].mean()),
        "delta_ci_low": ci_low,
        "delta_ci_high": ci_high,
        "rescues": rescues,
        "harms": harms,
        "mcnemar_exact_p": float(
            binomtest(rescues, discordant, 0.5).pvalue if discordant else 1.0
        ),
    }
    return summary, paired


def build_contrasts(
    all_episodes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries = []
    factor_rows = []
    for method in [ADAPTIVE, ROUTED]:
        summary, paired = paired_contrast(all_episodes, method)
        summaries.append(summary)
        for factor in FACTOR_ORDER:
            scoped = paired.loc[paired["factor"].eq(factor)]
            factor_rows.append(
                {
                    "factor": factor,
                    "method": method,
                    "states": len(scoped),
                    "delta_success_states": int(scoped["delta"].sum()),
                    "delta_success_rate": float(scoped["delta"].mean()),
                    "rescues": int((scoped["delta"] == 1).sum()),
                    "harms": int((scoped["delta"] == -1).sum()),
                }
            )
    return pd.DataFrame(summaries), pd.DataFrame(factor_rows)


def compute_utilities(all_episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cost in COMPUTE_COSTS:
        for method in METHOD_ORDER:
            scoped = all_episodes.loc[all_episodes["method"].eq(method)]
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


def evaluate_gate(
    method_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    factor_contrasts: pd.DataFrame,
    utilities: pd.DataFrame,
    integrity: dict[str, object],
) -> dict[str, object]:
    route = contrasts.set_index("method").loc[ROUTED]
    route_factors = factor_contrasts.loc[factor_contrasts["method"].eq(ROUTED)].set_index(
        "factor"
    )
    method_index = method_summary.set_index("method")
    utility_025 = utilities.loc[utilities["query_cost"].eq(0.025)].set_index("method")
    checks = {
        "at_least_five_rescues": int(route["rescues"]) >= 5,
        "rescues_exceed_harms": int(route["rescues"]) > int(route["harms"]),
        "pooled_delta_at_least_5pp": float(route["delta_success_rate"]) >= 0.05,
        "position_delta_nonnegative": float(
            route_factors.loc["Position", "delta_success_rate"]
        )
        >= 0.0,
        "environment_delta_nonnegative": float(
            route_factors.loc["Environment", "delta_success_rate"]
        )
        >= 0.0,
        "query_multiplier_at_most_1p5": float(
            method_index.loc[ROUTED, "mean_query_multiplier"]
        )
        <= 1.5,
        "utility_0025_above_h16": float(utility_025.loc[ROUTED, "mean_utility"])
        > float(utility_025.loc[BASELINE, "mean_utility"]),
        "integrity_passed": bool(integrity["passed"]),
    }
    return {"checks": checks, "gate_passed": all(checks.values())}


def make_plots(
    all_episodes: pd.DataFrame, method_summary: pd.DataFrame, output_dir: Path
) -> list[Path]:
    colors = ["#4C78A8", "#E45756", "#59A14F"]
    ordered = method_summary.set_index("method").loc[METHOD_ORDER]
    x = np.arange(len(METHOD_ORDER))
    success = ordered["success_rate"].to_numpy()
    yerr = np.vstack(
        [
            success - ordered["success_ci_low"].to_numpy(),
            ordered["success_ci_high"].to_numpy() - success,
        ]
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(x, success, yerr=yerr, color=colors, capsize=4)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Success rate")
    axes[0].set_xticks(x, METHOD_ORDER, rotation=16, ha="right")
    axes[0].set_title("Independent task transfer")
    axes[1].bar(x, ordered["mean_query_multiplier"], color=colors)
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Query multiplier")
    axes[1].set_xticks(x, METHOD_ORDER, rotation=16, ha="right")
    axes[1].set_title("Compute cost")
    fig.tight_layout()
    summary_path = output_dir / "route_success_compute.png"
    fig.savefig(summary_path, dpi=180)
    plt.close(fig)

    matrix = all_episodes.loc[all_episodes["method"].isin([BASELINE, ROUTED])].pivot(
        index="state_key", columns="method", values="success"
    )
    matrix = matrix.loc[:, [BASELINE, ROUTED]]
    factor_rank = {factor: index for index, factor in enumerate(FACTOR_ORDER)}
    matrix = matrix.loc[
        sorted(matrix.index, key=lambda key: (factor_rank[key.split("|", 1)[0]], key))
    ]
    fig, axis = plt.subplots(figsize=(6, max(7, 0.14 * len(matrix))))
    axis.imshow(matrix.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    axis.set_xticks([0, 1], [BASELINE, ROUTED], rotation=15, ha="right")
    axis.set_yticks(np.arange(len(matrix)), matrix.index, fontsize=5)
    axis.set_title("Paired routed outcomes")
    fig.tight_layout()
    matrix_path = output_dir / "route_paired_outcomes.png"
    fig.savefig(matrix_path, dpi=180)
    plt.close(fig)
    return [summary_path, matrix_path]


def percent_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = result[column].map(lambda value: f"{100 * value:.1f}%")
    return result


def write_report(
    output_dir: Path,
    integrity: dict[str, object],
    method_summary: pd.DataFrame,
    factor_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    factor_contrasts: pd.DataFrame,
    utilities: pd.DataFrame,
    gate: dict[str, object],
) -> Path:
    methods = percent_frame(
        method_summary,
        ["success_rate", "success_ci_low", "success_ci_high", "timeout_rate"],
    )
    factors = percent_frame(
        factor_summary, ["success_rate", "success_ci_low", "success_ci_high"]
    )
    contrast_display = percent_frame(
        contrasts, ["delta_success_rate", "delta_ci_low", "delta_ci_high"]
    )
    lines = [
        "# Factor-routed real-observation re-query: transfer results",
        "",
        "## Integrity",
        "",
        f"- Complete paired states: **{integrity['paired_state_count']}**.",
        f"- Frozen integrity: **{integrity['passed']}**.",
        "- Adaptive max-value fidelity: "
        f"**{integrity['adaptive_always_selected_max_value']}**.",
        "",
        "## Primary result",
        "",
        methods.to_markdown(index=False),
        "",
        "## Factor results",
        "",
        factors.to_markdown(index=False),
        "",
        "## Paired contrasts versus H16",
        "",
        contrast_display.to_markdown(index=False),
        "",
        "## Factor contrasts",
        "",
        factor_contrasts.to_markdown(index=False),
        "",
        "## Compute-adjusted utility",
        "",
        utilities.to_markdown(index=False),
        "",
        "## Preregistered gate",
        "",
        f"- Overall: **{'PASS' if gate['gate_passed'] else 'FAIL'}**.",
    ]
    lines.extend(
        f"- `{name}`: {'PASS' if passed else 'FAIL'}"
        for name, passed in gate["checks"].items()
    )
    lines.extend(
        [
            "",
            "A failed gate closes this exact factor router. No task-specific "
            "exceptions are fitted on this transfer split.",
            "",
            "## Figures",
            "",
            "- `route_success_compute.png`",
            "- `route_paired_outcomes.png`",
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
    integrity = validate_transfer_integrity(episodes, traces)
    route = build_factor_route(episodes)
    all_episodes = pd.concat([episodes, route], ignore_index=True)
    method_summary = summarize_methods(all_episodes)
    factor_summary = summarize_factors(all_episodes)
    contrasts, factor_contrasts = build_contrasts(all_episodes)
    utilities = compute_utilities(all_episodes)
    gate = evaluate_gate(
        method_summary, contrasts, factor_contrasts, utilities, integrity
    )

    episodes.to_csv(output_dir / "direct_episode_outcomes.csv", index=False)
    route.to_csv(output_dir / "routed_episode_outcomes.csv", index=False)
    method_summary.to_csv(output_dir / "method_summary.csv", index=False)
    factor_summary.to_csv(output_dir / "factor_summary.csv", index=False)
    contrasts.to_csv(output_dir / "paired_contrasts.csv", index=False)
    factor_contrasts.to_csv(output_dir / "factor_contrasts.csv", index=False)
    utilities.to_csv(output_dir / "compute_utilities.csv", index=False)
    plots = make_plots(all_episodes, method_summary, output_dir)
    report = write_report(
        output_dir,
        integrity,
        method_summary,
        factor_summary,
        contrasts,
        factor_contrasts,
        utilities,
        gate,
    )
    summary = {
        "campaign_dir": str(campaign_dir),
        "integrity": integrity,
        "gate": gate,
        "method_summary": method_summary.to_dict(orient="records"),
        "paired_contrasts": contrasts.to_dict(orient="records"),
        "report": str(report),
        "plots": [str(path) for path in plots],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=_json_default), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "factor_routed_transfer"
    summary = analyze(args.campaign_dir, output_dir)
    print(json.dumps(summary["gate"], indent=2))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Analyze the frozen query-0 H8 then H16 closed-loop holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest


BASELINE = "maxV-H16"
METHOD = "maxV-Q0-H8-then-H16"
METHOD_ORDER = [BASELINE, METHOD]
EXPECTED_TASK_COUNTS = {8: 30, 9: 30}
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260831
QUERY_COST = 0.025


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})


def method_from_strategy(strategy: str) -> str:
    mapping = {
        "max_value": BASELINE,
        "max_value_initial_requery": METHOD,
    }
    try:
        return mapping[str(strategy)]
    except KeyError as error:
        raise ValueError(f"Unexpected strategy: {strategy!r}") from error


def _state_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["suite"].astype(str)
        + "|task"
        + frame["task_id"].astype(int).astype(str)
        + "|init"
        + frame["init_state_id"].astype(int).astype(str)
        + "|seed"
        + frame["rollout_seed"].astype(int).astype(str)
    )


def load_traces(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if len(paths) != 10:
        raise ValueError(f"Expected ten strategy traces, found {len(paths)}")
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frames.append(frame)
    traces = pd.concat(frames, ignore_index=True)
    required = {
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "query_idx",
        "planning_strategy",
        "planning_selected_open_loop_steps",
        "planning_requery_triggered",
        "max_value_selected",
        "max_value_sample_idx",
        "candidate_values_json",
        "success",
        "final_t",
        "experiment_split",
    }
    missing = sorted(required - set(traces.columns))
    if missing:
        raise ValueError(f"Missing trace columns: {missing}")
    traces["method"] = traces["planning_strategy"].map(method_from_strategy)
    traces["success"] = parse_bool(traces["success"])
    for column in (
        "planning_requery_triggered",
        "max_value_selected",
        "target_drop_candidate",
        "wrong_object_interaction_candidate",
        "official_safety_violation",
    ):
        if column not in traces:
            traces[column] = False
        traces[column] = parse_bool(traces[column])
    traces["state_key"] = _state_key(traces)
    return traces


def aggregate_episodes(traces: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "method",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "state_key",
    ]
    rows: list[dict[str, Any]] = []
    for values, group in traces.groupby(keys, sort=True, dropna=False):
        record = dict(zip(keys, values))
        success = bool(group["success"].any())
        final_t = int(pd.to_numeric(group["final_t"], errors="coerce").max())
        record.update(
            {
                "success": success,
                "final_t": final_t,
                "query_count": int(group["query_idx"].nunique()),
                "requery_count": int(group["planning_requery_triggered"].sum()),
                "timeout": bool((not success) and final_t >= 280),
                "target_drop": bool(group["target_drop_candidate"].any()),
                "wrong_object": bool(group["wrong_object_interaction_candidate"].any()),
                "safety_violation": bool(group["official_safety_violation"].any()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def _json_float_array(value: object) -> np.ndarray:
    try:
        parsed = json.loads(str(value))
        return np.asarray(parsed, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError, json.JSONDecodeError):
        return np.asarray([], dtype=np.float64)


def q0_pairing(traces: pd.DataFrame) -> pd.DataFrame:
    q0 = traces.loc[traces["query_idx"].eq(0)].copy()
    columns = [
        "state_key",
        "method",
        "max_value_sample_idx",
        "candidate_values_json",
    ]
    baseline = q0.loc[q0["method"].eq(BASELINE), columns].set_index("state_key")
    method = q0.loc[q0["method"].eq(METHOD), columns].set_index("state_key")
    common = baseline.index.intersection(method.index)
    rows = []
    for key in common:
        left = baseline.loc[key]
        right = method.loc[key]
        left_values = _json_float_array(left["candidate_values_json"])
        right_values = _json_float_array(right["candidate_values_json"])
        max_diff = float("inf")
        if left_values.shape == right_values.shape and left_values.size:
            max_diff = float(np.max(np.abs(left_values - right_values)))
        rows.append(
            {
                "state_key": key,
                "baseline_max_value_idx": int(left["max_value_sample_idx"]),
                "method_max_value_idx": int(right["max_value_sample_idx"]),
                "candidate_value_max_abs_diff": max_diff,
            }
        )
    return pd.DataFrame(rows)


def validate_integrity(
    traces: pd.DataFrame, episodes: pd.DataFrame, q0: pd.DataFrame
) -> dict[str, object]:
    counts = episodes.groupby("method")["state_key"].nunique().to_dict()
    state_sets = {
        method: set(episodes.loc[episodes["method"].eq(method), "state_key"])
        for method in METHOD_ORDER
    }
    common = set.intersection(*state_sets.values())
    task_counts = (
        episodes.groupby(["method", "task_id"])["state_key"].nunique().to_dict()
    )
    baseline = traces.loc[traces["method"].eq(BASELINE)]
    method = traces.loc[traces["method"].eq(METHOD)]
    method_q0 = method.loc[method["query_idx"].eq(0)]
    method_later = method.loc[method["query_idx"].gt(0)]
    integrity = {
        "episode_counts": {key: int(value) for key, value in counts.items()},
        "paired_state_count": int(len(common)),
        "identical_state_sets": all(states == common for states in state_sets.values()),
        "task_counts": {f"{method_name}|{task}": int(value) for (method_name, task), value in task_counts.items()},
        "tasks_exact": set(episodes["task_id"].astype(int)) == {8, 9},
        "init_states_20_49": bool(episodes["init_state_id"].between(20, 49).all()),
        "split_values": sorted(traces["experiment_split"].dropna().astype(str).unique().tolist()),
        "all_max_value_selected": bool(traces["max_value_selected"].all()),
        "baseline_all_h16": bool(
            pd.to_numeric(baseline["planning_selected_open_loop_steps"]).eq(16).all()
            and (~baseline["planning_requery_triggered"]).all()
        ),
        "method_q0_h8": bool(
            len(method_q0) == 60
            and pd.to_numeric(method_q0["planning_selected_open_loop_steps"]).eq(8).all()
            and method_q0["planning_requery_triggered"].all()
        ),
        "method_later_h16": bool(
            pd.to_numeric(method_later["planning_selected_open_loop_steps"]).eq(16).all()
            and (~method_later["planning_requery_triggered"]).all()
        ),
        "one_requery_per_method_episode": bool(
            episodes.loc[episodes["method"].eq(METHOD), "requery_count"].eq(1).all()
        ),
        "q0_pairs": int(len(q0)),
        "q0_candidate_indices_match": bool(
            q0["baseline_max_value_idx"].eq(q0["method_max_value_idx"]).all()
        ),
        "q0_candidate_value_max_abs_diff": float(q0["candidate_value_max_abs_diff"].max()),
    }
    expected_task_counts = {
        (method_name, task): count
        for method_name in METHOD_ORDER
        for task, count in EXPECTED_TASK_COUNTS.items()
    }
    integrity["passed"] = bool(
        counts == {BASELINE: 60, METHOD: 60}
        and integrity["paired_state_count"] == 60
        and integrity["identical_state_sets"]
        and task_counts == expected_task_counts
        and integrity["tasks_exact"]
        and integrity["init_states_20_49"]
        and integrity["split_values"] == ["generalization"]
        and integrity["all_max_value_selected"]
        and integrity["baseline_all_h16"]
        and integrity["method_q0_h8"]
        and integrity["method_later_h16"]
        and integrity["one_requery_per_method_episode"]
        and integrity["q0_pairs"] == 60
        and integrity["q0_candidate_indices_match"]
        and integrity["q0_candidate_value_max_abs_diff"] <= 1e-5
    )
    return integrity


def _task_stratified_bootstrap(
    frame: pd.DataFrame, column: str, *, samples: int = BOOTSTRAP_SAMPLES
) -> tuple[float, float]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    strata = [group[column].to_numpy(dtype=float) for _, group in frame.groupby("task_id")]
    total = sum(len(values) for values in strata)
    draws = np.zeros(samples, dtype=np.float64)
    for values in strata:
        indices = rng.integers(0, len(values), size=(samples, len(values)))
        draws += values[indices].sum(axis=1) / total
    low, high = np.quantile(draws, [0.025, 0.975])
    return float(low), float(high)


def summarize_methods(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHOD_ORDER:
        group = episodes.loc[episodes["method"].eq(method)]
        rows.append(
            {
                "method": method,
                "episodes": int(len(group)),
                "successes": int(group["success"].sum()),
                "success_rate": float(group["success"].mean()),
                "mean_queries": float(group["query_count"].mean()),
                "mean_final_t": float(group["final_t"].mean()),
                "timeout_rate": float(group["timeout"].mean()),
                "drop_rate": float(group["target_drop"].mean()),
                "wrong_object_rate": float(group["wrong_object"].mean()),
                "safety_violation_rate": float(group["safety_violation"].mean()),
                "scheduled_feedback_cost": QUERY_COST if method == METHOD else 0.0,
                "utility_c0025": float(
                    group["success"].mean() - (QUERY_COST if method == METHOD else 0.0)
                ),
            }
        )
    return pd.DataFrame(rows)


def paired_analysis(episodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = episodes.loc[episodes["method"].eq(BASELINE)].set_index("state_key")
    method = episodes.loc[episodes["method"].eq(METHOD)].set_index("state_key")
    common = baseline.index.intersection(method.index)
    paired = pd.DataFrame(
        {
            "state_key": common,
            "task_id": baseline.loc[common, "task_id"].astype(int).to_numpy(),
            "init_state_id": baseline.loc[common, "init_state_id"].astype(int).to_numpy(),
            "rollout_seed": baseline.loc[common, "rollout_seed"].astype(int).to_numpy(),
            "baseline_success": baseline.loc[common, "success"].astype(bool).to_numpy(),
            "method_success": method.loc[common, "success"].astype(bool).to_numpy(),
        }
    )
    paired["delta"] = paired["method_success"].astype(int) - paired["baseline_success"].astype(int)
    rescues = int((paired["delta"] > 0).sum())
    harms = int((paired["delta"] < 0).sum())
    low, high = _task_stratified_bootstrap(paired, "delta")
    discordant = rescues + harms
    contrast = pd.DataFrame(
        [
            {
                "paired_episodes": int(len(paired)),
                "delta_success_rate": float(paired["delta"].mean()),
                "delta_ci_low": low,
                "delta_ci_high": high,
                "rescues": rescues,
                "harms": harms,
                "mcnemar_exact_p": float(
                    binomtest(rescues, discordant, 0.5).pvalue if discordant else 1.0
                ),
            }
        ]
    )
    return paired, contrast


def task_contrasts(paired: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for task, group in paired.groupby("task_id"):
        rows.append(
            {
                "task_id": int(task),
                "pairs": int(len(group)),
                "baseline_successes": int(group["baseline_success"].sum()),
                "method_successes": int(group["method_success"].sum()),
                "delta_success_states": int(group["delta"].sum()),
                "delta_success_rate": float(group["delta"].mean()),
                "rescues": int((group["delta"] > 0).sum()),
                "harms": int((group["delta"] < 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def evaluate_gate(
    integrity: dict[str, object],
    methods: pd.DataFrame,
    contrast: pd.DataFrame,
    tasks: pd.DataFrame,
) -> dict[str, object]:
    result = contrast.iloc[0]
    indexed = methods.set_index("method")
    baseline = indexed.loc[BASELINE]
    method = indexed.loc[METHOD]
    checks = {
        "at_least_three_rescues": int(result["rescues"]) >= 3,
        "rescues_exceed_harms": int(result["rescues"]) > int(result["harms"]),
        "delta_at_least_5pp": float(result["delta_success_rate"]) >= 0.05,
        "paired_ci_nonnegative": float(result["delta_ci_low"]) >= 0.0,
        "no_task_net_loss": bool(tasks["delta_success_states"].ge(0).all()),
        "compute_adjusted_utility_above_baseline": float(method["utility_c0025"])
        > float(baseline["utility_c0025"]),
        "drop_rate_not_increased": float(method["drop_rate"]) <= float(baseline["drop_rate"]),
        "wrong_object_rate_not_increased": float(method["wrong_object_rate"])
        <= float(baseline["wrong_object_rate"]),
        "no_added_safety_violation": float(method["safety_violation_rate"])
        <= float(baseline["safety_violation_rate"]),
        "integrity_passed": bool(integrity["passed"]),
    }
    return {"checks": checks, "gate_passed": bool(all(checks.values()))}


def write_outputs(
    output_dir: Path,
    integrity: dict[str, object],
    methods: pd.DataFrame,
    paired: pd.DataFrame,
    contrast: pd.DataFrame,
    tasks: pd.DataFrame,
    q0: pd.DataFrame,
    gate: dict[str, object],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    methods.to_csv(output_dir / "method_summary.csv", index=False)
    paired.to_csv(output_dir / "paired_outcomes.csv", index=False)
    contrast.to_csv(output_dir / "paired_contrast.csv", index=False)
    tasks.to_csv(output_dir / "task_contrasts.csv", index=False)
    q0.to_csv(output_dir / "q0_pairing_integrity.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(methods["method"], methods["success_rate"], color=["#4C78A8", "#59A14F"])
    axes[0].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("Terminal success rate")
    axes[0].set_title("Independent closed-loop holdout")
    axes[0].tick_params(axis="x", rotation=12)
    task_plot = tasks.set_index("task_id")[["baseline_successes", "method_successes"]]
    task_plot.plot.bar(ax=axes[1], color=["#4C78A8", "#59A14F"])
    axes[1].set_ylabel("Successful episodes")
    axes[1].set_title("Per-task paired outcomes")
    axes[1].tick_params(axis="x", rotation=0)
    fig.tight_layout()
    plot_path = output_dir / "initial_requery_holdout.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    percent_columns = [
        "success_rate",
        "timeout_rate",
        "drop_rate",
        "wrong_object_rate",
        "safety_violation_rate",
    ]
    display_methods = methods.copy()
    for column in percent_columns:
        display_methods[column] = display_methods[column].map(lambda value: f"{100*value:.1f}%")
    display_contrast = contrast.copy()
    for column in ("delta_success_rate", "delta_ci_low", "delta_ci_high"):
        display_contrast[column] = display_contrast[column].map(lambda value: f"{100*value:.1f}%")
    lines = [
        "# Initial real-observation re-query: holdout results",
        "",
        "## Integrity",
        "",
        f"- Paired episodes: **{integrity['paired_state_count']}**.",
        f"- Query-0 candidate max difference: **{integrity['q0_candidate_value_max_abs_diff']:.3e}**.",
        f"- Integrity: **{integrity['passed']}**.",
        "",
        "## Methods",
        "",
        display_methods.to_markdown(index=False),
        "",
        "## Paired contrast",
        "",
        display_contrast.to_markdown(index=False),
        "",
        "## Per task",
        "",
        tasks.to_markdown(index=False),
        "",
        "## Frozen gate",
        "",
        f"- Overall: **{'PASS' if gate['gate_passed'] else 'FAIL'}**.",
    ]
    lines.extend(
        f"- `{name}`: {'PASS' if passed else 'FAIL'}"
        for name, passed in gate["checks"].items()
    )
    report_path = output_dir / "RESULTS.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "integrity": integrity,
        "gate": gate,
        "method_summary": methods.to_dict(orient="records"),
        "paired_contrast": contrast.to_dict(orient="records")[0],
        "task_contrasts": tasks.to_dict(orient="records"),
        "report": str(report_path),
        "plot": str(plot_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=_json_default), encoding="utf-8"
    )
    return summary


def analyze(campaign_dir: Path, output_dir: Path) -> dict[str, object]:
    traces = load_traces(campaign_dir)
    episodes = aggregate_episodes(traces)
    q0 = q0_pairing(traces)
    integrity = validate_integrity(traces, episodes, q0)
    methods = summarize_methods(episodes)
    paired, contrast = paired_analysis(episodes)
    tasks = task_contrasts(paired)
    gate = evaluate_gate(integrity, methods, contrast, tasks)
    return write_outputs(output_dir, integrity, methods, paired, contrast, tasks, q0, gate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "initial_requery_holdout"
    summary = analyze(args.campaign_dir, output_dir)
    print(json.dumps(summary["gate"], indent=2, default=_json_default))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()


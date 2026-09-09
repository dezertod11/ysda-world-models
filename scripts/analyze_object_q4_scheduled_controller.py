#!/usr/bin/env python3
"""Analyze paired full-episode validation of the fixed query-4 controller."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BASELINE = "maxV-H16"
METHOD = "maxV-Q4-H8-requery-H8"
METHOD_ORDER = (BASELINE, METHOD)


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
        "max_value_scheduled_requery": METHOD,
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


def _json_array(value: object) -> np.ndarray:
    try:
        return np.asarray(json.loads(str(value)), dtype=np.float64).reshape(-1)
    except (TypeError, ValueError, json.JSONDecodeError):
        return np.asarray([], dtype=np.float64)


def _array_max_abs(left: object, right: object) -> float:
    left_values = _json_array(left)
    right_values = _json_array(right)
    if not left_values.size or left_values.shape != right_values.shape:
        return float("inf")
    return float(np.max(np.abs(left_values - right_values)))


def load_traces(campaign_dir: Path) -> pd.DataFrame:
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
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "query_idx",
        "t",
        "sim_state_json",
        "planning_strategy",
        "planning_selected_open_loop_steps",
        "planning_requery_triggered",
        "planning_scheduled_requery_active",
        "planning_scheduled_requery_completion",
        "max_value_selected",
        "max_value_sample_idx",
        "candidate_values_json",
        "candidate_first_actions_json",
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
        "planning_scheduled_requery_active",
        "planning_scheduled_requery_completion",
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


def _last_text(group: pd.DataFrame, column: str, fallback: str) -> str:
    if column not in group:
        return fallback
    values = group[column].dropna().astype(str)
    values = values.loc[~values.str.lower().isin({"", "nan", "none"})]
    return str(values.iloc[-1]) if len(values) else fallback


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
        failure_type = _last_text(
            group, "failure_type", "success" if success else "timeout_no_goal"
        )
        record.update(
            {
                "success": success,
                "final_t": final_t,
                "query_count": int(group["query_idx"].nunique()),
                "requery_count": int(group["planning_requery_triggered"].sum()),
                "failure_type": failure_type,
                "timeout": bool((not success) and final_t >= 280),
                "target_drop": bool(group["target_drop_candidate"].any()),
                "wrong_object": bool(group["wrong_object_interaction_candidate"].any()),
                "safety_violation": bool(group["official_safety_violation"].any()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)


def prefix_integrity(
    traces: pd.DataFrame, manifest: dict[str, object]
) -> pd.DataFrame:
    target_query = int(manifest["scheduled_requery_query_idx"])
    baseline = traces.loc[traces["method"].eq(BASELINE)].set_index(
        ["state_key", "query_idx"]
    )
    method = traces.loc[traces["method"].eq(METHOD)].set_index(
        ["state_key", "query_idx"]
    )
    states = sorted(
        set(traces.loc[traces["method"].eq(BASELINE), "state_key"])
        & set(traces.loc[traces["method"].eq(METHOD), "state_key"])
    )
    rows = []
    for state_key in states:
        baseline_queries = {
            int(value) for value in baseline.loc[state_key].index.tolist()
        }
        method_queries = {int(value) for value in method.loc[state_key].index.tolist()}
        reached_boundary = target_query in baseline_queries and target_query in method_queries
        compared_queries = sorted(
            (baseline_queries & method_queries) & set(range(target_query + 1))
        )
        state_diff = 0.0
        value_diff = 0.0
        action_diff = 0.0
        indices_match = True
        times_match = True
        for query_idx in compared_queries:
            left = baseline.loc[(state_key, query_idx)]
            right = method.loc[(state_key, query_idx)]
            state_diff = max(
                state_diff,
                _array_max_abs(left["sim_state_json"], right["sim_state_json"]),
            )
            value_diff = max(
                value_diff,
                _array_max_abs(
                    left["candidate_values_json"], right["candidate_values_json"]
                ),
            )
            action_diff = max(
                action_diff,
                _array_max_abs(
                    left["candidate_first_actions_json"],
                    right["candidate_first_actions_json"],
                ),
            )
            indices_match = bool(
                indices_match
                and int(left["max_value_sample_idx"])
                == int(right["max_value_sample_idx"])
            )
            times_match = bool(times_match and int(left["t"]) == int(right["t"]))
        full_prefix = compared_queries == list(range(target_query + 1))
        strict = bool(
            reached_boundary
            and full_prefix
            and times_match
            and indices_match
            and state_diff <= float(manifest["sim_state_max_abs_tolerance"])
            and value_diff <= float(manifest["candidate_value_max_abs_tolerance"])
            and action_diff
            <= float(manifest["candidate_first_action_max_abs_tolerance"])
        )
        rows.append(
            {
                "state_key": state_key,
                "reached_boundary": reached_boundary,
                "compared_queries": len(compared_queries),
                "full_prefix": full_prefix,
                "times_match": times_match,
                "candidate_indices_match": indices_match,
                "sim_state_max_abs_diff": state_diff,
                "candidate_value_max_abs_diff": value_diff,
                "candidate_first_action_max_abs_diff": action_diff,
                "strict_prefix": strict,
            }
        )
    return pd.DataFrame(rows)


def validate_schedule(traces: pd.DataFrame, manifest: dict[str, object]) -> bool:
    target = int(manifest["scheduled_requery_query_idx"])
    baseline = traces.loc[traces["method"].eq(BASELINE)]
    method = traces.loc[traces["method"].eq(METHOD)]
    if not (
        pd.to_numeric(baseline["planning_selected_open_loop_steps"]).eq(16).all()
        and (~baseline["planning_requery_triggered"]).all()
    ):
        return False
    for _state, group in method.groupby("state_key"):
        group = group.set_index("query_idx")
        if target not in group.index:
            return False
        before = group.loc[group.index < target]
        if not pd.to_numeric(before["planning_selected_open_loop_steps"]).eq(16).all():
            return False
        if int(group.loc[target, "planning_selected_open_loop_steps"]) != 8:
            return False
        if not bool(group.loc[target, "planning_requery_triggered"]):
            return False
        if target + 1 in group.index:
            if int(group.loc[target + 1, "planning_selected_open_loop_steps"]) != 8:
                return False
            if not bool(group.loc[target + 1, "planning_scheduled_requery_completion"]):
                return False
        later = group.loc[group.index > target + 1]
        if not pd.to_numeric(later["planning_selected_open_loop_steps"]).eq(16).all():
            return False
        if int(group["planning_requery_triggered"].sum()) != 1:
            return False
    return True


def validate_integrity(
    traces: pd.DataFrame,
    episodes: pd.DataFrame,
    prefix: pd.DataFrame,
    manifest: dict[str, object],
) -> dict[str, object]:
    expected = int(manifest["target_pairs"])
    counts = episodes.groupby("method")["state_key"].nunique().to_dict()
    state_sets = {
        method: set(episodes.loc[episodes["method"].eq(method), "state_key"])
        for method in METHOD_ORDER
    }
    common = set.intersection(*state_sets.values())
    strict_count = int(prefix["strict_prefix"].sum())
    checks = {
        "trace_files": int(traces["source_trace"].nunique()),
        "episode_counts": {key: int(value) for key, value in counts.items()},
        "paired_state_count": int(len(common)),
        "identical_state_sets": all(states == common for states in state_sets.values()),
        "suite_matches": sorted(episodes["suite"].astype(str).unique().tolist())
        == [str(manifest["suite"])],
        "task_ids_match": sorted(episodes["task_id"].astype(int).unique().tolist())
        == [int(value) for value in manifest["task_ids"]],
        "init_state_ids_match": sorted(
            episodes["init_state_id"].astype(int).unique().tolist()
        )
        == [int(value) for value in manifest["init_state_ids"]],
        "split_values": sorted(
            traces["experiment_split"].dropna().astype(str).unique().tolist()
        ),
        "all_max_value_selected": bool(traces["max_value_selected"].all()),
        "schedule_valid": validate_schedule(traces, manifest),
        "strict_prefix_pairs": strict_count,
        "minimum_strict_prefix_pairs": int(manifest["minimum_strict_prefix_pairs"]),
        "max_sim_state_difference": float(prefix["sim_state_max_abs_diff"].max()),
        "max_candidate_value_difference": float(
            prefix["candidate_value_max_abs_diff"].max()
        ),
        "max_candidate_first_action_difference": float(
            prefix["candidate_first_action_max_abs_diff"].max()
        ),
    }
    checks["valid"] = bool(
        counts == {BASELINE: expected, METHOD: expected}
        and checks["paired_state_count"] == expected
        and checks["identical_state_sets"]
        and checks["suite_matches"]
        and checks["task_ids_match"]
        and checks["init_state_ids_match"]
        and checks["split_values"] == ["generalization"]
        and checks["all_max_value_selected"]
        and checks["schedule_valid"]
        and strict_count >= checks["minimum_strict_prefix_pairs"]
    )
    return checks


def paired_outcomes(
    episodes: pd.DataFrame, prefix: pd.DataFrame, query_cost: float
) -> pd.DataFrame:
    baseline = episodes.loc[episodes["method"].eq(BASELINE)].set_index("state_key")
    method = episodes.loc[episodes["method"].eq(METHOD)].set_index("state_key")
    common = baseline.index.intersection(method.index)
    paired = pd.DataFrame(
        {
            "state_key": common,
            "init_state_id": baseline.loc[common, "init_state_id"].astype(int).to_numpy(),
            "rollout_seed": baseline.loc[common, "rollout_seed"].astype(int).to_numpy(),
            "baseline_success": baseline.loc[common, "success"].astype(bool).to_numpy(),
            "method_success": method.loc[common, "success"].astype(bool).to_numpy(),
            "baseline_queries": baseline.loc[common, "query_count"].astype(int).to_numpy(),
            "method_queries": method.loc[common, "query_count"].astype(int).to_numpy(),
            "method_requeries": method.loc[common, "requery_count"].astype(int).to_numpy(),
            "baseline_failure_type": baseline.loc[common, "failure_type"].astype(str).to_numpy(),
            "method_failure_type": method.loc[common, "failure_type"].astype(str).to_numpy(),
        }
    )
    paired = paired.merge(prefix[["state_key", "strict_prefix"]], on="state_key", how="left")
    paired["strict_prefix"] = paired["strict_prefix"].fillna(False).astype(bool)
    paired["delta"] = (
        paired["method_success"].astype(int) - paired["baseline_success"].astype(int)
    )
    paired["delta_after_cost"] = paired["delta"] - query_cost * paired["method_requeries"]
    paired["terminal_outcome"] = "both_fail"
    paired.loc[paired["baseline_success"] & paired["method_success"], "terminal_outcome"] = "both_success"
    paired.loc[paired["delta"].eq(1), "terminal_outcome"] = "rescue"
    paired.loc[paired["delta"].eq(-1), "terminal_outcome"] = "harm"
    return paired


def _cluster_bootstrap(group: pd.DataFrame, column: str) -> tuple[float, float]:
    clusters = group.groupby("init_state_id")[column].agg(["sum", "size"]).to_numpy(float)
    rng = np.random.default_rng(20260901)
    draws = rng.integers(0, len(clusters), size=(10_000, len(clusters)))
    sampled = clusters[draws]
    values = sampled[:, :, 0].sum(axis=1) / sampled[:, :, 1].sum(axis=1)
    return tuple(float(value) for value in np.quantile(values, [0.025, 0.975]))


def _mcnemar_p(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if not discordant:
        return 1.0
    tail = min(rescues, harms)
    probability = sum(math.comb(discordant, index) for index in range(tail + 1))
    return float(min(1.0, 2.0 * probability / (2**discordant)))


def summarize_paired(paired: pd.DataFrame, subset: str) -> pd.DataFrame:
    group = paired if subset == "nominal" else paired.loc[paired["strict_prefix"]]
    rescues = int(group["delta"].eq(1).sum())
    harms = int(group["delta"].eq(-1).sum())
    low, high = _cluster_bootstrap(group, "delta")
    return pd.DataFrame(
        [
            {
                "subset": subset,
                "pairs": int(len(group)),
                "baseline_success_rate": float(group["baseline_success"].mean()),
                "method_success_rate": float(group["method_success"].mean()),
                "success_delta": float(group["delta"].mean()),
                "success_delta_ci_low": low,
                "success_delta_ci_high": high,
                "rescues": rescues,
                "harms": harms,
                "mcnemar_pvalue": _mcnemar_p(rescues, harms),
                "adjusted_delta": float(group["delta_after_cost"].mean()),
                "baseline_mean_queries": float(group["baseline_queries"].mean()),
                "method_mean_queries": float(group["method_queries"].mean()),
            }
        ]
    )


def evaluate_gates(
    strict_summary: pd.DataFrame,
    integrity: dict[str, object],
    manifest: dict[str, object],
) -> dict[str, bool]:
    row = strict_summary.iloc[0]
    practical = bool(
        integrity["valid"]
        and row["success_delta"] > manifest["practical_gate"]["raw_success_delta_gt"]
        and row["adjusted_delta"]
        > manifest["practical_gate"]["adjusted_terminal_delta_gt"]
    )
    confirmatory = bool(
        practical
        and row["success_delta_ci_low"]
        > manifest["confirmatory_gate"]["cluster_bootstrap_ci_low_gt"]
        and row["mcnemar_pvalue"]
        < manifest["confirmatory_gate"]["mcnemar_two_sided_p_lt"]
    )
    return {
        "integrity_pass": bool(integrity["valid"]),
        "practical_gate_pass": practical,
        "confirmatory_gate_pass": confirmatory,
    }


def analyze(campaign_dir: Path, manifest_path: Path, output_dir: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    traces = load_traces(campaign_dir)
    episodes = aggregate_episodes(traces)
    prefix = prefix_integrity(traces, manifest)
    integrity = validate_integrity(traces, episodes, prefix, manifest)
    paired = paired_outcomes(episodes, prefix, float(manifest["query_cost"]))
    nominal = summarize_paired(paired, "nominal")
    strict = summarize_paired(paired, "strict")
    summaries = pd.concat([nominal, strict], ignore_index=True)
    gates = evaluate_gates(strict, integrity, manifest)
    init_summary = (
        paired.groupby("init_state_id", as_index=False)
        .agg(
            pairs=("delta", "size"),
            baseline_success_rate=("baseline_success", "mean"),
            method_success_rate=("method_success", "mean"),
            success_delta=("delta", "mean"),
            strict_prefix=("strict_prefix", "sum"),
        )
        .sort_values("init_state_id")
    )
    transitions = (
        paired.loc[paired["delta"].ne(0)]
        .groupby(
            ["terminal_outcome", "baseline_failure_type", "method_failure_type"],
            dropna=False,
        )
        .size()
        .rename("pairs")
        .reset_index()
        .sort_values("pairs", ascending=False)
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output_dir / "paired_outcomes.csv", index=False)
    prefix.to_csv(output_dir / "prefix_integrity.csv", index=False)
    summaries.to_csv(output_dir / "paired_summary.csv", index=False)
    init_summary.to_csv(output_dir / "init_state_summary.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )

    lines = [
        "# Object task-0 query-4 scheduled controller",
        "",
        f"- Integrity: **{'PASS' if gates['integrity_pass'] else 'FAIL'}**.",
        f"- Practical gate: **{'PASS' if gates['practical_gate_pass'] else 'FAIL'}**.",
        f"- Confirmatory gate: **{'PASS' if gates['confirmatory_gate_pass'] else 'FAIL'}**.",
        "",
        "## Paired terminal endpoint",
        "",
        summaries.to_markdown(index=False),
        "",
        "## Prefix integrity",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
        "",
        "## Init-state diagnostics",
        "",
        init_summary.to_markdown(index=False),
        "",
        "## Discordant failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
    ]
    report_path = output_dir / "RESULTS.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = {
        "integrity": integrity,
        "gates": gates,
        "nominal": nominal.iloc[0].to_dict(),
        "strict": strict.iloc[0].to_dict(),
        "report": str(report_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(result, indent=2, default=_json_default), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or (
        args.campaign_dir / "analysis" / "object_q4_scheduled_controller"
    )
    result = analyze(args.campaign_dir, args.freeze_manifest, output_dir)
    print(json.dumps(result["gates"], indent=2))
    print(f"Results: {result['report']}")


if __name__ == "__main__":
    main()

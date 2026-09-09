#!/usr/bin/env python3
"""Analyze the frozen privileged phase-oracle Value-of-Feedback transfer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest


COMMIT = "commit-H16"
ALWAYS_FEEDBACK = "always-H8-requery"
PHASE_ROUTE = "phase-oracle-H16/H8"
TRIGGER_PHASES = frozenset({"grasp", "transport"})
EXPECTED_TASKS = {5, 8, 9}
REPLAY_THRESHOLD = 1e-9
QUERY_COST = 0.025


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    return values.fillna(False).map(
        lambda value: str(value).strip().lower() in {"1", "true", "yes"}
    )


def _source_name(path: Path, suffix: str) -> str:
    return path.name.removesuffix(suffix)


def load_relabelled(dense_campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_dir = dense_campaign_dir / "runs"
    feedback_paths = sorted(run_dir.glob("*__feedback_pairs.parquet"))
    candidate_paths = sorted(run_dir.glob("*__candidate_outcomes.parquet"))
    if len(feedback_paths) != 4 or len(candidate_paths) != 4:
        raise ValueError(
            f"Expected four feedback and candidate shard files, got "
            f"{len(feedback_paths)} and {len(candidate_paths)}"
        )
    feedback_frames = []
    for path in feedback_paths:
        frame = pd.read_parquet(path)
        frame["source_run"] = _source_name(path, "__feedback_pairs.parquet")
        feedback_frames.append(frame)
    candidate_frames = []
    for path in candidate_paths:
        frame = pd.read_parquet(path)
        frame["source_run"] = _source_name(path, "__candidate_outcomes.parquet")
        candidate_frames.append(frame)
    return (
        pd.concat(feedback_frames, ignore_index=True),
        pd.concat(candidate_frames, ignore_index=True),
    )


def prepare_states(feedback: pd.DataFrame) -> pd.DataFrame:
    required = {
        "source_run",
        "snapshot_id",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "phase_at_snapshot",
        "experiment_split",
        "main_open_replay_state_max_abs",
        "dense_vof_v2",
        "open_terminal_available",
        "feedback_terminal_available",
        "open_terminal_success",
        "feedback_terminal_success",
    }
    missing = sorted(required - set(feedback.columns))
    if missing:
        raise ValueError(f"Missing feedback columns: {missing}")
    states = feedback.copy()
    states["state_uid"] = states["source_run"].astype(str) + "::" + states[
        "snapshot_id"
    ].astype(str)
    states["task_id"] = pd.to_numeric(states["task_id"], errors="raise").astype(int)
    states["init_state_id"] = pd.to_numeric(
        states["init_state_id"], errors="raise"
    ).astype(int)
    states["phase"] = states["phase_at_snapshot"].astype(str).str.lower()
    states["trigger"] = states["phase"].isin(TRIGGER_PHASES)
    states["replay_error"] = pd.to_numeric(
        states["main_open_replay_state_max_abs"], errors="coerce"
    )
    states["strict_replay"] = states["replay_error"].le(REPLAY_THRESHOLD)
    states["terminal_available"] = _bool_series(
        states["open_terminal_available"]
    ) & _bool_series(states["feedback_terminal_available"])
    states["commit_success"] = _bool_series(states["open_terminal_success"])
    states["feedback_success"] = _bool_series(states["feedback_terminal_success"])
    states["route_success"] = np.where(
        states["trigger"], states["feedback_success"], states["commit_success"]
    ).astype(bool)
    states["terminal_feedback_delta"] = (
        states["feedback_success"].astype(int) - states["commit_success"].astype(int)
    )
    states["route_terminal_delta"] = (
        states["route_success"].astype(int) - states["commit_success"].astype(int)
    )
    states["dense_vof"] = pd.to_numeric(states["dense_vof_v2"], errors="coerce")
    states["route_dense_delta"] = np.where(
        states["trigger"], states["dense_vof"], 0.0
    )
    states["independent_group"] = (
        "task"
        + states["task_id"].astype(str)
        + "|init"
        + states["init_state_id"].astype(str)
    )
    for endpoint in ("drop", "wrong", "safety"):
        source = {
            "drop": "terminal_target_drop_candidate",
            "wrong": "terminal_wrong_object_interaction_candidate",
            "safety": "terminal_official_safety_violation",
        }[endpoint]
        commit_col = f"open_{source}"
        feedback_col = f"feedback_{source}"
        states[f"commit_{endpoint}"] = _bool_series(states[commit_col])
        states[f"feedback_{endpoint}"] = _bool_series(states[feedback_col])
        states[f"route_{endpoint}"] = np.where(
            states["trigger"],
            states[f"feedback_{endpoint}"],
            states[f"commit_{endpoint}"],
        ).astype(bool)
    return states


def validate_integrity(
    states: pd.DataFrame, candidates: pd.DataFrame
) -> dict[str, object]:
    task_counts = states.groupby("task_id")["state_uid"].nunique().to_dict()
    strict_counts = (
        states.loc[states["strict_replay"]]
        .groupby("task_id")["state_uid"]
        .nunique()
        .to_dict()
    )
    strict = states.loc[states["strict_replay"] & states["terminal_available"]]
    triggered = strict.loc[strict["trigger"]]
    candidate_counts = candidates.groupby(["source_run", "snapshot_id"])[
        "candidate_idx"
    ].nunique()
    terminal_counts = (
        candidates.assign(
            terminal_flag=_bool_series(candidates["terminal_available"])
        )
        .groupby(["source_run", "snapshot_id"])["terminal_flag"]
        .sum()
    )
    terminal_candidates = candidates.loc[_bool_series(candidates["terminal_available"])]
    selected_terminal_only = bool(
        len(terminal_candidates) == len(states)
        and _bool_series(terminal_candidates["candidate_is_max_value"]).all()
        and terminal_counts.eq(1).all()
    )
    integrity = {
        "source_run_count": int(states["source_run"].nunique()),
        "state_count": int(states["state_uid"].nunique()),
        "task_counts": {str(key): int(value) for key, value in task_counts.items()},
        "strict_state_count": int(len(strict)),
        "strict_task_counts": {
            str(key): int(value) for key, value in strict_counts.items()
        },
        "terminal_pairs_complete": bool(states["terminal_available"].all()),
        "tasks_exact": set(states["task_id"]) == EXPECTED_TASKS,
        "init_states_in_10_19": bool(states["init_state_id"].between(10, 19).all()),
        "split_values": sorted(states["experiment_split"].astype(str).unique().tolist()),
        "candidate_sets_are_k4": bool(candidate_counts.eq(4).all()),
        "selected_terminal_only": selected_terminal_only,
        "triggered_strict_states": int(len(triggered)),
        "triggered_independent_groups": int(triggered["independent_group"].nunique()),
        "strict_replay_threshold": REPLAY_THRESHOLD,
        "max_replay_error": float(states["replay_error"].max()),
    }
    integrity["passed"] = bool(
        integrity["state_count"] == 78
        and integrity["source_run_count"] == 4
        and task_counts == {5: 34, 8: 14, 9: 30}
        and integrity["strict_state_count"] >= 66
        and strict_counts.get(5, 0) >= 25
        and strict_counts.get(8, 0) >= 12
        and strict_counts.get(9, 0) >= 25
        and integrity["terminal_pairs_complete"]
        and integrity["tasks_exact"]
        and integrity["init_states_in_10_19"]
        and integrity["split_values"] == ["generalization"]
        and integrity["candidate_sets_are_k4"]
        and integrity["selected_terminal_only"]
        and integrity["triggered_strict_states"] >= 15
        and integrity["triggered_independent_groups"] >= 10
    )
    return integrity


def _grouped_bootstrap_mean(
    frame: pd.DataFrame,
    value_column: str,
    *,
    samples: int = 5000,
    seed: int = 20260831,
) -> tuple[float, float]:
    usable = frame.loc[np.isfinite(pd.to_numeric(frame[value_column], errors="coerce"))]
    if usable.empty:
        return float("nan"), float("nan")
    strata = {
        int(task): [group.copy() for _key, group in task_frame.groupby("independent_group")]
        for task, task_frame in usable.groupby("task_id")
    }
    rng = np.random.default_rng(seed)
    values = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        chunks = []
        for groups in strata.values():
            chosen = rng.integers(0, len(groups), size=len(groups))
            chunks.extend(groups[offset] for offset in chosen)
        values[index] = pd.concat(chunks, ignore_index=True)[value_column].mean()
    return tuple(float(value) for value in np.quantile(values, [0.025, 0.975]))


def summarize_methods(strict: pd.DataFrame) -> pd.DataFrame:
    rows = []
    specifications = [
        (COMMIT, "commit_success", "commit_drop", "commit_wrong", "commit_safety", 0.0),
        (
            ALWAYS_FEEDBACK,
            "feedback_success",
            "feedback_drop",
            "feedback_wrong",
            "feedback_safety",
            1.0,
        ),
        (
            PHASE_ROUTE,
            "route_success",
            "route_drop",
            "route_wrong",
            "route_safety",
            float(strict["trigger"].mean()),
        ),
    ]
    for method, success, drop, wrong, safety, intervention_rate in specifications:
        rows.append(
            {
                "method": method,
                "states": int(len(strict)),
                "successes": int(strict[success].sum()),
                "success_rate": float(strict[success].mean()),
                "intervention_rate": float(intervention_rate),
                "utility_c0025": float(strict[success].mean() - QUERY_COST * intervention_rate),
                "drop_rate": float(strict[drop].mean()),
                "wrong_object_rate": float(strict[wrong].mean()),
                "safety_violation_rate": float(strict[safety].mean()),
            }
        )
    return pd.DataFrame(rows)


def paired_contrasts(strict: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, outcome, delta in [
        (ALWAYS_FEEDBACK, "feedback_success", "terminal_feedback_delta"),
        (PHASE_ROUTE, "route_success", "route_terminal_delta"),
    ]:
        rescues = int(((~strict["commit_success"]) & strict[outcome]).sum())
        harms = int((strict["commit_success"] & (~strict[outcome])).sum())
        low, high = _grouped_bootstrap_mean(strict, delta)
        discordant = rescues + harms
        p_value = (
            float(binomtest(rescues, discordant, 0.5).pvalue)
            if discordant
            else 1.0
        )
        rows.append(
            {
                "method": method,
                "states": int(len(strict)),
                "delta_success_rate": float(strict[delta].mean()),
                "delta_ci_low": low,
                "delta_ci_high": high,
                "rescues": rescues,
                "harms": harms,
                "mcnemar_exact_p": p_value,
            }
        )
    return pd.DataFrame(rows)


def task_phase_tables(strict: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    task_rows = []
    for task, group in strict.groupby("task_id"):
        task_rows.append(
            {
                "task_id": int(task),
                "states": int(len(group)),
                "commit_successes": int(group["commit_success"].sum()),
                "route_successes": int(group["route_success"].sum()),
                "delta_success_states": int(group["route_terminal_delta"].sum()),
                "rescues": int(((~group["commit_success"]) & group["route_success"]).sum()),
                "harms": int((group["commit_success"] & (~group["route_success"])).sum()),
                "trigger_rate": float(group["trigger"].mean()),
                "mean_route_dense_delta": float(group["route_dense_delta"].mean()),
            }
        )
    phase = (
        strict.groupby("phase", as_index=False)
        .agg(
            states=("state_uid", "size"),
            independent_groups=("independent_group", "nunique"),
            mean_dense_vof=("dense_vof", "mean"),
            positive_dense_rate=("dense_vof", lambda values: float((values > 0).mean())),
            terminal_rescues=("terminal_feedback_delta", lambda values: int((values > 0).sum())),
            terminal_harms=("terminal_feedback_delta", lambda values: int((values < 0).sum())),
        )
        .sort_values("phase")
    )
    return pd.DataFrame(task_rows), phase


def dense_summary(strict: pd.DataFrame) -> dict[str, float]:
    triggered = strict.loc[strict["trigger"]]
    low, high = _grouped_bootstrap_mean(triggered, "dense_vof")
    return {
        "triggered_states": int(len(triggered)),
        "trigger_rate": float(strict["trigger"].mean()),
        "triggered_mean_dense_vof": float(triggered["dense_vof"].mean()),
        "triggered_dense_ci_low": low,
        "triggered_dense_ci_high": high,
        "routed_dense_uplift_per_decision": float(strict["route_dense_delta"].mean()),
        "always_feedback_dense_uplift_per_decision": float(strict["dense_vof"].mean()),
        "matched_random_expected_dense_uplift": float(
            strict["trigger"].mean() * strict["dense_vof"].mean()
        ),
    }


def evaluate_gate(
    integrity: dict[str, object],
    methods: pd.DataFrame,
    contrasts: pd.DataFrame,
    tasks: pd.DataFrame,
    dense: dict[str, float],
) -> dict[str, object]:
    route = contrasts.loc[contrasts["method"].eq(PHASE_ROUTE)].iloc[0]
    commit_utility = float(methods.loc[methods["method"].eq(COMMIT), "utility_c0025"].iloc[0])
    route_row = methods.loc[methods["method"].eq(PHASE_ROUTE)].iloc[0]
    checks = {
        "at_least_three_terminal_rescues": int(route["rescues"]) >= 3,
        "rescues_exceed_harms": int(route["rescues"]) > int(route["harms"]),
        "terminal_delta_at_least_3pp": float(route["delta_success_rate"]) >= 0.03,
        "no_task_loses_more_than_one": bool(tasks["delta_success_states"].ge(-1).all()),
        "triggered_dense_mean_positive": dense["triggered_mean_dense_vof"] > 0.0,
        "triggered_dense_ci_nonnegative": dense["triggered_dense_ci_low"] >= 0.0,
        "route_dense_beats_always_feedback": (
            dense["routed_dense_uplift_per_decision"]
            > dense["always_feedback_dense_uplift_per_decision"]
        ),
        "compute_adjusted_utility_above_commit": float(route_row["utility_c0025"])
        > commit_utility,
        "no_added_official_safety_violation": float(route_row["safety_violation_rate"])
        <= float(methods.loc[methods["method"].eq(COMMIT), "safety_violation_rate"].iloc[0]),
        "integrity_passed": bool(integrity["passed"]),
    }
    return {"checks": checks, "gate_passed": bool(all(checks.values()))}


def make_plots(
    strict: pd.DataFrame, methods: pd.DataFrame, output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    phase_order = [phase for phase in ["approach", "grasp", "transport", "release"] if phase in set(strict["phase"])]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    data = [strict.loc[strict["phase"].eq(phase), "dense_vof"].dropna() for phase in phase_order]
    axes[0].boxplot(data, labels=phase_order, showmeans=True)
    axes[0].axhline(0.0, color="black", linestyle="--", linewidth=1)
    axes[0].set_title("Exact-state dense Value of Feedback")
    axes[0].set_ylabel("feedback - commit")
    axes[1].bar(methods["method"], methods["success_rate"], color=["#4C78A8", "#E45756", "#59A14F"])
    axes[1].set_ylim(0.0, 1.0)
    axes[1].set_title("Terminal success on the same snapshots")
    axes[1].tick_params(axis="x", rotation=18)
    fig.tight_layout()
    path = output_dir / "phase_vof_terminal_transfer.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [path]


def _percent_frame(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result:
            result[column] = result[column].map(
                lambda value: f"{100.0 * float(value):.1f}%" if np.isfinite(value) else "nan"
            )
    return result


def write_report(
    output_dir: Path,
    integrity: dict[str, object],
    methods: pd.DataFrame,
    contrasts: pd.DataFrame,
    tasks: pd.DataFrame,
    phases: pd.DataFrame,
    dense: dict[str, float],
    gate: dict[str, object],
) -> Path:
    method_display = _percent_frame(
        methods,
        ["success_rate", "intervention_rate", "drop_rate", "wrong_object_rate", "safety_violation_rate"],
    )
    contrast_display = _percent_frame(
        contrasts, ["delta_success_rate", "delta_ci_low", "delta_ci_high"]
    )
    lines = [
        "# Phase-aware terminal Value of Feedback: transfer results",
        "",
        "## Scope",
        "",
        "This is a privileged phase-oracle upper bound, not a deployable planner.",
        "",
        "## Integrity",
        "",
        f"- States: **{integrity['state_count']}**; strict: **{integrity['strict_state_count']}**.",
        f"- Triggered strict states/groups: **{integrity['triggered_strict_states']} / {integrity['triggered_independent_groups']}**.",
        f"- Integrity: **{integrity['passed']}**.",
        "",
        "## Terminal outcomes",
        "",
        method_display.to_markdown(index=False),
        "",
        "## Paired contrasts versus commit",
        "",
        contrast_display.to_markdown(index=False),
        "",
        "## Per-task route effects",
        "",
        tasks.to_markdown(index=False),
        "",
        "## Phase mechanism",
        "",
        phases.to_markdown(index=False),
        "",
        "## Dense routing summary",
        "",
        "```json",
        json.dumps(dense, indent=2, default=_json_default),
        "```",
        "",
        "## Frozen gate",
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
            "A PASS authorizes an observable phase-detector experiment; a FAIL closes this phase rule.",
            "",
            "## Figure",
            "",
            "- `phase_vof_terminal_transfer.png`",
            "",
        ]
    )
    path = output_dir / "RESULTS.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def analyze(dense_campaign_dir: Path, output_dir: Path) -> dict[str, object]:
    feedback, candidates = load_relabelled(dense_campaign_dir)
    states = prepare_states(feedback)
    integrity = validate_integrity(states, candidates)
    strict = states.loc[states["strict_replay"] & states["terminal_available"]].copy()
    methods = summarize_methods(strict)
    contrasts = paired_contrasts(strict)
    tasks, phases = task_phase_tables(strict)
    dense = dense_summary(strict)
    gate = evaluate_gate(integrity, methods, contrasts, tasks, dense)
    output_dir.mkdir(parents=True, exist_ok=True)
    states.to_csv(output_dir / "all_snapshot_outcomes.csv", index=False)
    strict.to_csv(output_dir / "strict_snapshot_outcomes.csv", index=False)
    methods.to_csv(output_dir / "method_summary.csv", index=False)
    contrasts.to_csv(output_dir / "paired_contrasts.csv", index=False)
    tasks.to_csv(output_dir / "task_contrasts.csv", index=False)
    phases.to_csv(output_dir / "phase_summary.csv", index=False)
    plots = make_plots(strict, methods, output_dir)
    report = write_report(
        output_dir, integrity, methods, contrasts, tasks, phases, dense, gate
    )
    summary = {
        "dense_campaign_dir": str(dense_campaign_dir),
        "integrity": integrity,
        "gate": gate,
        "dense_summary": dense,
        "method_summary": methods.to_dict(orient="records"),
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
    parser.add_argument("--dense-campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.dense_campaign_dir / "analysis" / "phase_vof_terminal_transfer"
    summary = analyze(args.dense_campaign_dir, output_dir)
    print(json.dumps(summary["gate"], indent=2, default=_json_default))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()

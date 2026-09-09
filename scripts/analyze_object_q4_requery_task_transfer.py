#!/usr/bin/env python3
"""Analyze frozen query-4 re-query transfer to untouched Object tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from analyze_counterfactual_feedback import load_campaign
    from analyze_terminal_event_atlas import (
        event_transition_summary,
        prepare_terminal_frame,
        summarize_terminal_effect,
    )
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import load_campaign
    from scripts.analyze_terminal_event_atlas import (
        event_transition_summary,
        prepare_terminal_frame,
        summarize_terminal_effect,
    )


def validate_transfer(frame: pd.DataFrame, manifest: dict[str, object]) -> dict[str, object]:
    expected_tasks = {int(value) for value in manifest["task_ids"]}
    expected_inits = {int(value) for value in manifest["init_state_ids"]}
    expected_queries = {int(value) for value in manifest["snapshot_query_indices"]}
    observed_tasks = {int(value) for value in frame["task_id"].unique()}
    observed_inits = {int(value) for value in frame["init_state_id"].unique()}
    observed_queries = {int(value) for value in frame["query_idx"].unique()}
    coverage = frame.groupby(["task_id", "init_state_id"], dropna=False).size()
    expected_cells = len(expected_tasks) * len(expected_inits)
    strict_threshold = float(manifest["replay_integrity_threshold"])
    replay_error = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    checks = {
        "suite_matches": sorted(frame["suite"].astype(str).unique().tolist())
        == [str(manifest["suite"])],
        "task_ids_match": observed_tasks == expected_tasks,
        "task0_excluded": 0 not in observed_tasks,
        "init_state_ids_match": observed_inits == expected_inits,
        "query_indices_match": observed_queries == expected_queries,
        "observed_pairs": int(len(frame)),
        "target_pairs": int(manifest["target_pairs"]),
        "observed_task_init_cells": int(len(coverage)),
        "target_task_init_cells": int(expected_cells),
        "pairs_per_cell_values": sorted({int(value) for value in coverage.tolist()}),
        "expected_pairs_per_cell": int(manifest["rollouts_per_task_init"]),
        "duplicate_analysis_states": int(frame["analysis_state_key"].duplicated().sum()),
        "strict_integrity_states": int(replay_error.le(strict_threshold).sum()),
        "max_replay_state_abs": float(replay_error.max()),
    }
    checks["valid"] = bool(
        checks["suite_matches"]
        and checks["task_ids_match"]
        and checks["task0_excluded"]
        and checks["init_state_ids_match"]
        and checks["query_indices_match"]
        and checks["observed_pairs"] == checks["target_pairs"]
        and checks["observed_task_init_cells"] == checks["target_task_init_cells"]
        and checks["pairs_per_cell_values"] == [checks["expected_pairs_per_cell"]]
        and checks["duplicate_analysis_states"] == 0
        and checks["strict_integrity_states"] == checks["target_pairs"]
    )
    return checks


def evaluate_gates(
    overall: pd.DataFrame, integrity: dict[str, object], manifest: dict[str, object]
) -> dict[str, bool]:
    row = overall.iloc[0]
    practical = bool(
        integrity["valid"]
        and row["success_delta"] > manifest["practical_gate"]["raw_success_delta_gt"]
        and row["always_requery_adjusted_delta"]
        > manifest["practical_gate"]["adjusted_terminal_delta_gt"]
    )
    confirmatory = bool(
        practical
        and row["success_delta_ci_low"]
        > manifest["confirmatory_gate"]["cluster_bootstrap_ci_low_gt"]
        and row["discordance_pvalue"]
        < manifest["confirmatory_gate"]["mcnemar_two_sided_p_lt"]
    )
    return {
        "integrity_pass": bool(integrity["valid"]),
        "practical_gate_pass": practical,
        "confirmatory_gate_pass": confirmatory,
    }


def write_report(
    *,
    frame: pd.DataFrame,
    overall: pd.DataFrame,
    task_summary: pd.DataFrame,
    phase_summary: pd.DataFrame,
    task_phase_summary: pd.DataFrame,
    transitions: pd.DataFrame,
    integrity: dict[str, object],
    gates: dict[str, bool],
    output_dir: Path,
) -> None:
    task_macro_delta = float(task_summary["success_delta"].mean())
    lines = [
        "# Object query-4 re-query: untouched-task transfer",
        "",
        f"- Exact-state pairs: **{len(frame)}**.",
        f"- Untouched tasks: **{frame['task_id'].nunique()}**.",
        f"- Task/init clusters: **{frame['independent_group'].nunique()}**.",
        f"- Rescue / harm: **{int(frame['rescue'].sum())} / {int(frame['harm'].sum())}**.",
        f"- Task-macro delta: **{100 * task_macro_delta:+.2f} pp**.",
        f"- Integrity gate: **{'PASS' if gates['integrity_pass'] else 'FAIL'}**.",
        f"- Practical transfer gate: **{'PASS' if gates['practical_gate_pass'] else 'FAIL'}**.",
        f"- Confirmatory transfer gate: **{'PASS' if gates['confirmatory_gate_pass'] else 'FAIL'}**.",
        "",
        "## Primary endpoint",
        "",
        overall.to_markdown(index=False),
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
        "",
        "## By untouched task",
        "",
        task_summary.to_markdown(index=False),
        "",
        "## By policy phase",
        "",
        phase_summary.to_markdown(index=False),
        "",
        "## By task and phase",
        "",
        task_phase_summary.to_markdown(index=False),
        "",
        "## Discordant failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
        "",
        "## Frozen decision",
        "",
        "The fixed query-4 schedule transfers suite-wide only when the practical gate passes.",
        "A confirmatory transfer claim additionally requires a positive lower cluster-CI bound",
        "and exact McNemar `p<0.05`. Per-task and phase rows remain diagnostics.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (
        campaign_dir / "analysis" / "object_q4_task_transfer"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.freeze_manifest.expanduser().read_text(encoding="utf-8"))
    feedback, _candidates = load_campaign(campaign_dir)
    if feedback.empty:
        raise FileNotFoundError(f"No feedback pairs under {campaign_dir / 'runs'}")

    frame = prepare_terminal_frame(feedback)
    integrity = validate_transfer(frame, manifest)
    overall = summarize_terminal_effect(frame, ())
    task_summary = summarize_terminal_effect(frame, ("task_id",))
    phase_summary = summarize_terminal_effect(frame, ("phase_at_snapshot",))
    task_phase_summary = summarize_terminal_effect(
        frame, ("task_id", "phase_at_snapshot")
    )
    transitions = event_transition_summary(frame)
    gates = evaluate_gates(overall, integrity, manifest)

    frame.to_parquet(output_dir / "transfer_pairs.parquet", index=False)
    overall.to_csv(output_dir / "primary_endpoint.csv", index=False)
    task_summary.to_csv(output_dir / "task_summary.csv", index=False)
    phase_summary.to_csv(output_dir / "phase_summary.csv", index=False)
    task_phase_summary.to_csv(output_dir / "task_phase_summary.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    write_report(
        frame=frame,
        overall=overall,
        task_summary=task_summary,
        phase_summary=phase_summary,
        task_phase_summary=task_phase_summary,
        transitions=transitions,
        integrity=integrity,
        gates=gates,
        output_dir=output_dir,
    )

    row = overall.iloc[0]
    summary = {
        "states": int(len(frame)),
        "tasks": int(frame["task_id"].nunique()),
        "task_init_clusters": int(frame["independent_group"].nunique()),
        "rescues": int(frame["rescue"].sum()),
        "harms": int(frame["harm"].sum()),
        "raw_success_delta": float(row["success_delta"]),
        "task_macro_success_delta": float(task_summary["success_delta"].mean()),
        "adjusted_terminal_delta": float(row["always_requery_adjusted_delta"]),
        "success_delta_ci_low": float(row["success_delta_ci_low"]),
        "success_delta_ci_high": float(row["success_delta_ci_high"]),
        "mcnemar_pvalue": float(row["discordance_pvalue"]),
        **gates,
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


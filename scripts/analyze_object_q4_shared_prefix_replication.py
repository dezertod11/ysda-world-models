#!/usr/bin/env python3
"""Analyze the frozen shared-prefix Object task-0 replication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
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


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.fillna(False).astype(str).str.lower().isin({"1", "true", "yes"})


def expected_keys(manifest: dict[str, Any]) -> set[tuple[int, int, int]]:
    result = set()
    step = int(manifest["rollout_seed_step"])
    rollouts = int(manifest["rollouts_per_init"])
    for shard in manifest["shards"]:
        base_seed = int(shard["base_seed"])
        for init_position, init_state_id in enumerate(shard["init_state_ids"]):
            for rollout_id in range(rollouts):
                episode_position = init_position * rollouts + rollout_id
                result.add(
                    (
                        int(init_state_id),
                        rollout_id,
                        base_seed + episode_position * step,
                    )
                )
    return result


def validate_integrity(
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, object]:
    observed_keys = {
        (int(row.init_state_id), int(row.rollout_id), int(row.rollout_seed))
        for row in frame.itertuples(index=False)
    }
    expected = expected_keys(manifest)
    replay_error = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    strict_count = int(replay_error.le(float(manifest["replay_integrity_threshold"])).sum())
    feedback_column = (
        "feedback_feedback_requery_performed"
        if "feedback_feedback_requery_performed" in frame
        else "feedback_requery_performed"
    )
    feedback_performed = (
        _as_bool(frame[feedback_column])
        if feedback_column in frame
        else pd.Series(False, index=frame.index)
    )
    feedback_success = _as_bool(frame["feedback_terminal_success"])
    feedback_path_valid = feedback_performed | feedback_success
    terminal_columns = ["open_terminal_success", "feedback_terminal_success"]
    candidate_counts = candidates.groupby("snapshot_id").size()
    candidate_max_counts = (
        candidates.assign(_is_max=_as_bool(candidates["candidate_is_max_value"]))
        .groupby("snapshot_id")["_is_max"]
        .sum()
    )
    checks = {
        "pairs": int(len(frame)),
        "target_pairs": int(manifest["target_pairs"]),
        "expected_keys_match": observed_keys == expected,
        "missing_keys": len(expected - observed_keys),
        "unexpected_keys": len(observed_keys - expected),
        "duplicate_snapshot_ids": int(frame["snapshot_id"].duplicated().sum()),
        "suite_matches": sorted(frame["suite"].astype(str).unique().tolist())
        == [str(manifest["suite"])],
        "task_matches": sorted(frame["task_id"].astype(int).unique().tolist())
        == [int(value) for value in manifest["task_ids"]],
        "query_matches": sorted(frame["query_idx"].astype(int).unique().tolist())
        == [int(manifest["snapshot_query_idx"])],
        "init_states_match": sorted(frame["init_state_id"].astype(int).unique().tolist())
        == [int(value) for value in manifest["init_state_ids"]],
        "split_matches": sorted(frame["experiment_split"].astype(str).unique().tolist())
        == [str(manifest["experiment_split"])],
        "feedback_performed": int(feedback_performed.sum()),
        "completed_before_requery": int((~feedback_performed & feedback_success).sum()),
        "feedback_paths_valid": int(feedback_path_valid.sum()),
        "terminal_labels_complete": bool(frame[terminal_columns].notna().all().all()),
        "candidate_pool_size_valid": bool(
            len(candidate_counts) == len(frame)
            and candidate_counts.eq(int(manifest["num_candidates"])).all()
        ),
        "one_max_value_candidate_per_pool": bool(
            len(candidate_max_counts) == len(frame) and candidate_max_counts.eq(1).all()
        ),
        "strict_replay_pairs": strict_count,
        "minimum_strict_replay_pairs": int(manifest["minimum_strict_replay_pairs"]),
        "max_replay_state_abs_error": float(replay_error.max()),
    }
    checks["valid"] = bool(
        checks["pairs"] == checks["target_pairs"]
        and checks["expected_keys_match"]
        and checks["duplicate_snapshot_ids"] == 0
        and checks["suite_matches"]
        and checks["task_matches"]
        and checks["query_matches"]
        and checks["init_states_match"]
        and checks["split_matches"]
        and checks["feedback_paths_valid"] == checks["target_pairs"]
        and checks["terminal_labels_complete"]
        and checks["candidate_pool_size_valid"]
        and checks["one_max_value_candidate_per_pool"]
        and strict_count >= checks["minimum_strict_replay_pairs"]
    )
    return checks


def gate_results(
    strict_overall: pd.DataFrame,
    integrity: dict[str, object],
    manifest: dict[str, Any],
) -> dict[str, bool]:
    if strict_overall.empty:
        return {
            "integrity_pass": bool(integrity["valid"]),
            "practical_gate_pass": False,
            "confirmatory_gate_pass": False,
        }
    row = strict_overall.iloc[0]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "object_q4_shared_prefix")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.freeze_manifest.expanduser().read_text(encoding="utf-8"))
    feedback, candidates = load_campaign(campaign_dir)
    if feedback.empty or candidates.empty:
        raise FileNotFoundError("Shared-prefix feedback/candidate artifacts are missing")
    frame = prepare_terminal_frame(feedback)
    integrity = validate_integrity(frame, candidates, manifest)
    strict_frame = frame.loc[frame["strict_integrity"]].copy()
    nominal = summarize_terminal_effect(frame, ())
    strict = summarize_terminal_effect(strict_frame, ())
    init_summary = summarize_terminal_effect(strict_frame, ("init_state_id",))
    rollout_summary = summarize_terminal_effect(strict_frame, ("rollout_id",))
    transitions = event_transition_summary(strict_frame)
    gates = gate_results(strict, integrity, manifest)

    frame.to_parquet(output_dir / "paired_outcomes.parquet", index=False)
    frame.to_csv(output_dir / "paired_outcomes.csv", index=False)
    nominal.to_csv(output_dir / "nominal_endpoint.csv", index=False)
    strict.to_csv(output_dir / "primary_strict_endpoint.csv", index=False)
    init_summary.to_csv(output_dir / "init_state_summary.csv", index=False)
    rollout_summary.to_csv(output_dir / "rollout_position_summary.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    strict_row = strict.iloc[0].to_dict() if len(strict) else {}
    summary = {
        "integrity": integrity,
        "gates": gates,
        "nominal": nominal.iloc[0].to_dict(),
        "strict": strict_row,
        "report": str(output_dir / "RESULTS.md"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=lambda value: value.item()),
        encoding="utf-8",
    )
    lines = [
        "# Object task-0 query-4 shared-prefix replication",
        "",
        f"- Integrity: **{'PASS' if gates['integrity_pass'] else 'FAIL'}**.",
        f"- Practical gate: **{'PASS' if gates['practical_gate_pass'] else 'FAIL'}**.",
        f"- Confirmatory gate: **{'PASS' if gates['confirmatory_gate_pass'] else 'FAIL'}**.",
        "",
        "## Primary strict endpoint",
        "",
        strict.to_markdown(index=False) if len(strict) else "No strict pairs.",
        "",
        "## Nominal sensitivity",
        "",
        nominal.to_markdown(index=False),
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
        "",
        "## Rollout-position sensitivity",
        "",
        rollout_summary.to_markdown(index=False),
        "",
        "## Failure transitions on strict pairs",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=lambda value: value.item()))


if __name__ == "__main__":
    main()

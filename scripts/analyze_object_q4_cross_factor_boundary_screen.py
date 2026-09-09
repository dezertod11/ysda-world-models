#!/usr/bin/env python3
"""Analyze the frozen task-0 query-4 cross-factor development screen."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from analyze_counterfactual_feedback import load_campaign
    from analyze_terminal_event_atlas import prepare_terminal_frame, summarize_terminal_effect
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import load_campaign
    from scripts.analyze_terminal_event_atlas import (
        prepare_terminal_frame,
        summarize_terminal_effect,
    )


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.fillna(False).astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def expected_keys(manifest: dict[str, Any]) -> set[tuple[str, str, int, int, int]]:
    result: set[tuple[str, str, int, int, int]] = set()
    rollouts = int(manifest["rollouts_per_init"])
    step = int(manifest["rollout_seed_step"])
    for cell in manifest["cells"]:
        for init_position, init_state_id in enumerate(cell["init_state_ids"]):
            for rollout_id in range(rollouts):
                episode_position = init_position * rollouts + rollout_id
                result.add(
                    (
                        str(cell["case_id"]),
                        str(cell["suite"]),
                        int(init_state_id),
                        rollout_id,
                        int(cell["base_seed"]) + episode_position * step,
                    )
                )
    return result


def attach_cell_metadata(frame: pd.DataFrame, manifest: dict[str, Any]) -> pd.DataFrame:
    metadata = pd.DataFrame(
        [
            {
                "case_id": str(cell["case_id"]),
                "factor": str(cell["factor"]),
                "perturbation": str(
                    cell.get("position_level", f"environment-seed-{cell.get('environment_seed')}")
                ),
            }
            for cell in manifest["cells"]
        ]
    )
    # load_campaign derives a broad factor from the suite name.  The temporary
    # Position suite still contains "object", so the frozen cell metadata is
    # the authoritative factor label for this cross-factor analysis.
    result = frame.drop(columns=["factor", "perturbation"], errors="ignore").merge(
        metadata, on="case_id", how="left", validate="many_to_one"
    )
    result["independent_group"] = (
        result["case_id"].astype(str) + "|" + result["independent_group"].astype(str)
    )
    return result


def validate_integrity(
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, object]:
    observed = {
        (
            str(row.case_id),
            str(row.suite),
            int(row.init_state_id),
            int(row.rollout_id),
            int(row.rollout_seed),
        )
        for row in frame.itertuples(index=False)
    }
    expected = expected_keys(manifest)
    replay = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    strict = replay.le(float(manifest["replay_integrity_threshold"]))
    feedback_column = (
        "feedback_feedback_requery_performed"
        if "feedback_feedback_requery_performed" in frame
        else "feedback_requery_performed"
    )
    feedback_performed = _as_bool(frame[feedback_column])
    feedback_success = _as_bool(frame["feedback_terminal_success"])
    decision_key = ["case_id", "snapshot_id"]
    candidate_counts = candidates.groupby(decision_key).size()
    max_counts = (
        candidates.assign(_is_max=_as_bool(candidates["candidate_is_max_value"]))
        .groupby(decision_key)["_is_max"]
        .sum()
    )
    expected_cases = sorted(str(cell["case_id"]) for cell in manifest["cells"])
    checks: dict[str, object] = {
        "pairs": int(len(frame)),
        "target_pairs": int(manifest["target_pairs"]),
        "expected_keys_match": observed == expected,
        "missing_keys": len(expected - observed),
        "unexpected_keys": len(observed - expected),
        "duplicate_decision_keys": int(frame.duplicated(decision_key).sum()),
        "cases_match": sorted(frame["case_id"].astype(str).unique()) == expected_cases,
        "query_matches": sorted(frame["query_idx"].astype(int).unique())
        == [int(manifest["snapshot_query_idx"])],
        "split_matches": sorted(frame["experiment_split"].astype(str).unique())
        == [str(manifest["experiment_split"])],
        "terminal_labels_complete": bool(
            frame[["open_terminal_success", "feedback_terminal_success"]]
            .notna()
            .all()
            .all()
        ),
        "feedback_paths_valid": int((feedback_performed | feedback_success).sum()),
        "candidate_pool_size_valid": bool(
            len(candidate_counts) == len(frame)
            and candidate_counts.eq(int(manifest["num_candidates"])).all()
        ),
        "one_max_value_candidate_per_pool": bool(
            len(max_counts) == len(frame) and max_counts.eq(1).all()
        ),
        "strict_replay_pairs": int(strict.sum()),
        "minimum_strict_replay_pairs": int(manifest["minimum_strict_replay_pairs"]),
        "max_replay_state_abs_error": float(replay.max()),
    }
    checks["valid"] = bool(
        checks["pairs"] == checks["target_pairs"]
        and checks["expected_keys_match"]
        and checks["duplicate_decision_keys"] == 0
        and checks["cases_match"]
        and checks["query_matches"]
        and checks["split_matches"]
        and checks["terminal_labels_complete"]
        and checks["feedback_paths_valid"] == checks["target_pairs"]
        and checks["candidate_pool_size_valid"]
        and checks["one_max_value_candidate_per_pool"]
        and checks["strict_replay_pairs"] >= checks["minimum_strict_replay_pairs"]
    )
    return checks


def add_boundary_flags(summary: pd.DataFrame, manifest: dict[str, Any]) -> pd.DataFrame:
    result = summary.copy()
    result["pooled_successes"] = (
        result["open_success_rate"] * result["states"]
        + result["feedback_success_rate"] * result["states"]
    ).round().astype(int)
    result["pooled_failures"] = 2 * result["states"] - result["pooled_successes"]
    result["effect_support"] = (
        result["rescues"].ge(int(manifest["minimum_effect_direction_pairs"]))
        & result["harms"].ge(int(manifest["minimum_effect_direction_pairs"]))
    )
    result["non_ceiling_opportunity"] = (
        (result["rescues"] + result["harms"]).ge(
            int(manifest["minimum_discordant_pairs"])
        )
        & result["pooled_successes"].ge(int(manifest["minimum_pooled_successes"]))
        & result["pooled_failures"].ge(int(manifest["minimum_pooled_failures"]))
    )
    result["eligible_for_new_seed_holdout"] = (
        result["effect_support"] | result["non_ceiling_opportunity"]
    )
    return result


def failure_transitions(frame: pd.DataFrame) -> pd.DataFrame:
    discordant = frame.loc[frame["terminal_effect"].ne(0)]
    if discordant.empty:
        return pd.DataFrame()
    return (
        discordant.groupby(
            [
                "case_id",
                "terminal_outcome",
                "open_terminal_failure_type",
                "feedback_terminal_failure_type",
            ],
            dropna=False,
        )
        .size()
        .rename("pairs")
        .reset_index()
        .sort_values(["case_id", "pairs"], ascending=[True, False])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "cross_factor_boundary")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.freeze_manifest.expanduser().read_text(encoding="utf-8"))
    feedback, candidates = load_campaign(campaign_dir)
    if feedback.empty or candidates.empty:
        raise FileNotFoundError("Cross-factor feedback/candidate artifacts are missing")

    frame = attach_cell_metadata(prepare_terminal_frame(feedback), manifest)
    integrity = validate_integrity(frame, candidates, manifest)
    strict = frame.loc[frame["strict_integrity"]].copy()
    overall = summarize_terminal_effect(strict, ())
    cells = add_boundary_flags(
        summarize_terminal_effect(strict, ("case_id", "factor", "perturbation")),
        manifest,
    )
    transitions = failure_transitions(strict)

    frame.to_parquet(output_dir / "paired_outcomes.parquet", index=False)
    frame.to_csv(output_dir / "paired_outcomes.csv", index=False)
    overall.to_csv(output_dir / "overall_descriptive.csv", index=False)
    cells.to_csv(output_dir / "cell_summary.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    eligible = cells.loc[cells["eligible_for_new_seed_holdout"], "case_id"].tolist()
    summary = {
        "integrity": integrity,
        "development_only": True,
        "eligible_cells": eligible,
        "effect_support_cells": cells.loc[cells["effect_support"], "case_id"].tolist(),
        "non_ceiling_opportunity_cells": cells.loc[
            cells["non_ceiling_opportunity"], "case_id"
        ].tolist(),
        "overall_descriptive": overall.iloc[0].to_dict(),
        "report": str(output_dir / "RESULTS.md"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=lambda value: value.item()),
        encoding="utf-8",
    )
    lines = [
        "# Object query-4 cross-factor boundary screen",
        "",
        "This is a development screen, not a confirmatory transfer result.",
        "",
        f"- Integrity: **{'PASS' if integrity['valid'] else 'FAIL'}**.",
        f"- Eligible cells: {', '.join(eligible) if eligible else 'none'}.",
        "",
        "## Cell summary",
        "",
        cells.to_markdown(index=False),
        "",
        "## Overall descriptive summary",
        "",
        overall.to_markdown(index=False),
        "",
        "## Failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=lambda value: value.item()))


if __name__ == "__main__":
    main()

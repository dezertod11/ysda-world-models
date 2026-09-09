#!/usr/bin/env python3
"""Evaluate the frozen Object task-0 query-4 requery holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import load_campaign
    from counterfactual_feedback_utils import deterministic_unit_interval
    from analyze_terminal_event_atlas import (
        _budget_row,
        event_transition_summary,
        prepare_terminal_frame,
        summarize_terminal_effect,
    )
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import load_campaign
    from scripts.counterfactual_feedback_utils import deterministic_unit_interval
    from scripts.analyze_terminal_event_atlas import (
        _budget_row,
        event_transition_summary,
        prepare_terminal_frame,
        summarize_terminal_effect,
    )


def validate_holdout(frame: pd.DataFrame, manifest: dict[str, object]) -> dict[str, object]:
    development = {int(value) for value in manifest["development_init_states"]}
    expected = {int(value) for value in manifest["holdout_init_states"]}
    observed = {int(value) for value in frame["init_state_id"].unique()}
    suites = sorted(frame["suite"].astype(str).unique().tolist())
    tasks = sorted(frame["task_id"].astype(int).unique().tolist())
    queries = sorted(frame["query_idx"].astype(int).unique().tolist())
    duplicate_states = int(frame["analysis_state_key"].duplicated().sum())
    checks = {
        "suite_matches": suites == [str(manifest["suite"])],
        "task_matches": tasks == [int(value) for value in manifest["task_ids"]],
        "query_matches": queries
        == [int(value) for value in manifest["snapshot_query_indices"]],
        "development_overlap": sorted(observed & development),
        "unexpected_init_states": sorted(observed - expected),
        "missing_init_states": sorted(expected - observed),
        "duplicate_analysis_states": duplicate_states,
        "observed_pairs": int(len(frame)),
        "target_pairs": int(manifest["target_pairs"]),
    }
    checks["valid"] = bool(
        checks["suite_matches"]
        and checks["task_matches"]
        and checks["query_matches"]
        and not checks["development_overlap"]
        and not checks["unexpected_init_states"]
        and not checks["missing_init_states"]
        and duplicate_states == 0
        and len(frame) == int(manifest["target_pairs"])
    )
    return checks


def frozen_ranker_budgets(
    frame: pd.DataFrame, manifest: dict[str, object]
) -> pd.DataFrame:
    scores: dict[str, np.ndarray] = {}
    for specification in manifest["secondary_rankers"]:
        feature = str(specification["feature"])
        direction = str(specification["direction"])
        if feature not in frame:
            continue
        values = pd.to_numeric(frame[feature], errors="coerce").to_numpy(dtype=float)
        if direction == "low":
            values = -values
        elif direction != "high":
            raise ValueError(f"Unsupported frozen direction: {direction}")
        scores[f"frozen_{direction}_{feature}"] = values

    scores["deterministic_random"] = np.asarray(
        [
            deterministic_unit_interval("object-q4-holdout-random", key)
            for key in frame["analysis_state_key"]
        ],
        dtype=float,
    )
    scores["oracle_reference"] = frame["terminal_effect"].to_numpy(dtype=float)
    rows = []
    for method, values in scores.items():
        for budget in manifest["secondary_budgets"]:
            row = _budget_row(frame, values, method=method, budget=float(budget))
            if row is not None:
                rows.append(row)
    return pd.DataFrame(rows)


def gate_results(
    overall: pd.DataFrame, integrity: dict[str, object], manifest: dict[str, object]
) -> dict[str, object]:
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
    frame: pd.DataFrame,
    overall: pd.DataFrame,
    strict: pd.DataFrame,
    init_summary: pd.DataFrame,
    frozen_budgets: pd.DataFrame,
    transitions: pd.DataFrame,
    integrity: dict[str, object],
    gates: dict[str, object],
    output_dir: Path,
) -> None:
    frozen_only = frozen_budgets.loc[
        ~frozen_budgets["method"].isin(["deterministic_random", "oracle_reference"])
    ]
    lines = [
        "# Frozen Object query-4 requery holdout",
        "",
        f"- Exact-state pairs: **{len(frame)}**.",
        f"- Independent init states: **{frame['init_state_id'].nunique()}**.",
        f"- Rescue / harm: **{int(frame['rescue'].sum())} / {int(frame['harm'].sum())}**.",
        f"- Integrity gate: **{'PASS' if gates['integrity_pass'] else 'FAIL'}**.",
        f"- Practical gate: **{'PASS' if gates['practical_gate_pass'] else 'FAIL'}**.",
        f"- Confirmatory gate: **{'PASS' if gates['confirmatory_gate_pass'] else 'FAIL'}**.",
        "",
        "## Primary paired endpoint",
        "",
        overall.to_markdown(index=False),
        "",
        "## Strict replay-integrity sensitivity",
        "",
        strict.to_markdown(index=False),
        "",
        "## Integrity checks",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
        "",
        "## Frozen secondary rankers",
        "",
        frozen_only.to_markdown(index=False),
        "",
        "## Init-state breakdown",
        "",
        init_summary.to_markdown(index=False),
        "",
        "## Discordant failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
        "",
        "## Decision rule",
        "",
        "The query-4 intervention is accepted only when the frozen practical gate passes.",
        "The stronger confirmatory claim additionally requires positive lower CI and `p<0.05`.",
        "Secondary rankers retain their development-frozen directions regardless of holdout outcomes.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "object_q4_holdout")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.freeze_manifest.expanduser().read_text(encoding="utf-8"))
    feedback, _candidates = load_campaign(campaign_dir)
    if feedback.empty:
        raise FileNotFoundError(f"No feedback pairs under {campaign_dir / 'runs'}")

    frame = prepare_terminal_frame(feedback)
    integrity = validate_holdout(frame, manifest)
    overall = summarize_terminal_effect(frame, ())
    strict = summarize_terminal_effect(frame.loc[frame["strict_integrity"]], ())
    init_summary = summarize_terminal_effect(frame, ("init_state_id",))
    frozen_budgets = frozen_ranker_budgets(frame, manifest)
    transitions = event_transition_summary(frame)
    gates = gate_results(overall, integrity, manifest)

    frame.to_parquet(output_dir / "holdout_pairs.parquet", index=False)
    overall.to_csv(output_dir / "primary_endpoint.csv", index=False)
    strict.to_csv(output_dir / "strict_primary_endpoint.csv", index=False)
    init_summary.to_csv(output_dir / "init_state_summary.csv", index=False)
    frozen_budgets.to_csv(output_dir / "frozen_ranker_budgets.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    write_report(
        frame,
        overall,
        strict,
        init_summary,
        frozen_budgets,
        transitions,
        integrity,
        gates,
        output_dir,
    )

    row = overall.iloc[0]
    summary = {
        "states": int(len(frame)),
        "rescues": int(frame["rescue"].sum()),
        "harms": int(frame["harm"].sum()),
        "raw_success_delta": float(row["success_delta"]),
        "adjusted_terminal_delta": float(row["always_requery_adjusted_delta"]),
        "success_delta_ci_low": float(row["success_delta_ci_low"]),
        "success_delta_ci_high": float(row["success_delta_ci_high"]),
        "mcnemar_pvalue": float(row["discordance_pvalue"]),
        **gates,
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

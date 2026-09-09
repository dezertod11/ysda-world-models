#!/usr/bin/env python3
"""Analyze the frozen Object query-4 Position direction holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import load_campaign
    from analyze_object_q4_cross_factor_boundary_screen import validate_integrity
    from analyze_terminal_event_atlas import prepare_terminal_frame, summarize_terminal_effect
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import load_campaign
    from scripts.analyze_object_q4_cross_factor_boundary_screen import validate_integrity
    from scripts.analyze_terminal_event_atlas import (
        prepare_terminal_frame,
        summarize_terminal_effect,
    )


def attach_holdout_metadata(
    frame: pd.DataFrame, manifest: dict[str, Any]
) -> pd.DataFrame:
    metadata = pd.DataFrame(
        [
            {
                "case_id": str(cell["case_id"]),
                "condition_id": str(cell["condition_id"]),
                "factor": str(cell["factor"]),
                "perturbation": str(cell["position_level"]),
                "shard": str(cell["shard"]),
            }
            for cell in manifest["cells"]
        ]
    )
    result = frame.drop(
        columns=["condition_id", "factor", "perturbation", "shard"],
        errors="ignore",
    ).merge(metadata, on="case_id", how="left", validate="many_to_one")
    result["independent_group"] = (
        result["condition_id"].astype(str)
        + "|init"
        + result["init_state_id"].astype(int).astype(str)
    )
    return result


def add_condition_integrity(
    integrity: dict[str, object],
    frame: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, object]:
    strict_counts = (
        frame.loc[frame["strict_integrity"]]
        .groupby("condition_id")
        .size()
        .astype(int)
        .to_dict()
    )
    expected_conditions = sorted(str(value) for value in manifest["conditions"])
    minimum = int(manifest["minimum_strict_pairs_per_condition"])
    condition_valid = all(strict_counts.get(condition, 0) >= minimum for condition in expected_conditions)
    result = dict(integrity)
    result["strict_pairs_by_condition"] = strict_counts
    result["minimum_strict_pairs_per_condition"] = minimum
    result["condition_strict_valid"] = condition_valid
    result["valid"] = bool(result["valid"] and condition_valid)
    return result


def interaction_bootstrap(
    frame: pd.DataFrame,
    *,
    primary_condition: str,
    control_condition: str,
    repetitions: int,
    seed: int,
) -> dict[str, float | int]:
    def by_init(condition: str) -> pd.DataFrame:
        return (
            frame.loc[frame["condition_id"].eq(condition)]
            .groupby("init_state_id")["terminal_effect"]
            .agg(["sum", "size"])
            .rename(columns={"sum": f"{condition}_sum", "size": f"{condition}_size"})
        )

    paired = by_init(primary_condition).join(by_init(control_condition), how="inner")
    if paired.empty:
        return {
            "shared_init_clusters": 0,
            "primary_delta": float("nan"),
            "control_delta": float("nan"),
            "interaction_delta": float("nan"),
            "interaction_ci_low": float("nan"),
            "interaction_ci_high": float("nan"),
        }

    columns = [
        f"{primary_condition}_sum",
        f"{primary_condition}_size",
        f"{control_condition}_sum",
        f"{control_condition}_size",
    ]
    values = paired[columns].to_numpy(dtype=float)
    primary_delta = float(values[:, 0].sum() / values[:, 1].sum())
    control_delta = float(values[:, 2].sum() / values[:, 3].sum())
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(repetitions, len(values)))
    sampled = values[draws]
    primary_draws = sampled[:, :, 0].sum(axis=1) / sampled[:, :, 1].sum(axis=1)
    control_draws = sampled[:, :, 2].sum(axis=1) / sampled[:, :, 3].sum(axis=1)
    interaction_draws = primary_draws - control_draws
    low, high = np.quantile(interaction_draws, [0.025, 0.975])
    return {
        "shared_init_clusters": int(len(paired)),
        "primary_delta": primary_delta,
        "control_delta": control_delta,
        "interaction_delta": float(primary_delta - control_delta),
        "interaction_ci_low": float(low),
        "interaction_ci_high": float(high),
    }


def failure_transitions(frame: pd.DataFrame) -> pd.DataFrame:
    discordant = frame.loc[frame["terminal_effect"].ne(0)]
    if discordant.empty:
        return pd.DataFrame()
    return (
        discordant.groupby(
            [
                "condition_id",
                "terminal_outcome",
                "open_terminal_failure_type",
                "feedback_terminal_failure_type",
            ],
            dropna=False,
        )
        .size()
        .rename("pairs")
        .reset_index()
        .sort_values(["condition_id", "pairs"], ascending=[True, False])
    )


def evaluate_gates(
    conditions: pd.DataFrame,
    interaction: dict[str, float | int],
    integrity: dict[str, object],
    manifest: dict[str, Any],
) -> dict[str, object]:
    primary_id = str(manifest["primary_condition"])
    primary = conditions.set_index("condition_id").loc[primary_id]
    alpha = float(manifest["alpha"])
    primary_checks = {
        "integrity": bool(integrity["valid"]),
        "cost_adjusted_delta_positive": bool(primary["always_requery_adjusted_delta"] > 0),
        "cluster_ci_lower_positive": bool(primary["success_delta_ci_low"] > 0),
        "mcnemar_p_below_alpha": bool(primary["discordance_pvalue"] < alpha),
    }
    primary_pass = all(primary_checks.values())
    interaction_checks = {
        "primary_gate_passed": primary_pass,
        "shared_init_clusters_sufficient": bool(
            interaction["shared_init_clusters"] >= int(manifest["minimum_shared_init_clusters"])
        ),
        "interaction_ci_lower_positive": bool(interaction["interaction_ci_low"] > 0),
    }
    interaction_pass = all(interaction_checks.values())
    if primary_pass and interaction_pass:
        decision = "confirm_y0p2_efficacy_and_direction_interaction"
    elif primary_pass:
        decision = "confirm_y0p2_efficacy_only"
    else:
        decision = "do_not_promote_fixed_cross_factor_feedback"
    return {
        "primary_checks": primary_checks,
        "primary_pass": primary_pass,
        "interaction_checks": interaction_checks,
        "interaction_pass": interaction_pass,
        "decision": decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir or (campaign_dir / "analysis" / "position_direction_holdout")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.freeze_manifest.expanduser().read_text(encoding="utf-8"))
    feedback, candidates = load_campaign(campaign_dir)
    if feedback.empty or candidates.empty:
        raise FileNotFoundError("Position direction holdout artifacts are missing")

    frame = attach_holdout_metadata(prepare_terminal_frame(feedback), manifest)
    integrity = add_condition_integrity(
        validate_integrity(frame, candidates, manifest), frame, manifest
    )
    strict = frame.loc[frame["strict_integrity"]].copy()
    conditions = summarize_terminal_effect(strict, ("condition_id", "factor", "perturbation"))
    full_sensitivity = summarize_terminal_effect(
        frame, ("condition_id", "factor", "perturbation")
    )
    interaction = interaction_bootstrap(
        strict,
        primary_condition=str(manifest["primary_condition"]),
        control_condition=str(manifest["control_condition"]),
        repetitions=int(manifest["bootstrap_repetitions"]),
        seed=int(manifest["bootstrap_seed"]),
    )
    gates = evaluate_gates(conditions, interaction, integrity, manifest)
    transitions = failure_transitions(strict)

    frame.to_parquet(output_dir / "paired_outcomes.parquet", index=False)
    frame.to_csv(output_dir / "paired_outcomes.csv", index=False)
    conditions.to_csv(output_dir / "condition_summary.csv", index=False)
    full_sensitivity.to_csv(output_dir / "full_sensitivity.csv", index=False)
    transitions.to_csv(output_dir / "failure_transitions.csv", index=False)
    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    (output_dir / "interaction.json").write_text(
        json.dumps(interaction, indent=2), encoding="utf-8"
    )
    summary = {
        "integrity": integrity,
        "development_rows_used": 0,
        "primary_condition": manifest["primary_condition"],
        "control_condition": manifest["control_condition"],
        "interaction": interaction,
        "gates": gates,
        "report": str(output_dir / "RESULTS.md"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines = [
        "# Object query-4 Position direction holdout",
        "",
        f"- Integrity: **{'PASS' if integrity['valid'] else 'FAIL'}**.",
        f"- Primary efficacy: **{'PASS' if gates['primary_pass'] else 'FAIL'}**.",
        f"- Direction interaction: **{'PASS' if gates['interaction_pass'] else 'FAIL'}**.",
        f"- Decision: `{gates['decision']}`.",
        "",
        "## Strict condition results",
        "",
        conditions.to_markdown(index=False),
        "",
        "## All-pair sensitivity",
        "",
        full_sensitivity.to_markdown(index=False),
        "",
        "## Interaction",
        "",
        "```json",
        json.dumps(interaction, indent=2),
        "```",
        "",
        "## Failure transitions",
        "",
        transitions.to_markdown(index=False) if len(transitions) else "No discordant pairs.",
        "",
        "## Frozen gates",
        "",
        "```json",
        json.dumps(gates, indent=2),
        "```",
        "",
        "## Integrity",
        "",
        "```json",
        json.dumps(integrity, indent=2),
        "```",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evaluate a frozen P3e recovery router on exact-state branch outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from analyze_online_regrasp_transfer import (
        DIAGNOSTICS,
        _bootstrap_mean,
        _fallback_integrity,
        _load,
        _mcnemar_exact,
        _pair_method,
    )
    from recovery_outcome_router import (
        ROUTER_FEATURES,
        ROUTER_STRATEGIES,
        load_recovery_router,
        route_recovery,
    )
except ModuleNotFoundError:
    from scripts.analyze_online_regrasp_transfer import (
        DIAGNOSTICS,
        _bootstrap_mean,
        _fallback_integrity,
        _load,
        _mcnemar_exact,
        _pair_method,
    )
    from scripts.recovery_outcome_router import (
        ROUTER_FEATURES,
        ROUTER_STRATEGIES,
        load_recovery_router,
        route_recovery,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _feature_integrity(frame: pd.DataFrame) -> bool:
    for _case_id, group in frame.groupby("case_id"):
        if len(group) != len(ROUTER_STRATEGIES):
            return False
        interventions = group.loc[group["strategy"] != "baseline_h8"]
        for feature in ROUTER_FEATURES:
            values = pd.to_numeric(interventions[feature], errors="coerce").to_numpy()
            if not np.isfinite(values).all() or float(np.ptp(values)) > 1e-12:
                return False
            if feature.startswith("trigger_localization_"):
                baseline = pd.to_numeric(
                    group.loc[group["strategy"] == "baseline_h8", feature],
                    errors="coerce",
                ).to_numpy()
                if (
                    not np.isfinite(baseline).all()
                    or float(np.max(np.abs(baseline - values[0]))) > 1e-12
                ):
                    return False
    return True


def _routed_rows(frame: pd.DataFrame, artifact: dict) -> pd.DataFrame:
    indexed = frame.set_index(["case_id", "strategy"], drop=False)
    rows = []
    for case_id, group in frame.groupby("case_id", sort=True):
        trigger_row = group.loc[
            group["strategy"] == "workspace_calibrated"
        ].iloc[0]
        decision = route_recovery(trigger_row.to_dict(), artifact)
        selected = str(decision["router_selected_strategy"])
        source = indexed.loc[(case_id, selected)].to_dict()
        source["router_selected_strategy"] = selected
        source["router_trigger_override"] = bool(decision["router_trigger_override"])
        for strategy, value in decision["router_probabilities"].items():
            source[f"router_probability__{strategy}"] = float(value)
        for strategy, value in decision["router_scores"].items():
            source[f"router_score__{strategy}"] = float(value)
        rows.append(source)
    return pd.DataFrame(rows)


def _compare(
    reference: pd.DataFrame,
    routed: pd.DataFrame,
    *,
    reference_name: str,
    cohort: str,
    repetitions: int,
    seed: int,
) -> tuple[dict, pd.DataFrame]:
    subset_ids = (
        routed["case_id"]
        if cohort == "all"
        else routed.loc[routed["evaluation_cohort"] == cohort, "case_id"]
    )
    reference_subset = reference.loc[reference.index.intersection(subset_ids)]
    routed_subset = routed.set_index("case_id").loc[reference_subset.index]
    pair = pd.DataFrame(
        {
            "case_id": reference_subset.index,
            "evaluation_cohort": reference_subset["evaluation_cohort"].to_numpy(),
            "independent_group": reference_subset["independent_group"].to_numpy(),
            "position_level": reference_subset["position_level"].to_numpy(),
            "task_id": reference_subset["task_id"].to_numpy(dtype=int),
            "init_state_id": reference_subset["init_state_id"].to_numpy(dtype=int),
            "reference_success": reference_subset["terminal_success"].to_numpy(dtype=int),
            "router_success": routed_subset["terminal_success"].to_numpy(dtype=int),
            "reference_final_t": reference_subset["terminal_final_t"].to_numpy(dtype=int),
            "router_final_t": routed_subset["terminal_final_t"].to_numpy(dtype=int),
            "reference_primitive_steps": reference_subset["primitive_steps"].to_numpy(dtype=int),
            "router_primitive_steps": routed_subset["primitive_steps"].to_numpy(dtype=int),
            "router_selected_strategy": routed_subset["router_selected_strategy"].to_numpy(),
        }
    )
    for diagnostic in DIAGNOSTICS:
        short = diagnostic.removeprefix("terminal_")
        pair[f"reference_{short}"] = reference_subset[diagnostic].to_numpy(dtype=int)
        pair[f"router_{short}"] = routed_subset[diagnostic].to_numpy(dtype=int)
    pair["success_delta"] = pair["router_success"] - pair["reference_success"]
    pair["rescued"] = (pair["success_delta"] == 1).astype(int)
    pair["harmed"] = (pair["success_delta"] == -1).astype(int)
    group_ci = _bootstrap_mean(
        pair,
        cluster_columns=["independent_group"],
        repetitions=repetitions,
        seed=seed,
    )
    cell_ci = _bootstrap_mean(
        pair,
        cluster_columns=["position_level", "task_id"],
        repetitions=repetitions,
        seed=seed + 1,
    )
    rescues = int(pair["rescued"].sum())
    harms = int(pair["harmed"].sum())
    both_success = pair["reference_success"].eq(1) & pair["router_success"].eq(1)
    result = {
        "reference": reference_name,
        "cohort": cohort,
        "n_cases": len(pair),
        "reference_successes": int(pair["reference_success"].sum()),
        "router_successes": int(pair["router_success"].sum()),
        "reference_sr": float(pair["reference_success"].mean()),
        "router_sr": float(pair["router_success"].mean()),
        "paired_sr_delta": float(pair["success_delta"].mean()),
        "group_ci_low": group_ci[0],
        "group_ci_high": group_ci[1],
        "cell_ci_low": cell_ci[0],
        "cell_ci_high": cell_ci[1],
        "rescues": rescues,
        "harms": harms,
        "mcnemar_exact_p": _mcnemar_exact(rescues, harms),
        "mean_primitive_steps_delta": float(
            (pair["router_primitive_steps"] - pair["reference_primitive_steps"]).mean()
        ),
        "mean_final_t_delta": float(
            (pair["router_final_t"] - pair["reference_final_t"]).mean()
        ),
        "both_success_cases": int(both_success.sum()),
        "mean_time_delta_both_success": (
            float(
                (
                    pair.loc[both_success, "router_final_t"]
                    - pair.loc[both_success, "reference_final_t"]
                ).mean()
            )
            if both_success.any()
            else float("nan")
        ),
    }
    for diagnostic in DIAGNOSTICS:
        short = diagnostic.removeprefix("terminal_")
        result[f"{short}_delta"] = float(
            pair[f"router_{short}"].mean() - pair[f"reference_{short}"].mean()
        )
    return result, pair


def analyze(args: argparse.Namespace) -> dict:
    campaign_dir = args.campaign_dir.expanduser().resolve()
    artifact_path = args.router_artifact.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = load_recovery_router(artifact_path)
    frame = _load(campaign_dir)
    observed = set(frame["strategy"].astype(str))
    if observed != set(ROUTER_STRATEGIES):
        raise ValueError(f"Unexpected holdout strategies: {sorted(observed)}")
    counts = frame.groupby("case_id")["strategy"].nunique()
    complete = bool(
        len(frame) == args.expected_cases * len(ROUTER_STRATEGIES)
        and int((counts == len(ROUTER_STRATEGIES)).sum()) == args.expected_cases
    )
    exact_replay = bool(
        (frame["snapshot_replay_max_abs"] <= args.replay_threshold).all()
    )
    feature_integrity = _feature_integrity(frame)
    baseline = frame.loc[frame["strategy"] == "baseline_h8"].set_index("case_id")
    full = frame.loc[
        frame["strategy"] == "workspace_calibrated"
    ].set_index("case_id")
    retreat = frame.loc[
        frame["strategy"] == "workspace_retreat_only"
    ].set_index("case_id")
    fallback_integrity = bool(
        _fallback_integrity(_pair_method(baseline, full, "workspace_calibrated"))
        and _fallback_integrity(
            _pair_method(baseline, retreat, "workspace_retreat_only")
        )
    )
    routed = _routed_rows(frame, artifact)

    comparisons = []
    pair_tables = []
    references = {
        "full_regrasp": full,
        "baseline_h8": baseline,
        "retreat_only": retreat,
    }
    for reference_index, (reference_name, reference_frame) in enumerate(
        references.items()
    ):
        for cohort_index, cohort in enumerate(("all", "replication", "novel_cell")):
            summary, pair = _compare(
                reference_frame,
                routed,
                reference_name=reference_name,
                cohort=cohort,
                repetitions=args.bootstrap_repetitions,
                seed=args.seed + reference_index * 100 + cohort_index * 10,
            )
            comparisons.append(summary)
            pair["reference"] = reference_name
            pair["cohort"] = cohort
            pair_tables.append(pair)
    comparison_frame = pd.DataFrame(comparisons)
    primary = comparison_frame.loc[
        (comparison_frame["reference"] == "full_regrasp")
        & (comparison_frame["cohort"] == "all")
    ].iloc[0]
    versus_baseline = comparison_frame.loc[
        (comparison_frame["reference"] == "baseline_h8")
        & (comparison_frame["cohort"] == "all")
    ].iloc[0]
    gate = bool(
        complete
        and exact_replay
        and feature_integrity
        and fallback_integrity
        and int(primary["rescues"]) >= args.min_rescues
        and int(primary["rescues"]) > int(primary["harms"])
        and float(primary["paired_sr_delta"]) > 0
        and float(primary["group_ci_low"]) >= 0
        and float(primary["mean_primitive_steps_delta"]) <= 0
        and float(primary["target_drop_candidate_delta"]) <= 0
        and float(primary["wrong_object_interaction_candidate_delta"]) <= 0
        and float(primary["official_safety_violation_delta"]) <= 0
        and float(versus_baseline["paired_sr_delta"]) >= 0
    )

    routed.to_csv(output_dir / "routed_cases.csv", index=False)
    routed.to_parquet(output_dir / "routed_cases.parquet", index=False)
    comparison_frame.to_csv(output_dir / "comparison_summary.csv", index=False)
    pd.concat(pair_tables, ignore_index=True).to_csv(
        output_dir / "paired_comparisons.csv", index=False
    )
    cell_rows = []
    for (position, task_id), group in routed.groupby(["position_level", "task_id"]):
        cell_rows.append(
            {
                "position_level": position,
                "task_id": int(task_id),
                "evaluation_cohort": str(group["evaluation_cohort"].iloc[0]),
                "n_cases": len(group),
                "baseline_sr": float(group["case_id"].map(baseline["terminal_success"]).mean()),
                "full_sr": float(group["case_id"].map(full["terminal_success"]).mean()),
                "retreat_sr": float(group["case_id"].map(retreat["terminal_success"]).mean()),
                "router_sr": float(group["terminal_success"].mean()),
                "selected_baseline": int(
                    group["router_selected_strategy"].eq("baseline_h8").sum()
                ),
                "selected_retreat": int(
                    group["router_selected_strategy"].eq(
                        "workspace_retreat_only"
                    ).sum()
                ),
                "selected_full": int(
                    group["router_selected_strategy"].eq(
                        "workspace_calibrated"
                    ).sum()
                ),
            }
        )
    cell_frame = pd.DataFrame(cell_rows)
    cell_frame.to_csv(output_dir / "cell_summary.csv", index=False)

    strategies = list(ROUTER_STRATEGIES) + ["recovery_outcome_router"]
    success_rates = [
        float(frame.loc[frame["strategy"] == strategy, "terminal_success"].mean())
        for strategy in ROUTER_STRATEGIES
    ] + [float(routed["terminal_success"].mean())]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(np.arange(len(strategies)), success_rates)
    axes[0].set_xticks(np.arange(len(strategies)), strategies, rotation=25, ha="right")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Terminal success rate")
    selection = routed["router_selected_strategy"].value_counts()
    axes[1].bar(
        np.arange(len(ROUTER_STRATEGIES)),
        [int(selection.get(strategy, 0)) for strategy in ROUTER_STRATEGIES],
    )
    axes[1].set_xticks(
        np.arange(len(ROUTER_STRATEGIES)),
        ROUTER_STRATEGIES,
        rotation=25,
        ha="right",
    )
    axes[1].set_ylabel("Selected holdout cases")
    fig.tight_layout()
    fig.savefig(output_dir / "recovery_outcome_router_holdout.png", dpi=180)
    plt.close(fig)

    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "campaign_dir": str(campaign_dir),
        "router_artifact": str(artifact_path),
        "router_artifact_sha256": _sha256(artifact_path),
        "complete": complete,
        "exact_replay": exact_replay,
        "feature_integrity": feature_integrity,
        "fallback_integrity": fallback_integrity,
        "holdout_gate_pass": gate,
        "route_counts": {
            strategy: int(
                routed["router_selected_strategy"].eq(strategy).sum()
            )
            for strategy in ROUTER_STRATEGIES
        },
        "comparisons": comparison_frame.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    primary_line = (
        f"{int(primary['reference_successes'])}/{int(primary['n_cases'])} -> "
        f"{int(primary['router_successes'])}/{int(primary['n_cases'])}, "
        f"delta {100 * float(primary['paired_sr_delta']):+.1f} pp, "
        f"CI [{100 * float(primary['group_ci_low']):+.1f}, "
        f"{100 * float(primary['group_ci_high']):+.1f}] pp, "
        f"{int(primary['rescues'])}/{int(primary['harms'])} rescue/harm"
    )
    (output_dir / "RESULTS.md").write_text(
        "\n".join(
            [
                "# P3e frozen recovery outcome router holdout",
                "",
                f"- Complete: **{complete}**.",
                f"- Exact replay / feature / fallback integrity: "
                f"**{exact_replay}/{feature_integrity}/{fallback_integrity}**.",
                f"- Primary router vs full regrasp: **{primary_line}**.",
                f"- Frozen gate: **{'PASS' if gate else 'NO-GO'}**.",
                "",
                "Full comparison table: comparison_summary.csv.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)
    if args.require_gate and not gate:
        raise SystemExit(2)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--campaign-dir", type=Path, required=True)
    result.add_argument("--router-artifact", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--expected-cases", type=int, default=75)
    result.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    result.add_argument("--seed", type=int, default=20260906)
    result.add_argument("--replay-threshold", type=float, default=1e-9)
    result.add_argument("--min-rescues", type=int, default=2)
    result.add_argument("--require-gate", action="store_true")
    return result


if __name__ == "__main__":
    analyze(parser().parse_args())

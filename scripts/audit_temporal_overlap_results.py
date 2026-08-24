#!/usr/bin/env python3
"""Audit outcomes, event labels, and seed-mode controls for overlap runs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from analyze_temporal_overlap_campaign import load_campaign_traces, parse_bool, prepare_traces


PAIR_METRICS = [
    "overlap_selected_rmse",
    "overlap_support_min",
    "overlap_set_chamfer",
    "overlap_energy_distance",
    "overlap_mmd2_median",
    "overlap_shift",
    "overlap_coupled_mean",
    "overlap_cosine_distance",
    "action_first_step_l2_std",
    "value_std",
]

KEY_H16_METRICS = [
    "overlap_selected_rmse",
    "overlap_selected_all_rmse",
    "overlap_gripper_mismatch",
    "overlap_cosine_distance",
    "overlap_support_min",
    "overlap_set_chamfer",
    "overlap_energy_distance",
    "overlap_mmd2_median",
    "action_first_step_l2_std",
    "value_std",
    "previous_prediction_error_future_proprio_l2",
]


def _joined(values: Iterable[object]) -> str:
    return ";".join(
        sorted(
            {
                str(value)
                for value in values
                if pd.notna(value) and str(value).lower() not in {"", "none", "nan"}
            }
        )
    )


def _target_heads(targets: object) -> list[str]:
    result = []
    for target in str(targets or "").split(","):
        tokens = [
            token
            for token in re.sub(r"_\d+$", "", target.strip().lower()).split("_")
            if token
        ]
        if tokens:
            result.append(tokens[-1])
    return sorted(set(result))


def episode_rows(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "experiment_split",
        "case_id",
        "temporal_overlap_seed_mode",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "task_description",
        "target_objects",
        "success",
        "critical_event_type",
        "critical_event_t",
        "failure_type",
        "final_t",
        "episode_goal_progress_max",
    ]
    available = [column for column in columns if column in frame]
    episodes = (
        frame.groupby("episode_uid", sort=False)[available]
        .first()
        .reset_index()
    )
    episodes["success"] = parse_bool(episodes["success"])
    episodes["critical_event_t"] = pd.to_numeric(
        episodes["critical_event_t"], errors="coerce"
    ).fillna(-1)
    episodes["collector_event"] = episodes["critical_event_t"].ge(0)
    episodes["collector_event_on_success"] = (
        episodes["collector_event"] & episodes["success"]
    )

    event_rows = frame.loc[
        frame["critical_event_t"].ge(0)
        & frame["t"].le(frame["critical_event_t"])
        & frame["t_after"].ge(frame["critical_event_t"])
    ].copy()
    event_columns = {
        "observed_goal_progress_end": "event_chunk_goal_progress_end",
        "observed_target_lift_max": "event_chunk_target_lift_max",
        "observed_target_drop_candidate": "event_chunk_drop_candidate",
        "observed_wrong_object_interaction_candidate": "event_chunk_wrong_object_candidate",
    }
    available_events = [column for column in event_columns if column in event_rows]
    if available_events:
        event_context = (
            event_rows.sort_values(["episode_uid", "t"])
            .groupby("episode_uid", sort=False)[available_events]
            .first()
            .rename(columns=event_columns)
            .reset_index()
        )
        episodes = episodes.merge(event_context, on="episode_uid", how="left")
    return episodes


def case_audit_table(episodes: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "experiment_split",
        "temporal_overlap_seed_mode",
        "case_id",
        "suite",
        "task_id",
        "init_state_id",
        "task_description",
        "target_objects",
    ]
    grouped = episodes.groupby(keys, dropna=False, sort=False)
    table = grouped.agg(
        episodes=("episode_uid", "size"),
        successes=("success", "sum"),
        collector_event_episodes=("collector_event", "sum"),
        collector_events_on_success=("collector_event_on_success", "sum"),
        event_types=("critical_event_type", _joined),
        event_t_min=(
            "critical_event_t",
            lambda values: min((int(value) for value in values if value >= 0), default=-1),
        ),
        event_t_max=("critical_event_t", "max"),
        event_t_unique=(
            "critical_event_t",
            lambda values: len({int(value) for value in values if value >= 0}),
        ),
        goal_progress_max_mean=("episode_goal_progress_max", "mean"),
    ).reset_index()
    table["failures"] = table["episodes"] - table["successes"]
    table["success_rate"] = table["successes"] / table["episodes"]
    table["collector_event_rate"] = (
        table["collector_event_episodes"] / table["episodes"]
    )
    table["mixed_outcome"] = table["successes"].between(
        1, table["episodes"] - 1
    )
    table["single_outcome"] = ~table["mixed_outcome"]
    table["target_head_tokens"] = table["target_objects"].map(
        lambda value: ",".join(_target_heads(value))
    )
    table["target_head_missing_from_description"] = table.apply(
        lambda row: any(
            re.search(rf"\b{re.escape(token)}\b", str(row["task_description"]).lower())
            is None
            for token in _target_heads(row["target_objects"])
        ),
        axis=1,
    )
    table["audit_flags"] = table.apply(_audit_flags, axis=1)
    return table


def _audit_flags(row: pd.Series) -> str:
    flags = []
    if bool(row["single_outcome"]):
        flags.append("single_outcome_case")
    if int(row["collector_events_on_success"]) > 0:
        flags.append("event_on_success")
    if (
        int(row["collector_event_episodes"]) == int(row["episodes"])
        and int(row["event_t_unique"]) == 1
    ):
        flags.append("fixed_time_event")
    if bool(row["target_head_missing_from_description"]):
        flags.append("instruction_goal_mismatch")
    return ";".join(flags)


def paired_seed_outcomes(episodes: pd.DataFrame) -> pd.DataFrame:
    paired = episodes.pivot_table(
        index=["case_id", "rollout_seed"],
        columns="temporal_overlap_seed_mode",
        values="success",
        aggfunc="first",
    )
    required = {"independent", "coupled"}
    if not required.issubset(paired.columns):
        return pd.DataFrame()
    paired = paired.dropna(subset=sorted(required)).reset_index()
    paired["independent"] = parse_bool(paired["independent"])
    paired["coupled"] = parse_bool(paired["coupled"])
    paired["outcome_pair"] = np.select(
        [
            paired["independent"] & paired["coupled"],
            paired["independent"] & ~paired["coupled"],
            ~paired["independent"] & paired["coupled"],
        ],
        ["both_success", "independent_only", "coupled_only"],
        default="both_fail",
    )
    return paired


def seed_mode_q1_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    metrics = [metric for metric in PAIR_METRICS if metric in frame]
    query_one = frame.loc[frame["query_idx"].eq(1)]
    paired = query_one.pivot_table(
        index=["case_id", "rollout_seed"],
        columns="temporal_overlap_seed_mode",
        values=metrics,
        aggfunc="first",
    )
    rows = []
    for metric in metrics:
        independent_key = (metric, "independent")
        coupled_key = (metric, "coupled")
        if independent_key not in paired or coupled_key not in paired:
            continue
        values = paired[[independent_key, coupled_key]].dropna()
        independent = pd.to_numeric(values[independent_key], errors="coerce")
        coupled = pd.to_numeric(values[coupled_key], errors="coerce")
        valid = independent.notna() & coupled.notna()
        independent = independent[valid]
        coupled = coupled[valid]
        independent_mean = float(independent.mean())
        coupled_mean = float(coupled.mean())
        rows.append(
            {
                "metric": metric,
                "paired_episodes": int(len(independent)),
                "independent_mean": independent_mean,
                "coupled_mean": coupled_mean,
                "coupled_over_independent": (
                    coupled_mean / independent_mean
                    if independent_mean != 0
                    else float("nan")
                ),
                "paired_correlation": float(independent.corr(coupled)),
            }
        )
    return pd.DataFrame(rows)


def key_h16_table(analysis_dir: Path) -> pd.DataFrame:
    path = analysis_dir / "temporal_overlap" / "query_detector_metrics.csv"
    if not path.is_file():
        return pd.DataFrame()
    detector = pd.read_csv(path)
    columns = [
        "seed_mode",
        "metric",
        "prevalence",
        "auprc",
        "auroc",
        "tpr",
        "fpr",
        "threshold",
        "positive_queries",
        "negative_queries",
    ]
    return (
        detector.loc[
            detector["horizon"].eq(16) & detector["metric"].isin(KEY_H16_METRICS),
            columns,
        ]
        .sort_values(["seed_mode", "auprc"], ascending=[True, False])
        .reset_index(drop=True)
    )


def write_report(
    output_dir: Path,
    episodes: pd.DataFrame,
    cases: pd.DataFrame,
    paired: pd.DataFrame,
    q1: pd.DataFrame,
    h16: pd.DataFrame,
    integrity: dict[str, object],
) -> Path:
    successes = int(episodes["success"].sum())
    events = int(episodes["collector_event"].sum())
    events_on_success = int(episodes["collector_event_on_success"].sum())
    mixed = int(cases["mixed_outcome"].sum())
    mismatches = cases.loc[cases["target_head_missing_from_description"]]
    lines = [
        "# Temporal overlap result audit",
        "",
        f"- Integrity: valid={integrity.get('valid', 'unknown')}; "
        f"traces={integrity.get('trace_files', 'unknown')}; "
        f"queries={integrity.get('queries', 'unknown')}; "
        f"checked overlaps={integrity.get('checked_overlaps', 'unknown')}.",
        f"- Episodes: {len(episodes)} ({successes} success, {len(episodes) - successes} fail).",
        f"- Collector-labeled events: {events}; events inside successful episodes: {events_on_success}.",
        f"- Mixed outcome case/mode cells: {mixed}/{len(cases)}.",
        f"- Instruction/goal head-token mismatches: {len(mismatches)} case/mode cells.",
        "",
        "The event columns are heuristic diagnostics, not validated physical-failure ground truth.",
        "`event_on_success`, `fixed_time_event`, and `instruction_goal_mismatch` flags must be resolved before early-warning claims.",
        "",
        "## Seed-mode control",
        "",
    ]
    if len(paired):
        counts = paired["outcome_pair"].value_counts()
        lines.extend(
            [
                f"Across {len(paired)} matched seeds: both success={int(counts.get('both_success', 0))}, "
                f"both fail={int(counts.get('both_fail', 0))}, independent-only success={int(counts.get('independent_only', 0))}, "
                f"coupled-only success={int(counts.get('coupled_only', 0))}.",
                "",
            ]
        )
    if len(q1):
        row = q1.loc[q1["metric"].eq("overlap_selected_rmse")]
        if len(row):
            selected = row.iloc[0]
            lines.extend(
                [
                    "At query 1, coupled noise did not reduce selected overlap RMSE: "
                    f"ratio={selected['coupled_over_independent']:.3f}, paired correlation={selected['paired_correlation']:.3f}.",
                    "",
                ]
            )
    lines.extend(["## H=16 numerical ranking", ""])
    for seed_mode in ["independent", "coupled"]:
        rows = h16.loc[h16["seed_mode"].eq(seed_mode)].head(3)
        if rows.empty:
            continue
        lines.append(f"### {seed_mode}")
        lines.append("")
        lines.append("| Metric | AUPRC | Prevalence | AUROC | TPR | FPR |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in rows.itertuples(index=False):
            lines.append(
                f"| `{row.metric}` | {row.auprc:.3f} | {row.prevalence:.3f} | "
                f"{row.auroc:.3f} | {row.tpr:.3f} | {row.fpr:.3f} |"
            )
        lines.append("")
    lines.extend(
        [
            "These numbers describe the current collector labels only. The research interpretation is frozen separately in `experiments/TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`.",
            "",
            "## Files",
            "",
            "- `episode_outcomes.csv`",
            "- `case_event_audit.csv`",
            "- `paired_seed_mode_outcomes.csv`",
            "- `seed_mode_q1_metric_comparison.csv`",
            "- `key_query_metrics_h16.csv`",
            "- `summary.json`",
        ]
    )
    path = output_dir / "README.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def audit(campaign_dir: Path, output_dir: Path) -> dict[str, Path]:
    frame, _ = load_campaign_traces(campaign_dir)
    frame = prepare_traces(frame)
    episodes = episode_rows(frame)
    cases = case_audit_table(episodes)
    paired = paired_seed_outcomes(episodes)
    q1 = seed_mode_q1_comparison(frame)
    h16 = key_h16_table(campaign_dir / "analysis")
    integrity_path = campaign_dir / "analysis" / "temporal_overlap" / "integrity_summary.json"
    integrity = (
        json.loads(integrity_path.read_text(encoding="utf-8"))
        if integrity_path.is_file()
        else {}
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "episode_outcomes": output_dir / "episode_outcomes.csv",
        "case_event_audit": output_dir / "case_event_audit.csv",
        "paired_seed_mode_outcomes": output_dir / "paired_seed_mode_outcomes.csv",
        "seed_mode_q1_metric_comparison": output_dir / "seed_mode_q1_metric_comparison.csv",
        "key_query_metrics_h16": output_dir / "key_query_metrics_h16.csv",
    }
    episodes.to_csv(paths["episode_outcomes"], index=False)
    cases.to_csv(paths["case_event_audit"], index=False)
    paired.to_csv(paths["paired_seed_mode_outcomes"], index=False)
    q1.to_csv(paths["seed_mode_q1_metric_comparison"], index=False)
    h16.to_csv(paths["key_query_metrics_h16"], index=False)

    summary = {
        "episodes": int(len(episodes)),
        "successes": int(episodes["success"].sum()),
        "failures": int((~episodes["success"]).sum()),
        "collector_event_episodes": int(episodes["collector_event"].sum()),
        "collector_events_on_success": int(
            episodes["collector_event_on_success"].sum()
        ),
        "case_mode_cells": int(len(cases)),
        "mixed_outcome_case_mode_cells": int(cases["mixed_outcome"].sum()),
        "instruction_goal_mismatch_case_mode_cells": int(
            cases["target_head_missing_from_description"].sum()
        ),
        "matched_seed_mode_pairs": int(len(paired)),
        "paired_outcomes": paired["outcome_pair"].value_counts().to_dict()
        if len(paired)
        else {},
        "integrity": {
            key: integrity.get(key)
            for key in [
                "trace_files",
                "episodes",
                "queries",
                "checked_overlaps",
                "seed_modes",
                "valid",
            ]
        },
    }
    paths["summary"] = output_dir / "summary.json"
    paths["summary"].write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["report"] = write_report(
        output_dir, episodes, cases, paired, q1, h16, integrity
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "result_audit"
    for name, path in audit(args.campaign_dir, output_dir).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()

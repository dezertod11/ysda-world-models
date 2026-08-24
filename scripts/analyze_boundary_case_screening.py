#!/usr/bin/env python3
"""Rank same-task/init success/fail boundary cases from a LIBERO campaign."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CASE_KEYS = ["suite", "task_id", "init_state_id"]
EPISODE_KEYS = [
    "source_trace",
    "suite",
    "task_id",
    "init_state_id",
    "pair_id",
    "rollout_id",
    "rollout_seed",
]
BOOL_COLUMNS = [
    "success",
    "task_instruction_differs_from_benchmark",
    "target_drop_candidate",
    "wrong_object_interaction_candidate",
    "official_safety_violation",
    "kinematic_deadlock_candidate",
    "successful_target_release",
]


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return float("nan"), float("nan")
    rate = successes / total
    denominator = 1.0 + z * z / total
    center = (rate + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def load_campaign_traces(campaign_dir: Path) -> tuple[pd.DataFrame, list[Path]]:
    paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not paths:
        raise FileNotFoundError(f"No query trace parquet files under {campaign_dir / 'runs'}")
    frames = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False), paths


def episode_table(traces: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(EPISODE_KEYS + ["success"]) - set(traces.columns))
    if missing:
        raise ValueError(f"Trace files lack required columns: {missing}")

    frame = traces.copy()
    for column in BOOL_COLUMNS:
        if column not in frame:
            frame[column] = False
        frame[column] = parse_bool(frame[column])
    frame = frame.sort_values(EPISODE_KEYS + ["query_idx"])
    episodes = frame.groupby(EPISODE_KEYS, dropna=False, sort=False).first().reset_index()

    event_columns = [
        "target_drop_candidate",
        "wrong_object_interaction_candidate",
        "official_safety_violation",
    ]
    episodes["physical_or_safety_event"] = episodes[event_columns].any(axis=1)
    episodes["failure_without_physical_event"] = ~episodes["success"] & ~episodes[
        "physical_or_safety_event"
    ]
    return episodes


def _first_text(group: pd.DataFrame, column: str) -> str:
    if column not in group:
        return ""
    values = group[column].dropna().astype(str)
    return values.iloc[0] if len(values) else ""


def summarize_cases(episodes: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, group in episodes.groupby(CASE_KEYS, dropna=False, sort=True):
        successes = int(group["success"].sum())
        total = int(len(group))
        failures = total - successes
        rate = successes / total
        ci_low, ci_high = wilson_interval(successes, total)
        minority = min(successes, failures)
        if minority >= 2:
            status = "confirmed_mixed"
        elif minority == 1:
            status = "provisional_mixed"
        elif successes == total:
            status = "all_success"
        else:
            status = "all_fail"
        rows.append(
            {
                **dict(zip(CASE_KEYS, keys)),
                "task_description": _first_text(group, "task_description"),
                "benchmark_task_description": _first_text(
                    group, "benchmark_task_description"
                ),
                "task_instruction_source": _first_text(
                    group, "task_instruction_source"
                ),
                "instruction_shift": bool(
                    group["task_instruction_differs_from_benchmark"].any()
                ),
                "num_rollouts": total,
                "num_success": successes,
                "num_failed": failures,
                "success_rate": rate,
                "success_rate_ci95_low": ci_low,
                "success_rate_ci95_high": ci_high,
                "minority_outcome_count": minority,
                "boundary_balance": 4.0 * rate * (1.0 - rate),
                "screen_status": status,
                "target_drop_failures": int(
                    (~group["success"] & group["target_drop_candidate"]).sum()
                ),
                "wrong_object_failures": int(
                    (~group["success"] & group["wrong_object_interaction_candidate"]).sum()
                ),
                "official_safety_failures": int(
                    (~group["success"] & group["official_safety_violation"]).sum()
                ),
                "failures_without_physical_event": int(
                    group["failure_without_physical_event"].sum()
                ),
                "successful_release_episodes": int(
                    group["successful_target_release"].sum()
                ),
                "mean_final_t": float(
                    pd.to_numeric(group.get("final_t"), errors="coerce").mean()
                ),
            }
        )

    summary = pd.DataFrame(rows)
    status_rank = {
        "confirmed_mixed": 0,
        "provisional_mixed": 1,
        "all_fail": 2,
        "all_success": 3,
    }
    summary["status_rank"] = summary["screen_status"].map(status_rank)
    summary = summary.sort_values(
        ["status_rank", "minority_outcome_count", "boundary_balance", "num_rollouts"],
        ascending=[True, False, False, False],
    ).drop(columns="status_rank")
    summary.insert(0, "rank", np.arange(1, len(summary) + 1))
    return summary.reset_index(drop=True)


def plot_cases(summary: pd.DataFrame, output_path: Path) -> None:
    ordered = summary.sort_values(["success_rate", "suite", "task_id"])
    labels = [
        f"{suite}/t{int(task_id)}"
        for suite, task_id in zip(ordered["suite"], ordered["task_id"])
    ]
    rates = ordered["success_rate"].to_numpy(dtype=float)
    lower = np.maximum(
        rates - ordered["success_rate_ci95_low"].to_numpy(dtype=float), 0.0
    )
    upper = np.maximum(
        ordered["success_rate_ci95_high"].to_numpy(dtype=float) - rates, 0.0
    )
    colors = [
        "#D1495B" if status == "all_fail" else
        "#2A9D8F" if status == "all_success" else
        "#E9C46A"
        for status in ordered["screen_status"]
    ]
    height = max(7.0, 0.25 * len(ordered))
    fig, axis = plt.subplots(figsize=(12, height))
    positions = np.arange(len(ordered))
    axis.barh(positions, rates, color=colors, alpha=0.9)
    axis.errorbar(rates, positions, xerr=np.vstack([lower, upper]), fmt="none", ecolor="#202020", capsize=2)
    axis.axvspan(0.2, 0.8, color="#457B9D", alpha=0.08, label="target 20-80% boundary")
    axis.set_yticks(positions, labels)
    axis.set_xlim(0.0, 1.0)
    axis.set_xlabel("Empirical success rate (Wilson 95% CI)")
    axis.set_title("LIBERO-PRO same-task/init boundary screening")
    axis.grid(axis="x", alpha=0.2)
    axis.legend(loc="lower right")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170)
    plt.close(fig)


def analyze(campaign_dir: Path, output_dir: Path) -> dict[str, object]:
    traces, paths = load_campaign_traces(campaign_dir)
    episodes = episode_table(traces)
    cases = summarize_cases(episodes)
    mixed = cases.loc[cases["minority_outcome_count"].gt(0)].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    episodes.to_csv(output_dir / "episode_outcomes.csv", index=False)
    cases.to_csv(output_dir / "boundary_case_summary.csv", index=False)
    mixed.to_csv(output_dir / "selected_mixed_cases.csv", index=False)
    plot_cases(cases, output_dir / "boundary_case_success_rates.png")

    result: dict[str, object] = {
        "campaign_dir": str(campaign_dir),
        "trace_files": len(paths),
        "num_cases": int(len(cases)),
        "num_rollouts": int(len(episodes)),
        "num_success": int(episodes["success"].sum()),
        "num_failed": int((~episodes["success"]).sum()),
        "confirmed_mixed_cases": int(cases["screen_status"].eq("confirmed_mixed").sum()),
        "provisional_mixed_cases": int(cases["screen_status"].eq("provisional_mixed").sum()),
        "instruction_shift_cases": int(cases["instruction_shift"].sum()),
        "target_drop_failures": int(cases["target_drop_failures"].sum()),
        "recommended_expansion_cases": mixed[CASE_KEYS + [
            "num_success",
            "num_failed",
            "success_rate",
            "screen_status",
        ]].to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )

    top_lines = [
        f"| {row.suite} | {int(row.task_id)} | {int(row.init_state_id)} | "
        f"{int(row.num_success)}/{int(row.num_rollouts)} | {row.screen_status} |"
        for row in mixed.itertuples(index=False)
    ]
    readme = "\n".join(
        [
            "# Ground-truth boundary screening",
            "",
            f"Analyzed {len(episodes)} rollouts in {len(cases)} same-task/init cases.",
            f"Found {result['confirmed_mixed_cases']} confirmed and "
            f"{result['provisional_mixed_cases']} provisional mixed cases.",
            "",
            "A `confirmed_mixed` case has at least two success and two failed rollouts; "
            "a `provisional_mixed` case has one minority outcome. Only mixed cases are "
            "eligible for the larger paired detector experiment.",
            "",
            "| Suite | Task | Init | Success | Status |",
            "|---|---:|---:|---:|---|",
            *(top_lines or ["| none | - | - | - | - |"]),
            "",
            "`boundary_case_summary.csv` contains every screened case and Wilson 95% "
            "intervals. `episode_outcomes.csv` retains seed-level outcomes and repaired "
            "simulator labels.",
            "",
        ]
    )
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.campaign_dir / "analysis" / "boundary_screening"
    result = analyze(args.campaign_dir, output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

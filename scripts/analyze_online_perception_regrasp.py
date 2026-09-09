#!/usr/bin/env python3
"""Analyze paired full-episode P3c online regrasp branches."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def _paired_bootstrap(
    paired: pd.DataFrame,
    *,
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    groups = paired["independent_group"].drop_duplicates().to_numpy()
    if not len(groups):
        return float("nan"), float("nan")
    by_group = {group: paired.loc[paired["independent_group"] == group] for group in groups}
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        sample = pd.concat([by_group[group] for group in sampled], ignore_index=True)
        estimates.append(float((sample["method_success"] - sample["baseline_success"]).mean()))
    return tuple(float(value) for value in np.quantile(estimates, [0.025, 0.975]))


def _load(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted(campaign_dir.rglob("*__online_branches.parquet"))
    if not paths:
        raise FileNotFoundError(f"No online branch tables under {campaign_dir}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame = frame.drop_duplicates(["case_id", "strategy"], keep="last")
    frame["terminal_success"] = _as_bool(frame["terminal_success"]).astype(int)
    for column in (
        "terminal_target_drop_candidate",
        "terminal_wrong_object_interaction_candidate",
        "terminal_official_safety_violation",
        "trigger_passed",
        "intervention_applied",
        "counterfactual_reused",
    ):
        if column in frame:
            frame[column] = _as_bool(frame[column]).astype(int)
    return frame


def analyze(args: argparse.Namespace) -> dict:
    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = _load(campaign_dir)
    expected = [item.strip() for item in args.expected_strategies.split(",") if item.strip()]
    observed = sorted(frame["strategy"].unique())
    counts = frame.groupby("case_id")["strategy"].nunique()
    complete_cases = int((counts == len(expected)).sum())
    exact_replay = bool((frame["snapshot_replay_max_abs"] <= args.replay_threshold).all())
    if set(observed) != set(expected):
        raise ValueError(f"Observed strategies {observed}, expected {expected}")

    baseline = frame.loc[frame["strategy"] == "baseline_h8"].set_index("case_id")
    summaries = []
    pair_tables = []
    for method in [item for item in expected if item != "baseline_h8"]:
        method_frame = frame.loc[frame["strategy"] == method].set_index("case_id")
        common = baseline.index.intersection(method_frame.index)
        pair = pd.DataFrame(
            {
                "case_id": common,
                "independent_group": baseline.loc[common, "independent_group"].to_numpy(),
                "position_level": baseline.loc[common, "position_level"].to_numpy(),
                "task_id": baseline.loc[common, "task_id"].to_numpy(),
                "baseline_success": baseline.loc[common, "terminal_success"].to_numpy(dtype=int),
                "method_success": method_frame.loc[common, "terminal_success"].to_numpy(dtype=int),
                "baseline_final_t": baseline.loc[common, "terminal_final_t"].to_numpy(dtype=int),
                "method_final_t": method_frame.loc[common, "terminal_final_t"].to_numpy(dtype=int),
                "trigger_passed": method_frame.loc[common, "trigger_passed"].to_numpy(dtype=int),
                "intervention_applied": method_frame.loc[common, "intervention_applied"].to_numpy(dtype=int),
            }
        )
        pair["method"] = method
        pair["rescued"] = ((pair["baseline_success"] == 0) & (pair["method_success"] == 1)).astype(int)
        pair["harmed"] = ((pair["baseline_success"] == 1) & (pair["method_success"] == 0)).astype(int)
        both_success = (pair["baseline_success"] == 1) & (pair["method_success"] == 1)
        pair_tables.append(pair)
        ci_low, ci_high = _paired_bootstrap(
            pair, repetitions=args.bootstrap_repetitions, seed=args.seed
        )

        def rate(column: str, strategy_frame: pd.DataFrame) -> float:
            return float(strategy_frame.loc[common, column].mean())

        summaries.append(
            {
                "method": method,
                "n_cases": len(pair),
                "n_groups": pair["independent_group"].nunique(),
                "baseline_successes": int(pair["baseline_success"].sum()),
                "method_successes": int(pair["method_success"].sum()),
                "baseline_sr": float(pair["baseline_success"].mean()),
                "method_sr": float(pair["method_success"].mean()),
                "paired_sr_delta": float(
                    (pair["method_success"] - pair["baseline_success"]).mean()
                ),
                "paired_sr_delta_ci_low": ci_low,
                "paired_sr_delta_ci_high": ci_high,
                "rescues": int(pair["rescued"].sum()),
                "harms": int(pair["harmed"].sum()),
                "triggered": int(pair["trigger_passed"].sum()),
                "interventions": int(pair["intervention_applied"].sum()),
                "trigger_rate": float(pair["trigger_passed"].mean()),
                "intervention_rate": float(pair["intervention_applied"].mean()),
                "mean_final_t_delta": float(
                    (pair["method_final_t"] - pair["baseline_final_t"]).mean()
                ),
                "both_success_cases": int(both_success.sum()),
                "mean_time_delta_both_success": float(
                    (pair.loc[both_success, "method_final_t"]
                    - pair.loc[both_success, "baseline_final_t"]).mean()
                )
                if both_success.any()
                else float("nan"),
                "drop_rate_delta": rate("terminal_target_drop_candidate", method_frame)
                - rate("terminal_target_drop_candidate", baseline),
                "wrong_rate_delta": rate(
                    "terminal_wrong_object_interaction_candidate", method_frame
                )
                - rate("terminal_wrong_object_interaction_candidate", baseline),
                "safety_rate_delta": rate(
                    "terminal_official_safety_violation", method_frame
                )
                - rate("terminal_official_safety_violation", baseline),
            }
        )

    summary_frame = pd.DataFrame(summaries).sort_values(
        [
            "paired_sr_delta",
            "harms",
            "wrong_rate_delta",
            "mean_time_delta_both_success",
            "interventions",
        ],
        ascending=[False, True, True, True, False],
        kind="stable",
    )
    recommended = str(summary_frame.iloc[0]["method"])
    best = summary_frame.iloc[0]
    complete = complete_cases == args.expected_cases and len(frame) == args.expected_cases * len(expected)
    gate = bool(
        complete
        and exact_replay
        and int(best["interventions"]) > 0
        and float(best["paired_sr_delta"]) >= 0.0
        and int(best["harms"]) <= args.max_harms
        and float(best["wrong_rate_delta"]) <= args.max_wrong_delta
        and float(best["safety_rate_delta"]) <= 0.0
    )
    if args.phase == "development":
        gate = bool(gate and int(best["rescues"]) > int(best["harms"]))

    frame.to_csv(output_dir / "online_branches.csv", index=False)
    frame.to_parquet(output_dir / "online_branches.parquet", index=False)
    summary_frame.to_csv(output_dir / "method_summary.csv", index=False)
    pd.concat(pair_tables, ignore_index=True).to_csv(output_dir / "paired_cases.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = np.arange(len(summary_frame))
    width = 0.34
    axes[0].bar(x - width / 2, summary_frame["baseline_sr"], width, label="baseline_h8")
    axes[0].bar(x + width / 2, summary_frame["method_sr"], width, label="method")
    axes[0].set_xticks(x, summary_frame["method"], rotation=20, ha="right")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Success rate")
    axes[0].legend()
    axes[1].bar(x - width, summary_frame["trigger_rate"], width, label="trigger")
    axes[1].bar(x, summary_frame["intervention_rate"], width, label="applied")
    axes[1].bar(x + width, summary_frame["paired_sr_delta"], width, label="SR delta")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xticks(x, summary_frame["method"], rotation=20, ha="right")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(output_dir / "online_regrasp_summary.png", dpi=180)
    plt.close(fig)

    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phase": args.phase,
        "campaign_dir": str(campaign_dir),
        "expected_cases": args.expected_cases,
        "complete_cases": complete_cases,
        "rows": len(frame),
        "exact_replay": exact_replay,
        "recommended_method": recommended,
        "gate_pass": gate,
        "methods": summary_frame.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown = [
        f"# P3c {args.phase} online regrasp results",
        "",
        f"- Complete cases: **{complete_cases}/{args.expected_cases}**.",
        f"- Exact snapshot replay: **{exact_replay}**.",
        f"- Recommended frozen method: **{recommended}**.",
        f"- Gate: **{'PASS' if gate else 'NO-GO'}**.",
        "",
        summary_frame.to_markdown(index=False),
        "",
        "The trigger uses RGB localization and robot proprioception only. Simulator object",
        "state is used solely for terminal evaluation labels and never for intervention selection.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    if args.require_gate and not gate:
        raise SystemExit(2)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--campaign-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--phase", choices=["screen", "development", "holdout"], required=True)
    result.add_argument("--expected-cases", type=int, required=True)
    result.add_argument(
        "--expected-strategies",
        default="baseline_h8,workspace_calibrated,global_conservative",
    )
    result.add_argument("--bootstrap-repetitions", type=int, default=5000)
    result.add_argument("--seed", type=int, default=20260904)
    result.add_argument("--replay-threshold", type=float, default=1e-9)
    result.add_argument("--max-harms", type=int, default=1)
    result.add_argument("--max-wrong-delta", type=float, default=0.05)
    result.add_argument("--require-gate", action="store_true")
    return result


if __name__ == "__main__":
    analyze(parser().parse_args())

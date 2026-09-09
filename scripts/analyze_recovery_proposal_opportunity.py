#!/usr/bin/env python3
"""Analyze the frozen P3 recovery-proposal opportunity campaign."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata

try:
    from recovery_proposal_utils import RECOVERY_PROPOSALS
except ModuleNotFoundError:
    from scripts.recovery_proposal_utils import RECOVERY_PROPOSALS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STATES = 80
BOOTSTRAP_REPETITIONS = 5000
QUERY_METRICS = (
    "candidate_value_mean",
    "candidate_value_std",
    "candidate_value_range",
    "candidate_action_internal_consistency_mean",
    "candidate_action_chunk_consistency_mean",
    "candidate_value_internal_consistency_mean",
    "candidate_future_proprio_internal_consistency_mean",
    "candidate_future_proprio_across_sample_std_mean",
    "candidate_action_consensus_first_mean",
    "candidate_action_consensus_chunk_mean",
    "planning_predicted_proprio_error",
)


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def clustered_mean_interval(
    frame: pd.DataFrame,
    values: Iterable[float],
    *,
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    work = pd.DataFrame(
        {
            "cluster": frame["independent_group"].astype(str).to_numpy(),
            "value": np.asarray(list(values), dtype=float),
        }
    )
    clusters = [part["value"].to_numpy(float) for _, part in work.groupby("cluster", sort=True)]
    if not clusters:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = np.empty(repetitions, dtype=float)
    for index in range(repetitions):
        selected = rng.integers(0, len(clusters), size=len(clusters))
        sample = np.concatenate([clusters[item] for item in selected])
        draws[index] = float(np.mean(sample))
    low, high = np.quantile(draws, [0.025, 0.975])
    return float(low), float(high)


def binary_auc(labels: Iterable[bool], scores: Iterable[float]) -> float:
    labels_array = np.asarray(list(labels), dtype=bool)
    scores_array = np.asarray(list(scores), dtype=float)
    finite = np.isfinite(scores_array)
    labels_array = labels_array[finite]
    scores_array = scores_array[finite]
    positive = int(labels_array.sum())
    negative = int((~labels_array).sum())
    if positive == 0 or negative == 0:
        return float("nan")
    ranks = rankdata(scores_array, method="average")
    rank_sum = float(ranks[labels_array].sum())
    return float((rank_sum - positive * (positive + 1) / 2) / (positive * negative))


def stratified_binary_auc(
    labels: Iterable[bool],
    scores: Iterable[float],
    strata: Iterable[str],
) -> tuple[float, int, int]:
    """Return AUC over positive/negative pairs drawn from the same stratum."""
    frame = pd.DataFrame(
        {
            "label": np.asarray(list(labels), dtype=bool),
            "score": np.asarray(list(scores), dtype=float),
            "stratum": np.asarray(list(strata), dtype=str),
        }
    )
    weighted_auc = 0.0
    comparable_pairs = 0
    comparable_strata = 0
    for _, part in frame.groupby("stratum", sort=True):
        finite = np.isfinite(part["score"].to_numpy(float))
        part = part.loc[finite]
        positive = int(part["label"].sum())
        negative = int((~part["label"]).sum())
        pairs = positive * negative
        if not pairs:
            continue
        auc = binary_auc(part["label"], part["score"])
        weighted_auc += auc * pairs
        comparable_pairs += pairs
        comparable_strata += 1
    if not comparable_pairs:
        return float("nan"), 0, 0
    return (
        float(weighted_auc / comparable_pairs),
        comparable_strata,
        comparable_pairs,
    )


def proposal_gate(summary: Mapping[str, Any]) -> tuple[bool, list[str]]:
    checks = {
        "complete_80_states": int(summary["n_states"]) == EXPECTED_STATES,
        "strict_replay_at_least_95pct": float(summary["strict_replay_rate"]) >= 0.95,
        "sr_at_least_10pct": float(summary["success_rate"]) >= 0.10,
        "bootstrap_lower_above_zero": float(summary["success_ci_low"]) > 0.0,
        "rescues_in_at_least_4_cells": int(summary["rescued_cells"]) >= 4,
        "rescues_in_at_least_3_tasks": int(summary["rescued_tasks"]) >= 3,
        "safety_delta_at_most_2p5pp": float(summary["safety_rate_delta"]) <= 0.025,
        "drop_delta_at_most_5pp": float(summary["drop_rate_delta"]) <= 0.05,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return not failed, failed


def load_outputs(campaign_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    branch_paths = sorted((campaign_dir / "runs").glob("*__recovery_branches.parquet"))
    query_paths = sorted((campaign_dir / "runs").glob("*__query_metrics.parquet"))
    if not branch_paths:
        raise FileNotFoundError(f"No recovery branch tables under {campaign_dir / 'runs'}")
    branches = pd.concat([pd.read_parquet(path) for path in branch_paths], ignore_index=True)
    queries = (
        pd.concat([pd.read_parquet(path) for path in query_paths], ignore_index=True)
        if query_paths
        else pd.DataFrame()
    )
    key = ["row_uid", "proposal"]
    if branches.duplicated(key).any():
        raise ValueError("Duplicate completed recovery branches")
    return branches, queries


def load_pre_intervention_queries(branches: pd.DataFrame) -> pd.DataFrame:
    """Load the common source query at t=64 for the selected recovery states."""
    identity = branches.drop_duplicates("row_uid").loc[
        :, ["row_uid", "source_run", "snapshot_id", "position_level", "task_id"]
    ]
    identity = identity.copy()
    identity["cell_key"] = (
        identity["position_level"].astype(str)
        + "|task"
        + identity["task_id"].astype(int).astype(str)
    )
    parts: list[pd.DataFrame] = []
    missing: list[str] = []
    campaign_root = PROJECT_ROOT / "experiments" / "campaigns"
    for source_run, expected in identity.groupby("source_run", sort=True):
        matches = list(
            campaign_root.glob(f"*/runs/{source_run}__feedback_pairs.parquet")
        )
        if len(matches) != 1:
            missing.append(str(source_run))
            continue
        part = pd.read_parquet(matches[0])
        part["source_run"] = str(source_run)
        part["row_uid"] = part["source_run"] + "|" + part["snapshot_id"].astype(str)
        part = part.loc[part["row_uid"].isin(expected["row_uid"])]
        parts.append(part)
    if missing:
        print(
            "[recovery-analysis] source queries unavailable for "
            + ", ".join(missing),
            flush=True,
        )
    if not parts:
        return pd.DataFrame()
    source = pd.concat(parts, ignore_index=True)
    if source.duplicated("row_uid").any():
        raise ValueError("Duplicate pre-intervention source queries")
    return source.merge(
        identity.loc[:, ["row_uid", "cell_key"]],
        on="row_uid",
        how="inner",
        validate="one_to_one",
    )


def summarize(
    branches: pd.DataFrame,
    *,
    repetitions: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    frame = branches.copy()
    for column in (
        "terminal_success",
        "strict_replay",
        "terminal_episode_target_drop_candidate",
        "terminal_episode_wrong_object_interaction_candidate",
        "terminal_episode_official_safety_violation",
        "source_feedback_drop",
        "source_feedback_wrong",
        "source_feedback_safety",
        "proposal_deployable",
    ):
        frame[column] = _as_bool(frame[column])
    frame["cell_key"] = (
        frame["position_level"].astype(str)
        + "|task"
        + frame["task_id"].astype(int).astype(str)
    )

    records = []
    for proposal_index, (proposal, part) in enumerate(frame.groupby("proposal", sort=True)):
        successes = part["terminal_success"].astype(float)
        ci_low, ci_high = clustered_mean_interval(
            part,
            successes,
            repetitions=repetitions,
            seed=20260904 + proposal_index,
        )
        success_part = part.loc[part["terminal_success"]]
        record = {
            "proposal": proposal,
            "deployable": bool(part["proposal_deployable"].all()),
            "n_states": int(len(part)),
            "n_groups": int(part["independent_group"].nunique()),
            "strict_replay_rate": float(part["strict_replay"].mean()),
            "successes": int(part["terminal_success"].sum()),
            "success_rate": float(successes.mean()),
            "success_ci_low": ci_low,
            "success_ci_high": ci_high,
            "rescued_cells": int(success_part["cell_key"].nunique()),
            "rescued_tasks": int(success_part["task_id"].nunique()),
            "drop_rate": float(part["terminal_episode_target_drop_candidate"].mean()),
            "baseline_drop_rate": float(part["source_feedback_drop"].mean()),
            "wrong_rate": float(
                part["terminal_episode_wrong_object_interaction_candidate"].mean()
            ),
            "baseline_wrong_rate": float(part["source_feedback_wrong"].mean()),
            "safety_rate": float(
                part["terminal_episode_official_safety_violation"].mean()
            ),
            "baseline_safety_rate": float(part["source_feedback_safety"].mean()),
            "mean_final_t": float(pd.to_numeric(part["terminal_final_t"]).mean()),
            "mean_queries": float(pd.to_numeric(part["continuation_queries"]).mean()),
            "mean_executed_steps": float(pd.to_numeric(part["branch_executed_steps"]).mean()),
        }
        record["drop_rate_delta"] = record["drop_rate"] - record["baseline_drop_rate"]
        record["wrong_rate_delta"] = record["wrong_rate"] - record["baseline_wrong_rate"]
        record["safety_rate_delta"] = record["safety_rate"] - record["baseline_safety_rate"]
        if record["deployable"]:
            passed, failed = proposal_gate(record)
        else:
            passed, failed = False, ["diagnostic_privileged_proposal"]
        record["gate_passed"] = passed
        record["failed_gate_checks"] = ";".join(failed)
        records.append(record)
    proposal_summary = pd.DataFrame(records).sort_values(
        ["deployable", "gate_passed", "success_rate"], ascending=[False, False, False]
    )

    cell_summary = (
        frame.groupby(["proposal", "position_level", "task_id"], sort=True)
        .agg(
            n_states=("row_uid", "size"),
            successes=("terminal_success", "sum"),
            success_rate=("terminal_success", "mean"),
            drop_rate=("terminal_episode_target_drop_candidate", "mean"),
            wrong_rate=("terminal_episode_wrong_object_interaction_candidate", "mean"),
            safety_rate=("terminal_episode_official_safety_violation", "mean"),
            mean_queries=("continuation_queries", "mean"),
        )
        .reset_index()
    )

    state = frame.pivot(index="row_uid", columns="proposal", values="terminal_success")
    deployable_names = proposal_summary.loc[proposal_summary["deployable"], "proposal"].tolist()
    all_success = state.fillna(False).astype(bool).any(axis=1)
    deployable_success = state.loc[:, [name for name in deployable_names if name in state]].fillna(False).astype(bool).any(axis=1)
    unique_states = frame.drop_duplicates("row_uid").set_index("row_uid").loc[state.index]
    all_low, all_high = clustered_mean_interval(
        unique_states.reset_index(), all_success.astype(float), repetitions=repetitions, seed=20261904
    )
    deploy_low, deploy_high = clustered_mean_interval(
        unique_states.reset_index(), deployable_success.astype(float), repetitions=repetitions, seed=20262904
    )
    passing = proposal_summary.loc[proposal_summary["gate_passed"], "proposal"].tolist()
    privileged = proposal_summary.loc[~proposal_summary["deployable"]].sort_values(
        "success_rate", ascending=False
    )
    privileged_sr = float(privileged.iloc[0]["success_rate"]) if len(privileged) else 0.0
    deployable_oracle_sr = float(deployable_success.mean())
    if passing:
        decision = "advance_fixed_proposal_to_untouched_reserve"
    elif privileged_sr >= 0.10:
        decision = "develop_perception_backed_regrasp_then_test_reserve"
    elif deployable_oracle_sr >= 0.10:
        decision = "freeze_rule_based_proposal_router_before_reserve"
    else:
        decision = "deprioritize_recovery_proposals"
    oracle = {
        "n_states": int(len(state)),
        "all_proposal_oracle_successes": int(all_success.sum()),
        "all_proposal_oracle_success_rate": float(all_success.mean()),
        "all_proposal_oracle_ci_low": all_low,
        "all_proposal_oracle_ci_high": all_high,
        "deployable_oracle_successes": int(deployable_success.sum()),
        "deployable_oracle_success_rate": deployable_oracle_sr,
        "deployable_oracle_ci_low": deploy_low,
        "deployable_oracle_ci_high": deploy_high,
        "passing_deployable_proposals": passing,
        "decision": decision,
    }
    return proposal_summary, cell_summary, oracle


def query_separation(queries: pd.DataFrame, branches: pd.DataFrame) -> pd.DataFrame:
    if queries.empty:
        return pd.DataFrame()
    labels = branches.loc[:, ["row_uid", "proposal", "terminal_success"]].copy()
    labels["terminal_success"] = _as_bool(labels["terminal_success"])
    records = []
    for metric in QUERY_METRICS:
        if metric not in queries:
            continue
        aggregate = (
            queries.assign(_value=pd.to_numeric(queries[metric], errors="coerce"))
            .groupby(["row_uid", "proposal"], sort=False)["_value"]
            .agg(["first", "mean", "max"])
            .reset_index()
            .merge(labels, on=["row_uid", "proposal"], validate="one_to_one")
        )
        for aggregation in ("first", "mean", "max"):
            values = aggregate[aggregation].to_numpy(float)
            success = aggregate["terminal_success"].to_numpy(bool)
            records.append(
                {
                    "metric": metric,
                    "aggregation": aggregation,
                    "n": int(np.isfinite(values).sum()),
                    "success_mean": float(np.nanmean(values[success])) if success.any() else np.nan,
                    "fail_mean": float(np.nanmean(values[~success])) if (~success).any() else np.nan,
                    "failure_auc": binary_auc(~success, values),
                }
            )
    result = pd.DataFrame(records)
    if not result.empty:
        result["failure_auc_strength"] = (result["failure_auc"] - 0.5).abs()
        result = result.sort_values("failure_auc_strength", ascending=False)
    return result


def pre_intervention_separation(
    source_queries: pd.DataFrame,
    branches: pd.DataFrame,
) -> pd.DataFrame:
    if source_queries.empty:
        return pd.DataFrame()
    records = []
    labels = branches.loc[:, ["row_uid", "proposal", "terminal_success"]].copy()
    labels["terminal_success"] = _as_bool(labels["terminal_success"])
    for proposal, proposal_labels in labels.groupby("proposal", sort=True):
        frame = source_queries.merge(
            proposal_labels.loc[:, ["row_uid", "terminal_success"]],
            on="row_uid",
            validate="one_to_one",
        )
        failure = ~frame["terminal_success"].to_numpy(bool)
        for metric in QUERY_METRICS:
            if metric not in frame:
                continue
            values = pd.to_numeric(frame[metric], errors="coerce").to_numpy(float)
            same_cell_auc, comparable_cells, comparable_pairs = stratified_binary_auc(
                failure,
                values,
                frame["cell_key"].astype(str),
            )
            records.append(
                {
                    "proposal": str(proposal),
                    "metric": metric,
                    "n": int(np.isfinite(values).sum()),
                    "successes": int((~failure).sum()),
                    "failures": int(failure.sum()),
                    "success_mean": float(np.nanmean(values[~failure])),
                    "fail_mean": float(np.nanmean(values[failure])),
                    "pooled_failure_auc": binary_auc(failure, values),
                    "same_cell_failure_auc": same_cell_auc,
                    "comparable_cells": comparable_cells,
                    "comparable_pairs": comparable_pairs,
                }
            )
    result = pd.DataFrame(records)
    if not result.empty:
        result["pooled_auc_strength"] = (
            result["pooled_failure_auc"] - 0.5
        ).abs()
        result = result.sort_values(
            ["proposal", "pooled_auc_strength"], ascending=[True, False]
        )
    return result


def _write_plot(summary: pd.DataFrame, cells: pd.DataFrame, output: Path) -> None:
    order = summary["proposal"].tolist()
    colors = ["#2878B5" if bool(value) else "#C65D21" for value in summary["deployable"]]
    figure, axes = plt.subplots(1, 3, figsize=(17, 5.2))
    y = np.arange(len(summary))
    lower = summary["success_rate"] - summary["success_ci_low"]
    upper = summary["success_ci_high"] - summary["success_rate"]
    axes[0].barh(y, summary["success_rate"], color=colors, alpha=0.9)
    axes[0].errorbar(summary["success_rate"], y, xerr=[lower, upper], fmt="none", color="black", capsize=3)
    axes[0].set_yticks(y, order)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, max(0.25, float(summary["success_ci_high"].max()) + 0.05))
    axes[0].set_xlabel("Terminal success rate")
    axes[0].set_title("Recovery from baseline both-fail states")
    axes[0].grid(axis="x", alpha=0.25)

    side = summary.set_index("proposal").loc[order]
    x = np.arange(len(order))
    width = 0.25
    axes[1].bar(x - width, side["drop_rate"], width, label="drop", color="#D95F02")
    axes[1].bar(x, side["wrong_rate"], width, label="wrong object", color="#7570B3")
    axes[1].bar(x + width, side["safety_rate"], width, label="official safety", color="#1B9E77")
    axes[1].set_xticks(x, order, rotation=25, ha="right")
    axes[1].set_ylabel("Rate")
    axes[1].set_title("Terminal side effects")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y", alpha=0.25)

    matrix = cells.copy()
    matrix["cell"] = matrix["position_level"].astype(str) + "/t" + matrix["task_id"].astype(str)
    pivot = matrix.pivot(index="proposal", columns="cell", values="success_rate").reindex(order)
    image = axes[2].imshow(pivot.to_numpy(float), vmin=0, vmax=max(0.3, float(np.nanmax(pivot))), cmap="YlGnBu", aspect="auto")
    axes[2].set_yticks(np.arange(len(pivot)), pivot.index)
    axes[2].set_xticks(np.arange(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    axes[2].set_title("Success rate by frozen cell")
    for row in range(len(pivot)):
        for column in range(len(pivot.columns)):
            axes[2].text(column, row, f"{pivot.iloc[row, column]:.0%}", ha="center", va="center", fontsize=8)
    figure.colorbar(image, ax=axes[2], fraction=0.046, pad=0.04)
    figure.tight_layout()
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _write_video_index(branches: pd.DataFrame, output_dir: Path) -> None:
    frame = branches.sort_values(["position_level", "task_id", "row_uid", "proposal"])
    sections = []
    for row_uid, part in frame.groupby("row_uid", sort=False):
        first = part.iloc[0]
        cards = []
        for branch in part.itertuples(index=False):
            if not str(branch.video_path).strip():
                continue
            source = PROJECT_ROOT / str(branch.video_path)
            relative = os.path.relpath(source, output_dir)
            cards.append(
                "<article><h3>"
                + html.escape(str(branch.proposal))
                + f" | success={bool(branch.terminal_success)} | t={int(branch.terminal_final_t)}</h3>"
                + f'<video controls preload="metadata" src="{html.escape(relative)}"></video></article>'
            )
        sections.append(
            "<section><h2>"
            + html.escape(
                f"{first.position_level} task={int(first.task_id)} init={int(first.init_state_id)} "
                f"rollout={int(first.rollout_id)} | {row_uid}"
            )
            + '<div class="grid">'
            + ("".join(cards) if cards else "<p>Videos disabled for this screening run.</p>")
            + "</div></section>"
        )
    document = """<!doctype html><html><head><meta charset="utf-8"><title>P3 recovery videos</title>
<style>body{font:14px system-ui;margin:24px;color:#1d2430}section{border-top:1px solid #ccd3dc;padding:18px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(280px,1fr));gap:14px}video{width:100%;background:#111}h2{font-size:16px}h3{font-size:13px;font-weight:600}@media(max-width:1000px){.grid{grid-template-columns:1fr}}</style>
</head><body><h1>Frozen exact-state recovery branches</h1>""" + "".join(sections) + "</body></html>"
    (output_dir / "video_index.html").write_text(document, encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    return frame.to_markdown(index=False)


def write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    cells: pd.DataFrame,
    oracle: Mapping[str, Any],
    separation: pd.DataFrame,
    pre_intervention: pd.DataFrame,
) -> None:
    display_columns = [
        "proposal",
        "deployable",
        "successes",
        "n_states",
        "success_rate",
        "success_ci_low",
        "success_ci_high",
        "rescued_cells",
        "rescued_tasks",
        "drop_rate",
        "wrong_rate",
        "mean_queries",
        "gate_passed",
    ]
    top_metrics = separation.head(15) if not separation.empty else separation
    privileged_pre = pre_intervention.loc[
        pre_intervention["proposal"].eq("privileged_regrasp_h8")
        & pre_intervention["metric"].isin(
            {
                "candidate_value_mean",
                "candidate_value_std",
                "candidate_value_range",
                "candidate_value_internal_consistency_mean",
            }
        )
    ]
    report = f"""# P3 recovery-proposal opportunity results

## Decision

**{oracle['decision']}**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

{_markdown_table(summary.loc[:, display_columns])}

## Oracle coverage

- Deployable proposal oracle: **{oracle['deployable_oracle_successes']}/{oracle['n_states']} = {oracle['deployable_oracle_success_rate']:.1%}** (cluster-bootstrap 95% CI {oracle['deployable_oracle_ci_low']:.1%} to {oracle['deployable_oracle_ci_high']:.1%}).
- All-proposal oracle, including privileged regrasp: **{oracle['all_proposal_oracle_successes']}/{oracle['n_states']} = {oracle['all_proposal_oracle_success_rate']:.1%}** (95% CI {oracle['all_proposal_oracle_ci_low']:.1%} to {oracle['all_proposal_oracle_ci_high']:.1%}).
- Passing deployable proposals: `{oracle['passing_deployable_proposals']}`.

## Per-cell results

{_markdown_table(cells)}

## Query-level descriptive signals

These are post-branch descriptive associations, not a trained or validated
selector. `failure_auc` uses a larger metric value as evidence for eventual
failure; values near 0.5 are uninformative and values below 0.5 reverse sign.
The `mean` and `max` aggregations include observations collected after the
proposal has already changed the trajectory. They are confounded by proposal
family, query timing and episode length, so even a high pooled AUC must not be
reported as a pre-intervention failure predictor.

{_markdown_table(top_metrics)}

## Common pre-intervention query

This table uses only the shared query at `t=64`, before the recovery proposal
changes the trajectory. `same_cell_failure_auc` compares only success/failure
pairs from the same frozen `(position level, task)` cell. The collapse of the
three uncertainty AUCs after this control shows that their pooled association
mostly tracks cell difficulty. The value mean remains exploratory and has not
been evaluated on the untouched reserve.

{_markdown_table(privileged_pre)}

## Artifacts

- `recovery_proposal_summary.csv`: primary proposal table and frozen gates.
- `recovery_cell_summary.csv`: eight-cell breakdown.
- `oracle_summary.json`: deployable and diagnostic oracle coverage.
- `query_metric_separation.csv`: descriptive uncertainty associations.
- `pre_intervention_metric_separation.csv`: pooled and same-cell source-query associations.
- `recovery_opportunity.png`: SR, side effects and cell heatmap.
- `video_index.html`: all proposals aligned by exact starting snapshot.

The privileged regrasp branch uses true simulator object position and must not
be reported as a deployable method.
"""
    (output_dir / "RESULTS.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments/campaigns/recovery_proposal_opportunity_20260904",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--expected-states", type=int, default=EXPECTED_STATES)
    parser.add_argument(
        "--expected-proposals",
        default="",
        help="Optional comma-separated proposal set for this campaign.",
    )
    parser.add_argument("--bootstrap-repetitions", type=int, default=BOOTSTRAP_REPETITIONS)
    args = parser.parse_args()
    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = (args.output_dir or campaign_dir / "analysis").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    branches, queries = load_outputs(campaign_dir)
    expected_proposals = {
        item.strip() for item in args.expected_proposals.split(",") if item.strip()
    }
    if expected_proposals and set(branches["proposal"].astype(str)) != expected_proposals:
        raise ValueError("Campaign proposal set does not match the frozen protocol")
    counts = branches.groupby("proposal")["row_uid"].nunique()
    if not counts.eq(args.expected_states).all():
        raise ValueError(f"Incomplete campaign state counts: {counts.to_dict()}")

    summary, cells, oracle = summarize(
        branches, repetitions=args.bootstrap_repetitions
    )
    separation = query_separation(queries, branches)
    source_queries = load_pre_intervention_queries(branches)
    pre_intervention = pre_intervention_separation(source_queries, branches)
    branches.to_parquet(output_dir / "all_recovery_branches.parquet", index=False)
    branches.to_csv(output_dir / "all_recovery_branches.csv", index=False)
    queries.to_parquet(output_dir / "all_query_metrics.parquet", index=False)
    summary.to_csv(output_dir / "recovery_proposal_summary.csv", index=False)
    cells.to_csv(output_dir / "recovery_cell_summary.csv", index=False)
    separation.to_csv(output_dir / "query_metric_separation.csv", index=False)
    pre_intervention.to_csv(
        output_dir / "pre_intervention_metric_separation.csv", index=False
    )
    (output_dir / "oracle_summary.json").write_text(
        json.dumps(oracle, indent=2), encoding="utf-8"
    )
    _write_plot(summary, cells, output_dir / "recovery_opportunity.png")
    _write_video_index(branches, output_dir)
    write_report(
        output_dir,
        summary,
        cells,
        oracle,
        separation,
        pre_intervention,
    )
    print(json.dumps(oracle, indent=2), flush=True)
    print(f"[recovery-analysis] results={output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

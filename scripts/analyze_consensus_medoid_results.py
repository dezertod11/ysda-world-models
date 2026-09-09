#!/usr/bin/env python3
"""Audit the pre-P5 development runs and plot episode-level comparisons."""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import pandas as pd
from scipy.stats import binomtest

if __package__:
    from .analyze_consensus_medoid_campaign import PAIR_KEYS, _cluster_bootstrap_interval, _load_traces
else:
    from analyze_consensus_medoid_campaign import PAIR_KEYS, _cluster_bootstrap_interval, _load_traces


STAGES = {
    "exact_development": (40, {"first": 1, "max_value": 3, "consensus_medoid_only": 3}),
    "architecture_development": (
        20, {"max_value": 5, "keystone_cluster_medoid": 5, "cosmos_consensus_guarded": 5}
    ),
}
LABELS = {
    "first": "Single sample K1",
    "max_value": "Max value",
    "consensus_medoid_only": "Pure medoid K3",
    "keystone_cluster_medoid": "KeyStone-style K5",
    "cosmos_consensus_guarded": "Cosmos guarded K5",
}
COLORS = {
    "first": "#525252", "max_value": "#377eb8", "consensus_medoid_only": "#b65e3c",
    "keystone_cluster_medoid": "#9674ad", "cosmos_consensus_guarded": "#258774",
}
SAFETY = [
    "target_drop_candidate", "wrong_object_interaction_candidate",
    "kinematic_deadlock_candidate", "official_safety_violation",
]


def validate_episodes(traces: pd.DataFrame, expected: int, strategies: dict) -> pd.DataFrame:
    keys = [*PAIR_KEYS, "planning_strategy"]
    if traces.duplicated([*keys, "query_idx"]).any():
        raise ValueError("Duplicate query rows; do not silently merge repeated executions")
    if set(traces.planning_strategy) != set(strategies):
        raise ValueError("Unexpected or missing strategy")
    groups = traces.groupby(keys, sort=False)
    for name, group in groups:
        group = group.sort_values("query_idx")
        if not np.array_equal(group.query_idx, np.arange(len(group))):
            raise ValueError(f"Incomplete query sequence: {name}")
        if (group[["success", "final_t", "num_queries"]].nunique() != 1).any():
            raise ValueError(f"Conflicting episode metadata: {name}")
        if int(group.num_queries.iloc[0]) != len(group):
            raise ValueError(f"Partial episode: {name}")
        if group.t.iloc[0] != 0 or group.t_after.iloc[-1] != group.final_t.iloc[-1]:
            raise ValueError(f"Invalid endpoint: {name}")
        if not np.array_equal(group.t.iloc[1:].to_numpy(), group.t_after.iloc[:-1].to_numpy()):
            raise ValueError(f"Discontinuous simulator timeline: {name}")
        if not (group.t_after - group.t).equals(group.executed_steps):
            raise ValueError(f"Invalid executed-step counts: {name}")
    episodes = traces.loc[traces.query_idx.eq(0)].copy()
    for strategy in strategies:
        e = episodes.loc[episodes.planning_strategy.eq(strategy)]
        if len(e) != expected or set(e.init_state_id) != set(range(expected)):
            raise ValueError(f"Unexpected initial-state coverage: {strategy}")
    return episodes


def initial_pair_audit(episodes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for left, right in itertools.combinations(sorted(episodes.planning_strategy.unique()), 2):
        a = episodes.loc[episodes.planning_strategy.eq(left)].set_index(PAIR_KEYS)
        b = episodes.loc[episodes.planning_strategy.eq(right)].set_index(PAIR_KEYS)
        for key in a.index.intersection(b.index):
            x, y = a.loc[key], b.loc[key]
            states = [np.asarray(json.loads(r.sim_state_json)) for r in (x, y)]
            actions = [np.asarray(json.loads(r.candidate_action_chunks_json)) for r in (x, y)]
            values = [np.asarray(json.loads(r.candidate_values_json)) for r in (x, y)]
            count = min(len(actions[0]), len(actions[1]))
            rows.append({
                **dict(zip(PAIR_KEYS, key)), "reference": left, "method": right,
                "compared_candidates": count,
                "same_candidate_count": len(actions[0]) == len(actions[1]),
                "sim_state_max_abs_delta": float(np.max(np.abs(states[0] - states[1]))),
                "action_max_abs_delta": float(np.max(np.abs(actions[0][:count] - actions[1][:count]))),
                "value_max_abs_delta": float(np.max(np.abs(values[0][:count] - values[1][:count]))),
            })
    return pd.DataFrame(rows)


def selector_audit(traces: pd.DataFrame, strategies: dict, module) -> pd.DataFrame:
    rows = []
    for strategy, group in traces.groupby("planning_strategy"):
        mismatch = 0
        matrix_error = 0.0
        shape_errors = 0
        for row in group.itertuples():
            actions = np.asarray(json.loads(row.candidate_action_chunks_json))
            values = np.asarray(json.loads(row.candidate_values_json))
            shape_errors += int(actions.shape != (strategies[strategy], 16, 7))
            selected, diagnostic = module.consensus_medoid_only(actions)
            matrix = np.asarray(json.loads(row.candidate_structured_distance_matrix_json))
            matrix_error = max(matrix_error, float(np.max(np.abs(matrix - diagnostic["total"]))))
            if strategy == "first":
                selected = 0
            elif strategy == "max_value":
                selected = int(values.argmax())
            elif strategy == "keystone_cluster_medoid":
                selected, _ = module.guarded_cluster_medoid(actions)
            elif strategy == "cosmos_consensus_guarded":
                _, mode = module.guarded_cluster_medoid(actions, horizon=5, medoid_distances=matrix)
                costs = np.asarray(json.loads(row.candidate_cosmos_joint_cost_json))
                members = mode["dominant_indices"]
                proposal = int(members[np.argmin(costs[members])])
                maximum = int(values.argmax())
                enabled = (
                    proposal != maximum
                    and values[maximum] - values[proposal] <= row.planning_value_margin
                    and row.planning_consensus_action_gain >= row.planning_uncertainty_margin
                    and costs[maximum] - costs[proposal] > 0
                )
                selected = proposal if enabled else maximum
            mismatch += int(selected != row.selected_sample_idx)
        rows.append({
            "planning_strategy": strategy, "query_rows": len(group),
            "selector_mismatches": mismatch, "action_shape_errors": shape_errors,
            "distance_matrix_max_abs_error": matrix_error,
        })
    return pd.DataFrame(rows)


def paired_tables(episodes: pd.DataFrame, strategies: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    paired = episodes.pivot(index=PAIR_KEYS, columns="planning_strategy", values="success").reset_index()
    if paired[list(strategies)].isna().any().any():
        raise ValueError("Missing cross-strategy pairs")
    rows, cases = [], []
    for left, right in itertools.combinations(strategies, 2):
        rescue = (~paired[left] & paired[right]).to_numpy()
        harm = (paired[left] & ~paired[right]).to_numpy()
        n = int(rescue.sum() + harm.sum())
        low, high = _cluster_bootstrap_interval(paired, left, right)
        rows.append({
            "reference": left, "method": right, "paired_episodes": len(paired),
            "delta_sr": float(paired[right].mean() - paired[left].mean()),
            "ci95_low": low, "ci95_high": high,
            "rescues": int(rescue.sum()), "harms": int(harm.sum()),
            "mcnemar_exact_p": float(binomtest(int(rescue.sum()), n).pvalue) if n else 1.0,
        })
        for index, pair in paired.iterrows():
            cases.append({
                **{key: pair[key] for key in PAIR_KEYS}, "reference": left, "method": right,
                "reference_success": bool(pair[left]), "method_success": bool(pair[right]),
                "effect": "rescue" if rescue[index] else "harm" if harm[index] else "same",
            })
    return pd.DataFrame(rows), pd.DataFrame(cases)


def plot_results(summary: pd.DataFrame, effects: pd.DataFrame, episodes: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for ax, (stage, (_, strategies)) in zip(axes, STAGES.items()):
        group = summary.loc[summary.stage.eq(stage)].set_index("planning_strategy").loc[list(strategies)]
        positions = np.arange(len(group))
        values = group.success_rate.to_numpy() * 100
        ax.bar(positions, values, color=[COLORS[s] for s in group.index], width=0.65)
        ax.errorbar(positions, values, yerr=np.vstack([
            values - group.sr_ci95_low.to_numpy() * 100,
            group.sr_ci95_high.to_numpy() * 100 - values,
        ]), fmt="none", ecolor="#252525", capsize=4)
        for position, row in enumerate(group.itertuples()):
            ax.text(position, row.sr_ci95_high * 100 + 2, f"{row.successes}/{row.episodes}", ha="center")
        ax.set(xticks=positions, xticklabels=[LABELS[s] for s in group.index], ylim=(0, 65), ylabel="Success rate (%)")
        ax.tick_params(axis="x", labelsize=9)
        ax.set_title("Stage A: 40 inits, K1/K3" if stage.startswith("exact") else "Stage B: 20 inits, K5")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("LIBERO-PRO Object task 0, execute H5; Wilson 95% intervals")
    fig.savefig(output / "success_rates.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(13, 5.5), layout="constrained")
    for ax, (stage, (_, strategies)) in zip(axes, STAGES.items()):
        pivot = episodes.loc[episodes.stage.eq(stage)].pivot(
            index="planning_strategy", columns="init_state_id", values="success"
        ).loc[list(strategies)]
        ax.imshow(pivot.astype(int), aspect="auto", vmin=0, vmax=1, cmap=ListedColormap(["#d7d9dc", "#258774"]))
        ax.set(yticks=np.arange(len(pivot)), yticklabels=[LABELS[s] for s in pivot.index],
               xticks=np.arange(len(pivot.columns)), xticklabels=pivot.columns, xlabel="Initial-state index")
        ax.set_title(stage.replace("_", " ").title() + ": green = success, gray = fail")
        ax.tick_params(axis="x", labelsize=8)
    fig.savefig(output / "paired_outcomes.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    for index, row in enumerate(effects.itertuples()):
        ax.errorbar(row.delta_sr * 100, index,
                    xerr=[[100 * (row.delta_sr - row.ci95_low)], [100 * (row.ci95_high - row.delta_sr)]],
                    fmt="o", color=COLORS[row.method], capsize=4)
    ax.axvline(0, color="#555555", linestyle="--", linewidth=1)
    ax.set(yticks=np.arange(len(effects)), yticklabels=[
        f"{'A' if r.stage.startswith('exact') else 'B'}: {LABELS[r.method]} vs {LABELS[r.reference]}"
        for r in effects.itertuples()
    ], xlabel="Paired success-rate change (percentage points)", title="Development effects; init bootstrap 95% CI")
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(output / "paired_effects.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, default=Path("experiments/campaigns"))
    parser.add_argument("--run-base", default="consensus_medoid_pre_p5_20260907")
    args = parser.parse_args()
    output = args.campaign_root / args.run_base / "analysis"
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "consensus_geometry", root / "cosmos-policy/cosmos_policy/experiments/robot/libero/consensus_medoid.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summaries, episode_frames, effects_frames, case_frames, audit_frames, selector_frames, reasons = [], [], [], [], [], [], []
    integrity = {}
    for stage, (expected, strategies) in STAGES.items():
        campaign = args.campaign_root / f"{args.run_base}__{stage}"
        manifest = json.loads((campaign / "manifest.json").read_text())
        if manifest["status"] != "completed" or any(r["status"] != "completed" for r in manifest["results"]):
            raise ValueError(f"Unfinished campaign: {stage}")
        traces = _load_traces(campaign)
        episodes = validate_episodes(traces, expected, strategies)
        audit = initial_pair_audit(episodes).assign(stage=stage)
        selectors = selector_audit(traces, strategies, module).assign(stage=stage)
        effects, cases = paired_tables(episodes, strategies)
        for strategy, candidates in strategies.items():
            e = episodes.loc[episodes.planning_strategy.eq(strategy)]
            q = traces.loc[traces.planning_strategy.eq(strategy)]
            ci = binomtest(int(e.success.sum()), len(e)).proportion_ci(method="wilson")
            summaries.append({
                "stage": stage, "planning_strategy": strategy, "candidates": candidates,
                "episodes": len(e), "successes": int(e.success.sum()), "success_rate": float(e.success.mean()),
                "sr_ci95_low": ci.low, "sr_ci95_high": ci.high,
                "query_rows": len(q), "mean_queries": float(e.num_queries.mean()),
                "candidate_draws": candidates * len(q), "mean_final_t": float(e.final_t.mean()),
                "switch_rate": float((~q.max_value_selected).mean()),
                "episodes_with_switch": int(q.groupby(PAIR_KEYS).max_value_selected.apply(lambda x: (~x).any()).sum()),
                "target_lift_episodes": int((e.episode_time_to_first_target_lift >= 0).sum()),
                **{name: int(e[name].sum()) for name in SAFETY},
            })
        if "cosmos_consensus_guarded" in strategies:
            guarded = traces.loc[traces.planning_strategy.eq("cosmos_consensus_guarded")]
            for reason, count in guarded.planning_consensus_fallback_reason.value_counts().items():
                reasons.append({"reason": reason, "queries": int(count), "fraction": float(count / len(guarded))})
            integrity["guard_value_gap_quantiles"] = guarded.planning_consensus_value_gap.quantile([0.5, 0.95, 1]).to_dict()
        integrity[stage] = {
            "manifest_status": manifest["status"], "episodes": len(episodes), "queries": len(traces),
            "failed_episodes": int((~episodes.success).sum()),
            "all_failures_reached_t280": bool(episodes.loc[~episodes.success].final_t.eq(280).all()),
            "all_initial_states_exact": bool(audit.sim_state_max_abs_delta.eq(0).all()),
            "selector_mismatches": int(selectors.selector_mismatches.sum()),
            "selector_matrix_max_abs_error": float(selectors.distance_matrix_max_abs_error.max()),
            "generated_horizon": 16, "execution_horizon": 5,
            "prediction_error_horizon_aligned": False,
            "wall_seconds": float((pd.Timestamp(manifest["finished_at"]) - pd.Timestamp(manifest["created_at"])).total_seconds()),
        }
        episode_frames.append(episodes.assign(stage=stage))
        effects_frames.append(effects.assign(stage=stage))
        case_frames.append(cases.assign(stage=stage))
        audit_frames.append(audit)
        selector_frames.append(selectors)
    tables = {
        "strategy_summary": pd.DataFrame(summaries), "episode_outcomes": pd.concat(episode_frames),
        "paired_effects": pd.concat(effects_frames, ignore_index=True),
        "paired_cases": pd.concat(case_frames, ignore_index=True),
        "initial_pool_audit": pd.concat(audit_frames, ignore_index=True),
        "selector_audit": pd.concat(selector_frames, ignore_index=True),
        "guard_reasons": pd.DataFrame(reasons),
    }
    for name, frame in tables.items():
        frame.to_csv(output / f"{name}.csv", index=False)
    (output / "integrity.json").write_text(json.dumps(integrity, indent=2) + "\n")
    plot_results(tables["strategy_summary"], tables["paired_effects"], tables["episode_outcomes"], output)
    print(json.dumps(integrity, indent=2))
    print(tables["paired_effects"].to_string(index=False))
    print(f"Saved audit and figures: {output}")


if __name__ == "__main__":
    main()

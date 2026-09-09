#!/usr/bin/env python3
"""Fixed selectors on already-exposed terminal branches; no new policy inference."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from scripts.analyze_trajectory_consensus_campaign import interval
except ModuleNotFoundError:
    from analyze_trajectory_consensus_campaign import interval

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/candidate_scores.parquet"


def runtime_module(name):
    path = ROOT / f"cosmos-policy/cosmos_policy/experiments/robot/libero/{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_pool(rows):
    if rows.candidate_idx.tolist() != list(range(4)):
        raise ValueError("Expected exactly four ordered candidates")
    for col in ("terminal_available", "terminal_success", "terminal_target_drop_candidate"):
        if rows[col].isna().any() or not rows[col].isin([True, False, 0, 1]).all():
            raise ValueError(f"Missing or invalid {col}")
    if not rows.terminal_available.all():
        raise ValueError("Incomplete terminal outcomes")
    for col in ("factor", "group_id", "task_id", "init_state_id", "sidecar_path", "open_loop_steps", "prediction_mode"):
        if rows[col].nunique(dropna=False) != 1:
            raise ValueError(f"Conflicting pool {col}")
    if not rows.open_loop_steps.eq(16).all() or not rows.prediction_mode.eq("parallel").all():
        raise ValueError("Expected H16 parallel branches")
    errors = rows.main_open_replay_state_max_abs.dropna().to_numpy(float)
    if not len(errors) or not np.isfinite(errors).all():
        return "missing_replay_audit"
    return "nonexact_replay" if np.max(np.abs(errors)) > 1e-9 else None


def choices(actions, values, geometry, consensus):
    results = {"max_value": (int(np.argmax(values)), values),
               "first_k4": (0, None)}
    for label, strategy in (
        ("osc_medoid", "trajectory_medoid"), ("raw_medoid", "trajectory_raw_medoid"),
        ("kdpe_endpoint", "trajectory_kdpe_endpoint"), ("osc_density", "trajectory_density"),
    ):
        selected, info = geometry.select_trajectory_consensus(actions, values, strategy=strategy)
        results[label] = (selected, info["trajectory_scores"])
    selected, _ = consensus.guarded_cluster_medoid(actions, horizon=16, random_seed=0)
    results["keystone"] = (selected, None)
    for label, args in {
        "no_integration": {"integrate": False}, "no_rotation": {"rotation_weight": 0},
        "no_gripper": {"gripper_weight": 0}, "uniform_time": {"discount": 1},
    }.items():
        scores = -geometry.trajectory_distances(actions, **args).mean(axis=1)
        selected = int(np.lexsort((np.arange(len(values)), -values, -scores))[0])
        results[label] = (selected, scores)
    return results


def mixed_concordance(scores, outcomes):
    if scores is None:
        return 0., 0
    diffs = np.asarray(scores)[outcomes][:, None] - np.asarray(scores)[~outcomes][None, :]
    return float((diffs > 0).sum() + 0.5 * (diffs == 0).sum()), diffs.size


def summarize(decisions):
    records = []
    for method, rows in decisions.groupby("method", sort=True):
        for scope, group in [("All", rows), *rows.groupby("factor")]:
            macro = group.groupby("factor").mean(numeric_only=True)
            ci = interval(group, repeats=5000)
            deterministic = method != "uniform_random_expected"
            rescues, harms = int(group.delta.eq(1).sum()), int(group.delta.eq(-1).sum())
            pairs = int(group.mixed_candidate_pairs.sum())
            records.append(dict(
                method=method, scope=scope, snapshots=len(group),
                macro_sr=float(macro.selected_success.mean()), pooled_sr=float(group.selected_success.mean()),
                macro_delta=float(macro.delta.mean()), ci95_low=ci[0], ci95_high=ci[1],
                rescues=rescues if deterministic else None, harms=harms if deterministic else None,
                mcnemar_p=(float(binomtest(rescues, rescues + harms).pvalue) if rescues + harms else 1.) if deterministic else None,
                oracle_sr=float(macro.oracle_success.mean()), macro_regret=float(macro.regret.mean()),
                macro_drop_rate=float(macro.selected_drop.mean()),
                within_pool_concordance=float(group.concordant_pair_credit.sum() / pairs) if pairs else None,
                mixed_candidate_pairs=pairs,
            ))
    return pd.DataFrame(records)


def analyze(source, output):
    geometry, consensus = runtime_module("trajectory_consensus"), runtime_module("consensus_medoid")
    data = pd.read_parquet(source)
    records, pools, exclusions = [], [], []
    for snapshot, rows in data.groupby("snapshot_group", sort=True):
        rows = rows.sort_values("candidate_idx")
        reason = validate_pool(rows)
        if reason:
            exclusions.append(dict(snapshot_group=snapshot, reason=reason))
            continue
        path = ROOT / rows.sidecar_path.iloc[0]
        with np.load(path, allow_pickle=False) as saved:
            actions, values = saved["candidate_actions"], saved["candidate_values"].reshape(-1)
        if actions.shape != (4, 16, 7) or not np.isfinite(actions).all():
            raise ValueError(f"Invalid action pool: {path}")
        np.testing.assert_allclose(values, rows.candidate_value.to_numpy(), rtol=1e-5, atol=1e-6)
        outcomes = rows.terminal_success.to_numpy(bool)
        drops = rows.terminal_target_drop_candidate.to_numpy(bool)
        baseline = int(np.argmax(values))
        shared = dict(snapshot_group=snapshot, factor=rows.factor.iloc[0],
                      task_id=int(rows.task_id.iloc[0]), init_state_id=int(rows.init_state_id.iloc[0]),
                      group_id=rows.group_id.iloc[0], query_idx=int(rows.query_idx.iloc[0]),
                      case_id=rows.case_id.iloc[0], baseline_success=int(outcomes[baseline]),
                      oracle_success=int(outcomes.any()), opportunity=int(outcomes.any()) - int(outcomes[baseline]))
        pools.append(dict(**shared, successful_candidates=int(outcomes.sum()),
                          pool_kind="all_fail" if not outcomes.any() else "all_success" if outcomes.all() else "mixed",
                          sidecar_path=str(path.relative_to(ROOT)),
                          sidecar_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for method, (selected, scores) in choices(actions, values, geometry, consensus).items():
            credit, count = mixed_concordance(scores, outcomes)
            records.append(dict(**shared, method=method, selected_idx=selected,
                selected_success=int(outcomes[selected]), delta=int(outcomes[selected]) - int(outcomes[baseline]),
                selected_drop=int(drops[selected]), regret=int(outcomes.any()) - int(outcomes[selected]),
                switched=selected != baseline, concordant_pair_credit=credit, mixed_candidate_pairs=count))
        expected = float(outcomes.mean())
        records.append(dict(**shared, method="uniform_random_expected", selected_idx=-1,
            selected_success=expected, delta=expected-int(outcomes[baseline]), selected_drop=float(drops.mean()),
            regret=int(outcomes.any())-expected, switched=.75, concordant_pair_credit=0., mixed_candidate_pairs=0))
    if not pools:
        raise ValueError("No audited complete pools")
    output.mkdir(parents=True, exist_ok=True)
    decisions = pd.DataFrame(records)
    decisions["switched"] = decisions.switched.astype(float)
    summary = summarize(decisions)
    pool_frame = pd.DataFrame(pools)
    opportunity = pool_frame.groupby(["factor", "pool_kind"]).size().unstack(fill_value=0)
    decisions.to_parquet(output / "decisions.parquet", index=False)
    summary.to_csv(output / "method_scores.csv", index=False)
    pool_frame.to_csv(output / "pool_audit.csv", index=False)
    opportunity.to_csv(output / "opportunity_counts.csv")
    pd.DataFrame(exclusions, columns=["snapshot_group", "reason"]).to_csv(output / "excluded_pools.csv", index=False)
    audit = dict(status="completed", interpretation="exploratory_already_exposed_P4b_not_new_holdout",
        source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        strict_pools=len(pools), excluded_pools=len(exclusions), methods=decisions.method.nunique(),
        source_code_sha256={name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                            for name, m in (("geometry", geometry), ("consensus", consensus))})
    (output / "summary.json").write_text(json.dumps(audit, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    all_scores = summary[summary.scope.eq("All")].sort_values("macro_delta")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(all_scores.method, 100*all_scores.macro_delta, color="#237b67")
    for y, row in enumerate(all_scores.itertuples()):
        ax.plot([100*row.ci95_low, 100*row.ci95_high], [y, y], color="#252525")
    ax.axvline(0, color="#b44242", linewidth=1)
    ax.set_xlabel("Macro terminal SR difference vs max-value (percentage points)")
    ax.set_title("Shared K4 pools; exposed data, not confirmatory")
    fig.tight_layout(); fig.savefig(output / "paired_effects.png", dpi=160); plt.close(fig)
    text = ["# Consensus common-pool diagnostic", "", json.dumps(audit, indent=2), "",
        "One fixed candidate is executed, followed by the original shared continuation policy.",
        "These are real terminal branches but not new closed-loop selector episodes.",
        "P4b labels were previously opened: all effects and ablations here are exploratory.", "",
        "## Available opportunity", opportunity.to_markdown(), "",
        "## Fixed methods", all_scores.to_markdown(index=False, floatfmt=".4f"), "",
        "![Paired effects](paired_effects.png)", "",
        "Uniform random is the exact expectation over the four measured outcomes, not a sampled episode.",
        "McNemar is omitted for this fractional control. Bootstrap resamples task/init clusters per factor.",
        "Within-pool concordance compares scores only across success/fail candidate pairs; ties count 0.5.",
        "Keystone has no scalar per-candidate ranking exported here, so its concordance is undefined.",
        "KDPE uses the paper bandwidths on induced OSC endpoints; it is explicitly an adaptation.",
        "No candidate outcomes or realized prediction errors enter any selector.", ""]
    (output / "RESULTS.md").write_text("\n".join(text))
    print(all_scores.to_string(index=False))
    print(json.dumps(audit, indent=2))
    return decisions, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.source, args.output)

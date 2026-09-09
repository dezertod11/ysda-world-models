#!/usr/bin/env python3
"""Audit fixed-query candidate outcomes before training task-critical P5 heads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.terminal_grounded_critic import TERMINAL_CRITIC_FEATURES
except ModuleNotFoundError:
    from terminal_grounded_critic import TERMINAL_CRITIC_FEATURES


def summarize_pool(group):
    group = group.sort_values("candidate_idx")
    if group.candidate_idx.tolist() != list(range(8)):
        raise ValueError("Expected exactly eight distinct candidates")
    if not group.terminal_available.eq(True).all() or not group.terminal_success.isin([True, False]).all():
        raise ValueError("Missing terminal outcomes")
    if not np.isfinite(group[list(TERMINAL_CRITIC_FEATURES)].to_numpy(dtype=float)).all():
        raise ValueError("Missing causal candidate features")
    if not group.open_loop_steps.eq(16).all() or not group.prediction_mode.eq("parallel").all():
        raise ValueError("Horizon or prediction-mode mismatch")
    replay = group.main_open_replay_state_max_abs.dropna().to_numpy(dtype=float)
    strict = len(replay) == 1 and np.isfinite(replay).all() and abs(replay[0]) <= 1e-9
    rows = []
    for k in (4, 8):
        candidates = group.iloc[:k]
        values = candidates.candidate_value.to_numpy(dtype=float)
        y = candidates.terminal_success.to_numpy(dtype=bool)
        first = group.iloc[0]
        factor = "Position" if "position" in str(first.case_id) else "Object"
        mixed = bool(y.any() and not y.all())
        accuracy = float(np.mean([float(a>b)+.5*float(a==b) for a in values[y] for b in values[~y]])) if mixed else None
        rows.append(dict(snapshot_id=str(first.snapshot_id), case_id=str(first.case_id), task_id=int(first.task_id),
            init_state_id=int(first.init_state_id), query_idx=int(first.query_idx), factor=factor, k=k,
            strict_replay=bool(strict), mixed=mixed, oracle_success=bool(y.any()), max_value_success=bool(y[np.argmax(values)]),
            first_success=bool(y[0]), uniform_expected_success=float(y.mean()), within_pool_value_accuracy=accuracy))
    return rows


def analyze(campaign, expected):
    manifest = json.loads((campaign / "manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("Incomplete campaign")
    parts, records = [], []
    for path in sorted((campaign / "runs").glob("*__candidate_outcomes.parquet")):
        frame = pd.read_parquet(path)
        frame["source_trace"] = str(path)
        frame["pool_id"] = path.name + "::" + frame.snapshot_id.astype(str)
        parts.append(frame)
        for pool_id, group in frame.groupby("pool_id"):
            records.extend(dict(pool_id=pool_id, **r) for r in summarize_pool(group))
    if not parts:
        raise ValueError("No candidate traces")
    candidates = pd.concat(parts, ignore_index=True)
    if candidates.pool_id.nunique() != expected:
        raise ValueError(f"Expected {expected} pools; found {candidates.pool_id.nunique()}")
    if expected == 36:
        for _, group in candidates.groupby(["case_id", "task_id", "init_state_id"]):
            if set(group.query_idx) != {0, 3}:
                raise ValueError("Missing scheduled query")
        if candidates[["case_id", "task_id", "init_state_id"]].drop_duplicates().shape[0] != 18:
            raise ValueError("Incomplete pilot grid")
    rows = pd.DataFrame(records)
    strict = rows[rows.strict_replay]
    mixed = strict[strict.k.eq(8) & strict.mixed]
    integrity = strict.pool_id.nunique() >= .9 * expected
    gate = integrity and len(mixed) >= 8 and mixed.task_id.nunique() >= 3 and mixed.factor.nunique() >= 2
    output = campaign / "p5_analysis"
    output.mkdir(exist_ok=True)
    candidates.to_parquet(output / "candidate_features_and_outcomes.parquet", index=False)
    rows.to_csv(output / "pool_audit.csv", index=False)
    scores = strict.groupby(["factor", "k"]).agg(pools=("pool_id", "size"), mixed=("mixed", "sum"),
        max_value_sr=("max_value_success", "mean"), oracle_sr=("oracle_success", "mean"),
        random_expected_sr=("uniform_expected_success", "mean"), value_accuracy=("within_pool_value_accuracy", "mean")).reset_index()
    scores.to_csv(output / "opportunity_scores.csv", index=False)
    payload = dict(status="completed", stage="development_data_audit", pools=expected,
        terminal_branches=len(candidates), strict_pools=int(strict.pool_id.nunique()), mixed_pools_k8=len(mixed),
        integrity_pass=bool(integrity), opportunity_gate=bool(gate), new_method_efficacy_test=False,
        action="design_grouped_P5_fit" if gate else "do_not_open_P5_holdout_no_automatic_expansion")
    (output / "summary.json").write_text(json.dumps(payload, indent=2)+"\n")
    report = ["# P5 boundary pilot: data opportunity, not method efficacy", "",
        "Scheduled q0/q3 on fixed Object/Position development cells, K8/H16, K1 continuation.",
        "No outcome-driven seed search. These data are development, not an untouched test set.", "",
        scores.to_markdown(index=False), "", json.dumps(payload, indent=2), "",
        "Within-pool value accuracy is conditional on mixed outcomes; it is not pooled failure AUC.",
        "Replay-invalid pools are excluded, never treated as successful integrity checks.",
        "No P5 model or holdout is automatically promoted by this opportunity gate."]
    (output / "RESULTS.md").write_text("\n".join(report)+"\n")
    print(json.dumps(payload), flush=True)
    if not integrity:
        raise ValueError("Replay integrity gate failed; see saved audit")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--expected-pools", type=int, required=True)
    args = parser.parse_args()
    analyze(args.campaign, args.expected_pools)

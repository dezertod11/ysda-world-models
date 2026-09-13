#!/usr/bin/env python3
"""Read-only audit of P3c/P3d raw branches, query budgets and split provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGNS = (
    ("perception_regrasp_online_trigger_20260904", "screen"),
    ("perception_regrasp_online_trigger_20260904", "development"),
    ("perception_regrasp_online_trigger_20260904", "holdout"),
    ("perception_regrasp_transfer_ablation_20260905", "development"),
)
BOOL_COLUMNS = (
    "terminal_success", "trigger_passed", "intervention_applied",
    "counterfactual_reused", "terminal_target_drop_candidate",
    "terminal_wrong_object_interaction_candidate", "terminal_official_safety_violation",
)
CASE_COLUMNS = (
    "suite", "split", "position_level", "task_id", "init_state_id",
    "rollout_id", "rollout_seed", "independent_group",
)


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in BOOL_COLUMNS:
        values = frame[column].astype(str).str.lower()
        if not values.isin(["true", "false", "1", "0"]).all():
            raise ValueError(f"Invalid or missing boolean in {column}")
        frame[column] = values.isin(["true", "1"]).astype(int)
    return frame


def validate_branches(frame: pd.DataFrame, manifest: pd.DataFrame) -> dict:
    """Reject duplicate/conflicting rows instead of silently keeping a rerun."""
    if frame.duplicated(["case_id", "strategy"]).any():
        raise ValueError("Duplicate case/strategy rows")
    if manifest.case_id.duplicated().any():
        raise ValueError("Duplicate manifest case")
    strategies = set(frame.strategy)
    if "baseline_h8" not in strategies:
        raise ValueError("Missing baseline")
    if set(frame.case_id) != set(manifest.case_id):
        raise ValueError("Raw cases do not match manifest")
    expected = manifest.set_index("case_id")
    f = frame.set_index("case_id")
    for column in CASE_COLUMNS:
        if not np.array_equal(f[column].to_numpy(), expected.loc[f.index, column].to_numpy()):
            raise ValueError(f"Manifest mismatch: {column}")
    for case_id, group in frame.groupby("case_id"):
        if set(group.strategy) != strategies:
            raise ValueError(f"Missing strategy in {case_id}")
        if group.prefix_state_sha256.nunique(dropna=False) != 1:
            raise ValueError(f"Different prefix snapshots in {case_id}")
        base = group.loc[group.strategy.eq("baseline_h8")].iloc[0]
        for _, reused in group.loc[group.counterfactual_reused.eq(1)].iterrows():
            cols = [c for c in frame if c.startswith("terminal_")]
            if not base[cols].equals(reused[cols]):
                raise ValueError(f"Fallback changed terminal outcome in {case_id}")
            if reused.primitive_steps != 0 or reused.intervention_applied:
                raise ValueError(f"Inconsistent fallback bookkeeping in {case_id}")
    replay = frame.snapshot_replay_max_abs.to_numpy(dtype=float)
    if not np.isfinite(replay).all() or (replay > 1e-9).any():
        raise ValueError("Recorded state restore error exceeds threshold")
    guard_fail = frame.trigger_passed.eq(1) & frame.intervention_applied.eq(0)
    return {
        "cases": len(manifest), "branches": len(frame),
        "trigger_positive_no_intervention": int(guard_fail.sum()),
        "max_recorded_restore_error": float(replay.max()),
        "unique_prefix_hashes": int(frame.prefix_state_sha256.nunique()),
    }


def validate_queries(frame: pd.DataFrame, queries: pd.DataFrame) -> None:
    if queries.duplicated(["case_id", "strategy", "query_idx"]).any():
        raise ValueError("Duplicate queries")
    if not set(queries.case_id).issubset(set(frame.case_id)):
        raise ValueError("Unknown query case")
    for case_id, group in frame.groupby("case_id"):
        q = queries.loc[queries.case_id.eq(case_id)]
        if not set(q.strategy).issubset({"common_prefix", *group.strategy}):
            raise ValueError("Unknown query strategy")
        prefix = q.loc[q.strategy.eq("common_prefix")].sort_values("query_idx")
        if prefix.query_idx.tolist() != list(range(5)):
            raise ValueError("Unexpected common-prefix queries")
        if prefix.query_t.tolist() != [0, 16, 32, 48, 64]:
            raise ValueError("Unexpected common-prefix timing")
        if prefix.executed_steps.tolist() != [16, 16, 16, 16, 8]:
            raise ValueError("Unexpected common-prefix horizon")
        for query in q.itertuples():
            seeds = [int(query.rollout_seed) + int(query.query_idx) * 1000 + k for k in range(4)]
            if json.loads(query.query_seed_values) != seeds:
                raise ValueError("Query seeds do not match frozen K4 pairing")
        for row in group.itertuples():
            suffix = q.loc[q.strategy.eq(row.strategy)].sort_values("query_idx")
            if row.counterfactual_reused:
                if not suffix.empty:
                    raise ValueError("Reused outcome unexpectedly has executed queries")
                continue
            if suffix.query_idx.tolist() != list(range(5, 5 + len(suffix))):
                raise ValueError("Nonconsecutive continuation query indices")
            t = 72 + int(row.primitive_steps)
            for query in suffix.itertuples():
                if query.query_t != t or not 1 <= query.executed_steps <= 8:
                    raise ValueError("Query timing/horizon mismatch")
                t += int(query.executed_steps)
            if t != row.terminal_final_t or t > 280:
                raise ValueError("Primitive/query action budget mismatch")
            if row.terminal_continuation_queries != len(suffix):
                raise ValueError("Continuation query count mismatch")


def paired_summary(frame: pd.DataFrame, method: str, cohort: str) -> tuple[dict, pd.DataFrame]:
    b = frame.loc[frame.strategy.eq("baseline_h8")].set_index("case_id")
    m = frame.loc[frame.strategy.eq(method)].set_index("case_id").loc[b.index]
    delta = m.terminal_success.to_numpy() - b.terminal_success.to_numpy()
    rescues, harms = int((delta == 1).sum()), int((delta == -1).sum())
    n = rescues + harms
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(rescues, harms) + 1)) / 2**n)
    # One case per independent init group in the primary and transfer cohorts.
    grouped = pd.DataFrame({"group": b.independent_group, "delta": delta}).groupby("group").delta.mean()
    rng = np.random.default_rng(20260910)
    ci = np.quantile(rng.choice(grouped.to_numpy(), (20000, len(grouped))).mean(axis=1), [.025, .975])
    summary = {
        "cohort": cohort, "method": method, "n": len(b),
        "baseline_successes": int(b.terminal_success.sum()),
        "method_successes": int(m.terminal_success.sum()),
        "delta_pp": float(delta.mean() * 100), "rescues": rescues, "harms": harms,
        "ci_low_pp": float(ci[0] * 100), "ci_high_pp": float(ci[1] * 100),
        "mcnemar_p": p,
    }
    diagnostics = m.loc[delta < 0].copy()
    for c in ("terminal_final_t", "terminal_success", "terminal_episode_target_drop_candidate_t"):
        diagnostics[f"baseline_{c}"] = b.loc[diagnostics.index, c]
    diagnostics["cohort"] = cohort
    return summary, diagnostics.reset_index()


def audit(root: Path, output: Path) -> dict:
    records, harms, checks, provenance, sources = [], [], [], [], []
    calibration_dir = root / "experiments/frozen_models/perception_regrasp_20260904"
    calibration = pd.read_csv(calibration_dir / "calibration_manifest.csv")
    cal_cells = set(zip(calibration.position_level, calibration.task_id))
    seen_groups: set[str] = set()
    for name, split in CAMPAIGNS:
        campaign = root / "experiments/campaigns" / name
        run_dir = campaign / "runs" / split
        paths = sorted(run_dir.glob("*__online_branches.parquet"))
        query_paths = sorted(run_dir.glob("*__query_metrics.parquet"))
        manifest_path = campaign / "manifests" / f"{split}_cases.parquet"
        manifest = pd.read_parquet(manifest_path)
        raw = normalize(pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))
        check = validate_branches(raw, manifest)
        queries = pd.concat([pd.read_parquet(p) for p in query_paths], ignore_index=True)
        validate_queries(raw, queries)
        stored_path = campaign / "analysis" / split / "online_branches.parquet"
        stored = normalize(pd.read_parquet(stored_path))
        keys = ["case_id", "strategy"]
        pd.testing.assert_frame_equal(
            raw.sort_values(keys).reset_index(drop=True),
            stored[raw.columns].sort_values(keys).reset_index(drop=True),
            check_dtype=False,
        )
        groups = set(manifest.independent_group)
        if groups & seen_groups or groups & set(calibration.independent_group):
            raise ValueError("Init-group leakage")
        seen_groups.update(groups)
        check.update(campaign=name, split=split, raw_matches_analysis=True, budgets_and_seeds=True)
        checks.append(check)
        cells = set(zip(manifest.position_level, manifest.task_id))
        provenance.append({"campaign": name, "split": split, "cells": len(cells),
                           "calibration_seen_cells": len(cells & cal_cells), "calibration_init_overlap": 0})
        if "evaluation_cohort" in raw:
            selections = [(cohort, raw.loc[raw.evaluation_cohort.eq(cohort)]) for cohort in ["replication", "novel_cell"]]
            novel = raw.loc[raw.evaluation_cohort.eq("novel_cell")]
            novel_cells = set(zip(novel.position_level, novel.task_id))
            provenance.append({"campaign": name, "split": "novel_cell", "cells": len(novel_cells),
                               "calibration_seen_cells": len(novel_cells & cal_cells), "calibration_init_overlap": 0})
        else:
            selections = [(split, raw)]
        for cohort, subset in selections:
            for method in sorted(set(subset.strategy) - {"baseline_h8"}):
                result, harm = paired_summary(subset, method, f"{name}/{cohort}")
                records.append(result)
                harms.append(harm)
        for path in [*paths, *query_paths, manifest_path, stored_path]:
            sources.append({"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for line in (calibration_dir / "perception_regrasp_artifacts.sha256").read_text().splitlines():
        expected_hash, filename = line.split()
        with (calibration_dir / filename).open("rb") as source:
            digest = hashlib.sha256()
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected_hash:
            raise ValueError(f"Frozen artifact changed: {filename}")
    trigger = json.loads((calibration_dir / "perception_regrasp_trigger_v1.json").read_text())
    if hashlib.sha256((calibration_dir / "heatmap_localization_oof_predictions.csv").read_bytes()).hexdigest() != trigger["source_oof_sha256"]:
        raise ValueError("Trigger calibration source hash mismatch")
    result = {"schema_version": 1, "scope": "CPU audit of saved data, not a new simulator replay",
              "bootstrap": {"repetitions": 20000, "seed": 20260910,
                            "unit": "independent init group", "role": "secondary audit, not replacement of frozen CI"},
              "checks": checks, "provenance": provenance, "comparisons": records, "sources": sources}
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(records).to_csv(output / "comparisons.csv", index=False)
    pd.concat(harms, ignore_index=True).to_csv(output / "harms.csv", index=False)
    print(pd.DataFrame(records).to_string(index=False))
    print(f"PASS: {sum(c['cases'] for c in checks)} cases / {sum(c['branches'] for c in checks)} branches; {output}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/campaigns/p3c_audit_20260910")
    args = parser.parse_args()
    audit(args.root.resolve(), args.output_dir.resolve())

#!/usr/bin/env python3
"""Compare consensus selectors on already-open P4b terminal candidate pools."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_geometry():
    path = ROOT / "cosmos-policy/cosmos_policy/experiments/robot/libero/trajectory_consensus.py"
    spec = importlib.util.spec_from_file_location("trajectory_consensus", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def screen(source: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    module = load_geometry()
    data = pd.read_parquet(source)
    pools = []
    for snapshot, rows in data.groupby("snapshot_group", sort=True):
        rows = rows.sort_values("candidate_idx")
        if len(rows) != 4 or rows.candidate_idx.tolist() != list(range(4)):
            raise ValueError("Incomplete K4 terminal pool")
        if not rows.terminal_available.all():
            raise ValueError("Missing terminal outcome")
        # Previously exposed holdout is development data for this new method.
        if rows.main_open_replay_state_max_abs.max() > 1e-9:
            continue
        path = ROOT / rows.sidecar_path.iloc[0]
        with np.load(path, allow_pickle=False) as saved:
            actions, values = saved["candidate_actions"], saved["candidate_values"]
        np.testing.assert_allclose(values, rows.candidate_value, rtol=1e-5, atol=1e-6)
        pools.append((snapshot, rows, actions, values))
    settings = [dict(strategy=s, density_weight=1.0, value_margin=.5, minimum_density_gain=.1)
                for s in ("trajectory_medoid", "trajectory_density")]
    for strategy, weight, margin in itertools.product(
        ("trajectory_value_density", "trajectory_value_density_aligned"), (.25, .5, 1., 2., 4.), (.25, .5, 1.)
    ):
        settings.append(dict(strategy=strategy, density_weight=weight, value_margin=margin, minimum_density_gain=.1))
    results, candidate_rows = [], []
    for index, setting in enumerate(settings):
        decisions = []
        for snapshot, rows, actions, values in pools:
            selected, diagnostic = module.select_trajectory_consensus(actions, values, **setting)
            baseline = int(np.argmax(values))
            success = rows.terminal_success.to_numpy(dtype=bool)
            drops = rows.terminal_target_drop_candidate.to_numpy(dtype=bool)
            decision = dict(
                setting_id=index, snapshot_group=snapshot, factor=rows.factor.iloc[0],
                task_id=int(rows.task_id.iloc[0]), init_state_id=int(rows.init_state_id.iloc[0]),
                baseline_success=int(success[baseline]), selected_success=int(success[selected]),
                delta=int(success[selected])-int(success[baseline]),
                drop_delta=int(drops[selected])-int(drops[baseline]), switched=selected != baseline,
                selected_idx=selected, baseline_idx=baseline,
            )
            decisions.append(decision)
        df = pd.DataFrame(decisions)
        by_factor = df.groupby("factor")[["delta", "drop_delta"]].mean()
        record = dict(setting_id=index, **setting, snapshots=len(df),
                      macro_delta=float(by_factor.delta.mean()),
                      macro_drop_delta=float(by_factor.drop_delta.mean()),
                      worst_factor_delta=float(by_factor.delta.min()),
                      rescues=int(df.delta.eq(1).sum()), harms=int(df.delta.eq(-1).sum()),
                      switch_rate=float(df.switched.mean()))
        record["selection_objective"] = record["macro_delta"] - max(0., record["macro_drop_delta"])
        results.append(record)
        candidate_rows.extend(decisions)
    grid = pd.DataFrame(results).sort_values(
        ["selection_objective", "worst_factor_delta", "harms", "density_weight", "setting_id"],
        ascending=[False, False, True, True, True],
    )
    finalists = []
    for strategy in ("trajectory_value_density", "trajectory_value_density_aligned"):
        best = grid[grid.strategy.eq(strategy)].iloc[0]
        finalists.append({key: best[key] for key in settings[0]} | {"setting_id": int(best.setting_id)})
    payload = dict(
        source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        label="already_open_P4b_development_not_confirmatory", strict_snapshots=len(pools),
        settings_evaluated=len(settings), finalists=finalists,
    )
    grid.to_csv(output / "offline_grid.csv", index=False)
    pd.DataFrame(candidate_rows).to_parquet(output / "offline_decisions.parquet", index=False)
    (output / "shortlist.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(grid.head(10).to_string(index=False))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "experiments/campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/candidate_scores.parquet")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    screen(args.source, args.output)

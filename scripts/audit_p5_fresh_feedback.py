#!/usr/bin/env python3
"""Audit fresh-observation feedback without changing frozen P5 collection/results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.review_p5_repeat_feedback import ROOT, audit
    from scripts.analyze_p5_repeat_feedback import paired_effect
    from scripts.p5_repeat_feedback import atomic_json
except ModuleNotFoundError:
    from review_p5_repeat_feedback import ROOT, audit
    from analyze_p5_repeat_feedback import paired_effect
    from p5_repeat_feedback import atomic_json


MODES = ("open16", "stale8", "fresh8")


def boundary_metrics(actions, reference):
    actions = np.asarray(actions, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if actions.ndim != 2 or reference.ndim != 2 or actions.shape[1] != 7 or reference.shape[1] != 7:
        raise ValueError("Expected step x 7 action arrays")
    if min(len(actions), len(reference)) < 16 or not np.isfinite(actions).all() or not np.isfinite(reference).all():
        raise ValueError("Need finite complete first 16 executed actions")
    # OSC clips translation inputs; PandaGripper responds to sign, not float equality.
    xyz, old_xyz = np.clip(actions[:, :3], -1, 1), np.clip(reference[:, :3], -1, 1)
    gripper, old_gripper = np.sign(actions[:, 6]), np.sign(reference[:, 6])
    return dict(
        boundary_xyz_l2=float(np.linalg.norm(xyz[8] - xyz[7])),
        replacement_xyz_l2_mean=float(np.linalg.norm(xyz[8:16] - old_xyz[8:16], axis=1).mean()),
        gripper_sign_mismatch_fraction=float(np.mean(gripper[8:16] != old_gripper[8:16])),
        boundary_gripper_sign_change=bool(gripper[8] != gripper[7]),
        boundary_gripper_reopens=bool(gripper[7] > 0 and gripper[8] < 0),
    )


def storyboard(directory, output, pool):
    import imageio.v2 as imageio
    import matplotlib.pyplot as plt

    offsets = [7, 8, 12, 16, 32]
    fig, axes = plt.subplots(3, len(offsets), figsize=(17, 6.3), layout="constrained")
    for row, mode in enumerate(MODES):
        stem = directory / "runs" / pool["id"] / f"r0_c{pool['selected']}_{mode}"
        outcome = json.loads(stem.with_suffix(".json").read_text())
        with imageio.get_reader(str(stem.with_suffix(".mp4"))) as reader:
            for col, offset in enumerate(offsets):
                axes[row, col].imshow(reader.get_data(offset))
                axes[row, col].set_title(f"t={pool['t'] + offset}", fontsize=10)
                axes[row, col].set_xticks([])
                axes[row, col].set_yticks([])
                if col == 0:
                    axes[row, col].set_ylabel(f"{mode}\nsuccess={outcome['terminal_success']}")
    fig.suptitle(f"{pool['id']} / {pool['case_id']} / task{pool['task_id']} init{pool['init_state_id']}: "
                 "requery after column 2; both real cameras; repeat 0", fontsize=12)
    fig.savefig(output / f"{pool['id']}_storyboard.png", dpi=140)
    plt.close(fig)


def analyze(directory, output, make_storyboards=False):
    config = json.loads((directory / "config.json").read_text())
    data, integrity, _videos = audit(directory, config, decode_videos=False)
    selected = data.loc[data.selected]
    pairs = selected.pivot(index=["pool_id", "repeat"], columns="mode", values="terminal_success")
    rows = []
    for pool in config["pools"]:
        for repeat in range(3):
            base = directory / "runs" / pool["id"]
            with np.load(base / f"r{repeat}_c{pool['selected']}_open16.npz", allow_pickle=False) as saved:
                old_actions = saved["executed_actions"].copy()
            outcomes = pairs.loc[(pool["id"], repeat)]
            effect = int(outcomes.fresh8) - int(outcomes.open16)
            for mode in MODES:
                record = json.loads((base / f"r{repeat}_c{pool['selected']}_{mode}.json").read_text())
                with np.load(base / f"r{repeat}_c{pool['selected']}_{mode}.npz", allow_pickle=False) as saved:
                    actions = saved["executed_actions"]
                    metrics = boundary_metrics(actions, old_actions)
                rows.append(dict(pool_id=pool["id"], repeat=repeat, case_id=pool["case_id"],
                    task_id=pool["task_id"], init_state_id=pool["init_state_id"], query_idx=pool["query_idx"],
                    snapshot_t=pool["t"], requery_t=pool["t"] + 8, mode=mode,
                    terminal_success=record["terminal_success"], terminal_final_t=record["terminal_final_t"],
                    failure_type=record["terminal_failure_type"],
                    first_lift_t=record["terminal_episode_episode_time_to_first_target_lift"],
                    drop_t=record["terminal_episode_target_drop_candidate_t"],
                    fresh_vs_open_effect=effect, **metrics))
    metrics = pd.DataFrame(rows)
    summary_metrics = metrics.groupby(["query_idx", "mode"]).agg(
        branches=("terminal_success", "size"), successes=("terminal_success", "sum"),
        boundary_xyz_mean=("boundary_xyz_l2", "mean"), boundary_xyz_median=("boundary_xyz_l2", "median"),
        replacement_xyz_mean=("replacement_xyz_l2_mean", "mean"),
        gripper_sign_mismatch=("gripper_sign_mismatch_fraction", "mean"),
        immediate_gripper_reopens=("boundary_gripper_reopens", "sum"),
    ).reset_index()
    harms = metrics.loc[metrics.fresh_vs_open_effect.eq(-1) & metrics["mode"].eq("fresh8")]
    render_records = []
    for pool in config["pools"]:
        replay = json.loads((directory / "runs" / pool["id"] / "replay_audit.json").read_text())
        for entry in replay["render_diagnostics"]:
            if entry["candidate_idx"] == 0:
                render_records.append(dict(pool_id=pool["id"], **entry,
                                           proprio_max=max(replay["proprio_diagnostics"])))
    render = pd.DataFrame(render_records)
    effects = [dict(query_idx=query, **paired_effect(group, "fresh8", ref))
               for query, group in selected.groupby("query_idx") for ref in ["open16", "stale8"]]
    output.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output / "boundary_metrics.csv", index=False)
    summary_metrics.to_csv(output / "boundary_summary.csv", index=False)
    render.to_csv(output / "initial_render_diagnostics.csv", index=False)
    metrics.loc[metrics.fresh_vs_open_effect.ne(0)].to_csv(output / "discordant_branches.csv", index=False)
    result = dict(
        scope="CPU audit; no new model inference or simulator execution", integrity=integrity,
        primary_effects=[paired_effect(selected, "fresh8", ref) for ref in ["stale8", "open16"]],
        query_effects_exploratory=effects, boundary_summary=summary_metrics.to_dict("records"),
        fresh_harm_failure_types=harms.failure_type.value_counts().to_dict(),
        immediate_reopens_in_fresh_harms=int(harms.boundary_gripper_reopens.sum()),
        q3_harms_from_pool33=int((harms.query_idx.eq(3) & harms.pool_id.eq("pool_33")).sum()),
        q3_harms_on_task9=int((harms.query_idx.eq(3) & harms.task_id.eq(9)).sum()),
        initial_render_mse_by_camera=render.groupby("camera").mse.agg(["median", "max"]).to_dict("index"),
        initial_proprio_max_abs=float(render.proprio_max.max()),
        limitations=["K8-selected initial chunk versus K1 replacement, not a matched-K feedback comparison",
                     "Stale tail is generated jointly with an unexecuted alternative prefix",
                     "Requery input RGB/proprio hashes and replacement values were not archived",
                     "Control-flow routing tested with timestamped test doubles, not actual GPU inference",
                     "Boundary changes are post-hoc descriptions, not validated fail predictors",
                     "No immediate drop event implies neither safety nor impossibility of later harm"],
    )
    atomic_json(output / "summary.json", result)
    if make_storyboards:
        import matplotlib
        matplotlib.use("Agg")
        for pool_id in ("pool_08", "pool_33"):
            storyboard(directory, output, next(p for p in config["pools"] if p["id"] == pool_id))
    print(summary_metrics.to_string(index=False))
    print("Fresh harms:", result["fresh_harm_failure_types"])
    print("Saved:", output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=ROOT / "experiments/campaigns/p5_repeat_feedback_20260910")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/campaigns/p5_fresh_audit_20260910")
    parser.add_argument("--storyboards", action="store_true")
    args = parser.parse_args()
    analyze(args.campaign.resolve(), args.output_dir.resolve(), args.storyboards)

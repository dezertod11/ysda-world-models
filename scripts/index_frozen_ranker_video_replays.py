#!/usr/bin/env python3
"""Create a portable side-by-side HTML index for paired replay videos."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def _safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("_")


def episode_videos(campaign_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "video_path" not in trace:
            continue
        first = trace.sort_values("query_idx").iloc[0]
        video = Path(str(first["video_path"]))
        rows.append(
            {
                "case_id": str(first.get("case_id", "")),
                "factor": str(first.get("planning_frozen_ranker_factor", "")),
                "suite": str(first["suite"]),
                "task_id": int(first["task_id"]),
                "init_state_id": int(first["init_state_id"]),
                "rollout_seed": int(first["rollout_seed"]),
                "planning_strategy": str(first["planning_strategy"]),
                "success": bool(first["success"]),
                "final_t": int(first["final_t"]),
                "video_num_frames": int(
                    first.get("video_num_frames", first["final_t"])
                ),
                "video_expected_frames": int(
                    first.get("video_expected_frames", first["final_t"])
                ),
                "video_path": str(video),
                "video_exists": video.is_file(),
            }
        )
    if not rows:
        raise ValueError(f"No replay videos found under {campaign_dir}")
    return pd.DataFrame(rows)


def query_zero_rows(campaign_dir: Path) -> pd.DataFrame:
    columns = [
        "factor",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "planning_strategy",
        "success",
        "final_t",
        "selected_sample_idx",
        "candidate_values_json",
        "candidate_frozen_ranker_scores_json",
        "candidate_first_actions_json",
    ]
    frames = []
    for path in sorted((campaign_dir / "runs").glob("*__query_traces.parquet")):
        trace = pd.read_parquet(path)
        if trace.empty or "query_idx" not in trace:
            continue
        query_zero = trace.loc[trace["query_idx"].eq(0)].copy()
        if "factor" not in query_zero:
            query_zero["factor"] = query_zero.get(
                "planning_frozen_ranker_factor", ""
            )
        if set(columns).issubset(query_zero):
            frames.append(query_zero[columns])
    if not frames:
        raise ValueError(f"No complete query-zero rows under {campaign_dir}")
    rows = pd.concat(frames, ignore_index=True)
    keys = [
        "factor",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "planning_strategy",
    ]
    duplicated = rows.duplicated(keys, keep=False)
    if duplicated.any():
        raise ValueError(f"Duplicate query-zero strategy rows under {campaign_dir}")
    return rows


def replay_fidelity(primary_campaign_dir: Path, replay_campaign_dir: Path) -> pd.DataFrame:
    keys = [
        "factor",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "planning_strategy",
    ]
    primary = query_zero_rows(primary_campaign_dir)
    replay = query_zero_rows(replay_campaign_dir)
    fidelity = replay.merge(
        primary,
        on=keys,
        how="left",
        validate="one_to_one",
        suffixes=("__replay", "__primary"),
    )
    if fidelity["success__primary"].isna().any():
        raise ValueError("At least one replay has no matching primary query-zero row")

    def max_abs_difference(row: pd.Series, column: str) -> float:
        replay_array = np.asarray(json.loads(row[f"{column}__replay"]), dtype=float)
        primary_array = np.asarray(json.loads(row[f"{column}__primary"]), dtype=float)
        if replay_array.shape != primary_array.shape:
            return float("inf")
        if not np.array_equal(np.isnan(replay_array), np.isnan(primary_array)):
            return float("inf")
        finite = np.isfinite(replay_array) & np.isfinite(primary_array)
        if not finite.any():
            return 0.0
        return float(np.max(np.abs(replay_array[finite] - primary_array[finite])))

    fidelity["outcome_reproduced"] = (
        fidelity["success__replay"].astype(bool)
        == fidelity["success__primary"].astype(bool)
    )
    fidelity["query0_selected_index_reproduced"] = (
        fidelity["selected_sample_idx__replay"].astype(int)
        == fidelity["selected_sample_idx__primary"].astype(int)
    )
    for column, label in (
        ("candidate_values_json", "query0_value_max_abs_diff"),
        ("candidate_frozen_ranker_scores_json", "query0_score_max_abs_diff"),
        ("candidate_first_actions_json", "query0_first_action_max_abs_diff"),
    ):
        fidelity[label] = fidelity.apply(
            lambda row, source=column: max_abs_difference(row, source), axis=1
        )
    return fidelity


def write_index(
    campaign_dir: Path,
    output_dir: Path,
    *,
    selection_csv: Path | None = None,
    primary_campaign_dir: Path | None = None,
) -> pd.DataFrame:
    episodes = episode_videos(campaign_dir)
    keys = ["case_id", "factor", "suite", "task_id", "init_state_id", "rollout_seed"]
    duplicated = episodes.duplicated([*keys, "planning_strategy"], keep=False)
    if duplicated.any():
        raise ValueError("Duplicate strategy videos were found for a replay pair")
    paths = episodes.pivot(index=keys, columns="planning_strategy", values="video_path")
    success = episodes.pivot(index=keys, columns="planning_strategy", values="success")
    final_t = episodes.pivot(index=keys, columns="planning_strategy", values="final_t")
    frame_count = episodes.pivot(
        index=keys, columns="planning_strategy", values="video_num_frames"
    )
    expected_frames = episodes.pivot(
        index=keys, columns="planning_strategy", values="video_expected_frames"
    )
    pairs = paths.reset_index()
    for strategy in ("max_value", "frozen_factor_ridge"):
        if strategy not in paths:
            pairs[f"{strategy}_video"] = ""
            pairs[f"{strategy}_success"] = False
            pairs[f"{strategy}_final_t"] = -1
            pairs[f"{strategy}_video_num_frames"] = -1
            pairs[f"{strategy}_video_expected_frames"] = -1
        else:
            pairs[f"{strategy}_video"] = paths[strategy].to_numpy()
            pairs[f"{strategy}_success"] = success[strategy].to_numpy()
            pairs[f"{strategy}_final_t"] = final_t[strategy].to_numpy()
            pairs[f"{strategy}_video_num_frames"] = frame_count[strategy].to_numpy()
            pairs[f"{strategy}_video_expected_frames"] = expected_frames[
                strategy
            ].to_numpy()
    source_keys = ["factor", "suite", "task_id", "init_state_id", "rollout_seed"]
    if selection_csv is not None:
        selection = pd.read_csv(selection_csv)
        selected_columns = [*source_keys, "case_id", "discordance"]
        selection = selection[selected_columns].rename(
            columns={"case_id": "primary_case_id", "discordance": "primary_discordance"}
        )
        pairs = pairs.merge(selection, on=source_keys, how="left", validate="one_to_one")
    if primary_campaign_dir is not None:
        fidelity = replay_fidelity(primary_campaign_dir, campaign_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fidelity.to_csv(output_dir / "replay_fidelity.csv", index=False)
        for strategy in ("max_value", "frozen_factor_ridge"):
            scoped = fidelity.loc[fidelity["planning_strategy"].eq(strategy)].copy()
            scoped = scoped.rename(
                columns={
                    "success__primary": f"{strategy}_primary_success",
                    "final_t__primary": f"{strategy}_primary_final_t",
                    "outcome_reproduced": f"{strategy}_outcome_reproduced",
                    "query0_selected_index_reproduced": f"{strategy}_query0_selected_index_reproduced",
                    "query0_value_max_abs_diff": f"{strategy}_query0_value_max_abs_diff",
                    "query0_score_max_abs_diff": f"{strategy}_query0_score_max_abs_diff",
                    "query0_first_action_max_abs_diff": f"{strategy}_query0_first_action_max_abs_diff",
                }
            )
            keep = [
                *source_keys,
                f"{strategy}_primary_success",
                f"{strategy}_primary_final_t",
                f"{strategy}_outcome_reproduced",
                f"{strategy}_query0_selected_index_reproduced",
                f"{strategy}_query0_value_max_abs_diff",
                f"{strategy}_query0_score_max_abs_diff",
                f"{strategy}_query0_first_action_max_abs_diff",
            ]
            pairs = pairs.merge(
                scoped[keep], on=source_keys, how="left", validate="one_to_one"
            )
        pairs["paired_outcome_reproduced"] = (
            pairs["max_value_outcome_reproduced"].astype(bool)
            & pairs["frozen_factor_ridge_outcome_reproduced"].astype(bool)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    portable_video_dir = output_dir / "videos"
    portable_video_dir.mkdir(parents=True, exist_ok=True)
    for index, row in pairs.iterrows():
        for strategy in ("max_value", "frozen_factor_ridge"):
            source = Path(str(row[f"{strategy}_video"]))
            filename = (
                f"{_safe_name(row['factor'])}__task{int(row['task_id'])}"
                f"__init{int(row['init_state_id'])}__seed{int(row['rollout_seed'])}"
                f"__{strategy}__success{bool(row[f'{strategy}_success'])}.mp4"
            )
            destination = portable_video_dir / filename
            if source.is_file() and source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            elif not destination.is_file():
                pairs.at[index, f"{strategy}_video"] = ""
                continue
            pairs.at[index, f"{strategy}_video"] = str(Path("videos") / filename)
    pairs = pairs.drop(
        columns=[
            strategy
            for strategy in ("max_value", "frozen_factor_ridge")
            if strategy in pairs
        ]
    )
    pairs.to_csv(output_dir / "video_pairs.csv", index=False)

    blocks = []
    for _, row in pairs.iterrows():
        videos = []
        for strategy, title in (
            ("max_value", "maxV-H16"),
            ("frozen_factor_ridge", "frozen-ranker-H16"),
        ):
            source_value = str(row[f"{strategy}_video"] or "")
            source = Path(source_value) if source_value else None
            relative = (
                source_value
                if source is not None and not source.is_absolute()
                else os.path.relpath(source, output_dir)
                if source is not None
                else ""
            )
            label = (
                f"{title}: replay success={bool(row[f'{strategy}_success'])}, "
                f"t={int(row[f'{strategy}_final_t'])}, "
                f"frames={int(row[f'{strategy}_video_num_frames'])}/"
                f"{int(row[f'{strategy}_video_expected_frames'])}"
            )
            if f"{strategy}_primary_success" in pairs:
                label += (
                    f"; primary success={bool(row[f'{strategy}_primary_success'])}; "
                    f"reproduced={bool(row[f'{strategy}_outcome_reproduced'])}"
                )
            media = (
                "<video controls preload='metadata' src='"
                + html.escape(relative)
                + "'></video>"
                if relative
                else "<p>Video missing</p>"
            )
            videos.append(
                "<section><h3>" + html.escape(label) + "</h3>" + media + "</section>"
            )
        heading = (
            f"{row['factor']} | task={int(row['task_id'])} | "
            f"init={int(row['init_state_id'])} | seed={int(row['rollout_seed'])}"
        )
        if "primary_discordance" in pairs:
            heading += f" | primary={row['primary_discordance']}"
        if "paired_outcome_reproduced" in pairs:
            heading += f" | pair reproduced={bool(row['paired_outcome_reproduced'])}"
        blocks.append(
            "<article><h2>"
            + html.escape(heading)
            + "</h2><div class='pair'>"
            + "".join(videos)
            + "</div></article>"
        )
    document = """<!doctype html>
<html><head><meta charset="utf-8"><title>Frozen H16 replay pairs</title>
<style>
body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f5;color:#171717}
article{border-top:1px solid #bbb;padding:18px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}
video{width:100%;background:#000}h2{font-size:18px}h3{font-size:15px;font-weight:600}
@media(max-width:900px){.pair{grid-template-columns:1fr}}
</style></head><body><h1>Frozen ranker discordant replays</h1>
<p>These are post-hoc inference replays, not frames from the primary run. Each
label reports both the primary and replay outcome; numerical GPU differences may
change a near-boundary trajectory.</p>"""
    document += "".join(blocks) + "</body></html>\n"
    (output_dir / "VIDEO_INDEX.html").write_text(document, encoding="utf-8")
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--selection-csv", type=Path)
    parser.add_argument("--primary-campaign-dir", type=Path)
    args = parser.parse_args()
    pairs = write_index(
        args.campaign_dir.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        selection_csv=(
            args.selection_csv.expanduser().resolve() if args.selection_csv else None
        ),
        primary_campaign_dir=(
            args.primary_campaign_dir.expanduser().resolve()
            if args.primary_campaign_dir
            else None
        ),
    )
    print(f"video_pairs={len(pairs)} output={args.output_dir.expanduser().resolve()}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate temporal-overlap CSV/NPZ alignment for a LIBERO campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def locate_sidecar(raw_path: str, campaign_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    matches = list((campaign_dir / "temporal_overlap").rglob(path.name))
    if len(matches) != 1:
        raise FileNotFoundError(f"Cannot uniquely locate overlap sidecar {raw_path!r}")
    return matches[0]


def validate_sidecar(trace: pd.DataFrame, sidecar_path: Path) -> dict[str, int | str]:
    episode = trace.sort_values("query_idx").reset_index(drop=True)
    with np.load(sidecar_path, allow_pickle=False) as data:
        available_keys = set(data.files)
        actions = data["candidate_actions_raw"]
        selected = data["selected_sample_idx"]
        query_t = data["query_t"]
        executed_steps = data["executed_steps"]
        candidate_seeds = data["candidate_seeds"]
        actual_actions = data["actual_executed_actions"]
        seed_mode = str(data["seed_mode"].item())
        schema_version = int(data["schema_version"].item())
        sidecar_description = (
            str(data["task_description"].item())
            if "task_description" in available_keys
            else ""
        )
        safety_arrays = {
            key: np.asarray(data[key])
            for key in (
                "safety_t",
                "safety_goal_predicates_satisfied",
                "safety_object_names",
                "safety_object_positions",
                "safety_eef_positions",
                "safety_target_names",
                "safety_target_goal_satisfied",
                "safety_target_released",
            )
            if key in available_keys
        }

    if actions.ndim != 4 or actions.shape[0] != len(episode):
        raise AssertionError(
            f"Unexpected candidate action shape {actions.shape} in {sidecar_path}"
        )
    if actions.shape[2:] != (16, 7):
        raise AssertionError(
            f"Expected [Q,B,16,7], got {actions.shape} in {sidecar_path}"
        )
    if not np.array_equal(query_t, episode["t"].to_numpy(dtype=np.int64)):
        raise AssertionError(
            f"query_t differs between trace and sidecar: {sidecar_path}"
        )
    if not np.array_equal(
        executed_steps, episode["executed_steps"].to_numpy(dtype=np.int64)
    ):
        raise AssertionError(
            f"executed_steps differs between trace and sidecar: {sidecar_path}"
        )
    if len(actual_actions) != int(executed_steps.sum()):
        raise AssertionError(f"Executed action count mismatch in {sidecar_path}")
    if sidecar_description and sidecar_description != str(episode["task_description"].iloc[0]):
        raise AssertionError(f"Task instruction differs between trace and sidecar: {sidecar_path}")
    if schema_version >= 2:
        required_safety = {
            "safety_t",
            "safety_goal_predicates_satisfied",
            "safety_object_names",
            "safety_object_positions",
            "safety_eef_positions",
            "safety_target_names",
            "safety_target_goal_satisfied",
            "safety_target_released",
        }
        missing_safety = sorted(required_safety - set(safety_arrays))
        if missing_safety:
            raise AssertionError(
                f"Schema v{schema_version} sidecar lacks safety arrays {missing_safety}: {sidecar_path}"
            )
        safety_steps = len(safety_arrays["safety_t"])
        if safety_steps != len(actual_actions):
            raise AssertionError(f"Safety trace/action length mismatch in {sidecar_path}")
        if safety_arrays["safety_object_positions"].shape[:2] != (
            safety_steps,
            len(safety_arrays["safety_object_names"]),
        ):
            raise AssertionError(f"Safety object pose shape mismatch in {sidecar_path}")
        if safety_arrays["safety_target_goal_satisfied"].shape[:2] != (
            safety_steps,
            len(safety_arrays["safety_target_names"]),
        ):
            raise AssertionError(f"Safety target predicate shape mismatch in {sidecar_path}")
    else:
        safety_steps = 0
    if seed_mode == "coupled" and len(candidate_seeds) > 1:
        if not np.all(candidate_seeds == candidate_seeds[0]):
            raise AssertionError(
                f"Coupled seeds changed across queries in {sidecar_path}"
            )

    checked_overlaps = 0
    for query_position in range(1, len(episode)):
        previous_steps = int(executed_steps[query_position - 1])
        overlap_length = min(8, 16 - previous_steps)
        row = episode.iloc[query_position]
        if overlap_length <= 0:
            if bool(row["overlap_valid"]):
                raise AssertionError(
                    f"Invalid overlap marked valid at query {query_position}"
                )
            continue
        old = actions[
            query_position - 1,
            int(selected[query_position - 1]),
            previous_steps : previous_steps + overlap_length,
            :6,
        ]
        new = actions[
            query_position,
            int(selected[query_position]),
            :overlap_length,
            :6,
        ]
        expected_rmse = float(np.sqrt(np.mean(np.square(old - new))))
        if not np.isclose(
            expected_rmse, float(row["overlap_selected_rmse"]), atol=1e-7
        ):
            raise AssertionError(
                f"Overlap RMSE mismatch at query {query_position} in {sidecar_path}"
            )
        if int(row["overlap_length"]) != overlap_length:
            raise AssertionError(f"Overlap length mismatch at query {query_position}")
        checked_overlaps += 1

    event_t = int(episode["critical_event_t"].iloc[0])
    expected_pre_event = (
        (episode["t"] < event_t)
        if event_t >= 0
        else pd.Series(True, index=episode.index)
    )
    if not np.array_equal(
        expected_pre_event.to_numpy(dtype=bool),
        episode["pre_critical_event_query"].to_numpy(dtype=bool),
    ):
        raise AssertionError(f"Pre-event labels are misaligned in {sidecar_path}")

    return {
        "sidecar": str(sidecar_path),
        "queries": len(episode),
        "samples": actions.shape[1],
        "checked_overlaps": checked_overlaps,
        "seed_mode": seed_mode,
        "schema_version": schema_version,
        "safety_steps": safety_steps,
    }


def validate_campaign(campaign_dir: Path) -> dict[str, object]:
    trace_paths = sorted((campaign_dir / "runs").glob("*__query_traces.parquet"))
    if not trace_paths:
        raise FileNotFoundError(f"No traces found under {campaign_dir / 'runs'}")
    traces = pd.concat(
        [pd.read_parquet(path).assign(source_trace=str(path)) for path in trace_paths],
        ignore_index=True,
        sort=False,
    )
    required = {
        "temporal_overlap_sidecar",
        "overlap_valid",
        "overlap_selected_rmse",
        "critical_event_t",
        "pre_critical_event_query",
    }
    missing = sorted(required - set(traces.columns))
    if missing:
        raise AssertionError(f"Missing trace columns: {missing}")

    episode_keys = [
        "source_trace",
        "suite",
        "task_id",
        "init_state_id",
        "pair_id",
        "rollout_id",
    ]
    results = []
    for _keys, episode in traces.groupby(episode_keys, dropna=False, sort=False):
        raw_sidecar = str(episode["temporal_overlap_sidecar"].iloc[0])
        results.append(
            validate_sidecar(episode, locate_sidecar(raw_sidecar, campaign_dir))
        )

    return {
        "campaign_dir": str(campaign_dir),
        "trace_files": len(trace_paths),
        "episodes": len(results),
        "queries": int(sum(int(result["queries"]) for result in results)),
        "checked_overlaps": int(
            sum(int(result["checked_overlaps"]) for result in results)
        ),
        "seed_modes": sorted({str(result["seed_mode"]) for result in results}),
        "valid": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()
    summary = validate_campaign(args.campaign_dir)
    rendered = json.dumps(summary, indent=2)
    print(rendered)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Relabel saved exact-state branch endpoints with dense LIBERO geometry."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from libero.libero import benchmark

from cosmos_policy.experiments.robot.libero.libero_utils import get_libero_env

from counterfactual_feedback_utils import dense_branch_utility_v2
from dense_consequence_utils import (
    capture_goal_geometry,
    geometry_delta_metrics,
    observation_from_libero_proprio,
    restore_flat_sim_state,
)
from libero_runtime_snapshot import restore_libero_runtime_state, runtime_snapshot_from_arrays


def _sidecar_path(raw_path: Any, source_dir: Path, run_name: str, snapshot_id: str) -> Path:
    path = Path(str(raw_path))
    if path.is_file():
        return path
    fallback = source_dir / f"{run_name}__snapshots" / f"{snapshot_id}.npz"
    if not fallback.is_file():
        raise FileNotFoundError(f"Missing sidecar for {snapshot_id}: {fallback}")
    return fallback


def _prefixed_metrics(row: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {
        key.removeprefix(prefix): value
        for key, value in row.items()
        if key.startswith(prefix)
    }


def relabel(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    source_dir = args.source_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    feedback = pd.read_parquet(source_dir / f"{args.run_name}__feedback_pairs.parquet")
    candidates = pd.read_parquet(source_dir / f"{args.run_name}__candidate_outcomes.parquet")
    candidate_groups = {
        snapshot_id: group.sort_values("candidate_idx")
        for snapshot_id, group in candidates.groupby("snapshot_id", sort=False)
    }

    feedback_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    env_cache: dict[tuple[str, int], Any] = {}
    try:
        for feedback_record in feedback.to_dict(orient="records"):
            snapshot_id = str(feedback_record["snapshot_id"])
            suite_name = str(feedback_record["suite"])
            task_id = int(feedback_record["task_id"])
            cache_key = (suite_name, task_id)
            if cache_key not in env_cache:
                task_suite = benchmark.get_benchmark_dict()[suite_name](-1)
                task = task_suite.get_task(task_id)
                env_cache[cache_key], _ = get_libero_env(task, "cosmos", resolution=256)
            env = env_cache[cache_key]
            sidecar = _sidecar_path(
                feedback_record.get("sidecar_path"), source_dir, args.run_name, snapshot_id
            )
            with np.load(sidecar, allow_pickle=False) as payload:
                restore_libero_runtime_state(
                    env,
                    runtime_snapshot_from_arrays(payload),
                    reset_env=False,
                    update_observables=False,
                )
                start_obs = observation_from_libero_proprio(payload["current_proprio"])
                start_geometry = capture_goal_geometry(env, start_obs)
                group = candidate_groups[snapshot_id]
                endpoint_states = np.asarray(payload["candidate_endpoint_states"])
                endpoint_proprio = np.asarray(payload["candidate_endpoint_proprio"])
                has_h32 = "candidate_h32_endpoint_states" in payload
                h32_states = (
                    np.asarray(payload["candidate_h32_endpoint_states"])
                    if has_h32
                    else None
                )
                h32_proprio = (
                    np.asarray(payload["candidate_h32_endpoint_proprio"])
                    if has_h32
                    else None
                )
                if len(group) != len(endpoint_states) or len(group) != len(endpoint_proprio):
                    raise ValueError(
                        f"{snapshot_id}: {len(group)} candidate rows but "
                        f"{len(endpoint_states)} endpoint states and "
                        f"{len(endpoint_proprio)} endpoint proprio vectors"
                    )
                if has_h32 and (
                    len(group) != len(h32_states) or len(group) != len(h32_proprio)
                ):
                    raise ValueError(f"{snapshot_id}: inconsistent H32 endpoint arrays")
                dense_by_index: dict[int, dict[str, float]] = {}
                h32_dense_by_index: dict[int, dict[str, float]] = {}
                for offset, (candidate_record, endpoint_state, candidate_proprio) in enumerate(
                    zip(group.to_dict(orient="records"), endpoint_states, endpoint_proprio)
                ):
                    restore_flat_sim_state(env, endpoint_state, update_observables=False)
                    endpoint_obs = observation_from_libero_proprio(candidate_proprio)
                    dense = geometry_delta_metrics(
                        start_geometry, capture_goal_geometry(env, endpoint_obs)
                    )
                    phase = str(candidate_record.get("phase_at_snapshot", "approach"))
                    enriched = {**candidate_record, **dense}
                    enriched["dense_utility_v2"] = dense_branch_utility_v2(enriched, phase)
                    candidate_idx = int(candidate_record["candidate_idx"])
                    dense_by_index[candidate_idx] = dense
                    if has_h32:
                        restore_flat_sim_state(
                            env, h32_states[offset], update_observables=False
                        )
                        h32_observation = observation_from_libero_proprio(
                            h32_proprio[offset]
                        )
                        h32_dense = geometry_delta_metrics(
                            start_geometry,
                            capture_goal_geometry(env, h32_observation),
                        )
                        h32_metrics = {
                            **_prefixed_metrics(candidate_record, "h32_"),
                            **h32_dense,
                        }
                        enriched.update(
                            {f"h32_{key}": value for key, value in h32_dense.items()}
                        )
                        enriched["h32_dense_utility_v2"] = dense_branch_utility_v2(
                            h32_metrics, phase
                        )
                        h32_dense_by_index[candidate_idx] = h32_dense
                    candidate_rows.append(enriched)

                restore_flat_sim_state(
                    env, payload["feedback_endpoint_state"], update_observables=False
                )
                feedback_obs = observation_from_libero_proprio(
                    payload["feedback_endpoint_proprio"]
                )
                feedback_dense = geometry_delta_metrics(
                    start_geometry, capture_goal_geometry(env, feedback_obs)
                )
                selected_idx = int(feedback_record["selected_candidate_idx"])
                open_dense = dense_by_index[selected_idx]
                open_metrics = {**_prefixed_metrics(feedback_record, "open_"), **open_dense}
                feedback_metrics = {
                    **_prefixed_metrics(feedback_record, "feedback_"),
                    **feedback_dense,
                }
                phase = str(feedback_record.get("phase_at_snapshot", "approach"))
                open_utility = dense_branch_utility_v2(open_metrics, phase)
                feedback_utility = dense_branch_utility_v2(feedback_metrics, phase)
                enriched_feedback = {
                    **feedback_record,
                    **{f"open_{key}": value for key, value in open_dense.items()},
                    **{f"feedback_{key}": value for key, value in feedback_dense.items()},
                    "open_dense_utility_v2": open_utility,
                    "feedback_dense_utility_v2": feedback_utility,
                    "dense_vof_v2": (
                        feedback_utility
                        - open_utility
                        - float(feedback_record.get("query_cost", 0.0))
                    ),
                }
                if has_h32:
                    restore_flat_sim_state(
                        env, payload["feedback_h32_endpoint_state"], update_observables=False
                    )
                    feedback_h32_observation = observation_from_libero_proprio(
                        payload["feedback_h32_endpoint_proprio"]
                    )
                    feedback_h32_dense = geometry_delta_metrics(
                        start_geometry,
                        capture_goal_geometry(env, feedback_h32_observation),
                    )
                    open_h32_dense = h32_dense_by_index[selected_idx]
                    open_h32_metrics = {
                        **_prefixed_metrics(feedback_record, "open_h32_"),
                        **open_h32_dense,
                    }
                    feedback_h32_metrics = {
                        **_prefixed_metrics(feedback_record, "feedback_h32_"),
                        **feedback_h32_dense,
                    }
                    open_h32_utility = dense_branch_utility_v2(open_h32_metrics, phase)
                    feedback_h32_utility = dense_branch_utility_v2(
                        feedback_h32_metrics, phase
                    )
                    enriched_feedback.update(
                        {
                            **{
                                f"open_h32_{key}": value
                                for key, value in open_h32_dense.items()
                            },
                            **{
                                f"feedback_h32_{key}": value
                                for key, value in feedback_h32_dense.items()
                            },
                            "open_h32_dense_utility_v2": open_h32_utility,
                            "feedback_h32_dense_utility_v2": feedback_h32_utility,
                            "h32_dense_vof_v2": (
                                feedback_h32_utility
                                - open_h32_utility
                                - float(feedback_record.get("query_cost", 0.0))
                            ),
                        }
                    )
                feedback_rows.append(enriched_feedback)
    finally:
        for env in env_cache.values():
            env.close()

    feedback_dense = pd.DataFrame(feedback_rows)
    candidates_dense = pd.DataFrame(candidate_rows)
    feedback_dense.to_parquet(
        output_dir / f"{args.run_name}__feedback_pairs.parquet", index=False
    )
    feedback_dense.to_csv(output_dir / f"{args.run_name}__feedback_pairs.csv", index=False)
    candidates_dense.to_parquet(
        output_dir / f"{args.run_name}__candidate_outcomes.parquet", index=False
    )
    candidates_dense.to_csv(
        output_dir / f"{args.run_name}__candidate_outcomes.csv", index=False
    )
    return feedback_dense, candidates_dense


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()
    feedback, candidates = relabel(args)
    print(
        f"[dense-relabel] run={args.run_name} snapshots={len(feedback)} "
        f"candidates={len(candidates)} nonzero_vof="
        f"{int((pd.to_numeric(feedback['dense_vof_v2'], errors='coerce') != 0).sum())}"
    )


if __name__ == "__main__":
    main()

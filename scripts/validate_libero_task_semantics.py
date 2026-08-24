#!/usr/bin/env python3
"""Validate policy instructions against active LIBERO / LIBERO-PRO BDDL goals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from libero.libero import benchmark
from libero.libero.envs.bddl_utils import robosuite_parse_problem

from cosmos_policy.experiments.robot.libero.libero_utils import (
    get_libero_bddl_file,
    get_libero_task_description,
)


DEFAULT_SUITES = (
    "libero_goal_task",
    "libero_spatial_task",
    "libero_10_task",
    "libero_object_task",
)


def _target_objects(goal_states: list[object]) -> list[str]:
    targets = []
    for state in goal_states:
        if isinstance(state, (list, tuple)) and len(state) >= 2:
            target = str(state[1])
            if target not in targets:
                targets.append(target)
    return targets


def validate_suites(suites: list[str]) -> pd.DataFrame:
    rows = []
    available = benchmark.get_benchmark_dict()
    for suite_name in suites:
        if suite_name not in available:
            raise KeyError(f"Unknown LIBERO suite: {suite_name}")
        suite = available[suite_name]()
        for task_id in range(suite.n_tasks):
            task = suite.get_task(task_id)
            bddl_path = Path(get_libero_bddl_file(task))
            problem = robosuite_parse_problem(str(bddl_path))
            bddl_description = get_libero_task_description(task)
            parsed_description = problem.get("language_instruction", "")
            if isinstance(parsed_description, (list, tuple)):
                parsed_description = " ".join(str(token) for token in parsed_description)
            parsed_description = str(parsed_description).strip()
            if not bddl_description or bddl_description != parsed_description:
                raise AssertionError(
                    f"Instruction parser mismatch for {suite_name}/task{task_id}: "
                    f"helper={bddl_description!r}, parsed={parsed_description!r}"
                )
            goal_states = list(problem.get("goal_state", []) or [])
            if not goal_states:
                raise AssertionError(f"No goal predicates in {bddl_path}")
            benchmark_description = str(task.language).strip()
            rows.append(
                {
                    "suite": suite_name,
                    "task_id": task_id,
                    "bddl_file": str(bddl_path),
                    "benchmark_description": benchmark_description,
                    "bddl_description": bddl_description,
                    "instruction_shift": benchmark_description != bddl_description,
                    "goal_predicates_json": json.dumps(goal_states, default=str),
                    "target_objects": ",".join(_target_objects(goal_states)),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suites", default=",".join(DEFAULT_SUITES))
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--require-shift", action="store_true")
    args = parser.parse_args()
    suites = [value.strip() for value in args.suites.split(",") if value.strip()]
    results = validate_suites(suites)
    shifted = results.loc[results["instruction_shift"]]
    if args.require_shift and shifted.empty:
        raise AssertionError("Expected at least one task instruction shift")
    print(
        f"validated_tasks={len(results)} instruction_shifts={len(shifted)} "
        f"suites={len(suites)}"
    )
    if len(shifted):
        print(
            shifted[
                ["suite", "task_id", "benchmark_description", "bddl_description"]
            ].to_string(index=False)
        )
    if args.output_csv is not None:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output_csv, index=False)
        print(f"output={args.output_csv}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build frozen development and full-task LIBERO-PRO consensus evaluations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = "trajectory_consensus_20260908"
LEVELS = [f"{axis}0.{step}" for axis in "xy" for step in range(1, 6)]


def method(name, strategy, weight=0., margin=.5, gain=.1, k=4):
    return dict(label=name, strategy=strategy, density_weight=weight,
                value_margin=margin, minimum_density_gain=gain, candidates=k)


def defaults():
    template = json.loads((ROOT / "experiments/configs/libero_campaign_consensus_medoid_pre_p5_20260907.json").read_text())
    values = template["defaults"]
    values.update(
        save_videos=True, num_open_loop_steps=16, collect_prediction_errors=True,
        environment_num_init_states=50, environment_seed=20260908,
        environment_root=f".runtime/{RUN}_environment", experiment_split="development",
    )
    return values


def make_job(phase, cell, task, inits, selection, seed):
    factor = cell.split("_")[0]
    kind = {"object": "pro_planning_grid", "environment": "pro_environment_planning_grid",
            "position": "pro_position_planning_grid"}[factor]
    suite = {"object": "libero_object_object", "environment": "libero_object_env",
             "position": "libero_object_temp"}[factor]
    job = dict(
        name=f"{cell}_t{task}_{selection['label']}", kind=kind,
        case_id=f"tc2_{cell}", suites=suite, task_ids=str(task), init_state_ids=inits,
        max_rollouts=1, base_seed=seed + task * 100000,
        uncertainty_seeds=",".join(map(str, range(selection["candidates"]))),
        strategy_lambdas=f"{selection['strategy']}:{selection['density_weight']}",
        planning_value_margin=selection["value_margin"],
        planning_uncertainty_margin=selection["minimum_density_gain"],
        experiment_split="holdout" if phase == "full" else "development",
    )
    if factor == "position":
        job["position_level"] = cell.split("_", 1)[1]
    return job


def build(shortlist, winner=None):
    first = method("first", "first", k=1)
    maximum = method("max_value", "max_value")
    old = method("old_guarded", "cosmos_consensus_guarded", margin=.02)
    finalists = [method(f"v2_{i}", s["strategy"], s["density_weight"], s["value_margin"], s["minimum_density_gain"])
                  for i, s in enumerate(shortlist["finalists"])]
    selections = [first, maximum, old, method("physical_medoid", "trajectory_medoid", 1.),
                  method("physical_density", "trajectory_density", 1.), *finalists]
    profiles = {}
    smoke = [make_job("smoke", "object", 0, "0", m, 18000000) for m in selections]
    profiles["smoke"] = dict(description="Seven selectors; one real rollout each, H16/K4 with K1 control", jobs=smoke)
    development = []
    for m in selections:
        for factor_id, factor in enumerate(["object", "environment"]):
            for task in range(10):
                development.append(make_job("development", factor, task, "0-1", m, 19000000 + factor_id * 2000000))
        for level_id, level in enumerate(["x0.2", "y0.2", "x0.3", "y0.3"]):
            for task in [0, 2, 5, 9]:
                development.append(make_job("development", f"position_{level}", task, "0", m, 24000000 + level_id * 2000000))
    profiles["development"] = dict(description="392 paired deployment rollouts, 10 tasks, three perturbation factors", jobs=development)
    if winner is not None:
        full = []
        chosen = [first, maximum, winner]
        for m in chosen:
            for factor_id, factor in enumerate(["object", "environment"]):
                for task in range(10):
                    full.append(make_job("full", factor, task, "0-49", m, 40000000 + factor_id * 2000000))
            for level_id, level in enumerate(LEVELS):
                for task in range(10):
                    full.append(make_job("full", f"position_{level}", task, "0-4", m, 50000000 + level_id * 2000000))
        profiles["full"] = dict(description="4500 frozen prospective rollouts: 1500 per method, 10 tasks, Object/Environment/10 Position levels", jobs=full)
    return dict(schema_version=1, defaults=defaults(), profiles=profiles), selections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--winner", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    shortlist = json.loads(args.shortlist.read_text())
    winner = json.loads(args.winner.read_text())["method"] if args.winner else None
    config, selections = build(shortlist, winner)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n")
    args.output.with_suffix(".methods.json").write_text(json.dumps(selections, indent=2) + "\n")
    print({phase: len(value["jobs"]) for phase, value in config["profiles"].items()})


if __name__ == "__main__":
    main()

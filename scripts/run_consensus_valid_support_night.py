#!/usr/bin/env python3
"""Resume consensus on valid benchmark support, then collect a P5 development pilot."""
from __future__ import annotations

import argparse
import ast
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    from scripts.run_trajectory_consensus_sequence import atomic_json, utc
except ModuleNotFoundError:
    from run_trajectory_consensus_sequence import atomic_json, utc

ROOT = Path(__file__).resolve().parents[1]
NIGHT = "consensus_p5_night_20260909"
COMPACT = "trajectory_consensus_20260909_valid199"
REFERENCES = "consensus_references_20260909_valid199"
PILOT = "p5_boundary_candidates_20260909"
OLD_COMPACT = "trajectory_consensus_20260908_compact"
OLD_REFERENCES = "consensus_references_20260908"
EXCLUDED_PREFIX = "position_y0_5_t1_"
DEFAULT_GPUS = "1,2,3,4,5,6,7"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_json(path, payload):
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError(f"Refusing to alter frozen data: {path}")
    else:
        atomic_json(path, payload)


def validate_gpu_ids(value):
    gpus = [item.strip() for item in value.split(",")]
    if len(gpus) != len(set(gpus)) or any(g not in tuple("1234567") for g in gpus):
        raise ValueError("Only unique physical GPUs 1-7 are allowed; GPU0 is reserved")
    return gpus


def validate_night_freeze(path, payload):
    if not path.exists() or json.loads(path.read_text()) == payload:
        frozen_json(path, payload)
        return
    original = json.loads(path.read_text())
    amendment = json.loads((path.parent / "resource_amendment_gpu17.json").read_text())
    name = "run_consensus_valid_support_night.py"
    expected = copy.deepcopy(original)
    expected["scripts"][name] = payload["scripts"][name]
    if (expected != payload
            or amendment["original_freeze_sha256"] != sha(path)
            or amendment["old_launcher_sha256"] != original["scripts"][name]
            or amendment["new_launcher_sha256"] != payload["scripts"][name]
            or amendment["gpu_ids"] != list(range(1, 8))
            or amendment["paired_episode_resume"] is not True):
        raise ValueError("Resource amendment cannot change frozen experiment settings")


def valid_config(config, profile):
    result = copy.deepcopy(config)
    jobs = result["profiles"][profile]["jobs"]
    excluded = [j for j in jobs if j["name"].startswith(EXCLUDED_PREFIX)]
    if len(jobs) != 360 or len(excluded) != 3:
        raise ValueError("Expected exactly one unavailable cell for three methods")
    if any(str(j["task_ids"]) != "1" or str(j["init_state_ids"]) != "1"
           or j.get("position_level") != "y0.5" for j in excluded):
        raise ValueError("Unexpected exclusion identity")
    result["profiles"][profile]["jobs"] = [j for j in jobs if j not in excluded]
    result["profiles"][profile]["description"] = "597 rollouts on 199 valid cases; empty y0.5/task1 init asset excluded symmetrically"
    return result


def pilot_config():
    jobs = []
    cells = [("object", None, t) for t in (0, 3)]
    cells += [("position", "x0.2", t) for t in (0, 2, 9)]
    cells += [("position", "y0.2", t) for t in (0, 2, 4, 9)]
    for cell_index, (factor, level, task) in enumerate(cells):
        for init in (7, 8):
            name = f"{factor}_{level or 'object'}_t{task}_i{init}".replace(".", "p")
            job = dict(name=name, kind="pro_counterfactual_feedback" if level is None else "pro_position_counterfactual_feedback",
                case_id=f"p5_{factor}_{level or 'object'}", suites="libero_object_object" if level is None else "libero_object_temp",
                task_ids=str(task), init_state_ids=str(init), rollouts_per_init=1,
                base_seed=81000000 + cell_index * 100000 + init * 1000, target_decision_states=2)
            if level:
                job["position_level"] = level
            jobs.append(job)
    smoke = copy.deepcopy(jobs[:1])
    smoke[0].update(name="p5_integration", init_state_ids="0", base_seed=82000000,
                    target_decision_states=1, snapshot_query_indices="0", experiment_split="screen")
    defaults = dict(dynamic_gpu_queue=True, rollout_seed_step=97, uncertainty_seeds="0,1,2,3,4,5,6,7",
        max_timesteps=280, open_loop_steps=16, sampling_mode="fixed_queries", snapshot_query_indices="0,3",
        phase_cap_fraction=1.0, consequence_horizon_steps=16, terminal_continuation_fraction=1.0,
        terminal_selected_feedback_only=False, continuation_num_candidates=1, skip_feedback_branch=True,
        query_cost=0.0, num_denoising_steps_action=5, prediction_mode="parallel", continuation_prediction_mode="parallel",
        num_denoising_steps_future_state=1, num_denoising_steps_value=1, num_future_state_samples=1,
        num_value_samples=1, value_ensemble_aggregation="average", experiment_split="development")
    return dict(schema_version=1, defaults=defaults, profiles=dict(
        pilot=dict(description="Development only: 36 fixed-query K8 pools, up to 288 terminal branches", jobs=jobs),
        smoke=dict(description="Integration only: one K8 exact-state pool", jobs=smoke)))


def asset_count(path):
    import torch
    # These are trusted project-owned LIBERO benchmark assets, not downloaded inputs.
    return len(torch.load(path, map_location="cpu", weights_only=False))


def prepare(root=ROOT):
    campaigns = root / "experiments/campaigns"
    old = campaigns / OLD_COMPACT
    old_ref = campaigns / OLD_REFERENCES
    target = campaigns / COMPACT
    references = campaigns / REFERENCES
    pilot = campaigns / PILOT
    for path in (target, references, pilot):
        path.mkdir(parents=True, exist_ok=True)

    task_map_path = root / "LIBERO-PRO/libero/libero/benchmark/libero_suite_task_map.py"
    task_map = ast.literal_eval(ast.parse(task_map_path.read_text()).body[0].value)
    task_name = task_map["libero_object_temp"][1]
    relative = Path("init_files/libero_object_temp_y0.5") / (task_name + ".pruned_init")
    original_asset = root / "LIBERO-PRO/libero/libero" / relative
    runtime_asset = root / ".runtime/libero_pro_position/y0.5/init_files/libero_object_temp" / original_asset.name
    if asset_count(original_asset) != 0 or sha(original_asset) != sha(runtime_asset):
        raise ValueError("Unavailable-cell amendment requires the original and runtime empty asset")
    manifest = json.loads((old / "manifest.json").read_text())
    excluded = [j for j in manifest["jobs"] if j["name"].startswith(EXCLUDED_PREFIX)]
    valid = [j for j in manifest["jobs"] if j not in excluded]
    if len(excluded) != 3 or len(valid) != 357:
        raise ValueError("Unexpected source campaign coverage")
    for job in excluded:
        if Path(job["completion_marker"]).exists():
            raise ValueError("Cannot exclude a measured outcome")
        if "only 0 init states" not in (old / "logs" / (job["name"] + ".log")).read_text():
            raise ValueError("Exclusion is not an empty-asset error")
    if not all(Path(j["completion_marker"]).is_file() for j in valid):
        raise ValueError("Valid source jobs are not all complete")

    config = valid_config(json.loads((old / "config.json").read_text()), "compact")
    frozen_json(target / "config.json", config)
    frozen_json(target / "config.methods.json", json.loads((old / "config.methods.json").read_text()))
    audit = dict(reason="Original benchmark init asset contains zero states; not policy failure",
        original_campaign=OLD_COMPACT, original_manifest_sha256=sha(old / "manifest.json"),
        original_asset=str(original_asset), original_asset_sha256=sha(original_asset), init_count=0,
        excluded_jobs=[j["name"] for j in excluded], retained_cases=199, retained_rollouts=597,
        outcome_based_exclusion=False, new_rollouts=0)
    frozen_json(target / "support_amendment.json", audit)
    derived = copy.deepcopy(manifest)
    derived.update(jobs=valid, config=str(target / "config.json"), status="completed",
                   run_prefix=COMPACT, derived_from=OLD_COMPACT, support_amendment=audit)
    derived["results"] = [r for r in derived.get("results", []) if not r.get("job", "").startswith(EXCLUDED_PREFIX)]
    frozen_json(target / "manifest.json", derived)
    for name in ("runs", "videos", "completed", "logs"):
        link = target / name
        if not link.exists():
            link.symlink_to(old / name, target_is_directory=True)
        if link.resolve() != (old / name).resolve():
            raise ValueError("Unexpected derived data path")

    ref_config = valid_config(json.loads((old_ref / "config.json").read_text()), "references")
    frozen_json(references / "config.json", ref_config)
    frozen_json(references / "config.methods.json", json.loads((old_ref / "config.methods.json").read_text()))
    freeze = json.loads((old_ref / "freeze.json").read_text())
    for name, digest in freeze["script_sha256"].items():
        if sha(root / "scripts" / name) != digest:
            raise ValueError(f"Original reference script changed: {name}")
    original_hashes = json.loads((campaigns / "trajectory_consensus_20260908/source_sha256.json").read_text())
    package = old_ref / "source/cosmos-policy/cosmos_policy"
    for name, digest in original_hashes.items():
        if name == "experiments/robot/libero/trajectory_consensus.py":
            digest = freeze["geometry_sha256"]
        if sha(package / name) != digest:
            raise ValueError(f"Reference runtime changed: {name}")
    source_link = references / "source"
    if not source_link.exists():
        source_link.symlink_to(old_ref / "source", target_is_directory=True)
    if source_link.resolve() != (old_ref / "source").resolve():
        raise ValueError("Wrong runtime link")
    frozen_json(references / "freeze.json", dict(original_reference_freeze=freeze,
        support_amendment=audit, config_sha256=sha(references / "config.json")))

    pc = pilot_config()
    asset_audit = []
    for phase in pc["profiles"].values():
        for job in phase["jobs"]:
            suite = job["suites"]
            stem = task_map[suite][int(job["task_ids"])]
            folder = suite + "_" + job["position_level"] if "position_level" in job else suite
            path = root / "LIBERO-PRO/libero/libero/init_files" / folder / (stem + ".pruned_init")
            count = asset_count(path)
            if count <= int(job["init_state_ids"]):
                raise ValueError(f"Pilot init unavailable: {job['name']} ({count} states)")
            asset_audit.append(dict(job=job["name"], path=str(path), count=count, sha256=sha(path)))
    frozen_json(pilot / "config.json", pc)
    frozen_json(pilot / "asset_audit.json", asset_audit)
    files = ["run_consensus_valid_support_night.py", "analyze_consensus_valid_support.py",
             "analyze_p5_boundary_pilot.py", "run_libero_experiment_campaign.py",
             "collect_counterfactual_feedback.py", "counterfactual_feedback_utils.py",
             "run_libero_pro_counterfactual_feedback_collect.sh", "run_libero_pro_planning_strategy_grid.sh",
             "analyze_trajectory_consensus_campaign.py", "analyze_consensus_reference_campaign.py"]
    validate_night_freeze(campaigns / NIGHT / "freeze.json", dict(
        scripts={f: sha(root / "scripts" / f) for f in files},
        configs={str(p): sha(p) for p in (target / "config.json", references / "config.json", pilot / "config.json")},
        original_runtime_manifest=freeze, pilot_is_development=True, gpu_ids=[3, 4, 5, 6, 7]))
    return target, references, pilot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--gpus", default=DEFAULT_GPUS)
    args = parser.parse_args()
    try:
        gpus = validate_gpu_ids(args.gpus)
    except ValueError as error:
        parser.error(str(error))
    args.gpus = ",".join(gpus)
    directory = ROOT / "experiments/campaigns" / NIGHT
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory / "sequence.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    compact, references, pilot = prepare()
    print("Prepared: 597 existing valid rollouts; 3 + 597 reference rollouts; 1 + 36 K8 pilot pools", flush=True)
    if not args.execute:
        return
    previous = directory / "sequence_status.json"
    old = json.loads(previous.read_text()) if previous.exists() else {}
    if old.get("status") == "completed":
        return
    started = old.get("started_at", utc())
    stage = "validate_compact"
    env = dict(os.environ, COSMOS_REPO=str(references / "source/cosmos-policy"), HF_HUB_OFFLINE="1",
               WANDB_MODE="offline", PYTHONUNBUFFERED="1", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
               LIBERO_PRO_PAIRED_RESUME="1")

    def status(state, **extra):
        atomic_json(previous, dict(run_base=NIGHT, status=state, stage=stage, started_at=started,
            updated_at=utc(), pid=os.getpid(), gpus=gpus, **extra))
        (directory / "heartbeat.txt").write_text(f"{utc()} pid={os.getpid()} stage={stage}\n")

    def command(parts):
        print("RUN", " ".join(map(str, parts)), flush=True)
        child = subprocess.Popen(list(map(str, parts)), cwd=ROOT, env=env, start_new_session=True)
        try:
            while child.poll() is None:
                status("running", child_pid=child.pid)
                time.sleep(10)
        except BaseException:
            import signal
            os.killpg(child.pid, signal.SIGTERM)
            child.wait()
            raise
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, parts)

    def collect(config, profile, name):
        path = directory.parent / name / "manifest.json"
        if path.exists() and json.loads(path.read_text()).get("status") == "completed":
            return
        command([sys.executable, ROOT / "scripts/run_libero_experiment_campaign.py", "--config", config,
                 "--profile", profile, "--run-prefix", name, "--gpus", args.gpus, "--execute"])

    try:
        command([sys.executable, ROOT / "scripts/analyze_consensus_valid_support.py", "--compact-only"])
        atomic_json(compact / "sequence_status.json", dict(status="completed", updated_at=utc(),
            interpretation="validated_support_subset_597_not_original_600", expected_rollouts=597))
        for phase, name in (("smoke", REFERENCES + "_smoke"), ("references", REFERENCES)):
            stage = "reference_" + phase
            collect(references / "config.json", phase, name)
            stage = "validate_" + phase
            command([sys.executable, ROOT / "scripts/analyze_trajectory_consensus_campaign.py",
                     "--campaign", directory.parent / name])
        stage = "matched_analysis"
        command([sys.executable, ROOT / "scripts/analyze_consensus_valid_support.py"])
        atomic_json(references / "sequence_status.json", dict(status="completed", updated_at=utc(), expected_rollouts=597))
        for phase, name in (("smoke", PILOT + "_smoke"), ("pilot", PILOT)):
            stage = "p5_" + phase
            collect(pilot / "config.json", phase, name)
            stage = "validate_p5_" + phase
            command([sys.executable, ROOT / "scripts/analyze_p5_boundary_pilot.py", "--campaign", directory.parent / name,
                     "--expected-pools", "1" if phase == "smoke" else "36"])
        status("completed")
    except BaseException as error:
        status("failed", error=repr(error))
        raise


if __name__ == "__main__":
    main()

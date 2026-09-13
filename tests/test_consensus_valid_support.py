import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_consensus_valid_support_night import (
    DEFAULT_GPUS, frozen_json, pilot_config, sha, valid_config,
    validate_gpu_ids, validate_night_freeze,
)
from scripts.analyze_p5_boundary_pilot import summarize_pool
from scripts.analyze_consensus_valid_support import validate_coverage
from scripts.terminal_grounded_critic import TERMINAL_CRITIC_FEATURES
from scripts.run_libero_experiment_campaign import expand_jobs, validate_job_inputs


ROOT = Path(__file__).resolve().parents[1]


def test_gpu_pool_includes_explicitly_authorized_zero():
    assert validate_gpu_ids(DEFAULT_GPUS) == list("01234567")
    assert validate_gpu_ids("0") == ["0"]
    assert validate_gpu_ids(" 1, 3, 7 ") == ["1", "3", "7"]


@pytest.mark.parametrize("value", ["", "0,0", "-1", "1,1", "8", "1,", "1,foo"])
def test_invalid_gpu_pool_rejected(value):
    with pytest.raises(ValueError):
        validate_gpu_ids(value)


def test_resource_amendment_keeps_original_freeze_and_all_other_settings(tmp_path):
    name = "run_consensus_valid_support_night.py"
    original = dict(scripts={name: "old", "collector.py": "same"}, configs={"c": "fixed"}, gpu_ids=[3, 4, 5, 6, 7])
    path = tmp_path / "freeze.json"
    frozen_json(path, original)
    digest = sha(path)
    changed = copy.deepcopy(original)
    changed["scripts"][name] = "new"
    amendment = dict(original_freeze_sha256=digest, old_launcher_sha256="old",
        new_launcher_sha256="new", gpu_ids=list(range(1, 8)), paired_episode_resume=True)
    frozen_json(tmp_path / "resource_amendment_gpu17.json", amendment)
    validate_night_freeze(path, changed)
    assert sha(path) == digest
    for section, key in (("configs", "c"), ("scripts", "collector.py")):
        tampered = copy.deepcopy(changed)
        tampered[section][key] = "changed"
        with pytest.raises(ValueError, match="experiment settings"):
            validate_night_freeze(path, tampered)


def test_gpu07_amendment_keeps_configs_and_collectors_frozen(tmp_path, monkeypatch):
    from scripts import run_consensus_valid_support_night as night
    monkeypatch.setattr(night, "ROOT", tmp_path)
    environment = tmp_path / "scripts/cosmos_env.sh"
    environment.parent.mkdir()
    environment.write_text("new environment")
    backup = tmp_path / "resource_gpu07_backup/scripts/cosmos_env.sh"
    backup.parent.mkdir(parents=True)
    backup.write_text("old environment")
    launcher = "run_consensus_valid_support_night.py"
    runner = "run_libero_experiment_campaign.py"
    original = dict(scripts={launcher: "v0", runner: "r0", "collector.py": "c0"},
                    configs={"c": "fixed"}, gpu_ids=[3, 4, 5, 6, 7])
    path = tmp_path / "freeze.json"
    frozen_json(path, original)
    previous_path = tmp_path / "resource_amendment_gpu17.json"
    frozen_json(previous_path, dict(original_freeze_sha256=sha(path), old_launcher_sha256="v0",
        new_launcher_sha256="v1", gpu_ids=list(range(1, 8)), paired_episode_resume=True))
    amendment = dict(original_freeze_sha256=sha(path), previous_resource_amendment_sha256=sha(previous_path),
        gpu_ids=list(range(8)), paired_episode_resume=True, method_configuration_changed=False,
        gpu_policy="idle_only_no_compute_processes",
        environment_script=dict(file="cosmos_env.sh", old_sha256=sha(backup), new_sha256=sha(environment)),
        script_changes={
            launcher: dict(old_sha256="v1", new_sha256="v2"),
            runner: dict(old_sha256="r0", new_sha256="r1")})
    amendment_path = tmp_path / "resource_amendment_gpu07.json"
    frozen_json(amendment_path, amendment)
    changed = copy.deepcopy(original)
    changed["scripts"].update({launcher: "v2", runner: "r1"})
    validate_night_freeze(path, changed)
    assert json.loads(path.read_text()) == original
    for section, key in (("configs", "c"), ("scripts", "collector.py")):
        tampered = copy.deepcopy(changed)
        tampered[section][key] = "changed"
        with pytest.raises(ValueError, match="experiment settings"):
            validate_night_freeze(path, tampered)
    for key, value in [("previous_resource_amendment_sha256", "wrong"),
                       ("method_configuration_changed", True), ("gpu_policy", "shared")]:
        tampered = copy.deepcopy(amendment)
        tampered[key] = value
        amendment_path.write_text(json.dumps(tampered))
        with pytest.raises(ValueError, match="experiment settings"):
            validate_night_freeze(path, changed)
    amendment_path.write_text(json.dumps(amendment))
    environment.write_text("unexpected change")
    with pytest.raises(ValueError, match="experiment settings"):
        validate_night_freeze(path, changed)


def test_amendment_excludes_only_empty_cell_symmetrically():
    original = json.loads((ROOT / "experiments/campaigns/trajectory_consensus_20260908_compact/config.json").read_text())
    before = copy.deepcopy(original)
    amended = valid_config(original, "compact")
    assert original == before
    jobs = amended["profiles"]["compact"]["jobs"]
    assert len(jobs) == 357
    assert not any(j["name"].startswith("position_y0_5_t1_") for j in jobs)
    assert all(j in original["profiles"]["compact"]["jobs"] for j in jobs)
    assert sum(5 if j["init_state_ids"] == "2-6" else 1 for j in jobs) == 597


def test_exclusion_cannot_remove_a_different_init():
    original = json.loads((ROOT / "experiments/campaigns/trajectory_consensus_20260908_compact/config.json").read_text())
    for j in original["profiles"]["compact"]["jobs"]:
        if j["name"].startswith("position_y0_5_t1_"):
            j["init_state_ids"] = "0"
    with pytest.raises(ValueError, match="identity"):
        valid_config(original, "compact")


def test_frozen_json_refuses_changes(tmp_path):
    path = tmp_path / "freeze.json"
    frozen_json(path, {"n": 199})
    frozen_json(path, {"n": 199})
    with pytest.raises(ValueError, match="frozen"):
        frozen_json(path, {"n": 200})


def test_compact_coverage_does_not_require_unrun_reference_methods():
    rows = []
    for method in ("first_k1", "max_value", "osc_medoid"):
        for factor, count in (("Object", 50), ("Environment", 50), ("Position", 99)):
            rows.extend(dict(method=method, factor=factor, case_id=factor, suite=factor,
                task_id=0, init_state_id=i, rollout_seed=i) for i in range(count))
    frame = pd.DataFrame(rows)
    validate_coverage(frame, compact_only=True)
    with pytest.raises(ValueError, match="methods"):
        validate_coverage(frame)
    with pytest.raises(ValueError, match="coverage"):
        validate_coverage(frame.iloc[1:], compact_only=True)


def test_pilot_has_fixed_queries_and_group_coverage():
    config = pilot_config()
    jobs = expand_jobs(config["profiles"]["pilot"], config["defaults"])
    assert len(jobs) == 18
    assert sum(j["target_decision_states"] for j in jobs) == 36
    assert len(set(j["base_seed"] for j in jobs)) == 18
    for j in jobs:
        validate_job_inputs(j)
        assert j["snapshot_query_indices"] == "0,3"
        assert j["open_loop_steps"] == 16
        assert j["continuation_num_candidates"] == 1
        assert j["uncertainty_seeds"] == "0,1,2,3,4,5,6,7"
        assert j["experiment_split"] == "development"
    smoke = expand_jobs(config["profiles"]["smoke"], config["defaults"])[0]
    validate_job_inputs(smoke)
    assert smoke["snapshot_query_indices"] == "0" and smoke["experiment_split"] == "screen"


def candidate_pool():
    g = pd.DataFrame({f: np.zeros(8) for f in TERMINAL_CRITIC_FEATURES})
    g["candidate_value"] = np.arange(8)
    for name, value in dict(candidate_idx=np.arange(8), terminal_available=True,
        terminal_success=[False]*4+[True]*4, open_loop_steps=16, prediction_mode="parallel",
        main_open_replay_state_max_abs=[np.nan]*7+[0.], snapshot_id="s", case_id="p5_object",
        task_id=0, init_state_id=7, query_idx=3).items():
        g[name] = value
    return g


def test_nested_budgets_use_same_candidates_and_outcomes():
    a, b = summarize_pool(candidate_pool())
    assert a["k"] == 4 and not a["oracle_success"]
    assert b["k"] == 8 and b["oracle_success"] and b["mixed"]
    assert b["within_pool_value_accuracy"] == 1
    assert b["strict_replay"]


def test_missing_replay_is_not_passed():
    g = candidate_pool()
    g["main_open_replay_state_max_abs"] = np.nan
    assert not summarize_pool(g)[0]["strict_replay"]


@pytest.mark.parametrize("change", ["duplicate", "missing_outcome", "horizon", "future_leak_missing_feature"])
def test_pilot_rejects_incomplete_or_incompatible_data(change):
    g = candidate_pool()
    if change == "duplicate":
        g.loc[0, "candidate_idx"] = 1
    elif change == "missing_outcome":
        g.loc[0, "terminal_available"] = False
    elif change == "horizon":
        g["open_loop_steps"] = 5
    else:
        g.loc[0, TERMINAL_CRITIC_FEATURES[-1]] = np.nan
    with pytest.raises(ValueError):
        summarize_pool(g)

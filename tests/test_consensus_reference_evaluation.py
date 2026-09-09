import copy
import json

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_consensus_common_pool import choices, mixed_concordance, runtime_module, validate_pool
from scripts.analyze_consensus_reference_campaign import paired_effects
from scripts.prepare_trajectory_consensus_campaign import build, method
from scripts.run_consensus_reference_sequence import METHODS, build_config, dependency_state
from scripts.run_trajectory_consensus_compact import compact_config


@pytest.fixture
def geometry():
    return runtime_module("trajectory_consensus")


def test_raw_medoid_is_actual_sample_and_value_breaks_ties(geometry):
    actions = np.zeros((4, 16, 7))
    actions[:, :, 0] = np.array([0, .01, .02, 1])[:, None]
    selected, info = geometry.select_trajectory_consensus(actions, [0, 1, 2, 0], strategy="trajectory_raw_medoid")
    expected = np.linalg.norm(actions.reshape(4, -1)[:, None] - actions.reshape(4, -1)[None, :], axis=-1)
    np.testing.assert_allclose(info["trajectory_distance_matrix"], expected)
    assert selected == 2


def test_kdpe_matches_direct_paper_kernel_order_and_rejects_outlier(geometry):
    actions = np.zeros((4, 16, 7))
    actions[:, :, 0] = np.array([0, .01, .04, .6])[:, None]
    actions[:, :, 3] = np.array([0, .01, .04, .6])[:, None]
    scores, squared = geometry.kdpe_endpoint_log_density(actions)
    direct = np.exp(-.5 * squared).mean(axis=1)
    assert np.argmax(scores) == np.argmax(direct)
    assert scores[3] < scores[0]
    assert np.isfinite(scores).all()
    np.testing.assert_allclose(squared, squared.T)
    np.testing.assert_allclose(np.diag(squared), 0)


def test_kde_stays_finite_for_widely_separated_candidates(geometry):
    actions = np.zeros((4, 16, 7))
    actions[:, :, 0] = np.array([-1, -.2, .3, 1])[:, None]
    scores, _ = geometry.kdpe_endpoint_log_density(actions, bandwidths=(1e-6, 1e-6, 1e-6))
    assert np.isfinite(scores).all()


def test_zero_kde_and_single_candidate(geometry):
    assert geometry.kdpe_endpoint_log_density(np.zeros((1, 16, 7)))[0].tolist() == [0]
    with pytest.raises(ValueError):
        geometry.kdpe_endpoint_log_density(np.zeros((4, 16, 7)), bandwidths=(0, .25, 1))


def test_uniform_time_and_component_ablations(geometry):
    actions = np.zeros((4, 16, 7))
    actions[1, :, 3] = .4
    actions[2, :, -1] = -1
    full = geometry.trajectory_distances(actions, discount=1)
    assert full[0, 1] > 0 and full[0, 2] > 0
    assert geometry.trajectory_distances(actions, rotation_weight=0)[0, 1] == 0
    assert geometry.trajectory_distances(actions, gripper_weight=0)[0, 2] == 0


def test_geometry_defaults_match_explicit_components(geometry):
    actions = np.random.default_rng(8).normal(size=(4, 16, 7))
    np.testing.assert_array_equal(geometry.trajectory_distances(actions),
        geometry.trajectory_distances(actions, integrate=True, rotation_weight=.5, gripper_weight=.25, discount=.95))


def test_choices_are_independent_of_outcomes(geometry):
    actions = np.random.default_rng(1).uniform(-1, 1, (4, 16, 7))
    result = choices(actions, np.arange(4), geometry, runtime_module("consensus_medoid"))
    assert len(result) == 11
    assert all(0 <= selected < 4 for selected, _ in result.values())
    # The selector API deliberately has no terminal labels or realized-error argument.
    assert set(result) >= {"keystone", "kdpe_endpoint", "raw_medoid", "osc_medoid"}


def pool():
    return pd.DataFrame(dict(candidate_idx=range(4), terminal_available=True,
        terminal_success=[False, True, False, True], terminal_target_drop_candidate=False,
        factor="Object", group_id="same", task_id=0, init_state_id=1,
        sidecar_path="same.npz", open_loop_steps=16, prediction_mode="parallel",
        main_open_replay_state_max_abs=[np.nan, np.nan, 1e-12, np.nan]))


def test_missing_replay_does_not_pass_as_exact():
    assert validate_pool(pool()) is None
    assert validate_pool(pool().assign(main_open_replay_state_max_abs=np.nan)) == "missing_replay_audit"
    assert validate_pool(pool().assign(main_open_replay_state_max_abs=.01)) == "nonexact_replay"
    with pytest.raises(ValueError, match="terminal_success"):
        validate_pool(pool().assign(terminal_success=np.nan))
    with pytest.raises(ValueError, match="four"):
        validate_pool(pool().iloc[:3])


def test_common_pool_report_writes_fractional_random_control(tmp_path, monkeypatch):
    from scripts import analyze_consensus_common_pool as analysis

    geometry, consensus = runtime_module("trajectory_consensus"), runtime_module("consensus_medoid")
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "runtime_module", lambda name: geometry if name == "trajectory_consensus" else consensus)
    actions = np.zeros((4, 16, 7))
    actions[:, :, 0] = np.array([0, .01, .02, .8])[:, None]
    values = np.arange(4, dtype=float)
    np.savez(tmp_path / "same.npz", candidate_actions=actions, candidate_values=values)
    rows = pool().assign(snapshot_group="s", candidate_value=values, query_idx=3, case_id="case")
    source = tmp_path / "candidates.parquet"
    rows.to_parquet(source)
    decisions, summary = analysis.analyze(source, tmp_path / "analysis")
    assert len(decisions) == 12
    random = summary[summary.method.eq("uniform_random_expected")]
    assert random.mcnemar_p.isna().all() and random.pooled_sr.eq(.5).all()
    assert (tmp_path / "analysis/decisions.parquet").is_file()


def test_within_pool_metric_and_constant_scores():
    y = np.array([False, True, True, False])
    assert mixed_concordance(np.array([0, 1, 1, 0]), y) == (4., 4)
    assert mixed_concordance(np.zeros(4), y) == (2., 4)
    assert mixed_concordance(np.ones(4), np.ones(4, dtype=bool)) == (0., 0)
    assert mixed_concordance(None, y) == (0., 0)


def configuration():
    shortlist = {"finalists": [dict(strategy=s, density_weight=.25, value_margin=.25, minimum_density_gain=.1)
        for s in ("trajectory_value_density", "trajectory_value_density_aligned")]}
    original, _ = build(shortlist, method("winner", "trajectory_medoid", 1.))
    return compact_config(original)


def test_reference_grid_is_matched_and_does_not_mutate_frozen_config():
    compact = configuration()
    before = copy.deepcopy(compact)
    config = build_config(compact)
    assert compact == before
    jobs = config["profiles"]["references"]["jobs"]
    assert len(jobs) == len({j['name'] for j in jobs}) == 360
    assert len(config["profiles"]["smoke"]["jobs"]) == 3
    sources = {(j["case_id"], j["task_ids"]): j for j in compact["profiles"]["compact"]["jobs"] if j["name"].endswith("_max_value")}
    assert sum(1 if j["init_state_ids"] == "1" else 5 for j in jobs) == 600
    for job in jobs:
        base = sources[job["case_id"], job["task_ids"]]
        for key in ("suites", "task_ids", "case_id", "base_seed", "init_state_ids"):
            assert job[key] == base[key]
        assert job["uncertainty_seeds"] == "0,1,2,3"
        assert sum(job["name"].endswith("_" + m["label"]) for m in METHODS) == 1
    assert config["defaults"]["dynamic_gpu_queue"]
    assert config["defaults"]["num_open_loop_steps"] == 16
    assert {j["experiment_split"] for j in jobs} == {"holdout"}
    assert {j["experiment_split"] for j in config["profiles"]["smoke"]["jobs"]} == {"screen"}


def test_dependency_requires_completed_analysis_and_stops_on_failure(tmp_path):
    p = tmp_path / "sequence_status.json"
    assert dependency_state(p) == "waiting"
    p.write_text(json.dumps({"status": "running", "stage": "analysis"}))
    assert dependency_state(p) == "waiting"
    p.write_text(json.dumps({"status": "completed"}))
    assert dependency_state(p) == "ready"
    p.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="manual inspection"):
        dependency_state(p)


def test_combined_pairing_and_holm():
    rows = pd.DataFrame([dict(method=m, case_id="case", suite="suite", task_id=0,
        init_state_id=i, rollout_seed=i, factor="Object", success=m != "max_value",
        sim_state_json="[1,2]", q0_action_pool_sha256="same") for m in ("max_value", "a", "b") for i in range(4)])
    effects = paired_effects(rows)
    primary = effects[effects.scope.eq("All")]
    assert primary.rescues.eq(4).all() and primary.harms.eq(0).all()
    assert primary.holm_macro_p.eq(.25).all()
    with pytest.raises(ValueError, match="Incomplete"):
        paired_effects(rows.iloc[:-1])
    with pytest.raises(AssertionError):
        paired_effects(rows.assign(sim_state_json=["[9,9]"] + ["[1,2]"] * (len(rows)-1)))

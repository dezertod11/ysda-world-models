import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_trajectory_consensus_campaign import analyze, interval, load_episodes


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trajectory_config", ROOT / "scripts/prepare_trajectory_consensus_campaign.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def shortlist():
    return {"finalists": [dict(strategy=s, density_weight=.25, value_margin=.25, minimum_density_gain=.1)
                          for s in ("trajectory_value_density", "trajectory_value_density_aligned")]}


def episodes(jobs):
    return sum(int(j["init_state_ids"].split("-")[-1]) - int(j["init_state_ids"].split("-")[0]) + 1 for j in jobs)


def test_stage_sizes_and_no_full_without_frozen_winner():
    config, methods = module.build(shortlist())
    assert "full" not in config["profiles"]
    assert len(methods) == 7
    assert episodes(config["profiles"]["smoke"]["jobs"]) == 7
    assert episodes(config["profiles"]["development"]["jobs"]) == 392
    assert config["defaults"]["num_open_loop_steps"] == 16
    assert config["defaults"]["save_videos"]
    assert config["defaults"]["environment_root"].endswith("trajectory_consensus_20260908_environment")


def test_full_coverage_and_matching_conditions():
    winner = module.method("winner", "trajectory_value_density", .25, .25, .1)
    config, _ = module.build(shortlist(), winner)
    jobs = config["profiles"]["full"]["jobs"]
    assert episodes(jobs) == 4500
    groups = {}
    for job in jobs:
        groups.setdefault((job["case_id"], job["task_ids"]), []).append(job)
    assert len(groups) == 120
    for group in groups.values():
        assert len(group) == 3
        for key in ("base_seed", "init_state_ids", "suites", "experiment_split"):
            assert len({j[key] for j in group}) == 1
    assert sum(j["kind"] == "pro_position_planning_grid" for j in jobs) == 300


def fixture_campaign(tmp_path, transform=lambda x: x, status="completed"):
    campaign = tmp_path / "example_smoke"
    (campaign / "runs").mkdir(parents=True)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"profiles": {"smoke": {"jobs": [
        {"name": "object_first", "init_state_ids": "0"}]}}}))
    config.with_suffix(".methods.json").write_text(json.dumps([{"label": "first", "strategy": "first"}]))
    video = campaign / "video.mp4"
    video.write_bytes(b"x" * 2048)
    trace = pd.DataFrame([dict(
        case_id="object", suite="libero_object_object", task_id=0, init_state_id=0,
        rollout_seed=100, query_idx=q, t=q * 16, t_after=(q + 1) * 16,
        executed_steps=16, num_open_loop_steps=16, success=True, final_t=32,
        num_queries=2, max_value_selected=True, prediction_error_horizon_aligned=True,
        video_path=str(video), sim_state_json="[0,1]",
    ) for q in range(2)])
    transform(trace).to_parquet(campaign / "runs/prefix__first__query_traces.parquet")
    (campaign / "manifest.json").write_text(json.dumps(dict(
        config=str(config), profile="smoke", status=status,
        jobs=[dict(name="object_first", kind="pro_planning_grid",
                   environment={"LIBERO_PRO_PLANNING_GRID_PREFIX": "prefix"})],
    )))
    return campaign


def test_analysis_counts_episode_not_queries(tmp_path):
    episodes, queries, _ = load_episodes(fixture_campaign(tmp_path))
    assert len(episodes) == 1
    assert queries.queries.sum() == 2


@pytest.mark.parametrize("change,message", [
    (lambda x: pd.concat([x, x.iloc[:1]]), "Duplicate queries"),
    (lambda x: x.iloc[:1], "Missing query"),
    (lambda x: x.assign(executed_steps=8), "Wrong executed"),
    (lambda x: x.assign(num_open_loop_steps=8), "H16"),
])
def test_analysis_rejects_corrupt_trace(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        load_episodes(fixture_campaign(tmp_path, change))


def test_analysis_cannot_freeze_running_campaign(tmp_path):
    with pytest.raises(ValueError, match="incomplete"):
        load_episodes(fixture_campaign(tmp_path, status="running"))


def test_bootstrap_constant_paired_effect_is_exact():
    data = pd.DataFrame([dict(factor=f, task_id=t, init_state_id=i, delta=1)
                         for f in ("Object", "Position") for t in range(2) for i in range(3)])
    np.testing.assert_allclose(interval(data, repeats=30), [1, 1])


def test_complete_development_report_and_freeze(tmp_path, monkeypatch):
    import imageio.v2 as imageio

    campaign = tmp_path / "test_development"
    (campaign / "runs").mkdir(parents=True)
    (campaign / "videos").mkdir()
    config = tmp_path / "config.json"
    methods = [module.method("first", "first", k=1), module.method("max_value", "max_value"),
               module.method("physical_density", "trajectory_density", 1.)]
    jobs = []
    for m in methods:
        video = campaign / "videos" / (m["label"] + ".mp4")
        video.write_bytes(b"x" * 2048)
        name = "object_" + m["label"]
        jobs.append(dict(name=name, init_state_ids="0", kind="pro_planning_grid",
                         environment={"LIBERO_PRO_PLANNING_GRID_PREFIX": name}))
        pd.DataFrame([dict(
            case_id="object", suite="libero_object_object", task_id=0, init_state_id=0,
            rollout_seed=100, query_idx=0, t=0, t_after=16, executed_steps=16,
            num_open_loop_steps=16, success=m["label"] == "physical_density", final_t=16,
            num_queries=1, max_value_selected=True, prediction_error_horizon_aligned=True,
            video_path=str(video), sim_state_json="[0,1]", target_drop_candidate=False,
            candidate_action_chunks_json=json.dumps(np.zeros((m["candidates"], 16, 7)).tolist()),
        )]).to_parquet(campaign / "runs" / (name + "__data__query_traces.parquet"))
    config.write_text(json.dumps({"profiles": {"development": {"jobs": jobs}}}))
    config.with_suffix(".methods.json").write_text(json.dumps(methods))
    (campaign / "manifest.json").write_text(json.dumps(dict(
        config=str(config), profile="development", status="completed", jobs=jobs,
    )))

    class Reader:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def count_frames(self):
            return 16

        def get_data(self, _):
            return np.arange(100)

    monkeypatch.setattr(imageio, "get_reader", lambda _: Reader())
    frozen = tmp_path / "winner.json"
    analyze(campaign, frozen)
    payload = json.loads(frozen.read_text())
    assert payload["method"]["strategy"] == "trajectory_density"
    assert payload["development_beats_max_value"]
    assert (campaign / "trajectory_analysis/RESULTS.md").is_file()
    assert (campaign / "trajectory_analysis/videos.html").is_file()
    effects = pd.read_csv(campaign / "trajectory_analysis/paired_effects.csv")
    assert effects.loc[effects.reference.eq("max_value"), "q0_action_pool_exact_rate"].eq(1).all()
    previous = frozen.read_text()
    analyze(campaign, frozen)
    assert frozen.read_text() == previous

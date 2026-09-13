import queue

import pandas as pd
import pytest

from scripts import run_libero_experiment_campaign as launcher
from scripts.prepare_trajectory_consensus_campaign import build, method
from scripts.run_trajectory_consensus_compact import compact_config, reuse_completed, select_reusable


def configuration():
    shortlist = {"finalists": [dict(strategy=s, density_weight=.25, value_margin=.25,
                                   minimum_density_gain=.1)
                              for s in ("trajectory_value_density", "trajectory_value_density_aligned")]}
    original, _ = build(shortlist, method("winner", "trajectory_medoid", 1.))
    return original, compact_config(original)


def test_counts_coverage_and_frozen_protocol():
    original, compact = configuration()
    original_jobs = {j["name"]: j for j in original["profiles"]["full"]["jobs"]}
    jobs = compact["profiles"]["compact"]["jobs"]
    assert len(jobs) == len({j["name"] for j in jobs}) == 360
    counts = {}
    groups = {}
    for job in jobs:
        source = original_jobs[job["source_job_name"]]
        position = job["kind"] == "pro_position_planning_grid"
        inits = [1] if position else range(2, 7)
        assert job["init_state_ids"] == ("1" if position else "2-6")
        assert job["name"] == launcher._safe_name(job["name"])
        assert "gpu_slot" not in job
        for key in ("strategy_lambdas", "uncertainty_seeds", "planning_value_margin",
                    "planning_uncertainty_margin", "suites", "task_ids", "case_id"):
            assert job[key] == source[key]
        for pair, init in enumerate(inits):
            assert job["base_seed"] + pair * 10000 == source["base_seed"] + init * 10000
        label = job["name"].split("_t", 1)[1].split("_", 1)[1]
        factor = job["name"].split("_", 1)[0]
        counts[label, factor] = counts.get((label, factor), 0) + len(inits)
        groups.setdefault((job["case_id"], job["task_ids"]), []).append(job)
    assert sum(counts.values()) == 600
    assert {label for label, _ in counts} == {"first", "max_value", "winner"}
    for label in ("first", "max_value", "winner"):
        assert [counts[label, f] for f in ("object", "environment", "position")] == [50, 50, 100]
    assert len(groups) == 120
    assert all(len(g) == 3 and len({j["base_seed"] for j in g}) == 1 for g in groups.values())
    assert compact["defaults"]["num_open_loop_steps"] == 16
    assert compact["defaults"]["dynamic_gpu_queue"] is True
    assert {k: v for k, v in compact["defaults"].items() if k != "dynamic_gpu_queue"} == original["defaults"]


def trace_and_job():
    _, config = configuration()
    job = next(j for j in config["profiles"]["compact"]["jobs"] if j["name"] == "object_t0_first")
    trace = pd.DataFrame([dict(
        init_state_id=i, task_id=0, suite=job["suites"], case_id=job["case_id"],
        planning_strategy="first", planning_risk_lambda=0., num_open_loop_steps=16,
        prediction_mode="parallel", num_denoising_steps_action=5, num_samples=1,
        rollout_seed=job["base_seed"] + (i - 2) * 10000,
        rollout_id=0, pair_id=i, query_idx=q, num_queries=2, success=i % 2 == 0,
        t=16*q, t_after=16*(q+1), executed_steps=16, final_t=32,
    ) for i in range(10) for q in range(2)])
    return trace, job


def test_reuse_preserves_outcomes_and_original_identity():
    trace, job = trace_and_job()
    selected = select_reusable(trace, job)
    assert set(selected.init_state_id) == set(range(2, 7))
    assert set(selected.success) == {False, True}
    assert selected.source_pair_id.equals(selected.init_state_id)
    assert selected.pair_id.eq(selected.init_state_id - 2).all()
    assert trace.pair_id.equals(trace.init_state_id)


@pytest.mark.parametrize("change,message", [
    (lambda d: d[d.init_state_id != 4], "every requested init"),
    (lambda d: d.assign(rollout_seed=0), "seed mismatch"),
    (lambda d: d[d.query_idx != 1], "incomplete"),
    (lambda d: d.assign(num_open_loop_steps=8), "protocol mismatch"),
    (lambda d: d.assign(planning_strategy="max_value"), "selector mismatch"),
    (lambda d: d.assign(t_after=16), "Truncated"),
])
def test_bad_reusable_trace_rejected(change, message):
    trace, job = trace_and_job()
    with pytest.raises(ValueError, match=message):
        select_reusable(change(trace), job)


def test_reuse_does_not_touch_running_campaign(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "reuse_manifest.json").write_text('[{"episodes": 5}]')
    assert reuse_completed({}, tmp_path / "missing", tmp_path) == 5


def test_shared_queue_waits_before_claiming_job(monkeypatch, tmp_path):
    pending = queue.Queue()
    pending.put({"name": "example"})
    free = iter([False, True])
    events = []
    monkeypatch.setattr(launcher, "gpu_is_free", lambda _: next(free))
    monkeypatch.setattr(launcher.time, "sleep", lambda _: events.append(("waiting", pending.qsize())))
    monkeypatch.setattr(launcher, "run_job", lambda *args: {"job": args[0]["name"], "gpu": args[3]})
    result = launcher.run_shared_gpu_queue(pending, "test", tmp_path, "3", False,
                                          lambda job, gpu: events.append((job["name"], gpu)))
    assert events == [("waiting", 1), ("example", "3")]
    assert result == [{"job": "example", "gpu": "3"}]
    assert pending.unfinished_tasks == 0


def test_busy_gpu_does_not_hold_work_from_other_workers(monkeypatch, tmp_path):
    pending = queue.Queue()
    pending.put({"name": "example"})
    monkeypatch.setattr(launcher, "gpu_is_free", lambda _: False)

    def other_worker(_):
        pending.get_nowait()
        pending.task_done()

    monkeypatch.setattr(launcher.time, "sleep", other_worker)
    assert launcher.run_shared_gpu_queue(pending, "test", tmp_path, "5", False, None) == []


@pytest.mark.parametrize("output,expected", [("4, 0\n", True), ("7000, 0\n", False), ("4, 100\n", False)])
def test_gpu_availability(monkeypatch, output, expected):
    monkeypatch.setattr(launcher.subprocess, "check_output",
                        lambda command, **kwargs: "" if "--query-compute-apps=pid" in command else output)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: None)
    assert launcher.gpu_is_free("3") is expected

import json
import time

import watch


def setup_plan(tmp_path, monkeypatch, statuses):
    monkeypatch.setattr(watch, "HERE", tmp_path)
    stages = []
    for i, state in enumerate(statuses):
        folder = tmp_path / f"s{i}"
        folder.mkdir()
        stages.append(str(folder))
        if state is not None:
            (folder / "sequence_status.json").write_text(json.dumps(state))
    (tmp_path / "plan.json").write_text(json.dumps(dict(
        stages=stages, supervisor_pid=999999999, deadline_epoch=time.time() + 100)))


def test_completed_despite_exited_supervisor(tmp_path, monkeypatch):
    setup_plan(tmp_path, monkeypatch, [dict(status="completed", matched_cases=199)] * 3)
    result = watch.status()
    assert result["status"] == "completed"
    assert result["matched_main_cases"] == 597
    assert result["supervisor_alive"] is False


def test_partial_is_not_completed(tmp_path, monkeypatch):
    setup_plan(tmp_path, monkeypatch, [dict(status="partial", matched_cases=33), None, None])
    result = watch.status()
    assert result["status"] == "stopped"
    assert result["matched_main_cases"] == 33


def test_single_stage_shortened_queue(tmp_path, monkeypatch):
    setup_plan(tmp_path, monkeypatch, [dict(status="completed", matched_cases=199)])
    result = watch.status()
    assert result["status"] == "completed"
    assert result["expected_main_cases"] == 199
    assert result["matched_main_cases"] == 199


def test_dead_supervisor_not_misreported_running(tmp_path, monkeypatch):
    setup_plan(tmp_path, monkeypatch, [dict(status="running", matched_cases=1), None, None])
    assert watch.status()["status"] == "stopped"


def test_frozen_auditor_load():
    auditor = watch.load_auditor()
    assert auditor.OPS == watch.HERE

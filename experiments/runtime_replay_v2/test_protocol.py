import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

import run_v2


def test_replica_config_preserves_tasks_methods_and_assets():
    source = json.loads((run_v2.BASE / "config.json").read_text())
    original = copy.deepcopy(source)
    result = run_v2.build_config(source, "test_v2", 10_000_000, {"test": "hash"})
    assert source == original
    regression = result["jobs"][0]
    assert regression["id"] == "parity_environment__t3_i2"
    assert regression["rollout_seed"] == 52_320_000
    assert regression["phase"] == "smoke"
    for old, new in zip(source["jobs"], result["jobs"][1:]):
        assert new == dict(old, rollout_seed=old["rollout_seed"] + 10_000_000)
    for key in ("arms", "event_parameters", "assets", "K", "prediction_mode", "denoising_steps"):
        assert result[key] == source[key]
    assert len([j for j in result["jobs"] if j["phase"] == "main"]) == 199
    assert result["runtime_snapshot_version"] == 2
    assert result["hours"] == 0


@pytest.mark.parametrize("deadline", [None, "2026-09-15T09:00:00+03:00", "2099-01-01T12:00:00"])
def test_reject_implicit_or_expired_deadline(deadline):
    with pytest.raises(ValueError):
        run_v2.future_deadline(deadline)


def test_explicit_future_deadline():
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert run_v2.future_deadline(future.isoformat()) == future.timestamp()


def test_collector_only_redirect():
    cmd = ["bash", "-ec", "shell program", str(run_v2.ROOT / "scripts/collect_p3_benchmark.py"), "--batch", "x.json"]
    expected = list(cmd)
    expected[3] = str(run_v2.HERE / "collect_v2.py")
    assert run_v2.redirected(cmd) == expected
    assert cmd[3].endswith("scripts/collect_p3_benchmark.py")


def test_existing_reporter_redirect_and_no_other_redirect():
    cmd = ["python", str(run_v2.ROOT / "scripts/analyze_p3_benchmark.py"), "--campaign", "test"]
    assert run_v2.redirected(cmd) == ["python", str(run_v2.REPORTER), "--campaign", "test"]
    unrelated = ["python", "unrelated.py", "--flag"]
    assert run_v2.redirected(unrelated) == unrelated


def test_old_configs_cannot_use_new_worker():
    with pytest.raises(ValueError, match="fresh v2"):
        run_v2.validate_v2({"runtime_snapshot_version": 1})

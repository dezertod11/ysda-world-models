import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import status_libero_campaign as status


def planning_job(name: str, gpu: str = "2", rollouts: int = 2) -> dict:
    return {
        "name": name,
        "gpu": gpu,
        "environment": {
            "LIBERO_PRO_PLANNING_GRID_MAX_ROLLOUTS_PER_INIT": str(rollouts),
            "LIBERO_PRO_PLANNING_GRID_SUITES": "suite",
            "LIBERO_PRO_PLANNING_GRID_TASK_IDS": "0",
            "LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS": "0",
            "LIBERO_PRO_PLANNING_GRID_STRATEGY_LAMBDAS": "max_value:0 action_l1:1",
        },
    }


def test_expected_rollouts_supports_ranges_and_strategy_count():
    job = planning_job("case", rollouts=3)
    job["environment"]["LIBERO_PRO_PLANNING_GRID_TASK_IDS"] = "0-2"
    job["environment"]["LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS"] = "0,2"

    assert status.expected_job_rollouts(job) == 3 * 3 * 2 * 2


def test_expected_rollouts_uses_counterfactual_snapshot_target():
    job = {
        "name": "vof",
        "environment": {
            "LIBERO_PRO_VOF_TARGET_DECISION_STATES": "100",
            "LIBERO_PRO_VOF_ROLLOUTS_PER_INIT": "4",
        },
    }

    assert status.expected_job_rollouts(job) == 100


def test_completed_campaign_counts_strategy_executions(tmp_path, monkeypatch):
    campaign = tmp_path / "status_test_campaign"
    (campaign / "runs").mkdir(parents=True)
    (campaign / "completed").mkdir()
    manifest = {
        "run_prefix": campaign.name,
        "profile": "test",
        "status": "completed",
        "created_at": "2026-08-21T10:00:00",
        "finished_at": "2026-08-21T10:05:00",
        "jobs": [planning_job("case")],
    }
    (campaign / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    marker = {
        "status": "completed",
        "started_at": "2026-08-21T10:00:00",
        "finished_at": "2026-08-21T10:05:00",
    }
    (campaign / "completed" / "case.json").write_text(json.dumps(marker), encoding="utf-8")
    for strategy in ("max_value", "action_l1"):
        frame = pd.DataFrame(
            {
                "pair_id": [0, 0, 0, 0],
                "rollout_id": [0, 0, 1, 1],
                "query_idx": [0, 1, 0, 1],
                "success": [True, True, False, False],
            }
        )
        frame.to_csv(
            campaign / "runs" / f"{campaign.name}__case__{strategy}__query_traces.csv",
            index=False,
        )
    monkeypatch.setattr(status, "_active_processes", lambda _: ())

    result = status.inspect_campaign(campaign, status.TraceCounter())

    assert result.state == "READY"
    assert result.completed_jobs == result.total_jobs == 1
    assert result.expected_rollouts == 4
    assert result.trace_stats.rollouts == 4
    assert result.trace_stats.successes == 2
    assert result.trace_stats.failures == 2


def test_eta_uses_completed_job_rate_and_gpu_queue():
    completed = planning_job("completed", gpu="2", rollouts=5)
    pending = planning_job("pending", gpu="2", rollouts=5)
    markers = {
        "completed": {
            "started_at": "2026-08-21T10:00:00",
            "finished_at": "2026-08-21T10:10:00",
        }
    }
    job_stats = {
        "completed": status.TraceStats(rollouts=10),
        "pending": status.TraceStats(),
    }

    eta = status._estimate_eta(
        [completed, pending],
        markers,
        job_stats,
        {"completed": None, "pending": None},
        datetime.fromisoformat("2026-08-21T10:10:00"),
    )

    assert eta == pytest.approx(600.0)


def test_counterfactual_feedback_rows_are_counted_as_snapshots(tmp_path):
    campaign = tmp_path / "vof_campaign"
    (campaign / "runs").mkdir(parents=True)
    frame = pd.DataFrame({"snapshot_id": ["a", "b", "c"], "local_vof": [0.0, 1.0, -1.0]})
    frame.to_parquet(campaign / "runs" / "vof__feedback_pairs.parquet", index=False)

    paths = status._preferred_trace_paths(campaign)
    stats = status._sum_stats(status.TraceCounter().count(path) for path in paths)

    assert len(paths) == 1
    assert stats.rollouts == 3

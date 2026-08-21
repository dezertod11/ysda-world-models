import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_temporal_overlap_campaign import (
    analyze_campaign,
    detector_table,
    event_detection_table,
    prepare_traces,
)


def synthetic_traces() -> pd.DataFrame:
    rows = []
    for rollout_id, score in enumerate((0.1, 0.2, 0.3, 0.4)):
        rows.append(
            {
                "source_run": "calibration",
                "suite": "id_suite",
                "case_id": "calibration_case",
                "task_id": 0,
                "init_state_id": 0,
                "pair_id": 0,
                "rollout_id": rollout_id,
                "rollout_seed": rollout_id,
                "query_idx": 1,
                "t": 8,
                "success": True,
                "experiment_split": "calibration",
                "overlap_valid": True,
                "pre_critical_event_query": True,
                "critical_event_t": -1,
                "steps_to_first_critical_event": -1,
                "critical_event_within_8": False,
                "critical_event_within_16": False,
                "critical_event_within_32": False,
                "overlap_selected_rmse": score,
            }
        )

    for rollout_id, event, score in ((0, True, 0.9), (1, False, 0.2)):
        rows.append(
            {
                "source_run": "holdout",
                "suite": "ood_suite",
                "case_id": "holdout_case",
                "task_id": 0,
                "init_state_id": 0,
                "pair_id": 0,
                "rollout_id": rollout_id,
                "rollout_seed": 100 + rollout_id,
                "query_idx": 1,
                "t": 8,
                "success": not event,
                "experiment_split": "holdout",
                "overlap_valid": True,
                "pre_critical_event_query": True,
                "critical_event_t": 16 if event else -1,
                "steps_to_first_critical_event": 8 if event else -1,
                "critical_event_within_8": event,
                "critical_event_within_16": event,
                "critical_event_within_32": event,
                "overlap_selected_rmse": score,
            }
        )
    return pd.DataFrame(rows)


def test_frozen_calibration_threshold_detects_holdout_event():
    traces = prepare_traces(synthetic_traces())
    detector = detector_table(traces, ["overlap_selected_rmse"], [8], alpha=0.25)
    row = detector.iloc[0]

    assert row["calibration_queries"] == 4
    assert row["threshold"] == pytest.approx(0.4)
    assert row["auroc"] == 1.0
    assert row["auprc"] == 1.0
    assert row["tpr"] == 1.0
    assert row["fpr"] == 0.0

    events = event_detection_table(traces, detector, ["overlap_selected_rmse"], [8])
    event = events.iloc[0]
    assert event["event_detection_rate"] == 1.0
    assert event["median_lead_steps"] == 8
    assert event["false_alarm_episode_rate"] == 0.0


def test_campaign_analysis_writes_reusable_tables(tmp_path):
    campaign_dir = tmp_path / "campaign"
    run_dir = campaign_dir / "runs"
    run_dir.mkdir(parents=True)
    synthetic_traces().drop(columns=["source_run"]).to_parquet(
        run_dir / "synthetic__query_traces.parquet", index=False
    )

    outputs = analyze_campaign(
        campaign_dir, campaign_dir / "analysis", horizons=(8,), alpha=0.25
    )

    assert outputs["query_detector_metrics"].is_file()
    assert outputs["event_detection_metrics"].is_file()
    assert outputs["report"].is_file()

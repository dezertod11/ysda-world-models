from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_object_q4_scheduled_controller import (
    BASELINE,
    METHOD,
    prefix_integrity,
    validate_schedule,
)


ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, object]:
    return {
        "scheduled_requery_query_idx": 4,
        "sim_state_max_abs_tolerance": 1e-9,
        "candidate_value_max_abs_tolerance": 1e-5,
        "candidate_first_action_max_abs_tolerance": 1e-5,
    }


def _trace() -> pd.DataFrame:
    rows = []
    for method in [BASELINE, METHOD]:
        for query_idx in range(7):
            is_trigger = method == METHOD and query_idx == 4
            is_completion = method == METHOD and query_idx == 5
            active = is_trigger or is_completion
            if method == BASELINE:
                t = query_idx * 16
            elif query_idx <= 4:
                t = query_idx * 16
            elif query_idx == 5:
                t = 72
            else:
                t = 80 + (query_idx - 6) * 16
            rows.append(
                {
                    "state_key": "state0",
                    "method": method,
                    "query_idx": query_idx,
                    "t": t,
                    "sim_state_json": json.dumps([query_idx, 0.5]),
                    "candidate_values_json": json.dumps([0.1, 0.2]),
                    "candidate_first_actions_json": json.dumps(
                        [[0.0] * 7, [1.0] * 7]
                    ),
                    "max_value_sample_idx": 1,
                    "planning_selected_open_loop_steps": 8 if active else 16,
                    "planning_requery_triggered": is_trigger,
                    "planning_scheduled_requery_active": active,
                    "planning_scheduled_requery_completion": is_completion,
                }
            )
    return pd.DataFrame(rows)


def test_deployment_config_has_exact_frozen_schedule() -> None:
    config = json.loads(
        (
            ROOT
            / "experiments/configs/libero_campaign_object_q4_scheduled_controller_20260901.json"
        ).read_text()
    )
    jobs = config["profiles"]["object_q4_scheduled_controller"]["jobs"]
    defaults = config["defaults"]

    assert len(jobs) == 5
    assert [job["init_state_ids"] for job in jobs] == [
        "0-9",
        "10-19",
        "20-29",
        "30-39",
        "40-49",
    ]
    assert defaults["strategy_lambdas"] == (
        "max_value:0 max_value_scheduled_requery:0"
    )
    assert defaults["planning_scheduled_requery_query_idx"] == 4
    assert defaults["planning_short_open_loop_steps"] == 8


def test_prefix_integrity_and_schedule_accept_exact_pair() -> None:
    traces = _trace()
    integrity = prefix_integrity(traces, _manifest())

    assert len(integrity) == 1
    assert bool(integrity.iloc[0]["strict_prefix"]) is True
    assert validate_schedule(traces, _manifest()) is True


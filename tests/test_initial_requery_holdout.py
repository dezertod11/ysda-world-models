from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_initial_requery_holdout import (
    BASELINE,
    METHOD,
    method_from_strategy,
    paired_analysis,
)


ROOT = Path(__file__).resolve().parents[1]


def test_initial_requery_config_is_independent_and_paired() -> None:
    config = json.loads(
        (
            ROOT
            / "experiments/configs/libero_campaign_initial_requery_holdout.json"
        ).read_text()
    )
    jobs = config["profiles"]["initial_requery_holdout"]["jobs"]
    defaults = config["defaults"]

    assert [job["task_ids"] for job in jobs] == ["8", "8", "8", "9", "9"]
    assert [job["init_state_ids"] for job in jobs] == [
        "20-29",
        "30-39",
        "40-49",
        "20-34",
        "35-49",
    ]
    assert {job["strategy_lambdas"] for job in jobs} == {
        "max_value:0 max_value_initial_requery:0"
    }
    assert {job["gpu_slot"] for job in jobs} == {0, 1, 2, 3, 4}
    assert defaults["max_rollouts"] == 1
    assert defaults["num_open_loop_steps"] == 16
    assert defaults["planning_short_open_loop_steps"] == 8
    assert defaults["experiment_split"] == "generalization"


def test_initial_requery_method_mapping() -> None:
    assert method_from_strategy("max_value") == BASELINE
    assert method_from_strategy("max_value_initial_requery") == METHOD


def test_paired_analysis_counts_rescues_and_harms() -> None:
    rows = []
    outcomes = [(False, True), (True, True), (True, False), (False, True)]
    for index, (baseline, method) in enumerate(outcomes):
        task = 8 if index < 2 else 9
        key = f"task{task}|state{index}"
        common = {
            "suite": "libero_object_env",
            "task_id": task,
            "init_state_id": 20 + index,
            "rollout_seed": 100 + index,
            "state_key": key,
        }
        rows.append({**common, "method": BASELINE, "success": baseline})
        rows.append({**common, "method": METHOD, "success": method})

    _paired, contrast = paired_analysis(pd.DataFrame(rows))
    result = contrast.iloc[0]

    assert int(result["rescues"]) == 2
    assert int(result["harms"]) == 1
    assert float(result["delta_success_rate"]) == 0.25


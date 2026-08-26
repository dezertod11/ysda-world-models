import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_pro_object_horizon_controls import method_from_trace, score_tables
from compare_real_planning_strategy_runs import _read_trace
from run_libero_experiment_campaign import expand_jobs, load_campaign


def test_p0_campaign_expands_to_24_jobs_with_matched_seeds():
    campaign = load_campaign(
        ROOT / "experiments/configs/libero_campaign_pro_object_horizon_controls.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["pro_object_horizon_controls_p0"], campaign["defaults"]
    )

    assert len(jobs) == 24
    fixed = next(job for job in jobs if job["name"] == "position_max_value_h8_x0p1")
    adaptive = next(job for job in jobs if job["name"] == "position_adaptive_controls_x0p1")
    assert fixed["base_seed"] == adaptive["base_seed"] == 2300000
    assert fixed["num_open_loop_steps"] == 8
    assert adaptive["num_open_loop_steps"] == 16


def test_method_mapping_separates_selection_from_feedback_controls():
    fixed = pd.DataFrame(
        {"planning_strategy": ["max_value"], "num_open_loop_steps": [8]}
    )
    horizon = pd.DataFrame(
        {
            "planning_strategy": ["max_value_disagreement_requery"],
            "num_open_loop_steps": [16],
        }
    )
    random = pd.DataFrame(
        {
            "planning_strategy": ["max_value_random_requery_43"],
            "num_open_loop_steps": [16],
        }
    )

    assert method_from_trace(fixed) == "maxV-H8"
    assert method_from_trace(horizon) == "horizon-only"
    assert method_from_trace(random) == "random-H8"


def test_position_score_macro_averages_shift_levels():
    rows = [
        {
            "method": "maxV-H16",
            "factor": "Position",
            "task_id": 0,
            "position_level": "x0.1",
            "success": True,
        },
        {
            "method": "maxV-H16",
            "factor": "Position",
            "task_id": 0,
            "position_level": "x0.5",
            "success": False,
        },
    ]
    factors, _ = score_tables(pd.DataFrame(rows))

    score = factors.loc[factors["factor"].eq("Position"), "success_rate"].iloc[0]
    assert score == 0.5


def test_comparison_reader_accepts_parquet_only(tmp_path):
    expected = pd.DataFrame({"query_idx": [0, 1], "success": [False, True]})
    expected.to_parquet(tmp_path / "parquet_run__query_traces.parquet", index=False)

    actual = _read_trace(tmp_path, "parquet_run")

    pd.testing.assert_frame_equal(actual, expected)

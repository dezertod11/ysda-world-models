import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_boundary_case_screening import episode_table, plot_cases, summarize_cases
from run_libero_experiment_campaign import validate_job_inputs


def synthetic_query_traces() -> pd.DataFrame:
    rows = []
    for task_id, outcomes in ((0, (True, True, False, False)), (1, (True,) * 4)):
        for rollout_id, success in enumerate(outcomes):
            for query_idx in range(2):
                rows.append(
                    {
                        "source_trace": "synthetic.parquet",
                        "suite": "libero_test",
                        "task_id": task_id,
                        "init_state_id": 0,
                        "pair_id": task_id,
                        "rollout_id": rollout_id,
                        "rollout_seed": 100 + rollout_id,
                        "query_idx": query_idx,
                        "success": success,
                        "final_t": 16,
                        "task_description": f"active task {task_id}",
                        "benchmark_task_description": f"old task {task_id}",
                        "task_instruction_source": "bddl",
                        "task_instruction_differs_from_benchmark": True,
                        "target_drop_candidate": not success and rollout_id == 2,
                        "successful_target_release": success,
                    }
                )
    return pd.DataFrame(rows)


def test_boundary_summary_ranks_confirmed_mixed_case_first():
    episodes = episode_table(synthetic_query_traces())
    summary = summarize_cases(episodes)

    mixed = summary.iloc[0]
    assert mixed["task_id"] == 0
    assert mixed["screen_status"] == "confirmed_mixed"
    assert mixed["num_success"] == 2
    assert mixed["num_failed"] == 2
    assert mixed["boundary_balance"] == pytest.approx(1.0)
    assert mixed["target_drop_failures"] == 1
    assert summary.iloc[1]["screen_status"] == "all_success"


def test_boundary_plot_accepts_zero_and_one_success_rates(tmp_path):
    summary = summarize_cases(episode_table(synthetic_query_traces()))
    output = tmp_path / "rates.png"

    plot_cases(summary, output)

    assert output.is_file()


def test_campaign_rejects_unknown_experiment_split_before_launch():
    job = {
        "name": "bad_split",
        "kind": "pro_paired",
        "task_ids": "0",
        "experiment_split": "screening",
    }
    with pytest.raises(ValueError, match="invalid experiment_split"):
        validate_job_inputs(job)

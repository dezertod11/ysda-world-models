import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_pro_object_baseline_benchmark import (
    METHOD_LABELS,
    analyze,
    exact_mcnemar_p,
    score_tables,
)
from run_libero_experiment_campaign import build_job, expand_jobs, load_campaign


def test_position_planning_sweep_expands_levels_and_keeps_matched_seeds():
    profile = {
        "jobs": [
            {
                "name": "position_max_value",
                "kind": "pro_position_planning_sweep",
                "position_levels": ["x0.1", "y0.5"],
                "base_seed": 2300000,
            }
        ]
    }
    jobs = expand_jobs(profile, {})

    assert [job["kind"] for job in jobs] == [
        "pro_position_planning_grid",
        "pro_position_planning_grid",
    ]
    assert [job["name"] for job in jobs] == [
        "position_max_value_x0p1",
        "position_max_value_y0p5",
    ]
    assert [job["base_seed"] for job in jobs] == [2300000, 2310000]


def test_position_planning_job_uses_private_materialized_variant(tmp_path):
    campaign = load_campaign(
        ROOT / "experiments/configs/libero_campaign_pro_object_baselines.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["pro_object_baseline_pilot"], campaign["defaults"]
    )
    job = next(item for item in jobs if item["name"] == "position_max_value_x0p1")

    commands, env, _ = build_job(job, "test_run", tmp_path)

    assert commands[0][-2:] == [
        str(ROOT / "scripts/prepare_libero_pro_position_variant.sh"),
        "x0.1",
    ]
    assert commands[1][-1] == str(ROOT / "scripts/run_libero_pro_planning_strategy_grid.sh")
    assert env["LIBERO_PRO_POSITION_LEVEL"] == "x0.1"
    assert env["LIBERO_BDDL_FILES_PATH"].endswith("/.runtime/libero_pro_position/x0.1/bddl_files")
    assert env["LIBERO_INIT_STATES_PATH"].endswith("/.runtime/libero_pro_position/x0.1/init_files")


def test_environment_job_prepares_shared_deterministic_variant(tmp_path):
    campaign = load_campaign(
        ROOT / "experiments/configs/libero_campaign_pro_object_baselines.json"
    )
    jobs = expand_jobs(
        campaign["profiles"]["pro_object_baseline_pilot"], campaign["defaults"]
    )
    job = next(item for item in jobs if item["name"] == "environment_max_value")

    commands, env, _ = build_job(job, "test_run", tmp_path)

    assert commands[0][-3:] == [
        str(ROOT / "scripts/prepare_libero_pro_environment_variant.sh"),
        "10",
        "20260825",
    ]
    assert commands[1][-1] == str(ROOT / "scripts/run_libero_pro_planning_strategy_grid.sh")
    assert env["LIBERO_BDDL_FILES_PATH"].endswith("/.runtime/libero_pro_environment/bddl_files")
    assert env["LIBERO_INIT_STATES_PATH"].endswith("/.runtime/libero_pro_environment/init_files")


def test_position_score_is_equal_weight_macro_average_over_levels():
    method = METHOD_LABELS["first"]
    rows = [
        {
            "method": method,
            "factor": "Position",
            "task_id": 0,
            "position_level": "x0.1",
            "success": True,
        }
    ]
    rows.extend(
        {
            "method": method,
            "factor": "Position",
            "task_id": 0,
            "position_level": "x0.5",
            "success": False,
        }
        for _ in range(9)
    )
    _, _, scores = score_tables(pd.DataFrame(rows))

    position = scores.loc[scores["factor"].eq("Position")].iloc[0]
    assert position["success_rate"] == pytest.approx(0.5)
    assert position["successes"] == 1
    assert position["episodes"] == 10


def test_exact_mcnemar_uses_only_discordant_pairs():
    assert exact_mcnemar_p(0, 0) == 1.0
    assert exact_mcnemar_p(8, 0) == pytest.approx(2.0 / 256.0)


def test_end_to_end_analyzer_writes_leaderboard_and_pairing(tmp_path):
    campaign_dir = tmp_path / "campaign"
    run_dir = campaign_dir / "runs"
    run_dir.mkdir(parents=True)
    jobs = []
    strategies = {
        "first": False,
        "max_value": True,
        "disagreement_requery_action": True,
    }
    factors = {
        "Object": ("libero_object_object", ""),
        "Position": ("libero_object_temp", "x0.1"),
        "Environment": ("libero_object_env", ""),
    }
    for factor, (suite, level) in factors.items():
        for strategy, success in strategies.items():
            prefix = f"{factor.lower()}_{strategy}"
            environment = {
                "LIBERO_PRO_PLANNING_GRID_PREFIX": prefix,
                "LIBERO_PRO_PLANNING_GRID_SUITES": suite,
                "LIBERO_PRO_PLANNING_GRID_TASK_IDS": "0",
                "LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS": "0",
                "LIBERO_PRO_PLANNING_GRID_MAX_ROLLOUTS_PER_INIT": "1",
                "LIBERO_PRO_PLANNING_GRID_STRATEGY_LAMBDAS": f"{strategy}:0",
            }
            if level:
                environment["LIBERO_PRO_POSITION_LEVEL"] = level
            jobs.append({"name": prefix, "environment": environment})
            pd.DataFrame(
                [
                    {
                        "suite": suite,
                        "task_id": 0,
                        "init_state_id": 0,
                        "rollout_seed": 123,
                        "query_idx": 0,
                        "success": success,
                        "planning_strategy": strategy,
                        "num_samples": 1 if strategy == "first" else 4,
                        "final_t": 16,
                        "planning_requery_triggered": strategy == "disagreement_requery_action",
                    }
                ]
            ).to_csv(run_dir / f"{prefix}__query_traces.csv", index=False)
    (campaign_dir / "manifest.json").write_text(
        json.dumps({"jobs": jobs}), encoding="utf-8"
    )

    outputs = analyze(campaign_dir, campaign_dir / "analysis")
    leaderboard = pd.read_csv(outputs["leaderboard"]).set_index("method")
    comparisons = pd.read_csv(outputs["comparisons"])

    assert leaderboard.loc[METHOD_LABELS["first"], "Mean"] == 0.0
    assert leaderboard.loc[METHOD_LABELS["max_value"], "Mean"] == 1.0
    assert len(comparisons) == 9
    assert outputs["plot"].is_file()

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analyze_frozen_ranker_closed_loop import analyze


def write_trace(
    runs: Path,
    *,
    factor: str,
    strategy: str,
    success: bool,
    model_sha: str,
) -> None:
    rows = []
    for pair_id in range(2):
        values = [float(index) for index in range(6)]
        scores = [float(5 - index) for index in range(6)]
        features = [[float(index)] * 11 for index in range(6)]
        rows.append(
            {
                "factor": factor,
                "case_id": f"case-{factor}",
                "suite": f"suite-{factor}",
                "task_id": pair_id,
                "init_state_id": 0,
                "pair_id": pair_id,
                "rollout_id": 0,
                "rollout_seed": 1000 + pair_id,
                "query_idx": 0,
                "planning_strategy": strategy,
                "planning_frozen_ranker_factor": factor,
                "planning_frozen_ranker_payload_sha256": model_sha,
                "candidate_values_json": json.dumps(values),
                "candidate_frozen_ranker_scores_json": json.dumps(scores),
                "candidate_frozen_ranker_features_json": json.dumps(features),
                "candidate_first_actions_json": json.dumps(values),
                "selected_sample_idx": 5 if strategy == "max_value" else 0,
                "max_value_sample_idx": 5,
                "max_value_selected": True,
                "max_value": 5.0,
                "selected_value": 5.0,
                "num_samples": 6,
                "success": success,
                "final_t": 16,
                "failure_type": "success" if success else "timeout",
            }
        )
    pd.DataFrame(rows).to_parquet(
        runs / f"{factor}__{strategy}__query_traces.parquet", index=False
    )


def test_closed_loop_analysis_passes_complete_positive_paired_result(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    runs = campaign / "runs"
    runs.mkdir(parents=True)
    model_sha = "frozen-sha"
    for factor in ("Environment", "Object", "Position"):
        write_trace(
            runs,
            factor=factor,
            strategy="max_value",
            success=False,
            model_sha=model_sha,
        )
        write_trace(
            runs,
            factor=factor,
            strategy="frozen_factor_ridge",
            success=True,
            model_sha=model_sha,
        )

    output = tmp_path / "analysis"
    result = analyze(
        campaign,
        output,
        draws=200,
        seed=7,
        expected_pairs_per_factor=2,
        expected_model_sha=model_sha,
    )

    assert result["paired_rollouts"] == 6
    assert result["gate"]["passed"] is True
    assert (output / "paired_terminal_success.png").is_file()
    assert (output / "paired_sr_delta_ci.png").is_file()
    assert (output / "candidate_preference_heatmap.png").is_file()
    factors = pd.read_csv(output / "paired_factor_summary.csv")
    assert factors["sr_delta"].eq(1.0).all()
    preference = pd.read_csv(output / "candidate_preference_summary.csv")
    assert set(preference["factor"]) == {"Environment", "Object", "Position"}
    assert preference["mean_selected_minus_max_value_z"].lt(0.0).all()

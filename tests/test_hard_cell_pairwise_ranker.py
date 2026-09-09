from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.hard_cell_pairwise_ranker import FEATURES, evaluate_ranker, fit_ranker


def _candidate_rows(init_states: range, split: str) -> pd.DataFrame:
    rows = []
    for factor in ("Object", "Position"):
        for init_state in init_states:
            for candidate_idx in range(8):
                successful = candidate_idx == 0
                row = {
                    "snapshot_id": f"{factor}_{init_state}",
                    "suite": (
                        "libero_object_object"
                        if factor == "Object"
                        else "libero_object_temp"
                    ),
                    "case_id": (
                        "pairwise_object_task0"
                        if factor == "Object"
                        else "pairwise_position_y0p3_task0"
                    ),
                    "factor": factor,
                    "task_id": 0,
                    "init_state_id": init_state,
                    "query_idx": 0,
                    "candidate_idx": candidate_idx,
                    "candidate_value": 1.0 if candidate_idx == 1 else 0.1,
                    "candidate_parallel_value": 1.0 if candidate_idx == 1 else 0.1,
                    "candidate_autoregressive_value": (
                        1.0 if successful else 0.05 * candidate_idx
                    ),
                    "terminal_available": True,
                    "terminal_success": successful,
                    "terminal_utility_v1": 3.0 if successful else 0.0,
                    "terminal_failure_type": "success" if successful else "timeout_no_goal",
                    "experiment_split": split,
                }
                for feature_index, feature in enumerate(FEATURES):
                    if feature in {
                        "candidate_parallel_value",
                        "candidate_autoregressive_value",
                        "autoregressive_value_delta",
                        "autoregressive_future_proprio_l2",
                    }:
                        continue
                    row[feature] = (
                        2.0 + 0.01 * feature_index
                        if successful
                        else -0.1 * candidate_idx + 0.01 * feature_index
                    )
                for dimension in range(9):
                    row[f"candidate_predicted_future_proprio_d{dimension}"] = float(
                        dimension
                    )
                    row[
                        f"candidate_autoregressive_predicted_future_proprio_d{dimension}"
                    ] = float(dimension) + (1.0 if successful else 0.0)
                rows.append(row)
    return pd.DataFrame(rows)


def test_pairwise_ranker_fits_and_rescues_untouched_states(tmp_path: Path) -> None:
    development = _candidate_rows(range(10, 25), "development")
    calibration = _candidate_rows(range(25, 30), "calibration")
    development_calibration = pd.concat([development, calibration], ignore_index=True)
    devcal_path = tmp_path / "devcal__candidate_outcomes.parquet"
    development_calibration.to_parquet(devcal_path, index=False)
    model_path = tmp_path / "frozen_model.json"

    fit_payload = fit_ranker([devcal_path], model_path, tmp_path / "fit")

    assert fit_payload["opportunity_gate"] == "PASS"
    assert model_path.is_file()

    holdout = _candidate_rows(range(30, 40), "holdout")
    holdout_path = tmp_path / "holdout__candidate_outcomes.parquet"
    holdout.to_parquet(holdout_path, index=False)
    holdout_payload = evaluate_ranker(
        [holdout_path], model_path, tmp_path / "holdout_analysis"
    )

    assert holdout_payload["gate"] == "PASS"
    assert holdout_payload["maxv_sr"] == 0.0
    assert holdout_payload["selected_sr"] == 1.0
    assert holdout_payload["rescues"] == 20
    assert holdout_payload["harms"] == 0

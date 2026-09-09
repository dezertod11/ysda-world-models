from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.analyze_autoregressive_value_ranking import (
    analyze,
    compare_candidates,
    summarize,
)


def _candidates(mode: str) -> pd.DataFrame:
    rows = []
    for init_state, successes in ((5, {1}), (6, {0, 1})):
        for candidate_idx in range(2):
            parallel_value = [0.9, 0.1] if init_state == 5 else [0.8, 0.2]
            autoregressive_value = [0.1, 0.9] if init_state == 5 else [0.8, 0.2]
            row = {
                "condition": "Object",
                "factor": "Object",
                "task_id": 0,
                "init_state_id": init_state,
                "query_idx": 0,
                "rollout_seed": 100 + init_state,
                "candidate_idx": candidate_idx,
                "candidate_seed": 1000 + candidate_idx,
                "candidate_value": (
                    parallel_value[candidate_idx]
                    if mode == "parallel"
                    else autoregressive_value[candidate_idx]
                ),
                "terminal_success_bool": candidate_idx in successes,
                "terminal_failure_type": (
                    "success" if candidate_idx in successes else "timeout_no_goal"
                ),
            }
            for summary_name in ("first", "last", "mean", "std"):
                for dimension in range(7):
                    row[f"candidate_action_{summary_name}_d{dimension}"] = float(
                        candidate_idx + dimension
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def test_autoregressive_value_detects_one_paired_rescue() -> None:
    paired, states = compare_candidates(
        _candidates("parallel"),
        _candidates("autoregressive"),
        expected_candidates=4,
    )
    summary = summarize(states).set_index("factor")

    assert paired["action_signature_max_abs"].max() == 0.0
    assert paired["terminal_outcome_agrees"].all()
    assert states["selector_rescue"].sum() == 1
    assert states["selector_harm"].sum() == 0
    assert summary.loc["All", "mixed_top1_delta_states"] == 1
    assert summary.loc["All", "rescues"] == 1


def test_same_pass_dual_analysis_passes_on_a_rescue(tmp_path: Path) -> None:
    frame = _candidates("parallel")
    frame["snapshot_id"] = "state_" + frame["init_state_id"].astype(str)
    frame["suite"] = "libero_object_object"
    frame["task_description"] = "pick the object"
    frame["terminal_available"] = True
    frame["terminal_success"] = frame["terminal_success_bool"]
    frame["terminal_utility_v1"] = frame["terminal_success_bool"].astype(float) * 3.0
    frame["case_id"] = "dual_value_object_task0"
    frame["candidate_parallel_value"] = frame["candidate_value"]
    autoregressive = _candidates("autoregressive")
    frame["candidate_autoregressive_value"] = autoregressive["candidate_value"]
    for dimension in range(9):
        frame[f"candidate_predicted_future_proprio_d{dimension}"] = float(dimension)
        frame[f"candidate_autoregressive_predicted_future_proprio_d{dimension}"] = (
            float(dimension) + 1.0
        )
    path = tmp_path / "dual__candidate_outcomes.parquet"
    frame.to_parquet(path, index=False)

    payload = analyze([path], tmp_path / "analysis", expected_candidates=4)

    assert payload["validity_pass"] is True
    assert payload["efficacy_pass"] is True
    assert payload["gate"] == "PASS"
    assert payload["mixed_top1_delta_states"] == 1
    assert payload["future_proprio_l2_mean"] == 3.0
    assert payload["future_proprio_l2_p95"] == 3.0
    assert (tmp_path / "analysis" / "RESULTS.md").is_file()

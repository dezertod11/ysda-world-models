from __future__ import annotations

import pandas as pd

from scripts.analyze_p4b_terminal_holdout import (
    _mcnemar_p,
    _paired_bootstrap_interval,
    _select_rows,
)


def _candidates() -> pd.DataFrame:
    rows = []
    for snapshot, baseline_success, safer_success in [
        ("a", False, True),
        ("b", True, True),
    ]:
        for candidate in range(4):
            rows.append(
                {
                    "snapshot_group": snapshot,
                    "group_id": snapshot,
                    "factor": "Object",
                    "case_id": "case",
                    "suite": "libero_object_object",
                    "task_id": 0,
                    "query_idx": 3,
                    "candidate_idx": candidate,
                    "candidate_value": 1.0 if candidate == 0 else 0.9 - candidate * 0.1,
                    "risk": 10.0 if candidate == 0 else 1.0 + candidate,
                    "terminal_success": baseline_success if candidate == 0 else safer_success,
                    "terminal_target_drop_candidate": candidate == 0 and not baseline_success,
                    "terminal_official_safety_violation": False,
                    "terminal_final_t": 280 if not baseline_success else 120,
                }
            )
    return pd.DataFrame(rows)


def test_terminal_selection_records_paired_rescue() -> None:
    selected = _select_rows(_candidates(), "risk", 2.0)

    assert len(selected) == 2
    assert selected["selection_changed"].all()
    assert selected["success_delta"].tolist() == [1, 0]
    low, high = _paired_bootstrap_interval(selected, repetitions=200, seed=1)
    assert 0 <= low <= high <= 1


def test_exact_mcnemar_uses_discordant_pairs() -> None:
    assert _mcnemar_p(0, 0) == 1.0
    assert _mcnemar_p(5, 0) == 0.0625


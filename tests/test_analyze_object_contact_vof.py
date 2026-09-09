from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analyze_object_contact_vof_development import (
    evaluate_ranking,
    fold_labels,
    score_quintiles,
    top_budget_mask,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "task_id": [1, 1, 2, 2, 3],
            "position_level": ["x0.2", "y0.1", "x0.2", "y0.1", "y0.2"],
            "cell_key": ["x0.2|task1", "y0.1|task1", "x0.2|task2", "y0.1|task2", "y0.2|task3"],
            "terminal_effect": [-1, 0, 0, 1, 1],
        }
    )


def test_fold_labels_cover_task_level_and_cell() -> None:
    frame = _frame()
    assert fold_labels(frame, "leave_one_task").nunique() == 3
    assert fold_labels(frame, "leave_one_level").nunique() == 3
    assert fold_labels(frame, "leave_one_cell").nunique() == 5


def test_top_budget_mask_selects_highest_scores() -> None:
    selected = top_budget_mask(np.arange(10), budget=0.2)
    assert selected.sum() == 2
    assert selected[-2:].all()


def test_score_quintiles_are_ordered() -> None:
    values = np.arange(20, dtype=float)
    result = score_quintiles(values, values)
    assert result["mean_effect"].is_monotonic_increasing


def test_evaluate_ranking_rewards_oracle_order() -> None:
    frame = pd.concat([_frame()] * 4, ignore_index=True)
    frame["cell_key"] = [f"cell{i // 4}" for i in range(len(frame))]
    score = frame["terminal_effect"].to_numpy(float)
    row, query, _quintiles = evaluate_ranking(frame, score)
    assert query.sum() == 4
    assert row["adjusted_gain"] > 0
    assert row["rescue_vs_harm_auc"] == 1.0

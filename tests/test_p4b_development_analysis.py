from __future__ import annotations

import pandas as pd

from scripts.analyze_p4b_development import _choose_selector


def test_choose_selector_applies_frozen_gate_and_tiebreak() -> None:
    grid = pd.DataFrame(
        [
            {
                "variant": "bad",
                "metric": "epistemic_mean",
                "risk_lambda": 1.0,
                "candidate_spearman": 0.2,
                "pooled_residual_delta": -0.2,
                "worst_factor_residual_delta": -0.1,
                "selection_change_rate": 0.4,
            },
            {
                "variant": "good_a",
                "metric": "epistemic_mean",
                "risk_lambda": 1.0,
                "candidate_spearman": 0.6,
                "pooled_residual_delta": -0.02,
                "worst_factor_residual_delta": -0.005,
                "selection_change_rate": 0.4,
            },
            {
                "variant": "good_b",
                "metric": "mean_plus_epistemic_rms",
                "risk_lambda": 2.0,
                "candidate_spearman": 0.7,
                "pooled_residual_delta": -0.03,
                "worst_factor_residual_delta": -0.01,
                "selection_change_rate": 0.5,
            },
        ]
    )

    chosen, eligible = _choose_selector(grid)

    assert len(eligible) == 2
    assert chosen["variant"] == "good_b"


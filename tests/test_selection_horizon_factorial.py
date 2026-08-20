import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_adaptive_planning_campaign import strategy_id
from analyze_selection_horizon_factorial import build_seed_table, effect_summary


def test_horizon_only_strategy_has_stable_analysis_id():
    row = pd.Series(
        {
            "planning_strategy": "max_value_disagreement_requery",
            "planning_risk_lambda": 1.0,
            "planning_short_open_loop_steps": 8,
        }
    )

    assert strategy_id(row) == "horizon_only_l1_h8"


def test_factorial_seed_table_computes_matched_causal_contrasts():
    outcomes = {
        10: {
            "max_value": 0,
            "action_l1": 1,
            "horizon_only_l1_h8": 1,
            "requery_l1_h8": 1,
        },
        20: {
            "max_value": 1,
            "action_l1": 1,
            "horizon_only_l1_h8": 0,
            "requery_l1_h8": 1,
        },
    }
    rows = []
    for rollout_seed, strategies in outcomes.items():
        for strategy, success in strategies.items():
            rows.append(
                {
                    "case_id": "case_a",
                    "suite": "suite",
                    "task_id": 0,
                    "init_state_id": 0,
                    "rollout_seed": rollout_seed,
                    "strategy_id": strategy,
                    "success": bool(success),
                    "num_queries_observed": 10 if strategy == "max_value" else 12,
                }
            )

    seeds = build_seed_table(pd.DataFrame(rows))
    effects = effect_summary(seeds).set_index("effect")

    assert len(seeds) == 2
    assert effects.loc["selection_at_full_horizon", "mean_effect"] == 0.5
    assert effects.loc["horizon_with_max_value", "mean_effect"] == 0.0
    assert effects.loc["combined_vs_baseline", "mean_effect"] == 0.5
    assert effects.loc["factorial_interaction", "mean_effect"] == 0.0

import json
from argparse import Namespace

import pandas as pd

from scripts.analyze_recovery_outcome_router_holdout import analyze
from scripts.recovery_outcome_router import ROUTER_FEATURES, ROUTER_STRATEGIES


def test_holdout_analyzer_routes_without_reading_outcomes(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    rows = []
    cases = [
        ("case_retreat", 1.0, True, 0, 1, 0),
        ("case_full", -1.0, True, 0, 0, 1),
        ("case_fallback", 0.0, False, 0, 0, 0),
    ]
    for index, (case_id, feature, trigger, baseline, retreat, full) in enumerate(cases):
        outcomes = {
            "baseline_h8": baseline,
            "workspace_retreat_only": retreat,
            "workspace_calibrated": full,
        }
        for strategy in ROUTER_STRATEGIES:
            row = {
                "case_id": case_id,
                "strategy": strategy,
                "evaluation_cohort": "novel_cell",
                "independent_group": case_id,
                "position_level": "x0.2",
                "task_id": index,
                "init_state_id": 45 + index,
                "terminal_success": outcomes[strategy],
                "terminal_final_t": 120 if outcomes[strategy] else 280,
                "terminal_target_drop_candidate": False,
                "terminal_wrong_object_interaction_candidate": False,
                "terminal_official_safety_violation": False,
                "trigger_passed": trigger if strategy != "baseline_h8" else False,
                "intervention_applied": trigger and strategy != "baseline_h8",
                "counterfactual_reused": not trigger and strategy != "baseline_h8",
                "primitive_steps": (
                    25
                    if strategy == "workspace_calibrated" and trigger
                    else 3
                    if strategy == "workspace_retreat_only" and trigger
                    else 0
                ),
                "snapshot_replay_max_abs": 0.0,
            }
            row.update(dict.fromkeys(ROUTER_FEATURES, 0.0))
            row[ROUTER_FEATURES[0]] = feature
            rows.append(row)
    pd.DataFrame(rows).to_parquet(campaign / "synthetic__online_branches.parquet")

    coefficients = [0.0] * len(ROUTER_FEATURES)
    retreat_coefficients = coefficients.copy()
    retreat_coefficients[0] = 4.0
    full_coefficients = coefficients.copy()
    full_coefficients[0] = -4.0
    artifact = {
        "schema_version": 1,
        "features": list(ROUTER_FEATURES),
        "strategies": list(ROUTER_STRATEGIES),
        "feature_medians": coefficients,
        "feature_means": coefficients,
        "feature_scales": [1.0] * len(ROUTER_FEATURES),
        "primitive_cost_lambda": 0.0,
        "primitive_costs": {
            "baseline_h8": 0.0,
            "workspace_retreat_only": 3 / 280,
            "workspace_calibrated": 25 / 280,
        },
        "heads": {
            "baseline_h8": {"coefficients": coefficients, "intercept": -5.0},
            "workspace_retreat_only": {
                "coefficients": retreat_coefficients,
                "intercept": 0.0,
            },
            "workspace_calibrated": {
                "coefficients": full_coefficients,
                "intercept": 0.0,
            },
        },
    }
    artifact_path = tmp_path / "router.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    result = analyze(
        Namespace(
            campaign_dir=campaign,
            router_artifact=artifact_path,
            output_dir=tmp_path / "analysis",
            expected_cases=3,
            bootstrap_repetitions=100,
            seed=7,
            replay_threshold=1e-9,
            min_rescues=1,
            require_gate=False,
        )
    )
    assert result["complete"]
    assert result["feature_integrity"]
    assert result["holdout_gate_pass"]
    assert result["route_counts"] == {
        "baseline_h8": 1,
        "workspace_retreat_only": 1,
        "workspace_calibrated": 1,
    }

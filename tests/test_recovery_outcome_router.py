import json

import numpy as np
import pytest

from scripts.recovery_outcome_router import (
    ROUTER_FEATURES,
    ROUTER_STRATEGIES,
    load_recovery_router,
    route_recovery,
)


def artifact():
    return {
        "schema_version": 1,
        "features": list(ROUTER_FEATURES),
        "strategies": list(ROUTER_STRATEGIES),
        "feature_medians": [0.0] * len(ROUTER_FEATURES),
        "feature_means": [0.0] * len(ROUTER_FEATURES),
        "feature_scales": [1.0] * len(ROUTER_FEATURES),
        "primitive_cost_lambda": 0.25,
        "primitive_costs": {
            "baseline_h8": 0.0,
            "workspace_retreat_only": 3 / 280,
            "workspace_calibrated": 25 / 280,
        },
        "heads": {
            "baseline_h8": {
                "coefficients": [0.0] * len(ROUTER_FEATURES),
                "intercept": -2.0,
            },
            "workspace_retreat_only": {
                "coefficients": [0.0] * len(ROUTER_FEATURES),
                "intercept": 0.0,
            },
            "workspace_calibrated": {
                "coefficients": [0.0] * len(ROUTER_FEATURES),
                "intercept": 2.0,
            },
        },
    }


def test_router_selects_best_cost_adjusted_head():
    result = route_recovery(
        {**dict.fromkeys(ROUTER_FEATURES, 0.0), "trigger_passed": True}, artifact()
    )
    assert result["router_selected_strategy"] == "workspace_calibrated"
    assert result["router_probabilities"]["workspace_calibrated"] > 0.8


def test_failed_trigger_forces_exact_baseline_and_imputes_nonfinite():
    record = {**dict.fromkeys(ROUTER_FEATURES, np.nan), "trigger_passed": False}
    result = route_recovery(record, artifact())
    assert result["router_selected_strategy"] == "baseline_h8"
    assert result["router_trigger_override"]
    assert set(result["router_feature_values"].values()) == {0.0}


def test_loader_rejects_feature_contract_drift(tmp_path):
    payload = artifact()
    payload["features"] = ["wrong"]
    path = tmp_path / "router.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="feature contract"):
        load_recovery_router(path)

from argparse import Namespace

import pandas as pd

from scripts.analyze_online_perception_regrasp import analyze
from scripts.build_online_regrasp_cases import rows_for_split


def test_online_case_splits_are_group_disjoint():
    groups = {
        split: {row["independent_group"] for row in rows_for_split(split)}
        for split in ("screen", "development", "holdout")
    }
    assert len(rows_for_split("screen")) == 12
    assert len(rows_for_split("development")) == 40
    assert len(rows_for_split("holdout")) == 40
    assert groups["screen"].isdisjoint(groups["development"])
    assert groups["screen"].isdisjoint(groups["holdout"])
    assert groups["development"].isdisjoint(groups["holdout"])


def test_analyzer_selects_net_rescuing_method(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    rows = []
    outcomes = {
        "case0": (0, 1, 0),
        "case1": (1, 1, 1),
        "case2": (0, 0, 0),
        "case3": (1, 1, 1),
    }
    for case_id, (baseline, workspace, conservative) in outcomes.items():
        for strategy, success in (
            ("baseline_h8", baseline),
            ("workspace_calibrated", workspace),
            ("global_conservative", conservative),
        ):
            rows.append(
                {
                    "case_id": case_id,
                    "strategy": strategy,
                    "independent_group": case_id,
                    "position_level": "x0.2",
                    "task_id": 5,
                    "terminal_success": bool(success),
                    "terminal_final_t": 120 if success else 280,
                    "terminal_target_drop_candidate": False,
                    "terminal_wrong_object_interaction_candidate": False,
                    "terminal_official_safety_violation": False,
                    "trigger_passed": strategy != "baseline_h8",
                    "intervention_applied": strategy != "baseline_h8",
                    "counterfactual_reused": strategy == "baseline_h8",
                    "snapshot_replay_max_abs": 0.0,
                }
            )
    pd.DataFrame(rows).to_parquet(campaign / "synthetic__online_branches.parquet")
    result = analyze(
        Namespace(
            campaign_dir=campaign,
            output_dir=tmp_path / "analysis",
            phase="screen",
            expected_cases=4,
            expected_strategies=(
                "baseline_h8,workspace_calibrated,global_conservative"
            ),
            bootstrap_repetitions=100,
            seed=7,
            replay_threshold=1e-9,
            max_harms=1,
            max_wrong_delta=0.05,
            require_gate=False,
        )
    )
    assert result["recommended_method"] == "workspace_calibrated"
    assert result["gate_pass"]

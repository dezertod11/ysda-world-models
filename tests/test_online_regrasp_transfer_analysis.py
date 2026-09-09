from argparse import Namespace

import pandas as pd

from scripts.analyze_online_regrasp_transfer import analyze


def test_transfer_analyzer_selects_new_cell_winner(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    rows = []
    cases = [
        ("rep0", "replication", 0, 1, 0),
        ("rep1", "replication", 1, 1, 1),
        ("new0", "novel_cell", 0, 1, 0),
        ("new1", "novel_cell", 0, 1, 0),
    ]
    for index, (case_id, cohort, baseline, regrasp, retreat) in enumerate(cases):
        for strategy, success, primitive_steps in (
            ("baseline_h8", baseline, 0),
            ("workspace_calibrated", regrasp, 25),
            ("workspace_retreat_only", retreat, 3),
        ):
            rows.append(
                {
                    "case_id": case_id,
                    "strategy": strategy,
                    "evaluation_cohort": cohort,
                    "independent_group": case_id,
                    "position_level": "x0.2" if cohort == "replication" else "y0.1",
                    "task_id": index,
                    "init_state_id": 40 + index,
                    "terminal_success": bool(success),
                    "terminal_final_t": 120 if success else 280,
                    "terminal_target_drop_candidate": False,
                    "terminal_wrong_object_interaction_candidate": False,
                    "terminal_official_safety_violation": False,
                    "trigger_passed": strategy != "baseline_h8",
                    "intervention_applied": strategy != "baseline_h8",
                    "counterfactual_reused": False,
                    "primitive_steps": primitive_steps,
                    "snapshot_replay_max_abs": 0.0,
                }
            )
    pd.DataFrame(rows).to_parquet(campaign / "synthetic__online_branches.parquet")
    result = analyze(
        Namespace(
            campaign_dir=campaign,
            output_dir=tmp_path / "analysis",
            phase="development",
            expected_cases=4,
            expected_strategies=(
                "baseline_h8,workspace_calibrated,workspace_retreat_only"
            ),
            bootstrap_repetitions=100,
            seed=7,
            replay_threshold=1e-9,
            min_interventions=1,
            max_drop_delta=0.05,
            max_wrong_delta=0.05,
            require_gate=False,
        )
    )
    assert result["selected_method"] == "workspace_calibrated"
    assert result["complete_cases"] == 4
    assert result["exact_replay"]

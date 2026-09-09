from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_terminal_opportunity_atlas import build_atlas


def test_build_atlas_reports_rescue_and_all_fail_cells(tmp_path: Path) -> None:
    runs = tmp_path / "experiments" / "campaigns" / "example" / "runs"
    runs.mkdir(parents=True)
    rows = []
    for snapshot, outcomes in (("rescue", (False, True)), ("all_fail", (False, False))):
        for candidate_idx, success in enumerate(outcomes):
            rows.append(
                {
                    "snapshot_id": snapshot,
                    "suite": "libero_object_object",
                    "case_id": "object",
                    "task_id": 0,
                    "task_description": "pick the object",
                    "init_state_id": 0 if snapshot == "rescue" else 1,
                    "query_idx": 0,
                    "candidate_idx": candidate_idx,
                    "candidate_value": 1.0 - candidate_idx,
                    "terminal_available": True,
                    "terminal_success": success,
                    "terminal_utility_v1": 3.0 if success else 0.0,
                }
            )
    source = runs / "example__candidate_outcomes.parquet"
    pd.DataFrame(rows).to_parquet(source, index=False)

    output = tmp_path / "analysis"
    summary = build_atlas([source], output)

    assert summary["snapshots"] == 2
    assert summary["success_rescues"] == 1
    assert summary["all_candidates_fail"] == 1
    cell = pd.read_csv(output / "campaign_task_query_summary.csv").iloc[0]
    assert cell["oracle_gap_pp"] == 50.0
    assert (output / "terminal_oracle_gap_by_cell.png").is_file()
    assert (output / "RESULTS.md").is_file()

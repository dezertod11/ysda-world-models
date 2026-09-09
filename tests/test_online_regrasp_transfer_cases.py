from scripts.build_online_regrasp_transfer_cases import (
    NOVEL_CELLS,
    REPLICATION_CELLS,
    rows_for_split,
)


def test_p3d_splits_and_cohorts_are_frozen_and_disjoint():
    development = rows_for_split("development")
    holdout = rows_for_split("holdout")
    assert len(development) == 75
    assert len(holdout) == 75
    assert set(REPLICATION_CELLS).isdisjoint(NOVEL_CELLS)
    assert {row["init_state_id"] for row in development} == set(range(40, 45))
    assert {row["init_state_id"] for row in holdout} == set(range(45, 50))
    assert {row["independent_group"] for row in development}.isdisjoint(
        row["independent_group"] for row in holdout
    )
    assert sum(row["evaluation_cohort"] == "replication" for row in development) == 40
    assert sum(row["evaluation_cohort"] == "novel_cell" for row in development) == 35

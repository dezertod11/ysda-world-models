import pandas as pd

from scripts.build_invariant_cate_reserve_holdout import build_config


def test_full_reserve_config_has_400_pairs_and_all_cells() -> None:
    cells = pd.DataFrame(
        [
            {
                "position_level": ["x0.2", "y0.1", "y0.2", "y0.3"][index % 4],
                "task_id": index + 1,
                "task_description": f"task {index + 1}",
            }
            for index in range(10)
        ]
    )
    config = build_config(cells)
    jobs = config["profiles"]["invariant_cate_reserve_holdout"]["jobs"]
    assert len(jobs) == 20
    assert sum(job["target_decision_states"] for job in jobs) == 400
    assert {job["init_state_ids"] for job in jobs} == {"5-14", "15-24"}
    assert all(job["kind"] == "pro_position_counterfactual_feedback" for job in jobs)
    assert {job["gpu_slot"] for job in jobs} == {0, 1, 2, 3, 4}

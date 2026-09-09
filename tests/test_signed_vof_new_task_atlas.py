import pandas as pd

from scripts.analyze_signed_vof_new_task_atlas import (
    build_gate,
    decode_position_level,
    select_boundary_cells,
    summarize_cells,
)


def test_decode_position_level() -> None:
    assert decode_position_level("position_y0p3_tasks4_6") == "y0.3"


def test_boundary_selection_and_gate() -> None:
    rows = []
    outcomes = {
        ("x0.2", 1): [1, 1, 0, 0, 0],
        ("x0.2", 2): [1, 1, 1, 0, 0],
        ("x0.2", 3): [1, 0, 0, 0, 0],
        ("y0.1", 4): [1, 1, 0, 0, 0],
        ("y0.2", 5): [1, 1, 1, 0, 0],
        ("y0.3", 6): [1, 0, 0, 0, 0],
    }
    for (level, task), values in outcomes.items():
        for index, success in enumerate(values):
            rows.append(
                {
                    "position_level": level,
                    "direction": level[0],
                    "task_id": task,
                    "task_description": f"task {task}",
                    "strict_usable": True,
                    "terminal_success_bool": bool(success),
                    "init_state_id": index,
                }
            )
    selected_rows = pd.DataFrame(rows)
    summary = summarize_cells(selected_rows)
    chosen = select_boundary_cells(summary)
    assert len(chosen) == 6
    assert set(chosen["direction"]) == {"x", "y"}
    gate = build_gate(selected_rows, summary, expected_states=30)
    assert gate["pass"] is True
    assert gate["selected_tasks"] == 6

import numpy as np
import pandas as pd
import pytest

from scripts.analyze_signed_vof_new_task_holdout import parse_case, policy_row
from scripts.build_signed_vof_new_task_holdout import build_config


def test_holdout_config_uses_disjoint_new_tasks() -> None:
    cells = [
        {"position_level": "x0.2" if i == 0 else "y0.2", "direction": "x" if i == 0 else "y", "task_id": i + 1}
        for i in range(6)
    ]
    config = build_config({"gate": {"pass": True}, "cells": cells})
    jobs = config["profiles"]["signed_vof_new_task_holdout"]["jobs"]
    assert len(jobs) == 12
    assert {job["init_state_ids"] for job in jobs} == {"5-14", "15-24"}
    assert all(job["task_ids"] != "0" for job in jobs)
    assert config["defaults"]["skip_feedback_branch"] is False


def test_parse_case_and_policy_effect() -> None:
    assert parse_case("position_y0p3_task7_init5_14") == ("y0.3", 7)
    frame = pd.DataFrame(
        {
            "commit_success": [False, True, False, True],
            "feedback_success": [True, False, False, True],
        }
    )
    row = policy_row(frame, np.asarray([True, False, True, True]), 0.025)
    assert row["rescues"] == 1
    assert row["harms"] == 0
    assert row["query_rate"] == 0.75
    assert row["raw_success_delta"] == 0.25
    assert row["adjusted_success_delta"] == pytest.approx(0.25 - 0.025 * 0.75)

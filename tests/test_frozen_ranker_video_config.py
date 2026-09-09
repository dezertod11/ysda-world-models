from __future__ import annotations

import pandas as pd

from scripts.build_frozen_ranker_discordant_video_config import (
    build_config,
    select_discordances,
)


def test_video_replay_config_is_balanced_and_preserves_seed() -> None:
    rows = []
    for direction in ("frozen_gain", "frozen_loss"):
        for factor, case_id in (
            ("Environment", "frozen_closed_loop__Environment"),
            ("Object", "frozen_closed_loop__Object"),
            ("Position", "frozen_closed_loop__Position_x0p3"),
        ):
            rows.append(
                {
                    "factor": factor,
                    "case_id": case_id,
                    "suite": "libero_object_temp" if factor == "Position" else "suite",
                    "task_id": 1,
                    "init_state_id": 5,
                    "rollout_seed": 123,
                    "discordance": direction,
                }
            )
    selected = select_discordances(pd.DataFrame(rows), per_direction=3)
    config = build_config(selected)
    jobs = config["profiles"]["frozen_h16_discordant_video_replays"]["jobs"]

    assert len(jobs) == 6
    assert {job["base_seed"] for job in jobs} == {123}
    assert config["defaults"]["save_videos"] is True
    assert config["defaults"]["experiment_split"] == "generalization"
    position = next(job for job in jobs if job["planning_frozen_ranker_factor"] == "Position")
    assert position["position_level"] == "x0.3"

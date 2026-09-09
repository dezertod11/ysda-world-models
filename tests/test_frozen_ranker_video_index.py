from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.index_frozen_ranker_video_replays import write_index


def _write_trace(
    campaign: Path,
    *,
    strategy: str,
    success: bool,
    selected: int,
    offset: float,
    video: Path | None,
) -> None:
    values = [float(index) + offset for index in range(6)]
    row = {
        "factor": "Environment",
        "case_id": "replay-case",
        "suite": "libero_object_env",
        "task_id": 8,
        "init_state_id": 7,
        "rollout_seed": 1234,
        "query_idx": 0,
        "planning_strategy": strategy,
        "planning_frozen_ranker_factor": "Environment",
        "success": success,
        "final_t": 100 if success else 280,
        "selected_sample_idx": selected,
        "candidate_values_json": json.dumps(values),
        "candidate_frozen_ranker_scores_json": json.dumps(values[::-1]),
        "candidate_first_actions_json": json.dumps([[value] * 7 for value in values]),
    }
    if video is not None:
        row["video_path"] = str(video)
    runs = campaign / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_parquet(
        runs / f"case__{strategy}__query_traces.parquet", index=False
    )


def test_video_index_reports_primary_replay_fidelity(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    replay = tmp_path / "replay"
    for strategy, success, selected in (
        ("max_value", True, 5),
        ("frozen_factor_ridge", False, 0),
    ):
        _write_trace(
            primary,
            strategy=strategy,
            success=success,
            selected=selected,
            offset=0.0,
            video=None,
        )
    for strategy, success, selected in (
        ("max_value", True, 5),
        ("frozen_factor_ridge", True, 0),
    ):
        video = tmp_path / f"{strategy}.mp4"
        video.write_bytes(b"video")
        _write_trace(
            replay,
            strategy=strategy,
            success=success,
            selected=selected,
            offset=0.001,
            video=video,
        )

    selection = tmp_path / "selection.csv"
    pd.DataFrame(
        [
            {
                "factor": "Environment",
                "case_id": "primary-case",
                "suite": "libero_object_env",
                "task_id": 8,
                "init_state_id": 7,
                "rollout_seed": 1234,
                "discordance": "frozen_loss",
            }
        ]
    ).to_csv(selection, index=False)

    output = tmp_path / "index"
    pairs = write_index(
        replay,
        output,
        selection_csv=selection,
        primary_campaign_dir=primary,
    )

    assert len(pairs) == 1
    assert bool(pairs.loc[0, "max_value_outcome_reproduced"]) is True
    assert bool(pairs.loc[0, "frozen_factor_ridge_outcome_reproduced"]) is False
    assert bool(pairs.loc[0, "paired_outcome_reproduced"]) is False
    assert str(pairs.loc[0, "max_value_video"]).startswith("videos/")
    assert pairs.loc[0, "max_value_video_num_frames"] == pairs.loc[
        0, "max_value_video_expected_frames"
    ]
    assert len(pd.read_csv(output / "replay_fidelity.csv")) == 2
    assert len(list((output / "videos").glob("*.mp4"))) == 2
    html = (output / "VIDEO_INDEX.html").read_text(encoding="utf-8")
    assert "primary success=False" in html
    assert "pair reproduced=False" in html

    (tmp_path / "max_value.mp4").unlink()
    (tmp_path / "frozen_factor_ridge.mp4").unlink()
    write_index(
        replay,
        output,
        selection_csv=selection,
        primary_campaign_dir=primary,
    )
    rebuilt_html = (output / "VIDEO_INDEX.html").read_text(encoding="utf-8")
    assert rebuilt_html.count("<video controls") == 2

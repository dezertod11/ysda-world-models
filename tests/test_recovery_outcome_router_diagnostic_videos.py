from pathlib import Path

import pandas as pd

from scripts.build_recovery_outcome_router_diagnostic_manifest import (
    DIAGNOSTIC_CASES,
    build_manifest,
)
from scripts.index_recovery_outcome_router_diagnostic_videos import (
    STRATEGIES,
    build_index,
)


def _manifest() -> pd.DataFrame:
    rows = []
    for index, case_id in enumerate(DIAGNOSTIC_CASES):
        rows.append(
            {
                "case_id": case_id,
                "split": "holdout",
                "evaluation_cohort": "novel_cell",
                "suite": "libero_object_temp",
                "position_level": "x0.2" if index < 2 else "y0.2",
                "task_id": 2 if index < 2 else 7 + index - 2,
                "init_state_id": 47 + index,
                "rollout_id": 0,
                "rollout_seed": 100 + index,
                "independent_group": case_id,
            }
        )
    return pd.DataFrame(rows)


def test_diagnostic_manifest_and_index_validate_exact_outcomes(tmp_path: Path) -> None:
    source = tmp_path / "holdout.parquet"
    _manifest().to_parquet(source, index=False)
    manifest_dir = tmp_path / "manifest"
    selected = build_manifest(source, manifest_dir)
    assert selected["diagnostic_role"].tolist() == list(DIAGNOSTIC_CASES.values())

    primary_dir = tmp_path / "primary"
    replay_dir = tmp_path / "replay"
    primary_dir.mkdir()
    replay_dir.mkdir()
    primary_rows = []
    replay_rows = []
    for case_index, case in selected.iterrows():
        for strategy_index, strategy in enumerate(STRATEGIES):
            success = (case_index + strategy_index) % 2 == 0
            common = {
                "case_id": case["case_id"],
                "strategy": strategy,
                "terminal_success": success,
                "terminal_final_t": 120 if success else 280,
                "terminal_failure_type": "success" if success else "timeout_no_goal",
                "prefix_state_sha256": f"state-{case_index}",
                "snapshot_replay_max_abs": 0.0,
            }
            primary_rows.append(common)
            video = tmp_path / f"{case_index}_{strategy_index}.mp4"
            video.write_bytes(b"video")
            replay_rows.append({**common, "video_path": str(video)})
    pd.DataFrame(primary_rows).to_parquet(
        primary_dir / "primary__online_branches.parquet"
    )
    pd.DataFrame(replay_rows).to_parquet(replay_dir / "replay__online_branches.parquet")

    output = tmp_path / "output"
    summary = build_index(
        replay_dir,
        primary_dir,
        manifest_dir / "diagnostic_cases.parquet",
        output,
    )
    assert len(summary) == len(DIAGNOSTIC_CASES) * len(STRATEGIES)
    assert summary["outcome_reproduced"].all()
    assert summary["prefix_state_reproduced"].all()
    assert len(list((output / "media").glob("*.mp4"))) == len(summary)
    assert (output / "VIDEO_INDEX.html").read_text().count("<video controls") == len(
        summary
    )

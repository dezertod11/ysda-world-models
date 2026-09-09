from argparse import Namespace

import pandas as pd

from scripts.build_perception_regrasp_manifest import build


def test_manifest_excludes_complete_independent_groups(tmp_path):
    source = pd.DataFrame(
        {
            "row_uid": ["a0", "a1", "b0", "c0"],
            "independent_group": ["a", "a", "b", "c"],
            "position_level": ["x0.2"] * 4,
            "task_id": [5] * 4,
            "task_description": ["pick the tomato sauce"] * 4,
        }
    )
    excluded = pd.DataFrame(
        {
            "row_uid": ["a0"],
            "independent_group": ["a"],
        }
    )
    source_path = tmp_path / "source.parquet"
    excluded_path = tmp_path / "excluded.parquet"
    output_path = tmp_path / "manifest.parquet"
    source.to_parquet(source_path, index=False)
    excluded.to_parquet(excluded_path, index=False)

    result = build(
        Namespace(
            source=source_path,
            exclude=[excluded_path],
            reserve=None,
            output=output_path,
            per_cell=0,
            seed=7,
        )
    )

    assert set(result["row_uid"]) == {"b0", "c0"}
    assert set(result["independent_group"]) == {"b", "c"}

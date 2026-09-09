from argparse import Namespace

import pandas as pd

from scripts.build_strict_group_reserve import build


def test_strict_reserve_removes_development_groups(tmp_path):
    reserve = pd.DataFrame(
        {
            "row_uid": ["r0", "r1", "r2"],
            "independent_group": ["shared", "new-a", "new-b"],
            "position_level": ["x0.2", "x0.2", "y0.2"],
            "task_id": [5, 5, 6],
        }
    )
    development = pd.DataFrame(
        {"row_uid": ["d0"], "independent_group": ["shared"]}
    )
    reserve_path = tmp_path / "reserve.parquet"
    development_path = tmp_path / "development.parquet"
    output_path = tmp_path / "strict.parquet"
    reserve.to_parquet(reserve_path, index=False)
    development.to_parquet(development_path, index=False)

    result = build(
        Namespace(
            reserve=reserve_path,
            development=development_path,
            output=output_path,
        )
    )

    assert result["row_uid"].tolist() == ["r1", "r2"]
    assert set(result["independent_group"]) == {"new-a", "new-b"}

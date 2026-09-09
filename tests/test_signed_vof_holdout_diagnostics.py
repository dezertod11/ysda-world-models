import numpy as np
import pandas as pd

from scripts.diagnose_signed_vof_new_task_holdout import standardized_shift


def test_standardized_shift_and_score_contribution() -> None:
    frame = pd.DataFrame({"a": [1.0, 4.0], "b": [3.0, np.nan]})
    payload = {
        "active_features": ["a", "b"],
        "preprocessing": {
            "impute_median": [2.0, 5.0],
            "mean": [2.0, 5.0],
            "scale": [1.0, 2.0],
        },
        "ridge": {"coefficients": [0.5, 2.0, -1.0]},
    }
    z, contribution, features = standardized_shift(frame, payload)
    assert features == ["a", "b"]
    assert z.tolist() == [[-1.0, -1.0], [2.0, 0.0]]
    assert contribution.tolist() == [[-2.0, 1.0], [4.0, 0.0]]

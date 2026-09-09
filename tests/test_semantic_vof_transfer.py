from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.evaluate_semantic_vof_transfer import (
    AGENT_DISAGREEMENT,
    CROSSVIEW,
    FAMILIES,
    PRIMARY,
    fit_transfer,
)


def test_primary_transfer_model_is_frozen_two_feature_extension() -> None:
    assert FAMILIES[PRIMARY][-2:] == [AGENT_DISAGREEMENT, CROSSVIEW]
    assert len(FAMILIES[PRIMARY]) == len(FAMILIES["scalar"]) + 2


def test_transfer_fit_returns_finite_prediction() -> None:
    features = ["x"]
    train = pd.DataFrame({"x": [-2.0, -1.0, 1.0, 2.0], "dense_vof_v2": [-1.0, -0.5, 0.5, 1.0]})
    test = pd.DataFrame({"x": [-3.0, 0.0, 3.0]})
    prediction = fit_transfer(train, test, features)
    assert prediction.shape == (3,)
    assert np.isfinite(prediction).all()
    assert prediction[0] < prediction[-1]

from __future__ import annotations

import math

import numpy as np

from scripts.p4b_residual_risk import (
    monte_carlo_predictive_mi,
    residual_risk_scores,
    select_candidate,
    within_snapshot_score,
)


def test_robust_scores_are_finite_and_predictive_mi_is_bounded() -> None:
    means = np.zeros((3, 5, 2), dtype=np.float32)
    means[1, :, 0] = 0.2
    means[2, :, 0] = -0.2
    variances = np.ones_like(means) * 0.5
    scores = residual_risk_scores(
        means,
        variances,
        mc_samples_per_head=64,
        mc_seed=7,
        mc_device="cpu",
    )

    assert all(values.shape == (5,) for values in scores.values())
    assert all(np.isfinite(values).all() for values in scores.values())
    assert np.all(scores["epistemic_mean"] > 0)
    assert np.all(scores["mc_predictive_mi"] >= -0.05)
    assert np.all(scores["mc_predictive_mi"] <= math.log(3) + 0.05)


def test_identical_heads_have_near_zero_mutual_information() -> None:
    means = np.zeros((3, 4, 2), dtype=np.float32)
    variances = np.ones_like(means)
    score = monte_carlo_predictive_mi(
        means, variances, samples_per_head=128, seed=3, device="cpu"
    )
    np.testing.assert_allclose(score, 0.0, atol=0.04)


def test_candidate_selector_penalizes_relative_risk() -> None:
    values = np.asarray([1.0, 0.95, 0.2])
    risk = np.asarray([10.0, 1.0, 1.0])

    assert select_candidate(values, risk, 0.0) == 0
    assert select_candidate(values, risk, 1.0) == 1
    assert within_snapshot_score(values, risk, 1.0).shape == values.shape


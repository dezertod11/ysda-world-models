from pathlib import Path

import numpy as np

from scripts.residual_dynamics_ensemble import (
    ResidualPreprocessor,
    conformal_threshold,
    jensen_renyi_divergence,
    randomized_pca,
    train_independent_heads,
    uncertainty_scores,
)


def _arrays(rows: int = 20) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(5)
    predicted = rng.normal(size=(rows, 12)).astype(np.float32)
    return {
        "current_visual": rng.normal(size=(rows, 12)).astype(np.float32),
        "predicted_visual": predicted,
        "actual_visual": predicted + rng.normal(scale=0.1, size=(rows, 12)),
        "current_proprio": rng.normal(size=(rows, 9)).astype(np.float32),
        "predicted_proprio": rng.normal(size=(rows, 9)).astype(np.float32),
        "actual_proprio": rng.normal(size=(rows, 9)).astype(np.float32),
        "actions": rng.normal(size=(rows, 16, 7)).astype(np.float32),
        "candidate_value": rng.normal(size=rows).astype(np.float32),
    }


def test_preprocessor_is_fit_only_on_supplied_rows() -> None:
    arrays = _arrays()
    train = np.arange(15)
    preprocessor = ResidualPreprocessor.fit(
        arrays,
        train,
        input_visual_components=5,
        target_visual_components=4,
        seed=7,
    )
    x = preprocessor.transform_input(arrays, np.arange(20))
    y = preprocessor.transform_target(arrays, np.arange(20))
    assert x.shape == (20, 5 + 9 + 9 + 16 * 7 + 1)
    assert y.shape == (20, 4 + 9)
    assert np.allclose(x[train].mean(axis=0), 0.0, atol=2e-5)
    assert np.allclose(y[train].mean(axis=0), 0.0, atol=2e-5)


def test_jrd_is_zero_for_identical_heads_and_grows_when_means_separate() -> None:
    means = np.zeros((3, 2, 4), dtype=np.float32)
    variances = np.ones_like(means)
    identical = jensen_renyi_divergence(means, variances)
    means[1, :, 0] = 3.0
    separated = jensen_renyi_divergence(means, variances)
    assert np.allclose(identical, 0.0, atol=1e-6)
    assert np.all(separated > identical)
    scores = uncertainty_scores(means, variances)
    assert set(scores) == {
        "ensemble_aleatoric_mean",
        "ensemble_aleatoric_max",
        "ensemble_epistemic_mean",
        "ensemble_epistemic_max",
        "ensemble_total_mean",
        "ensemble_jrd",
    }


def test_group_bootstrap_heads_train_and_conformal_is_finite(tmp_path: Path) -> None:
    rng = np.random.default_rng(9)
    x = rng.normal(size=(24, 5)).astype(np.float32)
    y = (x[:, :2] + rng.normal(scale=0.1, size=(24, 2))).astype(np.float32)
    groups = np.asarray([f"g{index // 4}" for index in range(24)])
    histories = train_independent_heads(
        x,
        y,
        groups,
        tmp_path,
        num_heads=2,
        hidden_dim=8,
        epochs=2,
        batch_size=8,
        seed=11,
        device="cpu",
    )
    assert len(histories) == 2
    assert (tmp_path / "head_0.pt").is_file()
    threshold, level = conformal_threshold([0.1, 0.2, 0.3, 0.4], alpha=0.2)
    assert threshold == 0.4
    assert level == 1.0


def test_randomized_pca_returns_requested_orthogonal_projection() -> None:
    values = np.random.default_rng(1).normal(size=(30, 10))
    _mean, components = randomized_pca(values, 4, seed=3)
    assert components.shape == (4, 10)
    assert np.allclose(components @ components.T, np.eye(4), atol=1e-5)

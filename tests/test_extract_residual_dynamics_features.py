from pathlib import Path

import numpy as np
import pandas as pd

from scripts.extract_residual_dynamics_features import extract_arrays


def test_extract_arrays_aligns_candidate_predictions_and_endpoints(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "transition.npz"
    candidates = 2
    predicted = np.stack(
        [np.full((4, 4, 3), 10 + index, dtype=np.uint8) for index in range(candidates)]
    )
    actual = np.stack(
        [np.full((4, 4, 3), 20 + index, dtype=np.uint8) for index in range(candidates)]
    )
    np.savez(
        sidecar,
        current_agentview=np.full((4, 4, 3), 1, dtype=np.uint8),
        current_wrist=np.full((4, 4, 3), 2, dtype=np.uint8),
        current_proprio=np.arange(9, dtype=np.float32),
        candidate_actions=np.arange(candidates * 16 * 7, dtype=np.float32).reshape(
            candidates, 16, 7
        ),
        candidate_values=np.asarray([0.25, 0.75], dtype=np.float32),
        candidate_predicted_future_images=predicted,
        candidate_predicted_future_wrists=predicted + 2,
        candidate_endpoint_agentview=actual,
        candidate_endpoint_wrist=actual + 2,
        candidate_predicted_future_proprio=np.ones((candidates, 9), dtype=np.float32),
        candidate_endpoint_proprio=np.full((candidates, 9), 3, dtype=np.float32),
    )
    manifest = pd.DataFrame(
        [
            {"sidecar_path": str(sidecar), "candidate_idx": index}
            for index in range(candidates)
        ]
    )

    def encoder(images):
        return np.asarray(
            [
                [float(np.asarray(image)[..., channel].mean()) for channel in range(3)]
                for image in images
            ],
            dtype=np.float32,
        )

    arrays = extract_arrays(manifest, encoder, row_batch_size=2)
    assert arrays["current_visual"].shape == (2, 6)
    assert arrays["predicted_visual"].shape == (2, 6)
    assert arrays["actual_visual"].shape == (2, 6)
    assert np.allclose(arrays["predicted_visual"][1, :3], 11)
    assert np.allclose(arrays["actual_visual"][1, :3], 21)
    assert arrays["actions"].shape == (2, 16, 7)
    assert np.allclose(arrays["candidate_value"], [0.25, 0.75])

import numpy as np
import pandas as pd

from scripts.train_perception_regrasp_heatmap import (
    _crossfit_depth_calibrator,
    _select_object_depth_modes,
)


def test_crossfit_depth_calibrator_covers_every_fold():
    targets = np.asarray([0.10, 0.12, 0.15, 0.18, 0.20, 0.23])
    predictions = pd.DataFrame(
        {
            "row_uid": [f"row-{index}" for index in range(len(targets))],
            "fold": [0, 1, 2, 0, 1, 2],
            "object_name": ["target"] * len(targets),
            "predicted_z_neural_global": targets * 0.8 + 0.01,
            "predicted_z_neural_local": targets * 1.1 - 0.01,
            "predicted_pixel_row": [1.0] * len(targets),
            "predicted_pixel_col": [1.0] * len(targets),
            "true_world_z": targets,
        }
    )
    frame = pd.DataFrame({"row_uid": predictions["row_uid"]})
    camera_to_world = np.repeat(np.eye(4)[None], len(targets), axis=0)
    intrinsics = np.repeat(np.eye(3)[None], len(targets), axis=0)
    arrays = {
        "true_world": np.stack([targets, targets, targets], axis=1),
        "camera_to_world": camera_to_world,
        "intrinsics": intrinsics,
    }

    calibrated, alpha, table = _crossfit_depth_calibrator(
        predictions,
        frame,
        arrays,
        ["target"],
        (0.0, 0.5),
        [0.1, 1.0],
    )

    assert calibrated.shape == targets.shape
    assert np.isfinite(calibrated).all()
    assert alpha in {0.1, 1.0}
    assert len(table) == 2


def test_object_depth_router_prefers_tail_robust_mode_and_records_fallback():
    predictions = pd.DataFrame(
        {
            "object_name": ["box"] * 4 + ["bottle"] * 4,
            "world_xy_l2_global": [0.01, 0.01, 0.01, 0.20, 0.03, 0.03, 0.03, 0.03],
            "world_xy_l2_median": [0.04, 0.04, 0.04, 0.04, 0.01, 0.01, 0.01, 0.01],
            "z_abs_global": [0.01] * 4 + [0.20] * 4,
            "z_abs_median": [0.02] * 4 + [0.10] * 4,
        }
    )

    selected, table = _select_object_depth_modes(
        predictions,
        ["global", "median"],
        gate_p90_z_m=0.06,
    )

    assert selected == {"bottle": "median", "box": "median"}
    bottle_rows = table.loc[table["object_name"].eq("bottle")]
    assert bottle_rows["used_z_gate_fallback"].all()
    box_rows = table.loc[table["object_name"].eq("box")]
    assert not box_rows["used_z_gate_fallback"].any()

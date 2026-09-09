import numpy as np

from scripts.perception_regrasp import (
    canonical_object_name,
    depth_summary_features,
    heatmap_depth_features,
    pixel_to_world_plane,
    raw_agentview_image,
    spatial_centroid,
    weighted_ridge,
)


def test_raw_agentview_image_preserves_camera_orientation():
    image = np.zeros((2, 3, 3), dtype=np.uint8)
    image[0] = 17
    image[1] = 231

    result = raw_agentview_image({"agentview_image": image})

    np.testing.assert_array_equal(result[0], np.full((3, 3), 17, dtype=np.uint8))
    np.testing.assert_array_equal(result[1], np.full((3, 3), 231, dtype=np.uint8))


def test_canonical_object_name_accepts_task_and_instance_names():
    assert canonical_object_name("pick up the tomato sauce and place it in the basket") == "tomato sauce"
    assert canonical_object_name("tomato_sauce_1") == "tomato sauce"


def test_spatial_centroid_tracks_dominant_patch():
    scores = np.full(16, -10.0)
    scores[6] = 10.0
    center = spatial_centroid(scores, 4, temperature=0.1)
    assert np.isclose(center["row"], 84.0)
    assert np.isclose(center["col"], 140.0)
    assert center["peak_probability"] > 0.99


def test_pixel_to_world_plane_intersects_camera_ray():
    point = pixel_to_world_plane(
        row=2.0,
        col=3.0,
        intrinsic=np.eye(3),
        camera_to_world=np.eye(4),
        plane_z=4.0,
    )
    np.testing.assert_allclose(point, [12.0, 8.0, 4.0])


def test_weighted_ridge_fits_a_linear_signal():
    features = np.asarray([[0.0], [1.0], [2.0], [3.0]])
    targets = np.asarray([0.0, 1.0, 2.0, 3.0])
    weights = weighted_ridge(features, targets, alpha=1e-8, positive_weight=1.0)
    predictions = features @ weights[:-1] + weights[-1]
    np.testing.assert_allclose(predictions, targets, atol=1e-5)


def test_depth_summary_features_are_finite_and_fixed_width():
    features = np.arange(4 * 20, dtype=np.float32).reshape(4, 20) / 100.0
    summary = depth_summary_features(
        features,
        scores=np.asarray([-1.0, 0.0, 2.0, 0.5]),
        temperature=0.1,
        random_feature_count=20,
    )
    assert summary.shape == (43,)
    assert np.isfinite(summary).all()


def test_heatmap_depth_features_encode_target_identity():
    first = heatmap_depth_features(0.2, 0.3, 64, 128, 256, 256, 0, 3)
    second = heatmap_depth_features(0.2, 0.3, 64, 128, 256, 256, 2, 3)
    assert first.shape == (22,)
    assert np.isfinite(first).all()
    assert not np.array_equal(first, second)

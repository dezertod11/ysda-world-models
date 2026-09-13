"""Frozen, privileged grounding diagnostics; never a deployable policy claim."""
from dataclasses import replace
import numpy as np

NAME = 'recovery_grounding_diagnostic_20260913'
ARMS = ('rgb_replay', 'oracle_xy_fixed_gate', 'oracle_xyz_fixed_gate', 'oracle_xyz_physical_gate')
SMOKE_CASES = ('x0.2_t5_i25', 'x0.3_t1_i25')


def select_cases(config):
    cases = [dict(j) for j in config['jobs'] if j['phase'] == 'main' and j['init_state_id'] in (25, 26)]
    if len(cases) != 32 or len({j['cell'] for j in cases}) != 16:
        raise ValueError('Expected all 16 frozen cells at init25 and init26, no outcome filtering')
    return cases


def replace_waypoint(localization, target, arm):
    if arm not in ARMS:
        raise ValueError('Unknown diagnostic arm')
    if arm == 'rgb_replay':
        return localization
    target = np.asarray(target, dtype=float)
    if target.shape != (3,) or not np.isfinite(target).all():
        raise ValueError('Named target pose must be finite XYZ')
    position = target.copy()
    if arm == 'oracle_xy_fixed_gate':
        position[2] = localization.world_position[2]
    return replace(localization, world_position=position)


def projection_metrics(localization, target, intrinsic, camera_to_world):
    try:
        from scripts.perception_regrasp import pixel_to_world_plane
        from scripts.probe_repair import project_eef
    except ModuleNotFoundError:
        from perception_regrasp import pixel_to_world_plane
        from probe_repair import project_eef
    target = np.asarray(target, dtype=float)
    pixel = project_eef(target, intrinsic, camera_to_world)
    predicted = np.array([localization['perception_pixel_col'], localization['perception_pixel_row']])
    world = np.array([localization['perception_world_' + a] for a in 'xyz'])
    rebuilt = pixel_to_world_plane(predicted[1], predicted[0], intrinsic, camera_to_world, world[2])
    at_true_z = pixel_to_world_plane(predicted[1], predicted[0], intrinsic, camera_to_world, target[2])
    roundtrip = (pixel_to_world_plane(pixel[1], pixel[0], intrinsic, camera_to_world, target[2])
                 if np.isfinite(pixel).all() else np.full(3, np.nan))
    return dict(target_xyz=target.tolist(), predicted_xyz=world.tolist(), projected_gt_cv=pixel.tolist(),
        predicted_pixel_cv=predicted.tolist(), target_in_front=bool(np.isfinite(pixel).all()),
        pixel_center_error=float(np.linalg.norm(predicted - pixel)),
        xy_error_m=float(np.linalg.norm(world[:2] - target[:2])),
        xy_error_true_plane_m=float(np.linalg.norm(at_true_z[:2] - target[:2])),
        world_reconstruction_error_m=float(np.linalg.norm(rebuilt - world)),
        gt_projection_roundtrip_error_m=float(np.linalg.norm(roundtrip - target)),
        plane_height_error_m=float(abs(world[2] - target[2])))

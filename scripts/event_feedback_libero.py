"""RGB/proprio adapters for event_feedback, reusing the frozen recovery primitives."""
import numpy as np

try:
    from event_feedback import Evidence
except ModuleNotFoundError:
    from scripts.event_feedback import Evidence


class PassiveMonitor:
    def __init__(self, env, description, config, localizer=None, artifact=None, masker=None):
        self.env, self.description, self.config = env, description, config
        self.localizer, self.artifact, self.masker = localizer, artifact, masker
        self.previous = None
        self.last_gripper = -1.
        self.localization = None
        self.diagnostics = {}

    def reset(self):
        self.previous = None

    def __call__(self, obs, actions):
        eef = np.asarray(obs['robot0_eef_pos'], dtype=float)
        if len(actions):
            self.last_gripper = float(actions[-1][6])
        command = float(sum(np.linalg.norm(np.asarray(a)[:3]) for a in actions))
        defaults = dict(eef=tuple(eef), gripper_command=self.last_gripper, commanded_motion=command)
        if self.localizer is None:
            return Evidence(**defaults)
        from collect_online_perception_regrasp import _localize
        from perception_regrasp import raw_agentview_image
        from perception_regrasp_trigger import evaluate_trigger
        from observation_contract import probe_allowed
        from probe_repair import tracking_rgb, project_eef
        from robosuite import macros
        from robosuite.utils.camera_utils import get_camera_intrinsic_matrix, get_camera_extrinsic_matrix
        from grounded_probe import component_mask, masked_motion
        loc = _localize(self.env, obs, self.localizer, self.description)
        self.localization = loc
        gate = evaluate_trigger(loc, eef, self.artifact, mode='workspace_calibrated')
        confidence = gate.finite_pass and gate.confidence_pass
        verdict = 'unknown'
        motion = {'reason': 'no_mask_model'}
        raw = raw_agentview_image(obs)
        rgb = tracking_rgb(raw, macros.IMAGE_CONVENTION)
        camera = get_camera_extrinsic_matrix(self.env.sim, 'agentview')
        intrinsic = get_camera_intrinsic_matrix(self.env.sim, 'agentview', *raw.shape[:2])
        if self.masker is not None:
            probability = self.masker.probability(rgb, self.description)
            mask = component_mask(probability, [loc['perception_pixel_col'], loc['perception_pixel_row']])
            if self.previous is not None:
                old = self.previous
                # Camera motion is not object motion; the first version uses the static external view.
                if np.allclose(camera, old['camera'], atol=1e-8, rtol=0):
                    flow = project_eef(eef, intrinsic, camera) - project_eef(old['eef'], intrinsic, camera)
                    motion = masked_motion(old['rgb'], rgb, old['mask'], mask, flow,
                                           confidence and old['confidence'])
                    verdict = motion['verification']
                else:
                    motion = {'reason': 'camera_moved'}
            self.previous = dict(rgb=rgb, mask=mask, eef=eef.copy(), camera=camera,
                                 confidence=confidence)
        self.diagnostics = dict(localization=loc, geometry_gate=gate.__dict__, passive_motion=motion)
        return Evidence(**defaults, target_distance=(gate.estimated_target_eef_distance_m
                         if gate.finite_pass else None), localization_valid=confidence,
                        geometry_allowed=gate.passed, probe_allowed=probe_allowed(eef, self.last_gripper),
                        grasp_verdict=verdict)


def perform_intervention(kind, obs, t, budget, *, c, p, r, env, tracker, monitor,
                         localizer, artifact, description, cfg, executed):
    """No restore or oracle: return the real state even when a guard rejects repair."""
    from perception_regrasp import localization_record
    from perception_regrasp_trigger import evaluate_trigger
    start = len(executed)
    max_t = t + budget
    if kind in ('preserve_probe', 'verify_regrasp'):
        target = r._eef_position(obs) + np.asarray([0., 0., .04])
        obs, success, current, _, = r._servo_stage(env, obs, tracker, lambda _: target,
            gripper=monitor.last_gripper, steps=min(3, budget), tolerance_m=.005,
            absolute_t=t, max_t=max_t, writer=None, flip_images=cfg.flip_images)
        info = dict(probe_gripper=monitor.last_gripper, probe_steps=current - t,
                    release_veto=True, verification='not_checked')
        if kind == 'preserve_probe' or success or current >= max_t:
            monitor.reset()
            return obs, success, executed[start:], info
        after = monitor(obs, executed[start:])
        info['verification'] = after.grasp_verdict
        if after.grasp_verdict != 'miss' or not after.geometry_allowed:
            monitor.reset()
            return obs, success, executed[start:], info
    else:
        current, info = t, {}
    def validator(localization, eef):
        return evaluate_trigger(localization_record(localization), eef, artifact,
                                mode='workspace_calibrated', require_miss=False).__dict__
    obs, success, current, _, repair = r._run_perception_regrasp(env, obs, tracker,
        localizer, description, absolute_t=current, max_t=max_t, writer=None,
        flip_images=cfg.flip_images, min_confidence=0., localization_validator=validator)
    info.update(repair=repair, release_veto=False)
    monitor.reset()
    return obs, success, executed[start:], info

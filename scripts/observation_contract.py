"""Information-before-release experiment; oracle arms are diagnostic only."""
from dataclasses import replace
import numpy as np

NAME = 'observation_contract_20260911'
ARMS = ('continue_h8', 'physical_regrasp', 'refresh_open_only', 'refresh_preserve_only',
        'refresh_open_regrasp', 'refresh_preserve_regrasp', 'oracle_calibrated', 'oracle_physical')
REFRESH = ARMS[2:6]
ORACLES = ARMS[6:]
CONTRASTS = (
    ('refresh_preserve_regrasp', 'physical_regrasp'),
    ('refresh_preserve_regrasp', 'refresh_open_regrasp'),
    ('refresh_preserve_regrasp', 'refresh_preserve_only'),
    ('refresh_preserve_only', 'refresh_open_only'),
    ('oracle_calibrated', 'physical_regrasp'),
    ('oracle_physical', 'oracle_calibrated'),
)
PARAMS = dict(retreat_z=.08, retreat_steps=3, probe_xy_limit=.45, probe_z_lower=0.,
              probe_z_upper=.50, physical_lower=[-.45, -.45, -.03], physical_upper=[.45, .45, .45])


def probe_allowed(eef, previous_gripper):
    xyz = np.asarray(eef, dtype=float)
    return bool(xyz.shape == (3,) and np.isfinite(xyz).all() and np.isfinite(previous_gripper)
        and np.max(np.abs(xyz[:2])) <= PARAMS['probe_xy_limit']
        and PARAMS['probe_z_lower'] <= xyz[2]
        and xyz[2] + PARAMS['retreat_z'] <= PARAMS['probe_z_upper'])


def refresh_allowed(decision, eef, previous_gripper):
    uncertain = not (decision.confidence_pass and decision.workspace_pass and decision.reach_pass)
    return bool(not decision.passed and decision.finite_pass and uncertain and probe_allowed(eef, previous_gripper))


def physical_workspace(world):
    xyz = np.asarray(world, dtype=float)
    return bool(xyz.shape == (3,) and np.isfinite(xyz).all() and
                np.all(xyz >= PARAMS['physical_lower']) and np.all(xyz <= PARAMS['physical_upper']))


def gate(loc, eef, artifact, *, physical=False, require_miss=True):
    from perception_regrasp_trigger import evaluate_trigger
    d = evaluate_trigger(loc, eef, artifact, mode='workspace_calibrated', require_miss=require_miss)
    if physical:
        workspace = physical_workspace([loc['perception_world_' + a] for a in 'xyz'])
        d = replace(d, workspace_pass=workspace,
            passed=bool(d.finite_pass and d.confidence_pass and workspace and d.reach_pass and d.miss_distance_pass))
    return d


def primitive(c, p, r, env, obs, tracker, localizer, artifact, description, cfg, t,
              *, gripper, observe_only, locate, physical=False):
    """Same Cartesian stages as the frozen primitive; only the first grip can differ."""
    info = dict(perception_localization_used=False, perception_regrasp_executed=False,
                observation_gripper=float(gripper), observe_only=bool(observe_only))
    total = 0
    target = r._eef_position(obs) + np.array([0., 0., .08])
    obs, success, t, n = r._servo_stage(env, obs, tracker, lambda _: target, gripper=gripper,
        steps=3, tolerance_m=.015, absolute_t=t, max_t=280, writer=None, flip_images=cfg.flip_images)
    total += n
    info['observation_steps'] = n
    from collect_feedback_controls import observation_arrays
    from p5_repeat_feedback import array_digest
    info['probe_end_audit'] = dict(t=t, sim_state=np.asarray(env.get_sim_state()).tolist(),
        observation_hashes={k: array_digest(v) for k, v in observation_arrays(obs, 'obs__').items()})
    if success:
        return obs, success, t, total, info
    loc = locate(obs)
    decision = gate(loc, r._eef_position(obs), artifact, physical=physical, require_miss=False)
    info.update(loc, perception_localization_used=True, perception_confidence_pass=True,
                perception_guard_pass=decision.passed,
                **{'perception_guard_' + k: v for k, v in decision.__dict__.items()})
    if observe_only or not decision.passed:
        return obs, False, t, total, info
    info['perception_regrasp_executed'] = True
    point = np.asarray([loc['perception_world_' + a] for a in 'xyz'], dtype=np.float64)
    for offset, count, tolerance in ((.08, 7, .018), (.012, 6, .012)):
        target = point + np.asarray([0., 0., offset])
        obs, success, t, n = r._servo_stage(env, obs, tracker, lambda _: target,
            gripper=-1., steps=count, tolerance_m=tolerance, absolute_t=t,
            max_t=280, writer=None, flip_images=cfg.flip_images)
        total += n
        if success:
            return obs, success, t, total, info
    actions = np.repeat(np.asarray([[0., 0., 0., 0., 0., 0., 1.]], dtype=np.float32), 4, axis=0)
    obs, success, t, n = r._execute(env, obs, actions, tracker, absolute_t=t, max_t=280,
                                   writer=None, flip_images=cfg.flip_images)
    total += n
    if success:
        return obs, success, t, total, info
    target = r._eef_position(obs) + np.asarray([0., 0., .10])
    obs, success, t, n = r._servo_stage(env, obs, tracker, lambda _: target,
        gripper=1., steps=5, tolerance_m=.015, absolute_t=t, max_t=280,
        writer=None, flip_images=cfg.flip_images)
    return obs, success, t, total + n, info


def intervene(c, p, r, env, obs, tracker, localizer, artifact, description, cfg,
              arm, loc, t, job, model, stats, resize):
    if arm not in ARMS:
        raise ValueError('Unknown observation arm: ' + arm)
    from perception_regrasp import canonical_object_name, localization_record
    original = gate(loc, r._eef_position(obs), artifact)
    diag = dict(initial_trigger_passed=original.passed, initial_t72_trigger_passed=original.passed,
        initial_gate=original.__dict__, initial_localization=loc, verification='not_probed',
        probe_steps=0, regrasp_steps=0, repair_requested=False, refresh_requested=False,
        delay_policy_queries=0, oracle=arm in ORACLES, previous_gripper=job['previous_gripper'])
    success = bool(env.check_success())
    if success or arm == 'continue_h8':
        return obs, success, t, diag, [], 5
    def learned(o):
        return p._localize(env, o, localizer, description)
    def oracle(o):
        # Privileged poses are reachable only from the explicitly tagged oracle arms.
        xyz = r._target_position(tracker, o)
        object_name = canonical_object_name(description)
        threshold = artifact['objects'][object_name]['score_range_lower']
        return dict(perception_object=object_name, perception_score_range=threshold,
            oracle_confidence_forced=True, **{'perception_world_' + a: float(v) for a, v in zip('xyz', xyz)})
    locate = oracle if arm in ORACLES else learned
    physical = arm == 'oracle_physical'
    if arm in ORACLES:
        loc = locate(obs)
        decision = gate(loc, r._eef_position(obs), artifact, physical=physical)
        diag['oracle_initial_gate'] = decision.__dict__
        requested = decision.passed
    else:
        requested = original.passed
    gripper, only = -1., False
    if arm in REFRESH and not original.passed:
        requested = refresh_allowed(original, r._eef_position(obs), job['previous_gripper'])
        diag['refresh_requested'] = requested
        gripper = float(np.clip(job['previous_gripper'], -1., 1.)) if 'preserve' in arm else -1.
        only = arm.endswith('_only')
    if requested:
        diag['repair_requested'] = not only
        if arm == 'physical_regrasp':
            def validator(localization, eef):
                return gate(localization_record(localization), eef, artifact, require_miss=False).__dict__
            obs, success, t, n, info = r._run_perception_regrasp(env, obs, tracker, localizer, description,
                absolute_t=t, max_t=280, writer=None, flip_images=cfg.flip_images,
                min_confidence=0., localization_validator=validator)
        else:
            obs, success, t, n, info = primitive(c, p, r, env, obs, tracker, localizer,
                artifact, description, cfg, t, gripper=gripper, observe_only=only,
                locate=locate, physical=physical)
        diag.update(regrasp_steps=n, regrasp_diagnostics=info)
        if diag['refresh_requested']:
            diag['probe_steps'] = info['observation_steps']
    return obs, success, t, diag, [], 5


def make_jobs(parent):
    source = [j for j in parent['jobs'] if j['phase'] == 'screen']
    jobs = []
    for case in ('x0.2_t2_i46_r0', 'x0.2_t9_i46_r0', 'x0.1_t9_i46_r0'):
        old = next(j for j in source if j['id'] == case)
        jobs.append(dict(old, phase='smoke', source_phase='screen', source_id=case,
                         prefix_seed=old['rollout_seed'], suffix_repeat=0))
    for suffix in (0, 1):
        for i, old in enumerate(source):
            seed = old['rollout_seed'] if suffix == 0 else 1_850_000_000 + i * 100_000
            jobs.append(dict(old, id=old['id'] + f'_s{suffix}', source_id=old['id'],
                source_phase='screen', prefix_seed=old['rollout_seed'], rollout_seed=seed,
                repeat=old['repeat'] * 2 + suffix, suffix_repeat=suffix))
    return jobs

"""Frozen timing/eligibility ablation. Simulator labels are never gate inputs."""
import numpy as np

NAME = 'timing_eligibility_20260911_v2'
ARMS = ('continue_h8', 'physical_regrasp', 'delayed_regrasp_h8',
        'delayed_latched_checked_h8', 'delayed_latched_h8')
DELAYED = ARMS[2:]
CONTRASTS = (
    ('delayed_latched_checked_h8', 'delayed_regrasp_h8'),
    ('delayed_latched_checked_h8', 'physical_regrasp'),
    ('delayed_regrasp_h8', 'physical_regrasp'),
    ('delayed_latched_h8', 'delayed_regrasp_h8'),
    ('delayed_latched_h8', 'delayed_latched_checked_h8'),
    ('physical_regrasp', 'continue_h8'),
)


def request_repair(arm, original, fresh, checked, success=False):
    if arm not in ARMS:
        raise ValueError('Unknown timing arm: ' + arm)
    if success or not original or arm == 'continue_h8':
        return False
    if arm == 'delayed_regrasp_h8':
        return bool(fresh)
    if arm == 'delayed_latched_checked_h8':
        return bool(checked)
    return True


def gate_record(decision):
    row = dict(decision.__dict__)
    row['failed_checks'] = [k for k in ('finite_pass', 'confidence_pass', 'workspace_pass',
                                      'miss_distance_pass', 'reach_pass') if not row[k]]
    return row


def intervene(c, p, r, env, obs, tracker, localizer, artifact, description, cfg,
              arm, loc, t, job, model, stats, resize):
    from perception_regrasp_trigger import evaluate_trigger
    from perception_regrasp import localization_record
    from collect_feedback_controls import observation_arrays
    from p5_repeat_feedback import array_digest

    original = evaluate_trigger(loc, r._eef_position(obs), artifact, mode='workspace_calibrated')
    success = bool(env.check_success())
    queries = []
    next_query = 5
    diag = dict(initial_trigger_passed=original.passed, initial_t72_trigger_passed=original.passed,
                verification='not_probed', probe_steps=0, regrasp_steps=0, repair_requested=False,
                initial_gate=gate_record(original), initial_localization=loc, delay_policy_queries=0)
    if arm in DELAYED and original.passed and not success:
        seeds = tuple(job['rollout_seed'] + 5000 + i for i in range(4))
        samples, metrics = c._sample_candidates(cfg, model, stats, obs, description, seeds, resize,
                                                 prediction_mode='parallel')
        index, _ = c._select_max_value(samples, open_loop_steps=8)
        queries.append(dict(t=t, seeds=seeds, index=index, metrics=metrics, role='delay_before_regrasp'))
        obs, success, t, _ = c._execute_actions(env, obs, samples[index]['actions'][:8], tracker,
                                               absolute_t=t, max_t=280)
        next_query = 6
        del samples
        diag['delay_policy_queries'] = 1
        if not success:
            loc = p._localize(env, obs, localizer, description)
    fresh = evaluate_trigger(loc, r._eef_position(obs), artifact, mode='workspace_calibrated')
    checked = evaluate_trigger(loc, r._eef_position(obs), artifact, mode='workspace_calibrated', require_miss=False)
    diag.update(fresh_gate=gate_record(fresh), fresh_nonmiss_gate=gate_record(checked),
                fresh_localization=loc, fresh_gate_evaluated_after_success=bool(success),
                decision_t=t, decision_eef_position=r._eef_position(obs).tolist())
    # All delayed policies must reach the same observation before their distinct gates.
    if diag['delay_policy_queries']:
        diag['delay_end_audit'] = dict(t=t, sim_state=np.asarray(env.get_sim_state()).tolist(),
            observation_hashes={k: array_digest(v) for k, v in observation_arrays(obs, 'obs__').items()})
    repair = request_repair(arm, original.passed, fresh.passed, checked.passed, success)
    diag['repair_requested'] = repair
    if repair:
        def validator(localization, eef):
            return evaluate_trigger(localization_record(localization), eef, artifact,
                                    mode='workspace_calibrated', require_miss=False).__dict__
        obs, success, t, n, info = r._run_perception_regrasp(env, obs, tracker, localizer, description,
            absolute_t=t, max_t=280, writer=None, flip_images=cfg.flip_images,
            min_confidence=0., localization_validator=validator)
        diag.update(regrasp_steps=n, regrasp_diagnostics=info)
    return obs, success, t, diag, queries, next_query


def make_jobs(parent, calibration):
    cells = list(dict.fromkeys((j['position_level'], j['task_id']) for j in parent['jobs']))
    jobs = []
    for phase, case in [('screen', 'x0.2_t2_i35_r1'), ('transfer', 'y0.1_t9_i34_r1')]:
        old = next(j for j in parent['jobs'] if j['phase'] == phase and j['id'] == case)
        jobs.append(dict(old, phase='smoke', source_phase=phase, source_id=case))
    for ci, (level, task) in enumerate(cells):
        seen = bool(((calibration.position_level == level) & (calibration.task_id == task)).any())
        for init in range(46, 50):
            if ((calibration.position_level == level) & (calibration.task_id == task) &
                    (calibration.init_state_id == init)).any():
                raise ValueError('Calibration overlap')
            for repeat in range(2):
                jobs.append(dict(id=f'{level}_t{task}_i{init}_r{repeat}', phase='screen',
                    cell=f'{level}_t{task}', position_level=level, task_id=task,
                    init_state_id=init, repeat=repeat, suite='libero_object_temp',
                    calibration_cell_seen=seen, rollout_seed=1_600_000_000 + ci * 10_000_000 + init * 100_000 + repeat * 50_000))
    return jobs

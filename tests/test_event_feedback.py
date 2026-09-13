from dataclasses import asdict, replace
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from scripts.event_feedback import (
    EventConfig, Evidence, EventController, PlanMemory, chunk_metrics, run_control_loop,
)


def evidence(**kwargs):
    return Evidence(**dict(dict(eef=(0., 0., 0.), gripper_command=1., commanded_motion=1.), **kwargs))


@pytest.mark.parametrize('change', [dict(min_prefix=16), dict(action_scale=[0.] * 7),
    dict(history_steps=3), dict(persistence=0), dict(max_interventions=-1),
    dict(value_std_threshold=float('nan')), dict(monitor_stride=4.)])
def test_bad_config_rejected(change):
    with pytest.raises(ValueError):
        EventConfig(**change)


def test_exact_sample_std_aggregation_and_no_k1_evidence():
    cfg = EventConfig()
    actions = np.stack([np.zeros((16, 7)), np.ones((16, 7))])
    metrics = chunk_metrics(actions, [0., 2.], cfg)
    assert metrics['action_prefix_std'] == .5
    assert metrics['value_std'] == 1.
    assert metrics['value_range'] == 2.
    single = chunk_metrics(actions[:1], [1.], cfg)
    assert EventController(cfg).query_reasons(single) == []


@pytest.mark.parametrize('corrupt', ['nan', 'horizon', 'value_count'])
def test_bad_samples_fail_before_execution(corrupt):
    actions, values = np.zeros((2, 16, 7)), [0., 1.]
    if corrupt == 'nan':
        actions[0, 0, 0] = np.nan
    elif corrupt == 'horizon':
        actions = actions[:, :8]
    else:
        values = [1.]
    with pytest.raises(ValueError):
        chunk_metrics(actions, values, EventConfig())


def test_overlap_aligns_absolute_indices_not_local_chunk_indices():
    memory = PlanMemory(EventConfig())
    old = np.repeat(np.arange(16)[None, :, None], 7, axis=2)
    new = np.repeat(np.arange(8, 24)[None, :, None], 7, axis=2)
    assert memory.update(100, old, 0)['overlap_steps'] == 0
    result = memory.update(108, new, 0)
    assert result['overlap_steps'] == 8
    assert result['overlap_pose_rmse'] == 0
    assert memory.update(124, new, 0)['overlap_pose_rmse'] is None
    memory.clear()
    assert memory.update(999, old, 0)['overlap_steps'] == 0


def test_state_decision_is_invariant_to_absolute_time_shift():
    outcomes = []
    for shift in (0, 47, 72, 1000):
        controller = EventController(EventConfig(), 'regrasp')
        rows = []
        for delta in (0, 4, 8, 12):
            e = evidence(localization_valid=True, target_distance=.02, geometry_allowed=True,
                         grasp_verdict='unknown' if delta == 0 else 'miss')
            rows.append(controller.observe(shift + delta, e))
        outcomes.append((rows, controller.route(e)))
    assert all(outcome == outcomes[0] for outcome in outcomes)
    assert outcomes[0][1] == 'regrasp'


@pytest.mark.parametrize('verdict', ['held', 'unknown'])
@pytest.mark.parametrize('method', ['regrasp', 'preserve_probe', 'verify_regrasp'])
def test_held_and_unknown_never_authorize_opening_or_probe(verdict, method):
    controller = EventController(EventConfig(), method)
    e = evidence(localization_valid=True, target_distance=.01, geometry_allowed=True,
                 probe_allowed=True, grasp_verdict=verdict)
    controller.observe(0, e)
    assert controller.route(e) == 'requery'


def test_miss_requires_prior_close_near_target_and_geometry():
    controller = EventController(EventConfig(), 'regrasp')
    e = evidence(geometry_allowed=True, grasp_verdict='miss')
    controller.observe(0, e)
    assert controller.route(e) == 'requery'
    controller.observe(4, replace(e, localization_valid=True, target_distance=.01))
    assert controller.route(e) == 'regrasp'
    assert controller.route(replace(e, geometry_allowed=False)) == 'requery'
    controller.observe(8, replace(e, gripper_command=-1.))
    assert controller.route(e) == 'requery'


def test_stall_persistence_duplicate_observations_and_recovery_reset():
    c = EventController(EventConfig(max_interventions=2), 'regrasp')
    assert c.observe(0, evidence())['reasons'] == []
    assert c.observe(4, evidence())['reasons'] == []
    assert c.observe(8, evidence())['reasons'] == []
    assert c.observe(12, evidence())['reasons'] == ['stalled']
    with pytest.raises(ValueError, match='same observation'):
        c.observe(12, evidence())
    c.mark(12)
    assert not c.available(27) and c.available(28)
    assert c.observe(16, evidence())['reasons'] == []
    c.mark(28)
    assert not c.available(1000)


def test_controller_does_not_consume_privileged_labels():
    fields = asdict(evidence())
    assert not {'success', 'object_pose', 'sim_state', 'query_idx', 't'} & fields.keys()
    with pytest.raises(TypeError):
        Evidence(**fields, success=True)


def rollout(*, timing='event', fixed_step=None, risky=False, success_at=None, method='requery',
            physical_steps=0, budget=48):
    state = [0]
    queries = []
    def step(action):
        state[0] += 1
        return state[0], state[0] == success_at
    def policy(obs, t, q):
        queries.append(t)
        a = np.zeros((2, 16, 7), dtype=np.float32)
        a[:, :, 0] = t / 100.
        if risky:
            a[0, :, :6] -= 1.
            a[1, :, :6] += 1.
        return a, [0., 1.], {}
    def monitor(obs, actions):
        return evidence(eef=(float(obs), 0., 0.), commanded_motion=0.,
            localization_valid=True, target_distance=.01, geometry_allowed=True,
            probe_allowed=True, grasp_verdict='miss')
    def intervene(kind, obs, t, remaining):
        executed = []
        success = False
        for _ in range(min(physical_steps, remaining)):
            executed.append(np.zeros(7))
            obs, success = step(executed[-1])
            if success:
                break
        return obs, success, executed, {'mock': True}
    cfg = EventConfig(max_steps=budget, value_std_threshold=2., persistence=999,
                      overlap_rmse_threshold=2.)
    result = run_control_loop(0, policy=policy, step=step, monitor=monitor,
        intervene=intervene, config=cfg, method=method, timing=timing, fixed_step=fixed_step)
    assert len(result['actions']) == result['final_t'] == state[0]
    return result, queries


def test_no_event_exactly_repeats_h16_and_no_extra_calls():
    base, bq = rollout(timing='none')
    event, eq = rollout()
    np.testing.assert_array_equal(base['actions'], event['actions'])
    assert bq == eq == [0, 16, 32]
    assert event['events'] == []


def test_shadow_does_not_modify_policy_actions_or_rng_call_schedule():
    base, bq = rollout(timing='none', risky=True)
    shadow, sq = rollout(timing='shadow', risky=True)
    np.testing.assert_array_equal(base['actions'], shadow['actions'])
    assert bq == sq
    assert not shadow['events'][0]['executed']


def test_event_before_former_magic_time_and_resume_base_horizon():
    result, queries = rollout(risky=True)
    assert queries == [0, 8, 16, 32]
    assert len(result['events']) == 1
    assert result['events'][0]['t'] == 8
    assert result['queries'][1]['metrics']['overlap_steps'] == 8
    assert result['queries'][1]['planned_end'] == 16
    assert 'action_sample_disagreement' in result['events'][0]['reasons']


def test_explicit_fixed_control_has_original_shared_prefix_structure():
    result, queries = rollout(timing='fixed', fixed_step=72, budget=112)
    assert queries == [0, 16, 32, 48, 64, 72, 80, 96]
    assert [e['t'] for e in result['events']] == [72]
    assert result['queries'][5]['planned_end'] == 80


@pytest.mark.parametrize('method', ['regrasp', 'preserve_probe', 'verify_regrasp'])
def test_all_recovery_routes_use_event_trigger_and_share_action_budget(method):
    result, queries = rollout(risky=True, method=method, physical_steps=25)
    assert result['events'][0]['kind'] == method
    assert queries == [0, 33]
    assert result['final_t'] == 48
    assert result['events'][0]['physical_steps'] == 25


def test_terminal_before_event_and_during_physical_steps():
    result, queries = rollout(risky=True, success_at=5)
    assert result['success'] and result['final_t'] == 5 and result['events'] == []
    result, queries = rollout(risky=True, success_at=12, method='regrasp', physical_steps=25)
    assert result['success'] and queries == [0] and result['final_t'] == 12


def test_insufficient_recovery_budget_falls_back_without_opening():
    result, queries = rollout(risky=True, method='regrasp', physical_steps=25, budget=24)
    assert result['events'][0]['kind'] == 'requery'
    assert 'insufficient_recovery_budget' in result['events'][0]['reasons']
    assert queries == [0, 8, 16]


def test_control_names_and_no_implicit_fixed_time():
    with pytest.raises(ValueError, match='required only'):
        rollout(timing='fixed')
    with pytest.raises(ValueError, match='required only'):
        rollout(fixed_step=72)


def test_collector_cli_validation_without_importing_cuda(tmp_path):
    import json
    root = Path(__file__).resolve().parents[1]
    cases, parameters = tmp_path / 'cases.json', tmp_path / 'parameters.json'
    cases.write_text(json.dumps([dict(suite='libero_object', task_id=0, init_state_id=0, rollout_seed=5)]))
    parameters.write_text('{}')
    output = subprocess.run([sys.executable, str(root / 'scripts/collect_event_feedback.py'),
        '--cases', str(cases), '--parameters', str(parameters), '--output', str(tmp_path / 'out'),
        '--validate-only'], text=True, capture_output=True, timeout=30)
    assert output.returncode == 0, output.stderr
    assert json.loads(output.stdout)['timing'] == 'event'
    assert not (tmp_path / 'out').exists()


def test_calibration_uses_group_maxima_not_correlated_queries():
    from scripts.calibrate_event_feedback import calibrate
    rows = []
    for init in range(40):
        for seed in range(2):
            rows.append(dict(success=True, timing='shadow',
                case=dict(suite='suite', task_id=0, init_state_id=init, rollout_seed=seed),
                queries=[dict(metrics=dict(action_prefix_std=float(init + seed),
                    value_std=float(init + seed) / 10, overlap_pose_rmse=None))] * 100))
    params, report = calibrate(rows, EventConfig(), .1)
    assert len(report['calibration_groups']) == 40
    assert report['scores']['action_prefix_std']['groups'] == 40
    assert params['action_std_threshold'] == 39.
    assert report['disabled_features'] == ['overlap_pose_rmse']
    assert params['overlap_rmse_threshold'] > 1e100


def test_calibration_refuses_small_data_and_intervention_biased_samples():
    from scripts.calibrate_event_feedback import calibrate
    row = dict(success=True, timing='none', case=dict(suite='s', task_id=0, init_state_id=0),
               queries=[dict(metrics=dict(action_prefix_std=.1, value_std=.2))])
    with pytest.raises(ValueError, match='Insufficient'):
        calibrate([row] * 100, EventConfig())
    with pytest.raises(ValueError, match='non-intervened'):
        calibrate([dict(row, timing='event')], EventConfig())


@pytest.mark.parametrize('verdict', ['held', 'unknown'])
def test_probe_adapter_veto_keeps_physical_state_and_never_calls_release(monkeypatch, verdict):
    from types import SimpleNamespace
    from scripts.event_feedback_libero import perform_intervention
    monkeypatch.setitem(sys.modules, 'perception_regrasp', SimpleNamespace(localization_record=lambda x: x))
    monkeypatch.setitem(sys.modules, 'perception_regrasp_trigger', SimpleNamespace(evaluate_trigger=None))
    executed = []
    def servo(env, obs, tracker, target, **kw):
        assert kw['gripper'] == .7
        executed.extend([np.zeros(7)] * 3)
        return {'after_probe': True}, False, kw['absolute_t'] + 3, 3
    def repair(*args, **kwargs):
        pytest.fail('Release called on held/unknown object')
    class Monitor:
        last_gripper = .7
        def __call__(self, obs, actions):
            assert obs['after_probe'] and len(actions) == 3
            return evidence(grasp_verdict=verdict, geometry_allowed=True)
        def reset(self):
            pass
    r = SimpleNamespace(_eef_position=lambda obs: np.zeros(3), _servo_stage=servo,
                        _run_perception_regrasp=repair)
    out, success, physical, info = perform_intervention('verify_regrasp', {}, 40, 240,
        c=None, p=None, r=r, env=None, tracker=None, monitor=Monitor(), localizer=None,
        artifact={}, description='target', cfg=SimpleNamespace(flip_images=True), executed=executed)
    assert out['after_probe'] and not success and len(physical) == 3
    assert info['verification'] == verdict and info['release_veto']


def test_calibration_never_reuses_even_failed_development_inits():
    from scripts.calibrate_event_feedback import calibrate
    rows = [dict(success=True, timing='shadow',
        case=dict(suite='s', task_id=0, init_state_id=i),
        queries=[dict(metrics=dict(action_prefix_std=.1, value_std=.2))]) for i in range(40)]
    rows.append(dict(rows[0], success=False, case=dict(suite='s', task_id=0, init_state_id=99)))
    _, report = calibrate(rows, EventConfig())
    assert 's/0/99' in report['calibration_groups']
    assert 's/0/99' not in report['successful_groups']

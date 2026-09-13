import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import observation_contract as m

ROOT = Path(__file__).resolve().parents[1]


def decision(eligible=True, **kwargs):
    return SimpleNamespace(passed=eligible, finite_pass=True, confidence_pass=eligible,
        workspace_pass=True, reach_pass=True, miss_distance_pass=True, **kwargs)


@pytest.mark.parametrize('xyz,grip,ok', [([0, 0, .2], 1.002, True),
    ([0, 0, .2], -1.002, True), ([.451, 0, .2], 1, False),
    ([0, 0, -.001], 1, False), ([0, 0, .421], 1, False),
    ([0, 0, np.nan], 1, False), ([0, 0, .2], np.nan, False), ([0, 0], 1, False)])
def test_probe_bounds(xyz, grip, ok):
    assert m.probe_allowed(xyz, grip) == ok


def test_miss_only_rejection_does_not_probe():
    d = decision(False)
    assert m.refresh_allowed(d, [0, 0, .2], 1)
    d.confidence_pass, d.miss_distance_pass = True, False
    assert not m.refresh_allowed(d, [0, 0, .2], 1)
    d.confidence_pass, d.finite_pass = False, False
    assert not m.refresh_allowed(d, [0, 0, .2], 1)
    assert not m.refresh_allowed(decision(), [0, 0, .2], 1)


def test_manifest_existing_prefixes_and_distinct_suffixes():
    parent = json.loads((ROOT / 'experiments/campaigns/timing_eligibility_20260911_v2/config.json').read_text())
    jobs = m.make_jobs(parent)
    smoke = [j for j in jobs if j['phase'] == 'smoke']
    screen = [j for j in jobs if j['phase'] == 'screen']
    assert len(smoke) == 3 and len(screen) == 192
    assert len({j['id'] for j in screen}) == 192
    assert len({j['source_id'] for j in screen}) == 96
    assert len({(j['cell'], j['init_state_id'], j['repeat']) for j in screen}) == 192
    assert {j['init_state_id'] for j in screen} == {46, 47, 48, 49}
    seeds = sorted(j['rollout_seed'] for j in screen)
    assert min(np.diff(seeds)) >= 50000 and max(seeds) + 32000 < 2**31
    for job in screen:
        if not job['suffix_repeat']:
            assert job['prefix_seed'] == job['rollout_seed']
        else:
            assert job['prefix_seed'] != job['rollout_seed']


@pytest.mark.parametrize('arm', m.ARMS)
@pytest.mark.parametrize('eligible', (False, True))
@pytest.mark.parametrize('grip', (-1.002, 1.002))
def test_routing_preserves_baseline_and_isolates_oracle(monkeypatch, arm, eligible, grip):
    oracle_calls, calls = [], []
    monkeypatch.setitem(sys.modules, 'perception_regrasp', SimpleNamespace(
        canonical_object_name=lambda x: 'target', localization_record=lambda x: x))
    monkeypatch.setattr(m, 'gate', lambda *a, **k: decision(eligible if not a[0].get('oracle_confidence_forced') else True))
    def target(*_):
        assert arm in m.ORACLES
        oracle_calls.append(1)
        return [.1, 0, .05]
    def primitive(*a, **k):
        calls.append(k)
        k['locate'](a[4])
        return a[4], False, 75, 3, dict(observation_steps=3)
    monkeypatch.setattr(m, 'primitive', primitive)
    def original(*a, **k):
        calls.append({'original': True})
        return a[1], False, 75, 3, {}
    r = SimpleNamespace(_eef_position=lambda o: np.array([0., 0., .2]),
                        _target_position=target, _run_perception_regrasp=original)
    p = SimpleNamespace(_localize=lambda *a: {})
    result = m.intervene(None, p, r, SimpleNamespace(check_success=lambda: False), {},
        None, None, {'objects': {'target': {'score_range_lower': 1}}}, 'target',
        SimpleNamespace(flip_images=True), arm, {}, 72, {'previous_gripper': grip}, None, None, None)
    diag = result[3]
    assert result[-2:] == ([], 5)
    assert bool(oracle_calls) == (arm in m.ORACLES)
    expected = arm in m.ORACLES or arm in m.REFRESH or (arm == 'physical_regrasp' and eligible)
    assert bool(calls) == expected
    assert diag['refresh_requested'] == (arm in m.REFRESH and not eligible)
    if arm in m.REFRESH:
        assert calls[0]['observe_only'] == (not eligible and arm.endswith('_only'))
        expected_grip = float(np.clip(grip, -1, 1)) if not eligible and 'preserve' in arm else -1.
        assert calls[0]['gripper'] == expected_grip


@pytest.mark.parametrize('observe_only,guard', ((True, True), (False, False), (False, True)))
def test_primitive_stage_geometry_and_probe_audit(monkeypatch, observe_only, guard):
    stages = []
    def servo(env, obs, tracker, target, **k):
        stages.append((target(obs).tolist(), k['gripper'], k['steps'], k['tolerance_m']))
        assert k['max_t'] == 280
        return obs, False, k['absolute_t'] + k['steps'], k['steps']
    def execute(env, obs, actions, tracker, **k):
        np.testing.assert_array_equal(actions, np.tile([0, 0, 0, 0, 0, 0, 1], (4, 1)))
        return obs, False, k['absolute_t'] + 4, 4
    r = SimpleNamespace(_eef_position=lambda o: np.array([0., 0., .2]), _servo_stage=servo, _execute=execute)
    monkeypatch.setattr(m, 'gate', lambda *a, **k: decision(guard))
    monkeypatch.setitem(sys.modules, 'collect_feedback_controls', SimpleNamespace(observation_arrays=lambda *a: {'x': np.zeros(1)}))
    monkeypatch.setitem(sys.modules, 'p5_repeat_feedback', SimpleNamespace(array_digest=lambda x: 'digest'))
    result = m.primitive(None, None, r, SimpleNamespace(get_sim_state=lambda: np.zeros(2)), {}, None,
        None, {}, 'target', SimpleNamespace(flip_images=True), 72, gripper=1., observe_only=observe_only,
        locate=lambda obs: dict(perception_world_x=.1, perception_world_y=0., perception_world_z=.05))
    full = guard and not observe_only
    assert result[2:4] == ((97, 25) if full else (75, 3))
    assert result[-1]['probe_end_audit']['t'] == 75
    assert len(stages) == (4 if full else 1)
    assert stages[0][1:] == (1., 3, .015)
    np.testing.assert_allclose(stages[0][0], [0, 0, .28])
    if full:
        assert [s[1:3] for s in stages[1:]] == [(-1., 7), (-1., 6), (1., 5)]
        np.testing.assert_allclose([s[0] for s in stages[1:]], [[.1, 0, .13], [.1, 0, .062], [0, 0, .3]])


def test_physical_gate_changes_workspace_only(monkeypatch):
    from scripts.perception_regrasp_trigger import TriggerDecision
    base = TriggerDecision('workspace_calibrated', False, True, True, False, True, True, .2, 1.)
    monkeypatch.setitem(sys.modules, 'perception_regrasp_trigger', SimpleNamespace(evaluate_trigger=lambda *a, **k: base))
    loc = dict(perception_world_x=.05, perception_world_y=.04, perception_world_z=.073)
    assert m.gate(loc, [0, 0, .2], {}, physical=True).passed
    assert m.gate(loc, [0, 0, .2], {}) == base
    loc['perception_world_x'] = .5
    assert not m.gate(loc, [0, 0, .2], {}, physical=True).passed


def test_cached_prefix_seed_reapplied_after_loader():
    tree = ast.parse((ROOT / 'scripts/collect_observation_contract.py').read_text())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) and ast.unparse(stmt.value.func) == 'legacy.prefix':
                    assert ast.unparse(node.body[i-1]) == "c.set_seed_everywhere(job['rollout_seed'])"
                    found = True
    assert found

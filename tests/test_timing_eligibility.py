import itertools
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.timing_eligibility import ARMS, DELAYED, gate_record, intervene, make_jobs, request_repair


@pytest.mark.parametrize('original,fresh,checked,success', itertools.product((False, True), repeat=4))
def test_distinct_gate_policies(original, fresh, checked, success):
    active = original and not success
    assert not request_repair('continue_h8', original, fresh, checked, success)
    assert request_repair('physical_regrasp', original, fresh, checked, success) == active
    assert request_repair('delayed_regrasp_h8', original, fresh, checked, success) == (active and fresh)
    assert request_repair('delayed_latched_checked_h8', original, fresh, checked, success) == (active and checked)
    assert request_repair('delayed_latched_h8', original, fresh, checked, success) == active


def test_new_screen_is_disjoint_from_calibration_and_old_holdout():
    root = Path(__file__).resolve().parents[1]
    parent = json.loads((root / 'experiments/campaigns/grounded_probe_20260911_v2/config.json').read_text())
    calibration = pd.read_csv(root / 'experiments/frozen_models/perception_regrasp_20260904/calibration_manifest.csv')
    jobs = make_jobs(parent, calibration)
    assert len([j for j in jobs if j['phase'] == 'smoke']) == 2
    screen = [j for j in jobs if j['phase'] == 'screen']
    assert len(screen) == 96
    assert {j['init_state_id'] for j in screen} == {46, 47, 48, 49}
    seeds = sorted(j['rollout_seed'] for j in screen)
    assert min(np.diff(seeds)) >= 50000
    assert max(seeds) + 32000 < 2**31
    calibration.loc[calibration.index[0], ['position_level', 'task_id', 'init_state_id']] = ['x0.2', 2, 46]
    with pytest.raises(ValueError, match='overlap'):
        make_jobs(parent, calibration)


@pytest.mark.parametrize('arm', ARMS)
@pytest.mark.parametrize('success_after_delay', (False, True))
def test_intervention_delay_seeds_and_current_primitive_guard(monkeypatch, arm, success_after_delay):
    def decision(loc, eef, artifact, *, mode, require_miss=True):
        ok = loc['initial'] or not require_miss
        return SimpleNamespace(passed=ok, finite_pass=True, confidence_pass=True, workspace_pass=True,
            miss_distance_pass=ok, reach_pass=True, mode=mode, estimated_target_eef_distance_m=.1, score_threshold=1.)
    monkeypatch.setitem(sys.modules, 'perception_regrasp_trigger', SimpleNamespace(evaluate_trigger=decision))
    monkeypatch.setitem(sys.modules, 'perception_regrasp', SimpleNamespace(localization_record=lambda x: x))
    monkeypatch.setitem(sys.modules, 'collect_feedback_controls', SimpleNamespace(observation_arrays=lambda obs, prefix: {'obs': np.array([obs['step']])}))
    monkeypatch.setitem(sys.modules, 'p5_repeat_feedback', SimpleNamespace(array_digest=lambda x: str(x.tolist())))
    env = SimpleNamespace(check_success=lambda: False, get_sim_state=lambda: np.zeros(2))
    seeds_used, repairs = [], []
    def sample(cfg, model, stats, obs, desc, seeds, resize, **kwargs):
        seeds_used.append(seeds)
        return [dict(actions=np.zeros((16, 7)))], {}
    def execute(env, obs, actions, tracker, *, absolute_t, max_t):
        assert len(actions) == 8 and absolute_t == 72 and max_t == 280
        return {'step': 80}, success_after_delay, 80, 8
    def repair(env, obs, tracker, localizer, description, **kwargs):
        guard = kwargs['localization_validator']({'initial': False}, np.zeros(3))
        assert guard['passed'] and guard['miss_distance_pass']
        repairs.append(kwargs['absolute_t'])
        return obs, False, kwargs['absolute_t'] + 3, 3, {'perception_regrasp_executed': False}
    c = SimpleNamespace(_sample_candidates=sample, _select_max_value=lambda *a, **kw: (0, {}), _execute_actions=execute)
    p = SimpleNamespace(_localize=lambda *args: {'initial': False})
    r = SimpleNamespace(_eef_position=lambda obs: np.zeros(3), _run_perception_regrasp=repair)
    result = intervene(c, p, r, env, {'step': 72}, None, None, {}, 'target', SimpleNamespace(flip_images=True),
                       arm, {'initial': True}, 72, {'rollout_seed': 100000}, None, None, None)
    _, _, _, diag, queries, next_q = result
    delayed = arm in DELAYED
    assert seeds_used == ([(105000, 105001, 105002, 105003)] if delayed else [])
    assert len(queries) == int(delayed)
    assert next_q == (6 if delayed else 5)
    expected = arm == 'physical_regrasp' or (arm in DELAYED[1:] and not success_after_delay)
    assert bool(repairs) == expected
    if delayed:
        assert diag['delay_end_audit']['t'] == 80
    assert diag['initial_t72_trigger_passed']


def test_gate_log_names_failures():
    d = SimpleNamespace(passed=False, finite_pass=True, confidence_pass=False, workspace_pass=True,
                        miss_distance_pass=False, reach_pass=True)
    assert gate_record(d)['failed_checks'] == ['confidence_pass', 'miss_distance_pass']


def test_cached_prefix_reapplies_seed_and_cudnn_mode_after_model_load():
    path = Path(__file__).resolve().parents[1] / 'scripts/collect_timing_eligibility.py'
    tree = ast.parse(path.read_text())
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        statements = node.body
        for index, statement in enumerate(statements):
            if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
                continue
            if ast.unparse(statement.value.func) != 'legacy.prefix':
                continue
            previous = statements[index - 1]
            assert isinstance(previous, ast.Expr) and isinstance(previous.value, ast.Call)
            assert ast.unparse(previous.value.func) == 'c.set_seed_everywhere'
            assert ast.unparse(previous.value.args[0]) == "job['rollout_seed']"
            found = True
    assert found

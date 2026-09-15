import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from p3_benchmark import ARMS, policy_source, run_episode, benchmark_jobs
from event_feedback import EventConfig, Evidence
from analyze_p3_benchmark import paired_effect


def simulation(arm, *, terminal=100, recover_steps=3, monitor=None, fail_gate=False):
    actual, calls, interventions = [], [], []
    def policy(obs, t, q, k):
        calls.append((t, q, k))
        a = np.zeros((k, 16, 7), dtype=np.float32)
        a[:, :, 0] = q + 1
        a[:, :, 6] = 1
        return a, np.arange(k, dtype=float), {}
    def step(a):
        actual.append(a.copy())
        return len(actual), len(actual) >= terminal
    def recover(obs, t, budget):
        interventions.append(t)
        physical = []
        for _ in range(0 if fail_gate else min(recover_steps, budget)):
            a = np.ones(7, dtype=np.float32) * -9
            obs, done = step(a)
            physical.append(a)
            if done:
                break
        return obs, len(actual) >= terminal, physical, {}
    monitor = monitor or (lambda obs, aa: Evidence(eef=(0., 0., 0.), gripper_command=1., commanded_motion=1.))
    result = run_episode(0, arm=arm, policy=policy, step=step, recover=recover, monitor=monitor)
    np.testing.assert_array_equal(result['actions'], actual)
    return result, calls, interventions


def test_historical_control_preserves_prefix_and_counts_physical_steps():
    base, _, _ = simulation('max_value_h16')
    fixed, queries, interventions = simulation('p3_at72')
    np.testing.assert_array_equal(base['actions'][:72], fixed['actions'][:72])
    assert interventions == [72]
    assert (75, 5, 4) in queries
    assert fixed['final_t'] == 100
    assert fixed['events'][0]['physical_steps'] == 3


def test_failed_gate_does_not_rewind_and_falls_back_to_h8():
    control, _, _ = simulation('h8_at72')
    blocked, _, _ = simulation('p3_at72', fail_gate=True)
    np.testing.assert_array_equal(control['actions'], blocked['actions'])
    assert blocked['events'][0]['physical_steps'] == 0


def test_early_success_is_retained_without_intervention():
    result, _, interventions = simulation('p3_at72', terminal=20)
    assert result['success'] and result['final_t'] == 20 and not interventions


def miss_monitor(delay=0):
    def monitor(obs, aa):
        close = obs >= delay
        near = obs <= delay + 4
        return Evidence(eef=(0., 0., .1), gripper_command=1. if close else -1., commanded_motion=1.,
            localization_valid=True, target_distance=.02 if near else .12,
            geometry_allowed=True, grasp_verdict='unknown' if near else 'miss')
    return monitor


def test_event_moves_with_observed_grasp_not_absolute_time():
    a, _, first = simulation('p3_event', monitor=miss_monitor())
    b, _, second = simulation('p3_event', monitor=miss_monitor(20))
    assert first == [12] and second == [32]
    assert len(a['events']) == len(b['events']) == 1


def test_shadow_does_not_change_actions_or_outcome():
    base, _, _ = simulation('max_value_h16')
    shadow, _, interventions = simulation('shadow', monitor=miss_monitor())
    np.testing.assert_array_equal(base['actions'], shadow['actions'])
    assert shadow['events'] and not shadow['events'][0]['executed'] and not interventions


def test_unknown_evidence_does_not_release_even_when_policy_is_uncertain():
    result, _, interventions = simulation('p3_event')
    assert not interventions and not result['events']


def test_terminal_during_recovery_and_global_budget():
    result, _, _ = simulation('p3_at72', terminal=74, recover_steps=25)
    assert result['success'] and result['final_t'] == 74
    result, _, _ = simulation('p3_at72', terminal=999, recover_steps=25)
    assert not result['success'] and result['final_t'] == 280


def test_namespace_policy_source(tmp_path):
    path = tmp_path / 'cosmos_policy/experiments/robot'
    path.mkdir(parents=True)
    (path / 'cosmos_utils.py').touch()
    module = SimpleNamespace(__file__=None, __path__=[str(tmp_path / 'cosmos_policy')])
    assert policy_source(module) == tmp_path / 'cosmos_policy'


def test_namespace_resolves_active_submodule_with_two_source_trees(tmp_path, monkeypatch):
    paths = [tmp_path / 'a/cosmos_policy', tmp_path / 'b/cosmos_policy']
    for root in paths:
        (root / 'experiments/robot').mkdir(parents=True)
        (root / 'experiments/robot/cosmos_utils.py').touch()
    module = SimpleNamespace(__name__='cosmos_policy', __file__=None, __path__=paths)
    monkeypatch.setattr('importlib.util.find_spec', lambda _: SimpleNamespace(
        origin=str(paths[1] / 'experiments/robot/cosmos_utils.py')))
    assert policy_source(module) == paths[1]


def test_namespace_source_through_frozen_runtime_symlink(tmp_path):
    real = tmp_path / 'original/cosmos_policy'
    (real / 'experiments/robot').mkdir(parents=True)
    (real / 'experiments/robot/cosmos_utils.py').touch()
    link = tmp_path / 'frozen'
    link.symlink_to(real.parent, target_is_directory=True)
    module = SimpleNamespace(__file__=None, __path__=[link / 'cosmos_policy'])
    assert policy_source(module) == (link / 'cosmos_policy').resolve()


def test_real_benchmark_manifest_support_and_exclusion():
    root = Path(__file__).resolve().parents[1]
    data = pd.read_csv(root / 'experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/episode_outcomes.csv')
    jobs = benchmark_jobs(data.to_dict('records'))
    assert len(jobs) == 199
    assert not any(j['level'] == 'y0.5' and j['task_id'] == 1 for j in jobs)


def test_macro_effect_does_not_confuse_pooled_success():
    rows = []
    for factor, n in [('Object', 2), ('Environment', 2), ('Position', 6)]:
        for i in range(n):
            for arm in ('a', 'b'):
                rows.append(dict(factor=factor, task_id=i // 2, init_state_id=0,
                    id=factor + str(i), arm=arm, success=arm == 'a' and factor == 'Object'))
    effect = paired_effect(pd.DataFrame(rows), 'a', 'b', repeats=100)
    assert effect['delta_pp'] == pytest.approx(100 / 3)
    assert effect['rescues'] == 2
    assert effect['cluster_sign_p'] > 0
    assert effect['clusters'] == 5

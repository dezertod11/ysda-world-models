from datetime import datetime, timezone
import importlib
from pathlib import Path

import pytest

from scripts.decoder_medoid_night import (EXTENSIONS, STAGE_ARMS, admissible_batch, deadline_times,
    extension_choice, group_estimate, ordered_jobs)
from scripts.decoder_token_medoid import make_jobs


def test_design_preserves_original_cases_and_adds_only_declared_controls():
    original = make_jobs()
    jobs = ordered_jobs(original)
    assert {j['id']: j for j in jobs if j['phase'] == 'screen'} == {
        j['id']: j for j in original if j['phase'] == 'screen'}
    assert len(jobs) == 3 + 180 + 180 + 120
    assert sum(len(STAGE_ARMS[j['phase']]) for j in jobs) == 1440
    h8 = [j for j in jobs if j['phase'] == 'horizon8']
    assert all(j['init_state_id'] == 0 for j in h8)
    assert {j['task_id'] for j in h8} == set(range(10))
    assert {j['seed_group'] for j in h8} == {0, 1, 2}
    early = [j for j in jobs if j['phase'] == 'screen'][:40]
    assert {j['task_id'] for j in early} == set(range(10))
    assert {j['seed_group'] for j in early} == {0, 1, 2}


def test_deadline_is_absolute_with_compute_and_report_reserves():
    times = deadline_times()
    assert datetime.fromtimestamp(times['deadline_epoch'], timezone.utc).isoformat() == '2026-09-12T07:00:00+00:00'
    assert times['compute_deadline_epoch'] == times['deadline_epoch'] - 1200
    assert times['kill_deadline_epoch'] == times['compute_deadline_epoch'] + 120
    assert times['report_deadline_epoch'] == times['deadline_epoch'] - 120


@pytest.mark.parametrize('stage', STAGE_ARMS)
def test_admission_never_starts_a_pair_that_does_not_fit(stage):
    duration = group_estimate(stage, [])
    assert admissible_batch(stage, duration + 179, 3) == 0
    assert admissible_batch(stage, duration + 180, 3) == 1
    assert admissible_batch(stage, 3 * duration + 180, 99) == 3
    assert admissible_batch(stage, -1, 3) == 0
    assert admissible_batch(stage, 100000, 0) == 0
    assert admissible_batch(stage, 100000, 1) == 1
    assert group_estimate(stage, [10000]) == 15000


def test_fixed_controls_use_original_candidate_indices_and_h8_routes():
    choices = dict(max_value=2, decoder_medoid=1)
    diagnostic = dict(prefix8_diagnostic_index=0)
    assert extension_choice('fixed_candidate_1', choices, diagnostic) == 1
    assert extension_choice('fixed_candidate_2', choices, diagnostic) == 2
    assert extension_choice('max_value_h8', choices, diagnostic) == 2
    assert extension_choice('decoder_full_h8', choices, diagnostic) == 1
    assert extension_choice('decoder_prefix_h8', choices, diagnostic) == 0
    assert {s['horizon'] for arm, s in EXTENSIONS.items() if arm.endswith('h8')} == {8}


def test_matched_controls_exclude_incomplete_groups_and_reject_mismatch():
    from scripts.analyze_decoder_medoid_night import FAMILIES, family_tables
    rows = []
    for task in range(3):
        for arm in FAMILIES['seed_controls']:
            rows.append(dict(id=f't{task}', task_id=task, arm=arm, factor='Object', seed_group=task,
                terminal_success=arm == 'decoder_medoid', initial_sha256='start', q0_pool_sha256='pool',
                env_seed=task, task_description='same', terminal_final_t=280, elapsed_seconds=1,
                candidate_calls_logical=54))
    rows.append(dict(rows[0], id='partial'))
    result, rates, comparisons, matched = family_tables(rows, 'seed_controls', ['t0', 't1', 't2', 'partial'])
    assert result['complete_groups'] == 3 and result['partial']
    assert len(matched) == 18
    gain = comparisons.iloc[0]
    assert gain.rescue == 3 and gain.harm == 0 and gain.macro_delta == 1
    assert gain.cluster_ci_low == gain.cluster_ci_high == 1
    rows[1]['initial_sha256'] = 'changed'
    with pytest.raises(ValueError, match='Paired contract'):
        family_tables(rows, 'seed_controls', ['t0', 't1', 't2'])


def test_watchdog_refuses_reused_pid_or_nonleader(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    runner = importlib.import_module('run_decoder_medoid_night')
    calls = []
    monkeypatch.setattr(runner, 'process_start', lambda _: 'new')
    monkeypatch.setattr(runner.os, 'kill', lambda *args: calls.append(args))
    assert not runner.signal_owned(dict(pid=123, start_ticks='old'), 15)
    assert calls == []
    monkeypatch.setattr(runner.os, 'getpgid', lambda _: 122)
    with pytest.raises(ValueError, match='leader'):
        runner.signal_owned(dict(pid=123, start_ticks='new'), 15, group=True)


def test_current_process_identity_can_be_read(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    runner = importlib.import_module('run_decoder_medoid_night')
    assert runner.process_start(runner.os.getpid()).isdigit()
    assert runner.process_start(999999999) is None


def test_expired_queue_does_not_wait_for_dependency_or_touch_a_gpu(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    runner = importlib.import_module('run_decoder_medoid_night')
    admission = importlib.import_module('run_libero_experiment_campaign')
    monkeypatch.setattr(runner, 'DIRECTORY', tmp_path)
    monkeypatch.setattr(runner, 'validate', lambda *_: None)
    monkeypatch.setattr(runner, 'job_done', lambda _: False)
    monkeypatch.setattr(runner.signal, 'signal', lambda *_: None)
    monkeypatch.setattr(admission, 'gpu_is_free', lambda _: pytest.fail('Expired queue must not inspect/admit GPU'))
    calls = []
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(
        pid=999999999, terminate=lambda: None, wait=lambda **_: 0))
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: calls.append(k['timeout']))
    now = runner.time.time()
    plan = dict(deadline_epoch=now + 1200, compute_deadline_epoch=now - 1,
        report_deadline_epoch=now + 1080, expected_rollouts={'screen': 720},
        jobs=[dict(phase='smoke', id='not-completed')])
    runner.run(plan, dict(dependency='absent-and-must-not-be-read'))
    result = json.loads((tmp_path / 'night_finished.json').read_text())
    assert result['status'] == 'partial' and result['active'] == {}
    assert result['reports_complete'] and len(calls) == 2
    assert all(0 < timeout <= 600 for timeout in calls)

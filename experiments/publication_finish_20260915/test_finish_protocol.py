"""The publication deadline cannot silently change scientific support."""
import importlib.util
import json
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('finish_run', HERE / 'run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def source():
    return json.loads((run.PARENT / 'config.json').read_text())


def test_main_and_timing_preserve_every_historical_job():
    original = source()
    new = run.make_config(original, 'test', {})
    assert new['jobs'] == [j for j in original['jobs'] if j['phase'] != 'smoke']
    assert sum(len(run.expected_arms(j)) for j in new['jobs']) == 1280
    assert sum(j['phase'] == 'main' for j in new['jobs']) == 128
    assert new['arms'] == original['arms']
    for key in ('runtime_hashes', 'artifacts', 'localizer', 'trigger', 'position_files', 'K'):
        assert new[key] == original[key]


def test_smoke_is_fresh_not_a_legacy_snapshot_replay():
    cfg = run.make_config(source(), 'smoke', {}, smoke=True)
    assert cfg['technical_only']
    assert len(cfg['jobs']) == 2
    assert {j['cohort'] for j in cfg['jobs']} == {'replication', 'transfer'}
    assert all(j['phase'] == 'main' for j in cfg['jobs'])
    assert sum(len(run.expected_arms(j)) for j in cfg['jobs']) == 8


@pytest.mark.parametrize('date', ['2026-09-14T00:00:00+03:00', '2099-01-01T00:00:00'])
def test_expired_or_ambiguous_deadline_rejected(date):
    with pytest.raises(ValueError):
        run.deadline_epoch(date)


def test_redirect_does_not_change_arbitrary_commands():
    assert run.redirect(['echo', 'hello']) == ['echo', 'hello']
    command = ['python', str(run.ROOT / 'scripts/collect_recovery_confirmation.py'), '--batch', 'x']
    assert run.redirect(command)[1] == str(HERE / 'collect.py')


def test_source_input_is_not_mutated():
    original = source()
    before = json.dumps(original, sort_keys=True)
    run.make_config(original, 'test', {}, smoke=True)
    assert json.dumps(original, sort_keys=True) == before

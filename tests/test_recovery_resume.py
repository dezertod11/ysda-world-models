import copy
import pytest

from scripts.resume_recovery_confirmation import resource_config


def test_resume_changes_only_worker_cap():
    config = dict(max_workers=8, jobs=[dict(rollout_seed=17)], phase_order=['main', 'timing'], K=4)
    old = copy.deepcopy(config)
    result = resource_config(config, dict(hours=9, max_workers=5))
    assert config == old
    assert result == dict(old, max_workers=5)


@pytest.mark.parametrize('hours,workers', [(0, 5), (float('nan'), 5), (9, 0), (9, 9)])
def test_invalid_resource_windows(hours, workers):
    with pytest.raises(ValueError):
        resource_config({}, dict(hours=hours, max_workers=workers))


def test_transient_write_retry_does_not_hide_persistent_failure(monkeypatch):
    import errno
    import scripts.resume_recovery_confirmation as module
    calls = []
    def write(path, value):
        calls.append(path)
        if len(calls) < 3:
            raise OSError(errno.ENOSPC, 'test NFS error')
    monkeypatch.setattr(module, 'atomic_json', write)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    module.retry_atomic_json('status', {})
    assert len(calls) == 3
    def always_full(*args):
        raise OSError(errno.ENOSPC, 'persistent')
    monkeypatch.setattr(module, 'atomic_json', always_full)
    with pytest.raises(OSError):
        module.retry_atomic_json('status', {})

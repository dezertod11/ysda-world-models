"""Guard descriptive means, missing groups and source-count transcription."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('joint_build',Path(__file__).with_name('build.py'))
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_gr00t_seed_effects_are_not_replaced_by_best_seed():
    rows=build.registry_rows(build.REGISTRY.read_text())
    base=build.triple(rows,'GR00T','SIMPLER','Baseline')
    method=build.triple(rows,'GR00T','SIMPLER','Decoder action-token medoid')
    assert [r['successes'] for r in base] == [49,51,50]
    assert [r['successes'] for r in method] == [66,46,51]
    assert 100*sum(r['sr'] for r in method)/3 == pytest.approx(56.59722222)


def test_incomplete_group_cannot_be_averaged():
    rows=build.registry_rows(build.REGISTRY.read_text())
    with pytest.raises(ValueError):
        build.triple([r for r in rows if r['sampling']!='[2,997,996]'],
                     'GR00T','SIMPLER','Decoder action-token medoid')


def test_invalid_binomial_count_fails():
    text='## Test\n\n| Метод | Success |\n|---|---|\n| Baseline | 11/10 |\n'
    with pytest.raises(ValueError):
        build.registry_rows(text)


def test_all_registry_rows_have_valid_counts():
    rows=build.registry_rows(build.REGISTRY.read_text())
    assert len(rows)>50
    assert any(r['section'].startswith('LIBERO-Plus') for r in rows)
    assert all(0<=r['successes']<=r['n'] for r in rows)


def test_empty_ablation_is_not_complete():
    result = dict(complete=True, runtime_snapshot_version=2, cases=128, branches=512,
                  parent_config_sha256=build.SCOPED_SHA, new_arm='retreat_requery', aggregate=[])
    assert not build.ready_ablation(result)


def test_counts_require_each_cohort_and_arm_exactly_once():
    rows = [dict(cohort=c, arm=a, successes=10, n=64, boundary=72)
            for c in ('replication', 'transfer') for a in ('h8', 'full')]
    assert len(build.checked_counts({'aggregate': rows}, ('h8', 'full'))) == 4
    with pytest.raises(AssertionError):
        build.checked_counts({'aggregate': rows[:-1] + [rows[0]]}, ('h8', 'full'))


def test_wrong_boundary_is_not_the_main_comparison():
    rows = [dict(cohort=c, arm='full', successes=10, n=64, boundary=56)
            for c in ('replication', 'transfer')]
    with pytest.raises(AssertionError):
        build.checked_counts({'aggregate': rows}, ('full',))

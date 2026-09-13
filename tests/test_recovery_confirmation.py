import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.recovery_confirmation import ARMS, PRIMARY, TIMES, make_jobs, seed_for, suffix_query, expected_arms, job_done
from scripts.analyze_recovery_confirmation import holm
from scripts.analyze_recovery_confirmation import analyze
from scripts.p5_repeat_feedback import atomic_json, digest
from scripts.p5_candidate_replication import atomic_npz

ROOT = Path(__file__).resolve().parents[1]


def calibration():
    return pd.read_csv(ROOT / 'experiments/frozen_models/perception_regrasp_20260904/calibration_manifest.csv')


def test_balanced_frozen_grid():
    jobs = make_jobs(calibration())
    main = pd.DataFrame([j for j in jobs if j['phase'] == 'main'])
    assert len(main) == 128
    assert main.groupby('cohort').size().to_dict() == {'replication': 64, 'transfer': 64}
    assert main.groupby('cell').size().eq(8).all()
    assert len(jobs) == 384
    assert sum(len(expected_arms(j)) for j in jobs) == 1280
    assert len(set(j['id'] for j in jobs)) == len(jobs)
    assert main.rollout_seed.nunique() == len(main)
    assert not main[main.cohort.eq('transfer')].calibration_cell_seen.any()


def test_no_calibration_overlap_and_reject_seen_transfer():
    frame = calibration()
    for job in make_jobs(frame):
        assert not ((frame.position_level == job['position_level']) &
            (frame.task_id == job['task_id']) & (frame.init_state_id == job['init_state_id'])).any()
    extra = pd.DataFrame([dict(position_level='x0.3', task_id=1, init_state_id=0)])
    with pytest.raises(ValueError, match='Transfer cell'):
        make_jobs(pd.concat([frame, extra], ignore_index=True))


def test_timing_uses_same_case_seed_and_registered_schedule():
    jobs = make_jobs(calibration())
    main = {j['case_id']: j for j in jobs if j['phase'] == 'main'}
    for job in jobs:
        assert job['rollout_seed'] == main[job['case_id']]['rollout_seed']
    assert [suffix_query(t) for t in TIMES] == [4, 5, 6]
    with pytest.raises(ValueError):
        suffix_query(73)
    assert seed_for('x0.3', 1, 25) == seed_for('x0.3', 1, 25)


def test_holm_family_and_order():
    np.testing.assert_allclose(holm([.04, .001, .03]), [.06, .003, .06])
    assert len(PRIMARY) == 4
    assert PRIMARY[1] == ('transfer', 'physical_regrasp', 'continue_h8')


def test_done_does_not_accept_missing_outputs(tmp_path):
    job = make_jobs(calibration())[0]
    assert not job_done(tmp_path, job)
    folder = tmp_path / job['phase'] / job['id']
    folder.mkdir(parents=True)
    (folder / 'completed.json').write_text(json.dumps({'arms': list(ARMS)}))
    with pytest.raises(ValueError, match='arm set'):
        job_done(tmp_path, job)


def test_sources_compile_and_no_online_oracle_arm():
    for name in ('recovery_confirmation', 'collect_recovery_confirmation',
                 'run_recovery_confirmation', 'analyze_recovery_confirmation'):
        ast.parse((ROOT / 'scripts' / (name + '.py')).read_text())
    assert not any('oracle' in arm for arm in ARMS)


def test_partial_analysis_withholds_inference(tmp_path):
    job = make_jobs(calibration())[0]
    atomic_json(tmp_path / 'config.json', dict(jobs=[job], sampling_scope='test', transfer_scope='test'))
    summary = analyze(tmp_path, 'main')
    assert summary['inference_withheld']
    assert summary['missing'] == [job['id']]
    assert 'effects' not in summary


def test_early_success_is_retained_for_all_arms(tmp_path):
    source = make_jobs(calibration())
    jobs = [next(j for j in source if j['phase'] == 'main' and j['cohort'] == cohort)
            for cohort in ('replication', 'transfer')]
    atomic_json(tmp_path / 'config.json', dict(jobs=jobs, sampling_scope='test', transfer_scope='test'))
    for job in jobs:
        folder = tmp_path / 'main' / job['id']
        actions = np.zeros((10, 7), dtype=np.float32)
        prefix = folder / 'prefix_72.npz'
        atomic_npz(prefix, prefix_actions=actions)
        for arm in expected_arms(job):
            path = folder / (arm + '.json')
            atomic_npz(path.with_suffix('.npz'), executed_actions=actions, final_state=np.zeros(2),
                       frame_t=np.arange(11))
            # Codec is exercised by the real GPU smoke; this fixture tests accounting/statistics.
            path.with_suffix('.mp4').write_bytes(b'test-video-placeholder')
            queries = []
            if arm == 'baseline_h16':
                queries = [dict(t=0, seeds=[job['rollout_seed'] + i for i in range(4)], index=1,
                    candidate_values=[0., 1., 0., 0.], metrics={}, requested_horizon=16,
                    candidate_actions=np.zeros((4, 16, 7)).tolist())]
            atomic_json(path, dict(job, job_id=job['id'], arm=arm, simulator_labels_online=False,
                terminal_success=True, terminal_final_t=10, video_start_t=0, video_frames=11,
                terminal_target_drop_candidate=False, queries=queries, intervention={},
                prefix_t=0 if arm == 'baseline_h16' else 10, prefix_sha256=digest(prefix),
                npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4'))))
        atomic_json(folder / 'completed.json', dict(arms=list(expected_arms(job))))
    summary = analyze(tmp_path, 'main')
    assert summary['complete'] and summary['branches'] == 8
    assert summary['audit']['full_prefix_checks'] == 6
    assert summary['audit']['no_intervention_parity'] == 4
    assert all(row['sr'] == 1. for row in summary['aggregate'])
    assert all(row['delta'] == 0. for row in summary['effects'])

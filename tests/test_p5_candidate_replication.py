import json

import numpy as np
import pandas as pd

from scripts.p5_candidate_replication import make_jobs, branch_schedule, local_frame_metrics, atomic_npz, signal_arrays
from scripts.analyze_p5_candidate_replication import analyze, split_candidate
from scripts.p5_repeat_feedback import atomic_json, digest
from scripts.run_p5_candidate_replication import done


def source_pools():
    return {'pools': [dict(id=name, task_id=task, init_state_id=init, selected=baseline,
        suite='libero_object_temp', environment={}, task_description='place the object',
        sidecar=f'{name}.npz', sidecar_sha256=name, case_id='p5_position_x0.2')
        for name, task, init, baseline in [('pool_13',2,7,4), ('pool_11',0,8,7)]]}


def test_fixed_replication_and_neighbor_design():
    jobs = make_jobs(source_pools())
    assert sum(j['expected_branches'] for j in jobs[:2]) == 50
    assert sum(j['expected_branches'] for j in jobs[2:]) == 640
    assert [(j['task_id'], j['init_state_id']) for j in jobs[2:]] == [(t,i) for t in (0,2) for i in (9,10,11,12)]
    assert jobs[0]['candidates'] == [4,3,5] and jobs[1]['candidates'] == [7,6]
    assert all('sidecar' not in j and 'baseline' not in j for j in jobs[2:])


def test_new_suffix_seeds_shared_across_candidates_disjoint_from_smoke():
    seeds_by_job = []
    for job in make_jobs(source_pools()):
        main = branch_schedule(job)
        smoke = branch_schedule(job, True)
        assert len(main) == job['expected_branches'] and len(set(main)) == len(main)
        seeds = {s for _,_,s in main}
        assert len(seeds) == 10 and seeds.isdisjoint(s for _,_,s in smoke)
        for r in range(10):
            assert len({s for rep,_,s in main if rep == r}) == 1
        seeds_by_job.append(seeds)
    assert len(set.union(*seeds_by_job)) == 100


def test_smoke_has_six_branches():
    ids = {'repeat_pool_13','repeat_pool_11','neighbor_t2_i12'}
    assert sum(len(branch_schedule(j,True)) for j in make_jobs(source_pools()) if j['id'] in ids) == 6


def test_local_metrics_exclude_later_fall():
    rows = [dict(t=49,robot_target_contact_count=2,target_lift_max=.01,goal_progress=0),
            dict(t=64,robot_target_contact_count=0,target_lift_max=.03,goal_progress=.5),
            dict(t=65,target_drop_candidate=1,target_lift_max=.5,goal_progress=1)]
    result = local_frame_metrics(rows)
    assert result['local_frames'] == 2 and result['local_contact_steps'] == 1
    assert not result['local_drop'] and result['local_target_lift_max'] == .03
    assert result['local_goal_progress_end'] == .5


def test_scalar_and_object_position_signals_roundtrip(tmp_path):
    records = [dict(t=49+i, contact=1, eef_position=np.array([i,2,3]),
                    object_positions=np.zeros((2,3))+i) for i in range(3)]
    arrays = signal_arrays(records)
    assert arrays['signal_keys'].tolist() == ['contact','t']
    assert arrays['signals'].shape == (3,2)
    assert arrays['signal_field__object_positions'].shape == (3,2,3)
    path = tmp_path/'signals.npz'
    atomic_npz(path, **arrays)
    with np.load(path,allow_pickle=False) as data:
        np.testing.assert_array_equal(data['signal_field__eef_position'][:,0], [0,1,2])


def test_neighbor_split_never_selects_on_test_labels():
    frame = pd.DataFrame([[1]*5+[0]*5, [0]*5+[1]*5])
    values = pd.Series([.2,.9])
    assert split_candidate(frame,values,list(range(5,10))) == 0
    assert split_candidate(frame,values,list(range(5))) == 1
    frame.iloc[:,5:] = [[1]*5,[0]*5]
    assert split_candidate(frame,values,list(range(5,10))) == 0


def test_split_ties_follow_frozen_value_not_index_only():
    frame = pd.DataFrame(np.ones((3,10)))
    assert split_candidate(frame,pd.Series([.1,.7,.7]),list(range(5))) == 1


def test_completed_marker_alone_is_not_enough(tmp_path):
    job = make_jobs(source_pools())[0]
    sub = tmp_path/'runs'/job['id']
    sub.mkdir(parents=True)
    (sub/'completed.json').write_text(json.dumps({'status':'completed'}))
    assert not done(tmp_path,job,False)
    for repeat,index,seed in branch_schedule(job):
        path = sub/f'r{repeat:02d}_c{index}.json'
        path.write_text(json.dumps(dict(suffix_seed=seed,terminal_available=True,video_path=None)))
        atomic_npz(path.with_suffix('.npz'), actions=np.zeros((16,7)))
    assert done(tmp_path,job,False)


def test_atomic_npz_roundtrip_without_pickle(tmp_path):
    path = tmp_path/'pool.npz'
    atomic_npz(path, actions=np.arange(112).reshape(16,7))
    with np.load(path,allow_pickle=False) as result:
        assert result['actions'].shape == (16,7)
    assert not path.with_suffix('.tmp').exists()


def test_primary_report_uses_new_paired_seeds_and_three_test_holm(tmp_path):
    jobs = make_jobs(source_pools())
    config = dict(jobs=jobs, primary_pairs=[['repeat_pool_13',3,4],['repeat_pool_13',5,4],['repeat_pool_11',6,7]],
                  neighbor_split=[list(range(5)),list(range(5,10))])
    atomic_json(tmp_path/'config.json', config)
    for job in jobs[:2]:
        pool = tmp_path/'pools'/f'{job["id"]}.npz'
        atomic_npz(pool, values=np.arange(8))
        sha = digest(pool)
        atomic_json(pool.with_suffix('.json'), dict(sha256=sha))
        sub = tmp_path/'runs'/job['id']
        atomic_json(sub/'completed.json', dict(status='completed'))
        atomic_json(sub/'replay_audit.json', dict(passed=True))
        for repeat,index,seed in branch_schedule(job):
            success = job['id']=='repeat_pool_11' or index!=job['baseline']
            atomic_json(sub/f'r{repeat:02d}_c{index}.json', dict(job_id=job['id'],kind=job['kind'],
                task_id=job['task_id'],init_state_id=job['init_state_id'],repeat=repeat,candidate_idx=index,
                selected=index==job['baseline'],suffix_seed=seed,terminal_available=True,terminal_success=success,
                pool_sha256=sha,candidate_value=float(index),local_contact_steps=1,local_target_lift_max=.1,
                local_drop=False,terminal_target_drop_candidate=False,local_wrong_object=False,
                local_goal_progress_end=0,video_path=None))
    analyze(tmp_path)
    effects = pd.read_csv(tmp_path/'analysis/fixed_pair_effects.csv')
    assert effects.pairs.tolist()==[10,10,10]
    assert effects.delta.tolist()==[1,1,0]
    assert effects.conditional_replication_pass.tolist()==[True,True,False]
    assert effects.holm_p.iloc[0]==effects.holm_p.iloc[1]
    summary = json.loads((tmp_path/'analysis/summary.json').read_text())
    assert summary['status']=='partial' and summary['branches']==50

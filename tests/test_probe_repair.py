from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.probe_repair import (ARMS, CELLS, make_jobs, motion_decision,
                                 project_eef, track_crop, validation_gate, validate_probe_pair,tracking_rgb)


@pytest.mark.parametrize('obj,eef,n,confidence,expected',[
    ([0,3],[0,4],8,True,'held'),
    ([0,.1],[0,4],8,True,'miss'),
    ([0,3],[0,4],3,True,'unknown'),
    ([0,3],[0,4],8,False,'unknown'),
    ([0,0],[0,1],8,True,'unknown'),
    ([0,-3],[0,4],8,True,'unknown'),
    ([np.nan,0],[0,4],8,True,'unknown'),
    ([0,12],[0,4],8,True,'unknown'),
])
def test_motion_abstains_without_observable_confident_motion(obj,eef,n,confidence,expected):
    assert motion_decision(obj,eef,n,confidence)==expected


def test_projection_uses_camera_extrinsics_and_rejects_behind_camera():
    k=np.array([[100,0,64],[0,100,64],[0,0,1]])
    camera=np.eye(4);camera[0,3]=2
    np.testing.assert_allclose(project_eef([2,0,2],k,camera),[64,64])
    np.testing.assert_allclose(project_eef([2.1,0,2],k,camera),[69,64])
    assert np.isnan(project_eef([0,0,-1],k,camera)).all()


def test_lk_flow_on_synthetic_translation():
    import cv2
    rng=np.random.default_rng(11)
    image=rng.integers(0,256,(128,128,3),dtype=np.uint8)
    moved=cv2.warpAffine(image,np.array([[1,0,0],[0,1,3]],dtype=float),(128,128))
    tracked=track_crop(image,moved,[64,64])
    assert tracked['tracks']>=4
    np.testing.assert_allclose(tracked['flow'],[0,3],atol=.2)
    assert motion_decision(tracked['flow'],[0,4],tracked['tracks'],True)=='held'
    assert track_crop(np.zeros_like(image),np.zeros_like(image),[64,64])['tracks']==0
    assert track_crop(image,moved,[-100,64])['tracks']==0


def test_native_opengl_tracking_is_converted_to_camera_projection_coordinates():
    import cv2
    raw=np.random.default_rng(33).integers(0,256,(128,128,3),dtype=np.uint8)
    after=cv2.warpAffine(raw,np.array([[1,0,0],[0,1,4]],dtype=float),(128,128))
    tracked=track_crop(tracking_rgb(raw,'opengl'),tracking_rgb(after,'opengl'),[64,64])
    np.testing.assert_allclose(tracked['flow'],[0,-4],atol=.2)
    assert motion_decision(tracked['flow'],[0,-4],tracked['tracks'],True)=='held'
    np.testing.assert_array_equal(tracking_rgb(raw,'opencv'),raw)
    with pytest.raises(ValueError):tracking_rgb(raw,'invalid')


def test_frozen_schedule_is_disjoint_from_calibration_and_holdout():
    root=Path(__file__).resolve().parents[1]
    calibration=pd.read_csv(root/'experiments/frozen_models/perception_regrasp_20260904/calibration_manifest.csv')
    jobs=make_jobs(calibration)
    assert len(jobs)==102 and len({j['id'] for j in jobs})==102
    assert len({j['rollout_seed'] for j in jobs})==102
    assert all(j['rollout_seed']+1000*40+3<2**31 for j in jobs)
    assert {p:sum(j['phase']==p for j in jobs)*len(ARMS) for p in ('smoke','screen','holdout')}==dict(smoke=24,screen=192,holdout=192)
    assert len({j['cell'] for j in jobs if not j['calibration_cell_seen']})==3
    assert not {j['init_state_id'] for j in jobs if j['phase']=='screen'} & {j['init_state_id'] for j in jobs if j['phase']=='holdout'}
    invalid=pd.concat([calibration,pd.DataFrame([dict(position_level=CELLS[0][0],task_id=CELLS[0][1],init_state_id=25)])])
    with pytest.raises(ValueError,match='overlap'):make_jobs(invalid)


def test_screen_gate_requires_strong_controls_not_just_continuation():
    good=dict(complete=True,pairs=48,verified_minus_full=.1,verified_minus_probe=.1,
              verified_minus_continue=.1,verified_drop_count=1,full_drop_count=2,changed_from_full=8)
    assert validation_gate(good)
    for field,value in [('complete',False),('pairs',47),('verified_minus_full',.04),
                        ('verified_minus_probe',0),('verified_drop_count',3),('changed_from_full',7)]:
        assert not validation_gate(dict(good,**{field:value}))


def test_replay_audit_rejects_changed_input_and_sim_state():
    first=dict(t=75,sim_state=[1.,2.],observation_hashes={'rgb':'frozen'})
    validate_probe_pair(first,first)
    with pytest.raises(ValueError):validate_probe_pair(first,dict(first,t=76))
    with pytest.raises(ValueError):validate_probe_pair(first,dict(first,observation_hashes={'rgb':'changed'}))
    with pytest.raises(AssertionError):validate_probe_pair(first,dict(first,sim_state=[2.,2.]))


@pytest.mark.parametrize('arm,verdict,expected_probe,expected_repair',[
    ('continue_h8','miss',0,0),('physical_regrasp','miss',0,3),
    ('probe_only','miss',3,0),('probe_verify_repair','held',3,0),
    ('probe_verify_repair','unknown',3,0),('probe_verify_repair','miss',3,3)])
def test_intervention_never_rolls_back_physical_fallback(monkeypatch,arm,verdict,expected_probe,expected_repair):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    import collect_probe_repair as collector
    import perception_regrasp_trigger as trigger
    camera=SimpleNamespace(get_camera_intrinsic_matrix=lambda *_:np.eye(3),get_camera_extrinsic_matrix=lambda *_:np.eye(4))
    monkeypatch.setitem(sys.modules,'robosuite.utils.camera_utils',camera)
    monkeypatch.setitem(sys.modules,'robosuite',SimpleNamespace(macros=SimpleNamespace(IMAGE_CONVENTION='opengl')))
    monkeypatch.setattr(trigger,'evaluate_trigger',lambda *a,**k:SimpleNamespace(passed=True))
    monkeypatch.setattr(collector,'motion_decision',lambda *a:verdict)
    monkeypatch.setattr(collector,'track_crop',lambda *a:dict(flow=[0,0],tracks=10))
    class Env:
        sim=None
        t=72
        def check_success(self):return False
        def get_sim_state(self):return np.array([self.t],dtype=float)
        def obs(self):return dict(agentview_image=np.full((8,8,3),self.t,dtype=np.uint8),eef=np.array([0,0,1+self.t/1000]))
    env=Env()
    def servo(env,obs,tracker,target_fn,**kwargs):
        assert kwargs['gripper']==1 and kwargs['steps']==3
        env.t+=3
        return env.obs(),False,env.t,3
    def repair(env,obs,*a,**k):
        assert int(obs['agentview_image'][0,0,0])==env.t
        env.t+=3
        return env.obs(),False,env.t,3,dict(perception_guard_pass=False)
    r=SimpleNamespace(_eef_position=lambda o:o['eef'],_servo_stage=servo,_run_perception_regrasp=repair)
    p=SimpleNamespace(_localize=lambda *a:{})
    obs,success,t,diag=collector.intervention(None,p,r,env,env.obs(),None,None,{},'pick',
        SimpleNamespace(flip_images=False),arm,dict(perception_pixel_row=4,perception_pixel_col=4),72)
    assert not success and t==72+expected_probe+expected_repair and env.t==t
    assert int(obs['agentview_image'][0,0,0])==t
    assert diag['probe_steps']==expected_probe and diag['regrasp_steps']==expected_repair
    if expected_probe:assert diag['probe_end_audit']['t']==75


@pytest.mark.parametrize('success_at', [None,31])
def test_prefix_time_accounting_and_frozen_resume(monkeypatch,tmp_path,success_at):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    import collect_probe_repair as collector
    class Env:
        t=0
        def obs(self):return dict(rgb=np.full((4,4,3),self.t,dtype=np.uint8))
        def reset(self):self.t=0
        def set_init_state(self,state):return self.obs()
        def step(self,a):
            self.t+=1
            return self.obs(),0,False,{}
    env=Env();samples_called=[]
    def sample(cfg,model,stats,obs,desc,seeds,resize,**kw):
        samples_called.append(seeds)
        assert int(obs['rgb'][0,0,0])==env.t
        return [dict(actions=np.full((16,7),.5)) for _ in range(4)],{}
    def execute(env,obs,actions,tracker,absolute_t,max_t):
        t=absolute_t;done=False
        for a in actions:
            if t>=max_t:break
            obs,_,_,_=env.step(a);t+=1
            done=t==success_at
            if done:break
        return obs,done,t,t-absolute_t
    c=SimpleNamespace(set_seed_everywhere=lambda *_:None,get_task_init_states_compat=lambda *_:[0]*40,
        get_libero_dummy_action=lambda *_:np.zeros(7),SafetySignalTracker=lambda *_:None,
        _sample_candidates=sample,_select_max_value=lambda *a,**kw:(0,{}),_execute_actions=execute,
        capture_libero_runtime_state=lambda env:dict(sim_state=np.array([env.t])),runtime_snapshot_arrays=lambda x:x,
        prepare_observation=lambda obs,*a:obs)
    cfg=SimpleNamespace(model_family='cosmos',flip_images=False)
    job=dict(task_id=2,init_state_id=25,rollout_seed=1234)
    data,meta=collector.prefix(c,None,env,None,SimpleNamespace(language='pick'),cfg,None,{},4,job,tmp_path)
    expected=72 if success_at is None else success_at
    assert meta['t']==expected and meta['success']==(success_at is not None)
    assert len(data['prefix_actions'])==expected and env.t==expected+10
    assert samples_called==[tuple(1234+q*1000+i for i in range(4)) for q in range(5 if success_at is None else 2)]
    saved,resumed=collector.prefix(c,None,env,None,None,cfg,None,{},4,job,tmp_path)
    assert meta==resumed and len(samples_called)==(5 if success_at is None else 2)
    np.testing.assert_array_equal(saved['prefix_actions'],data['prefix_actions'])

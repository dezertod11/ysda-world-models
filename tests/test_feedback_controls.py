import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.feedback_controls import (ARMS, check_predecessor, choose_tail,
                                       continuity_cost, make_jobs)
from scripts.analyze_feedback_controls import contrast


def test_schedule_has_separate_smoke_and_balanced_matched_screen():
    path = Path(__file__).resolve().parents[1]/'experiments/campaigns/p5_repeat_feedback_20260910/config.json'
    jobs = make_jobs(json.loads(path.read_text()))
    assert len(jobs)==27
    assert len({j['id'] for j in jobs})==27
    assert sum(j['phase']=='screen' for j in jobs)*len(ARMS)==120
    assert sum(j['phase']=='smoke' for j in jobs)*len(ARMS)==15
    assert len({j['query_seed'] for j in jobs})==27
    assert not {j['query_seed'] for j in jobs} & {j['suffix_seed'] for j in jobs}
    assert all(j['t'] in (48,64) for j in jobs)


@pytest.mark.parametrize('status,active,free,expected',[
    ('running',{},True,'waiting_predecessor'),
    ('completed',{},False,'waiting_predecessor'),
    ('completed',{'3':123},True,'waiting_predecessor'),
    ('completed',{},True,'ready'),
    ('budget_exhausted',{},True,'ready'),
    ('failed',{},True,'blocked_predecessor_failure'),
])
def test_queue_never_assumes_a_stale_status_means_free(status,active,free,expected):
    assert check_predecessor(dict(status=status,active=active),free)==expected


def test_continuity_uses_time_aligned_tail_and_gripper_sign():
    old = np.zeros((16,7)); old[8:,6]=.997
    candidates = np.repeat(old[None],4,axis=0)
    candidates[:,:8,6]=1.001
    np.testing.assert_array_equal(continuity_cost(candidates,old),np.zeros(4))
    candidates[1,:8,6]=-1
    assert continuity_cost(candidates,old)[1]==.25
    candidates[2,:,:]=-1
    assert np.all((continuity_cost(candidates,old)>=0)&(continuity_cost(candidates,old)<=1))


def test_choice_keeps_generated_actions_and_k1_is_first_sample():
    old=np.zeros((16,7))
    fresh=np.zeros((4,16,7)); fresh[1]=1; fresh[2]=.5
    stale=np.repeat(np.arange(112).reshape(1,16,7),4,axis=0)
    values=np.array([.49,.5,.1,.0])
    for arm, index in [('fresh_k1',0),('fresh_k4',1),('fresh_continuity_k4',0)]:
        tail,chosen,_=choose_tail(arm,old,fresh,values,stale,values)
        assert chosen==index
        np.testing.assert_array_equal(tail,fresh[index,:8])
    tail,index,_=choose_tail('stale_k4',old,fresh,values,stale,values)
    assert index==1
    np.testing.assert_array_equal(tail,stale[1,8:16])


def test_bad_inputs_stop_instead_of_becoming_fails():
    with pytest.raises(ValueError):
        continuity_cost(np.zeros((1,16,7)),np.zeros((16,7)))
    with pytest.raises(ValueError):
        continuity_cost(np.full((4,16,7),np.nan),np.zeros((16,7)))


def test_partial_predecessor_must_be_explicitly_finished():
    assert check_predecessor(dict(status='partial'),True)=='waiting_predecessor'
    assert check_predecessor(dict(status='partial',finished_at='2026-09-10'),True)=='ready'
    assert check_predecessor(dict(status='analysis_failed'),True)=='blocked_predecessor_failure'


def test_delivery_is_allowlisted_idempotent_and_refuses_overwrites(tmp_path):
    import base64
    import hashlib
    from scripts.run_feedback_controls import install_bundle, NEW, NAME
    names=['scripts/'+name for name in NEW]+[
        'experiments/campaigns/'+NAME+'/config.json',
        'experiments/FEEDBACK_CONTROLS_PROTOCOL_20260910.md',
        'experiments/RESEARCH_PRIORITIES_20260910.md']
    bundle={name:dict(base64=base64.b64encode(name.encode()).decode(),
                      sha256=hashlib.sha256(name.encode()).hexdigest()) for name in names}
    invalid=dict(bundle); invalid['.ssh/key']=invalid.pop(names[0])
    with pytest.raises(ValueError,match='manifest'):
        install_bundle(tmp_path,invalid)
    assert not list(tmp_path.iterdir())
    install_bundle(tmp_path,bundle)
    install_bundle(tmp_path,bundle)
    path=tmp_path/names[0]
    path.write_text('existing server changes')
    with pytest.raises(ValueError,match='overwrite'):
        install_bundle(tmp_path,bundle)
    assert path.read_text()=='existing server changes'


def test_delivery_checksum_failure_writes_nothing(tmp_path):
    import base64
    import hashlib
    from scripts.run_feedback_controls import install_bundle, NEW, NAME
    names=['scripts/'+name for name in NEW]+[
        'experiments/campaigns/'+NAME+'/config.json',
        'experiments/FEEDBACK_CONTROLS_PROTOCOL_20260910.md',
        'experiments/RESEARCH_PRIORITIES_20260910.md']
    bundle={name:dict(base64=base64.b64encode(name.encode()).decode(),
                      sha256=hashlib.sha256(name.encode()).hexdigest()) for name in names}
    bundle[names[-1]]['sha256']='invalid'
    with pytest.raises(ValueError,match='checksum'):
        install_bundle(tmp_path,bundle)
    assert not list(tmp_path.iterdir())


def test_pool_generation_uses_real_midpoint_and_shared_fresh_stale_seeds(monkeypatch,tmp_path):
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from scripts.collect_feedback_controls import prepare_pool
    class Env:
        t=0
        def obs(self):
            return {'pixels':np.full((4,4,3),self.t,dtype=np.uint8)}
        def reset(self):
            self.t=0
        def set_init_state(self,state):
            return self.obs()
        def step(self,action):
            self.t+=1
            return self.obs(),0,False,{}
        def get_sim_state(self):
            return np.array([self.t],dtype=float)
    env=Env(); calls=[]
    def sample(cfg,model,stats,obs,desc,seeds,resize,**kwargs):
        calls.append((env.t,int(obs['pixels'][0,0,0]),seeds))
        return [dict(actions=np.full((16,7),i/10),value_prediction=i/4) for i in range(4)],{}
    def restore(env,snapshot):
        env.t=int(snapshot['sim_state'][0]); return env.obs()
    def execute(env,obs,actions,tracker,absolute_t,max_t):
        t=absolute_t
        for action in actions:
            if t>=max_t: break
            obs,_,_,_=env.step(action); t+=1
        return obs,False,t,t-absolute_t
    c=SimpleNamespace(set_seed_everywhere=lambda *_:None,
        get_task_init_states_compat=lambda *_:[0]*20,get_libero_dummy_action=lambda *_:np.zeros(7),
        SafetySignalTracker=lambda *_:SimpleNamespace(records=[]),_sample_candidates=sample,
        _select_max_value=lambda *_a,**_k:(3,{}),_execute_actions=execute,
        capture_libero_runtime_state=lambda env:dict(sim_state=env.get_sim_state()),
        runtime_snapshot_arrays=lambda state:state,_copy_observation=lambda obs:{k:v.copy() for k,v in obs.items()},
        _restore_snapshot=restore,extract_future_proprio_from_sample=lambda *_:None,
        _to_numpy=np.asarray,prepare_observation=lambda obs,*_:obs)
    cfg=SimpleNamespace(model_family='cosmos',flip_images=False)
    job=dict(id='example',init_state_id=13,task_id=0,t=48,description='pick',prefix_seed=1000,query_seed=2000)
    data,meta=prepare_pool(c,env,None,None,cfg,None,{},4,job,tmp_path)
    assert len(calls)==6
    # Ten settling steps are outside the task counter: physical timestamps are shifted by ten.
    assert calls[-2]==(66,66,(2000,2001,2002,2003))
    assert calls[-1]==(66,58,(2000,2001,2002,2003))
    assert meta['mid_t']==56 and not meta['prefix_success']
    assert meta['start_input_hashes']!=meta['fresh_input_hashes']
    np.testing.assert_array_equal(data['old_actions'],data['initial_actions'][3])
    saved,old_meta=prepare_pool(c,env,None,None,cfg,None,{},4,job,tmp_path)
    assert len(calls)==6 and meta==old_meta
    np.testing.assert_array_equal(saved['fresh_actions'],data['fresh_actions'])


def test_contrast_clusters_repeats_and_handles_no_effect():
    rows=[dict(cell=cell,init_state_id=i,repeat=r,arm=a,terminal_success=(i%2==0))
          for cell in ('a','b','c') for i in range(4) for r in range(2) for a in ('x','y')]
    result=contrast(pd.DataFrame(rows),'x','y')
    assert result['pairs']==24 and result['clusters']==12
    assert result['delta']==0 and result['cluster_sign_p']==1


@pytest.mark.parametrize('start', [48,64])
@pytest.mark.parametrize('arm', ARMS)
@pytest.mark.parametrize('success_after', [6,12,32])
def test_branch_shared_prefix_real_inputs_and_k4_suffix(monkeypatch,start,arm,success_after):
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from scripts.collect_feedback_controls import run_branch, input_hashes
    class Env:
        t=start
        def obs(self):
            return {'pixels':np.full((4,4,3),self.t,dtype=np.uint8)}
        def step(self,action):
            self.t+=1
            return self.obs(),0,self.t>=start+success_after,{}
        def get_sim_state(self):
            return np.array([self.t],dtype=float)
    env=Env()
    def restore(env,snap):
        env.t=int(snap['sim_state'][0]); return env.obs()
    def execute(env,obs,actions,tracker,absolute_t,max_t):
        t=absolute_t; success=False
        for action in actions:
            if t>=max_t: break
            obs,_,success,_=env.step(action); t+=1
            if success: break
        return obs,success,t,t-absolute_t
    calls=[]
    def sample(cfg,model,stats,obs,description,seeds,resize,**kwargs):
        assert int(obs['pixels'][0,0,0])==env.t
        calls.append(seeds)
        return [dict(actions=np.zeros((16,7)))]*4,{}
    c=SimpleNamespace(_restore_snapshot=restore,SafetySignalTracker=lambda *_:SimpleNamespace(records=[]),
        _execute_actions=execute,_sample_candidates=sample,_select_max_value=lambda *a,**kw:(0,{}),
        prepare_observation=lambda obs,*_:obs,get_libero_image=lambda obs,**_:obs['pixels'],
        get_libero_wrist_image=lambda obs,**_:obs['pixels'],
        _terminal_outcome=lambda tracker,success,final_t,max_t,continuation_queries:dict(
            terminal_success=success,terminal_final_t=final_t,terminal_available=True))
    cfg=SimpleNamespace(flip_images=False)
    job=dict(id='test',cell='test',phase='smoke',task_id=0,init_state_id=0,repeat=0,t=start,
             suffix_seed=500,query_seed=100,description='pick object')
    old=np.zeros((16,7)); old[:8]=.25
    mid_t=start+min(8,success_after)
    data=dict(start_obs__pixels=env.obs()['pixels'],old_actions=old,mid_state=np.array([mid_t]),
              fresh_actions=np.ones((4,16,7))*.5,stale_actions=np.ones((4,16,7))*.75,
              fresh_values=np.arange(4)/4,stale_values=np.arange(4)/4)
    env.t=mid_t
    meta=dict(fresh_input_hashes=input_hashes(c,cfg,env.obs(),4),prefix_success=success_after<=8,mid_t=mid_t,sha256='frozen')
    row,arrays,frames=run_branch(c,env,cfg,None,{},4,job,data,meta,arm,dict(sim_state=np.array([start])))
    assert row['terminal_success'] and row['terminal_final_t']==start+success_after
    assert len(frames)==success_after+1 and arrays['executed_actions'].shape==(success_after,7)
    np.testing.assert_array_equal(arrays['executed_actions'][:8],old[:min(8,success_after)])
    assert calls==([tuple(500+10_000_000+(start+16)*1000+i for i in range(4))] if success_after>16 else [])
    assert row['logical_requery_candidates']==(0 if success_after<=8 or arm=='open16' else 1 if arm=='fresh_k1' else 4)

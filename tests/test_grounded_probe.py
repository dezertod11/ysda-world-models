import numpy as np
import pandas as pd
import pytest

from scripts.grounded_probe import component_mask,masked_motion,should_repair,make_jobs,ARMS,TRANSFER_CELLS
from scripts.analyze_grounded_probe import select_winner


def test_component_is_target_near_localizer_not_largest_blob():
    probability=np.zeros((96,96),np.float32)
    probability[5:30,5:30]=.99;probability[60:72,60:72]=.95
    mask=component_mask(probability,[66,66])
    assert mask.sum()==144 and mask[65,65] and not mask[15,15]
    assert not component_mask(probability,[95,5]).any()


def textured_pair(shift,gripper_shift=0):
    rng=np.random.default_rng(4)
    texture=rng.integers(0,255,(24,24,3),dtype=np.uint8)
    a=np.zeros((96,96,3),np.uint8);b=a.copy()
    a[44:68,22:46]=texture;b[44+shift:68+shift,22:46]=texture
    grip=rng.integers(0,255,(18,18,1),dtype=np.uint8).repeat(3,axis=2)
    a[44:62,49:67]=grip;b[44+gripper_shift:62+gripper_shift,49:67]=grip
    m0=np.zeros((96,96),bool);m1=m0.copy()
    m0[44:68,22:46]=True;m1[44+shift:68+shift,22:46]=True
    return a,b,m0,m1


def test_masked_tracks_reject_gripper_motion_for_static_target():
    args=textured_pair(0,-6)
    result=masked_motion(*args,[0,-6],True)
    assert result['tracks']>=4
    assert result['verification']=='miss'


def test_masked_tracks_confirm_coupled_motion():
    result=masked_motion(*textured_pair(-6,-6),[0,-6],True)
    assert result['verification']=='held',result
    assert result['centroid_flow']==[0,-6]


def test_masked_tracks_abstain_without_valid_mask_or_confidence():
    args=list(textured_pair(-6,-6))
    assert masked_motion(*args,[0,-6],False)['verification']=='unknown'
    args[3][:]=False
    assert masked_motion(*args,[0,-6],True)['verification']=='unknown'


@pytest.mark.parametrize('verdict',('held','miss','unknown'))
def test_repair_policies_have_explicit_unknown_fallback(verdict):
    assert should_repair('mask_verify_conservative',verdict)==(verdict!='held')
    assert should_repair('mask_verify_miss',verdict)==(verdict=='miss')
    assert should_repair('probe_always_regrasp',verdict)
    assert not should_repair('probe_only',verdict)


def test_frozen_manifest_splits_and_calibration_guard():
    calibration=pd.DataFrame([dict(position_level='x0.2',task_id=2,init_state_id=10)])
    jobs=make_jobs(calibration,[('x0.2',2)])
    splits={phase:{j['init_state_id'] for j in jobs if j['phase']==phase} for phase in ('smoke','screen','holdout')}
    assert splits['screen']==set(range(34,38))
    assert splits['holdout']==set(range(38,46))
    assert len({j['rollout_seed'] for j in jobs})==len(jobs)
    assert not splits['screen']&splits['holdout']
    calibration.loc[0,'init_state_id']=34
    with pytest.raises(ValueError,match='overlap'):make_jobs(calibration,[('x0.2',2)])


def test_transfer_is_disjoint_and_seed_values_are_valid():
    from scripts.probe_repair import CELLS
    calibration=pd.DataFrame([dict(position_level='x0.2',task_id=2,init_state_id=10)])
    jobs=make_jobs(calibration,CELLS,TRANSFER_CELLS)
    assert len([j for j in jobs if j['phase']=='transfer'])==48
    assert max(j['rollout_seed'] for j in jobs)<2**31
    assert len({j['rollout_seed'] for j in jobs})==len(jobs)
    assert set(CELLS).isdisjoint(TRANSFER_CELLS)


def outcomes():
    n=dict(continue_h8=24,physical_regrasp=30,probe_only=24,probe_verify_repair=27,
           probe_always_regrasp=29,mask_verify_miss=34,mask_verify_conservative=34,delayed_regrasp_h8=32)
    return pd.DataFrame([dict(job_id=i,arm=a,terminal_success=i<n[a],terminal_target_drop_candidate=False,
        query_count=10,initial_trigger_passed=True,repair_requested=False) for i in range(48) for a in ARMS])


def test_promotion_requires_strong_control_not_only_continue():
    data=outcomes()
    winner,decisions=select_winner(data)
    assert winner=='mask_verify_conservative'
    for arm in ('mask_verify_conservative','mask_verify_miss','delayed_regrasp_h8'):
        data.loc[data.arm.eq(arm),'terminal_success']=data.loc[data.arm.eq('physical_regrasp'),'terminal_success'].to_numpy()
    assert select_winner(data)[0] is None


def test_promotion_rejects_drop_harm_and_excess_queries():
    data=outcomes()
    data.loc[data.arm.eq('mask_verify_conservative'),'terminal_target_drop_candidate']=True
    data.loc[data.arm.eq('mask_verify_miss'),'query_count']=20
    assert select_winner(data)[0] is None

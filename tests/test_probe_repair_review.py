import numpy as np
import pandas as pd
import pytest

from scripts.review_probe_repair_results import target_probe_motion,exact_cluster_p,audit_noop_paths
from scripts.probe_repair import ARMS


def test_motion_uses_same_probe_endpoint_and_named_target():
    prefix=dict(obs__target_pos=np.array([0.,0.,0.]),obs__other_pos=np.array([1.,0.,0.]),
                obs__robot0_eef_pos=np.array([0.,0.,.1]))
    trace={'signal_field__object_positions':np.array([[[0.,0.,0.],[1,0,0]],[[0,0,.02],[1,0,0]]]),
           'signal_field__eef_position':np.array([[0,0,.11],[0,0,.12]])}
    target,eef=target_probe_motion(prefix,trace,'target',2)
    np.testing.assert_allclose(target,[0,0,.02]);np.testing.assert_allclose(eef,[0,0,.02])
    with pytest.raises(ValueError):target_probe_motion(prefix,trace,'target',3)
    reordered=dict(trace,signal_field__object_positions=trace['signal_field__object_positions'][:,::-1])
    with pytest.raises(ValueError,match='order'):target_probe_motion(prefix,reordered,'target',2)


def test_zero_displacement_does_not_mean_no_eef_motion():
    prefix=dict(obs__target_pos=np.zeros(3),obs__robot0_eef_pos=np.array([0.,0.,.1]))
    trace={'signal_field__object_positions':np.zeros((3,1,3)),
           'signal_field__eef_position':np.array([[0,0,.11],[0,0,.12],[0,0,.13]])}
    target,eef=target_probe_motion(prefix,trace,'target',3)
    assert np.linalg.norm(target)==0
    np.testing.assert_allclose(eef,[0,0,.03])


def test_exact_sign_flip_keeps_repeats_in_init_cluster():
    data=pd.DataFrame([dict(cell='a',init_state_id=i,repeat=r,arm=arm,terminal_success=arm=='x')
        for i in range(4) for r in (0,1) for arm in ('x','y')])
    assert exact_cluster_p(data,'x','y')==2/16
    data['terminal_success']=True
    assert exact_cluster_p(data,'x','y')==1


def test_noop_audit_rejects_divergent_actions(tmp_path):
    d=tmp_path/'screen'/'case';d.mkdir(parents=True)
    arrays=dict(executed_actions=np.zeros((3,7)),final_state=np.zeros(2),signals=np.zeros((3,2)))
    for arm in ARMS:np.savez(d/(arm+'.npz'),**arrays)
    data=pd.DataFrame([dict(arm='probe_verify_repair',job_id='case',initial_trigger_passed=False,verification='not_probed')])
    assert audit_noop_paths(tmp_path,data)==dict(no_trigger=1,probe_without_repair=0)
    data['initial_trigger_passed']=True;data['verification']='held'
    assert audit_noop_paths(tmp_path,data)==dict(no_trigger=0,probe_without_repair=1)
    arrays['executed_actions'][0,0]=1
    np.savez(d/'probe_verify_repair.npz',**arrays)
    with pytest.raises(ValueError,match='No-op parity'):
        audit_noop_paths(tmp_path,data)

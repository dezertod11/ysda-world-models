import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

spec=importlib.util.spec_from_file_location('retreat_contract',Path(__file__).with_name('contract.py'))
contract=importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)


@pytest.mark.parametrize('passed',[True,False])
def test_retreat_never_executes_grasp_and_uses_the_same_gate(monkeypatch,passed):
    calls=[]
    def primitive(*args,**kwargs):
        calls.append(kwargs)
        return 'fresh_obs',False,75,3,{'perception_regrasp_executed':False}
    oc=SimpleNamespace(intervene=lambda *args:'original',
        gate=lambda *args:SimpleNamespace(passed=passed),primitive=primitive)
    monkeypatch.setitem(sys.modules,'observation_contract',oc)
    contract.install_intervention()
    env=SimpleNamespace(check_success=lambda:False)
    r=SimpleNamespace(_eef_position=lambda obs:'eef')
    p=SimpleNamespace(_localize=lambda *args:{})
    args=(None,p,r,env,'obs',None,None,{},'task',None,'retreat_requery',{},72,{},None,None,None)
    result=oc.intervene(*args)
    assert len(calls)==int(passed)
    assert result[3]['repair_requested'] is False
    assert result[3]['refresh_requested']==passed
    if passed:
        assert calls[0]['observe_only'] is True
        assert calls[0]['gripper']==-1.
        assert result[2]==75
    else: assert result[2]==72


def test_existing_arms_are_unchanged(monkeypatch):
    oc=SimpleNamespace(intervene=lambda *args:'original')
    monkeypatch.setitem(sys.modules,'observation_contract',oc)
    contract.install_intervention()
    args=[None]*17; args[10]='physical_regrasp'
    assert oc.intervene(*args)=='original'

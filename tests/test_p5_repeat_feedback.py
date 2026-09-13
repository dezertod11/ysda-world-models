import numpy as np
import pandas as pd
import pytest

from scripts.p5_repeat_feedback import schedule, suffix_seed, replacement_window, check_saved_pool, array_digest
from scripts.analyze_p5_repeat_feedback import paired_effect
from scripts.p5_repeat_feedback import source_instruction, saved_policy_observation
from scripts.p5_repeat_feedback import atomic_json
from scripts.analyze_p5_repeat_feedback import analyze


def test_replay_preserves_original_policy_instruction():
    original='pick up the alphabet soup and place it in the basket'
    assert source_instruction(original,original)==original
    with pytest.raises(ValueError):
        source_instruction('Pick the alphabet soup and place it in the basket',original)


@pytest.mark.parametrize('flip', [False,True])
def test_archived_rgb_is_exact_and_does_not_mutate_env_observation(flip):
    saved=np.arange(36,dtype=np.uint8).reshape(3,4,3)
    obs={'agentview_image':np.zeros_like(saved),'robot0_eye_in_hand_image':np.zeros_like(saved),'state':12}
    proprio=np.arange(9,dtype=np.float32)
    result=saved_policy_observation(obs,{'current_agentview':saved,'current_wrist':saved,'current_proprio':proprio},flip)
    np.testing.assert_array_equal(np.flipud(result['agentview_image']) if flip else result['agentview_image'],saved)
    assert not obs['agentview_image'].any() and result['state']==12
    result['agentview_image'][:]=0
    assert saved.any()
    np.testing.assert_array_equal(np.concatenate([result['robot0_gripper_qpos'],result['robot0_eef_pos'],result['robot0_eef_quat']]),proprio)


def test_schedule_full_coverage_and_no_outcome_filter():
    for selected in range(8):
        rows=schedule(selected)
        assert len(rows)==30 and len(set(rows))==30
        for repeat in range(3):
            assert [i for r,i,m in rows if r==repeat and m=='open16']==list(range(8))
            assert {(i,m) for r,i,m in rows if r==repeat and m!='open16'}=={(selected,'fresh8'),(selected,'stale8')}
        assert len(schedule(selected,True))==3


def test_fresh_and_stale_windows_refer_to_same_absolute_interval():
    actions=np.arange(112).reshape(16,7)
    np.testing.assert_array_equal(replacement_window(actions,'fresh8'),actions[:8])
    np.testing.assert_array_equal(replacement_window(actions,'stale8'),actions[8:])
    with pytest.raises(ValueError):replacement_window(actions[:8],'fresh8')
    with pytest.raises(ValueError):replacement_window(actions,'open16')


def test_suffix_seed_is_shared_across_arms_and_candidates():
    assert [suffix_seed(81007000,r) for r in range(3)]==[81107000,81207000,81307000]
    actions=np.zeros((8,16,7),dtype=np.float32)
    assert array_digest(actions)==array_digest(actions.copy())
    changed=actions.copy();changed[0,0,0]=1
    assert array_digest(changed)!=array_digest(actions)


def test_saved_actions_and_max_value_are_checked():
    values=dict(candidate_actions=np.zeros((8,16,7)),candidate_values=np.arange(8),selected_max_value_idx=7)
    assert check_saved_pool(values,np.arange(8))==7
    with pytest.raises(ValueError):check_saved_pool(dict(values,selected_max_value_idx=0),np.arange(8))
    with pytest.raises(AssertionError):check_saved_pool(values,np.arange(8)+1)


def test_paired_analysis_clusters_repeats_queries_and_variants():
    records=[]
    for task in (0,1):
        for variant in ('x','y'):
            for repeat in range(3):
                for mode in ('fresh8','stale8'):
                    records.append(dict(pool_id=f'{task}_{variant}',task_id=task,init_state_id=7,
                        repeat=repeat,mode=mode,terminal_success=mode=='fresh8'))
    result=paired_effect(pd.DataFrame(records),'fresh8','stale8')
    assert result['pairs']==12 and result['task_init_clusters']==2
    assert result['delta_sr']==1 and result['rescues']==12
    assert result['cluster_signflip_p']==.5


def test_analysis_writes_partial_tables_plot_and_gallery(tmp_path):
    pools=[]
    originals=[]
    for task in (0,1):
        pool=dict(id=f'pool_{task:02d}',case_id='test_position',task_id=task,init_state_id=7,
            query_idx=0,t=0,sidecar_sha256=f'sha{task}')
        pools.append(pool)
        common=dict(pool_id=pool['id'],case_id=pool['case_id'],task_id=task,init_state_id=7,
            query_idx=0,repeat=0,candidate_idx=0,selected=True,prefix_integrity=True,
            terminal_available=True,source_sha256=pool['sidecar_sha256'],candidate_value=.7,
            terminal_target_drop_candidate=False,terminal_wrong_object_interaction_candidate=False,
            terminal_continuation_queries=4,video_path=None)
        for mode in ('open16','fresh8','stale8'):
            row=dict(common,mode=mode,terminal_success=task==0 or mode=='fresh8',additional_queries=int(mode!='open16'))
            atomic_json(tmp_path/'runs'/pool['id']/f'r0_c0_{mode}.json',row)
        atomic_json(tmp_path/'runs'/pool['id']/'replay_audit.json',{'passed':True})
        originals.append(dict(case_id=pool['case_id'],task_id=task,init_state_id=7,
            query_idx=0,candidate_idx=0,terminal_success=task==0))
    source=tmp_path/'original.parquet'
    pd.DataFrame(originals).to_parquet(source,index=False)
    atomic_json(tmp_path/'config.json',dict(pools=pools,expected_branches=60,source=str(source),primary_comparison='fresh8_minus_stale8'))
    analyze(tmp_path)
    assert (tmp_path/'analysis/selected_candidate_success.png').stat().st_size>1000
    assert (tmp_path/'videos.html').is_file()
    assert 'Status: partial; 6/60 branches.' in (tmp_path/'analysis/RESULTS.md').read_text()
    effects=pd.read_csv(tmp_path/'analysis/paired_effects.csv')
    assert len(effects)==2 and effects.pairs.eq(2).all()

#!/usr/bin/env python3
"""Shared-prefix physical diagnostic intervention, without simulator rollback."""
import argparse
import json
import time
from pathlib import Path
import signal

import numpy as np

from probe_repair import ARMS, PARAMS, track_crop, motion_decision, project_eef, validate_probe_pair, tracking_rgb
from p5_repeat_feedback import atomic_json,digest,array_digest
from p5_candidate_replication import atomic_npz,signal_arrays
from collect_feedback_controls import observation_arrays,restore_observation,input_hashes


def prefix(c,p,env,suite,task,cfg,model,stats,resize,job,directory):
    meta_path=directory/'prefix.json'; path=directory/'prefix.npz'
    if meta_path.exists():
        meta=json.loads(meta_path.read_text())
        if digest(path)!=meta['sha256']:
            raise ValueError('Prefix changed')
        with np.load(path,allow_pickle=False) as f:
            return {k:f[k].copy() for k in f.files},meta
    if path.exists():
        raise ValueError('Uncommitted prefix, manual review required')
    c.set_seed_everywhere(job['rollout_seed'])
    states=c.get_task_init_states_compat(suite,job['task_id'],task)
    if job['init_state_id']>=len(states):
        raise ValueError('Missing init asset')
    env.reset(); obs=env.set_init_state(states[job['init_state_id']])
    for _ in range(10):
        obs,_,done,_=env.step(c.get_libero_dummy_action(cfg.model_family))
        if done: raise ValueError('Success during settle')
    tracker=c.SafetySignalTracker(env,obs)
    actions=[]; t=0; success=False
    for q in range(5):
        samples,_=c._sample_candidates(cfg,model,stats,obs,str(task.language),
            tuple(job['rollout_seed']+q*1000+i for i in range(4)),resize,prediction_mode='parallel')
        index,_=c._select_max_value(samples,open_loop_steps=16)
        selected=np.asarray(samples[index]['actions'],dtype=np.float32)[:8 if q==4 else 16]
        before=t
        obs,success,t,_=c._execute_actions(env,obs,selected,tracker,absolute_t=t,max_t=72)
        actions.extend(selected[:t-before]); del samples
        if success: break
    data=dict(c.runtime_snapshot_arrays(c.capture_libero_runtime_state(env)),
        prefix_actions=np.asarray(actions,dtype=np.float32),**observation_arrays(obs,'obs__'))
    atomic_npz(path,**data)
    meta=dict(t=t,success=success,sha256=digest(path),input_hashes=input_hashes(c,cfg,obs,resize),
              frozen_before_branch_labels=True)
    atomic_json(meta_path,meta)
    return data,meta


def intervention(c,p,r,env,obs,tracker,localizer,artifact,description,cfg,arm,localization,t):
    from perception_regrasp_trigger import evaluate_trigger
    from perception_regrasp import raw_agentview_image,localization_record
    from robosuite.utils.camera_utils import get_camera_intrinsic_matrix,get_camera_extrinsic_matrix
    from robosuite import macros
    decision=evaluate_trigger(localization,r._eef_position(obs),artifact,mode='workspace_calibrated')
    diagnostic=dict(initial_trigger_passed=decision.passed,verification='not_probed',
                    probe_steps=0,regrasp_steps=0,repair_requested=False)
    success=bool(env.check_success())
    if success or arm=='continue_h8' or not decision.passed:
        return obs,success,t,diagnostic
    repair=arm=='physical_regrasp'
    if arm in ('probe_only','probe_verify_repair'):
        before=raw_agentview_image(obs).copy()
        intrinsic=get_camera_intrinsic_matrix(env.sim,'agentview',before.shape[0],before.shape[1])
        transform=get_camera_extrinsic_matrix(env.sim,'agentview')
        eef0=r._eef_position(obs).copy()
        target=eef0+np.array([0.,0.,PARAMS['probe_height_m']])
        obs,success,t,n=r._servo_stage(env,obs,tracker,lambda _:target,gripper=1.,steps=PARAMS['probe_steps'],
            tolerance_m=.005,absolute_t=t,max_t=280,writer=None,flip_images=cfg.flip_images)
        diagnostic['probe_steps']=n
        diagnostic['probe_end_audit']=dict(t=t,sim_state=np.asarray(env.get_sim_state()).tolist(),
            observation_hashes={k:array_digest(v) for k,v in observation_arrays(obs,'obs__').items()})
        if not success:
            after=raw_agentview_image(obs)
            flow=track_crop(tracking_rgb(before,macros.IMAGE_CONVENTION),tracking_rgb(after,macros.IMAGE_CONVENTION),
                            [localization['perception_pixel_col'],localization['perception_pixel_row']])
            eef_flow=project_eef(r._eef_position(obs),intrinsic,transform)-project_eef(eef0,intrinsic,transform)
            localized=p._localize(env,obs,localizer,description)
            post=evaluate_trigger(localized,r._eef_position(obs),artifact,mode='workspace_calibrated',require_miss=False)
            verdict=motion_decision(flow['flow'],eef_flow,flow['tracks'],post.passed)
            diagnostic.update(verification=verdict,object_flow=flow['flow'],tracks=flow['tracks'],
                              eef_flow=eef_flow.tolist(),post_probe_confidence=post.passed,
                              tracking_coordinates='opencv',observation_coordinates=macros.IMAGE_CONVENTION)
            repair=arm=='probe_verify_repair' and verdict=='miss'
    if repair and not success:
        diagnostic['repair_requested']=True
        def validator(loc,eef):
            return evaluate_trigger(localization_record(loc),eef,artifact,
                                    mode='workspace_calibrated',require_miss=False).__dict__
        obs,success,t,n,info=r._run_perception_regrasp(env,obs,tracker,localizer,description,
            absolute_t=t,max_t=280,writer=None,flip_images=cfg.flip_images,
            min_confidence=0.,localization_validator=validator)
        diagnostic.update(regrasp_steps=n,regrasp_diagnostics=info)
    # Every arm continues from the actual post-probe/retreat state, including failed guards.
    return obs,success,t,diagnostic


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--batch',type=Path,required=True)
    args=parser.parse_args(); batch=json.loads(args.batch.read_text()); directory=Path(batch['campaign'])
    config=json.loads((directory/'config.json').read_text())
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from perception_regrasp import FrozenPatchLocalizer
    from perception_regrasp_trigger import load_trigger_artifact
    from robosuite import macros
    import imageio.v2 as imageio
    if macros.IMAGE_CONVENTION!='opengl':raise ValueError('Frozen localizer requires native OpenGL input')
    cfg=c.default_policy_config('libero_object_temp',seed=0,num_open_loop_steps=16,
        num_denoising_steps_action=5,prediction_mode='parallel',num_denoising_steps_future_state=1,
        num_denoising_steps_value=1,num_future_state_samples=1,num_value_samples=1,value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg); c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path); stats=c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg); model,mc=c.get_model(cfg)
    if cfg.chunk_size!=mc.dataloader_train.dataset.chunk_size: raise ValueError('Horizon mismatch')
    localizer=FrozenPatchLocalizer(config['localizer'],device='cuda')
    artifact=load_trigger_artifact(config['trigger']); resize=c.get_image_resize_size(cfg.model_family)
    suite=c.benchmark.get_benchmark_dict()['libero_object_temp']()
    for job in batch['jobs']:
        if stopped or time.time()>batch['deadline_epoch']: return
        output=directory/job['phase']/job['id']; output.mkdir(parents=True,exist_ok=True)
        if (output/'completed.json').exists(): continue
        task=suite.get_task(job['task_id']); description=str(task.language)
        env,_=c.get_libero_env(task,cfg.model_family,resolution=cfg.env_img_res)
        try:
            data,meta=prefix(c,p,env,suite,task,cfg,model,stats,resize,job,output)
            snapshot=runtime_snapshot_from_arrays(data)
            c._restore_snapshot(env,snapshot)
            obs0=restore_observation(data,'obs__')
            np.testing.assert_allclose(env.get_sim_state(),snapshot['sim_state'],atol=1e-9,rtol=0)
            localization={} if meta['success'] else p._localize(env,obs0,localizer,description)
            atomic_json(output/'localization.json',localization)
            offset=job['repeat']%4
            for arm in ARMS[offset:]+ARMS[:offset]:
                if stopped or time.time()>batch['deadline_epoch']: return
                path=output/(arm+'.json')
                if path.exists():
                    previous=json.loads(path.read_text())
                    if previous['prefix_sha256']!=meta['sha256'] or any(
                        not path.with_suffix(ext).exists() or digest(path.with_suffix(ext))!=previous[key]
                        for ext,key in (('.npz','npz_sha256'),('.mp4','video_sha256'))):
                        raise ValueError('Incomplete or changed committed branch')
                    continue
                started=time.time(); c._restore_snapshot(env,snapshot)
                np.testing.assert_allclose(env.get_sim_state(),snapshot['sim_state'],atol=1e-9,rtol=0)
                obs=c._copy_observation(obs0); tracker=c.SafetySignalTracker(env,obs)
                def frame(o):
                    return np.concatenate([c.get_libero_image(o,flip_images=cfg.flip_images),c.get_libero_wrist_image(o,flip_images=cfg.flip_images)],axis=1)
                frames=[frame(obs)]; executed=[]; step=env.step
                def record(a):
                    result=step(a); executed.append(np.asarray(a,dtype=np.float32)); frames.append(frame(result[0])); return result
                env.step=record
                try:
                    if meta['success']:
                        success=True; t=meta['t']; diag=dict(verification='prefix_success',initial_trigger_passed=False,probe_steps=0,regrasp_steps=0)
                    else:
                        obs,success,t,diag=intervention(c,p,r,env,obs,tracker,localizer,artifact,description,cfg,arm,localization,meta['t'])
                    if 'probe_end_audit' in diag:
                        reference=output/'probe_replay_reference.json'
                        if reference.exists():
                            validate_probe_pair(json.loads(reference.read_text()),diag['probe_end_audit'])
                        else:
                            atomic_json(reference,diag['probe_end_audit'])
                    intervention_end=np.asarray(env.get_sim_state()).copy()
                    intervention_t=t
                    queries=[]; q=5
                    while not success and t<280:
                        seeds=tuple(job['rollout_seed']+q*1000+i for i in range(4))
                        samples,metrics=c._sample_candidates(cfg,model,stats,obs,description,seeds,resize,prediction_mode='parallel')
                        index,_=c._select_max_value(samples,open_loop_steps=8)
                        queries.append(dict(t=t,seeds=seeds,index=index,metrics=metrics))
                        obs,success,t,_=c._execute_actions(env,obs,samples[index]['actions'][:8],tracker,absolute_t=t,max_t=280)
                        q+=1; del samples
                finally:
                    env.step=step
                outcome=c._terminal_outcome(tracker,success=success,final_t=t,max_t=280,continuation_queries=len(queries))
                outcome.update(job_id=job['id'],arm=arm,cell=job['cell'],phase=job['phase'],
                    task_id=job['task_id'],init_state_id=job['init_state_id'],repeat=job['repeat'],
                    rollout_seed=job['rollout_seed'],calibration_cell_seen=job['calibration_cell_seen'],
                    prefix_sha256=meta['sha256'],prefix_t=meta['t'],prefix_success=meta['success'],
                    intervention_end_t=intervention_t,intervention=diag,queries=queries,
                    physical_fallback=True,diagnostic_only_simulator_labels=True,video_frames=len(frames),
                    elapsed_seconds=time.time()-started)
                atomic_npz(path.with_suffix('.npz'),executed_actions=np.asarray(executed,dtype=np.float32),
                    intervention_end_state=intervention_end,final_state=np.asarray(env.get_sim_state()).copy(),
                    frame_t=np.arange(meta['t'],t+1),**signal_arrays(tracker.records))
                tmp=output/(arm+'.tmp.mp4')
                with imageio.get_writer(tmp,fps=20,codec='libx264',pixelformat='yuv420p',macro_block_size=1) as writer:
                    for im in frames: writer.append_data(im)
                tmp.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')),video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path,outcome)
                print(f"[probe] {job['id']} {arm} success={success} verdict={diag['verification']}",flush=True)
            atomic_json(output/'completed.json',dict(status='completed',prefix_sha256=meta['sha256']))
        finally:
            env.close()


if __name__=='__main__': main()

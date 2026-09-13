#!/usr/bin/env python3
"""Frozen shared-prefix comparison of object verification and delayed recovery."""
import argparse
import json
from pathlib import Path
import signal
import time
import numpy as np

import collect_probe_repair as legacy
from grounded_probe import FrozenObjectMask,component_mask,masked_motion,should_repair
from probe_repair import validate_probe_pair,tracking_rgb
from p5_repeat_feedback import atomic_json,digest
from p5_candidate_replication import atomic_npz,signal_arrays
from collect_feedback_controls import restore_observation


def intervene(c,p,r,env,obs,tracker,localizer,masker,artifact,description,cfg,arm,loc,t,job,model,stats,resize):
    from perception_regrasp_trigger import evaluate_trigger
    from perception_regrasp import raw_agentview_image,localization_record
    from robosuite import macros
    extra={};queries=[];next_query=5
    original=evaluate_trigger(loc,r._eef_position(obs),artifact,mode='workspace_calibrated')
    if arm in ('continue_h8','physical_regrasp','probe_only','probe_verify_repair'):
        before=tracking_rgb(raw_agentview_image(obs),macros.IMAGE_CONVENTION)
        out,success,t,diag=legacy.intervention(c,p,r,env,obs,tracker,localizer,artifact,description,cfg,arm,loc,t)
        if arm=='probe_only' and diag['probe_steps']:
            extra.update(probe_before_rgb=before,probe_after_rgb=tracking_rgb(raw_agentview_image(out),macros.IMAGE_CONVENTION))
        return out,success,t,diag,extra,queries,next_query
    if arm=='delayed_regrasp_h8':
        if original.passed and not env.check_success():
            seeds=tuple(job['rollout_seed']+5000+i for i in range(4))
            samples,metrics=c._sample_candidates(cfg,model,stats,obs,description,seeds,resize,prediction_mode='parallel')
            index,_=c._select_max_value(samples,open_loop_steps=8)
            queries.append(dict(t=t,seeds=seeds,index=index,metrics=metrics,role='delay_before_regrasp'))
            obs,success,t,_=c._execute_actions(env,obs,samples[index]['actions'][:8],tracker,absolute_t=t,max_t=280)
            next_query=6;del samples
            loc=p._localize(env,obs,localizer,description) if not success else loc
        obs,success,t,diag=legacy.intervention(c,p,r,env,obs,tracker,localizer,artifact,description,cfg,'physical_regrasp',loc,t)
        diag.update(initial_t72_trigger_passed=original.passed,delay_policy_queries=len(queries))
        return obs,success,t,diag,extra,queries,next_query
    before=tracking_rgb(raw_agentview_image(obs),macros.IMAGE_CONVENTION)
    obs,success,t,diag=legacy.intervention(c,p,r,env,obs,tracker,localizer,artifact,description,cfg,'probe_only',loc,t)
    if not diag['probe_steps'] or success:return obs,success,t,diag,extra,queries,next_query
    after=tracking_rgb(raw_agentview_image(obs),macros.IMAGE_CONVENTION)
    extra.update(probe_before_rgb=before,probe_after_rgb=after)
    if arm.startswith('mask_verify'):
        probability0=masker.probability(before,description);probability1=masker.probability(after,description)
        after_loc=p._localize(env,obs,localizer,description)
        mask0=component_mask(probability0,[loc['perception_pixel_col'],loc['perception_pixel_row']])
        mask1=component_mask(probability1,[after_loc['perception_pixel_col'],after_loc['perception_pixel_row']])
        verdict=masked_motion(before,after,mask0,mask1,diag['eef_flow'],diag['post_probe_confidence'])
        diag.update(legacy_verification=diag['verification'],verification=verdict['verification'],masked=verdict)
        extra.update(target_probability_before=probability0,target_probability_after=probability1,
                     target_mask_before=mask0,target_mask_after=mask1)
    repair=should_repair(arm,diag['verification'])
    if repair:
        def validator(localization,eef):
            return evaluate_trigger(localization_record(localization),eef,artifact,
                mode='workspace_calibrated',require_miss=False).__dict__
        diag['repair_requested']=True
        obs,success,t,n,info=r._run_perception_regrasp(env,obs,tracker,localizer,description,
            absolute_t=t,max_t=280,writer=None,flip_images=cfg.flip_images,
            min_confidence=0.,localization_validator=validator)
        diag.update(regrasp_steps=n,regrasp_diagnostics=info)
    return obs,success,t,diag,extra,queries,next_query


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--batch',type=Path,required=True)
    args=parser.parse_args();batch=json.loads(args.batch.read_text());directory=Path(batch['campaign'])
    config=json.loads((directory/'config.json').read_text());arms=tuple(batch['arms'])
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from perception_regrasp import FrozenPatchLocalizer
    from perception_regrasp_trigger import load_trigger_artifact
    from robosuite import macros
    import imageio.v2 as imageio
    if macros.IMAGE_CONVENTION!='opengl':raise ValueError('Frozen localizer requires OpenGL')
    cfg=c.default_policy_config('libero_object_temp',seed=0,num_open_loop_steps=16,
        num_denoising_steps_action=5,prediction_mode='parallel',num_denoising_steps_future_state=1,
        num_denoising_steps_value=1,num_future_state_samples=1,num_value_samples=1,value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg);c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path);stats=c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg);model,mc=c.get_model(cfg)
    if cfg.chunk_size!=mc.dataloader_train.dataset.chunk_size:raise ValueError('Horizon mismatch')
    localizer=FrozenPatchLocalizer(config['localizer'],device='cuda')
    masker=FrozenObjectMask(directory/'mask_model') if any(a.startswith('mask_verify') for a in arms) else None
    artifact=load_trigger_artifact(config['trigger']);resize=c.get_image_resize_size(cfg.model_family)
    suite=c.benchmark.get_benchmark_dict()['libero_object_temp']()
    for job in batch['jobs']:
        if stopped or time.time()>batch['deadline_epoch']:return
        output=directory/job['phase']/job['id'];output.mkdir(parents=True,exist_ok=True)
        if (output/'completed.json').exists():continue
        task=suite.get_task(job['task_id']);description=str(task.language)
        env,_=c.get_libero_env(task,cfg.model_family,resolution=cfg.env_img_res)
        try:
            data,meta=legacy.prefix(c,p,env,suite,task,cfg,model,stats,resize,job,output)
            snapshot=runtime_snapshot_from_arrays(data);c._restore_snapshot(env,snapshot)
            obs0=restore_observation(data,'obs__')
            loc={} if meta['success'] else p._localize(env,obs0,localizer,description)
            atomic_json(output/'localization.json',loc)
            offset=(job['init_state_id']+job['repeat'])%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                if stopped or time.time()>batch['deadline_epoch']:return
                path=output/(arm+'.json')
                if path.exists():
                    prev=json.loads(path.read_text())
                    if prev['prefix_sha256']!=meta['sha256'] or any(digest(path.with_suffix(ext))!=prev[key]
                        for ext,key in (('.npz','npz_sha256'),('.mp4','video_sha256'))):raise ValueError('Changed branch')
                    continue
                started=time.time();c._restore_snapshot(env,snapshot)
                np.testing.assert_allclose(env.get_sim_state(),snapshot['sim_state'],atol=1e-9,rtol=0)
                obs=c._copy_observation(obs0);tracker=c.SafetySignalTracker(env,obs)
                def frame(o):
                    return np.concatenate([c.get_libero_image(o,flip_images=cfg.flip_images),c.get_libero_wrist_image(o,flip_images=cfg.flip_images)],axis=1)
                frames=[frame(obs)];executed=[];step=env.step
                def record(a):
                    result=step(a);executed.append(np.asarray(a,dtype=np.float32));frames.append(frame(result[0]));return result
                env.step=record
                try:
                    if meta['success']:
                        success=True;t=meta['t'];diag=dict(verification='prefix_success',initial_trigger_passed=False,probe_steps=0,regrasp_steps=0)
                        extra={};queries=[];q=5
                    else:
                        obs,success,t,diag,extra,queries,q=intervene(c,p,r,env,obs,tracker,localizer,masker,artifact,description,cfg,arm,loc,meta['t'],job,model,stats,resize)
                    if 'probe_end_audit' in diag:
                        reference=output/'probe_replay_reference.json'
                        if reference.exists():validate_probe_pair(json.loads(reference.read_text()),diag['probe_end_audit'])
                        else:atomic_json(reference,diag['probe_end_audit'])
                    intervention_end=np.asarray(env.get_sim_state()).copy();intervention_t=t
                    while not success and t<280:
                        seeds=tuple(job['rollout_seed']+q*1000+i for i in range(4))
                        samples,metrics=c._sample_candidates(cfg,model,stats,obs,description,seeds,resize,prediction_mode='parallel')
                        index,_=c._select_max_value(samples,open_loop_steps=8)
                        queries.append(dict(t=t,seeds=seeds,index=index,metrics=metrics))
                        obs,success,t,_=c._execute_actions(env,obs,samples[index]['actions'][:8],tracker,absolute_t=t,max_t=280)
                        q+=1;del samples
                finally:env.step=step
                outcome=c._terminal_outcome(tracker,success=success,final_t=t,max_t=280,continuation_queries=len(queries))
                outcome.update(job_id=job['id'],arm=arm,cell=job['cell'],phase=job['phase'],task_id=job['task_id'],
                    init_state_id=job['init_state_id'],repeat=job['repeat'],rollout_seed=job['rollout_seed'],
                    calibration_cell_seen=job['calibration_cell_seen'],prefix_sha256=meta['sha256'],prefix_t=meta['t'],
                    prefix_success=meta['success'],intervention_end_t=intervention_t,intervention=diag,queries=queries,
                    physical_fallback=True,diagnostic_only_simulator_labels=True,video_frames=len(frames),
                    elapsed_seconds=time.time()-started,mask_freeze_sha256=digest(directory/'mask_model/freeze.json'))
                atomic_npz(path.with_suffix('.npz'),executed_actions=np.asarray(executed,dtype=np.float32),
                    intervention_end_state=intervention_end,final_state=np.asarray(env.get_sim_state()).copy(),
                    frame_t=np.arange(meta['t'],t+1),**signal_arrays(tracker.records),**extra)
                temp=output/(arm+'.tmp.mp4')
                with imageio.get_writer(temp,fps=20,codec='libx264',pixelformat='yuv420p',macro_block_size=1) as writer:
                    for im in frames:writer.append_data(im)
                temp.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')),video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path,outcome)
                print(f'[grounded] {job["id"]} {arm} success={success} verdict={diag["verification"]}',flush=True)
            atomic_json(output/'completed.json',dict(status='completed',arms=arms,prefix_sha256=meta['sha256']))
        finally:env.close()


if __name__=='__main__':main()

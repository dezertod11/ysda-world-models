#!/usr/bin/env python3
"""Persistent, bounded batches of exact saved actions with matched suffix seeds."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import time

import numpy as np

from p5_repeat_feedback import (array_digest, atomic_json, digest, replacement_window,
                                saved_policy_observation, schedule, source_instruction, suffix_seed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def expired():
        return stopped or time.time() >= batch['deadline_epoch']

    import collect_counterfactual_feedback as c
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from libero_resident import CPUQueue, AsyncImageIO
    import imageio.v2 as imageio

    cpu = CPUQueue(capacity=2)
    videos = AsyncImageIO(imageio, cpu)
    state_path = args.batch.with_suffix('.status.json')
    state = dict(status='loading', pid=os.getpid(), completed_branches=0, gpu=os.environ['CUDA_VISIBLE_DEVICES'])
    def publish(**items):
        state.update(items, updated_at_epoch=time.time())
        atomic_json(state_path, state)
    publish()
    cfg = c.default_policy_config(batch['pools'][0]['suite'], seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(cfg.seed)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    stats = c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg)
    model, model_cfg = c.get_model(cfg)
    if cfg.chunk_size != model_cfg.dataloader_train.dataset.chunk_size:
        raise ValueError('Checkpoint chunk mismatch')
    resize = c.get_image_resize_size(cfg.model_family)
    publish(status='running', model_loads=1)
    try:
        for pool in batch['pools']:
            if expired(): break
            output = Path(batch['output'])/pool['id']
            output.mkdir(parents=True, exist_ok=True)
            if digest(pool['sidecar']) != pool['sidecar_sha256']:
                raise ValueError('Frozen saved actions changed')
            with np.load(pool['sidecar'], allow_pickle=False) as source:
                data = {k:source[k].copy() for k in source.files}
            snapshot = runtime_snapshot_from_arrays(data)
            cfg.task_suite_name = pool['suite']
            suite = c.benchmark.get_benchmark_dict()[pool['suite']]()
            task = suite.get_task(pool['task_id'])
            env, environment_description = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
            try:
                description = source_instruction(task.language, pool['task_description'])
                # Replay all eight saved prefixes before collecting any new labels for this pool.
                errors, render_diagnostics, proprio_diagnostics = [], [], []
                for index, actions in enumerate(data['candidate_actions']):
                    obs = c._restore_snapshot(env, snapshot)
                    np.testing.assert_allclose(np.asarray(env.get_sim_state()),snapshot['sim_state'],rtol=0,atol=1e-9)
                    for name, get in [('agentview',c.get_libero_image),('wrist',c.get_libero_wrist_image)]:
                        diff=get(obs,flip_images=cfg.flip_images).astype(float)-data['current_'+name].astype(float)
                        render_diagnostics.append(dict(candidate_idx=index,camera=name,
                            mse=float(np.mean(diff**2)),max_abs=float(np.abs(diff).max()),
                            changed_fraction=float(np.mean(diff!=0))))
                    proprio_diagnostics.append(float(np.abs(np.asarray(c.proprio_from_libero_obs(obs),dtype=np.float32)
                        -data['current_proprio']).max()))
                    tracker = c.SafetySignalTracker(env, obs)
                    c._execute_actions(env, obs, actions, tracker, absolute_t=pool['t'], max_t=pool['t']+16)
                    error = float(np.abs(np.asarray(env.get_sim_state())-data['candidate_endpoint_states'][index]).max())
                    errors.append(error)
                audit = dict(passed=max(errors)<=1e-9, endpoint_errors=errors,
                    render_diagnostics=render_diagnostics,proprio_diagnostics=proprio_diagnostics,
                    initial_policy_conditioning='archived_real_snapshot',
                    policy_task_description=description, environment_task_description=environment_description,
                    action_sha256=array_digest(data['candidate_actions']), sidecar_sha256=pool['sidecar_sha256'])
                atomic_json(output/'replay_audit.json', audit)
                if not audit['passed']:
                    raise ValueError(f"Saved prefix replay failed: {pool['id']} {max(errors)}")
                for repeat, index, mode in schedule(pool['selected'], batch['smoke']):
                    if expired(): break
                    key = f'r{repeat}_c{index}_{mode}'
                    path = output/(key+'.json')
                    if path.exists():
                        old = json.loads(path.read_text())
                        if old['source_sha256'] != pool['sidecar_sha256']:
                            raise ValueError('Resume source mismatch')
                        if old.get('video_path') and not Path(old['video_path']).is_file():
                            videos.recover(old['video_path'], fps=30, macro_block_size=1).result()
                        continue
                    publish(pool=pool['id'], branch=key)
                    started = time.time()
                    obs_start = saved_policy_observation(c._copy_observation(c._restore_snapshot(env, snapshot)),
                        data,cfg.flip_images)
                    tracker = c.SafetySignalTracker(env, obs_start)
                    actions = data['candidate_actions'][index]
                    seed = suffix_seed(pool['rollout_seed'], repeat)
                    record = repeat==0 and index==pool['selected']
                    frames, executed, mid_state = [], [], None
                    step = env.step
                    if record:
                        def frame(obs):
                            return np.concatenate([c.get_libero_image(obs, flip_images=cfg.flip_images),
                                c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)], axis=1)
                        frames.append(frame(obs_start))
                    def recorded_step(action):
                        nonlocal mid_state
                        result = step(action)
                        executed.append(np.asarray(action, dtype=np.float32))
                        if len(executed)==8:
                            mid_state = np.asarray(env.get_sim_state()).copy()
                        if record: frames.append(frame(result[0]))
                        return result
                    env.step = recorded_step
                    try:
                        first = 16 if mode=='open16' else 8
                        obs, success, t, _ = c._execute_actions(env, obs_start, actions[:first], tracker,
                            absolute_t=pool['t'], max_t=min(280,pool['t']+first))
                        additional_queries = 0
                        requery_actions = None
                        if mode!='open16' and not success and t<280:
                            query_obs = obs if mode=='fresh8' else obs_start
                            query_seed = seed+5_000_000+pool['query_idx']*1000
                            samples, _ = c._sample_candidates(cfg, model, stats, query_obs, description,
                                (query_seed,), resize, prediction_mode='parallel')
                            requery_actions = np.asarray(samples[0]['actions'], dtype=np.float32)
                            obs, success, t, _ = c._execute_actions(env, obs, replacement_window(requery_actions,mode),
                                tracker, absolute_t=t, max_t=min(280,pool['t']+16))
                            additional_queries = 1
                            del samples
                        endpoint = np.asarray(env.get_sim_state()).copy()
                        if mode=='open16':
                            np.testing.assert_allclose(endpoint, data['candidate_endpoint_states'][index],rtol=0,atol=1e-9)
                        obs, success, t, queries = c._continue_to_terminal(cfg, model, stats, env, obs,
                            tracker, description, (0,), rollout_seed=seed, absolute_t=t, max_t=280,
                            resize_size=resize, prediction_mode='parallel')
                        outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280,
                            continuation_queries=queries)
                    finally:
                        env.step = step
                    # Every arm shares exactly the same first eight executed actions and state.
                    prefix_path = output/f'c{index}_prefix.json'
                    prefix = dict(actions=array_digest(np.asarray(executed[:8],dtype=np.float32)),
                        state=mid_state.tolist() if mid_state is not None else None)
                    if prefix_path.exists():
                        previous=json.loads(prefix_path.read_text())
                        if previous['actions'] != prefix['actions']:
                            raise ValueError('First-eight-action integrity mismatch')
                        if (previous['state'] is None) != (prefix['state'] is None):
                            raise ValueError('First-eight-state availability mismatch')
                        if prefix['state'] is not None:
                            np.testing.assert_allclose(previous['state'],prefix['state'],rtol=0,atol=1e-9)
                    else:
                        atomic_json(prefix_path,prefix)
                    video_path = str(output/(key+'.mp4')) if record else None
                    if record:
                        with videos.get_writer(video_path,fps=30,macro_block_size=1) as writer:
                            for value in frames: writer.append_data(value)
                    arrays = dict(executed_actions=np.asarray(executed,dtype=np.float32), endpoint_state=endpoint,
                        final_state=np.asarray(env.get_sim_state()),
                        frame_t=np.arange(pool['t'],t+1) if record else np.empty(0,dtype=int))
                    if requery_actions is not None:arrays['requery_actions']=requery_actions
                    temporary=output/(key+'.tmp')
                    with temporary.open('wb') as f:np.savez_compressed(f,**arrays)
                    temporary.replace(output/(key+'.npz'))
                    outcome.update(pool_id=pool['id'],case_id=pool['case_id'],task_id=pool['task_id'],
                        init_state_id=pool['init_state_id'],query_idx=pool['query_idx'],snapshot_t=pool['t'],
                        factor=pool['factor'],repeat=repeat,candidate_idx=index,mode=mode,
                        candidate_value=float(data['candidate_values'][index]),selected=index==pool['selected'],
                        suffix_seed=seed,source_sha256=pool['sidecar_sha256'],saved_action_sha256=array_digest(actions),
                        policy_task_description=description,environment_task_description=environment_description,
                        additional_queries=additional_queries,elapsed_seconds=time.time()-started,
                        video_path=video_path,video_frames=len(frames),prefix_integrity=True)
                    atomic_json(path,outcome)
                    state['completed_branches']+=1
                    publish(last_completed=key)
                    print(f"[repeat] {pool['id']} {key} success={success} t={t}",flush=True)
            finally:
                env.close()
        cpu.close()
        publish(status='budget_exhausted' if expired() else 'completed')
    except BaseException as error:
        cpu.executor.shutdown(wait=True)
        publish(status='failed',error=repr(error))
        raise


if __name__=='__main__':
    main()

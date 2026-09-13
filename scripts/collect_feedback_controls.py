#!/usr/bin/env python3
"""Five exact-state branches, shared K4 pools, archived real inputs and videos."""
import argparse
import json
from pathlib import Path
import signal
import time

import numpy as np

from feedback_controls import ARMS, choose_tail, job_done
from p5_repeat_feedback import atomic_json, array_digest, digest, source_instruction
from p5_candidate_replication import atomic_npz, signal_arrays


def observation_arrays(obs, prefix):
    return {prefix+k: np.asarray(v).copy() for k, v in obs.items()
            if np.asarray(v).dtype.kind in 'bifu'}


def restore_observation(data, prefix):
    return {k[len(prefix):]: v.copy() for k, v in data.items() if k.startswith(prefix)}


def input_hashes(c, cfg, obs, resize):
    return {k: array_digest(v) for k, v in c.prepare_observation(obs, resize, cfg.flip_images).items()}


def pack_samples(c, samples, prefix):
    result = {prefix+'actions': np.stack([np.asarray(s['actions'], dtype=np.float32) for s in samples]),
              prefix+'values': np.asarray([s['value_prediction'] for s in samples], dtype=np.float32)}
    for name, values in [
        ('future_proprio', [c.extract_future_proprio_from_sample(dict(s)) for s in samples]),
        ('future_image', [s.get('future_image_predictions', {}).get('future_image') for s in samples]),
        ('future_wrist', [s.get('future_image_predictions', {}).get('future_wrist_image') for s in samples])]:
        if all(v is not None for v in values):
            result[prefix+name] = np.stack([c._to_numpy(v) for v in values])
    if not np.isfinite(result[prefix+'values']).all():
        raise ValueError('Missing/non-finite candidate values')
    return result


def prepare_pool(c, env, suite, task, cfg, model, stats, resize, job, output):
    path = output/'pool.npz'
    meta_path = output/'pool.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get('skipped'):
            return None, meta
        if digest(path) != meta['sha256']:
            raise ValueError('Frozen pool changed')
        with np.load(path, allow_pickle=False) as saved:
            return {k: saved[k].copy() for k in saved.files}, meta
    if path.exists():
        raise ValueError('Uncommitted pool: manual integrity review required')
    c.set_seed_everywhere(job['prefix_seed'])
    states = c.get_task_init_states_compat(suite, job['task_id'], task)
    if job['init_state_id'] >= len(states):
        raise ValueError('Missing init asset, not a policy failure')
    env.reset()
    obs = env.set_init_state(states[job['init_state_id']])
    for _ in range(10):
        obs, _, done, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
        if done:
            raise ValueError('Already successful during settle')
    tracker = c.SafetySignalTracker(env, obs)
    t, prefix_actions = 0, []
    while t < job['t']:
        samples, _ = c._sample_candidates(cfg, model, stats, obs, job['description'],
            tuple(job['prefix_seed']+t*100+i for i in range(4)), resize, prediction_mode='parallel')
        selected, _ = c._select_max_value(samples, open_loop_steps=16)
        actions = np.asarray(samples[selected]['actions'], dtype=np.float32)
        before = t
        obs, done, t, _ = c._execute_actions(env, obs, actions, tracker, absolute_t=t, max_t=job['t'])
        prefix_actions.extend(actions[:t-before])
        del samples
        if done:
            meta = dict(skipped=True, reason='success_before_decision', t=t)
            atomic_json(meta_path, meta)
            return None, meta
    snapshot = c.capture_libero_runtime_state(env)
    start_obs = c._copy_observation(obs)
    samples, _ = c._sample_candidates(cfg, model, stats, start_obs, job['description'],
        tuple(job['prefix_seed']+t*100+i for i in range(4)), resize, prediction_mode='parallel')
    selected, _ = c._select_max_value(samples, open_loop_steps=16)
    data = dict(c.runtime_snapshot_arrays(snapshot), **pack_samples(c, samples, 'initial_'))
    data.update(observation_arrays(start_obs, 'start_obs__'))
    data['prefix_actions'] = np.asarray(prefix_actions, dtype=np.float32)
    old = np.asarray(samples[selected]['actions'], dtype=np.float32)
    data['old_actions'] = old
    del samples
    # Use the same restore route as every measured branch, then audit real inputs at t+8.
    c._restore_snapshot(env, snapshot)
    tracker = c.SafetySignalTracker(env, start_obs)
    mid_obs, done, mid_t, _ = c._execute_actions(env, start_obs, old[:8], tracker,
        absolute_t=t, max_t=t+8)
    data['mid_state'] = np.asarray(env.get_sim_state()).copy()
    data.update(observation_arrays(mid_obs, 'mid_obs__'))
    meta = dict(selected=selected, prefix_success=done, mid_t=mid_t,
        start_input_hashes=input_hashes(c,cfg,start_obs,resize),
        fresh_input_hashes=input_hashes(c,cfg,mid_obs,resize), pools_frozen_before_terminal_labels=True)
    if not done:
        seeds = tuple(job['query_seed']+i for i in range(4))
        for label, query_obs in [('fresh_', mid_obs), ('stale_', start_obs)]:
            samples, metrics = c._sample_candidates(cfg, model, stats, query_obs,
                job['description'], seeds, resize, prediction_mode='parallel')
            data.update(pack_samples(c, samples, label))
            meta[label+'metrics'] = metrics
            del samples
    atomic_npz(path, **data)
    meta['sha256'] = digest(path)
    atomic_json(meta_path, meta)
    return data, meta


def run_branch(c, env, cfg, model, stats, resize, job, data, meta, arm, snapshot):
    obs = restore_observation(data, 'start_obs__')
    c._restore_snapshot(env, snapshot)
    np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
    tracker = c.SafetySignalTracker(env, obs)
    def frame(value):
        return np.concatenate([c.get_libero_image(value, flip_images=cfg.flip_images),
                               c.get_libero_wrist_image(value, flip_images=cfg.flip_images)], axis=1)
    frames, executed, query_inputs = [frame(obs)], [], []
    step = env.step
    def record(action):
        result = step(action)
        executed.append(np.asarray(action, dtype=np.float32))
        frames.append(frame(result[0]))
        return result
    env.step = record
    try:
        obs, success, t, _ = c._execute_actions(env, obs, data['old_actions'][:8], tracker,
            absolute_t=job['t'], max_t=job['t']+8)
        if success != meta['prefix_success'] or t != meta['mid_t']:
            raise ValueError('First-eight termination differs from frozen pool')
        np.testing.assert_allclose(env.get_sim_state(), data['mid_state'], atol=1e-9, rtol=0)
        actual_hashes = input_hashes(c,cfg,obs,resize)
        if actual_hashes != meta['fresh_input_hashes']:
            raise ValueError('Fresh observation replay mismatch; do not collect labels')
        index, cost, tail = -1, np.zeros(4), np.empty((0,7))
        if not success:
            tail, index, cost = choose_tail(arm, data['old_actions'], data['fresh_actions'],
                data['fresh_values'], data['stale_actions'], data['stale_values'])
            obs, success, t, _ = c._execute_actions(env, obs, tail, tracker,
                absolute_t=t, max_t=job['t']+16)
        endpoint = np.asarray(env.get_sim_state()).copy()
        # Match suffix RNG by absolute simulation time, independently of requery RNG.
        queries = 0
        while not success and t < 280:
            query_inputs.append(dict(t=t, hashes=input_hashes(c,cfg,obs,resize)))
            seeds = tuple(job['suffix_seed']+10_000_000+t*1000+i for i in range(4))
            samples, _ = c._sample_candidates(cfg, model, stats, obs, job['description'],
                seeds, resize, prediction_mode='parallel')
            selected, _ = c._select_max_value(samples, open_loop_steps=16)
            obs, success, t, _ = c._execute_actions(env, obs, samples[selected]['actions'],
                tracker, absolute_t=t, max_t=280)
            queries += 1
            del samples
        row = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280, continuation_queries=queries)
    finally:
        env.step = step
    actual_k = 0 if meta['prefix_success'] or arm == 'open16' else (1 if arm == 'fresh_k1' else 4)
    row.update(job_id=job['id'], cell=job['cell'], phase=job['phase'], arm=arm,
        task_id=job['task_id'], init_state_id=job['init_state_id'], repeat=job['repeat'],
        snapshot_t=job['t'], suffix_seed=job['suffix_seed'], query_seed=job['query_seed'],
        pool_sha256=meta['sha256'], prefix_integrity=True, fresh_input_hashes=actual_hashes,
        candidate_index=index, continuity_costs=cost.tolist(), logical_requery_candidates=actual_k,
        logical_suffix_candidates=4*queries, suffix_inputs=query_inputs,
        safety_metrics_are_project_proxies=True, video_frames=len(frames))
    arrays = dict(executed_actions=np.asarray(executed), replacement_actions=tail,
        endpoint_state=endpoint, final_state=np.asarray(env.get_sim_state()).copy(),
        frame_t=np.arange(job['t'], t+1), **signal_arrays(tracker.records))
    return row, arrays, frames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    directory = Path(batch['campaign'])
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    import collect_counterfactual_feedback as c
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    import imageio.v2 as imageio
    cfg = c.default_policy_config(batch['jobs'][0]['suite'], seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    stats = c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg)
    model, model_config = c.get_model(cfg)
    if cfg.chunk_size != model_config.dataloader_train.dataset.chunk_size:
        raise ValueError('Model horizon mismatch')
    resize = c.get_image_resize_size(cfg.model_family)
    for job in batch['jobs']:
        if stopped or time.time() >= batch['deadline_epoch']:
            return
        if job_done(directory, job):
            continue
        output = directory/job['phase']/job['id']
        output.mkdir(parents=True, exist_ok=True)
        cfg.task_suite_name = job['suite']
        suite = c.benchmark.get_benchmark_dict()[job['suite']]()
        task = suite.get_task(job['task_id'])
        source_instruction(task.language, job['description'])
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            data, meta = prepare_pool(c, env, suite, task, cfg, model, stats, resize, job, output)
            if meta.get('skipped'):
                atomic_json(output/'completed.json', dict(status='skipped', **meta))
                continue
            snapshot = runtime_snapshot_from_arrays(data)
            offset = job['repeat'] % len(ARMS)
            for arm in ARMS[offset:]+ARMS[:offset]:
                if stopped or time.time() >= batch['deadline_epoch']:
                    return
                path = output/(arm+'.json')
                if path.exists():
                    row = json.loads(path.read_text())
                    if row['pool_sha256'] != meta['sha256'] or row['suffix_seed'] != job['suffix_seed']:
                        raise ValueError('Resume mismatch')
                    if not path.with_suffix('.npz').exists() or not path.with_suffix('.mp4').exists():
                        raise ValueError('Committed branch missing artifacts')
                    continue
                started = time.time()
                row, arrays, frames = run_branch(c,env,cfg,model,stats,resize,job,data,meta,arm,snapshot)
                atomic_npz(path.with_suffix('.npz'), **arrays)
                temporary_video = output/(arm+'.tmp.mp4')
                with imageio.get_writer(temporary_video, fps=30, macro_block_size=1, codec='libx264',
                                        pixelformat='yuv420p') as writer:
                    for frame in frames:
                        writer.append_data(frame)
                temporary_video.replace(path.with_suffix('.mp4'))
                row['elapsed_seconds'] = time.time()-started
                atomic_json(path, row)
                print(f"[feedback] {job['id']} {arm} success={row['terminal_success']}", flush=True)
            atomic_json(output/'completed.json', dict(status='completed', pool_sha256=meta['sha256']))
        finally:
            env.close()


if __name__ == '__main__':
    main()

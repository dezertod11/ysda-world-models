#!/usr/bin/env python3
"""Resident model, frozen pools, per-frame local and terminal consequences."""
import argparse
import json
import os
from pathlib import Path
import signal
import time

import numpy as np

from p5_repeat_feedback import array_digest, atomic_json, digest, saved_policy_observation, source_instruction
from p5_candidate_replication import atomic_npz, branch_schedule, local_frame_metrics, signal_arrays


def make_pool(c, env, task, suite, cfg, model, stats, resize, job, directory):
    path = directory / 'pools' / f'{job["id"]}.npz'
    meta_path = path.with_suffix('.json')
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get('skipped'):
            return None, meta
        if digest(path) != meta['sha256']:
            raise ValueError('Frozen pool changed')
        return path, meta
    if path.exists():
        raise ValueError('Uncommitted pool: inspect before regenerating')
    if job['kind'] == 'replication':
        assert digest(job['sidecar']) == job['sidecar_sha256']
        with np.load(job['sidecar'], allow_pickle=False) as saved:
            data = {k: saved[k].copy() for k in saved.files}
        atomic_npz(path, **data)
        meta = dict(selected=job['baseline'], generated=False, source_sha256=job['sidecar_sha256'])
    else:
        states = c.get_task_init_states_compat(suite, job['task_id'], task)
        if job['init_state_id'] >= len(states):
            raise ValueError('Required init asset missing; never count as policy failure')
        env.reset()
        obs = env.set_init_state(states[job['init_state_id']])
        for _ in range(10):
            obs, _, done, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
            if done:
                raise ValueError('Task already successful during settle')
        tracker = c.SafetySignalTracker(env, obs)
        prefix_actions = []
        t = 0
        for query in range(3):
            seeds = tuple(job['prefix_seed'] + query*1000 + i for i in range(8))
            samples, _ = c._sample_candidates(cfg, model, stats, obs, job['description'], seeds, resize, prediction_mode='parallel')
            selected, _ = c._select_max_value(samples, open_loop_steps=16)
            actions = np.asarray(samples[selected]['actions'], dtype=np.float32)
            before = t
            obs, success, t, _ = c._execute_actions(env, obs, actions, tracker, absolute_t=t, max_t=48)
            prefix_actions.extend(actions[:t-before])
            del samples
            if success:
                meta = dict(skipped=True, reason='success_before_q3', t=t, generated=True)
                atomic_json(meta_path, meta)
                return None, meta
        assert t == 48
        obs = c._copy_observation(obs)
        snapshot = c.capture_libero_runtime_state(env)
        seeds = tuple(job['prefix_seed'] + 3000 + i for i in range(8))
        samples, metrics = c._sample_candidates(cfg, model, stats, obs, job['description'], seeds, resize, prediction_mode='parallel')
        selected, _ = c._select_max_value(samples, open_loop_steps=16)
        states_end, observations_end = [], []
        for sample in samples:
            restored = c._restore_snapshot(env, snapshot)
            check = c.SafetySignalTracker(env, restored)
            end, _, _, _ = c._execute_actions(env, restored, sample['actions'], check, absolute_t=48, max_t=64)
            states_end.append(np.asarray(env.get_sim_state()).copy())
            observations_end.append(c._copy_observation(end))
        payload = c._sidecar_payload(cfg, snapshot, obs, samples, seeds, selected, states_end,
            observations_end, [], [], None, None, None, None, {}, 16)
        payload['prefix_actions'] = np.asarray(prefix_actions, dtype=np.float32)
        atomic_npz(path, **payload)
        meta = dict(selected=selected, generated=True, query_metrics=metrics,
                    candidate_features=[c._candidate_features(sample, i) for i, sample in enumerate(samples)])
        del samples
    meta.update(job_id=job['id'], sha256=digest(path), frozen_before_terminal_labels=True)
    atomic_json(meta_path, meta)
    return path, meta


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
    state = dict(pid=os.getpid(), gpu=os.environ['CUDA_VISIBLE_DEVICES'], status='loading', completed_branches=0)
    def publish(**values):
        state.update(values, updated_at=time.time())
        atomic_json(args.batch.with_suffix('.status.json'), state)
    def expired():
        return stopped or time.time() >= batch['deadline_epoch']
    publish()
    import collect_counterfactual_feedback as c
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    import imageio.v2 as imageio
    from libero_resident import CPUQueue, AsyncImageIO
    cpu = CPUQueue(capacity=2)
    videos = AsyncImageIO(imageio, cpu)
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
    assert cfg.chunk_size == model_config.dataloader_train.dataset.chunk_size
    resize = c.get_image_resize_size(cfg.model_family)
    publish(status='running', model_loads=1)
    try:
        for job in batch['jobs']:
            if expired():
                break
            cfg.task_suite_name = job['suite']
            suite = c.benchmark.get_benchmark_dict()[job['suite']]()
            task = suite.get_task(job['task_id'])
            description = source_instruction(task.language, job['description'])
            env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
            output = directory / ('smoke' if batch['smoke'] else 'runs') / job['id']
            output.mkdir(parents=True, exist_ok=True)
            try:
                pool_path, meta = make_pool(c, env, task, suite, cfg, model, stats, resize, job, directory)
                if meta.get('skipped'):
                    atomic_json(output / 'completed.json', dict(status='skipped', **meta))
                    continue
                with np.load(pool_path, allow_pickle=False) as source:
                    data = {k: source[k].copy() for k in source.files}
                snapshot = runtime_snapshot_from_arrays(data)
                errors = []
                for index in job['candidates']:
                    obs = c._restore_snapshot(env, snapshot)
                    np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                    tracker = c.SafetySignalTracker(env, obs)
                    c._execute_actions(env, obs, data['candidate_actions'][index], tracker, absolute_t=48, max_t=64)
                    errors.append(float(np.abs(np.asarray(env.get_sim_state()) - data['candidate_endpoint_states'][index]).max()))
                atomic_json(output / 'replay_audit.json', dict(passed=max(errors) <= 1e-9, endpoint_errors=errors, pool_sha256=meta['sha256']))
                if max(errors) > 1e-9:
                    raise ValueError(f'Replay failed: {job["id"]}')
                for repeat, index, seed in branch_schedule(job, batch['smoke']):
                    if expired():
                        break
                    key = f'r{repeat:02d}_c{index}'
                    path = output / f'{key}.json'
                    if path.exists():
                        previous = json.loads(path.read_text())
                        assert previous['pool_sha256'] == meta['sha256'] and previous['suffix_seed'] == seed
                        if previous['video_path'] and not (directory / previous['video_path']).exists():
                            videos.recover(str(directory / previous['video_path']), fps=30, macro_block_size=1).result()
                        continue
                    publish(job=job['id'], branch=key)
                    started = time.time()
                    obs = saved_policy_observation(c._copy_observation(c._restore_snapshot(env, snapshot)), data, cfg.flip_images)
                    tracker = c.SafetySignalTracker(env, obs)
                    actions = data['candidate_actions'][index]
                    record = batch['smoke'] or repeat in (0, 9)
                    def frame(value):
                        return np.concatenate([c.get_libero_image(value, flip_images=cfg.flip_images),
                            c.get_libero_wrist_image(value, flip_images=cfg.flip_images)], axis=1)
                    frames = [frame(obs)] if record else []
                    executed = []
                    step = env.step
                    def recorded_step(action):
                        result = step(action)
                        executed.append(np.asarray(action, dtype=np.float32))
                        if record:
                            frames.append(frame(result[0]))
                        return result
                    env.step = recorded_step
                    try:
                        obs_end, success, t, count = c._execute_actions(env, obs, actions, tracker, absolute_t=48, max_t=64)
                        endpoint = np.asarray(env.get_sim_state()).copy()
                        np.testing.assert_allclose(endpoint, data['candidate_endpoint_states'][index], atol=1e-9, rtol=0)
                        local = c._local_outcome(tracker, 0, obs, obs_end, success=success, executed_steps=count)
                        local.update(local_frame_metrics(tracker.records))
                        endpoint_proprio = np.asarray(c.proprio_from_libero_obs(obs_end), dtype=np.float32)
                        _, success, t, queries = c._continue_to_terminal(cfg, model, stats, env, obs_end, tracker,
                            description, (0,), rollout_seed=seed, absolute_t=t, max_t=280, resize_size=resize, prediction_mode='parallel')
                        terminal = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280, continuation_queries=queries)
                    finally:
                        env.step = step
                    video_path = output / f'{key}.mp4' if record else None
                    if record:
                        with videos.get_writer(str(video_path), fps=30, macro_block_size=1) as writer:
                            for value in frames:
                                writer.append_data(value)
                    atomic_npz(output / f'{key}.npz', executed_actions=np.asarray(executed), endpoint_state=endpoint,
                        endpoint_proprio=endpoint_proprio, final_state=np.asarray(env.get_sim_state()),
                        frame_t=np.arange(48, t+1), signal_object_names=np.asarray(tracker.movable_objects),
                        signal_target_names=np.asarray(tracker.target_objects),
                        signal_goal_predicates_json=np.asarray(json.dumps(tracker.goal_states)),
                        **signal_arrays(tracker.records))
                    atomic_json(path, dict(job_id=job['id'], kind=job['kind'], task_id=job['task_id'],
                        init_state_id=job['init_state_id'], query_idx=3, snapshot_t=48, repeat=repeat,
                        candidate_idx=index, selected=index == meta['selected'], candidate_value=float(data['candidate_values'][index]),
                        suffix_seed=seed, pool_sha256=meta['sha256'], action_sha256=array_digest(actions),
                        elapsed_seconds=time.time()-started, video_path=str(video_path.relative_to(directory)) if record else None,
                        video_frames=len(frames), **local, **terminal))
                    state['completed_branches'] += 1
                    publish(last_completed=key)
                    print(f'[replication] {job["id"]} {key} success={success} local_contact={local["local_contact_steps"]}', flush=True)
                if all((output / f'r{r:02d}_c{i}.json').exists() for r, i, _ in branch_schedule(job, batch['smoke'])):
                    atomic_json(output / 'completed.json', dict(status='completed'))
            finally:
                env.close()
        cpu.close()
        publish(status='budget_exhausted' if expired() else 'completed')
    except BaseException as error:
        cpu.executor.shutdown(wait=True)
        publish(status='failed', error=repr(error))
        raise


if __name__ == '__main__':
    main()

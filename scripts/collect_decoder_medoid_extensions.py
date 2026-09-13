#!/usr/bin/env python3
"""Fixed-seed and H8 controls, replaying the frozen study's initial snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

import numpy as np

from decoder_medoid_night import EXTENSIONS, STAGE_ARMS, extension_choice
from collect_decoder_token_medoid import committed, pack, sample_pool, selectors, unpack
from collect_feedback_controls import input_hashes, restore_observation
from p5_candidate_replication import atomic_npz, signal_arrays
from p5_repeat_feedback import atomic_json, digest


def run(batch):
    directory = Path(batch['campaign'])
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
    import imageio.v2 as imageio
    import torch
    jobs = batch['jobs']
    first = jobs[0]
    if any((j['suite'], j['level'], j['phase']) != (first['suite'], first['level'], first['phase']) for j in jobs):
        raise ValueError('One suite/level/phase per worker')
    cfg = c.default_policy_config(first['suite'], seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    stats = c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg)
    model, mc = c.get_model(cfg)
    if cfg.chunk_size != 16 or mc.dataloader_train.dataset.chunk_size != 16:
        raise ValueError('Generated horizon must remain 16')
    resize = c.get_image_resize_size(cfg.model_family)
    suite = c.benchmark.get_benchmark_dict()[first['suite']]()
    for job in jobs:
        if expired():
            return
        parent = directory / job['parent_phase'] / job['id']
        if not (parent / 'completed.json').exists():
            raise ValueError('Base paired group must be complete first')
        for arm in STAGE_ARMS['screen']:
            if not committed(parent / (arm + '.json')):
                raise ValueError('Incomplete base rollout')
            row = json.loads((parent / (arm + '.json')).read_text())
            for key in ('id', 'candidate_seeds', 'env_seed', 'init_state_id', 'suite', 'task_id', 'level'):
                if row[key] != job[key]:
                    raise ValueError('Parent identity mismatch: ' + key)
        start_meta = json.loads((parent / 'start.json').read_text())
        pool_meta = json.loads((parent / 'q0_pool.json').read_text())
        for name, metadata in (('start', start_meta), ('q0_pool', pool_meta)):
            if digest(parent / (name + '.npz')) != metadata['sha256']:
                raise ValueError('Changed parent artifact: ' + name)
        with np.load(parent / 'start.npz', allow_pickle=False) as f:
            start = {k: f[k].copy() for k in f.files}
        with np.load(parent / 'q0_pool.npz', allow_pickle=False) as f:
            pool_data = {k: f[k].copy() for k in f.files}
        snapshot = runtime_snapshot_from_arrays(start)
        obs0 = restore_observation(start, 'obs__')
        q0_samples = unpack(pool_data, pool_meta['latent_indices'])
        output = directory / job['phase'] / job['id']
        output.mkdir(parents=True, exist_ok=True)
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        if description != start_meta['task_description'] or start_meta['env_seed'] != job['env_seed']:
            raise ValueError('Parent instruction/environment seed changed')
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        arms = STAGE_ARMS[job['phase']]
        offset = (job['task_id'] + job['init_state_id'] + job['seed_group']) % len(arms)
        try:
            for arm in arms[offset:] + arms[:offset]:
                path = output / (arm + '.json')
                if committed(path):
                    previous = json.loads(path.read_text())
                    if previous['initial_sha256'] != start_meta['sha256'] or previous['q0_pool_sha256'] != pool_meta['sha256']:
                        raise ValueError('Resume parent changed')
                    continue
                if expired():
                    return
                spec = EXTENSIONS[arm]
                fixed = spec.get('fixed_index')
                seeds = [job['candidate_seeds'][fixed]] if fixed is not None else job['candidate_seeds']
                c.set_seed_everywhere(job['env_seed'])
                c._restore_snapshot(env, snapshot)
                np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                obs = c._copy_observation(obs0)
                if input_hashes(c, cfg, obs, resize) != start_meta['input_hashes']:
                    raise ValueError('Initial model input differs')
                tracker = c.SafetySignalTracker(env, obs)
                started = time.monotonic()
                torch.cuda.reset_peak_memory_stats()
                def frame(o):
                    return np.concatenate([c.get_libero_image(o, flip_images=cfg.flip_images),
                        c.get_libero_wrist_image(o, flip_images=cfg.flip_images)], axis=1)
                frames, actions, queries, arrays = [frame(obs)], [], [], {}
                step = env.step
                def record(a):
                    result = step(a)
                    actions.append(np.asarray(a, dtype=np.float32))
                    frames.append(frame(result[0]))
                    return result
                env.step = record
                t, q, success, calls = 0, 0, False, 0
                try:
                    while not success and t < 280:
                        if expired():
                            return
                        query_started = time.monotonic()
                        if q == 0:
                            samples = [q0_samples[fixed]] if fixed is not None else q0_samples
                            original_index = extension_choice(arm, pool_meta['choices'], pool_meta['diagnostic'])
                            index = 0 if fixed is not None else original_index
                            metrics = {'num_samples': 1.} if fixed is not None else pool_meta['metrics']
                            diagnostic, audits = pool_meta['diagnostic'], pool_meta['capture']
                            sampling_seconds = pool_meta['elapsed_seconds']
                        else:
                            samples, metrics, features, incidence, audits = sample_pool(c, cfg, model, stats,
                                obs, description, seeds, resize, capture=fixed is None)
                            if fixed is not None:
                                index, original_index, diagnostic = 0, fixed, {'fixed_candidate_index': fixed}
                            else:
                                choices, diagnostic = selectors(samples, features, incidence)
                                index = original_index = extension_choice(arm, choices, diagnostic)
                            sampling_seconds = time.monotonic() - query_started
                            del features
                        calls += len(samples)
                        before = c._copy_observation(obs)
                        for key, value in pack(c, samples).items():
                            if key != 'generated_latent':
                                arrays[f'q{q:03d}_{key}'] = value
                        arrays[f'q{q:03d}_future_proprio'] = np.stack([c.extract_future_proprio_from_sample(s) for s in samples])
                        arrays[f'q{q:03d}_input_external'] = c.get_libero_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_input_wrist'] = c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)
                        t0 = t
                        obs, success, t, executed = c._execute_actions(env, obs, samples[index]['actions'][:spec['horizon']],
                            tracker, absolute_t=t, max_t=280)
                        # H8 observations are not ground truth for a generated H16 future.
                        errors = c.prediction_error_metrics_for_query(samples[index], before, obs, stats,
                            cfg.flip_images, success) if executed == 16 else {}
                        errors.pop('prediction_error_value_abs_chunk_success', None)
                        arrays[f'q{q:03d}_actual_external'] = c.get_libero_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_actual_wrist'] = c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_actual_proprio'] = c.proprio_from_libero_obs(obs)
                        queries.append(dict(query=q, t=t0, t_after=t, executed=executed, index=index,
                            original_candidate_index=original_index, candidate_seeds=seeds, selected_seed=seeds[index],
                            metrics=metrics, selectors=diagnostic, capture=audits,
                            input_hashes=input_hashes(c, cfg, before, resize), sampling_seconds=sampling_seconds,
                            prediction_error_horizon_aligned=executed == 16, prediction_errors=errors, common_q0_pool=q == 0))
                        print(f'[decoder-control-query] {job["id"]} {arm} q={q} t={t} selected={original_index}', flush=True)
                        q += 1
                        del samples
                finally:
                    env.step = step
                outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280, continuation_queries=q)
                outcome.update(job, arm=arm, task_description=description, queries=queries,
                    initial_sha256=start_meta['sha256'], q0_pool_sha256=pool_meta['sha256'],
                    video_frames=len(frames), elapsed_seconds=time.monotonic() - started,
                    candidate_calls_logical=calls, cuda_peak_bytes=torch.cuda.max_memory_allocated(),
                    selector_uses_simulator_labels=False, prediction_mode='parallel',
                    generated_horizon=16, executed_horizon=spec['horizon'])
                atomic_npz(path.with_suffix('.npz'), **arrays, **signal_arrays(tracker.records),
                    executed_actions=np.asarray(actions), frame_t=np.arange(t + 1), final_state=np.asarray(env.get_sim_state()))
                temporary = path.with_suffix('.tmp.mp4')
                with imageio.get_writer(temporary, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                    for im in frames:
                        writer.append_data(im)
                temporary.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path, outcome)
                print(f'[decoder-control] {job["id"]} {arm} success={success} steps={t}', flush=True)
            atomic_json(output / 'completed.json', dict(status='completed', arms=arms))
        finally:
            env.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    run(json.loads(parser.parse_args().batch.read_text()))

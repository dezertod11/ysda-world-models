#!/usr/bin/env python3
"""Paired full-episode hidden-token medoid transfer, with a read-only hook gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import time

import numpy as np

from decoder_token_medoid import ARMS, ActionHiddenCapture, patch_weights, token_cosine_medoid
from p5_repeat_feedback import atomic_json, digest, array_digest
from p5_candidate_replication import atomic_npz, signal_arrays
from collect_feedback_controls import observation_arrays, restore_observation, input_hashes


def sample_pool(c, cfg, model, stats, obs, description, seeds, resize, capture=True):
    from cosmos_policy.experiments.robot.libero.uncertainty_metrics import summarize_action_ensemble
    samples, features, audits = [], [], []
    incidence = None
    for seed in seeds:
        reader = ActionHiddenCapture(model) if capture else None
        try:
            one, _ = c._sample_candidates(cfg, model, stats, obs, description, (seed,), resize,
                                          prediction_mode='parallel')
            sample = one[0]
            if np.asarray(sample['actions']).shape != (16, 7):
                raise ValueError('Expected H16 x 7 native action chunk')
            if reader is not None:
                hidden, counts, audit = reader.finish(sample)
                if audit['calls'] != cfg.num_denoising_steps_action:
                    raise ValueError('Denoiser/capture call count changed')
                if incidence is not None:
                    np.testing.assert_array_equal(incidence, counts)
                incidence = counts
                features.append(hidden)
                audits.append(audit)
            samples.append(sample)
        finally:
            if reader is not None:
                reader.close()
    metrics = summarize_action_ensemble(samples)
    return samples, metrics, np.asarray(features), incidence, audits


def pack(c, samples):
    data = dict(actions=np.stack([s['actions'] for s in samples]).astype(np.float32),
                values=np.asarray([s['value_prediction'] for s in samples], dtype=np.float32))
    for name in ('future_image', 'future_wrist_image'):
        predictions = [s.get('future_image_predictions', {}).get(name) for s in samples]
        if all(p is not None for p in predictions):
            data[name] = np.stack([c._to_numpy(p) for p in predictions])
    data['generated_latent'] = np.stack([c._to_numpy(s['generated_latent']) for s in samples])
    if not all(np.isfinite(a).all() for a in data.values()):
        raise ValueError('Non-finite candidate pool')
    return data


def unpack(data, indices):
    return [dict(actions=data['actions'][i], value_prediction=float(data['values'][i]),
                 generated_latent=data['generated_latent'][i], latent_indices=indices,
                 future_image_predictions={name: data[name][i]
                    for name in ('future_image', 'future_wrist_image') if name in data})
            for i in range(len(data['actions']))]


def selectors(samples, features, incidence):
    from cosmos_policy.experiments.robot.libero.consensus_medoid import consensus_medoid_only
    values = np.asarray([s['value_prediction'] for s in samples], dtype=float)
    if len(values) != 3 or not np.isfinite(values).all():
        raise ValueError('Selectors require three finite candidates')
    action_index, action = consensus_medoid_only(np.stack([s['actions'] for s in samples]),
        horizon=5, discount=.9, translation_weight=1., rotation_weight=.5, gripper_weight=.25)
    hidden_index, costs, distances = token_cosine_medoid(features, patch_weights(incidence))
    uniform_index, uniform_costs, _ = token_cosine_medoid(features, patch_weights(incidence, early_weight=1.))
    prefix_index, prefix_costs, _ = token_cosine_medoid(features, patch_weights(incidence, prefix=8))
    indices = dict(first=0, max_value=int(np.argmax(values)), action_medoid=action_index,
                   decoder_medoid=hidden_index)
    return indices, dict(indices=indices, values=values, decoder_costs=costs,
        decoder_distances=distances, action_costs=action['costs'],
        uniform_diagnostic_index=uniform_index, uniform_diagnostic_costs=uniform_costs,
        prefix8_diagnostic_index=prefix_index, prefix8_diagnostic_costs=prefix_costs,
        hidden_sha256=array_digest(features), hidden_shape=list(features.shape))


def hook_smoke(c, cfg, model, stats, obs, description, seeds, resize, output):
    import torch
    outputs, rngs = [], []
    for capture in (False, True, True):
        c.set_seed_everywhere(918273)
        result = sample_pool(c, cfg, model, stats, obs, description, seeds, resize, capture=capture)
        outputs.append((pack(c, result[0]), result[1:]))
        rngs.append((torch.get_rng_state().numpy().copy(), torch.cuda.get_rng_state().numpy().copy()))
        del result
    for data, _ in outputs[1:]:
        for key, reference in outputs[0][0].items():
            np.testing.assert_array_equal(reference, data[key], err_msg='Hook changed ' + key)
    np.testing.assert_array_equal(outputs[1][1][1], outputs[2][1][1])
    for states in rngs[1:]:
        for a, b in zip(rngs[0], states):
            np.testing.assert_array_equal(a, b, err_msg='Hook changed RNG state')
    features, incidence, audits = outputs[1][1][1:]
    weights = patch_weights(incidence)
    counts = [a['calls'] for a in audits]
    if len(set(counts)) != 1:
        raise ValueError('Different denoiser call counts between candidates')
    atomic_npz(output / 'hook_features.npz', hidden=features, incidence=incidence, weights=weights)
    atomic_json(output / 'hook_audit.json', dict(passed=True, exact_actions_latents_values_images=True,
        repeated_hidden_exact=True, rng_unchanged=True, seeds=seeds, capture=audits,
        hidden_shape=list(features.shape), weights_min=float(weights.min()), weights_max=float(weights.max()),
        feature_sha256=digest(output / 'hook_features.npz')))


def committed(path):
    if not path.exists():
        return False
    row = json.loads(path.read_text())
    for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
        if digest(path.with_suffix(ext)) != row[key]:
            raise ValueError('Changed committed rollout ' + str(path))
    return True


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
    import torch
    suite_name = batch['jobs'][0]['suite']
    if any(j['suite'] != suite_name or j['level'] != batch['jobs'][0]['level'] for j in batch['jobs']):
        raise ValueError('One suite/level per worker process')
    cfg = c.default_policy_config(suite_name, seed=0, num_open_loop_steps=16,
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
        raise ValueError('Generated horizon changed')
    resize = c.get_image_resize_size(cfg.model_family)
    suite = c.benchmark.get_benchmark_dict()[suite_name]()
    for job in batch['jobs']:
        if stopped or time.time() >= batch['deadline_epoch']:
            return
        output = directory / job['phase'] / job['id']
        output.mkdir(parents=True, exist_ok=True)
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            c.set_seed_everywhere(job['env_seed'])
            start_file = output / 'start.json'
            if start_file.exists():
                start_meta = json.loads(start_file.read_text())
                if digest(output / 'start.npz') != start_meta['sha256']:
                    raise ValueError('Changed initial snapshot')
                with np.load(output / 'start.npz', allow_pickle=False) as f:
                    start = {k: f[k].copy() for k in f.files}
            else:
                states = c.get_task_init_states_compat(suite, job['task_id'], task)
                if job['init_state_id'] >= len(states):
                    raise ValueError('Missing initial state, not a policy failure')
                env.reset()
                obs = env.set_init_state(states[job['init_state_id']])
                for _ in range(10):
                    obs, _, success, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
                    if success:
                        raise ValueError('Already successful during settle')
                start = dict(c.runtime_snapshot_arrays(c.capture_libero_runtime_state(env)),
                             **observation_arrays(obs, 'obs__'))
                atomic_npz(output / 'start.npz', **start)
                start_meta = dict(sha256=digest(output / 'start.npz'), input_hashes=input_hashes(c, cfg, obs, resize),
                                  task_description=description, env_seed=job['env_seed'])
                atomic_json(start_file, start_meta)
            snapshot = runtime_snapshot_from_arrays(start)
            obs0 = restore_observation(start, 'obs__')
            if start_meta['task_description'] != description:
                raise ValueError('Instruction changed')
            c._restore_snapshot(env, snapshot)
            if job['phase'] == 'smoke':
                hook_smoke(c, cfg, model, stats, obs0, description, job['candidate_seeds'], resize, output)
                atomic_json(output / 'completed.json', dict(status='completed', phase='smoke'))
                print('[decoder] hook parity passed: ' + job['id'], flush=True)
                continue
            pool_meta_file = output / 'q0_pool.json'
            if pool_meta_file.exists():
                pool_meta = json.loads(pool_meta_file.read_text())
                if digest(output / 'q0_pool.npz') != pool_meta['sha256']:
                    raise ValueError('Changed common q0 pool')
                with np.load(output / 'q0_pool.npz', allow_pickle=False) as f:
                    pool_data = {k: f[k].copy() for k in f.files}
            else:
                c.set_seed_everywhere(job['env_seed'])
                started = time.monotonic()
                samples, metrics, features, incidence, audits = sample_pool(c, cfg, model, stats, obs0,
                    description, job['candidate_seeds'], resize)
                choices, diagnostic = selectors(samples, features, incidence)
                pool_data = dict(pack(c, samples), hidden=features, incidence=incidence)
                atomic_npz(output / 'q0_pool.npz', **pool_data)
                pool_meta = dict(sha256=digest(output / 'q0_pool.npz'), latent_indices=samples[0]['latent_indices'],
                    metrics=metrics, choices=choices, diagnostic=diagnostic, capture=audits,
                    elapsed_seconds=time.monotonic() - started)
                atomic_json(pool_meta_file, pool_meta)
                del samples, features
            q0_samples = unpack(pool_data, pool_meta['latent_indices'])
            offset = (job['task_id'] + job['init_state_id'] + job['seed_group']) % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                path = output / (arm + '.json')
                if committed(path):
                    continue
                if stopped or time.time() >= batch['deadline_epoch']:
                    return
                c.set_seed_everywhere(job['env_seed'])
                c._restore_snapshot(env, snapshot)
                np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                obs = c._copy_observation(obs0)
                if input_hashes(c, cfg, obs, resize) != start_meta['input_hashes']:
                    raise ValueError('Initial model inputs differ between arms')
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
                        if stopped or time.time() >= batch['deadline_epoch']:
                            return
                        query_started = time.monotonic()
                        seeds = job['candidate_seeds'][:1] if arm == 'first' else job['candidate_seeds']
                        if q == 0:
                            samples = q0_samples[:1] if arm == 'first' else q0_samples
                            index = pool_meta['choices'][arm]
                            metrics = pool_meta['metrics'] if arm != 'first' else {'num_samples': 1.}
                            diagnostic, audits = pool_meta['diagnostic'], pool_meta['capture']
                            sampling_seconds = pool_meta['elapsed_seconds']
                        else:
                            samples, metrics, features, incidence, audits = sample_pool(c, cfg, model, stats,
                                obs, description, seeds, resize, capture=arm != 'first')
                            if arm == 'first':
                                index, diagnostic = 0, dict(indices={'first': 0})
                            else:
                                choices, diagnostic = selectors(samples, features, incidence)
                                index = choices[arm]
                            sampling_seconds = time.monotonic() - query_started
                            del features
                        calls += len(samples)
                        before = c._copy_observation(obs)
                        for key, value in pack(c, samples).items():
                            # Full generated latent is retained for q0; later queries keep outputs, not all activations.
                            if key != 'generated_latent':
                                arrays[f'q{q:03d}_{key}'] = value
                        arrays[f'q{q:03d}_future_proprio'] = np.stack([c.extract_future_proprio_from_sample(s) for s in samples])
                        arrays[f'q{q:03d}_input_external'] = c.get_libero_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_input_wrist'] = c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)
                        t0 = t
                        obs, success, t, executed = c._execute_actions(env, obs, samples[index]['actions'], tracker,
                                                                      absolute_t=t, max_t=280)
                        # A terminal/truncated chunk has not reached the predicted H16 future time.
                        errors = c.prediction_error_metrics_for_query(samples[index], before, obs, stats,
                            cfg.flip_images, success) if executed == 16 else {}
                        # Terminal value is not trained as success-within-this-chunk probability.
                        errors.pop('prediction_error_value_abs_chunk_success', None)
                        arrays[f'q{q:03d}_actual_external'] = c.get_libero_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_actual_wrist'] = c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)
                        arrays[f'q{q:03d}_actual_proprio'] = c.proprio_from_libero_obs(obs)
                        queries.append(dict(query=q, t=t0, t_after=t, executed=executed, index=index,
                            candidate_seeds=seeds, metrics=metrics, selectors=diagnostic, capture=audits,
                            input_hashes=input_hashes(c, cfg, before, resize), sampling_seconds=sampling_seconds,
                            prediction_error_horizon_aligned=executed == 16, prediction_errors=errors,
                            common_q0_pool=q == 0))
                        print(f'[decoder-query] {job["id"]} {arm} q={q} t={t} selected={index}', flush=True)
                        q += 1
                        del samples
                finally:
                    env.step = step
                outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280,
                                               continuation_queries=q)
                outcome.update(job, arm=arm, task_description=description, queries=queries,
                    initial_sha256=start_meta['sha256'], q0_pool_sha256=pool_meta['sha256'],
                    video_frames=len(frames), elapsed_seconds=time.monotonic() - started,
                    candidate_calls_logical=calls, cuda_peak_bytes=torch.cuda.max_memory_allocated(),
                    selector_uses_simulator_labels=False, prediction_mode='parallel',
                    generated_horizon=16, executed_horizon=16)
                atomic_npz(path.with_suffix('.npz'), **arrays, **signal_arrays(tracker.records),
                    executed_actions=np.asarray(actions), frame_t=np.arange(t + 1), final_state=np.asarray(env.get_sim_state()))
                temp = path.with_suffix('.tmp.mp4')
                with imageio.get_writer(temp, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                    for im in frames:
                        writer.append_data(im)
                temp.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path, outcome)
                print(f'[decoder] {job["id"]} {arm} success={success} steps={t}', flush=True)
            atomic_json(output / 'completed.json', dict(status='completed', arms=ARMS))
        finally:
            env.close()


if __name__ == '__main__':
    main()

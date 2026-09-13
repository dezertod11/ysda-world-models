#!/usr/bin/env python3
"""Collect full episodes and paired recovery branches with physical fallbacks."""
import argparse
import copy
import json
from pathlib import Path
import signal
import time

import numpy as np

from recovery_confirmation import ARMS, TIMES, expected_arms, suffix_query
from p5_repeat_feedback import atomic_json, digest
from p5_candidate_replication import atomic_npz, signal_arrays
from collect_feedback_controls import observation_arrays, restore_observation, input_hashes
from observation_contract import intervene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    directory = Path(batch['campaign'])
    config = json.loads((directory / 'config.json').read_text())
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def checkpoint():
        if stopped or time.time() >= batch['deadline_epoch']:
            raise InterruptedError('Campaign deadline or requested stop')

    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from perception_regrasp import FrozenPatchLocalizer
    from perception_regrasp_trigger import load_trigger_artifact
    from robosuite import macros
    import imageio.v2 as imageio
    if macros.IMAGE_CONVENTION != 'opengl':
        raise ValueError('Frozen localizer requires native OpenGL RGB')
    cfg = c.default_policy_config('libero_object_temp', seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    stats = c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg)
    model, mc = c.get_model(cfg)
    if cfg.chunk_size != mc.dataloader_train.dataset.chunk_size:
        raise ValueError('Generated horizon changed')
    localizer = FrozenPatchLocalizer(config['localizer'], device='cuda')
    artifact = load_trigger_artifact(config['trigger'])
    resize = c.get_image_resize_size(cfg.model_family)
    suite = c.benchmark.get_benchmark_dict()['libero_object_temp']()

    def frame(obs):
        return np.concatenate([c.get_libero_image(obs, flip_images=cfg.flip_images),
                               c.get_libero_wrist_image(obs, flip_images=cfg.flip_images)], axis=1)

    def sample(obs, description, seed, q, t, horizon):
        checkpoint()
        seeds = tuple(seed + q * 1000 + i for i in range(4))
        samples, metrics = c._sample_candidates(cfg, model, stats, obs, description,
            seeds, resize, prediction_mode='parallel')
        index, _ = c._select_max_value(samples, open_loop_steps=horizon)
        record = dict(t=t, query=q, seeds=seeds, index=index, metrics=metrics,
            input_hashes=input_hashes(c, cfg, obs, resize),
            candidate_actions=[np.asarray(x['actions']).tolist() for x in samples],
            candidate_values=[float(x['value_prediction']) for x in samples],
            requested_horizon=horizon)
        actions = np.asarray(samples[index]['actions'], dtype=np.float32).copy()
        del samples
        return actions, record

    def commit(folder, arm, job, obs, env, tracker, success, t, frames, actions, queries,
               prefix_sha, prefix_t, diag, started, *, video_start_t=0, branch_actions=None):
        path = folder / (arm + '.json')
        if len(frames) != t - video_start_t + 1:
            raise ValueError('Full video frame accounting mismatch')
        outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280,
                                      continuation_queries=len(queries))
        outcome.update({k: job[k] for k in ('cell', 'cohort', 'task_id', 'init_state_id',
            'repeat', 'rollout_seed', 'calibration_cell_seen', 'phase', 'boundary')})
        outcome.update(job_id=job['id'], case_id=job['case_id'], arm=arm,
            task_description=str(suite.get_task(job['task_id']).language), prefix_sha256=prefix_sha,
            prefix_t=prefix_t, queries=queries, intervention=diag, physical_fallback=True,
            simulator_labels_online=False, diagnostic_only_simulator_labels=True,
            video_frames=len(frames), video_start_t=video_start_t,
            elapsed_seconds=time.time() - started)
        arrays = dict(executed_actions=np.asarray(actions, dtype=np.float32),
            final_state=np.asarray(env.get_sim_state()).copy(),
            frame_t=np.arange(video_start_t, t + 1), **signal_arrays(tracker.records))
        if branch_actions is not None:
            arrays['branch_actions'] = np.asarray(branch_actions, dtype=np.float32)
        atomic_npz(path.with_suffix('.npz'), **arrays)
        temporary = path.with_suffix('.tmp.mp4')
        with imageio.get_writer(temporary, fps=20, codec='libx264', pixelformat='yuv420p',
                                macro_block_size=1) as writer:
            for image in frames:
                writer.append_data(image)
        temporary.replace(path.with_suffix('.mp4'))
        outcome.update(npz_sha256=digest(path.with_suffix('.npz')),
                       video_sha256=digest(path.with_suffix('.mp4')))
        atomic_json(path, outcome)
        print(f'[recovery-confirm] {job["id"]} {arm} success={success} t={t}', flush=True)

    def load_prefix(folder, boundary):
        stem = folder / f'prefix_{boundary}'
        meta = json.loads(stem.with_suffix('.json').read_text())
        if digest(stem.with_suffix('.npz')) != meta['sha256']:
            raise ValueError('Changed branch snapshot')
        with np.load(stem.with_suffix('.npz'), allow_pickle=False) as values:
            data = {k: values[k].copy() for k in values.files}
        return data, meta

    def baseline(env, task, job, folder):
        if (folder / 'baseline_h16.json').exists():
            for boundary in TIMES:
                load_prefix(folder, boundary)
            return
        # An interrupted, uncommitted baseline is regenerated deterministically.
        c.set_seed_everywhere(job['rollout_seed'])
        states = c.get_task_init_states_compat(suite, job['task_id'], task)
        if not 0 <= job['init_state_id'] < len(states):
            raise ValueError('Init state outside benchmark assets')
        env.reset()
        obs = env.set_init_state(states[job['init_state_id']])
        for _ in range(10):
            obs, _, done, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
            if done:
                raise ValueError('Success during settle')
        tracker = c.SafetySignalTracker(env, obs)
        frames, actions, queries = [frame(obs)], [], []
        t, q, success = 0, 0, False
        started = time.time()
        saved = set()

        def save(boundary):
            data = dict(c.runtime_snapshot_arrays(c.capture_libero_runtime_state(env)),
                prefix_actions=np.asarray(actions, dtype=np.float32),
                prefix_frames=np.asarray(frames, dtype=np.uint8),
                **observation_arrays(obs, 'obs__'))
            stem = folder / f'prefix_{boundary}'
            atomic_npz(stem.with_suffix('.npz'), **data)
            atomic_json(stem.with_suffix('.json'), dict(t=t, success=success,
                boundary=boundary, sha256=digest(stem.with_suffix('.npz')),
                tracker_records=tracker.records, queries=copy.deepcopy(queries),
                input_hashes=input_hashes(c, cfg, obs, resize)))
            saved.add(boundary)

        while not success and t < 280:
            chosen, query = sample(obs, str(task.language), job['rollout_seed'], q, t, 16)
            queries.append(query)
            for action in chosen[:16]:
                if success or t >= 280:
                    break
                obs, success, t, _ = c._execute_actions(env, obs, np.asarray([action]), tracker,
                                                       absolute_t=t, max_t=280)
                actions.append(action.copy())
                frames.append(frame(obs))
                if t in TIMES:
                    save(t)
            q += 1
        for boundary in TIMES:
            if boundary not in saved:
                if not success or t >= boundary:
                    raise ValueError('Missed registered snapshot')
                save(boundary)
        commit(folder, 'baseline_h16', job, obs, env, tracker, success, t, frames, actions,
               queries, None, 0, dict(repair_requested=False, generated_horizon=16), started)

    for job in batch['jobs']:
        checkpoint()
        folder = directory / job['phase'] / job['id']
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / 'completed.json').exists():
            continue
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            c.set_seed_everywhere(job['rollout_seed'])
            if job['phase'] == 'smoke':
                source = Path(config['replay_source']) / 'screen' / job['source_id']
                meta = json.loads((source / 'prefix.json').read_text())
                if digest(source / 'prefix.npz') != job['source_hashes']['prefix.npz']:
                    raise ValueError('Smoke source hash changed')
                with np.load(source / 'prefix.npz', allow_pickle=False) as values:
                    data = {k: values[k].copy() for k in values.files}
                meta['queries'], meta['tracker_records'] = [], []
                video_start_t = meta['t']
                history_frames = [frame(restore_observation(data, 'obs__'))]
                history_actions = []
            else:
                parent = directory / 'main' / job['case_id']
                if job['phase'] == 'main':
                    baseline(env, task, job, folder)
                data, meta = load_prefix(parent, job['boundary'])
                video_start_t = 0
                history_frames = list(data['prefix_frames'])
                history_actions = list(data['prefix_actions'])
            snapshot = runtime_snapshot_from_arrays(data)
            obs0 = restore_observation(data, 'obs__')
            c._restore_snapshot(env, snapshot)
            loc = {} if meta['success'] else p._localize(env, obs0, localizer, description)
            atomic_json(folder / 'localization.json', loc)
            offset = job['init_state_id'] % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                checkpoint()
                path = folder / (arm + '.json')
                if path.exists():
                    old = json.loads(path.read_text())
                    if old['prefix_sha256'] != meta['sha256'] or any(
                        digest(path.with_suffix(ext)) != old[key] for ext, key in
                        (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256'))):
                        raise ValueError('Changed committed branch')
                    continue
                started = time.time()
                c._restore_snapshot(env, snapshot)
                np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                obs = c._copy_observation(obs0)
                tracker = c.SafetySignalTracker(env, obs)
                frames, actions, branch_actions = list(history_frames), list(history_actions), []
                original_step = env.step

                def record(action):
                    result = original_step(action)
                    actions.append(np.asarray(action, dtype=np.float32).copy())
                    branch_actions.append(np.asarray(action, dtype=np.float32).copy())
                    frames.append(frame(result[0]))
                    return result

                env.step = record
                try:
                    t, success = meta['t'], meta['success']
                    branch_job = dict(job, previous_gripper=float(data['prefix_actions'][-1, 6]))
                    diag = dict(repair_requested=False, refresh_requested=False, prefix_success=success)
                    if not success:
                        obs, success, t, diag, _, _ = intervene(c, p, r, env, obs, tracker,
                            localizer, artifact, description, cfg, arm, loc, t,
                            branch_job, model, stats, resize)
                    q = suffix_query(job['boundary'])
                    queries = []
                    while not success and t < 280:
                        chosen, query = sample(obs, description, job['rollout_seed'], q, t, 8)
                        queries.append(query)
                        obs, success, t, _ = c._execute_actions(env, obs, chosen[:8], tracker,
                                                               absolute_t=t, max_t=280)
                        q += 1
                finally:
                    env.step = original_step
                diag['signal_scope'] = 'post_boundary_only; prefix signals saved separately'
                commit(folder, arm, job, obs, env, tracker, success, t, frames, actions, queries,
                    meta['sha256'], meta['t'], diag, started, video_start_t=video_start_t,
                    branch_actions=branch_actions)
            atomic_json(folder / 'completed.json', dict(status='completed', arms=list(expected_arms(job))))
        finally:
            env.close()


if __name__ == '__main__':
    try:
        main()
    except InterruptedError as error:
        print(str(error), flush=True)

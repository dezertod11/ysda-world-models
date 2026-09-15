#!/usr/bin/env python3
"""Full paired P3 episodes, including common-prefix and passive-monitor audits."""
import argparse
import copy
import json
from pathlib import Path
import signal
import time

import numpy as np

from p3_benchmark import ARMS, policy_source, run_episode
from event_feedback import EventConfig, Evidence
from p5_repeat_feedback import digest, array_digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json
from p5_candidate_replication import atomic_npz, signal_arrays
from collect_feedback_controls import observation_arrays, restore_observation, input_hashes


def committed(path):
    if not path.exists():
        return False
    row = json.loads(path.read_text())
    for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
        if digest(path.with_suffix(ext)) != row[key]:
            raise ValueError('Changed committed artifact: ' + str(path))
    return True


def collect(batch):
    directory = Path(batch['campaign'])
    frozen = json.loads((directory / 'config.json').read_text())
    config_sha = digest(directory / 'config.json')
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def check():
        if stopped or time.time() >= batch['deadline_epoch']:
            raise InterruptedError('Campaign deadline or requested stop')
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from observation_contract import intervene
    from perception_regrasp import FrozenPatchLocalizer, canonical_object_name
    from perception_regrasp_trigger import load_trigger_artifact
    from event_feedback_libero import PassiveMonitor
    from grounded_probe import FrozenObjectMask
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from robosuite import macros
    import cosmos_policy
    import imageio.v2 as imageio
    runtime = policy_source(cosmos_policy)
    if runtime != (Path(frozen['runtime']) / 'cosmos_policy').resolve():
        raise ValueError('Unexpected active Cosmos source: ' + str(runtime))
    if macros.IMAGE_CONVENTION != 'opengl':
        raise ValueError('Localizer requires native OpenGL observation orientation')
    suite_name = batch['jobs'][0]['suite']
    if any((j['suite'], j['level']) != (suite_name, batch['jobs'][0]['level']) for j in batch['jobs']):
        raise ValueError('One asset variant per worker')
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
    if mc.dataloader_train.dataset.chunk_size != 16:
        raise ValueError('Unexpected model horizon')
    localizer = FrozenPatchLocalizer(frozen['localizer'], device='cuda')
    artifact = load_trigger_artifact(frozen['trigger'])
    masker = FrozenObjectMask(frozen['mask'])
    resize = c.get_image_resize_size(cfg.model_family)
    event_config = EventConfig(**frozen['event_parameters'])
    suite = c.benchmark.get_benchmark_dict()[suite_name]()
    for job in batch['jobs']:
        check()
        folder = directory / job['phase'] / job['id']
        folder.mkdir(parents=True, exist_ok=True)
        arms = tuple(frozen['arms']) + (('shadow',) if job['phase'] == 'smoke' else ())
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        if description != job['task_description']:
            raise ValueError('Task instruction differs from reference manifest')
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            c.set_seed_everywhere(job['rollout_seed'])
            start_path = folder / 'start.json'
            if start_path.exists():
                initial_meta = json.loads(start_path.read_text())
                if digest(folder / 'start.npz') != initial_meta['sha256'] or initial_meta['config_sha256'] != config_sha:
                    raise ValueError('Initial snapshot changed')
                with np.load(folder / 'start.npz', allow_pickle=False) as z:
                    start = {k: z[k].copy() for k in z.files}
            else:
                states = c.get_task_init_states_compat(suite, job['task_id'], task)
                if job['init_state_id'] >= len(states):
                    raise ValueError('Missing init asset; not a policy failure')
                env.reset()
                obs = env.set_init_state(states[job['init_state_id']])
                for _ in range(10):
                    obs, _, done, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
                    if done:
                        raise ValueError('Success during settling')
                start = dict(c.runtime_snapshot_arrays(c.capture_libero_runtime_state(env)),
                             **observation_arrays(obs, 'obs__'))
                atomic_npz(folder / 'start.npz', **start)
                initial_meta = dict(sha256=digest(folder / 'start.npz'), config_sha256=config_sha,
                    input_hashes=input_hashes(c, cfg, obs, resize), job=job)
                atomic_json(start_path, initial_meta)
            snapshot = runtime_snapshot_from_arrays(start)
            obs0 = restore_observation(start, 'obs__')
            supported = canonical_object_name(description) in localizer.supported_objects
            pool_cache = {}
            offset = (job['task_id'] + job['init_state_id']) % len(ARMS)
            order = ARMS[offset:] + ARMS[:offset] + (('shadow',) if job['phase'] == 'smoke' else ())
            for arm in order:
                check()
                path = folder / (arm + '.json')
                if committed(path):
                    row = json.loads(path.read_text())
                    if row['config_sha256'] != config_sha or row['initial_sha256'] != initial_meta['sha256']:
                        raise ValueError('Resume configuration/initial state mismatch')
                    continue
                c._restore_snapshot(env, snapshot)
                np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                obs = c._copy_observation(obs0)
                tracker = c.SafetySignalTracker(env, obs)
                executed, frames = [], []
                def frame(o):
                    return np.concatenate([c.get_libero_image(o, flip_images=cfg.flip_images),
                        c.get_libero_wrist_image(o, flip_images=cfg.flip_images)], axis=1)
                frames.append(frame(obs))
                original_step = env.step
                def record(action):
                    check()
                    if len(executed) >= event_config.max_steps:
                        raise ValueError('Exceeded physical step budget')
                    result = original_step(action)
                    executed.append(np.asarray(action, dtype=np.float32).copy())
                    frames.append(frame(result[0]))
                    return result
                env.step = record
                started = time.monotonic()
                actual_candidates = 0
                sampling_seconds = 0.
                monitor_seconds = 0.
                monitor = PassiveMonitor(env, description, event_config,
                    localizer if supported else None, artifact if supported else None, masker if supported else None)
                class TimedMonitor:
                    @property
                    def diagnostics(self):
                        return monitor.diagnostics
                    def __call__(self, o, recent):
                        nonlocal monitor_seconds
                        before = time.monotonic()
                        evidence = monitor(o, recent)
                        monitor_seconds += time.monotonic() - before
                        return evidence
                def policy(o, t, q, k):
                    nonlocal actual_candidates, sampling_seconds
                    hashes = input_hashes(c, cfg, o, resize)
                    # Share only exactly equal policy inputs and stochastic seeds.
                    key = (json.dumps(hashes, sort_keys=True), q)
                    before = time.monotonic()
                    if key not in pool_cache:
                        seeds = tuple(job['rollout_seed'] + q * 1000 + i for i in range(4))
                        samples, metrics = c._sample_candidates(cfg, model, stats, o, description,
                            seeds, resize, prediction_mode='parallel')
                        pool_cache[key] = (np.stack([s['actions'] for s in samples]).astype(np.float32),
                            np.asarray([s['value_prediction'] for s in samples]), dict(uncertainty=metrics,
                                seeds=seeds, input_hashes=hashes))
                        actual_candidates += 4
                        del samples
                    sampling_seconds += time.monotonic() - before
                    aa, vv, meta = pool_cache[key]
                    extra = copy.deepcopy(meta)
                    extra['seeds'] = extra['seeds'][:k]
                    extra['pool_sha256'] = array_digest(aa[:k])
                    if k == 1:
                        extra['uncertainty'] = {}
                    return aa[:k].copy(), vv[:k].copy(), extra
                def step(action):
                    o, done, _, _ = c._execute_actions(env, None, np.asarray([action]), tracker,
                        absolute_t=len(executed), max_t=event_config.max_steps)
                    return o, done
                def recover(o, t, budget):
                    if not supported:
                        return o, False, [], dict(repair_requested=False, reason='unsupported_target')
                    loc = p._localize(env, o, localizer, description)
                    previous = float(executed[-1][6]) if executed else -1.
                    before = len(executed)
                    o, done, end, diag, _, _ = intervene(c, p, r, env, o, tracker, localizer,
                        artifact, description, cfg, 'physical_regrasp', loc, t,
                        dict(job, previous_gripper=previous), model, stats, resize)
                    if end != len(executed):
                        raise ValueError('Recovery step accounting mismatch')
                    return o, done, executed[before:], diag
                try:
                    result = run_episode(obs, arm=arm, policy=policy, step=step, recover=recover,
                        monitor=TimedMonitor(), config=event_config, check=check)
                finally:
                    env.step = original_step
                np.testing.assert_array_equal(result.pop('actions'), np.asarray(executed))
                if len(frames) != result['final_t'] + 1:
                    raise ValueError('Video does not include every physical step')
                outcome = c._terminal_outcome(tracker, success=result['success'], final_t=result['final_t'],
                    max_t=event_config.max_steps, continuation_queries=result['model_calls'])
                outcome.update(result, job=job, arm=arm, task_description=description,
                    initial_sha256=initial_meta['sha256'], config_sha256=config_sha,
                    initial_input_hashes=initial_meta['input_hashes'], simulator_labels_online=False,
                    video_frames=len(frames), video_start_t=0, safety_signal_scope='whole_episode_proxies',
                    elapsed_seconds=time.monotonic() - started, monitor_seconds=monitor_seconds,
                    sampling_seconds=sampling_seconds, actual_sampled_candidates=actual_candidates,
                    logical_candidates=result['model_calls'] * (1 if arm == 'first_k1' else 4),
                    timing_caveat='Generation cache shared across arms; use logical counts for method cost',
                    supported_target=supported)
                atomic_npz(path.with_suffix('.npz'), executed_actions=np.asarray(executed, dtype=np.float32),
                    final_state=env.get_sim_state(), frame_t=np.arange(result['final_t'] + 1),
                    **signal_arrays(tracker.records))
                tmp = path.with_suffix('.tmp.mp4')
                with imageio.get_writer(tmp, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                    for im in frames:
                        writer.append_data(im)
                tmp.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path, outcome)
                print(f'[p3-benchmark] {job["id"]} {arm} success={result["success"]} t={result["final_t"]}', flush=True)
            from analyze_p3_benchmark import audit_case
            audit = audit_case(folder, arms, decode=job['phase'] == 'smoke')
            atomic_json(folder / 'completed.json', dict(status='completed', config_sha256=config_sha, **audit))
        finally:
            env.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    try:
        collect(json.loads(args.batch.read_text()))
    except InterruptedError as error:
        print(str(error), flush=True)

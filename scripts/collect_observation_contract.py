#!/usr/bin/env python3
"""Physical observation-contract interventions from exact saved prefixes."""
import argparse
import json
from pathlib import Path
import shutil
import signal
import time

import numpy as np

from observation_contract import ARMS, ORACLES, intervene
from p5_repeat_feedback import atomic_json, digest
from p5_candidate_replication import atomic_npz, signal_arrays
from collect_feedback_controls import restore_observation
from probe_repair import validate_probe_pair
import collect_probe_repair as legacy


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
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from perception_regrasp import FrozenPatchLocalizer
    from perception_regrasp_trigger import load_trigger_artifact
    from robosuite import macros
    import imageio.v2 as imageio
    if macros.IMAGE_CONVENTION != 'opengl':
        raise ValueError('Frozen localizer requires OpenGL input')
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
        raise ValueError('Horizon mismatch')
    localizer = FrozenPatchLocalizer(config['localizer'], device='cuda')
    artifact = load_trigger_artifact(config['trigger'])
    resize = c.get_image_resize_size(cfg.model_family)
    suite = c.benchmark.get_benchmark_dict()['libero_object_temp']()
    for job in batch['jobs']:
        if stopped or time.time() > batch['deadline_epoch']:
            return
        output = directory / job['phase'] / job['id']
        output.mkdir(parents=True, exist_ok=True)
        if (output / 'completed.json').exists():
            continue
        if job.get('source_id'):
            source = Path(config['replay_source']) / job['source_phase'] / job['source_id']
            for name in ('prefix.npz', 'prefix.json'):
                path = output / name
                if not path.exists():
                    shutil.copy2(source / name, path)
                if digest(path) != job['source_hashes'][name]:
                    raise ValueError('Changed replay prefix')
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            # Loading Cosmos changes cuDNN flags; cached prefixes must use the fresh-prefix mode too.
            c.set_seed_everywhere(job['rollout_seed'])
            data, meta = legacy.prefix(c, p, env, suite, task, cfg, model, stats, resize, job, output)
            if meta['success'] or meta['t'] != 72:
                raise ValueError('Expected the frozen nonterminal t72 prefix')
            job = dict(job, previous_gripper=float(data['prefix_actions'][-1, 6]))
            snapshot = runtime_snapshot_from_arrays(data)
            c._restore_snapshot(env, snapshot)
            obs0 = restore_observation(data, 'obs__')
            loc = {} if meta['success'] else p._localize(env, obs0, localizer, description)
            atomic_json(output / 'localization.json', loc)
            offset = (job['init_state_id'] + job['repeat']) % len(ARMS)
            for arm in ARMS[offset:] + ARMS[:offset]:
                if stopped or time.time() > batch['deadline_epoch']:
                    return
                path = output / (arm + '.json')
                if path.exists():
                    old = json.loads(path.read_text())
                    if old['prefix_sha256'] != meta['sha256'] or any(
                        digest(path.with_suffix(ext)) != old[key]
                        for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256'))):
                        raise ValueError('Changed committed branch')
                    continue
                started = time.time()
                c._restore_snapshot(env, snapshot)
                np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
                obs = c._copy_observation(obs0)
                tracker = c.SafetySignalTracker(env, obs)
                def frame(o):
                    return np.concatenate([c.get_libero_image(o, flip_images=cfg.flip_images),
                                           c.get_libero_wrist_image(o, flip_images=cfg.flip_images)], axis=1)
                frames = [frame(obs)]
                executed = []
                step = env.step
                def record(a):
                    result = step(a)
                    executed.append(np.asarray(a, dtype=np.float32))
                    frames.append(frame(result[0]))
                    return result
                env.step = record
                try:
                    if meta['success']:
                        success, t, queries, q = True, meta['t'], [], 5
                        diag = dict(initial_trigger_passed=False, initial_t72_trigger_passed=False,
                            verification='prefix_success', probe_steps=0, regrasp_steps=0,
                            repair_requested=False, delay_policy_queries=0)
                    else:
                        obs, success, t, diag, queries, q = intervene(c, p, r, env, obs, tracker,
                            localizer, artifact, description, cfg, arm, loc, meta['t'], job, model, stats, resize)
                    if 'delay_end_audit' in diag:
                        ref = output / 'delay_replay_reference.json'
                        if ref.exists():
                            validate_probe_pair(json.loads(ref.read_text()), diag['delay_end_audit'])
                        else:
                            atomic_json(ref, diag['delay_end_audit'])
                    intervention_t = t
                    intervention_end = np.asarray(env.get_sim_state()).copy()
                    while not success and t < 280:
                        seeds = tuple(job['rollout_seed'] + q * 1000 + i for i in range(4))
                        samples, metrics = c._sample_candidates(cfg, model, stats, obs, description,
                            seeds, resize, prediction_mode='parallel')
                        index, _ = c._select_max_value(samples, open_loop_steps=8)
                        queries.append(dict(t=t, seeds=seeds, index=index, metrics=metrics))
                        obs, success, t, _ = c._execute_actions(env, obs, samples[index]['actions'][:8],
                            tracker, absolute_t=t, max_t=280)
                        q += 1
                        del samples
                finally:
                    env.step = step
                outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280,
                                               continuation_queries=len(queries))
                outcome.update({k: job[k] for k in ('cell', 'phase', 'task_id', 'init_state_id',
                    'repeat', 'rollout_seed', 'calibration_cell_seen', 'source_id', 'prefix_seed', 'suffix_repeat')})
                outcome.update(job_id=job['id'], arm=arm, task_description=description,
                    prefix_sha256=meta['sha256'], prefix_t=meta['t'], prefix_success=meta['success'],
                    intervention_end_t=intervention_t, intervention=diag, queries=queries,
                    physical_fallback=True, diagnostic_only_simulator_labels=arm not in ORACLES, simulator_labels_online=arm in ORACLES,
                    video_frames=len(frames), elapsed_seconds=time.time() - started)
                atomic_npz(path.with_suffix('.npz'), executed_actions=np.asarray(executed, dtype=np.float32),
                    intervention_end_state=intervention_end, final_state=np.asarray(env.get_sim_state()).copy(),
                    frame_t=np.arange(meta['t'], t + 1), **signal_arrays(tracker.records))
                temp = output / (arm + '.tmp.mp4')
                with imageio.get_writer(temp, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as w:
                    for im in frames:
                        w.append_data(im)
                temp.replace(path.with_suffix('.mp4'))
                outcome.update(npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4')))
                atomic_json(path, outcome)
                print(f'[observation] {job["id"]} {arm} success={success} repair={diag["repair_requested"]}', flush=True)
            atomic_json(output / 'completed.json', dict(status='completed', arms=list(ARMS), prefix_sha256=meta['sha256']))
        finally:
            env.close()


if __name__ == '__main__':
    main()

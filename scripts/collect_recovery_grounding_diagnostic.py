#!/usr/bin/env python3
"""Camera audit and matched oracle waypoints on frozen recovery prefixes."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import signal
import time

import numpy as np

from recovery_grounding_diagnostic import ARMS, projection_metrics, replace_waypoint
from p5_repeat_feedback import digest
from resume_recovery_confirmation import retry_atomic_json as atomic_json
from p5_candidate_replication import atomic_npz, signal_arrays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    batch = json.loads(args.batch.read_text())
    directory = Path(batch['campaign'])
    config = json.loads((directory / 'config.json').read_text())
    source = Path(config['source_campaign'])
    old = json.loads((source / 'config.json').read_text())
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def check():
        if stopped or time.time() >= batch['deadline_epoch']:
            raise InterruptedError('Diagnostic deadline/requested stop')
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from collect_feedback_controls import restore_observation, input_hashes
    from libero_runtime_snapshot import runtime_snapshot_from_arrays
    from perception_regrasp import FrozenPatchLocalizer, localization_record
    from perception_regrasp_trigger import load_trigger_artifact
    from observation_contract import gate, physical_workspace
    from robosuite import macros
    from robosuite.utils.camera_utils import get_camera_intrinsic_matrix, get_camera_extrinsic_matrix
    if macros.IMAGE_CONVENTION != 'opengl':
        raise ValueError('Frozen source uses native OpenGL observation rows')
    cfg = c.default_policy_config('libero_object_temp', seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(0)
    suite = c.benchmark.get_benchmark_dict()['libero_object_temp']()
    if batch['stage'] != 'geometry':
        c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
        stats = c.load_dataset_stats(cfg.dataset_stats_path)
        c.prewarm_libero_renderer(cfg)
        model, mc = c.get_model(cfg)
        if mc.dataloader_train.dataset.chunk_size != 16:
            raise ValueError('Generated horizon changed')
        localizer = FrozenPatchLocalizer(old['localizer'], device='cuda')
        artifact = load_trigger_artifact(old['trigger'])
        resize = c.get_image_resize_size(cfg.model_family)

    for job in batch['jobs']:
        check()
        parent = source / 'main' / job['id']
        for name, sha in job['source_hashes'].items():
            if digest(parent / name) != sha:
                raise ValueError('Changed source artifact: ' + str(parent / name))
        with np.load(parent / 'prefix_72.npz', allow_pickle=False) as z:
            data = {key: z[key].copy() for key in z.files}
        meta = json.loads((parent / 'prefix_72.json').read_text())
        reference = json.loads((parent / 'physical_regrasp.json').read_text())
        names = reference['terminal_episode_target_objects'].split(',')
        if len(names) != 1 or not names[0].strip():
            raise ValueError('Named single target required')
        target_name = names[0].strip()
        snapshot = runtime_snapshot_from_arrays(data)
        obs0 = restore_observation(data, 'obs__')
        task = suite.get_task(job['task_id'])
        description = str(task.language)
        if reference['task_description'] != description:
            raise ValueError('Task command changed')
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        try:
            c._restore_snapshot(env, snapshot)
            np.testing.assert_allclose(env.get_sim_state(), snapshot['sim_state'], atol=1e-9, rtol=0)
            if batch['stage'] == 'geometry':
                from collect_perception_regrasp_calibration import render_segmentation_compat, _target_geom_ids
                from probe_repair import project_eef
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                loc = reference['intervention']['initial_localization']
                target = np.asarray(obs0[target_name + '_pos'])
                views = []
                fig, axes = plt.subplots(1, 2, figsize=(10, 5), layout='constrained')
                for ax, camera_name, key in zip(axes, ['agentview', 'robot0_eye_in_hand'],
                                                ['agentview_image', 'robot0_eye_in_hand_image']):
                    raw = obs0[key]
                    h, w = raw.shape[:2]
                    k = get_camera_intrinsic_matrix(env.sim, camera_name, h, w)
                    transform = get_camera_extrinsic_matrix(env.sim, camera_name)
                    projected = project_eef(target, k, transform)
                    rendered = env.sim.render(camera_name=camera_name, height=h, width=w)
                    seg = render_segmentation_compat(env.sim, camera_name, h, w)
                    mask = np.isin(seg[:, :, 1], _target_geom_ids(env.sim, target_name))
                    rr, cc = np.nonzero(mask)
                    view = dict(camera=camera_name, projected_gt_cv=projected.tolist(),
                        intrinsic=k.tolist(), camera_to_world=transform.tolist(), target_pixels=int(mask.sum()),
                        observation_raw_mae=float(np.abs(raw.astype(float) - rendered).mean()),
                        observation_flipped_mae=float(np.abs(raw.astype(float) - rendered[::-1]).mean()))
                    if camera_name == 'agentview':
                        view.update(projection_metrics(loc, target, k, transform))
                        point = np.asarray(view['predicted_pixel_cv'])
                        view['predicted_pixel_to_target_mask_px'] = (float(np.min(np.hypot(cc - point[0], rr - point[1])))
                                                                   if len(rr) else None)
                        ax.scatter(*point, c='red', marker='x', label='RGB prediction')
                    ax.imshow(raw[::-1])
                    if mask.any():
                        ax.contour(mask, levels=[.5], colors=['lime'], linewidths=.7)
                    ax.scatter(*projected, c='cyan', marker='+', label='GT center (offline)')
                    ax.set(xlim=(0, w - 1), ylim=(h - 1, 0), title=camera_name)
                    ax.legend(fontsize=8)
                    views.append(view)
                fig.suptitle(job['id'] + ': camera/target audit, privileged labels only')
                folder = directory / 'geometry'
                folder.mkdir(parents=True, exist_ok=True)
                figure = folder / (job['id'] + '.png')
                fig.savefig(figure, dpi=130)
                plt.close(fig)
                first = views[0]
                if (not np.isfinite(first['world_reconstruction_error_m']) or
                        first['world_reconstruction_error_m'] > 1e-6 or
                        not np.isfinite(first['gt_projection_roundtrip_error_m']) or
                        first['gt_projection_roundtrip_error_m'] > 1e-6):
                    raise ValueError('Camera numerical consistency failed; stop before oracle rollouts')
                atomic_json(folder / (job['id'] + '.json'), dict(job_id=job['id'], cohort=job['cohort'],
                    views=views, target_object=target_name, source_hashes=job['source_hashes'],
                    offline_gt_only=True, figure_sha256=digest(figure), numerical_geometry_pass=True))
                print('[geometry] ' + job['id'], flush=True)
                continue

            folder = directory / 'rollouts' / job['id']
            folder.mkdir(parents=True, exist_ok=True)
            selected_arms = ARMS[:1] if batch['stage'] == 'smoke' else ARMS
            for arm in selected_arms:
                check()
                path = folder / (arm + '.json')
                if path.exists():
                    saved = json.loads(path.read_text())
                    for ext, key in (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256')):
                        if digest(path.with_suffix(ext)) != saved[key]:
                            raise ValueError('Changed committed diagnostic')
                    continue
                c.set_seed_everywhere(job['rollout_seed'])
                c._restore_snapshot(env, snapshot)
                obs = c._copy_observation(obs0)
                tracker = c.SafetySignalTracker(env, obs)
                frames, actions, queries = list(data['prefix_frames']), list(data['prefix_actions']), []
                current_obs = obs
                original_step = env.step
                def frame(o):
                    return np.concatenate([c.get_libero_image(o, flip_images=cfg.flip_images),
                                           c.get_libero_wrist_image(o, flip_images=cfg.flip_images)], axis=1)
                def record(action):
                    nonlocal current_obs
                    check()
                    if len(actions) >= 280:
                        raise ValueError('Physical budget exceeded')
                    result = original_step(action)
                    current_obs = result[0]
                    actions.append(np.asarray(action, dtype=np.float32).copy())
                    frames.append(frame(current_obs))
                    return result
                env.step = record
                started = time.time()
                try:
                    t, success = meta['t'], meta['success']
                    loc = p._localize(env, obs, localizer, description)
                    initial = gate(loc, r._eef_position(obs), artifact)
                    physical = arm == 'oracle_xyz_physical_gate'
                    def privileged_record(o):
                        name = loc['perception_object']
                        return dict(perception_object=name,
                            perception_score_range=artifact['objects'][name]['score_range_lower'],
                            **{'perception_world_' + a: float(v) for a, v in zip('xyz', o[target_name + '_pos'])})
                    requested = (gate(privileged_record(obs), r._eef_position(obs), artifact, physical=True).passed
                                 if physical else initial.passed)
                    diag = dict(initial_gate=initial.__dict__, initial_localization=loc,
                        repair_requested=requested, oracle=arm != 'rgb_replay', gate_mode='physical_GT' if physical else 'fixed_RGB',
                        privileged_target=target_name, post_guard=None, primitive={})
                    class Adapter:
                        latest_rgb = None
                        def localize(self, image, text, **kwargs):
                            self.latest_rgb = localizer.localize(image, text, **kwargs)
                            modified = replace_waypoint(self.latest_rgb, current_obs[target_name + '_pos'], arm)
                            diag['post_retreat_rgb'] = localization_record(self.latest_rgb)
                            diag['post_retreat_target_xyz'] = np.asarray(current_obs[target_name + '_pos']).tolist()
                            diag['executed_waypoint'] = np.asarray(modified.world_position).tolist()
                            return modified
                    adapter = Adapter()
                    def validator(localization, eef):
                        rgb_decision = gate(localization_record(adapter.latest_rgb), eef, artifact, require_miss=False)
                        decision = (gate(privileged_record(current_obs), eef, artifact,
                                         physical=True, require_miss=False) if physical else rgb_decision)
                        # A true pose must not make the diagnostic command an out-of-bounds waypoint.
                        safety = physical_workspace(localization.world_position) if arm != 'rgb_replay' else True
                        diag['post_guard'] = dict(rgb=rgb_decision.__dict__, selected=decision.__dict__,
                                                  waypoint_safety_pass=safety)
                        return dict(decision.__dict__, passed=bool(decision.passed and safety))
                    if requested and not success:
                        obs, success, t, n, info = r._run_perception_regrasp(env, obs, tracker, adapter,
                            description, absolute_t=t, max_t=280, writer=None, flip_images=cfg.flip_images,
                            min_confidence=0., localization_validator=validator)
                        diag.update(primitive_steps=n, primitive=info)
                    q = 5
                    while not success and t < 280:
                        check()
                        seeds = tuple(job['rollout_seed'] + q * 1000 + i for i in range(4))
                        samples, metrics = c._sample_candidates(cfg, model, stats, obs, description, seeds,
                                                               resize, prediction_mode='parallel')
                        index, _ = c._select_max_value(samples, open_loop_steps=8)
                        chosen = np.asarray(samples[index]['actions'], dtype=np.float32).copy()
                        queries.append(dict(t=t, query=q, seeds=seeds, index=index, metrics=metrics,
                            candidate_actions=[np.asarray(x['actions']).tolist() for x in samples],
                            candidate_values=[float(x['value_prediction']) for x in samples],
                            input_hashes=input_hashes(c, cfg, obs, resize), requested_horizon=8))
                        del samples
                        obs, success, t, _ = c._execute_actions(env, obs, chosen[:8], tracker, absolute_t=t, max_t=280)
                        q += 1
                finally:
                    env.step = original_step
                arrays = dict(executed_actions=np.asarray(actions, dtype=np.float32),
                    final_state=np.asarray(env.get_sim_state()).copy(), frame_t=np.arange(t + 1),
                    **signal_arrays(tracker.records))
                replay_verified = False
                if arm == 'rgb_replay':
                    with np.load(parent / 'physical_regrasp.npz', allow_pickle=False) as saved:
                        np.testing.assert_allclose(arrays['executed_actions'], saved['executed_actions'], atol=1e-6, rtol=0)
                        np.testing.assert_allclose(arrays['final_state'], saved['final_state'], atol=1e-8, rtol=0)
                    if bool(reference['terminal_success']) != bool(success):
                        raise ValueError('Replay label changed')
                    replay_verified = True
                if len(frames) != t + 1 or len(actions) != t:
                    raise ValueError('Video/action accounting mismatch')
                atomic_npz(path.with_suffix('.npz'), **arrays)
                import imageio.v2 as imageio
                tmp = path.with_suffix('.tmp.mp4')
                with imageio.get_writer(tmp, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                    for image in frames:
                        writer.append_data(image)
                tmp.replace(path.with_suffix('.mp4'))
                outcome = c._terminal_outcome(tracker, success=success, final_t=t, max_t=280, continuation_queries=len(queries))
                atomic_json(path, dict(outcome, job_id=job['id'], cohort=job['cohort'], cell=job['cell'], arm=arm,
                    rollout_seed=job['rollout_seed'], task_description=description, intervention=diag, queries=queries,
                    source_hashes=job['source_hashes'], diagnostic_only=True,
                    simulator_labels_online=arm != 'rgb_replay', replay_reference_verified=replay_verified,
                    video_frames=len(frames), elapsed_seconds=time.time() - started,
                    npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4'))))
                print(f'[grounding] {job["id"]} {arm} success={success} t={t}', flush=True)
        finally:
            env.close()


if __name__ == '__main__':
    try:
        main()
    except InterruptedError as error:
        print(str(error), flush=True)

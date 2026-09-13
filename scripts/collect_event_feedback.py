#!/usr/bin/env python3
"""Collect full event-conditioned Cosmos rollouts, separately from frozen t72 campaigns."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import time

import numpy as np

from event_feedback import EventConfig, METHODS, run_control_loop
from p5_repeat_feedback import atomic_json, digest
from p5_candidate_replication import atomic_npz, signal_arrays


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True, help='JSON list: suite, task_id, init_state_id, rollout_seed')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--method', choices=METHODS, default='requery')
    parser.add_argument('--timing', choices=('event', 'shadow', 'none', 'fixed'), default='event')
    parser.add_argument('--fixed-step', type=int, help='Only explicit historical control, never event input')
    parser.add_argument('--parameters', type=Path, required=True, help='Frozen EventConfig JSON, no implicit sweep')
    parser.add_argument('--localizer', type=Path)
    parser.add_argument('--trigger', type=Path)
    parser.add_argument('--mask', type=Path)
    parser.add_argument('--samples', type=int, default=4)
    parser.add_argument('--hours', type=float, default=9.)
    parser.add_argument('--validate-only', action='store_true', help='Validate configuration without loading GPU models')
    args = parser.parse_args()
    if (args.timing == 'fixed') != (args.fixed_step is not None):
        parser.error('--fixed-step is required only with --timing fixed')
    if (args.localizer is None) != (args.trigger is None):
        parser.error('--localizer and --trigger must be provided together')
    if args.method != 'requery' and not all((args.localizer, args.trigger, args.mask)):
        parser.error('Recovery methods require --localizer, --trigger and --mask; no ungrounded release fallback')
    if args.mask and not args.localizer:
        parser.error('--mask requires a localizer')
    if args.samples < 1 or not np.isfinite(args.hours) or args.hours <= 0:
        parser.error('Invalid sample count or deadline')
    return args


def main():
    args = arguments()
    config = EventConfig(**json.loads(args.parameters.read_text()))
    if config.generated_horizon != 16:
        raise ValueError('Frozen Cosmos checkpoint generates 16 actions')
    if args.fixed_step is not None and not 0 < args.fixed_step < config.max_steps:
        raise ValueError('Fixed control must be inside episode budget')
    cases = json.loads(args.cases.read_text())
    if not isinstance(cases, list) or not cases:
        raise ValueError('Empty/non-list case manifest')
    identities = set()
    for case in cases:
        key = (case['suite'], case['task_id'], case['init_state_id'], case['rollout_seed'])
        if key in identities:
            raise ValueError('Duplicate rollout identity')
        if not isinstance(key[0], str) or not key[0].replace('_', '').isalnum():
            raise ValueError('Invalid suite name')
        if any(type(x) is not int or x < 0 for x in key[1:]):
            raise ValueError('Invalid task/init/seed identity')
        if case['rollout_seed'] + config.max_steps * 1000 + args.samples >= 2 ** 32:
            raise ValueError('Sampling seeds exceed NumPy range')
        identities.add(key)
    dependencies = ['event_feedback.py', 'event_feedback_libero.py', 'collect_event_feedback.py',
        'collect_counterfactual_feedback.py', 'collect_recovery_proposals.py',
        'collect_online_perception_regrasp.py', 'perception_regrasp.py',
        'perception_regrasp_trigger.py', 'probe_repair.py', 'grounded_probe.py', 'observation_contract.py',
        'calibrate_event_feedback.py']
    metadata = dict(config=asdict(config), method=args.method, timing=args.timing,
        fixed_step=args.fixed_step, samples=args.samples, cases=cases,
        parameters_sha256=digest(args.parameters), cases_sha256=digest(args.cases),
        scripts={name: digest(Path(__file__).parent / name) for name in dependencies},
        seed_scheme='rollout_seed + physical_action_index * 1000 + sample_index',
        status='experimental_uncalibrated_thresholds', simulator_labels_online=False,
        perception_paths={k: str(getattr(args, k)) if getattr(args, k) else None
                          for k in ('localizer', 'trigger', 'mask')})
    metadata['perception_hashes'] = {}
    for name in ('localizer', 'trigger', 'mask'):
        path = getattr(args, name)
        if path is not None:
            if not path.exists():
                raise ValueError('Missing perception artifact: ' + str(path))
            paths = [path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
            metadata['perception_hashes'].update({str(p.resolve()): digest(p) for p in paths})
    calibration_path = args.parameters.with_suffix('.calibration.json')
    if calibration_path.exists():
        from calibrate_event_feedback import group_id
        calibration = json.loads(calibration_path.read_text())
        if calibration['parameters_sha256'] != digest(args.parameters):
            raise ValueError('Changed calibrated parameters')
        if set(map(group_id, cases)) & set(calibration['calibration_groups']):
            raise ValueError('Evaluation init groups overlap calibration; choose disjoint groups')
        if calibration['source_configuration']['samples'] != args.samples:
            raise ValueError('Sample count differs from calibration')
        if calibration['source_configuration']['perception_hashes'] != metadata['perception_hashes']:
            raise ValueError('Perception artifacts differ from calibration')
        metadata.update(calibration=calibration, calibration_sha256=digest(calibration_path),
                        status=calibration['status'])
    if args.validate_only:
        print(json.dumps(dict(valid=True, cases=len(cases), method=args.method,
                              timing=args.timing, status=metadata['status']), indent=2))
        return
    import collect_counterfactual_feedback as c
    import collect_online_perception_regrasp as p
    import collect_recovery_proposals as r
    from event_feedback_libero import PassiveMonitor, perform_intervention
    from collect_feedback_controls import input_hashes
    from perception_regrasp import FrozenPatchLocalizer
    from perception_regrasp_trigger import load_trigger_artifact
    from grounded_probe import FrozenObjectMask
    from robosuite import macros
    import imageio.v2 as imageio
    import cosmos_policy
    # Pin the actual policy source, not only the wrapper code.
    runtime = Path(cosmos_policy.__file__).parent
    metadata['runtime_hashes'] = {str(f.relative_to(runtime)): digest(f) for f in sorted(runtime.rglob('*.py'))}
    if 'calibration' in metadata:
        source = metadata['calibration']['source_configuration']
        if source['runtime_hashes'] != metadata['runtime_hashes'] or source['scripts'] != metadata['scripts']:
            raise ValueError('Runtime or implementation changed since calibration')
    import os
    metadata['libero_paths'] = {k: os.environ.get(k) for k in
                              ('LIBERO_BDDL_FILES_PATH', 'LIBERO_INIT_STATES_PATH')}
    metadata['libero_hashes'] = {}
    for root in metadata['libero_paths'].values():
        if not root:
            raise ValueError('Use cosmos_env_libero_pro.sh with explicit benchmark asset roots')
        for suite_name in {case['suite'] for case in cases}:
            parent = Path(root) / suite_name
            if not parent.is_dir():
                raise ValueError('Missing suite assets: ' + str(parent))
            metadata['libero_hashes'].update({str(f.resolve()): digest(f) for f in sorted(parent.rglob('*')) if f.is_file()})
    metadata = json.loads(json.dumps(metadata))
    args.output.mkdir(parents=True, exist_ok=True)
    freeze = args.output / 'config.json'
    if freeze.exists() and json.loads(freeze.read_text()) != metadata:
        raise ValueError('Changed frozen run; choose a NEW output directory')
    atomic_json(freeze, metadata)
    stopped = False
    deadline = time.monotonic() + args.hours * 3600
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def check():
        if stopped or time.monotonic() >= deadline:
            raise InterruptedError('Deadline/requested stop; only committed episodes are resumed')
    if args.localizer and macros.IMAGE_CONVENTION != 'opengl':
        raise ValueError('Frozen localizer requires native OpenGL RGB')
    cfg = c.default_policy_config(cases[0]['suite'], seed=0, num_open_loop_steps=config.execution_horizon,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    c.validate_config(cfg)
    c.set_seed_everywhere(0)
    c.init_t5_text_embeddings_cache(cfg.t5_text_embeddings_path)
    stats = c.load_dataset_stats(cfg.dataset_stats_path)
    c.prewarm_libero_renderer(cfg)
    model, mc = c.get_model(cfg)
    if config.generated_horizon != mc.dataloader_train.dataset.chunk_size:
        raise ValueError('Checkpoint action horizon mismatch')
    localizer = FrozenPatchLocalizer(args.localizer, device='cuda') if args.localizer else None
    artifact = load_trigger_artifact(args.trigger) if args.trigger else None
    masker = FrozenObjectMask(args.mask) if args.mask else None
    resize = c.get_image_resize_size(cfg.model_family)
    for case in cases:
        check()
        name = f'{case["suite"]}_t{case["task_id"]}_i{case["init_state_id"]}_s{case["rollout_seed"]}'
        path = args.output / (name + '.json')
        if path.exists():
            old = json.loads(path.read_text())
            if any(digest(path.with_suffix(ext)) != old[key] for ext, key in
                   (('.npz', 'npz_sha256'), ('.mp4', 'video_sha256'))):
                raise ValueError('Changed committed episode: ' + name)
            continue
        cfg.task_suite_name = case['suite']
        suite = c.benchmark.get_benchmark_dict()[case['suite']]()
        task = suite.get_task(case['task_id'])
        description = str(task.language)
        c.set_seed_everywhere(case['rollout_seed'])
        env, _ = c.get_libero_env(task, cfg.model_family, resolution=cfg.env_img_res)
        started = time.monotonic()
        try:
            states = c.get_task_init_states_compat(suite, case['task_id'], task)
            if case['init_state_id'] >= len(states):
                raise ValueError('Init index outside official benchmark assets')
            env.reset()
            obs = env.set_init_state(states[case['init_state_id']])
            for _ in range(10):
                obs, _, done, _ = env.step(c.get_libero_dummy_action(cfg.model_family))
                if done:
                    raise ValueError('Success during settle')
            tracker = c.SafetySignalTracker(env, obs)
            frames, executed = [], []
            def frame(o):
                return np.concatenate([c.get_libero_image(o, flip_images=cfg.flip_images),
                    c.get_libero_wrist_image(o, flip_images=cfg.flip_images)], axis=1)
            frames.append(frame(obs))
            initial_hashes = input_hashes(c, cfg, obs, resize)
            original_step = env.step
            def record(action):
                check()
                if len(executed) >= config.max_steps:
                    raise ValueError('Physical action budget exceeded')
                result = original_step(action)
                executed.append(np.asarray(action, dtype=np.float32).copy())
                frames.append(frame(result[0]))
                return result
            env.step = record
            monitor = PassiveMonitor(env, description, config, localizer, artifact, masker)
            monitor_calls, monitor_seconds, sampling_seconds = 0, 0., 0.
            class TimedMonitor:
                @property
                def diagnostics(self):
                    return monitor.diagnostics

                def __call__(self, o, recent):
                    nonlocal monitor_calls, monitor_seconds
                    before = time.monotonic()
                    result = monitor(o, recent)
                    monitor_calls += 1
                    monitor_seconds += time.monotonic() - before
                    return result

            def policy(o, t, q):
                nonlocal sampling_seconds
                check()
                before = time.monotonic()
                seeds = tuple(case['rollout_seed'] + t * 1000 + i for i in range(args.samples))
                samples, metrics = c._sample_candidates(cfg, model, stats, o, description,
                    seeds, resize, prediction_mode='parallel')
                sampling_seconds += time.monotonic() - before
                return (np.stack([s['actions'] for s in samples]),
                    np.asarray([s['value_prediction'] for s in samples]),
                    dict(seeds=seeds, uncertainty=metrics, input_hashes=input_hashes(c, cfg, o, resize)))
            def step(action):
                o, success, _, _ = c._execute_actions(env, None, np.asarray([action]), tracker,
                    absolute_t=len(executed), max_t=config.max_steps)
                return o, success
            def intervene(kind, o, t, budget):
                return perform_intervention(kind, o, t, budget, c=c, p=p, r=r, env=env,
                    tracker=tracker, monitor=monitor, localizer=localizer, artifact=artifact,
                    description=description, cfg=cfg, executed=executed)
            try:
                result = run_control_loop(obs, policy=policy, step=step, monitor=TimedMonitor(),
                    intervene=intervene, config=config, method=args.method, timing=args.timing,
                    fixed_step=args.fixed_step, check=check)
            finally:
                env.step = original_step
            np.testing.assert_array_equal(result.pop('actions'), np.asarray(executed))
            if len(frames) != result['final_t'] + 1:
                raise ValueError('Video frame accounting mismatch')
            outcome = c._terminal_outcome(tracker, success=result['success'], final_t=result['final_t'],
                max_t=config.max_steps, continuation_queries=result['model_calls'])
            outcome.update(result, case=case, method=args.method, timing=args.timing,
                task_description=description, elapsed_seconds=time.monotonic() - started,
                initial_input_hashes=initial_hashes, config_sha256=digest(freeze),
                simulator_labels_online=False, video_start_t=0, video_frames=len(frames),
                passive_monitor_calls=monitor_calls, passive_monitor_seconds=monitor_seconds,
                model_sampling_seconds=sampling_seconds,
                monitor_cost_scope='scheduled passive checks; verification inside recovery included in wall time',
                safety_signal_scope='whole_episode_diagnostics_only')
            atomic_npz(path.with_suffix('.npz'), executed_actions=np.asarray(executed, dtype=np.float32),
                frame_t=np.arange(result['final_t'] + 1), **signal_arrays(tracker.records))
            temporary = path.with_suffix('.tmp.mp4')
            with imageio.get_writer(temporary, fps=20, codec='libx264', pixelformat='yuv420p', macro_block_size=1) as writer:
                for im in frames:
                    writer.append_data(im)
            temporary.replace(path.with_suffix('.mp4'))
            outcome.update(npz_sha256=digest(path.with_suffix('.npz')), video_sha256=digest(path.with_suffix('.mp4')))
            atomic_json(path, outcome)
            print(f'[event-feedback] {name} success={result["success"]} events={len(result["events"])}', flush=True)
        finally:
            env.close()


if __name__ == '__main__':
    main()

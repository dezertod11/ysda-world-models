#!/usr/bin/env python3
"""Model-free audit of saved-prefix physics and cross-process rendering."""
import argparse
import json
from pathlib import Path

import numpy as np

from p5_repeat_feedback import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--pool-id', default='pool_00')
    args = parser.parse_args()
    import collect_counterfactual_feedback as c
    from libero_runtime_snapshot import runtime_snapshot_from_arrays

    cfg = json.loads((args.campaign/'config.json').read_text())
    pool = next(p for p in cfg['pools'] if p['id'] == args.pool_id)
    with np.load(pool['sidecar'], allow_pickle=False) as source:
        data = {k: source[k].copy() for k in source.files}
    snapshot = runtime_snapshot_from_arrays(data)
    policy = c.default_policy_config(pool['suite'], seed=0, num_open_loop_steps=16,
        num_denoising_steps_action=5, prediction_mode='parallel', num_denoising_steps_future_state=1,
        num_denoising_steps_value=1, num_future_state_samples=1, num_value_samples=1,
        value_ensemble_aggregation_scheme='average')
    task = c.benchmark.get_benchmark_dict()[pool['suite']]().get_task(pool['task_id'])
    env, description = c.get_libero_env(task, policy.model_family, resolution=policy.env_img_res)
    result = dict(pool_id=pool['id'], policy_language=str(task.language),
        bddl_language=description, images=[], endpoint_errors=[])
    try:
        for i, actions in enumerate(data['candidate_actions']):
            obs = c._restore_snapshot(env, snapshot)
            images = []
            for kind, get in [('agentview', c.get_libero_image), ('wrist', c.get_libero_wrist_image)]:
                now = get(obs, flip_images=policy.flip_images)
                old = data['current_'+kind]
                diff = now.astype(float)-old.astype(float)
                images.append(dict(kind=kind, mse=float(np.mean(diff**2)),
                    max=float(np.abs(diff).max()), changed_fraction=float(np.mean(diff != 0))))
            result['images'].append(images)
            tracker = c.SafetySignalTracker(env, obs)
            c._execute_actions(env, obs, actions, tracker, absolute_t=pool['t'], max_t=pool['t']+16)
            result['endpoint_errors'].append(float(np.abs(np.asarray(env.get_sim_state())
                -data['candidate_endpoint_states'][i]).max()))
    finally:
        env.close()
    atomic_json(args.campaign/('render_probe_'+pool['id']+'.json'), result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

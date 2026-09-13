"""Frozen schedules and matched-window actions for the P5 suffix experiment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

SUFFIX_OFFSETS = (100_000, 200_000, 300_000)
MODES = ('open16', 'fresh8', 'stale8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_digest(array):
    value = np.ascontiguousarray(array)
    return hashlib.sha256(str(value.dtype).encode()+str(value.shape).encode()+value.tobytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    def convert(x):
        if isinstance(x, np.generic): return x.item()
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, Path): return str(x)
        raise TypeError(type(x).__name__)
    temporary.write_text(json.dumps(value, indent=2, default=convert)+'\n')
    temporary.replace(path)


def schedule(selected, smoke=False):
    if not 0 <= selected < 8:
        raise ValueError('Expected a K8 selected index')
    if smoke:
        return [(0, selected, mode) for mode in MODES]
    rows = []
    for repeat in range(3):
        rows.extend((repeat, i, 'open16') for i in range(8))
        # Alternate intervention order without using any outcomes.
        arms = ('fresh8', 'stale8') if repeat % 2 == 0 else ('stale8', 'fresh8')
        rows.extend((repeat, selected, mode) for mode in arms)
    return rows


def suffix_seed(original, repeat):
    return int(original) + SUFFIX_OFFSETS[repeat]


def replacement_window(actions, mode):
    actions = np.asarray(actions)
    if actions.shape != (16, 7) or not np.isfinite(actions).all():
        raise ValueError('Expected finite H16 x 7 actions')
    if mode == 'fresh8': return actions[:8]
    if mode == 'stale8': return actions[8:16]
    raise ValueError(mode)


def check_saved_pool(values, row_values):
    actions = np.asarray(values['candidate_actions'])
    if actions.shape != (8, 16, 7) or not np.isfinite(actions).all():
        raise ValueError('Invalid saved K8/H16 action pool')
    saved = np.asarray(values['candidate_values'])
    np.testing.assert_allclose(saved, row_values, rtol=0, atol=1e-7)
    selected = int(values['selected_max_value_idx'])
    if selected != int(np.argmax(row_values)):
        raise ValueError('Saved max-value selection differs from the original trace')
    return selected


def source_instruction(task_language, saved_description):
    """The source collector conditioned on task.language, not the BDDL paraphrase."""
    description = str(task_language)
    if description != saved_description:
        raise ValueError('Source policy task language changed')
    return description


def saved_policy_observation(obs, data, flip_images):
    """Use archived real measurements, not refreshed observable caches."""
    result = dict(obs)
    for key, source in [('agentview_image', 'current_agentview'),
                        ('robot0_eye_in_hand_image', 'current_wrist')]:
        value = np.asarray(data[source])
        if value.dtype != np.uint8 or value.shape != np.asarray(obs[key]).shape:
            raise ValueError('Invalid archived camera input')
        result[key] = (np.flipud(value) if flip_images else value).copy()
    proprio = np.asarray(data['current_proprio'],dtype=np.float32)
    if proprio.shape != (9,) or not np.isfinite(proprio).all():
        raise ValueError('Invalid archived proprio input')
    for key, value in [('robot0_gripper_qpos',proprio[:2]),('robot0_eef_pos',proprio[2:5]),
                       ('robot0_eef_quat',proprio[5:9])]:
        result[key] = value.copy()
    return result

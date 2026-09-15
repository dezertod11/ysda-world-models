"""Real CPU simulation regression tests; no policy or GPU required."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "LIBERO-PRO")]
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("MUJOCO_GL", "glfw")
os.environ.setdefault("LIBERO_CONFIG_PATH", str(ROOT / ".runtime/libero_pro"))

import numpy as np
import pytest

import libero_runtime_snapshot as legacy
import runtime_snapshot as v2
from event_feedback import EventConfig
from event_feedback_libero import PassiveMonitor


@pytest.fixture(scope="module")
def fixture():
    from libero.libero.envs.env_wrapper import ControlEnv
    case = ROOT / "experiments/campaigns/p3_benchmark_seed_replication_20260915_s1/main/environment__t3_i2"
    with np.load(case / "start.npz", allow_pickle=False) as z:
        old = legacy.runtime_snapshot_from_arrays(z)
    with np.load(case / "max_value_h16.npz", allow_pickle=False) as z:
        actions = z["executed_actions"].copy()
    bddl = ROOT / ".runtime/trajectory_consensus_20260908_environment/bddl_files/libero_object_env/pick_up_the_bbq_sauce_and_place_it_in_the_basket.bddl"
    render = os.environ.get("REPLAY_TEST_RGB") == "1"
    env = ControlEnv(bddl_file_name=str(bddl), use_camera_obs=render,
                     has_offscreen_renderer=render, has_renderer=False,
                     camera_heights=256, camera_widths=256)
    try:
        if render:
            from OpenGL import GL
            renderer = GL.glGetString(GL.GL_RENDERER).decode()
            assert "llvmpipe" in renderer.lower(), renderer
        np.random.seed(52320000)
        env.reset()
        env.env.sim.reset()
        obs = legacy.restore_libero_runtime_state(env, old, reset_env=False)
        snapshot = v2.capture_libero_runtime_state(env)
        yield env, obs, snapshot, actions
    finally:
        env.close()


def advance(env, actions, monitor=False):
    watched = PassiveMonitor(env, "pick up the bbq sauce and place it in the basket", EventConfig())
    states, observations, goals = [], [], []
    for i, action in enumerate(actions):
        obs, _, done, _ = env.step(np.asarray(action, dtype=np.float32).tolist())
        states.append(v2._integration(env))
        observations.append({k: np.asarray(v).copy() for k, v in obs.items()})
        goals.append(done)
        if monitor and (i + 1) % 4 == 0:
            watched(obs, actions[max(0, i - 3):i + 1])
    return np.asarray(states), observations, goals


def assert_trace_equal(a, b):
    np.testing.assert_array_equal(a[0], b[0])
    assert a[2] == b[2]
    for oa, ob in zip(a[1], b[1]):
        assert oa.keys() == ob.keys()
        for key in oa:
            np.testing.assert_array_equal(oa[key], ob[key], err_msg=key)


def test_npz_roundtrip(fixture, tmp_path):
    _, _, snapshot, _ = fixture
    path = tmp_path / "start.npz"
    arrays = v2.runtime_snapshot_arrays(snapshot)
    np.savez_compressed(path, **arrays)
    with np.load(path, allow_pickle=False) as z:
        loaded = v2.runtime_snapshot_from_arrays(z)
    restored_arrays = v2.runtime_snapshot_arrays(loaded)
    assert arrays.keys() == restored_arrays.keys()
    for key in arrays:
        np.testing.assert_array_equal(arrays[key], restored_arrays[key])


def test_reject_legacy(fixture):
    env, _, snapshot, _ = fixture
    with pytest.raises(ValueError, match="v2 required"):
        v2.runtime_snapshot_from_arrays(legacy.runtime_snapshot_arrays(snapshot))
    bad = dict(snapshot)
    bad.pop("schema_version")
    before = v2._integration(env)
    with pytest.raises(ValueError, match="v2 required"):
        v2.restore_libero_runtime_state(env, bad)
    np.testing.assert_array_equal(before, v2._integration(env))


@pytest.mark.parametrize("key,value", [("mujoco_version", "wrong"), ("integration_spec", 0)])
def test_reject_incompatible(fixture, key, value):
    env, _, snapshot, _ = fixture
    bad = dict(snapshot, **{key: value})
    with pytest.raises(ValueError, match="mismatch"):
        v2.restore_libero_runtime_state(env, bad)


@pytest.mark.parametrize("t", [0, 48, 80, 160])
def test_continuation_and_different_reset_history(fixture, tmp_path, t):
    env, _, initial, actions = fixture
    v2.restore_libero_runtime_state(env, initial)
    advance(env, actions[:t])
    snapshot = v2.capture_libero_runtime_state(env)
    np.savez_compressed(tmp_path / "snapshot.npz", **v2.runtime_snapshot_arrays(snapshot))
    expected = advance(env, actions[t:])
    with np.load(tmp_path / "snapshot.npz", allow_pickle=False) as z:
        snapshot = v2.runtime_snapshot_from_arrays(z)
    for seed in [100, 98765]:
        np.random.seed(seed)
        v2.restore_libero_runtime_state(env, snapshot)
        # Compare all observations including both RGB views when enabled.
        assert_trace_equal(expected, advance(env, actions[t:], monitor=True))


def test_soft_restore(fixture):
    env, _, snapshot, actions = fixture
    v2.restore_libero_runtime_state(env, snapshot)
    expected = advance(env, actions[:16])
    v2.restore_libero_runtime_state(env, snapshot, reset_env=False)
    assert_trace_equal(expected, advance(env, actions[:16]))


def test_initial_observations_exact(fixture):
    env, obs, snapshot, _ = fixture
    restored = v2.restore_libero_runtime_state(env, snapshot)
    for key in obs:
        np.testing.assert_array_equal(obs[key], restored[key], err_msg=key)

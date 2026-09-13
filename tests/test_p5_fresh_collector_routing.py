"""Exercise the frozen collector with timestamped sensor data and a toy simulator.

No CUDA/model imports: the collector and its execute/continue loops are real;
only the environment, model, tracker and video backend are test doubles.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import p5_repeat_feedback as helpers


ROOT = Path(__file__).resolve().parents[1]


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {f.name for f in functions} == set(names)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *functions], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)


@pytest.mark.parametrize("start,success_after", [(0, 32), (48, 32), (0, 6), (48, 12)])
def test_real_collector_routes_fresh_sensors_and_correct_action_windows(monkeypatch, tmp_path, start, success_after):
    class Env:
        def __init__(self):
            self.t = start

        def observation(self):
            return {
                "agentview_image": np.full((4, 4, 3), self.t, dtype=np.uint8),
                "robot0_eye_in_hand_image": np.full((4, 4, 3), self.t, dtype=np.uint8),
                "robot0_gripper_qpos": np.full(2, self.t, dtype=np.float32),
                "robot0_eef_pos": np.full(3, self.t, dtype=np.float32),
                "robot0_eef_quat": np.full(4, self.t, dtype=np.float32),
            }

        def get_sim_state(self):
            return np.array([self.t], dtype=np.float64)

        def check_success(self):
            return self.t >= start + success_after

        def step(self, action):
            self.t += 1
            return self.observation(), 0, self.check_success(), {}

        def close(self):
            pass

    env = Env()
    calls = []
    description = "pick up the alphabet soup and place it in the basket"

    def restore(environment, snapshot):
        environment.t = int(snapshot["sim_state"][0])
        return environment.observation()

    def sample(cfg, model, stats, obs, task_description, seeds, resize_size, **kwargs):
        assert task_description == description
        stamp = int(obs["robot0_eef_pos"][0])
        for field in env.observation():
            np.testing.assert_array_equal(obs[field], np.full_like(obs[field], stamp))
        calls.append(dict(physical_t=env.t, observed_t=stamp, seeds=seeds))
        actions = (np.arange(112).reshape(16, 7) / 1000 + stamp / 1000).astype(np.float32)
        return [dict(actions=actions)], {}

    cfg = SimpleNamespace(chunk_size=16, model_family="cosmos", env_img_res=4,
                          seed=0, flip_images=True, t5_text_embeddings_path="unused",
                          dataset_stats_path="unused", num_open_loop_steps=16)
    shared = {"np": np, "_sample_candidates": sample,
              "_select_max_value": lambda samples, **kwargs: (0, {})}
    load_functions(ROOT / "scripts/collect_counterfactual_feedback.py",
                   ["_execute_actions", "_continue_to_terminal"], shared)
    noop = lambda *args, **kwargs: None
    tracker = lambda *args: SimpleNamespace(observe=noop)
    c = SimpleNamespace(
        default_policy_config=lambda *args, **kwargs: cfg, validate_config=noop,
        set_seed_everywhere=noop, init_t5_text_embeddings_cache=noop,
        load_dataset_stats=lambda *args: {}, prewarm_libero_renderer=noop,
        get_model=lambda *args: (object(), SimpleNamespace(dataloader_train=SimpleNamespace(
            dataset=SimpleNamespace(chunk_size=16)))), get_image_resize_size=lambda *args: 4,
        benchmark=SimpleNamespace(get_benchmark_dict=lambda: {"toy": lambda: SimpleNamespace(
            get_task=lambda idx: SimpleNamespace(language=description))}),
        get_libero_env=lambda *args, **kwargs: (env, description),
        _restore_snapshot=restore, _copy_observation=copy.deepcopy,
        get_libero_image=lambda obs, **kwargs: np.flipud(obs["agentview_image"]),
        get_libero_wrist_image=lambda obs, **kwargs: np.flipud(obs["robot0_eye_in_hand_image"]),
        proprio_from_libero_obs=lambda obs: np.concatenate([
            obs["robot0_gripper_qpos"], obs["robot0_eef_pos"], obs["robot0_eef_quat"]]),
        SafetySignalTracker=tracker, _sample_candidates=sample,
        _execute_actions=shared["_execute_actions"], _continue_to_terminal=shared["_continue_to_terminal"],
        _terminal_outcome=lambda tracker, **kwargs: dict(
            terminal_success=kwargs["success"], terminal_final_t=kwargs["final_t"]),
    )

    class Writer:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def append_data(self, frame):
            pass

    resident = SimpleNamespace(
        CPUQueue=lambda **kwargs: SimpleNamespace(close=noop, executor=SimpleNamespace(shutdown=noop)),
        AsyncImageIO=lambda *args: SimpleNamespace(get_writer=lambda *args, **kwargs: Writer()),
    )
    monkeypatch.setitem(sys.modules, "collect_counterfactual_feedback", c)
    monkeypatch.setitem(sys.modules, "libero_resident", resident)
    monkeypatch.setitem(sys.modules, "p5_repeat_feedback", helpers)
    monkeypatch.setitem(sys.modules, "libero_runtime_snapshot", SimpleNamespace(
        runtime_snapshot_from_arrays=lambda data: dict(sim_state=data["sim_state"])))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "test_double")
    spec = importlib.util.spec_from_file_location("frozen_collector_test", ROOT / "scripts/collect_p5_repeat_feedback.py")
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    monkeypatch.setattr(collector.signal, "signal", noop)

    sidecar = tmp_path / "saved.npz"
    saved_actions = np.arange(8 * 16 * 7, dtype=np.float32).reshape(8, 16, 7) / 10000
    np.savez(sidecar, sim_state=np.array([start]), candidate_actions=saved_actions,
             candidate_endpoint_states=np.full((8, 1), start + min(16, success_after)),
             candidate_values=np.arange(8), current_agentview=env.observation()["agentview_image"],
             current_wrist=env.observation()["robot0_eye_in_hand_image"],
             current_proprio=np.full(9, start, dtype=np.float32))
    pool = dict(id="pool", suite="toy", task_id=0, init_state_id=0, selected=7,
                case_id="case", query_idx=start // 16, t=start, factor="toy",
                rollout_seed=123, sidecar=str(sidecar), sidecar_sha256=helpers.digest(sidecar),
                task_description=description)
    batch_path = tmp_path / "batch.json"
    helpers.atomic_json(batch_path, dict(pools=[pool], output=str(tmp_path / "runs"),
                                        deadline_epoch=collector.time.time() + 60, smoke=True))
    monkeypatch.setattr(sys, "argv", ["collector", "--batch", str(batch_path)])
    collector.main()

    requeries = [call for call in calls if call["physical_t"] == start + 8]
    if success_after <= 8:
        assert not calls
    else:
        assert [call["observed_t"] for call in requeries] == [start + 8, start]
        assert requeries[0]["seeds"] == requeries[1]["seeds"]
        assert len(requeries[0]["seeds"]) == 1
    suffixes = [call for call in calls if call["physical_t"] == start + 16]
    if success_after > 16:
        assert len(suffixes) == 3
        assert len({call["seeds"] for call in suffixes}) == 1
        assert all(call["observed_t"] == start + 16 for call in suffixes)
    for mode in helpers.MODES:
        stem = tmp_path / "runs/pool" / f"r0_c7_{mode}"
        outcome = json.loads(stem.with_suffix(".json").read_text())
        assert outcome["terminal_final_t"] == start + success_after
        assert outcome["terminal_success"]
        with np.load(stem.with_suffix(".npz")) as arrays:
            actions = arrays["executed_actions"]
            np.testing.assert_array_equal(actions[:min(8, success_after)], saved_actions[7, :min(8, success_after)])
            if mode != "open16" and success_after > 8:
                new = helpers.replacement_window(arrays["requery_actions"], mode)
                np.testing.assert_array_equal(actions[8:16], new[:min(8, success_after - 8)])
            else:
                assert "requery_actions" not in arrays
            assert len(arrays["frame_t"]) == len(actions) + 1 == success_after + 1

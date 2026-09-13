import copy
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading

import numpy as np
import pytest

from scripts import run_libero_experiment_campaign as legacy
from scripts.libero_resident import (AsyncImageIO, CPUQueue, CompatibleQueue, ResidentModel,
                                    TorchRNG, compatibility_key, requests_for_job)
from scripts.run_libero_resident_campaign import batch_payload

ROOT = Path(__file__).resolve().parents[1]


def job():
    config = json.loads((ROOT / "experiments/campaigns/consensus_references_20260909_valid199/config.json").read_text())
    jobs = legacy.expand_jobs(config["profiles"]["references"], config["defaults"])
    return copy.deepcopy(next(j for j in jobs if j["name"] == "position_x0_3_t3_raw_medoid"))


def test_compatible_queue_is_bounded_and_never_duplicates():
    jobs = [dict(i=i, group=i % 3) for i in range(30)]
    q = CompatibleQueue(jobs, lambda j: j["group"], 4)
    result = []
    while not q.empty():
        batch = q.take()
        assert len(batch) <= 4 and len({j['group'] for j in batch}) == 1
        result.extend(batch)
    assert sorted(j['i'] for j in result) == list(range(30))
    assert q.take() == []


def test_batch_keeps_variant_and_model_settings_separate(tmp_path):
    first = job()
    _, env, _ = legacy.build_job(first, "parity", tmp_path)
    second = dict(first, task_ids="4", base_seed=12345, strategy_lambdas="keystone_cluster_medoid:0.0", name="other")
    _, env2, _ = legacy.build_job(second, "parity", tmp_path)
    assert compatibility_key(first, env) == compatibility_key(second, env2)
    for changed in [dict(first, position_level="y0.3"), dict(first, num_denoising_steps_action=10)]:
        _, other, _ = legacy.build_job(changed, "parity", tmp_path)
        assert compatibility_key(first, env) != compatibility_key(changed, other)
        with pytest.raises(ValueError, match="one runtime"):
            batch_payload([first, changed], "parity", tmp_path, "2")


def test_rejects_unimplemented_collector_hooks(tmp_path):
    first = dict(job(), record_temporal_overlap=True)
    _, env, _ = legacy.build_job(first, "test", tmp_path)
    with pytest.raises(ValueError, match="without temporal"):
        requests_for_job(first, env)


@dataclass
class Config:
    seed: int = 1
    task_suite_name: str = "test"
    checkpoint: str = "fixed"


def test_cache_restores_loader_side_effects_and_rejects_model_changes():
    import random
    rng = TorchRNG()
    original = rng.capture()
    try:
        def load(cfg):
            random.seed(0)
            np.random.seed(0)
            random.random()
            return object(), object()
        cache = ResidentModel(load, rng)
        model = cache(Config())
        expected = (random.random(), np.random.rand())
        random.seed(999)
        np.random.seed(999)
        assert cache(Config(seed=8, task_suite_name="new")) is model
        assert (random.random(), np.random.rand()) == expected
        assert cache.loads == 1 and cache.hits == 1
        with pytest.raises(ValueError, match="Incompatible"):
            cache(Config(checkpoint="other"))
    finally:
        rng.restore(original)


def test_cpu_artifacts_are_ordered_and_errors_propagate():
    cpu = CPUQueue(2)
    seen = []
    a = cpu.submit(seen.append, "video")
    def mark():
        a.result()
        seen.append("marker")
    cpu.submit(mark)
    cpu.close()
    assert seen == ["video", "marker"]
    cpu = CPUQueue()
    def fail():
        raise ValueError("encoder failed")
    cpu.submit(fail)
    with pytest.raises(ValueError, match="encoder"):
        cpu.close()


def test_video_frames_are_durable_before_encoding_and_recoverable(tmp_path):
    class Deferred:
        def submit(self, fn):
            self.fn = fn
    class FakeImageIO:
        def get_writer(self, path, **kwargs):
            class Writer:
                def __enter__(self):
                    self.frames = []
                    return self
                def append_data(self, frame):
                    self.frames.append(frame.copy())
                def __exit__(self, *args):
                    Path(path).write_bytes(np.asarray(self.frames).tobytes())
            return Writer()
    deferred = Deferred()
    imageio = AsyncImageIO(FakeImageIO(), deferred)
    path = tmp_path / "episode.mp4"
    frame = np.ones((3, 4, 3), dtype=np.uint8)
    with imageio.get_writer(path, fps=30) as writer:
        writer.append_data(frame)
        frame[:] = 0
    assert not path.exists()
    assert path.with_suffix('.frames.npy').exists()
    imageio.recover(path, fps=30)
    deferred.fn()
    assert path.read_bytes() == bytes([1]) * 36
    assert not path.with_suffix('.frames.npy').exists()


def test_adapter_matches_actual_legacy_shell_arguments(tmp_path, monkeypatch):
    """Use the unchanged shell scripts as the argv oracle, without CUDA imports."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ['run_libero_pro_planning_strategy_grid.sh', 'run_libero_pro_paired_prediction_collect.sh']:
        path = scripts / name
        path.write_text((ROOT / "scripts" / name).read_text())
        path.chmod(0o755)
    (scripts / "cosmos_env_libero_pro.sh").write_text("export COSMOS_REPO=\"$FAKE_ROOT\"\nexport COSMOS_VENV=\"$FAKE_ROOT\"\nexport PATH=\"$FAKE_ROOT/bin:$PATH\"\n")
    (tmp_path / "bin").mkdir()
    python = tmp_path / "bin/python"
    capture = tmp_path / "capture.py"
    capture.write_text('import json, os, sys\nwith open(os.environ["ARGV_FILE"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
    python.write_text(f'#!/bin/bash\nexec "{sys.executable}" "{capture}" "$@"\n')
    python.chmod(0o755)
    first = job()
    _, env, _ = legacy.build_job(first, "shell_oracle", tmp_path)
    import os
    subprocess.run(['bash', str(scripts / 'run_libero_pro_planning_strategy_grid.sh')],
        env=dict(os.environ, **env, FAKE_ROOT=str(tmp_path), ARGV_FILE=str(tmp_path/'argv.jsonl')),
        check=True, capture_output=True, text=True)
    argv = json.loads((tmp_path/'argv.jsonl').read_text().splitlines()[0])
    assert argv[:3] == ['-m', 'cosmos_policy.experiments.robot.libero.uncertainty_comparison', 'collect-paired']
    parsed = {}
    index = 3
    while index < len(argv):
        name = argv[index].removeprefix('--').replace('-', '_')
        if index+1 == len(argv) or argv[index+1].startswith('--'):
            parsed[name] = True
            index += 1
        else:
            parsed[name] = argv[index+1]
            index += 2
    request, = requests_for_job(first, env)
    renames = {'value_ensemble_aggregation': 'value_ensemble_aggregation_scheme',
               'planning_frozen_ranker_model': 'planning_frozen_ranker_model_path',
               'planning_terminal_critic_model': 'planning_terminal_critic_model_path'}
    for key, value in parsed.items():
        target = renames.get(key, key)
        assert target in request, (key, request)
        assert str(request[target]) == str(value), (key, request[target], value)


def test_parity_rejects_changed_metrics(tmp_path, monkeypatch):
    import pandas as pd
    from scripts import verify_libero_resident as parity
    monkeypatch.setattr(parity, 'compare_frames', lambda *a: 64)
    a, b = tmp_path/'a.parquet', tmp_path/'b.parquet'
    data = pd.DataFrame(dict(query_idx=[0, 1], selected_value=[.5, .6], video_path=['a', 'a']))
    data.to_parquet(a)
    data.assign(video_path='b').to_parquet(b)
    assert parity.compare_outputs(a,b)['exact_controller']
    data.assign(selected_value=[.5,.60000001], video_path='b').to_parquet(b)
    with pytest.raises(AssertionError):
        parity.compare_outputs(a,b)


def test_only_declared_decoded_image_diagnostics_can_differ(tmp_path,monkeypatch):
    import pandas as pd
    from scripts import verify_libero_resident as parity
    monkeypatch.setattr(parity,'compare_frames',lambda *a:64)
    a,b=tmp_path/'a.parquet',tmp_path/'b.parquet'
    data=pd.DataFrame(dict(selected_value=[.5],future_image_pixel_std_mean=[2.0],video_path=['a']))
    data.to_parquet(a)
    data.assign(future_image_pixel_std_mean=2.001,video_path='b').to_parquet(b)
    result=parity.compare_outputs(a,b,image_diagnostics=True)
    assert result['exact_controller'] and not result['all_metrics_exact']
    with pytest.raises(AssertionError):parity.compare_outputs(a,b)
    data.assign(selected_value=.501,video_path='b').to_parquet(b)
    with pytest.raises(AssertionError):parity.compare_outputs(a,b,image_diagnostics=True)


def test_cold_repeat_variability_is_reported_but_not_accepted_as_migration_parity(tmp_path, monkeypatch):
    import pandas as pd
    from scripts import verify_libero_resident as parity
    monkeypatch.setattr(parity, 'compare_frames', lambda *a: 64)
    a, b = tmp_path/'a.parquet', tmp_path/'b.parquet'
    data = pd.DataFrame(dict(selected_value=[.5], video_path=['a']))
    data.to_parquet(a)
    data.assign(selected_value=.501, video_path='b').to_parquet(b)
    diagnostic = parity.characterize_cold_repeat(a, b)
    assert not diagnostic['exact_controller']
    assert diagnostic['differing_columns'] == ['selected_value']
    with pytest.raises(AssertionError):
        parity.compare_outputs(a, b, image_diagnostics=True)


def test_production_gate_rejects_stale_executor(tmp_path,monkeypatch):
    from scripts import run_libero_resident_campaign as resident
    path, config = tmp_path/'report.json', tmp_path/'config.json'
    config.write_text('{}')
    path.write_text(json.dumps(dict(passed=True,executor_sha256={'wrong':'hash'})))
    with pytest.raises(ValueError,match='stale'):
        resident.validate_parity(path,config)


def test_resident_amendment_changes_only_launcher(tmp_path, monkeypatch):
    from scripts import run_consensus_valid_support_night as night
    monkeypatch.setattr(night,'ROOT',tmp_path)
    scripts=tmp_path/'scripts'
    scripts.mkdir()
    (scripts/'cosmos_env.sh').write_text('new')
    backup=tmp_path/'resource_gpu07_backup/scripts/cosmos_env.sh'
    backup.parent.mkdir(parents=True)
    backup.write_text('old')
    name='run_consensus_valid_support_night.py'
    runner='run_libero_experiment_campaign.py'
    original=dict(scripts={name:'v0',runner:'r0'},configs={'c':'fixed'})
    freeze=tmp_path/'freeze.json'
    night.frozen_json(freeze,original)
    p17=tmp_path/'resource_amendment_gpu17.json'
    night.frozen_json(p17,dict(original_freeze_sha256=night.sha(freeze),old_launcher_sha256='v0',
        new_launcher_sha256='v1',gpu_ids=list(range(1,8)),paired_episode_resume=True))
    p07=tmp_path/'resource_amendment_gpu07.json'
    night.frozen_json(p07,dict(original_freeze_sha256=night.sha(freeze),previous_resource_amendment_sha256=night.sha(p17),
        gpu_ids=list(range(8)),gpu_policy='idle_only_no_compute_processes',paired_episode_resume=True,
        method_configuration_changed=False, script_changes={name:dict(old_sha256='v1',new_sha256='v2'),
            runner:dict(old_sha256='r0',new_sha256='r1')},environment_script=dict(file='cosmos_env.sh',
                old_sha256=night.sha(backup),new_sha256=night.sha(scripts/'cosmos_env.sh'))))
    adapters={}
    for f in ['libero_resident.py','libero_resident_worker.py','run_libero_resident_campaign.py','verify_libero_resident.py']:
        (scripts/f).write_text('fixed adapter')
        adapters[f]=night.sha(scripts/f)
    report=tmp_path/'parity.json'
    report.write_text('{"passed": true}')
    amendment=dict(original_freeze_sha256=night.sha(freeze),previous_resource_amendment_sha256=night.sha(p07),
        old_launcher_sha256='v2',new_launcher_sha256='v3',method_configuration_changed=False,
        scope='references_only',gpu_policy='idle_only_no_compute_processes',adapter_sha256=adapters,
        parity_report_relative='parity.json',parity_report_sha256=night.sha(report),batch_size=8)
    path=tmp_path/'resource_amendment_resident.json'
    night.frozen_json(path,amendment)
    changed=dict(scripts={name:'v3',runner:'r1'},configs={'c':'fixed'})
    night.validate_night_freeze(freeze,changed)
    with pytest.raises(ValueError,match='experiment settings'):
        night.validate_night_freeze(freeze,dict(changed,configs={'c':'changed'}))
    (scripts/'libero_resident.py').write_text('changed adapter')
    with pytest.raises(ValueError,match='adapter changed'):
        night.validate_night_freeze(freeze,changed)

import subprocess

import pytest

from scripts import run_libero_experiment_campaign as campaign


@pytest.mark.parametrize("responses,expected", [
    (["4, 0", "", "4, 0", ""], True),
    (["4, 0", "12345"], False),
    (["4, 0", "", "256, 0"], False),
    (["4, 0", "", "4, 0", "12345"], False),
    (["4, 5"], False),
    (["0, N/A"], False),
    (["-1, 0"], False),
    (["0, -1"], False),
])
def test_admission_requires_stable_idle_and_no_processes(monkeypatch, responses, expected):
    replies = iter(responses)
    calls = []

    def check(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 10
        assert command[command.index("--id") + 1] == "0"
        return next(replies)

    monkeypatch.setattr(campaign.subprocess, "check_output", check)
    monkeypatch.setattr(campaign.time, "sleep", lambda _: None)
    assert campaign.gpu_is_free("0") is expected
    assert len(calls) == len(responses)


@pytest.mark.parametrize("error", [
    FileNotFoundError("nvidia-smi"),
    subprocess.CalledProcessError(1, ["nvidia-smi"]),
    subprocess.TimeoutExpired(["nvidia-smi"], 10),
])
def test_unreadable_gpu_is_not_admitted(monkeypatch, error):
    def check(*args, **kwargs):
        raise error
    monkeypatch.setattr(campaign.subprocess, "check_output", check)
    assert not campaign.gpu_is_free("0")


@pytest.mark.parametrize("authorize,dynamic,message", [
    (False, True, "explicit"),
    (True, False, "idle-only"),
])
def test_gpu_zero_cannot_bypass_idle_only_queue(monkeypatch, tmp_path, authorize, dynamic, message):
    config = {"profiles": {"test": {}}, "defaults": {"dynamic_gpu_queue": dynamic}}
    monkeypatch.setattr(campaign, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(campaign, "load_campaign", lambda _: config)
    monkeypatch.setattr(campaign, "expand_jobs", lambda *args: [{"name": "test"}])
    monkeypatch.setattr(campaign, "validate_job_inputs", lambda _: None)
    args = ["--profile", "test", "--gpus", "0", "--run-prefix", "test", "--execute"]
    if authorize:
        args.append("--allow-gpu-zero")
    with pytest.raises(ValueError, match=message):
        campaign.main(args)


def test_gpu_zero_authorization_is_opt_in():
    assert not campaign.parse_args([]).allow_gpu_zero
    assert campaign.parse_args(["--allow-gpu-zero"]).allow_gpu_zero


def test_admitted_gpu_zero_passes_explicit_shell_authorization(monkeypatch, tmp_path):
    captured = {}

    class Process:
        stdout = []

        def __init__(self, *args, **kwargs):
            captured.update(kwargs["env"])

        def wait(self):
            return 0

    monkeypatch.setattr(campaign, "build_job",
                        lambda *args: ([["probe"]], {}, tmp_path / "completed/test.json"))
    monkeypatch.setattr(campaign.subprocess, "Popen", Process)
    (tmp_path / "logs").mkdir()
    result = campaign.run_job({"name": "test"}, "test", tmp_path, "0", False)
    assert result["status"] == "completed"
    assert captured["CUDA_VISIBLE_DEVICES"] == "0"
    assert captured["MLSPACE_ALLOW_GPU0"] == "1"

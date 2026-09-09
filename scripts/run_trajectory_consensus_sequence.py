#!/usr/bin/env python3
"""Resumable development -> frozen full benchmark; launch under nohup."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUN = "trajectory_consensus_20260908"


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


class Sequence:
    def __init__(self, gpus):
        self.gpus = gpus
        self.directory = ROOT / "experiments/campaigns" / RUN
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / "sequence.lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.stage = "starting"
        self.started = utc()
        self.env = dict(os.environ, WANDB_MODE="offline", HF_HUB_OFFLINE="1", PYTHONUNBUFFERED="1")
        self.env["CUDA_VISIBLE_DEVICES"] = ",".join(gpus)
        self.env["COSMOS_REPO"] = str(self.directory / "source/cosmos-policy")
        self.status("running")

    def status(self, state, **extra):
        atomic_json(self.directory / "sequence_status.json", dict(
            run_base=RUN, status=state, stage=self.stage, pid=os.getpid(),
            gpus=self.gpus, started_at=self.started, updated_at=utc(), **extra,
        ))
        (self.directory / "heartbeat.txt").write_text(f"{utc()} pid={os.getpid()} stage={self.stage}\n")

    def command(self, command):
        print(f"[{utc()}] {self.stage}: {' '.join(map(str, command))}", flush=True)
        child = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=self.env)
        try:
            while child.poll() is None:
                self.status("running", child_pid=child.pid)
                time.sleep(15)
        except BaseException:
            child.terminate()
            child.wait()
            raise
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, command)

    def snapshot(self):
        source = self.directory / "source/cosmos-policy/cosmos_policy"
        if not (self.directory / "source_sha256.json").exists():
            shutil.copytree(ROOT / "cosmos-policy/cosmos_policy", source, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(source.rglob("*")) if p.is_file()}
            atomic_json(self.directory / "source_sha256.json", hashes)
        for name, digest in json.loads((self.directory / "source_sha256.json").read_text()).items():
            if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Frozen source changed: {name}")

    def wait_for_gpus(self):
        self.stage = "waiting_for_gpus"
        stable = 0
        while stable < 2:
            output = subprocess.check_output([
                "nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits"], text=True)
            rows = {parts[0].strip(): (int(parts[1]), int(parts[2]))
                    for parts in (line.split(",") for line in output.splitlines())}
            free = all(g in rows and rows[g][0] < 256 and rows[g][1] < 5 for g in self.gpus)
            stable = stable + 1 if free else 0
            self.status("waiting", gpu_snapshot=rows)
            print(f"GPU capacity {stable}/2: {rows}", flush=True)
            if stable < 2:
                time.sleep(60)

    def campaign(self, phase, config):
        campaign = self.directory.parent / f"{RUN}_{phase}"
        manifest = campaign / "manifest.json"
        if not manifest.exists() or json.loads(manifest.read_text())["status"] != "completed":
            self.wait_for_gpus()
            self.stage = phase
            self.command([sys.executable, ROOT / "scripts/run_libero_experiment_campaign.py",
                          "--config", config, "--profile", phase, "--run-prefix", campaign.name,
                          "--gpus", ",".join(self.gpus), "--execute"])
        self.stage = f"analyze_{phase}"
        command = [sys.executable, ROOT / "scripts/analyze_trajectory_consensus_campaign.py",
                   "--campaign", campaign]
        if phase == "development":
            command += ["--freeze", self.directory / "winner.json"]
        self.command(command)

    def run(self):
        self.snapshot()
        shortlist = self.directory / "offline/shortlist.json"
        if not shortlist.exists():
            self.stage = "offline_screen"
            self.command([sys.executable, ROOT / "scripts/screen_trajectory_consensus.py",
                          "--output", shortlist.parent])
        config = self.directory / "development_config.json"
        self.stage = "prepare_development"
        if not config.exists():
            self.command([sys.executable, ROOT / "scripts/prepare_trajectory_consensus_campaign.py",
                          "--shortlist", shortlist, "--output", config])
        self.campaign("smoke", config)
        self.campaign("development", config)
        self.stage = "freeze_full_test"
        full_config = self.directory / "full_config.json"
        if not full_config.exists():
            self.command([sys.executable, ROOT / "scripts/prepare_trajectory_consensus_campaign.py",
                          "--shortlist", shortlist, "--winner", self.directory / "winner.json",
                          "--output", full_config])
        freeze = self.directory / "full_sha256.json"
        files = [full_config, self.directory / "winner.json", self.directory / "source_sha256.json"]
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        if freeze.exists() and json.loads(freeze.read_text()) != hashes:
            raise ValueError("Frozen full-test settings or evidence changed")
        atomic_json(freeze, hashes)
        self.campaign("full", full_config)
        self.stage = "finished"
        self.status("completed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpus", default="6,7")
    args = parser.parse_args()
    gpus = args.gpus.split(",")
    if len(set(gpus)) != len(gpus) or not gpus or any(g not in "2 3 4 5 6 7".split() for g in gpus):
        parser.error("Only unique physical GPUs 2-7 are allowed")
    sequence = Sequence(gpus)
    try:
        sequence.run()
    except BaseException as error:
        sequence.status("failed", error=repr(error))
        raise


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Retire the two paused original schedulers after their live jobs finish."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from run_trajectory_consensus_sequence import atomic_json, utc

ROOT = Path(__file__).resolve().parents[1]
BASE = "trajectory_consensus_20260908"
REPLACEMENT = BASE + "_compact"
SCHEDULERS = {
    786278: "scripts/run_trajectory_consensus_sequence.py",
    1175267: "scripts/run_libero_experiment_campaign.py",
}


def identity(pid):
    proc = Path(f"/proc/{pid}")
    try:
        command = proc.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode()
        fields = proc.joinpath("stat").read_text().rsplit(")", 1)[1].split()
        return dict(pid=pid, cwd=str(proc.joinpath("cwd").resolve()), command=command,
                    state=fields[0], start_ticks=fields[19])
    except FileNotFoundError:
        return None


def descendants():
    rows = subprocess.check_output(["ps", "-eo", "pid=,ppid=,stat="], text=True).splitlines()
    rows = [line.split() for line in rows]
    parents = set(SCHEDULERS)
    while True:
        found = {int(pid) for pid, ppid, _ in rows if int(ppid) in parents}
        if found <= parents:
            break
        parents |= found
    return [int(pid) for pid, _, state in rows
            if int(pid) in parents - set(SCHEDULERS) and not state.startswith("Z")]


def main():
    directory = ROOT / "experiments/campaigns" / REPLACEMENT
    lock = (directory / "drain.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    originals = {pid: identity(pid) for pid in SCHEDULERS}
    for pid, info in originals.items():
        if info and (info["cwd"] != str(ROOT) or SCHEDULERS[pid] not in info["command"] or info["state"] != "T"):
            raise RuntimeError(f"Refusing to retire unexpected or unpaused PID {pid}: {info}")
    paths = [ROOT / "experiments/campaigns" / BASE / "sequence_status.json",
             ROOT / "experiments/campaigns" / (BASE + "_full") / "manifest.json"]
    audit_path = directory / "superseded_status_audit.json"
    if not audit_path.exists():
        atomic_json(audit_path, dict(created_at=utc(), schedulers=originals,
                                    previous_files={str(p): json.loads(p.read_text()) for p in paths}))

    def update(state, children):
        atomic_json(directory / "drain_status.json", dict(status=state, updated_at=utc(),
                                                         pid=os.getpid(), remaining_children=children))
        for path in paths:
            data = json.loads(path.read_text())
            data.update(status=state, superseded_by=REPLACEMENT, updated_at=utc(),
                        reason="User requested fewer rollouts and GPUs 3-7; original results retained")
            atomic_json(path, data)

    while True:
        children = descendants()
        update("superseded_draining", children)
        if not children:
            break
        time.sleep(15)
    for pid, previous in reversed(list(originals.items())):
        current = identity(pid)
        if current is None:
            continue
        if previous != current:
            raise RuntimeError(f"PID identity changed before retirement: {pid}")
        # These are stopped schedulers with no live children, not GPU collectors.
        os.kill(pid, signal.SIGKILL)
    update("superseded", [])


if __name__ == "__main__":
    main()

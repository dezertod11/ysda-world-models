#!/usr/bin/env python3
"""Materialize deterministic LIBERO-PRO environment BDDL and init states."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import random
import sys
import zipfile
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIBERO_PRO_ROOT = PROJECT_ROOT / "LIBERO-PRO"
sys.path.insert(0, str(LIBERO_PRO_ROOT))

from perturbation import (  # noqa: E402
    BDDLCombinedPerturbator,
    PerturbFlags,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def init_state_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with zipfile.ZipFile(path) as archive:
            return len(pickle.loads(archive.read("archive/data.pkl")))
    except (KeyError, OSError, pickle.PickleError, zipfile.BadZipFile):
        return 0


def write_init_states(path: Path, states: list[np.ndarray]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archive/data.pkl", pickle.dumps(np.asarray(states)))
        archive.writestr("archive/version", b"1")
    temporary.replace(path)


def materialize_bddl(output_dir: Path, seed: int) -> list[Path]:
    source_dir = LIBERO_PRO_ROOT / "libero/libero/bddl_files/libero_object"
    environment_config = LIBERO_PRO_ROOT / "libero_ood/ood_environment.yaml"
    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = BDDLCombinedPerturbator({"environment": str(environment_config)})
    flags = PerturbFlags(use_environment=True)
    outputs: list[Path] = []
    for task_index, source in enumerate(sorted(source_dir.glob("*.bddl"))):
        content = source.read_text(encoding="utf-8")
        transformed = pipeline.perturb_content(
            content=content,
            task_suite_name="libero_object",
            task_name=source.stem,
            flags=flags,
            seed=seed + task_index,
        )
        if transformed == content:
            raise RuntimeError(f"Environment perturbation did not modify {source.name}")
        destination = output_dir / source.name
        destination.write_text(transformed, encoding="utf-8")
        outputs.append(destination)
    if len(outputs) != 10:
        raise RuntimeError(f"Expected 10 LIBERO-Object BDDL files, found {len(outputs)}")
    return outputs


def materialize_init_states(
    bddl_files: list[Path], output_dir: Path, num_inits: int, seed: int
) -> None:
    from libero.libero.envs import OffScreenRenderEnv

    output_dir.mkdir(parents=True, exist_ok=True)
    for task_index, bddl_file in enumerate(bddl_files):
        output_path = output_dir / f"{bddl_file.stem}.pruned_init"
        if init_state_count(output_path) >= num_inits:
            print(f"[environment] keep {output_path.name}: {init_state_count(output_path)} states")
            continue
        states: list[np.ndarray] = []
        for init_index in range(num_inits):
            item_seed = seed + task_index * 10000 + init_index
            random.seed(item_seed)
            np.random.seed(item_seed)
            environment = None
            try:
                environment = OffScreenRenderEnv(
                    bddl_file_name=str(bddl_file),
                    camera_heights=128,
                    camera_widths=128,
                )
                states.append(environment.get_sim_state())
            finally:
                if environment is not None:
                    environment.close()
        write_init_states(output_path, states)
        print(f"[environment] wrote {output_path.name}: {len(states)} states")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--num-inits", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260825)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.num_inits < 1:
        raise ValueError("--num-inits must be positive")
    output_root = args.output_root.resolve()
    bddl_dir = output_root / "bddl_files/libero_object_env"
    init_dir = output_root / "init_files/libero_object_env"
    bddl_files = materialize_bddl(bddl_dir, args.seed)
    materialize_init_states(bddl_files, init_dir, args.num_inits, args.seed)
    metadata = {
        "schema_version": 1,
        "source_suite": "libero_object",
        "target_suite": "libero_object_env",
        "environment": "living_room_table",
        "seed": args.seed,
        "num_init_states_per_task": args.num_inits,
        "ood_environment_sha256": sha256(
            LIBERO_PRO_ROOT / "libero_ood/ood_environment.yaml"
        ),
        "bddl_sha256": {path.name: sha256(path) for path in bddl_files},
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"[environment] ready: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

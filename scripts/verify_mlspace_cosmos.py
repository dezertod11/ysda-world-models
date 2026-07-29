#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download


def main() -> None:
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if "0" in {item.strip() for item in visible_devices.split(",")}:
        raise RuntimeError("Physical GPU 0 must not be used on MLSpace")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")

    from libero import libero as libero_package
    from libero.libero import benchmark, get_libero_path

    project_root = Path(__file__).resolve().parents[1]
    expected_libero = (project_root / "LIBERO-PRO").resolve()
    imported_libero = Path(libero_package.__file__).resolve()
    if expected_libero not in imported_libero.parents:
        raise RuntimeError(
            f"Expected LIBERO-PRO from {expected_libero}, imported {imported_libero}"
        )

    suites = benchmark.get_benchmark_dict()
    required_suite = "libero_spatial_object"
    if required_suite not in suites:
        raise RuntimeError(f"{required_suite} is missing from LIBERO-PRO")

    bddl_path = Path(get_libero_path("bddl_files"))
    init_path = Path(get_libero_path("init_states"))
    if not bddl_path.is_dir() or not init_path.is_dir():
        raise RuntimeError("LIBERO-PRO BDDL/init paths are invalid")

    from cosmos_policy.experiments.robot.libero import uncertainty_metrics

    cached_files = {
        "policy_checkpoint": (
            "nvidia/Cosmos-Policy-LIBERO-Predict2-2B",
            "Cosmos-Policy-LIBERO-Predict2-2B.pt",
        ),
        "t5_embeddings": (
            "nvidia/Cosmos-Policy-LIBERO-Predict2-2B",
            "libero_t5_embeddings.pkl",
        ),
        "dataset_statistics": (
            "nvidia/Cosmos-Policy-LIBERO-Predict2-2B",
            "libero_dataset_statistics.json",
        ),
        "video_tokenizer": (
            "nvidia/Cosmos-Predict2-2B-Video2World",
            "tokenizer/tokenizer.pth",
        ),
    }
    resolved_cache = {
        name: Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_files_only=True,
            )
        ).resolve()
        for name, (repo_id, filename) in cached_files.items()
    }

    print(f"python={os.sys.executable}")
    print(f"torch={torch.__version__}")
    print(f"cuda_visible_devices={visible_devices}")
    print(f"logical_cuda_0={torch.cuda.get_device_name(0)}")
    print(f"libero={imported_libero}")
    print(f"libero_suites={len(suites)}")
    print(f"bddl_files={bddl_path}")
    print(f"uncertainty_metrics={Path(uncertainty_metrics.__file__).resolve()}")
    for name, path in resolved_cache.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()

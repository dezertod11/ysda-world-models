#!/usr/bin/env python3
"""Train frozen bootstrap Gaussian heads on standard-LIBERO residual transitions."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.build_residual_dynamics_dataset import sha256_file
    from scripts.residual_dynamics_ensemble import (
        ResidualPreprocessor,
        train_independent_heads,
    )
except ModuleNotFoundError:
    from build_residual_dynamics_dataset import sha256_file
    from residual_dynamics_ensemble import ResidualPreprocessor, train_independent_heads


def train(args: argparse.Namespace) -> dict[str, object]:
    manifest_path = args.manifest.expanduser().resolve()
    feature_path = args.features.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if (output_dir / "ensemble.json").exists() and not args.force:
        raise FileExistsError(f"Frozen ensemble already exists: {output_dir}")
    if args.force and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_parquet(manifest_path)
    with np.load(feature_path, allow_pickle=False) as payload:
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    if len(manifest) != len(arrays["row_index"]):
        raise ValueError("Feature rows do not match transition manifest")
    train_indices = np.flatnonzero(manifest["split"].astype(str).eq("train").to_numpy())
    if len(train_indices) < args.min_train_rows:
        raise ValueError(
            f"Only {len(train_indices)} train rows; need {args.min_train_rows}"
        )
    preprocessor = ResidualPreprocessor.fit(
        arrays,
        train_indices,
        input_visual_components=args.input_visual_components,
        target_visual_components=args.target_visual_components,
        seed=args.seed,
    )
    preprocessor.save(output_dir / "preprocessing.npz")
    x_train = preprocessor.transform_input(arrays, train_indices)
    y_train = preprocessor.transform_target(arrays, train_indices)
    histories = train_independent_heads(
        x_train,
        y_train,
        manifest.iloc[train_indices]["group_id"].astype(str).to_numpy(),
        output_dir,
        num_heads=args.num_heads,
        hidden_dim=args.hidden_dim,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        seed=args.seed,
        device=args.device,
    )
    history_frame = pd.DataFrame(
        [
            {key: value for key, value in row.items() if key != "sampled_groups"}
            for row in histories
        ]
    )
    history_frame.to_csv(output_dir / "training_history.csv", index=False)
    (output_dir / "bootstrap_groups.json").write_text(
        json.dumps(
            {str(row["head"]): row["sampled_groups"] for row in histories}, indent=2
        ),
        encoding="utf-8",
    )
    script_dir = Path(__file__).resolve().parent
    code_files = (
        "build_residual_dynamics_dataset.py",
        "extract_residual_dynamics_features.py",
        "residual_dynamics_ensemble.py",
        "train_residual_dynamics_ensemble.py",
        "analyze_residual_dynamics_ensemble.py",
    )
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "features": str(feature_path),
        "features_sha256": sha256_file(feature_path),
        "training_split": "train",
        "train_rows": len(train_indices),
        "train_groups": int(manifest.iloc[train_indices]["group_id"].nunique()),
        "num_heads": args.num_heads,
        "input_dim": int(x_train.shape[1]),
        "target_dim": int(y_train.shape[1]),
        "hidden_dim": args.hidden_dim,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "input_visual_components": int(preprocessor.input_visual_components.shape[0]),
        "target_visual_components": int(preprocessor.target_visual_components.shape[0]),
        "seed": args.seed,
        "device": args.device,
        "code_sha256": {
            filename: sha256_file(script_dir / filename) for filename in code_files
        },
    }
    (output_dir / "ensemble.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    frozen_files = [
        output_dir / "preprocessing.npz",
        *[output_dir / f"head_{index}.pt" for index in range(args.num_heads)],
        output_dir / "training_history.csv",
        output_dir / "bootstrap_groups.json",
        output_dir / "ensemble.json",
    ]
    (output_dir / "SHA256SUMS").write_text(
        "\n".join(f"{sha256_file(path)}  {path.name}" for path in frozen_files) + "\n",
        encoding="utf-8",
    )
    return metadata


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--features", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--num-heads", type=int, default=5)
    result.add_argument("--hidden-dim", type=int, default=256)
    result.add_argument("--input-visual-components", type=int, default=64)
    result.add_argument("--target-visual-components", type=int, default=64)
    result.add_argument("--epochs", type=int, default=120)
    result.add_argument("--batch-size", type=int, default=256)
    result.add_argument("--learning-rate", type=float, default=1e-3)
    result.add_argument("--weight-decay", type=float, default=1e-5)
    result.add_argument("--seed", type=int, default=20260906)
    result.add_argument("--device", default="cuda")
    result.add_argument("--min-train-rows", type=int, default=400)
    result.add_argument("--force", action="store_true")
    return result


def main() -> int:
    metadata = train(parser().parse_args())
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Train one early-stopped P4b residual ensemble variant."""

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
    from scripts.p4b_residual_risk import train_early_stopped_heads
    from scripts.residual_dynamics_ensemble import ResidualPreprocessor
except ModuleNotFoundError:
    from build_residual_dynamics_dataset import sha256_file
    from p4b_residual_risk import train_early_stopped_heads
    from residual_dynamics_ensemble import ResidualPreprocessor


def train(args: argparse.Namespace) -> dict[str, object]:
    manifest_path = args.manifest.expanduser().resolve()
    feature_path = args.features.expanduser().resolve()
    preprocessing_path = args.preprocessing_from.expanduser().resolve()
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
    train_indices = np.flatnonzero(manifest["split"].astype(str).eq("train"))
    if len(train_indices) < args.min_train_rows:
        raise ValueError(
            f"Only {len(train_indices)} train rows; need {args.min_train_rows}"
        )

    preprocessor = ResidualPreprocessor.load(preprocessing_path)
    shutil.copy2(preprocessing_path, output_dir / "preprocessing.npz")
    features = preprocessor.transform_input(arrays, train_indices)
    targets = preprocessor.transform_target(arrays, train_indices)
    summaries, history, shared_variance = train_early_stopped_heads(
        features,
        targets,
        manifest.iloc[train_indices]["group_id"].astype(str).to_numpy(),
        output_dir,
        loss_mode=args.loss_mode,
        log_variance_l2=args.log_variance_l2,
        num_heads=args.num_heads,
        hidden_dim=args.hidden_dim,
        max_epochs=args.max_epochs,
        min_epochs=args.min_epochs,
        patience=args.patience,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        seed=args.seed,
        device=args.device,
    )
    np.save(output_dir / "shared_variance.npy", shared_variance, allow_pickle=False)
    pd.DataFrame(history).to_csv(output_dir / "training_history.csv", index=False)
    pd.DataFrame(
        [
            {key: value for key, value in row.items() if key != "sampled_groups"}
            for row in summaries
        ]
    ).to_csv(output_dir / "head_summary.csv", index=False)
    (output_dir / "bootstrap_groups.json").write_text(
        json.dumps(
            {str(row["head"]): row["sampled_groups"] for row in summaries},
            indent=2,
        ),
        encoding="utf-8",
    )

    script_dir = Path(__file__).resolve().parent
    code_files = (
        "p4b_residual_risk.py",
        "train_p4b_residual_ensemble.py",
        "analyze_p4b_development.py",
        "analyze_p4b_terminal_holdout.py",
    )
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "variant_name": args.variant_name,
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "features": str(feature_path),
        "features_sha256": sha256_file(feature_path),
        "preprocessing_source": str(preprocessing_path),
        "preprocessing_source_sha256": sha256_file(preprocessing_path),
        "training_split": "train",
        "train_rows": len(train_indices),
        "train_groups": int(manifest.iloc[train_indices]["group_id"].nunique()),
        "num_heads": args.num_heads,
        "input_dim": int(features.shape[1]),
        "target_dim": int(targets.shape[1]),
        "hidden_dim": args.hidden_dim,
        "loss_mode": args.loss_mode,
        "log_variance_l2": args.log_variance_l2,
        "max_epochs": args.max_epochs,
        "min_epochs": args.min_epochs,
        "patience": args.patience,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "seed": args.seed,
        "device": args.device,
        "code_sha256": {
            filename: sha256_file(script_dir / filename)
            for filename in code_files
            if (script_dir / filename).is_file()
        },
    }
    (output_dir / "ensemble.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    frozen_files = [
        output_dir / "preprocessing.npz",
        output_dir / "shared_variance.npy",
        *[output_dir / f"head_{index}.pt" for index in range(args.num_heads)],
        output_dir / "training_history.csv",
        output_dir / "head_summary.csv",
        output_dir / "bootstrap_groups.json",
        output_dir / "ensemble.json",
    ]
    (output_dir / "SHA256SUMS").write_text(
        "\n".join(f"{sha256_file(path)}  {path.name}" for path in frozen_files)
        + "\n",
        encoding="utf-8",
    )
    return metadata


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--variant-name", required=True)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--features", type=Path, required=True)
    result.add_argument("--preprocessing-from", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument(
        "--loss-mode", choices=["gaussian_nll", "mean_mse"], required=True
    )
    result.add_argument("--log-variance-l2", type=float, default=0.0)
    result.add_argument("--num-heads", type=int, default=5)
    result.add_argument("--hidden-dim", type=int, default=256)
    result.add_argument("--max-epochs", type=int, default=160)
    result.add_argument("--min-epochs", type=int, default=12)
    result.add_argument("--patience", type=int, default=15)
    result.add_argument("--batch-size", type=int, default=256)
    result.add_argument("--learning-rate", type=float, default=1e-3)
    result.add_argument("--weight-decay", type=float, default=1e-5)
    result.add_argument("--seed", type=int, default=20260907)
    result.add_argument("--device", default="cuda")
    result.add_argument("--min-train-rows", type=int, default=400)
    result.add_argument("--force", action="store_true")
    return result


def main() -> int:
    print(json.dumps(train(parser().parse_args()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


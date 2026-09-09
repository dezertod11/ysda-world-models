import json
from argparse import Namespace

import numpy as np
import pandas as pd

from scripts.analyze_residual_dynamics_ensemble import (
    analyze,
    average_precision,
    balanced_average_precision,
    detection_table,
    offline_hard_filter,
    roc_auc,
)
from scripts.train_residual_dynamics_ensemble import train


def test_binary_ranking_metrics_are_one_for_perfect_ordering() -> None:
    labels = np.asarray([False, False, True, True])
    scores = np.asarray([0.0, 0.1, 0.8, 1.0])
    assert roc_auc(labels, scores) == 1.0
    assert average_precision(labels, scores) == 1.0
    assert balanced_average_precision(labels, scores) == 1.0


def test_detection_table_compares_whole_groups() -> None:
    groups = pd.DataFrame(
        {
            "group_id": ["i0", "i1", "o0", "o1"],
            "split": ["id_test", "id_test", "ood_test", "ood_test"],
            "factor": ["ID", "ID", "Object", "Object"],
            "score": [0.0, 0.1, 0.8, 0.9],
        }
    )
    result = detection_table(groups, ["score"], bootstrap_repetitions=20, seed=3)
    assert set(result["factor"]) == {"Object", "All OOD"}
    assert np.allclose(result["roc_auc"], 1.0)


def test_offline_filter_uses_value_only_inside_conformal_feasible_set() -> None:
    candidates = pd.DataFrame(
        {
            "snapshot_group": ["s", "s", "s"],
            "group_id": ["g", "g", "g"],
            "split": ["ood_test"] * 3,
            "factor": ["Object"] * 3,
            "candidate_idx": [0, 1, 2],
            "candidate_value": [0.9, 0.8, 0.7],
            "ensemble_jrd": [0.6, 0.2, 0.1],
            "local_utility_v1": [-1.0, 1.0, 0.5],
            "local_success": [False, True, False],
        }
    )
    result = offline_hard_filter(candidates, threshold=0.3)
    assert int(result.iloc[0]["baseline_candidate_idx"]) == 0
    assert int(result.iloc[0]["filtered_candidate_idx"]) == 1
    assert bool(result.iloc[0]["selection_changed"])
    assert float(result.iloc[0]["filtered_local_utility"]) == 1.0


def test_end_to_end_cpu_artifact_and_analysis(tmp_path) -> None:
    rng = np.random.default_rng(17)
    groups = 30
    candidates_per_group = 2
    rows = groups * candidates_per_group
    group_index = np.repeat(np.arange(groups), candidates_per_group)
    split = np.select(
        [group_index < 15, group_index < 20, group_index < 25],
        ["train", "calibration", "id_test"],
        default="ood_test",
    )
    factor = np.where(split == "ood_test", "Object", "ID")
    predicted_visual = rng.normal(size=(rows, 12)).astype(np.float32)
    residual_scale = np.where(split == "ood_test", 0.8, 0.1).astype(np.float32)
    actual_visual = (
        predicted_visual
        + rng.normal(size=(rows, 12)).astype(np.float32) * residual_scale[:, None]
    )
    predicted_proprio = rng.normal(size=(rows, 9)).astype(np.float32)
    actual_proprio = (
        predicted_proprio
        + rng.normal(size=(rows, 9)).astype(np.float32) * residual_scale[:, None]
    )
    features = tmp_path / "features.npz"
    np.savez(
        features,
        row_index=np.arange(rows),
        current_visual=rng.normal(size=(rows, 12)).astype(np.float32),
        predicted_visual=predicted_visual,
        actual_visual=actual_visual,
        current_proprio=rng.normal(size=(rows, 9)).astype(np.float32),
        predicted_proprio=predicted_proprio,
        actual_proprio=actual_proprio,
        actions=rng.normal(size=(rows, 16, 7)).astype(np.float32),
        candidate_value=rng.normal(size=rows).astype(np.float32),
    )
    manifest = pd.DataFrame(
        {
            "row_uid": [f"row-{index}" for index in range(rows)],
            "group_id": [f"group-{index}" for index in group_index],
            "snapshot_group": [f"snapshot-{index}" for index in group_index],
            "split": split,
            "factor": factor,
            "suite": np.where(
                split == "ood_test", "libero_object_object", "libero_object"
            ),
            "task_id": group_index % 10,
            "candidate_idx": np.tile(np.arange(candidates_per_group), groups),
            "candidate_value": rng.normal(size=rows),
            "value_std": rng.uniform(size=rows),
            "local_utility_v1": rng.normal(size=rows),
            "local_success": rng.uniform(size=rows) > 0.5,
            "terminal_available": split == "ood_test",
            "terminal_success": rng.uniform(size=rows) > 0.5,
        }
    )
    manifest_path = tmp_path / "manifest.parquet"
    manifest.to_parquet(manifest_path, index=False)
    artifact = tmp_path / "artifact"
    train(
        Namespace(
            manifest=manifest_path,
            features=features,
            output_dir=artifact,
            force=False,
            min_train_rows=10,
            input_visual_components=5,
            target_visual_components=4,
            seed=23,
            num_heads=2,
            hidden_dim=8,
            epochs=2,
            batch_size=16,
            learning_rate=1e-3,
            weight_decay=1e-5,
            device="cpu",
        )
    )
    output = tmp_path / "analysis"
    summary = analyze(
        Namespace(
            manifest=manifest_path,
            features=features,
            artifact_dir=artifact,
            output_dir=output,
            device="cpu",
            batch_size=16,
            alpha=0.1,
            max_id_fpr=1.0,
            min_jrd_ap=0.0,
            min_ap_gain=-1.0,
            min_error_rho=-1.0,
            bootstrap_repetitions=10,
            seed=29,
        )
    )
    assert summary["complete"]
    assert "jrd_trajectory_prediction_error_spearman" in summary
    assert (artifact / "SHA256SUMS").is_file()
    metadata = json.loads((artifact / "ensemble.json").read_text(encoding="utf-8"))
    assert set(metadata["code_sha256"]) == {
        "build_residual_dynamics_dataset.py",
        "extract_residual_dynamics_features.py",
        "residual_dynamics_ensemble.py",
        "train_residual_dynamics_ensemble.py",
        "analyze_residual_dynamics_ensemble.py",
    }
    assert (output / "summary.json").is_file()
    correlations = pd.read_csv(output / "prediction_error_correlations.csv")
    assert set(correlations["unit"]) == {"candidate", "trajectory"}
    assert (output / "ood_detection_average_precision.png").is_file()
    assert len(pd.read_csv(output / "offline_hard_filter.csv")) == 5

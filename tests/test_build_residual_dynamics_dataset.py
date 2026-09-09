from pathlib import Path

import numpy as np
import pandas as pd

from scripts.build_residual_dynamics_dataset import build_dataset


def _sidecar(path: Path, candidates: int = 2) -> None:
    images = np.zeros((candidates, 8, 8, 3), dtype=np.uint8)
    np.savez(
        path,
        current_agentview=np.zeros((8, 8, 3), dtype=np.uint8),
        current_wrist=np.zeros((8, 8, 3), dtype=np.uint8),
        current_proprio=np.zeros(9, dtype=np.float32),
        candidate_actions=np.zeros((candidates, 16, 7), dtype=np.float32),
        candidate_values=np.zeros(candidates, dtype=np.float32),
        candidate_endpoint_agentview=images,
        candidate_endpoint_wrist=images,
        candidate_endpoint_proprio=np.zeros((candidates, 9), dtype=np.float32),
        candidate_predicted_future_images=images,
        candidate_predicted_future_wrists=images,
        candidate_predicted_future_proprio=np.zeros((candidates, 9), dtype=np.float32),
    )


def test_dataset_deduplicates_rows_and_keeps_groups_inside_splits(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    runs = campaign / "runs"
    runs.mkdir(parents=True)
    rows = []
    for task_id in range(2):
        for init_state_id in range(6):
            sidecar = runs / f"id_{task_id}_{init_state_id}.npz"
            _sidecar(sidecar)
            for candidate_idx in range(2):
                rows.append(
                    {
                        "snapshot_id": sidecar.stem,
                        "suite": "libero_object",
                        "task_id": task_id,
                        "init_state_id": init_state_id,
                        "rollout_id": 0,
                        "candidate_idx": candidate_idx,
                        "candidate_value": float(candidate_idx),
                        "open_loop_steps": 16,
                        "sidecar_path": str(sidecar),
                    }
                )
    ood = runs / "ood.npz"
    _sidecar(ood)
    for candidate_idx in range(2):
        rows.append(
            {
                "snapshot_id": "ood",
                "suite": "libero_object_object",
                "task_id": 0,
                "init_state_id": 0,
                "rollout_id": 0,
                "candidate_idx": candidate_idx,
                "candidate_value": 0.0,
                "open_loop_steps": 16,
                "sidecar_path": str(ood),
            }
        )
    table = pd.DataFrame(rows)
    table.to_parquet(runs / "source__candidate_outcomes.parquet", index=False)
    table.to_parquet(runs / "duplicate__candidate_outcomes.parquet", index=False)

    result = build_dataset([campaign], tmp_path / "output")
    assert len(result) == len(rows)
    assert not result["row_uid"].duplicated().any()
    assert result.groupby("group_id")["split"].nunique().max() == 1
    assert set(result.loc[result["factor"].eq("ID"), "split"]) == {
        "train",
        "calibration",
        "id_test",
    }
    assert set(result.loc[result["factor"].eq("Object"), "split"]) == {"ood_test"}

#!/usr/bin/env python3
"""Compare repeated-query diagnostic artifacts within and across processes."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np


def max_abs_difference(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return float("inf")
    return float(np.max(np.abs(left - right), initial=0.0))


def compare_artifacts(
    left: dict[str, np.ndarray],
    right: dict[str, np.ndarray],
    *,
    action_tolerance: float,
    value_tolerance: float,
) -> dict[str, object]:
    identity_keys = (
        "init_state_ids",
        "candidate_seeds",
        "observation_hashes",
        "simulator_hashes",
    )
    identities_match = all(np.array_equal(left[key], right[key]) for key in identity_keys)
    action_diff = max_abs_difference(left["actions"][:, 0], right["actions"][:, 0])
    value_diff = max_abs_difference(left["values"][:, 0], right["values"][:, 0])
    selected_match = float(
        np.mean(left["selected_indices"][:, 0] == right["selected_indices"][:, 0])
    )
    return {
        "inputs_match": bool(identities_match),
        "action_max_abs_diff": action_diff,
        "value_max_abs_diff": value_diff,
        "selected_index_match_rate": selected_match,
        "strict_match": bool(
            identities_match
            and action_diff <= action_tolerance
            and value_diff <= value_tolerance
            and selected_match == 1.0
        ),
    }


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as values:
        return {key: values[key] for key in values.files}


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--action-tolerance", type=float, default=1e-5)
    parser.add_argument("--value-tolerance", type=float, default=1e-5)
    args = parser.parse_args()

    paths = sorted(args.input_dir.expanduser().glob("*.npz"))
    if len(paths) < 2:
        raise FileNotFoundError("At least two diagnostic NPZ files are required")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {}
    metadata = {}
    within_rows = []
    for path in paths:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        artifacts[path] = _load(path)
        metadata[path] = meta
        within_rows.append(
            {
                "mode": meta["torch"]["mode"],
                "replica_id": meta["replica_id"],
                **meta["within_process"],
            }
        )

    cross_rows = []
    modes = sorted({str(meta["torch"]["mode"]) for meta in metadata.values()})
    for mode in modes:
        mode_paths = [
            path for path in paths if str(metadata[path]["torch"]["mode"]) == mode
        ]
        for left_path, right_path in itertools.combinations(mode_paths, 2):
            cross_rows.append(
                {
                    "mode": mode,
                    "left_replica": metadata[left_path]["replica_id"],
                    "right_replica": metadata[right_path]["replica_id"],
                    **compare_artifacts(
                        artifacts[left_path],
                        artifacts[right_path],
                        action_tolerance=args.action_tolerance,
                        value_tolerance=args.value_tolerance,
                    ),
                }
            )

    _write_csv(output_dir / "within_process.csv", within_rows)
    _write_csv(output_dir / "cross_process.csv", cross_rows)
    mode_summary = {}
    for mode in modes:
        within = [row for row in within_rows if row["mode"] == mode]
        cross = [row for row in cross_rows if row["mode"] == mode]
        mode_summary[mode] = {
            "within_process_exact": bool(within and all(row["exact"] for row in within)),
            "cross_process_strict": bool(cross and all(row["strict_match"] for row in cross)),
            "max_cross_action_abs_diff": max(
                (float(row["action_max_abs_diff"]) for row in cross), default=float("nan")
            ),
            "max_cross_value_abs_diff": max(
                (float(row["value_max_abs_diff"]) for row in cross), default=float("nan")
            ),
            "min_cross_selected_index_match_rate": min(
                (float(row["selected_index_match_rate"]) for row in cross),
                default=float("nan"),
            ),
        }
    summary = {
        "artifact_count": len(paths),
        "action_tolerance": args.action_tolerance,
        "value_tolerance": args.value_tolerance,
        "modes": mode_summary,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    lines = [
        "# Cosmos identical-query reproducibility diagnostic",
        "",
        f"Artifacts: **{len(paths)}**.",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "Detailed comparisons are in `within_process.csv` and `cross_process.csv`.",
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build deterministic video replays for confirmatory discordant outcomes."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Sequence

from build_adaptive_confirmatory_config import parse_strategy_id


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def case_stratum(case_id: str) -> str:
    holdout_prefixes = ("spatial_mug_", "long_milk_", "goal_mug_")
    if case_id.endswith(("_surrogate_screen", "_surrogate_confirm")):
        return "new_ood_holdout" if case_id.startswith("new_ood_") else "known_boundary"
    return (
        "new_ood_holdout"
        if case_id.startswith(("new_ood_", *holdout_prefixes))
        else "known_boundary"
    )


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def max_timesteps_for_suite(suite: str) -> int:
    if suite.startswith("libero_10"):
        return 520
    if suite.startswith("libero_object"):
        return 280
    if suite.startswith("libero_goal_with"):
        return 320
    if suite.startswith("libero_goal"):
        return 300
    return 220


def selected_strategies(path: Path) -> dict[str, str]:
    rows = read_rows(path)
    result = {row["selection_category"]: row["strategy_id"] for row in rows}
    supported = [
        {"no_extra_inference", "adaptive_horizon"},
        {"non_surrogate_adaptive", "surrogate_adaptive"},
    ]
    if set(result) not in supported:
        raise ValueError(
            "Expected one of the frozen category sets "
            f"{[sorted(values) for values in supported]}, got {sorted(result)}"
        )
    return result


def select_discordant_rows(
    rows: list[dict[str, str]],
    selected: dict[str, str],
    *,
    wins_per_stratum: int,
    losses_per_stratum: int,
) -> list[dict[str, str]]:
    selected_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for category in selected:
        strategy = selected[category]
        strategy_rows = [row for row in rows if row["strategy_id"] == strategy]
        for stratum in ("known_boundary", "new_ood_holdout"):
            stratum_rows = [
                row for row in strategy_rows if case_stratum(row["case_id"]) == stratum
            ]
            for direction, limit in ((1, wins_per_stratum), (-1, losses_per_stratum)):
                candidates = sorted(
                    (
                        row
                        for row in stratum_rows
                        if int(float(row["delta"])) == direction
                    ),
                    key=lambda row: (row["case_id"], int(float(row["rollout_seed"]))),
                )
                added = 0
                for row in candidates:
                    key = (row["case_id"], row["rollout_seed"])
                    if key in seen:
                        continue
                    replay = dict(row)
                    replay["selection_category"] = category
                    replay["selection_reason"] = "win" if direction == 1 else "loss"
                    replay["case_stratum"] = stratum
                    selected_rows.append(replay)
                    seen.add(key)
                    added += 1
                    if added >= limit:
                        break
    return selected_rows


def build_config(
    base_config: dict,
    selected: dict[str, str],
    replay_rows: list[dict[str, str]],
) -> dict:
    jobs = []
    for index, row in enumerate(replay_rows):
        rollout_seed = int(float(row["rollout_seed"]))
        selected_token, selected_overrides = parse_strategy_id(row["strategy_id"])
        strategy_tokens = [
            "max_value:0",
            "uncertainty_penalty_action:1",
            "disagreement_requery_action:1",
            selected_token,
        ]
        strategy_lambdas = " ".join(dict.fromkeys(strategy_tokens))
        jobs.append(
            {
                "name": safe_name(
                    f"{row['selection_category']}__{row['selection_reason']}__"
                    f"{row['case_id']}__seed{rollout_seed}"
                ),
                "kind": "pro_planning_grid",
                "gpu_slot": index % 6,
                "experiment_split": "holdout",
                "case_id": row["case_id"],
                "suites": row["suite"],
                "task_ids": str(int(float(row["task_id"]))),
                "init_state_ids": str(int(float(row["init_state_id"]))),
                "max_rollouts": 1,
                "base_seed": rollout_seed,
                "max_timesteps": max_timesteps_for_suite(row["suite"]),
                "strategy_lambdas": strategy_lambdas,
                "selection_category": row["selection_category"],
                "selection_reason": row["selection_reason"],
                "selected_strategy_id": row["strategy_id"],
                **selected_overrides,
            }
        )
    defaults = dict(base_config["defaults"])
    defaults["save_videos"] = True
    return {
        "schema_version": 1,
        "profiles": {
            "adaptive_video_replays": {
                "description": (
                    "Deterministic visual replays of preregistered confirmatory "
                    "discordant outcomes"
                ),
                "jobs": jobs,
            }
        },
        "defaults": defaults,
    }


def write_selection_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    columns = [
        "selection_category",
        "selection_reason",
        "case_stratum",
        "strategy_id",
        "case_id",
        "suite",
        "task_id",
        "init_state_id",
        "rollout_seed",
        "baseline_success",
        "success",
        "delta",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--frozen-selection-csv", type=Path, required=True)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selection-manifest", type=Path, default=None)
    parser.add_argument("--wins-per-stratum", type=int, default=1)
    parser.add_argument("--losses-per-stratum", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.wins_per_stratum < 0 or args.losses_per_stratum < 0:
        raise ValueError("Replay counts must be non-negative")
    selected = selected_strategies(args.frozen_selection_csv)
    outcome_rows = read_rows(args.analysis_dir / "paired_seed_outcomes.csv")
    replay_rows = select_discordant_rows(
        outcome_rows,
        selected,
        wins_per_stratum=args.wins_per_stratum,
        losses_per_stratum=args.losses_per_stratum,
    )
    if not replay_rows:
        print("No selected-strategy discordant outcomes found")
        return 3
    base_config = json.loads(args.base_config.read_text(encoding="utf-8"))
    config = build_config(base_config, selected, replay_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    selection_manifest = args.selection_manifest or args.output.with_suffix(".csv")
    write_selection_manifest(selection_manifest, replay_rows)
    print(f"Selected {len(replay_rows)} discordant case/seed replays")
    print(f"Wrote: {args.output}")
    print(f"Wrote: {selection_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

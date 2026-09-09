#!/usr/bin/env python3
"""Verify implementation invariants for the frozen-ranker smoke campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_frozen_ranker_closed_loop import (
    BASELINE,
    METHOD,
    load_campaign_episodes,
    q0_integrity,
)


EXPECTED_PAIR_COUNTS = {"Environment": 1, "Object": 1, "Position": 2}


def verify(campaign_dir: Path, expected_model_sha: str) -> dict[str, object]:
    episodes, paired = load_campaign_episodes(campaign_dir)
    integrity = q0_integrity(campaign_dir)
    pair_counts = paired.groupby("factor").size().to_dict()
    hashes = sorted(
        value for value in episodes["model_payload_sha256"].astype(str).unique() if value
    )
    match_columns = [column for column in integrity if column.endswith("_match")]
    checks = {
        "eight_episode_rollouts": len(episodes) == 8,
        "four_complete_pairs": len(paired) == 4 and bool(paired["pair_complete"].all()),
        "expected_factor_pairs": pair_counts == EXPECTED_PAIR_COUNTS,
        "model_hash_matches": hashes == [expected_model_sha],
        "six_candidates": bool(
            episodes["candidate_count_min"].eq(6).all()
            and episodes["candidate_count_max"].eq(6).all()
        ),
        "q0_candidate_pools_match": bool(integrity[match_columns].all().all()),
        "baseline_is_argmax_value": bool(
            integrity["baseline_selected_argmax_value"].all()
        ),
        "ranker_is_argmax_score": bool(
            integrity["frozen_selected_argmax_score"].all()
        ),
        "ranker_changes_at_least_one_selection": bool(
            integrity["selectors_disagree"].any()
        ),
        "strategies_present": set(episodes["planning_strategy"]) == {BASELINE, METHOD},
    }
    result = {
        "passed": all(checks.values()),
        "checks": checks,
        "pair_counts": {key: int(value) for key, value in pair_counts.items()},
        "model_payload_sha256": hashes,
    }
    output = campaign_dir / "analysis" / "smoke_integrity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--expected-model-sha", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.campaign_dir.expanduser().resolve(), args.expected_model_sha),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

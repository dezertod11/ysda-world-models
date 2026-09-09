from __future__ import annotations

import json

import pandas as pd

from scripts.analyze_proposal_opportunity_k16 import analyze


def _state(
    snapshot: str,
    factor: str,
    group: str,
    query: int,
    maxv: bool,
    oracle: bool,
) -> dict[str, object]:
    return {
        "analysis_snapshot_id": snapshot,
        "factor": factor,
        "case_id": f"synthetic_{factor.lower()}",
        "independent_group": group,
        "suite": f"suite_{factor.lower()}",
        "task_id": 0,
        "task_description": "synthetic task",
        "init_state_id": int(group[-1]),
        "query_idx": query,
        "phase": "approach",
        "candidates": 16,
        "outcome_heterogeneous": oracle != maxv,
        "maxv_success": maxv,
        "oracle_success": oracle,
        "success_rescue": oracle and not maxv,
        "success_harm_possible": False,
        "maxv_utility": 3.0 if maxv else 0.0,
        "oracle_utility": 3.0 if oracle else 0.0,
        "utility_rescue": oracle != maxv,
        "source_run": "synthetic",
        "source_path": "/tmp/synthetic.parquet",
        "campaign": "proposal_opportunity_k16_test",
        "all_candidates_fail": not oracle,
        "all_candidates_succeed": maxv and not (oracle != maxv),
    }


def test_analyze_routes_only_rescue_positive_factor(tmp_path) -> None:
    rows = [
        _state("o0q0", "Object", "Object|0", 0, False, True),
        _state("o0q3", "Object", "Object|0", 3, True, True),
        _state("o1q0", "Object", "Object|1", 0, False, True),
        _state("o1q3", "Object", "Object|1", 3, True, True),
        _state("e0q0", "Environment", "Environment|0", 0, False, False),
        _state("e1q0", "Environment", "Environment|1", 0, False, False),
    ]
    atlas_dir = tmp_path / "atlas"
    output_dir = tmp_path / "analysis"
    atlas_dir.mkdir()
    pd.DataFrame(rows).to_csv(atlas_dir / "opportunity_states.csv", index=False)
    candidates = []
    for state in rows:
        for candidate_idx in range(16):
            if state["oracle_success"] and not state["maxv_success"]:
                success = candidate_idx == 1
            elif state["maxv_success"]:
                success = True
            else:
                success = False
            candidates.append(
                {
                    "snapshot_id": state["analysis_snapshot_id"],
                    "suite": state["suite"],
                    "task_id": state["task_id"],
                    "task_description": state["task_description"],
                    "init_state_id": state["init_state_id"],
                    "query_idx": state["query_idx"],
                    "phase_at_snapshot": state["phase"],
                    "case_id": state["factor"].lower(),
                    "candidate_idx": candidate_idx,
                    "candidate_value": float(16 - candidate_idx),
                    "terminal_available": True,
                    "terminal_success": success,
                    "terminal_utility_v1": 3.0 if success else 0.0,
                }
            )
    candidate_path = tmp_path / "synthetic__candidate_outcomes.parquet"
    pd.DataFrame(candidates).to_parquet(candidate_path, index=False)

    summary = analyze(
        atlas_dir,
        "proposal_opportunity_k16_test",
        output_dir,
        [candidate_path],
        bootstrap_samples=200,
        seed=7,
    )

    assert summary["states"] == 6
    assert summary["candidate_branches"] == 96
    assert summary["selector_eligible_factors"] == ["Object"]
    assert summary["hard_factor_hypothesis_supported"] is False
    factors = pd.read_csv(output_dir / "factor_summary.csv").set_index("factor")
    assert factors.loc["Object", "success_rescues"] == 2
    assert factors.loc["Object", "oracle_gap_pp"] == 50.0
    assert not bool(factors.loc["Environment", "selector_gate_pass"])
    payload = json.loads((output_dir / "summary.json").read_text())
    assert payload["selector_eligible_factors"] == ["Object"]
    nested = pd.read_csv(output_dir / "nested_budget_summary.csv")
    assert set(nested["budget"]) == {4, 8, 16}
    assert set(nested["factor"]) == {"Environment", "Object"}
    assert (output_dir / "k16_opportunity_summary.png").stat().st_size > 0
    assert "NOT SUPPORTED" in (output_dir / "RESULTS.md").read_text()

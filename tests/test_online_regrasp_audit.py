import pandas as pd
import pytest

from scripts.audit_online_regrasp import normalize, validate_branches, validate_queries


def fixture():
    case = dict(case_id="c", suite="libero_object_temp", split="holdout",
                position_level="x0.2", task_id=2, init_state_id=35, rollout_id=0,
                rollout_seed=123, independent_group="x0.2|task2|init35")
    baseline = dict(**case, strategy="baseline_h8", prefix_state_sha256="same",
                    snapshot_replay_max_abs=0.0, terminal_success=0,
                    terminal_final_t=80, terminal_continuation_queries=1,
                    primitive_steps=0, trigger_passed=0, intervention_applied=0,
                    counterfactual_reused=0, terminal_target_drop_candidate=0,
                    terminal_wrong_object_interaction_candidate=0,
                    terminal_official_safety_violation=0)
    method = dict(baseline, strategy="workspace_calibrated", counterfactual_reused=1)
    queries = []
    for idx, t in enumerate([0, 16, 32, 48, 64, 72]):
        queries.append(dict(**case, strategy="common_prefix" if idx < 5 else "baseline_h8",
                            query_idx=idx, query_t=t, executed_steps=16 if idx < 4 else 8,
                            query_seed_values=str([123 + idx * 1000 + k for k in range(4)])))
    return pd.DataFrame([baseline, method]), pd.DataFrame([case]), pd.DataFrame(queries)


def test_valid_fallback_and_query_budget():
    branches, manifest, queries = fixture()
    assert validate_branches(branches, manifest)["cases"] == 1
    validate_queries(branches, queries)


def test_reject_duplicate_raw_rows():
    branches, manifest, _ = fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        validate_branches(pd.concat([branches, branches.iloc[:1]]), manifest)


@pytest.mark.parametrize("column,value,message", [
    ("rollout_seed", 999, "Manifest mismatch"),
    ("prefix_state_sha256", "different", "Different prefix"),
    ("terminal_success", 1, "Fallback changed"),
])
def test_reject_mispaired_or_changed_fallback(column, value, message):
    branches, manifest, _ = fixture()
    branches.loc[1, column] = value
    with pytest.raises(ValueError, match=message):
        validate_branches(branches, manifest)


def test_reject_unaccounted_primitive_steps():
    branches, _, queries = fixture()
    branches.loc[0, "primitive_steps"] = 3
    with pytest.raises(ValueError, match="timing"):
        validate_queries(branches, queries)


def test_reject_changed_suffix_seeds():
    branches, _, queries = fixture()
    queries.loc[5, "query_seed_values"] = "[1, 2, 3, 4]"
    with pytest.raises(ValueError, match="seeds"):
        validate_queries(branches, queries)


def test_missing_success_is_not_a_failure_label():
    branches, _, _ = fixture()
    branches.loc[1, "terminal_success"] = None
    with pytest.raises(ValueError, match="boolean"):
        normalize(branches)

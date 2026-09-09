import pandas as pd
import pytest

from scripts.analyze_consensus_medoid_results import validate_episodes


def complete_trace():
    return pd.DataFrame([
        {
            "suite": "libero_object_object", "task_id": 0,
            "init_state_id": 0, "rollout_seed": 10,
            "planning_strategy": "first", "query_idx": q,
            "success": True, "final_t": 10, "num_queries": 2,
            "t": q * 5, "t_after": (q + 1) * 5, "executed_steps": 5,
        }
        for q in range(2)
    ])


def test_complete_episode_counts_once():
    episodes = validate_episodes(complete_trace(), 1, {"first": 1})
    assert len(episodes) == 1
    assert bool(episodes.success.iloc[0])


def test_duplicate_execution_is_not_silently_merged():
    traces = complete_trace()
    with pytest.raises(ValueError, match="Duplicate query"):
        validate_episodes(pd.concat([traces, traces]), 1, {"first": 1})


def test_partial_episode_cannot_enter_sr():
    with pytest.raises(ValueError, match="Partial episode"):
        validate_episodes(complete_trace().iloc[:1], 1, {"first": 1})


def test_conflicting_outcomes_rejected():
    traces = complete_trace()
    traces.loc[1, "success"] = False
    with pytest.raises(ValueError, match="Conflicting episode metadata"):
        validate_episodes(traces, 1, {"first": 1})


def test_timeline_gap_rejected():
    traces = complete_trace()
    traces.loc[1, "t"] = 6
    with pytest.raises(ValueError, match="Discontinuous simulator timeline"):
        validate_episodes(traces, 1, {"first": 1})


def test_missing_init_coverage_rejected():
    with pytest.raises(ValueError, match="initial-state coverage"):
        validate_episodes(complete_trace(), 2, {"first": 1})

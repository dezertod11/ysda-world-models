import pandas as pd

from scripts.analyze_perception_regrasp_comparison import build_pairs, summarize_pairs


def _frame(proposal: str, outcomes: list[bool]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_uid": [f"row-{index}" for index in range(len(outcomes))],
            "independent_group": [f"group-{index}" for index in range(len(outcomes))],
            "position_level": ["y0.2"] * len(outcomes),
            "task_id": [4] * len(outcomes),
            "proposal": [proposal] * len(outcomes),
            "terminal_success": outcomes,
            "terminal_failure_type": ["success" if value else "timeout" for value in outcomes],
        }
    )


def test_paired_comparison_counts_upper_bound_coverage():
    learned = _frame("perception_regrasp_h8", [True, True, False, False])
    reference = _frame("privileged_regrasp_h8", [True, False, True, False])

    paired = build_pairs(learned, reference)
    summary = summarize_pairs(paired, bootstrap_repetitions=100, seed=7)

    assert summary["both_success"] == 1
    assert summary["learned_only_success"] == 1
    assert summary["privileged_only_success"] == 1
    assert summary["neither_success"] == 1
    assert summary["privileged_success_coverage"] == 0.5
    assert summary["learned_minus_privileged"] == 0.0

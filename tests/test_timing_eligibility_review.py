import pandas as pd
import pytest

from scripts.review_timing_eligibility import gate_partition, pair_cases


def test_gate_partition_uses_eligible_states_and_separates_success():
    rows = []
    for eligible, fresh, checked, success in [
        (True, True, True, False), (True, False, True, False),
        (True, False, False, False), (True, False, False, True),
        (False, False, True, False),
    ]:
        rows.append(dict(arm='delayed_regrasp_h8', original_eligible=eligible,
            intervention=dict(fresh_gate_evaluated_after_success=success,
                              fresh_gate={'passed': fresh}, fresh_nonmiss_gate={'passed': checked})))
    assert gate_partition(pd.DataFrame(rows)) == dict(initial_eligible=4, fresh_pass=1,
        miss_only_block=1, other_block=1, success_during_delay=1)


def test_pair_cases_orients_help_and_harm_and_requires_complete_pairs():
    rows = [dict(job_id=case, arm=arm, terminal_success=success)
            for case, left, right in [('a', True, False), ('b', False, True), ('c', True, True)]
            for arm, success in [('left', left), ('right', right)]]
    data = pd.DataFrame(rows)
    assert pair_cases(data, 'left', 'right') == dict(rescues=['a'], harms=['b'])
    with pytest.raises(ValueError, match='Incomplete'):
        pair_cases(data.iloc[:-1], 'left', 'right')

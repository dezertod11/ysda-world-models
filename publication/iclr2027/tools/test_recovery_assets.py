"""Recovery publication checks preserve full support and pair arithmetic."""
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("recovery_assets", Path(__file__).with_name("recovery_assets.py"))
ASSETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSETS)


def test_confirmation_pair_arithmetic():
    row = ASSETS.checked_pair("final", 64, 16, 41, 27, 2, 29.6875, 48.4375)
    assert row["delta_pp"] == pytest.approx(39.0625)


@pytest.mark.parametrize("values", [
    (64, 16, 41, 28, 2, 29, 49),
    (64, 16, 65, 50, 1, 20, 90),
    (64, 16, 41, 27, 2, -4, 2),
    (64, 16, 41, 50, 25, 29, 49),
])
def test_invalid_counts_or_interval_rejected(values):
    with pytest.raises(ValueError):
        ASSETS.checked_pair("bad", *values)


def test_all_frozen_cells_retained():
    data = pd.read_csv(ASSETS.INPUTS["cells"])
    wide = ASSETS.checked_cells(data)
    assert len(wide) == 8
    assert wide.continue_h8.sum() == 16
    assert wide.physical_regrasp.sum() == 41


def test_cell_effects_preserve_comparator_reversals():
    wide = ASSETS.checked_cells(pd.read_csv(ASSETS.INPUTS["cells"]))
    rows = ASSETS.cell_contrasts(wide)
    assert sum(r["net_vs_h8"] for r in rows) == 25
    assert sum(r["net_vs_h16"] for r in rows) == 24
    assert sum(r["net_vs_h8"] > 0 for r in rows) == 6
    assert sum(r["net_vs_h16"] > 0 for r in rows) == 5
    case = next(r for r in rows if r["cell"] == "x0.2_t6")
    assert case["net_vs_h8"] == 1 and case["net_vs_h16"] == -1


def test_dropping_a_cell_fails_closed():
    data = pd.read_csv(ASSETS.INPUTS["cells"])
    with pytest.raises(ValueError):
        ASSETS.checked_cells(data[data.cell.ne(ASSETS.CELLS[0])])


def test_dropping_a_control_fails_closed():
    data = pd.read_csv(ASSETS.INPUTS["cells"])
    with pytest.raises(ValueError):
        ASSETS.checked_cells(data[data.arm.ne("refresh_preserve_only")])


def test_duplicated_rows_fail_closed():
    data = pd.read_csv(ASSETS.INPUTS["cells"])
    with pytest.raises(ValueError):
        ASSETS.checked_cells(pd.concat([data, data.iloc[:1]]))


def test_publication_keeps_boundary_and_gate_tables():
    assert "recovery_oracle.tex" in ASSETS.TABLES
    assert "recovery_confirmation.tex" in ASSETS.TABLES
    assert "recovery_cells.tex" in ASSETS.TABLES
    assert "recovery_gate.tex" in ASSETS.TABLES
    assert "consensus_scores.tex" not in ASSETS.TABLES


def test_full_broad_table_preserves_macro_denominator():
    import json
    scores = pd.read_csv(ASSETS.INPUTS['broad_scores'])
    summary = json.loads(ASSETS.INPUTS['broad_summary'].read_text())
    rows = ASSETS.checked_broad(scores, summary)
    assert rows[1][-2:] == ['53.42','93/199']
    assert rows[3][-2:] == ['54.10','96/199']
    assert 'recovery_broad.tex' in ASSETS.TABLES


def test_partial_or_changed_broad_support_is_rejected():
    import json
    scores = pd.read_csv(ASSETS.INPUTS['broad_scores'])
    summary = json.loads(ASSETS.INPUTS['broad_summary'].read_text())
    with pytest.raises(ValueError):
        ASSETS.checked_broad(scores, dict(summary, complete=False))
    with pytest.raises(ValueError):
        ASSETS.checked_broad(scores.iloc[:-1], summary)


def test_legacy_broad_cohort_cannot_replace_corrected_runtime():
    import json
    scores = pd.read_csv(ASSETS.INPUTS['broad_scores'])
    summary = json.loads(ASSETS.INPUTS['broad_summary'].read_text())
    with pytest.raises(ValueError, match='corrected runtime'):
        ASSETS.checked_broad(scores, dict(summary, config_sha256='legacy'))


def test_supporting_feedback_is_not_marked_as_v2():
    result = ASSETS.checked_feedback(pd.read_csv(ASSETS.INPUTS['feedback_endpoint']))
    assert (result['control'], result['feedback'], result['n']) == (46, 64, 100)
    assert result['corrected_runtime_audit_complete'] is False


def test_feedback_cannot_drop_harms():
    data = pd.read_csv(ASSETS.INPUTS['feedback_endpoint'])
    data.loc[0, 'harms'] = 0
    with pytest.raises(ValueError):
        ASSETS.checked_feedback(data)

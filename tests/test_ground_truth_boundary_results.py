import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_ground_truth_boundary_results import auc_score, benjamini_hochberg


def test_auc_score_uses_failure_as_positive_class():
    assert auc_score([False, False, True, True], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc_score([False, False, True, True], [0.8, 0.9, 0.1, 0.2]) == 0.0


def test_auc_score_handles_ties():
    assert auc_score([False, True], [1.0, 1.0]) == pytest.approx(0.5)


def test_benjamini_hochberg_is_monotone_in_rank_order():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, np.nan])
    assert adjusted[:3].tolist() == pytest.approx([0.03, 0.04, 0.04])
    assert np.isnan(adjusted[3])

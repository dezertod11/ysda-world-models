"""Focused tests for numerical publication assets and the portable TeX package."""

import importlib.util
import zipfile
from pathlib import Path

import pandas as pd
import pytest


SPEC = importlib.util.spec_from_file_location("publication_build", Path(__file__).with_name("build.py"))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


def fixture_scores():
    return pd.DataFrame({"arm": ["a"] * 3, "factor": ["Object", "Environment", "Position"],
                         "n": [30, 30, 60], "successes": [28, 15, 31],
                         "micro_sr": [28 / 30, 15 / 30, 31 / 60]})


def check(scores):
    return BUILD.checked_factor_rows(scores, {"a": "Example"},
                                    {"Object": 30, "Environment": 30, "Position": 60},
                                    {"a": [28, 15, 31]})


def test_macro_is_not_micro_on_h8_subset():
    row = check(fixture_scores())[0]
    assert row["macro_sr"] == pytest.approx(.65)
    assert row["micro_sr"] == pytest.approx(74 / 120)
    assert row["n"] == 120 and row["successes"] == 74


@pytest.mark.parametrize("column,value", [("n", 60), ("successes", 27), ("micro_sr", .5)])
def test_changed_data_fail_closed(column, value):
    scores = fixture_scores()
    scores.loc[0, column] = value
    with pytest.raises(AssertionError):
        check(scores)


def test_duplicate_factor_fails():
    scores = fixture_scores()
    with pytest.raises(AssertionError):
        check(pd.concat([scores, scores.iloc[:1]]))


def test_missing_factor_fails():
    with pytest.raises(KeyError):
        check(fixture_scores().iloc[:2])


def test_unexpected_arm_fails():
    scores = fixture_scores()
    scores.loc[0, "arm"] = "unreviewed"
    with pytest.raises(AssertionError):
        check(scores)


def test_table_uses_macro_and_counts(tmp_path):
    target = tmp_path / "table.tex"
    BUILD.write_count_table(target, check(fixture_scores()))
    assert "Example & 28 & 15 & 31 & 74 & 65.00" in target.read_text()


def test_package_excludes_logs_secrets_and_caches(tmp_path):
    stage = tmp_path / "source"
    stage.mkdir()
    for name in ["main.tex", "iclr2027.tex", "references.bib", "test.sty", "test.bst",
                 "token.env", ".secret", "trace.log", "cached.pyc"]:
        (stage / name).write_text("fixture")
    archive = BUILD.package_sources(stage, tmp_path)
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {"main.tex", "iclr2027.tex", "references.bib",
                                         "test.sty", "test.bst", "README.txt"}
        assert "not a submitted paper" in bundle.read("README.txt").decode()

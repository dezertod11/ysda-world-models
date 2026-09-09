from __future__ import annotations

import json
from pathlib import Path

from scripts.run_libero_experiment_campaign import build_job, expand_jobs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT
    / "experiments"
    / "configs"
    / "libero_campaign_p4b_terminal_candidates_20260907.json"
)


def test_p4b_terminal_config_matches_frozen_protocol(tmp_path: Path) -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    jobs = payload["profiles"]["p4b_terminal_candidates"]["jobs"]
    defaults = payload["defaults"]

    assert len(jobs) == 6
    assert {int(job["gpu_slot"]) for job in jobs} == set(range(6))
    assert sum(int(job["target_decision_states"]) for job in jobs) == 200
    assert {job["suites"] for job in jobs} == {
        "libero_object_object",
        "libero_object_env",
        "libero_object_temp",
    }
    assert {
        job.get("position_level") for job in jobs if "position_level" in job
    } == {"x0.1", "y0.1", "x0.3", "y0.3"}

    assert defaults["uncertainty_seeds"] == "0,1,2,3"
    assert defaults["open_loop_steps"] == 16
    assert defaults["sampling_mode"] == "fixed_queries"
    assert defaults["snapshot_query_indices"] == "3"
    assert defaults["terminal_continuation_fraction"] == 1.0
    assert defaults["terminal_selected_feedback_only"] is False
    assert defaults["continuation_num_candidates"] == 1
    assert defaults["skip_feedback_branch"] is True
    assert defaults["experiment_split"] == "holdout"

    expanded = expand_jobs(payload["profiles"]["p4b_terminal_candidates"], defaults)
    for job in expanded:
        _commands, environment, _marker = build_job(job, "p4b-config-test", tmp_path)
        assert environment["LIBERO_PRO_VOF_OPEN_LOOP_STEPS"] == "16"
        assert environment["LIBERO_PRO_VOF_SNAPSHOT_QUERY_INDICES"] == "3"
        assert environment["LIBERO_PRO_VOF_TERMINAL_CONTINUATION_FRACTION"] == "1.0"
        assert environment["LIBERO_PRO_VOF_TERMINAL_SELECTED_FEEDBACK_ONLY"] == "0"
        assert environment["LIBERO_PRO_VOF_CONTINUATION_NUM_CANDIDATES"] == "1"
        assert environment["LIBERO_PRO_VOF_SKIP_FEEDBACK_BRANCH"] == "1"

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_libero_experiment_campaign import build_job, expand_jobs


ROOT = Path(__file__).resolve().parents[1]
CONFIG = (
    ROOT / "experiments" / "configs" / "libero_campaign_p4_standard_id_20260906.json"
)


def test_p4_standard_id_config_matches_frozen_protocol(tmp_path: Path) -> None:
    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    jobs = payload["profiles"]["p4_standard_id"]["jobs"]
    defaults = payload["defaults"]

    assert len(jobs) == 10
    assert {int(job["task_ids"]) for job in jobs} == set(range(10))
    assert all(job["kind"] == "pro_counterfactual_feedback" for job in jobs)
    assert all(job["suites"] == "libero_object" for job in jobs)
    assert all(job["init_state_ids"] == "0-39" for job in jobs)
    assert all(int(job["rollouts_per_init"]) == 2 for job in jobs)
    assert all(int(job["target_decision_states"]) == 80 for job in jobs)
    assert {int(job["gpu_slot"]) for job in jobs} == {0, 1, 2, 3}

    assert defaults["uncertainty_seeds"] == "0,1,2,3"
    assert defaults["sampling_mode"] == "fixed_queries"
    assert defaults["snapshot_query_indices"] == "0,3,6,9"
    assert defaults["open_loop_steps"] == 16
    assert defaults["consequence_horizon_steps"] == 16
    assert defaults["terminal_continuation_fraction"] == 0.0
    assert defaults["continuation_num_candidates"] == 0
    assert defaults["skip_feedback_branch"] is True
    assert defaults["prediction_mode"] == "parallel"
    assert defaults["experiment_split"] == "development"

    expanded = expand_jobs(payload["profiles"]["p4_standard_id"], defaults)
    _commands, environment, _marker = build_job(expanded[0], "p4-config-test", tmp_path)
    assert environment["LIBERO_PRO_VOF_OPEN_LOOP_STEPS"] == "16"

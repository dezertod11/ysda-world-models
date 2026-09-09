from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/configs/libero_campaign_frozen_h16_closed_loop.json"
MODEL = ROOT / "experiments/frozen_models/factor_h16_dense_ridge_v1.json"


def _count(spec: str) -> int:
    total = 0
    for token in spec.split(","):
        if "-" in token:
            start, end = map(int, token.split("-", 1))
            total += end - start + 1
        else:
            total += 1
    return total


def test_closed_loop_config_has_the_preregistered_360_pairs() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    profile = config["profiles"]["frozen_h16_closed_loop_full"]
    pairs = {"Environment": 0, "Object": 0, "Position": 0}
    for job in profile["jobs"]:
        factor = job["planning_frozen_ranker_factor"]
        pairs[factor] += (
            _count(job["task_ids"])
            * _count(job["init_state_ids"])
            * int(job["max_rollouts"])
        )

    assert pairs == {"Environment": 120, "Object": 120, "Position": 120}
    assert sum(pairs.values()) == 360
    defaults = config["defaults"]
    assert defaults["strategy_lambdas"] == "max_value:0 frozen_factor_ridge:0"
    assert defaults["uncertainty_seeds"] == "0,1,2,3,4,5"
    assert defaults["num_open_loop_steps"] == 16
    assert defaults["num_denoising_steps_action"] == 5
    assert defaults["max_timesteps"] == 280


def test_frozen_model_payload_hash_is_self_consistent() -> None:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    expected = model.pop("frozen_payload_sha256")
    payload = json.dumps(model, sort_keys=True, separators=(",", ":")).encode("utf-8")

    assert hashlib.sha256(payload).hexdigest() == expected
    assert expected == "086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb"

"""Validate downloaded S0 outcomes and export descriptive diagnostics, not new tests."""
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from p3_benchmark import ARMS, FACTORS

CAMPAIGN = ROOT / "experiments/campaigns/p3_benchmark_runtime_v2_20260915_s0"
OLD = ROOT / "experiments/campaigns/p3_benchmark_closure_20260914_v3"
SHA = "10d8f0530edaaa024e734769d007553659bfe1bd7060e5f3f936805239293446"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert digest(CAMPAIGN / "config.json") == SHA
    config = json.loads((CAMPAIGN / "config.json").read_text())
    summary = json.loads((CAMPAIGN / "analysis/summary.json").read_text())
    assert summary["complete"] and summary["matched_cases"] == 199
    rows, parity, changes = [], [], []
    verified = 0
    for job in config["jobs"]:
        if job["phase"] != "main":
            continue
        folder = CAMPAIGN / "main" / job["id"]
        marker = json.loads((folder / "completed.json").read_text())
        assert marker["audit_pass"] and marker["config_sha256"] == SHA
        records = {}
        for arm in ARMS:
            record = json.loads((folder / (arm + ".json")).read_text())
            assert record["job"] == job and record["config_sha256"] == SHA
            for suffix, key in ((".mp4", "video_sha256"), (".npz", "npz_sha256")):
                assert digest(folder / (arm + suffix)) == record[key]
                verified += 1
            rows.append(dict(id=job["id"], factor=job["factor"], arm=arm,
                success=record["success"], queries=record["model_calls"],
                candidates=record["logical_candidates"],
                interventions=sum(e["executed"] and e["physical_steps"] > 0 for e in record["events"]),
                episode_drop_proxy=record["terminal_episode_target_drop_candidate"]))
            old = json.loads((OLD / "main" / job["id"] / (arm + ".json")).read_text())
            assert old["job"] == job
            if record["success"] != old["success"]:
                changes.append(dict(id=job["id"], factor=job["factor"], arm=arm,
                    old_success=old["success"], new_success=record["success"]))
            records[arm] = record
        assert len({r["initial_sha256"] for r in records.values()}) == 1
        h16, event = records["max_value_h16"], records["p3_event"]
        assert not any(e["executed"] and e["physical_steps"] > 0 for e in event["events"])
        a = [(q["t"], q["metadata"]["input_hashes"]) for q in h16["queries"]]
        b = [(q["t"], q["metadata"]["input_hashes"]) for q in event["queries"]]
        assert a == b
        assert h16["video_sha256"] == event["video_sha256"]
        parity.append(dict(id=job["id"], identical_query_inputs=True, identical_video=True))

    data = pd.DataFrame(rows)
    assert len(data) == 995 and not data.duplicated(["id", "arm"]).any()
    saved = pd.read_csv(CAMPAIGN / "analysis/episode_outcomes.csv")
    pd.testing.assert_series_equal(data.set_index(["id", "arm"]).success.sort_index(),
                                   saved.set_index(["id", "arm"]).success.sort_index())
    counts = data.groupby(["arm", "factor"]).success.agg(["size", "sum", "mean"])
    for arm in ARMS:
        assert counts.loc[arm, "size"].to_dict() == dict(Environment=50, Object=50, Position=99)
    out = HERE / "review_20260915"
    out.mkdir(exist_ok=True)
    counts.to_csv(out / "factor_counts.csv")
    pd.DataFrame(changes, columns=["id", "factor", "arm", "old_success", "new_success"]).to_csv(
        out / "v1_v2_outcome_changes.csv", index=False)
    pd.DataFrame(parity).to_csv(out / "event_parity.csv", index=False)
    costs = data.groupby("arm").agg(successes=("success", "sum"),
        queries_mean=("queries", "mean"), candidates_mean=("candidates", "mean"),
        interventions=("interventions", "sum"), episode_drop_proxy=("episode_drop_proxy", "sum"))
    costs.to_csv(out / "cost_and_episode_proxies.csv")
    wide = data.pivot(index=["factor", "id"], columns="arm", values="success")
    effects = []
    for factor, part in wide.groupby(level="factor"):
        for arm in ("h8_at72", "p3_at72", "p3_event"):
            delta = part[arm].astype(int) - part.max_value_h16.astype(int)
            effects.append(dict(factor=factor, arm=arm, pairs=len(part),
                rescues=int(delta.eq(1).sum()), harms=int(delta.eq(-1).sum()), delta_pp=100 * delta.mean()))
    effects = pd.DataFrame(effects)
    effects.to_csv(out / "factor_rescue_harm.csv", index=False)
    coverage = pd.read_csv(HERE / "publication_audit/event_coverage_by_seed.csv").iloc[0]
    assert coverage.episodes == 199
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    part = effects[effects.arm.eq("p3_at72")].set_index("factor").loc[list(FACTORS)]
    bars = axes[0].bar(part.index, part.delta_pp, color=["#af4145", "#ba8530", "#287a83"])
    axes[0].bar_label(bars, labels=[f"{x:+.2f} pp" for x in part.delta_pp], padding=4)
    axes[0].axhline(0, color="#555555", lw=.8)
    axes[0].set(ylim=(-6, 6), ylabel="SR difference (percentage points)", title="P3 fixed - H16, corrected runtime")
    keys = ("episodes", "supported_target", "localization_valid_episode", "grasp_attempt_episode",
            "attempt_and_miss_episode", "persistent_miss_episode", "physical_interventions")
    bars = axes[1].barh(range(len(keys)), [int(coverage[k]) for k in keys], color="#287a83")
    axes[1].bar_label(bars, padding=3)
    axes[1].set(yticks=range(len(keys)), yticklabels=["All", "Supported", "Localized", "Attempt",
        "Attempt + miss", "Persistent miss", "Recovery"], xlim=(0, 230), title="Event evidence (episode counts)")
    axes[1].invert_yaxis()
    fig.savefig(out / "effect_and_coverage.png", dpi=160)
    plt.close(fig)
    validation = dict(config_sha256=SHA, cases=199, outcomes=995,
        verified_video_and_npz_hashes=verified, event_input_and_video_parity_cases=len(parity),
        v1_v2_changed_outcomes=changes, local_video_decode_repeated=False,
        sources={name: digest(CAMPAIGN / "analysis" / name) for name in
                 ("summary.json", "episode_outcomes.csv", "paired_effects.csv")})
    (out / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation, indent=2))
    print(costs.to_string())
    print(effects.to_string(index=False))


if __name__ == "__main__":
    main()

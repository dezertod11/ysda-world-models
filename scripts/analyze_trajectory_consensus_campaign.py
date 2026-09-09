#!/usr/bin/env python3
"""Validate complete rollouts, compare paired strategies, and freeze development winner."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import binomtest


KEYS = ["case_id", "suite", "task_id", "init_state_id", "rollout_seed"]
STATIC = ["success", "final_t", "num_queries", "target_drop_candidate", "failure_type",
          "official_safety_violation", "prediction_mode", "num_open_loop_steps"]


def load_episodes(campaign: Path):
    manifest = json.loads((campaign / "manifest.json").read_text())
    config = json.loads(Path(manifest["config"]).read_text())
    definitions = {j["name"]: j for j in config["profiles"][manifest["profile"]]["jobs"]}
    methods = json.loads(Path(manifest["config"]).with_suffix(".methods.json").read_text())
    if manifest["profile"] == "full":
        methods.append({"label": "winner"})
    if manifest["status"] != "completed":
        raise ValueError("Campaign incomplete; freezing and final reporting require all jobs")
    episodes, query_rows = [], []
    for job in manifest["jobs"]:
        definition = definitions[job["name"]]
        matches = [m for m in methods if job["name"].endswith("_" + m["label"])]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous method label: {job['name']}")
        label = matches[0]["label"]
        prefix = job["environment"]["LIBERO_PRO_PLANNING_GRID_PREFIX"]
        paths = list((campaign / "runs").glob(prefix + "__*__query_traces.parquet"))
        if len(paths) != 1:
            raise ValueError(f"Expected one trace per job: {job['name']}")
        columns = [*KEYS, *STATIC, "query_idx", "t", "t_after", "executed_steps", "max_value_selected",
                   "video_path", "replay_video_path", "prediction_error_horizon_aligned", "sim_state_json", "task_description",
                   "candidate_action_chunks_json"]
        available = pq.read_schema(paths[0]).names
        x = pd.read_parquet(paths[0], columns=[c for c in columns if c in available])
        if x.duplicated([*KEYS, "query_idx"]).any():
            raise ValueError(f"Duplicate queries: {paths[0]}")
        for key, g in x.groupby(KEYS):
            g = g.sort_values("query_idx")
            if not np.array_equal(g.query_idx, np.arange(len(g))) or not g.num_queries.eq(len(g)).all():
                raise ValueError("Missing query or partial episode")
            if any(g[c].nunique() != 1 for c in ["success", "final_t", "num_queries"]):
                raise ValueError("Conflicting episode outcome")
            if g.t.iloc[0] != 0 or g.t_after.iloc[-1] != g.final_t.iloc[-1]:
                raise ValueError("Truncated simulator timeline")
            if not np.array_equal(g.t_after.iloc[:-1], g.t.iloc[1:]):
                raise ValueError("Discontinuous simulator timeline")
            if not np.array_equal(g.t_after - g.t, g.executed_steps):
                raise ValueError("Wrong executed chunk lengths")
            if not g.num_open_loop_steps.eq(16).all():
                raise ValueError("H16 execution contract changed")
            video = Path(g.video_path.iloc[0])
            if not video.is_file() or video.stat().st_size < 1024:
                raise ValueError(f"Missing episode video: {video}")
        e = x[x.query_idx.eq(0)].copy()
        if "candidate_action_chunks_json" in e:
            e["q0_action_pool_sha256"] = e.candidate_action_chunks_json.map(
                lambda s: hashlib.sha256(np.asarray(json.loads(s), dtype="<f8").tobytes()).hexdigest())
            e = e.drop(columns="candidate_action_chunks_json")
        expected_ids = definition["init_state_ids"]
        lo, hi = map(int, expected_ids.split("-")) if "-" in expected_ids else (int(expected_ids), int(expected_ids))
        if len(e) != hi - lo + 1 or set(e.init_state_id) != set(range(lo, hi + 1)):
            raise ValueError("Incomplete init coverage")
        factor = "Position" if "position" in job["kind"] else "Environment" if "environment" in job["kind"] else "Object"
        e["method"] = label
        e["factor"] = factor
        e["source_trace"] = str(paths[0])
        e["new_init_relative_to_development"] = e.init_state_id >= (1 if factor == "Position" else 2)
        episodes.append(e)
        marker_path = job.get("completion_marker")
        job_seconds = float("nan")
        reused = False
        if marker_path and Path(marker_path).exists():
            marker = json.loads(Path(marker_path).read_text())
            reused = bool(marker.get("reused", False))
            job_seconds = (datetime.fromisoformat(marker["finished_at"]) -
                           datetime.fromisoformat(marker["started_at"])).total_seconds()
        query_rows.append(dict(method=label, factor=factor, queries=len(x),
                               switched=int((~x.max_value_selected.astype(bool)).sum()),
                               aligned_prediction_queries=int(x.prediction_error_horizon_aligned.sum()),
                               job_seconds=job_seconds, episodes=len(e),
                               reused_episodes=len(e) if reused else 0,
                               reused_queries=len(x) if reused else 0))
    return pd.concat(episodes, ignore_index=True), pd.DataFrame(query_rows), methods


def interval(paired, repeats=5000):
    # Resample task/init clusters within each perturbation factor; Position levels stay together.
    rng = np.random.default_rng(20260908)
    estimates = np.zeros(repeats)
    for _, factor in paired.groupby("factor"):
        clusters = factor.groupby(["task_id", "init_state_id"]).delta.agg(["sum", "count"])
        sampled = rng.integers(0, len(clusters), size=(repeats, len(clusters)))
        estimates += clusters["sum"].to_numpy()[sampled].sum(axis=1) / clusters["count"].to_numpy()[sampled].sum(axis=1)
    estimates /= paired.factor.nunique()
    return np.quantile(estimates, [.025, .975]).tolist()


def analyze(campaign: Path, freeze: Path | None = None):
    campaign = campaign.resolve()
    episodes, queries, methods = load_episodes(campaign)
    output = campaign / "trajectory_analysis"
    output.mkdir(exist_ok=True)
    summary = episodes.groupby(["factor", "method"], as_index=False).agg(
        episodes=("success", "size"), successes=("success", "sum"), sr=("success", "mean"),
        drops=("target_drop_candidate", "sum"), drop_rate=("target_drop_candidate", "mean"),
        mean_queries=("num_queries", "mean"), mean_final_t=("final_t", "mean"),
    )
    pairs, comparisons = [], []
    for left, right in itertools.combinations(sorted(episodes.method.unique()), 2):
        a = episodes[episodes.method.eq(left)]
        b = episodes[episodes.method.eq(right)]
        merged = a.merge(b, on=[*KEYS, "factor"], suffixes=("_reference", "_method"), validate="one_to_one")
        if len(merged) != len(a) or len(merged) != len(b):
            raise ValueError("Cross-strategy pairing incomplete")
        for state_a, state_b in zip(merged.sim_state_json_reference, merged.sim_state_json_method):
            if not np.allclose(json.loads(state_a), json.loads(state_b), rtol=0, atol=1e-9):
                raise ValueError("Paired strategies do not share their initial simulator state")
        merged["delta"] = merged.success_method.astype(int) - merged.success_reference.astype(int)
        if "q0_action_pool_sha256_reference" in merged:
            merged["q0_action_pool_exact"] = (merged.q0_action_pool_sha256_reference == merged.q0_action_pool_sha256_method)
        merged["reference"], merged["method"] = left, right
        pairs.append(merged)
        for scope, group in [("All", merged), *merged.groupby("factor")]:
            rescue, harm = int(group.delta.eq(1).sum()), int(group.delta.eq(-1).sum())
            low, high = interval(group)
            comparisons.append(dict(
                reference=left, method=right, scope=scope, episodes=len(group),
                macro_delta=float(group.groupby("factor").delta.mean().mean()),
                ci95_low=low, ci95_high=high, rescues=rescue, harms=harm,
                q0_action_pool_exact_rate=float(group.q0_action_pool_exact.mean()) if "q0_action_pool_exact" in group else float("nan"),
                mcnemar_exact_p=float(binomtest(rescue, rescue + harm).pvalue) if rescue + harm else 1.,
            ))
    effects = pd.DataFrame(comparisons)
    episodes.to_csv(output / "episode_outcomes.csv", index=False)
    summary.to_csv(output / "factor_scores.csv", index=False)
    effects.to_csv(output / "paired_effects.csv", index=False)
    pd.concat(pairs, ignore_index=True).to_parquet(output / "paired_cases.parquet", index=False)
    queries.to_csv(output / "query_behavior.csv", index=False)
    costs = queries.groupby("method").agg(
        job_seconds=("job_seconds", "sum"), queries=("queries", "sum"),
        episodes=("episodes", "sum"), switched=("switched", "sum"),
        reused_episodes=("reused_episodes", "sum"), reused_queries=("reused_queries", "sum"),
    )
    costs["switch_rate"] = costs.switched / costs.queries
    costs["job_seconds_per_episode"] = costs.job_seconds / (costs.episodes - costs.reused_episodes).replace(0, np.nan)
    costs["job_seconds_per_query"] = costs.job_seconds / (costs.queries - costs.reused_queries).replace(0, np.nan)
    costs.to_csv(output / "cost_and_switch_rates.csv")
    episodes.groupby(["factor", "task_id", "method"]).success.agg(["size", "sum", "mean"]).to_csv(output / "task_scores.csv")
    episodes[episodes.new_init_relative_to_development].groupby(["factor", "method"]).success.agg(["size", "sum", "mean"]).to_csv(output / "reserved_init_scores.csv")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pivot = summary.pivot(index="factor", columns="method", values="sr")
    ax = pivot.plot.bar(figsize=(11, 5), ylim=(0, 1), ylabel="Success rate", rot=0)
    ax.set_title("LIBERO-PRO Object suite: perturbation factors, H16")
    ax.figure.tight_layout()
    ax.figure.savefig(output / "factor_success_rates.png", dpi=170)
    plt.close(ax.figure)
    video_paths = sorted((campaign / "videos").rglob("*.mp4"))
    (output / "video_index.json").write_text(json.dumps([str(p.relative_to(campaign)) for p in video_paths], indent=2))
    if len(video_paths) != len(episodes):
        raise ValueError("Video count does not match the completed episode count")
    import imageio.v2 as imageio
    for _, group in episodes.groupby("method"):
        video = Path(group.video_path.iloc[0])
        with imageio.get_reader(video) as reader:
            if reader.count_frames() != int(group.final_t.iloc[0]):
                raise ValueError(f"Truncated video: {video}")
            if np.std(reader.get_data(0)) < 1:
                raise ValueError(f"Blank video: {video}")
    gallery = ["<!doctype html><meta charset='utf-8'><title>Matched trajectory videos</title>",
               "<style>body{font:15px sans-serif;margin:24px} .row{display:flex;flex-wrap:wrap;gap:16px}video{width:340px;max-width:100%}figure{margin:8px 0}</style>",
               "<h1>Matched deployment videos</h1>"]
    for key, group in episodes.groupby(KEYS):
        instruction = group.task_description.iloc[0] if "task_description" in group else ""
        gallery.append("<h2>" + html.escape(str(key)) + "</h2><p>" +
                       html.escape(instruction) + "</p><div class='row'>")
        for row in group.itertuples():
            video = "../" + str(Path(row.video_path).relative_to(campaign))
            gallery.append(f"<figure><figcaption>{html.escape(row.method)}: success={bool(row.success)}</figcaption>"
                           f"<video controls preload='none' src='{html.escape(video, quote=True)}'></video></figure>")
        gallery.append("</div>")
    (output / "videos.html").write_text("\n".join(gallery))
    text = ["# Trajectory consensus campaign", "", f"Campaign: `{campaign.name}`", "",
            "Smoke is integration-only; its single-case intervals cannot establish efficacy. Development selects settings; subsequent evaluation keeps the selected method frozen.", "",
            summary.to_markdown(index=False, floatfmt=".4f"), "",
            "![Factor SR](factor_success_rates.png)", "",
            "[Matched videos, all rollouts](videos.html)", "",
            effects.to_markdown(index=False, floatfmt=".4f"), "",
            costs.reset_index().to_markdown(index=False, floatfmt=".3f"), "",
            "Job wall time includes model loading, rendering, I/O and per-job analysis; not pure neural inference latency.",
            f"Complete episodes: {len(episodes)}. Query rows: {int(queries.queries.sum())}. Videos: {len(video_paths)}.",
            "Matched deployment init/seeds; not common-pool counterfactual branches. Intervals are stratified task/init bootstrap.",
            "q0_action_pool_exact_rate audits bitwise action-pool matching; K1 and K4 pools differ by construction. Differences without any selector switch are not a selector benefit.",
            "Official safety flags from LIBERO-PRO are not an official LIBERO-Safety evaluation."]
    if (campaign / "amendment.json").exists():
        text.insert(4, "Resource-amended compact evaluation: 600 rollouts instead of the original 4500. "
                    "Object/Environment use init2-6; Position uses init1 at all ten levels, across all ten tasks. "
                    "The outcome-independent subset was declared after full collection had started; "
                    "it is not the original full benchmark. See amendment.json and reuse_manifest.json.")
        text.extend(["Cost accounting: reused episodes retain their original outcomes and videos, "
                     "but their historical GPU cost is not included in this campaign's wall time. "
                     "Per-episode/query cost divides only by newly collected episodes/queries. "
                     "Do not compare raw total costs without accounting for reuse."])
    (output / "RESULTS.md").write_text("\n".join(text) + "\n")
    if freeze is not None:
        if "development" not in campaign.name:
            raise ValueError("Only the development phase can select a winner")
        ranked = summary.groupby("method").agg(macro_sr=("sr", "mean"), macro_drop=("drop_rate", "mean"))
        candidates = ranked.loc[[m["label"] for m in methods if m["strategy"].startswith("trajectory_")]].copy()
        baseline_drop = ranked.loc["max_value", "macro_drop"]
        candidates["objective"] = candidates.macro_sr - (candidates.macro_drop - baseline_drop).clip(lower=0)
        candidates = candidates.sort_values(["objective", "macro_drop"], ascending=[False, True], kind="stable")
        label = candidates.index[0]
        chosen = next(dict(m) for m in methods if m["label"] == label)
        chosen["label"] = "winner"
        payload = dict(
            frozen_at=datetime.now(timezone.utc).isoformat(), development_campaign=campaign.name,
            development_label=label, method=chosen, ranking=candidates.reset_index().to_dict("records"),
            development_beats_max_value=bool(candidates.loc[label, "objective"] > ranked.loc["max_value", "macro_sr"]),
            results_sha256=hashlib.sha256((output / "episode_outcomes.csv").read_bytes()).hexdigest(),
        )
        if freeze.exists():
            old = json.loads(freeze.read_text())
            if old["results_sha256"] != payload["results_sha256"] or old["method"] != chosen:
                raise ValueError("Refusing to overwrite an existing freeze with different data/settings")
        else:
            freeze.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    analyze(args.campaign, args.freeze)

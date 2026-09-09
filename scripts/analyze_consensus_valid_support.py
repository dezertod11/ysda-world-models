#!/usr/bin/env python3
"""Analyze six frozen selectors on the structurally available 199-case support."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import pandas as pd

try:
    from scripts.analyze_trajectory_consensus_campaign import KEYS, load_episodes
    from scripts.analyze_consensus_reference_campaign import paired_effects
    from scripts.run_consensus_valid_support_night import ROOT, COMPACT, REFERENCES
except ModuleNotFoundError:
    from analyze_trajectory_consensus_campaign import KEYS, load_episodes
    from analyze_consensus_reference_campaign import paired_effects
    from run_consensus_valid_support_night import ROOT, COMPACT, REFERENCES


def validate_coverage(episodes, compact_only=False):
    expected_methods = {"first_k1", "max_value", "osc_medoid"}
    if not compact_only:
        expected_methods |= {"raw_medoid", "keystone", "kdpe_endpoint"}
    if set(episodes.method) != expected_methods:
        raise ValueError("Unexpected methods")
    for _, rows in episodes.groupby("method"):
        if rows.groupby("factor").size().to_dict() != {"Environment": 50, "Object": 50, "Position": 99}:
            raise ValueError("Incorrect valid-support coverage")
        if rows.duplicated(KEYS).any():
            raise ValueError("Duplicate cases")
        if (rows.case_id.eq("tc2_position_y0.5") & rows.task_id.eq(1)).any():
            raise ValueError("Unavailable cell included")


def main(compact_only=False):
    compact = ROOT / "experiments/campaigns" / COMPACT
    references = ROOT / "experiments/campaigns" / REFERENCES
    a, aq, _ = load_episodes(compact)
    a = a.replace({"method": {"first": "first_k1", "winner": "osc_medoid"}})
    if compact_only:
        episodes = a
        query_costs = aq.assign(campaign=COMPACT)
    else:
        b, bq, _ = load_episodes(references)
        episodes = pd.concat([a, b], ignore_index=True)
        query_costs = pd.concat([aq.assign(campaign=COMPACT), bq.assign(campaign=REFERENCES)])
    validate_coverage(episodes, compact_only)
    effects = paired_effects(episodes)
    out = compact / "trajectory_analysis" if compact_only else references / "matched_analysis"
    out.mkdir(exist_ok=True)
    scores = episodes.groupby(["factor", "method"]).agg(episodes=("success", "size"),
        successes=("success", "sum"), sr=("success", "mean"), drops=("target_drop_candidate", "sum")).reset_index()
    scores.to_csv(out / "factor_scores.csv", index=False)
    effects.to_csv(out / "paired_effects.csv", index=False)
    episodes.to_csv(out / "episode_outcomes.csv", index=False)
    query_costs.to_csv(out / "query_costs.csv", index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ax = (100*scores.pivot(index="factor", columns="method", values="sr")).plot.bar(figsize=(10, 5), rot=0)
    ax.set_ylim(0, 105); ax.set_ylabel("Success rate (%)")
    ax.figure.tight_layout(); ax.figure.savefig(out / "factor_success_rates.png", dpi=160); plt.close(ax.figure)
    methods = int(episodes.method.nunique())
    gallery = ["<!doctype html><meta charset='utf-8'><title>199 matched cases</title>",
        "<style>body{font:15px sans-serif;margin:24px}.row{display:flex;flex-wrap:wrap;gap:12px}video{width:300px}figure{margin:0 0 16px}</style>",
        f"<h1>{methods} selectors, 199 valid configurations</h1><p>y0.5/task1 has no benchmark init states and is excluded from every method.</p>"]
    import imageio.v2 as imageio
    for _, rows in episodes.groupby("method"):
        row = rows.iloc[0]
        with imageio.get_reader(row.video_path) as reader:
            if reader.count_frames() != int(row.final_t) or reader.get_data(0).std() < 1:
                raise ValueError("Truncated or blank representative video")
    for keys, group in episodes.groupby(KEYS):
        gallery.append("<h2>" + html.escape(str(keys)) + "</h2><div class='row'>")
        for row in group.sort_values("method").itertuples():
            gallery.append(f"<figure><figcaption>{html.escape(row.method)}: success={row.success}</figcaption>"
                f"<video controls preload='none' src='{html.escape(row.video_path, quote=True)}'></video></figure>")
        gallery.append("</div>")
    (out / "videos.html").write_text("\n".join(gallery))
    summary = dict(status="completed", rollouts=len(episodes), matched_cases=199, methods=methods,
        support_amendment=json.loads((compact / "support_amendment.json").read_text()),
        original_full600_completed=False, empty_assets_are_not_policy_failures=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    report = ["# Frozen consensus comparison on valid support", "",
        f"{len(episodes)} real closed-loop rollouts: 199 cases x {methods} methods. The original 200-case grid was not completed.",
        "The original y0.5/task1 init asset is empty. Its case is excluded symmetrically, without observing a policy outcome.",
        "H16, joint parallel generation; K4 except K1. No selector settings were tuned on these outcomes.",
        "KDPE is an induced-OSC endpoint adaptation, not the original N100 pose-action experiment.", "",
        scores.to_markdown(index=False, floatfmt=".4f"), "", effects.to_markdown(index=False, floatfmt=".4f"), "",
        "![Factor scores](factor_success_rates.png)", "", "[All matched videos](videos.html)", "",
        "Macro-SR weights factors equally. Bootstrap clusters task/init within factors.",
        "Primary comparisons use Holm-adjusted McNemar p-values; per-factor tests are descriptive.",
        "Q0 matching does not imply identical candidate pools at later queries. Job seconds are not pure inference latency."]
    (out / "RESULTS.md").write_text("\n".join(report)+"\n")
    print(effects[effects.scope.eq("All")].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact-only", action="store_true")
    main(parser.parse_args().compact_only)

#!/usr/bin/env python3
"""Merge complete, frozen compact and reference campaigns without touching inputs."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from scripts.analyze_trajectory_consensus_campaign import KEYS, interval, load_episodes
except ModuleNotFoundError:
    from analyze_trajectory_consensus_campaign import KEYS, interval, load_episodes


def paired_effects(episodes):
    baseline = episodes[episodes.method.eq("max_value")]
    effects = []
    for method, rows in episodes.groupby("method"):
        if method == "max_value":
            continue
        paired = baseline.merge(rows, on=[*KEYS, "factor"], suffixes=("_base", "_method"), validate="one_to_one")
        if not len(paired) or len(paired) != len(baseline) or len(paired) != len(rows):
            raise ValueError("Incomplete matched grid")
        for left, right in zip(paired.sim_state_json_base, paired.sim_state_json_method):
            np.testing.assert_allclose(json.loads(left), json.loads(right), atol=1e-9, rtol=0)
        paired["delta"] = paired.success_method.astype(int) - paired.success_base.astype(int)
        for scope, group in [("All", paired), *paired.groupby("factor")]:
            rescue, harm = int(group.delta.eq(1).sum()), int(group.delta.eq(-1).sum())
            low, high = interval(group)
            effects.append(dict(method=method, reference="max_value", scope=scope, pairs=len(group),
                macro_delta=float(group.groupby("factor").delta.mean().mean()), ci95_low=low, ci95_high=high,
                rescues=rescue, harms=harm, mcnemar_p=float(binomtest(rescue, rescue+harm).pvalue) if rescue+harm else 1.,
                q0_pool_exact_rate=float(group.q0_action_pool_sha256_base.eq(group.q0_action_pool_sha256_method).mean())))
    result = pd.DataFrame(effects)
    # Adjust all five primary macro comparisons, including K1, together.
    primary = result[result.scope.eq("All")].sort_values("mcnemar_p")
    adjusted = np.maximum.accumulate(primary.mcnemar_p.to_numpy() * np.arange(len(primary), 0, -1))
    result.loc[primary.index, "holm_macro_p"] = np.minimum(adjusted, 1.)
    return result


def analyze(compact, references):
    a, aq, _ = load_episodes(compact.resolve())
    b, bq, _ = load_episodes(references.resolve())
    a = a.replace({"method": {"winner": "osc_medoid", "first": "first_k1"}})
    if set(a.method) != {"first_k1", "max_value", "osc_medoid"} or set(b.method) != {"raw_medoid", "keystone", "kdpe_endpoint"}:
        raise ValueError("Unexpected matched methods")
    episodes = pd.concat([a, b], ignore_index=True)
    if not episodes.groupby("method").size().eq(200).all():
        raise ValueError("Expected 200 complete rollouts per method")
    effects = paired_effects(episodes)
    output = references / "matched_analysis"
    output.mkdir(exist_ok=True)
    scores = episodes.groupby(["factor", "method"]).agg(episodes=("success", "size"),
        successes=("success", "sum"), sr=("success", "mean"), drops=("target_drop_candidate", "sum")).reset_index()
    scores.to_csv(output / "factor_scores.csv", index=False)
    effects.to_csv(output / "paired_effects.csv", index=False)
    episodes.to_csv(output / "episode_outcomes.csv", index=False)
    pd.concat([aq.assign(campaign="compact"), bq.assign(campaign="references")]).to_csv(output / "query_costs.csv", index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pivot = scores.pivot(index="factor", columns="method", values="sr")
    ax = (100 * pivot).plot.bar(figsize=(10, 5), rot=0)
    ax.set_ylabel("Success rate (%)"); ax.set_ylim(0, 105)
    ax.figure.tight_layout(); ax.figure.savefig(output / "factor_success_rates.png", dpi=160); plt.close(ax.figure)
    gallery = ["<!doctype html><meta charset='utf-8'><title>Matched reference rollouts</title>",
        "<style>body{font:15px sans-serif;margin:24px}.row{display:flex;flex-wrap:wrap;gap:12px}video{width:300px}figure{margin:0 0 16px}h2{font-size:18px}</style>",
        "<h1>Matched deployment rollouts: six methods</h1>"]
    for keys, group in episodes.groupby(KEYS, sort=True):
        gallery.append("<h2>" + html.escape(str(keys)) + "</h2><div class='row'>")
        for row in group.sort_values("method").itertuples():
            video = Path(row.video_path)
            if not video.is_file():
                raise ValueError(f"Missing video: {video}")
            gallery.append(f"<figure><figcaption>{html.escape(row.method)}: success={row.success}, t={row.final_t}</figcaption>"
                           f"<video controls preload='none' src='{html.escape(str(video))}'></video></figure>")
        gallery.append("</div>")
    (output / "videos.html").write_text("\n".join(gallery))
    summary = dict(status="completed", episodes=len(episodes), matched_cases=200, methods=6,
        interpretation="resource_amended_matched_reference_evaluation_not_original_full4500",
        manifests={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (compact / "manifest.json", references / "manifest.json")})
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    report = ["# Matched consensus reference evaluation", "", "1200 real closed-loop rollouts; 200 matched configurations per method.",
        "All methods use H16; K4 except the K1 control. Candidate generation is joint parallel, not autoregressive planning.",
        "The reference methods were fixed before their collection; compact winner was not retuned.",
        "KDPE is adapted to induced OSC endpoints. KeyStone is the existing fixed-seed implementation.", "",
        "## Factor scores", scores.to_markdown(index=False, floatfmt=".4f"), "",
        "## Paired comparisons", effects.to_markdown(index=False, floatfmt=".4f"), "",
        "![Factor SR](factor_success_rates.png)", "", "[All matched videos](videos.html)", "",
        "Bootstrap preserves task/init clusters within factors; macro averages factors equally.",
        "Matching init and rollout seeds does not guarantee identical candidate pools. q0 checks do not certify every later pool.",
        "Only Holm-adjusted macro comparisons form the primary statistical family; per-factor tests are descriptive.",
        "Elapsed job times are not pure inference latency. Videos reference server paths and require export for another machine.", ""]
    (output / "RESULTS.md").write_text("\n".join(report))
    print(effects[effects.scope.eq("All")].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.compact, args.references)

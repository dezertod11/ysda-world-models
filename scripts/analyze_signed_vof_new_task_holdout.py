#!/usr/bin/env python3
"""Evaluate the frozen signed-VoF router on a prospective new-task holdout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest

try:
    from analyze_counterfactual_feedback import binary_auc
    from analyze_signed_vof_router import derive_sidecar_features
    from freeze_signed_vof_router import predict_frozen_payload, select_with_frozen_threshold
except ModuleNotFoundError:
    from scripts.analyze_counterfactual_feedback import binary_auc
    from scripts.analyze_signed_vof_router import derive_sidecar_features
    from scripts.freeze_signed_vof_router import predict_frozen_payload, select_with_frozen_threshold


CASE_PATTERN = re.compile(r"position_([xy]\d+p\d+)_task(\d+)_init")
REPLAY_THRESHOLD = 1e-9
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


def parse_case(case_id: str) -> tuple[str, int]:
    match = CASE_PATTERN.search(case_id)
    if not match:
        raise ValueError(f"Cannot decode holdout case_id={case_id!r}")
    return match.group(1).replace("p", "."), int(match.group(2))


def load_pairs(campaign_dir: Path) -> pd.DataFrame:
    paths = sorted((campaign_dir / "runs").glob("*__feedback_pairs.parquet"))
    if not paths:
        raise FileNotFoundError(f"No feedback pairs under {campaign_dir / 'runs'}")
    parts = []
    for path in paths:
        frame = pd.read_parquet(path)
        frame["source_run"] = path.name.removesuffix("__feedback_pairs.parquet")
        parts.append(frame)
    frame = pd.concat(parts, ignore_index=True).copy()
    parsed = frame["case_id"].astype(str).map(parse_case)
    frame["position_level"] = parsed.map(lambda item: item[0])
    frame["case_task_id"] = parsed.map(lambda item: item[1])
    replay = pd.to_numeric(frame["main_open_replay_state_max_abs"], errors="coerce")
    frame["strict_integrity"] = (
        replay.le(REPLAY_THRESHOLD)
        & _as_bool(frame["open_terminal_available"])
        & _as_bool(frame["feedback_terminal_available"])
        & _as_bool(frame["feedback_available"])
        & pd.to_numeric(frame["query_idx"], errors="coerce").eq(4)
        & frame["task_id"].astype(int).eq(frame["case_task_id"])
    )
    frame["commit_success"] = _as_bool(frame["open_terminal_success"])
    frame["feedback_success"] = _as_bool(frame["feedback_terminal_success"])
    frame["terminal_effect"] = frame["feedback_success"].astype(int) - frame["commit_success"].astype(int)
    return frame


def append_current_proprio(frame: pd.DataFrame, campaign_dir: Path) -> pd.DataFrame:
    rows = []
    for row in frame.itertuples(index=False):
        sidecar = (
            campaign_dir
            / "runs"
            / f"{row.source_run}__snapshots"
            / Path(str(row.sidecar_path)).name
        )
        if not sidecar.is_file():
            raise FileNotFoundError(sidecar)
        features = derive_sidecar_features(sidecar, feedback_steps=int(row.feedback_steps))
        rows.append({key: value for key, value in features.items() if key.startswith("pre_current_proprio_")})
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def clustered_interval(
    frame: pd.DataFrame,
    contribution: np.ndarray,
    *,
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    work = pd.DataFrame(
        {
            "cluster": (
                frame["position_level"].astype(str)
                + "|task"
                + frame["task_id"].astype(int).astype(str)
                + "|init"
                + frame["init_state_id"].astype(int).astype(str)
            ),
            "sum": contribution,
            "size": 1,
        }
    ).groupby("cluster", sort=True)[["sum", "size"]].sum()
    values = work.to_numpy(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(repetitions, len(values)))
    sampled = values[draws]
    statistic = sampled[:, :, 0].sum(axis=1) / sampled[:, :, 1].sum(axis=1)
    return tuple(float(value) for value in np.quantile(statistic, [0.025, 0.975]))


def policy_row(frame: pd.DataFrame, query: np.ndarray, query_cost: float) -> dict[str, object]:
    commit = frame["commit_success"].to_numpy(bool)
    feedback = frame["feedback_success"].to_numpy(bool)
    query = np.asarray(query, dtype=bool)
    outcome = np.where(query, feedback, commit)
    effect = outcome.astype(float) - commit.astype(float)
    adjusted = effect - query_cost * query.astype(float)
    rescue = query & ~commit & feedback
    harm = query & commit & ~feedback
    return {
        "states": len(frame),
        "commit_success_rate": float(commit.mean()),
        "policy_success_rate": float(outcome.mean()),
        "query_rate": float(query.mean()),
        "rescues": int(rescue.sum()),
        "harms": int(harm.sum()),
        "neutral_queries": int((query & (commit == feedback)).sum()),
        "raw_success_delta": float(effect.mean()),
        "adjusted_success_delta": float(adjusted.mean()),
    }


def plot_summary(cell_summary: pd.DataFrame, frame: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    x = np.arange(len(cell_summary))
    width = 0.25
    labels = [f"{r.position_level}/t{r.task_id}" for r in cell_summary.itertuples(index=False)]
    axes[0].bar(x - width, cell_summary["commit_success_rate"], width, label="commit")
    axes[0].bar(x, cell_summary["always_requery_success_rate"], width, label="always requery")
    axes[0].bar(x + width, cell_summary["router_success_rate"], width, label="frozen router")
    axes[0].set_xticks(x, labels, rotation=35, ha="right")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Terminal success rate")
    axes[0].legend()
    colors = np.where(frame["terminal_effect"].to_numpy() > 0, "#16865b", np.where(frame["terminal_effect"].to_numpy() < 0, "#c53c45", "#9ca3af"))
    axes[1].scatter(frame["router_score"], frame["terminal_effect"], c=colors, alpha=0.65, s=24)
    axes[1].axvline(float(frame["router_threshold"].iloc[0]), color="black", linestyle="--", label="frozen threshold")
    axes[1].set_xlabel("Frozen predicted signed VoF score")
    axes[1].set_ylabel("Observed feedback effect")
    axes[1].set_yticks([-1, 0, 1])
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    router_path = Path(manifest["frozen_router"])
    if not router_path.is_absolute():
        router_path = PROJECT_ROOT / router_path
    router = json.loads(router_path.read_text(encoding="utf-8"))
    all_pairs = load_pairs(campaign_dir)
    strict = append_current_proprio(
        all_pairs.loc[all_pairs["strict_integrity"]].reset_index(drop=True), campaign_dir
    )
    predicted_mean, predicted_std, score = predict_frozen_payload(router, strict)
    query = select_with_frozen_threshold(router, score)
    strict["predicted_vof_mean"] = predicted_mean
    strict["predicted_vof_std"] = predicted_std
    strict["router_score"] = score
    strict["router_query"] = query
    strict["router_threshold"] = float(router["router"]["absolute_score_threshold"])
    strict["router_success"] = np.where(query, strict["feedback_success"], strict["commit_success"])
    query_cost = float(manifest["query_cost"])

    commit_row = policy_row(strict, np.zeros(len(strict), dtype=bool), query_cost)
    always_row = policy_row(strict, np.ones(len(strict), dtype=bool), query_cost)
    router_row = policy_row(strict, query, query_cost)
    oracle_query = (strict["terminal_effect"].to_numpy(float) > 0)
    oracle_row = policy_row(strict, oracle_query, query_cost)
    overall = pd.DataFrame(
        [
            {"policy": "always_commit", **commit_row},
            {"policy": "always_requery", **always_row},
            {"policy": "frozen_signed_vof", **router_row},
            {"policy": "oracle_query", **oracle_row},
        ]
    )

    raw_contribution = strict["router_success"].to_numpy(float) - strict["commit_success"].to_numpy(float)
    adjusted_contribution = raw_contribution - query_cost * query.astype(float)
    raw_ci = clustered_interval(strict, raw_contribution, repetitions=int(manifest["bootstrap_repetitions"]), seed=int(manifest["bootstrap_seed"]))
    adjusted_ci = clustered_interval(strict, adjusted_contribution, repetitions=int(manifest["bootstrap_repetitions"]), seed=int(manifest["bootstrap_seed"]) + 1)
    rescues = int((query & (strict["terminal_effect"].to_numpy() > 0)).sum())
    harms = int((query & (strict["terminal_effect"].to_numpy() < 0)).sum())
    mcnemar_p = float(binomtest(min(rescues, harms), rescues + harms, 0.5).pvalue) if rescues + harms else 1.0
    discordant = strict["terminal_effect"].ne(0).to_numpy()
    auc = binary_auc(strict.loc[discordant, "terminal_effect"].gt(0), strict.loc[discordant, "router_score"])

    cell_rows = []
    for (level, task_id), indices in strict.groupby(["position_level", "task_id"], sort=True).groups.items():
        group = strict.loc[indices].reset_index(drop=True)
        group_query = group["router_query"].to_numpy(bool)
        row = policy_row(group, group_query, query_cost)
        always_group = policy_row(group, np.ones(len(group), dtype=bool), query_cost)
        cell_rows.append(
            {
                "position_level": level,
                "task_id": int(task_id),
                "task_description": str(group["task_description"].iloc[0]),
                **{key: value for key, value in row.items() if key != "states"},
                "states": len(group),
                "always_requery_success_rate": always_group["policy_success_rate"],
                "router_success_rate": row["policy_success_rate"],
            }
        )
    cell_summary = pd.DataFrame(cell_rows)

    selected_cells = manifest["selected_cells"]
    selected_tasks = {int(cell["task_id"]) for cell in selected_cells}
    selected_directions = {str(cell["direction"]) for cell in selected_cells}
    checks = {
        "integrity_at_least_228_of_240": len(strict) >= int(manifest["minimum_strict_pairs"]),
        "raw_router_delta_positive": router_row["raw_success_delta"] > 0.0,
        "adjusted_cluster_ci_lower_positive": adjusted_ci[0] > 0.0,
        "query_rate_at_most_60pct": router_row["query_rate"] <= 0.60,
        "atlas_cell_coverage": len(selected_tasks) >= 3 and selected_directions == {"x", "y"},
    }
    gate = {
        "expected_pairs": int(manifest["target_pairs"]),
        "all_pairs": len(all_pairs),
        "strict_pairs": len(strict),
        "router": router_row,
        "raw_cluster_ci": list(raw_ci),
        "adjusted_cluster_ci": list(adjusted_ci),
        "rescue_vs_harm_auc": auc,
        "exact_mcnemar_pvalue": mcnemar_p,
        "checks": checks,
        "pass": bool(all(checks.values())),
        "decision": "promote_signed_vof_router_to_online_replication" if all(checks.values()) else "do_not_promote_signed_vof_router",
    }

    strict.to_parquet(output_dir / "strict_router_predictions.parquet", index=False)
    strict.to_csv(output_dir / "strict_router_predictions.csv", index=False)
    overall.to_csv(output_dir / "policy_summary.csv", index=False)
    cell_summary.to_csv(output_dir / "cell_summary.csv", index=False)
    (output_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    plot_summary(cell_summary, strict, output_dir / "signed_vof_holdout_summary.png")
    lines = [
        "# Frozen signed-VoF new-task holdout result",
        "",
        f"- Integrity: {len(strict)}/{manifest['target_pairs']} strict pairs.",
        f"- Commit SR: {100 * router_row['commit_success_rate']:.1f}%.",
        f"- Frozen-router SR: {100 * router_row['policy_success_rate']:.1f}%.",
        f"- Query rate: {100 * router_row['query_rate']:.1f}%.",
        f"- Raw delta: {100 * router_row['raw_success_delta']:+.1f} pp, cluster CI [{100 * raw_ci[0]:+.1f}, {100 * raw_ci[1]:+.1f}].",
        f"- Cost-adjusted delta: {100 * router_row['adjusted_success_delta']:+.1f} pp, cluster CI [{100 * adjusted_ci[0]:+.1f}, {100 * adjusted_ci[1]:+.1f}].",
        f"- Selected rescues / harms: {rescues} / {harms}; exact McNemar p={mcnemar_p:.6g}.",
        f"- Rescue-vs-harm score AUROC: {auc:.3f}.",
        f"- Gate: **{'PASS' if gate['pass'] else 'FAIL'}**; decision `{gate['decision']}`.",
        "",
        "## Policies",
        "",
        overall.to_markdown(index=False),
        "",
        "## Cells",
        "",
        cell_summary.to_markdown(index=False),
    ]
    (output_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(gate, indent=2))
    print(f"Results: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

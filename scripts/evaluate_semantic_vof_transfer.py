#!/usr/bin/env python3
"""Frozen Environment task-transfer evaluation for semantic VoF features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_semantic_vof import (
    PRIVILEGED_TOKENS,
    QUERY_COST,
    SCALAR_FEATURES,
    _prepare_matrix,
    _ridge_predict,
    extract_features,
    prediction_metrics,
    uplift_at_budget,
)


EXPECTED_TRAIN = 98
EXPECTED_TEST = 67
BUDGETS = (0.10, 0.20, 0.30)
AGENT_DISAGREEMENT = "clip_agent_candidate_disagreement"
CROSSVIEW = "clip_cross_view_selected"
FAMILIES = {
    "scalar": SCALAR_FEATURES,
    "scalar+agent-disagreement": SCALAR_FEATURES + [AGENT_DISAGREEMENT],
    "scalar+crossview": SCALAR_FEATURES + [CROSSVIEW],
    "scalar+semantic2": SCALAR_FEATURES + [AGENT_DISAGREEMENT, CROSSVIEW],
}
PRIMARY = "scalar+semantic2"


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def fit_transfer(
    train: pd.DataFrame, test: pd.DataFrame, features: list[str]
) -> np.ndarray:
    x_train, x_test = _prepare_matrix(train, test, features)
    return _ridge_predict(
        x_train,
        train["dense_vof_v2"].to_numpy(float),
        x_test,
    )


def evaluate_transfer(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, object],
]:
    target = test["dense_vof_v2"].to_numpy(float)
    predictions = test[
        ["row_id", "task_id", "init_state_id", "rollout_id", "query_idx", "dense_vof_v2"]
    ].copy()
    metric_rows = []
    uplift_rows = []
    task_rows = []
    for family, features in FAMILIES.items():
        prediction = fit_transfer(train, test, features)
        predictions[family] = prediction
        metric_rows.append({"family": family, **prediction_metrics(target, prediction)})
        for budget in BUDGETS:
            uplift_rows.append({"family": family, **uplift_at_budget(target, prediction, budget)})
        for task, indices in test.groupby("task_id").groups.items():
            index = np.asarray(list(indices), dtype=int)
            task_rows.append(
                {
                    "family": family,
                    "task_id": int(task),
                    "states": int(len(index)),
                    **prediction_metrics(target[index], prediction[index]),
                    **{
                        f"uplift20_{key}": value
                        for key, value in uplift_at_budget(target[index], prediction[index], 0.20).items()
                        if key in {"uplift_per_state", "compute_adjusted_uplift"}
                    },
                }
            )
    metrics = pd.DataFrame(metric_rows)
    uplifts = pd.DataFrame(uplift_rows)
    tasks = pd.DataFrame(task_rows)
    metric_index = metrics.set_index("family")
    uplift20 = uplifts.loc[np.isclose(uplifts["budget"], 0.20)].set_index("family")
    primary_tasks = tasks.loc[tasks["family"].eq(PRIMARY)]
    forbidden = [
        feature
        for feature in FAMILIES[PRIMARY]
        if any(token in feature.lower() for token in PRIVILEGED_TOKENS)
    ]
    train_tasks = set(train["task_id"].astype(int))
    test_tasks = set(test["task_id"].astype(int))
    checks = {
        "exact_train_test_coverage": len(train) == EXPECTED_TRAIN and len(test) == EXPECTED_TEST,
        "task_sets_frozen_and_disjoint": train_tasks == {0, 1, 2, 3}
        and test_tasks == {5, 8, 9}
        and train_tasks.isdisjoint(test_tasks),
        "primary_spearman_gain_at_least_0p05": float(metric_index.loc[PRIMARY, "spearman"])
        >= float(metric_index.loc["scalar", "spearman"]) + 0.05,
        "primary_auc_not_below_scalar": float(metric_index.loc[PRIMARY, "sign_auc"])
        >= float(metric_index.loc["scalar", "sign_auc"]),
        "primary_uplift20_positive": float(uplift20.loc[PRIMARY, "uplift_per_state"]) > 0.0,
        "primary_uplift20_above_scalar": float(uplift20.loc[PRIMARY, "uplift_per_state"])
        > float(uplift20.loc["scalar", "uplift_per_state"]),
        "primary_compute_adjusted_uplift20_positive": float(
            uplift20.loc[PRIMARY, "compute_adjusted_uplift"]
        )
        > 0.0,
        "primary_uplift20_nonnegative_each_task": bool(
            primary_tasks["uplift20_uplift_per_state"].ge(0).all()
        ),
        "no_privileged_features": not forbidden,
    }
    gate = {
        "checks": checks,
        "forbidden_features": forbidden,
        "gate_passed": bool(all(checks.values())),
    }
    return predictions, metrics, uplifts, tasks, gate


def write_outputs(
    output_dir: Path,
    semantic: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    uplifts: pd.DataFrame,
    tasks: pd.DataFrame,
    gate: dict[str, object],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    semantic.to_parquet(output_dir / "transfer_semantic_features.parquet", index=False)
    predictions.to_csv(output_dir / "transfer_predictions.csv", index=False)
    metrics.to_csv(output_dir / "model_summary.csv", index=False)
    uplifts.to_csv(output_dir / "uplift_summary.csv", index=False)
    tasks.to_csv(output_dir / "task_summary.csv", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(metrics["family"], metrics["spearman"], color=["#4C78A8", "#F28E2B", "#E15759", "#59A14F"])
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_ylabel("Transfer Spearman")
    axes[0].tick_params(axis="x", rotation=18)
    axes[0].set_title("Environment task transfer")
    for family, group in uplifts.groupby("family"):
        axes[1].plot(group["budget"], group["uplift_per_state"], marker="o", label=family)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_xlabel("Re-query budget")
    axes[1].set_ylabel("Dense VoF uplift per state")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    plot_path = output_dir / "semantic_vof_task_transfer.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    lines = [
        "# Semantic VoF Environment task transfer: results",
        "",
        f"- Development states: **{EXPECTED_TRAIN}** (tasks 0-3).",
        f"- Transfer states: **{EXPECTED_TEST}** (tasks 5/8/9).",
        f"- Gate: **{'PASS' if gate['gate_passed'] else 'FAIL'}**.",
        "",
        "## Models",
        "",
        metrics.to_markdown(index=False),
        "",
        "## Uplift",
        "",
        uplifts.to_markdown(index=False),
        "",
        "## Per task",
        "",
        tasks.to_markdown(index=False),
        "",
        "## Gate",
        "",
    ]
    lines.extend(f"- `{name}`: {'PASS' if passed else 'FAIL'}" for name, passed in gate["checks"].items())
    report = output_dir / "RESULTS.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "gate": gate,
        "model_summary": metrics.to_dict(orient="records"),
        "uplift_summary": uplifts.to_dict(orient="records"),
        "task_summary": tasks.to_dict(orient="records"),
        "report": str(report),
        "plot": str(plot_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=_json_default), encoding="utf-8"
    )
    return summary


def main() -> None:
    root = PROJECT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-pairs",
        type=Path,
        default=root / "experiments/campaigns/counterfactual_feedback_dense_relabel_20260827/analysis/counterfactual_feedback/strict_feedback_pairs_all.parquet",
    )
    parser.add_argument(
        "--train-semantic-features",
        type=Path,
        default=root / "experiments/campaigns/semantic_vof_screen_20260831/analysis/semantic_features.parquet",
    )
    parser.add_argument(
        "--test-pairs",
        type=Path,
        default=root / "experiments/campaigns/phase_vof_terminal_transfer_20260831__dense_relabel/analysis/phase_vof_terminal_transfer/strict_snapshot_outcomes.csv",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--row-batch-size", type=int, default=8)
    parser.add_argument("--reuse-features", action="store_true")
    args = parser.parse_args()

    train = pd.read_parquet(args.train_pairs).reset_index(drop=True)
    train["row_id"] = np.arange(len(train), dtype=int)
    train_semantic = pd.read_parquet(args.train_semantic_features)
    train = train.merge(train_semantic, on="row_id", validate="one_to_one")
    train = train.loc[train["factor"].eq("Environment")].reset_index(drop=True)

    test = pd.read_csv(args.test_pairs).reset_index(drop=True)
    test["row_id"] = np.arange(len(test), dtype=int)
    feature_path = args.output_dir / "transfer_semantic_features.parquet"
    if args.reuse_features and feature_path.exists():
        test_semantic = pd.read_parquet(feature_path)
    else:
        test_semantic = extract_features(
            test,
            project_root=root,
            model_name="openai/clip-vit-base-patch32",
            device=args.device,
            row_batch_size=args.row_batch_size,
        )
    test = test.merge(test_semantic, on="row_id", validate="one_to_one")
    predictions, metrics, uplifts, tasks, gate = evaluate_transfer(train, test)
    summary = write_outputs(args.output_dir, test_semantic, predictions, metrics, uplifts, tasks, gate)
    print(json.dumps(summary["gate"], indent=2, default=_json_default))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()

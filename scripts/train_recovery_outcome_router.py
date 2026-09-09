#!/usr/bin/env python3
"""Fit the frozen P3e recovery outcome heads on P3d development branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler

from recovery_outcome_router import ROUTER_FEATURES, ROUTER_STRATEGIES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mcnemar_exact(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if not discordant:
        return 1.0
    extreme = max(rescues, harms)
    tail = sum(math.comb(discordant, value) for value in range(extreme, discordant + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def _bootstrap_delta(
    frame: pd.DataFrame,
    reference: str,
    *,
    cluster: list[str],
    repetitions: int,
    seed: int,
) -> tuple[float, float]:
    grouped = frame.assign(
        delta=frame["router_success"].astype(float) - frame[reference].astype(float)
    ).groupby(cluster, as_index=False)["delta"].mean()
    values = grouped["delta"].to_numpy()
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(repetitions, len(values)))
    return tuple(float(value) for value in np.quantile(values[indices].mean(1), [0.025, 0.975]))


def _markdown_summary(frame: pd.DataFrame) -> str:
    columns = (
        "cohort",
        "n_cases",
        "workspace_calibrated_sr",
        "router_sr",
        "vs_full_delta",
        "vs_full_rescues",
        "vs_full_harms",
        "selected_baseline",
        "selected_retreat",
        "selected_full",
    )
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in frame[list(columns)].itertuples(index=False, name=None):
        values = [f"{value:.6g}" if isinstance(value, float) else str(value) for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _prepare(branches_path: Path) -> tuple[pd.DataFrame, np.ndarray]:
    branches = pd.read_parquet(branches_path)
    branches = branches.drop_duplicates(["case_id", "strategy"], keep="last")
    observed = set(branches["strategy"].astype(str))
    if observed != set(ROUTER_STRATEGIES):
        raise ValueError(f"Unexpected strategies: {sorted(observed)}")
    reference = branches.loc[
        branches["strategy"] == "workspace_calibrated"
    ].set_index("case_id")
    outcomes = branches.pivot(index="case_id", columns="strategy", values="terminal_success")
    frame = reference[
        [
            "evaluation_cohort",
            "position_level",
            "task_id",
            "init_state_id",
            "independent_group",
            "trigger_passed",
            *ROUTER_FEATURES,
        ]
    ].join(outcomes)
    frame["cell"] = (
        frame["position_level"].astype(str) + "|task" + frame["task_id"].astype(str)
    )
    for strategy in ROUTER_STRATEGIES:
        frame[strategy] = frame[strategy].astype(int)
    frame["trigger_passed"] = frame["trigger_passed"].astype(int)
    features = (
        frame[list(ROUTER_FEATURES)].apply(pd.to_numeric, errors="coerce").to_numpy()
    )
    if not np.isfinite(features).all():
        raise ValueError("P3e development requires finite observation features")
    return frame, features


def fit(args: argparse.Namespace) -> dict:
    branches_path = args.branches.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frame, features = _prepare(branches_path)
    labels = {
        strategy: frame[strategy].to_numpy(dtype=int)
        for strategy in ROUTER_STRATEGIES
    }
    groups = frame["cell"].to_numpy()
    costs = {
        "baseline_h8": 0.0,
        "workspace_retreat_only": args.retreat_steps / args.episode_budget,
        "workspace_calibrated": args.regrasp_steps / args.episode_budget,
    }

    oof_probabilities = {
        strategy: np.full(len(frame), np.nan, dtype=np.float64)
        for strategy in ROUTER_STRATEGIES
    }
    splitter = LeaveOneGroupOut()
    for train, test in splitter.split(features, groups=groups):
        train_features = features[train]
        medians = np.nanmedian(train_features, axis=0)
        train_finite = np.where(np.isfinite(train_features), train_features, medians)
        test_finite = np.where(np.isfinite(features[test]), features[test], medians)
        scaler = StandardScaler().fit(train_finite)
        train_scaled = scaler.transform(train_finite)
        test_scaled = scaler.transform(test_finite)
        for strategy in ROUTER_STRATEGIES:
            model = LogisticRegression(C=args.c_value, max_iter=5000).fit(
                train_scaled, labels[strategy][train]
            )
            oof_probabilities[strategy][test] = model.predict_proba(test_scaled)[:, 1]

    score_matrix = np.column_stack(
        [
            oof_probabilities[strategy]
            - args.primitive_cost_lambda * costs[strategy]
            for strategy in ROUTER_STRATEGIES
        ]
    )
    selected_indices = np.argmax(score_matrix, axis=1)
    selected = np.asarray(ROUTER_STRATEGIES, dtype=object)[selected_indices]
    selected = np.where(
        frame["trigger_passed"].to_numpy(dtype=bool), selected, "baseline_h8"
    )
    router_success = np.asarray(
        [labels[strategy][index] for index, strategy in enumerate(selected)],
        dtype=int,
    )
    frame["router_selected_strategy"] = selected
    frame["router_success"] = router_success
    for strategy in ROUTER_STRATEGIES:
        frame[f"router_probability__{strategy}"] = oof_probabilities[strategy]
        frame[f"router_score__{strategy}"] = (
            oof_probabilities[strategy]
            - args.primitive_cost_lambda * costs[strategy]
        )

    summaries = []
    for cohort in ("all", "replication", "novel_cell"):
        subset = (
            frame
            if cohort == "all"
            else frame.loc[frame["evaluation_cohort"] == cohort]
        )
        item = {"cohort": cohort, "n_cases": len(subset)}
        for strategy in ROUTER_STRATEGIES:
            item[f"{strategy}_sr"] = float(subset[strategy].mean())
        item["router_sr"] = float(subset["router_success"].mean())
        for reference in ("workspace_calibrated", "baseline_h8"):
            delta = subset["router_success"] - subset[reference]
            rescues = int((delta == 1).sum())
            harms = int((delta == -1).sum())
            prefix = (
                "vs_full" if reference == "workspace_calibrated" else "vs_baseline"
            )
            item[f"{prefix}_delta"] = float(delta.mean())
            item[f"{prefix}_rescues"] = rescues
            item[f"{prefix}_harms"] = harms
            item[f"{prefix}_mcnemar_p"] = _mcnemar_exact(rescues, harms)
            group_ci = _bootstrap_delta(
                subset,
                reference,
                cluster=["independent_group"],
                repetitions=args.bootstrap_repetitions,
                seed=args.seed + len(summaries) * 10,
            )
            cell_ci = _bootstrap_delta(
                subset,
                reference,
                cluster=["position_level", "task_id"],
                repetitions=args.bootstrap_repetitions,
                seed=args.seed + len(summaries) * 10 + 1,
            )
            item[f"{prefix}_group_ci_low"], item[f"{prefix}_group_ci_high"] = group_ci
            item[f"{prefix}_cell_ci_low"], item[f"{prefix}_cell_ci_high"] = cell_ci
        item["selected_baseline"] = int(
            subset["router_selected_strategy"].eq("baseline_h8").sum()
        )
        item["selected_retreat"] = int(
            subset["router_selected_strategy"].eq("workspace_retreat_only").sum()
        )
        item["selected_full"] = int(
            subset["router_selected_strategy"].eq("workspace_calibrated").sum()
        )
        summaries.append(item)
    summary_frame = pd.DataFrame(summaries)
    overall = summary_frame.loc[summary_frame["cohort"] == "all"].iloc[0]
    novel = summary_frame.loc[summary_frame["cohort"] == "novel_cell"].iloc[0]
    gate = bool(
        overall["vs_full_rescues"] >= args.min_oof_rescues
        and overall["vs_full_harms"] == 0
        and overall["vs_full_delta"] > 0
        and novel["vs_full_delta"] >= 0
    )

    final_medians = np.nanmedian(features, axis=0)
    final_finite = np.where(np.isfinite(features), features, final_medians)
    final_scaler = StandardScaler().fit(final_finite)
    heads = {}
    for strategy in ROUTER_STRATEGIES:
        model = LogisticRegression(C=args.c_value, max_iter=5000).fit(
            final_scaler.transform(final_finite), labels[strategy]
        )
        heads[strategy] = {
            "coefficients": model.coef_[0].astype(float).tolist(),
            "intercept": float(model.intercept_[0]),
        }

    artifact = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_name": "p3e_recovery_outcome_ensemble_v1",
        "model_type": "independent_logistic_terminal_success_heads",
        "source_branches": str(branches_path),
        "source_branches_sha256": _sha256(branches_path),
        "development_cases": len(frame),
        "development_cells": int(frame["cell"].nunique()),
        "cross_validation": "leave-one-position-task-cell-out",
        "features": list(ROUTER_FEATURES),
        "strategies": list(ROUTER_STRATEGIES),
        "logistic_c": args.c_value,
        "primitive_cost_lambda": args.primitive_cost_lambda,
        "primitive_costs": costs,
        "feature_medians": final_medians.astype(float).tolist(),
        "feature_means": final_scaler.mean_.astype(float).tolist(),
        "feature_scales": final_scaler.scale_.astype(float).tolist(),
        "heads": heads,
        "development_gate_pass": gate,
        "selection_note": (
            "Localization-only C=0.3 tied for best terminal OOF SR in the "
            "compact linear sweep; the smallest feature family was selected."
        ),
    }
    artifact_path = output_dir / "recovery_outcome_router_v1.json"
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    frame.reset_index().to_csv(
        output_dir / "recovery_outcome_router_oof.csv", index=False
    )
    summary_frame.to_csv(
        output_dir / "recovery_outcome_router_oof_summary.csv", index=False
    )
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact": str(artifact_path),
        "artifact_sha256": _sha256(artifact_path),
        "development_gate_pass": gate,
        "cohorts": summary_frame.to_dict(orient="records"),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (output_dir / "RESULTS.md").write_text(
        "\n".join(
            [
                "# P3e recovery outcome router: development OOF",
                "",
                f"- Development gate: **{'PASS' if gate else 'NO-GO'}**.",
                f"- Cases/cells: **{len(frame)}/{frame['cell'].nunique()}**.",
                "- Validation: leave one complete position x task cell out.",
                "- Features: seven pre-intervention RGB-localization and EEF-relation values.",
                "",
                _markdown_summary(summary_frame),
                "",
                "The router and all hyperparameters are frozen before holdout init 45--49.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)
    if args.require_gate and not gate:
        raise SystemExit(2)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--branches", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--c-value", type=float, default=0.3)
    result.add_argument("--primitive-cost-lambda", type=float, default=0.25)
    result.add_argument("--retreat-steps", type=float, default=3.0)
    result.add_argument("--regrasp-steps", type=float, default=25.0)
    result.add_argument("--episode-budget", type=float, default=280.0)
    result.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    result.add_argument("--seed", type=int, default=20260906)
    result.add_argument("--min-oof-rescues", type=int, default=2)
    result.add_argument("--require-gate", action="store_true")
    return result


if __name__ == "__main__":
    fit(parser().parse_args())

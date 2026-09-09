#!/usr/bin/env python3
"""Compare P4b residual-risk variants and freeze one prospective selector."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_residual_dynamics_ensemble import (
        balanced_average_precision,
        roc_auc,
    )
    from scripts.build_residual_dynamics_dataset import sha256_file
    from scripts.p4b_residual_risk import (
        RISK_SCORE_NAMES,
        artifact_variances,
        calibrate_variance_temperature,
        json_ready,
        predict_heads,
        residual_risk_scores,
        select_candidate,
    )
    from scripts.residual_dynamics_ensemble import ResidualPreprocessor
except ModuleNotFoundError:
    from analyze_residual_dynamics_ensemble import (
        balanced_average_precision,
        roc_auc,
    )
    from build_residual_dynamics_dataset import sha256_file
    from p4b_residual_risk import (
        RISK_SCORE_NAMES,
        artifact_variances,
        calibrate_variance_temperature,
        json_ready,
        predict_heads,
        residual_risk_scores,
        select_candidate,
    )
    from residual_dynamics_ensemble import ResidualPreprocessor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELECTOR_METRICS = (
    "epistemic_mean",
    "predicted_mean_residual_rms",
    "mean_plus_epistemic_rms",
    "expected_residual_rms",
)


def _artifact_specs(values: list[str]) -> list[tuple[str, Path]]:
    result = []
    for value in values:
        if "=" not in value:
            raise ValueError("Artifact must use NAME=PATH syntax")
        name, path = value.split("=", 1)
        resolved = Path(path).expanduser().resolve()
        if not name or not (resolved / "ensemble.json").is_file():
            raise FileNotFoundError(value)
        result.append((name, resolved))
    if len({name for name, _path in result}) != len(result):
        raise ValueError("P4b artifact names must be unique")
    return result


def _spearman(frame: pd.DataFrame, left: str, right: str) -> float:
    values = frame[[left, right]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(values) < 3 or values[left].nunique() < 2 or values[right].nunique() < 2:
        return float("nan")
    return float(values.corr(method="spearman").iloc[0, 1])


def _score_variant(
    manifest: pd.DataFrame,
    arrays: dict[str, np.ndarray],
    name: str,
    artifact_dir: Path,
    *,
    device: str,
    batch_size: int,
    mc_samples: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    preprocessor = ResidualPreprocessor.load(artifact_dir / "preprocessing.npz")
    indices = np.arange(len(manifest), dtype=np.int64)
    inputs = preprocessor.transform_input(arrays, indices)
    targets = preprocessor.transform_target(arrays, indices)
    means, predicted_variances = predict_heads(
        inputs, artifact_dir, device=device, batch_size=batch_size
    )
    variances = artifact_variances(predicted_variances, artifact_dir)
    calibration = np.flatnonzero(manifest["split"].astype(str).eq("calibration"))
    temperature, calibration_nll = calibrate_variance_temperature(
        means, variances, targets, calibration
    )
    scores = residual_risk_scores(
        means,
        variances,
        temperature=temperature,
        mc_samples_per_head=mc_samples,
        mc_seed=seed,
        mc_device=device,
    )
    frame = manifest[
        [
            "row_uid",
            "snapshot_group",
            "group_id",
            "split",
            "factor",
            "suite",
            "task_id",
            "case_id",
            "query_idx",
            "candidate_idx",
            "candidate_value",
        ]
    ].copy()
    frame["variant"] = name
    frame["target_standardized_residual_rms"] = np.sqrt(
        np.mean(np.square(targets), axis=1)
    )
    for score_name, values in scores.items():
        frame[score_name] = values
    metadata = {
        "variant": name,
        "artifact_dir": str(artifact_dir),
        "artifact_manifest_sha256": sha256_file(artifact_dir / "ensemble.json"),
        "artifact_checksum_sha256": (
            sha256_file(artifact_dir / "SHA256SUMS")
            if (artifact_dir / "SHA256SUMS").is_file()
            else None
        ),
        "variance_temperature": temperature,
        "calibration_mixture_nll": calibration_nll,
        "heads": int(means.shape[0]),
    }
    return frame, metadata


def _metric_tables(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    id_queries = sorted(
        scored.loc[scored["factor"].eq("ID"), "query_idx"]
        .dropna()
        .astype(int)
        .unique()
    )
    matched = scored.loc[
        scored["factor"].eq("ID")
        | scored["query_idx"].fillna(-1).astype(int).isin(id_queries)
    ]
    heldout = matched.loc[matched["split"].isin(["id_test", "ood_test"])]
    trajectory = (
        heldout.groupby(
            ["variant", "group_id", "split", "factor"], as_index=False
        )[
            [*RISK_SCORE_NAMES, "target_standardized_residual_rms"]
        ]
        .max()
    )
    correlation_records = []
    detection_records = []
    for variant, rows in heldout.groupby("variant", sort=False):
        groups = trajectory.loc[trajectory["variant"].eq(variant)]
        id_test = groups.loc[groups["split"].eq("id_test")]
        for metric in RISK_SCORE_NAMES:
            correlation_records.append(
                {
                    "variant": variant,
                    "metric": metric,
                    "candidate_spearman": _spearman(
                        rows, metric, "target_standardized_residual_rms"
                    ),
                    "trajectory_spearman": _spearman(
                        groups, metric, "target_standardized_residual_rms"
                    ),
                    "minimum": float(rows[metric].min()),
                    "median": float(rows[metric].median()),
                    "maximum": float(rows[metric].max()),
                    "unique_values": int(rows[metric].nunique()),
                }
            )
            for factor in ["Environment", "Object", "Position", "All OOD"]:
                positive = groups.loc[groups["split"].eq("ood_test")]
                if factor != "All OOD":
                    positive = positive.loc[positive["factor"].eq(factor)]
                labels = np.concatenate(
                    [
                        np.zeros(len(id_test), dtype=bool),
                        np.ones(len(positive), dtype=bool),
                    ]
                )
                values = np.concatenate(
                    [id_test[metric].to_numpy(), positive[metric].to_numpy()]
                )
                detection_records.append(
                    {
                        "variant": variant,
                        "metric": metric,
                        "factor": factor,
                        "roc_auc": roc_auc(labels, values),
                        "balanced_average_precision": balanced_average_precision(
                            labels, values
                        ),
                        "id_groups": len(id_test),
                        "ood_groups": len(positive),
                    }
                )
    return pd.DataFrame(correlation_records), pd.DataFrame(detection_records)


def _selector_grid(
    scored: pd.DataFrame,
    correlations: pd.DataFrame,
    lambdas: list[float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    id_queries = sorted(
        scored.loc[scored["factor"].eq("ID"), "query_idx"]
        .dropna()
        .astype(int)
        .unique()
    )
    ood = scored.loc[
        scored["split"].eq("ood_test")
        & scored["query_idx"].fillna(-1).astype(int).isin(id_queries)
    ]
    summaries = []
    selections = []
    for (variant, metric), correlation in correlations.loc[
        correlations["metric"].isin(SELECTOR_METRICS)
    ].set_index(["variant", "metric"])["candidate_spearman"].items():
        rows = ood.loc[ood["variant"].eq(variant)]
        for risk_lambda in lambdas:
            current = []
            for snapshot_group, candidates in rows.groupby(
                "snapshot_group", sort=False
            ):
                candidates = candidates.sort_values("candidate_idx")
                values = candidates["candidate_value"].to_numpy(dtype=float)
                risks = candidates[metric].to_numpy(dtype=float)
                baseline_position = int(np.nanargmax(values))
                selected_position = select_candidate(values, risks, risk_lambda)
                baseline = candidates.iloc[baseline_position]
                selected = candidates.iloc[selected_position]
                current.append(
                    {
                        "variant": variant,
                        "metric": metric,
                        "risk_lambda": risk_lambda,
                        "snapshot_group": snapshot_group,
                        "group_id": str(candidates.iloc[0]["group_id"]),
                        "factor": str(candidates.iloc[0]["factor"]),
                        "baseline_candidate_idx": int(baseline["candidate_idx"]),
                        "selected_candidate_idx": int(selected["candidate_idx"]),
                        "selection_changed": baseline_position != selected_position,
                        "baseline_residual": float(
                            baseline["target_standardized_residual_rms"]
                        ),
                        "selected_residual": float(
                            selected["target_standardized_residual_rms"]
                        ),
                    }
                )
            selection = pd.DataFrame(current)
            selection["residual_delta"] = (
                selection["selected_residual"] - selection["baseline_residual"]
            )
            factor_delta = selection.groupby("factor")["residual_delta"].mean()
            summary = {
                "variant": variant,
                "metric": metric,
                "risk_lambda": risk_lambda,
                "candidate_spearman": float(correlation),
                "snapshots": len(selection),
                "selection_change_rate": float(selection["selection_changed"].mean()),
                "baseline_residual_mean": float(selection["baseline_residual"].mean()),
                "selected_residual_mean": float(selection["selected_residual"].mean()),
                "pooled_residual_delta": float(selection["residual_delta"].mean()),
                "pooled_relative_delta": float(
                    selection["residual_delta"].mean()
                    / selection["baseline_residual"].mean()
                ),
            }
            for factor in ["Environment", "Object", "Position"]:
                summary[f"{factor.lower()}_residual_delta"] = float(
                    factor_delta.get(factor, np.nan)
                )
            summary["worst_factor_residual_delta"] = float(factor_delta.max())
            summaries.append(summary)
            selections.extend(current)
    return pd.DataFrame(summaries), pd.DataFrame(selections)


def _choose_selector(grid: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    eligible = grid.loc[
        grid["candidate_spearman"].ge(0.50)
        & grid["pooled_residual_delta"].le(-0.003)
        & grid["worst_factor_residual_delta"].le(0.002)
        & grid["selection_change_rate"].between(0.10, 0.75)
    ].copy()
    if eligible.empty:
        raise RuntimeError("No P4b selector passed the frozen development gate")
    metric_order = {name: index for index, name in enumerate(SELECTOR_METRICS)}
    eligible["metric_order"] = eligible["metric"].map(metric_order)
    eligible = eligible.sort_values(
        [
            "worst_factor_residual_delta",
            "pooled_residual_delta",
            "candidate_spearman",
            "metric_order",
            "risk_lambda",
            "variant",
        ],
        ascending=[True, True, False, True, True, True],
        kind="stable",
    )
    return eligible.iloc[0], eligible


def _write_plots(
    output_dir: Path,
    grid: pd.DataFrame,
    detection: pd.DataFrame,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    shown = grid.sort_values("pooled_residual_delta").head(20).copy()
    labels = (
        shown["variant"].astype(str)
        + " / "
        + shown["metric"].astype(str)
        + " / l="
        + shown["risk_lambda"].astype(str)
    )
    fig, axis = plt.subplots(figsize=(11, 7))
    axis.barh(labels[::-1], shown["pooled_relative_delta"][::-1] * 100)
    axis.axvline(0, color="black", linewidth=1)
    axis.set(xlabel="Selected minus max-value residual, % of baseline")
    fig.tight_layout()
    fig.savefig(output_dir / "selector_residual_reduction.png", dpi=180)
    plt.close(fig)

    pooled = detection.loc[detection["factor"].eq("All OOD")].sort_values(
        "balanced_average_precision", ascending=False
    )
    labels = pooled["variant"].astype(str) + " / " + pooled["metric"].astype(str)
    fig, axis = plt.subplots(figsize=(11, 8))
    axis.barh(labels[::-1], pooled["balanced_average_precision"][::-1])
    axis.set(xlabel="Class-balanced OOD average precision", xlim=(0, 1))
    fig.tight_layout()
    fig.savefig(output_dir / "robust_score_ood_detection.png", dpi=180)
    plt.close(fig)


def analyze(args: argparse.Namespace) -> dict[str, object]:
    manifest_path = args.manifest.expanduser().resolve()
    feature_path = args.features.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_parquet(manifest_path)
    with np.load(feature_path, allow_pickle=False) as payload:
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    scored_frames = []
    variant_metadata = []
    for variant_index, (name, artifact_dir) in enumerate(
        _artifact_specs(args.artifact)
    ):
        scored, metadata = _score_variant(
            manifest,
            arrays,
            name,
            artifact_dir,
            device=args.device,
            batch_size=args.batch_size,
            mc_samples=args.mc_samples,
            seed=args.seed + variant_index * 1009,
        )
        scored_frames.append(scored)
        variant_metadata.append(metadata)
    scored = pd.concat(scored_frames, ignore_index=True)
    correlations, detection = _metric_tables(scored)
    grid, selections = _selector_grid(scored, correlations, args.risk_lambda)
    chosen, eligible = _choose_selector(grid)
    chosen_variant = next(
        item for item in variant_metadata if item["variant"] == chosen["variant"]
    )
    artifact_dir = Path(str(chosen_variant["artifact_dir"]))
    relative_artifact = (
        str(artifact_dir.relative_to(PROJECT_ROOT))
        if artifact_dir.is_relative_to(PROJECT_ROOT)
        else str(artifact_dir)
    )
    selector = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "frozen_before_terminal_holdout",
        "variant": str(chosen["variant"]),
        "artifact_dir": relative_artifact,
        "artifact_manifest_sha256": chosen_variant["artifact_manifest_sha256"],
        "artifact_checksum_sha256": chosen_variant["artifact_checksum_sha256"],
        "variance_temperature": float(chosen_variant["variance_temperature"]),
        "risk_metric": str(chosen["metric"]),
        "risk_lambda": float(chosen["risk_lambda"]),
        "selection_formula": "z(candidate_value) - lambda * z(log(candidate_risk))",
        "development_gate": {
            "candidate_spearman_min": 0.50,
            "pooled_residual_delta_max": -0.003,
            "worst_factor_residual_delta_max": 0.002,
            "selection_change_rate_range": [0.10, 0.75],
        },
        "development_result": chosen.to_dict(),
        "terminal_holdout_gate": {
            "minimum_heterogeneous_snapshots": 20,
            "minimum_factors_with_five_heterogeneous_snapshots": 2,
            "paired_success_delta_strictly_positive": True,
            "cluster_bootstrap_ci_lower_min": 0.0,
            "rescues_must_exceed_harms": True,
            "drop_and_official_safety_must_not_increase": True,
        },
        "development_manifest": str(manifest_path),
        "development_manifest_sha256": sha256_file(manifest_path),
        "development_features_sha256": sha256_file(feature_path),
        "analysis_code_sha256": sha256_file(Path(__file__).resolve()),
    }
    selector_path = output_dir / "frozen_selector.json"
    selector_path.write_text(
        json.dumps(json_ready(selector), indent=2), encoding="utf-8"
    )
    (output_dir / "FROZEN_SELECTOR_SHA256").write_text(
        f"{sha256_file(selector_path)}  frozen_selector.json\n", encoding="utf-8"
    )
    scored.to_parquet(output_dir / "candidate_scores.parquet", index=False)
    correlations.to_csv(output_dir / "score_correlations.csv", index=False)
    detection.to_csv(output_dir / "ood_detection_metrics.csv", index=False)
    grid.to_csv(output_dir / "selector_grid.csv", index=False)
    eligible.to_csv(output_dir / "eligible_selectors.csv", index=False)
    chosen_rows = selections.loc[
        selections["variant"].eq(chosen["variant"])
        & selections["metric"].eq(chosen["metric"])
        & selections["risk_lambda"].eq(chosen["risk_lambda"])
    ]
    chosen_rows.to_csv(output_dir / "frozen_selector_development_rows.csv", index=False)
    pd.DataFrame(variant_metadata).to_csv(
        output_dir / "variant_calibration.csv", index=False
    )
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "development_pass",
        "rows": len(manifest),
        "variants": len(variant_metadata),
        "eligible_selectors": len(eligible),
        "chosen": chosen.to_dict(),
        "selector_sha256": sha256_file(selector_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(json_ready(summary), indent=2), encoding="utf-8"
    )
    _write_plots(output_dir, grid, detection)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--features", type=Path, required=True)
    result.add_argument("--artifact", action="append", required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--device", default="cuda")
    result.add_argument("--batch-size", type=int, default=512)
    result.add_argument("--mc-samples", type=int, default=32)
    result.add_argument(
        "--risk-lambda", type=float, action="append", default=[0.25, 0.5, 1.0, 2.0]
    )
    result.add_argument("--seed", type=int, default=20260907)
    return result


def main() -> int:
    print(json.dumps(json_ready(analyze(parser().parse_args())), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


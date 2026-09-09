#!/usr/bin/env python3
"""Evaluate a frozen P4b selector on prospective all-candidate terminal branches."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scripts.analyze_residual_dynamics_ensemble import (
        average_precision,
        balanced_average_precision,
        roc_auc,
    )
    from scripts.build_residual_dynamics_dataset import sha256_file
    from scripts.p4b_residual_risk import (
        artifact_variances,
        json_ready,
        predict_heads,
        residual_risk_scores,
        select_candidate,
    )
    from scripts.residual_dynamics_ensemble import ResidualPreprocessor
except ModuleNotFoundError:
    from analyze_residual_dynamics_ensemble import (
        average_precision,
        balanced_average_precision,
        roc_auc,
    )
    from build_residual_dynamics_dataset import sha256_file
    from p4b_residual_risk import (
        artifact_variances,
        json_ready,
        predict_heads,
        residual_risk_scores,
        select_candidate,
    )
    from residual_dynamics_ensemble import ResidualPreprocessor


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    return (
        values.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "yes"})
    )


def _resolve_artifact(selector: dict[str, object]) -> Path:
    path = Path(str(selector["artifact_dir"])).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not (path / "ensemble.json").is_file():
        raise FileNotFoundError(path)
    if sha256_file(path / "ensemble.json") != selector["artifact_manifest_sha256"]:
        raise RuntimeError("Frozen P4b artifact manifest hash mismatch")
    checksum = path / "SHA256SUMS"
    expected_checksum_hash = selector.get("artifact_checksum_sha256")
    if expected_checksum_hash and sha256_file(checksum) != expected_checksum_hash:
        raise RuntimeError("Frozen P4b SHA256SUMS hash mismatch")
    return path


def _campaign_complete(campaign_dir: Path) -> tuple[bool, int, int]:
    manifest_path = campaign_dir / "manifest.json"
    if not manifest_path.is_file():
        return False, 0, 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    results = {str(row.get("job")): row for row in payload.get("results", [])}
    completed = sum(
        str(results.get(str(job.get("name")), {}).get("status")) == "completed"
        for job in jobs
    )
    return payload.get("status") == "completed", completed, len(jobs)


def _paired_bootstrap_interval(
    rows: pd.DataFrame, *, repetitions: int, seed: int
) -> tuple[float, float]:
    groups = rows["group_id"].astype(str).unique()
    if not len(groups):
        return float("nan"), float("nan")
    by_group = {
        group: rows.loc[rows["group_id"].astype(str).eq(group), "success_delta"].to_numpy(
            dtype=float
        )
        for group in groups
    }
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        sampled = rng.choice(groups, size=len(groups), replace=True)
        values = np.concatenate([by_group[group] for group in sampled])
        estimates.append(float(values.mean()))
    return tuple(np.quantile(estimates, [0.025, 0.975]).astype(float))


def _mcnemar_p(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(rescues, harms) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def _select_rows(
    scored: pd.DataFrame, risk_metric: str, risk_lambda: float
) -> pd.DataFrame:
    records = []
    for snapshot_group, candidates in scored.groupby("snapshot_group", sort=False):
        candidates = candidates.sort_values("candidate_idx")
        values = candidates["candidate_value"].to_numpy(dtype=float)
        risk = candidates[risk_metric].to_numpy(dtype=float)
        baseline_position = int(np.nanargmax(values))
        selected_position = select_candidate(values, risk, risk_lambda)
        baseline = candidates.iloc[baseline_position]
        selected = candidates.iloc[selected_position]
        candidate_success = _bool_series(candidates["terminal_success"])
        records.append(
            {
                "snapshot_group": snapshot_group,
                "group_id": str(candidates.iloc[0]["group_id"]),
                "factor": str(candidates.iloc[0]["factor"]),
                "case_id": str(candidates.iloc[0]["case_id"]),
                "suite": str(candidates.iloc[0]["suite"]),
                "task_id": int(candidates.iloc[0]["task_id"]),
                "query_idx": int(candidates.iloc[0]["query_idx"]),
                "candidates": len(candidates),
                "heterogeneous_outcomes": candidate_success.nunique() > 1,
                "baseline_candidate_idx": int(baseline["candidate_idx"]),
                "selected_candidate_idx": int(selected["candidate_idx"]),
                "selection_changed": baseline_position != selected_position,
                "baseline_value": float(baseline["candidate_value"]),
                "selected_value": float(selected["candidate_value"]),
                "baseline_risk": float(baseline[risk_metric]),
                "selected_risk": float(selected[risk_metric]),
                "baseline_success": bool(
                    _bool_series(pd.Series([baseline["terminal_success"]])).iloc[0]
                ),
                "selected_success": bool(
                    _bool_series(pd.Series([selected["terminal_success"]])).iloc[0]
                ),
                "oracle_success": bool(candidate_success.any()),
                "baseline_drop": bool(
                    _bool_series(
                        pd.Series([baseline["terminal_target_drop_candidate"]])
                    ).iloc[0]
                ),
                "selected_drop": bool(
                    _bool_series(
                        pd.Series([selected["terminal_target_drop_candidate"]])
                    ).iloc[0]
                ),
                "baseline_official_safety": bool(
                    _bool_series(
                        pd.Series([baseline["terminal_official_safety_violation"]])
                    ).iloc[0]
                ),
                "selected_official_safety": bool(
                    _bool_series(
                        pd.Series([selected["terminal_official_safety_violation"]])
                    ).iloc[0]
                ),
                "baseline_final_t": float(baseline["terminal_final_t"]),
                "selected_final_t": float(selected["terminal_final_t"]),
            }
        )
    frame = pd.DataFrame(records)
    frame["success_delta"] = (
        frame["selected_success"].astype(int) - frame["baseline_success"].astype(int)
    )
    frame["drop_delta"] = (
        frame["selected_drop"].astype(int) - frame["baseline_drop"].astype(int)
    )
    frame["official_safety_delta"] = (
        frame["selected_official_safety"].astype(int)
        - frame["baseline_official_safety"].astype(int)
    )
    return frame


def _summary_table(rows: pd.DataFrame) -> pd.DataFrame:
    records = []
    for scope, current in [
        *[(factor, part) for factor, part in rows.groupby("factor")],
        *[(case_id, part) for case_id, part in rows.groupby("case_id")],
        ("All", rows),
    ]:
        records.append(
            {
                "scope": scope,
                "snapshots": len(current),
                "heterogeneous_snapshots": int(current["heterogeneous_outcomes"].sum()),
                "baseline_success_rate": float(current["baseline_success"].mean()),
                "selected_success_rate": float(current["selected_success"].mean()),
                "oracle_success_rate": float(current["oracle_success"].mean()),
                "paired_success_delta": float(current["success_delta"].mean()),
                "rescues": int(current["success_delta"].eq(1).sum()),
                "harms": int(current["success_delta"].eq(-1).sum()),
                "selection_change_rate": float(current["selection_changed"].mean()),
                "drop_delta": float(current["drop_delta"].mean()),
                "official_safety_delta": float(
                    current["official_safety_delta"].mean()
                ),
            }
        )
    return pd.DataFrame(records)


def _write_plots(output_dir: Path, rows: pd.DataFrame, scored: pd.DataFrame, metric: str):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    table = _summary_table(rows)
    shown = table.loc[table["scope"].isin(["Environment", "Object", "Position", "All"])]
    positions = np.arange(len(shown))
    width = 0.25
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.bar(positions - width, shown["baseline_success_rate"], width, label="max value")
    axis.bar(positions, shown["selected_success_rate"], width, label="P4b")
    axis.bar(positions + width, shown["oracle_success_rate"], width, label="oracle")
    axis.set_xticks(positions, shown["scope"])
    axis.set(ylabel="Terminal success rate", ylim=(0, 1))
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_dir / "terminal_success_comparison.png", dpi=180)
    plt.close(fig)

    success = _bool_series(scored["terminal_success"])
    fig, axis = plt.subplots(figsize=(8, 5))
    axis.boxplot(
        [scored.loc[success, metric], scored.loc[~success, metric]],
        tick_labels=["success", "failure"],
        showfliers=False,
    )
    axis.set(ylabel=metric)
    fig.tight_layout()
    fig.savefig(output_dir / "candidate_risk_by_terminal_outcome.png", dpi=180)
    plt.close(fig)


def analyze(args: argparse.Namespace) -> dict[str, object]:
    campaign_dir = args.campaign_dir.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    feature_path = args.features.expanduser().resolve()
    selector_path = args.selector.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selector = json.loads(selector_path.read_text(encoding="utf-8"))
    if selector.get("status") != "frozen_before_terminal_holdout":
        raise RuntimeError("Selector was not frozen before terminal holdout")
    artifact_dir = _resolve_artifact(selector)
    manifest = pd.read_parquet(manifest_path)
    with np.load(feature_path, allow_pickle=False) as payload:
        arrays = {key: np.asarray(payload[key]) for key in payload.files}
    preprocessor = ResidualPreprocessor.load(artifact_dir / "preprocessing.npz")
    indices = np.arange(len(manifest), dtype=np.int64)
    inputs = preprocessor.transform_input(arrays, indices)
    means, predicted_variances = predict_heads(
        inputs, artifact_dir, device=args.device, batch_size=args.batch_size
    )
    variances = artifact_variances(predicted_variances, artifact_dir)
    scores = residual_risk_scores(
        means,
        variances,
        temperature=float(selector["variance_temperature"]),
        mc_samples_per_head=args.mc_samples,
        mc_seed=args.seed,
        mc_device=args.device,
    )
    scored = manifest.copy()
    for name, values in scores.items():
        scored[name] = values

    expected_candidates = pd.to_numeric(scored["num_candidates"], errors="coerce")
    terminal_available = _bool_series(scored["terminal_available"])
    complete_groups = scored.groupby("snapshot_group").agg(
        rows=("candidate_idx", "size"),
        unique_candidates=("candidate_idx", "nunique"),
        expected_candidates=("num_candidates", "first"),
        terminal_rows=("terminal_available", lambda values: int(_bool_series(values).sum())),
    )
    complete_mask = (
        complete_groups["rows"].eq(complete_groups["expected_candidates"])
        & complete_groups["unique_candidates"].eq(complete_groups["expected_candidates"])
        & complete_groups["terminal_rows"].eq(complete_groups["expected_candidates"])
    )
    valid_groups = complete_groups.index[complete_mask]
    valid = scored.loc[scored["snapshot_group"].isin(valid_groups)].copy()
    if valid.empty:
        raise RuntimeError("No complete all-candidate terminal snapshots")

    metric = str(selector["risk_metric"])
    rows = _select_rows(valid, metric, float(selector["risk_lambda"]))
    low, high = _paired_bootstrap_interval(
        rows, repetitions=args.bootstrap_repetitions, seed=args.seed
    )
    summary_table = _summary_table(rows)
    terminal_success = _bool_series(valid["terminal_success"])
    failure = ~terminal_success.to_numpy()
    risk = valid[metric].to_numpy(dtype=float)
    factor_heterogeneous = (
        rows.groupby("factor")["heterogeneous_outcomes"].sum().astype(int)
    )
    complete, completed_jobs, total_jobs = _campaign_complete(campaign_dir)
    replay_values = pd.to_numeric(
        valid.get("main_open_replay_state_max_abs", pd.Series(np.nan, index=valid.index)),
        errors="coerce",
    )
    replay_max = float(replay_values.max()) if replay_values.notna().any() else float("nan")
    rescues = int(rows["success_delta"].eq(1).sum())
    harms = int(rows["success_delta"].eq(-1).sum())
    gate_components = {
        "campaign_complete": complete and completed_jobs == total_jobs,
        "complete_snapshot_fraction": float(complete_mask.mean()) >= 0.98,
        "terminal_row_fraction": float(terminal_available.mean()) >= 0.98,
        "exact_replay": np.isfinite(replay_max) and replay_max <= 1e-9,
        "heterogeneous_snapshots": int(rows["heterogeneous_outcomes"].sum()) >= 20,
        "factor_coverage": int(factor_heterogeneous.ge(5).sum()) >= 2,
        "positive_success_delta": float(rows["success_delta"].mean()) > 0,
        "nonnegative_ci_lower": low >= 0.0,
        "rescues_exceed_harms": rescues > harms,
        "drop_nonincrease": float(rows["drop_delta"].mean()) <= 0.0,
        "official_safety_nonincrease": float(
            rows["official_safety_delta"].mean()
        )
        <= 0.0,
    }
    gate_pass = all(gate_components.values())
    summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "completed_pass" if gate_pass else "completed_no_go",
        "selector_sha256": sha256_file(selector_path),
        "manifest_sha256": sha256_file(manifest_path),
        "features_sha256": sha256_file(feature_path),
        "candidate_rows": len(scored),
        "expected_candidate_rows": int(expected_candidates.sum() / expected_candidates.median()),
        "terminal_row_fraction": float(terminal_available.mean()),
        "snapshots": int(scored["snapshot_group"].nunique()),
        "complete_snapshots": len(valid_groups),
        "complete_snapshot_fraction": float(complete_mask.mean()),
        "replay_max_abs": replay_max,
        "risk_metric": metric,
        "risk_lambda": float(selector["risk_lambda"]),
        "candidate_failure_roc_auc": roc_auc(failure, risk),
        "candidate_failure_average_precision": average_precision(failure, risk),
        "candidate_failure_balanced_average_precision": balanced_average_precision(
            failure, risk
        ),
        "baseline_success_rate": float(rows["baseline_success"].mean()),
        "selected_success_rate": float(rows["selected_success"].mean()),
        "oracle_success_rate": float(rows["oracle_success"].mean()),
        "paired_success_delta": float(rows["success_delta"].mean()),
        "paired_success_delta_ci": [low, high],
        "rescues": rescues,
        "harms": harms,
        "mcnemar_p": _mcnemar_p(rescues, harms),
        "heterogeneous_snapshots": int(rows["heterogeneous_outcomes"].sum()),
        "factor_heterogeneous_snapshots": factor_heterogeneous.to_dict(),
        "selection_change_rate": float(rows["selection_changed"].mean()),
        "drop_delta": float(rows["drop_delta"].mean()),
        "official_safety_delta": float(rows["official_safety_delta"].mean()),
        "gate_components": gate_components,
        "offline_gate_pass": gate_pass,
    }
    scored.to_parquet(output_dir / "candidate_scores.parquet", index=False)
    rows.to_csv(output_dir / "paired_selections.csv", index=False)
    summary_table.to_csv(output_dir / "factor_case_summary.csv", index=False)
    pd.DataFrame(
        [{"factor": key, "heterogeneous_snapshots": value} for key, value in factor_heterogeneous.items()]
    ).to_csv(output_dir / "heterogeneous_snapshot_counts.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(json_ready(summary), indent=2), encoding="utf-8"
    )
    _write_plots(output_dir, rows, valid, metric)
    return summary


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--campaign-dir", type=Path, required=True)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--features", type=Path, required=True)
    result.add_argument("--selector", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--device", default="cuda")
    result.add_argument("--batch-size", type=int, default=512)
    result.add_argument("--mc-samples", type=int, default=32)
    result.add_argument("--bootstrap-repetitions", type=int, default=5000)
    result.add_argument("--seed", type=int, default=20260907)
    return result


def main() -> int:
    print(json.dumps(json_ready(analyze(parser().parse_args())), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


#!/usr/bin/env python3
"""Freeze and evaluate the preregistered factor-specific H16 candidate ranker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from analyze_counterfactual_feedback import CANDIDATE_RANK_FEATURES
    from counterfactual_feedback_utils import deterministic_unit_interval
except ModuleNotFoundError:  # Imported as scripts.frozen_candidate_ranker in tests.
    from scripts.analyze_counterfactual_feedback import CANDIDATE_RANK_FEATURES
    from scripts.counterfactual_feedback_utils import deterministic_unit_interval


MODEL_SCHEMA_VERSION = 1
DEFAULT_TARGET = "dense_utility_v2"
DEFAULT_ALPHA = 1.0
DEFAULT_BOOTSTRAP_SEED = 2_026_08_28


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _factor(frame: pd.DataFrame) -> pd.Series:
    if "factor" in frame:
        return frame["factor"].astype(str)
    case = frame.get("case_id", pd.Series("", index=frame.index)).astype(str)
    suite = frame.get("suite", pd.Series("", index=frame.index)).astype(str)
    result = pd.Series("Object", index=frame.index, dtype=object)
    result.loc[case.str.contains("position", case=False) | suite.str.contains("temp")] = (
        "Position"
    )
    result.loc[
        case.str.contains("environment", case=False) | suite.str.contains("env")
    ] = "Environment"
    return result


def prepare_candidates(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"snapshot_id", "suite", "task_id", "init_state_id", "candidate_idx"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Candidate table is missing required columns: {missing}")
    result = frame.copy()
    result["factor"] = _factor(result)
    if "analysis_snapshot_id" not in result:
        if "source_run" in result:
            result["analysis_snapshot_id"] = (
                result["source_run"].astype(str) + "::" + result["snapshot_id"].astype(str)
            )
        else:
            result["analysis_snapshot_id"] = result["snapshot_id"].astype(str)
    result["independent_group"] = (
        result["factor"].astype(str)
        + "|"
        + result["suite"].astype(str)
        + "|"
        + result["task_id"].astype(str)
        + "|"
        + result["init_state_id"].astype(str)
    )
    return result


def read_candidates(path: Path) -> pd.DataFrame:
    resolved = path.expanduser().resolve()
    frame = pd.read_parquet(resolved) if resolved.suffix == ".parquet" else pd.read_csv(resolved)
    return prepare_candidates(frame)


def _within_snapshot_z(frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    numeric = frame[list(features)].apply(pd.to_numeric, errors="coerce")
    grouped = numeric.groupby(frame["analysis_snapshot_id"])
    means = grouped.transform("mean")
    std = grouped.transform(lambda values: values.std(ddof=0))
    std = std.mask(~np.isfinite(std) | (std < 1e-8), 1.0)
    return ((numeric - means) / std).to_numpy(dtype=float)


def _centered_target(frame: pd.DataFrame, target: str) -> np.ndarray:
    values = pd.to_numeric(frame[target], errors="coerce")
    means = values.groupby(frame["analysis_snapshot_id"]).transform("mean")
    return (values - means).to_numpy(dtype=float)


def fit_frozen_model(
    candidates: pd.DataFrame,
    *,
    target: str = DEFAULT_TARGET,
    features: Sequence[str] = CANDIDATE_RANK_FEATURES,
    alpha: float = DEFAULT_ALPHA,
    source_path: Path | None = None,
) -> dict[str, Any]:
    frame = prepare_candidates(candidates)
    if target not in frame:
        raise ValueError(f"Training target is missing: {target}")
    missing_features = [feature for feature in features if feature not in frame]
    if missing_features:
        raise ValueError(f"Frozen feature set is incomplete: {missing_features}")
    if alpha <= 0:
        raise ValueError("Ridge alpha must be positive")

    factors: dict[str, Any] = {}
    for factor, scoped in frame.groupby("factor", sort=True):
        scoped = scoped.reset_index(drop=True)
        x = _within_snapshot_z(scoped, features)
        y = _centered_target(scoped, target)
        valid = np.isfinite(y)
        if valid.sum() < len(features) + 2:
            raise ValueError(
                f"{factor}: {valid.sum()} valid rows are insufficient for {len(features)} features"
            )
        median = np.nanmedian(x[valid], axis=0)
        median = np.where(np.isfinite(median), median, 0.0)
        x_train = np.where(np.isfinite(x[valid]), x[valid], median)
        mean = x_train.mean(axis=0)
        std = x_train.std(axis=0)
        std[std < 1e-8] = 1.0
        x_train = (x_train - mean) / std
        penalty = np.eye(x_train.shape[1], dtype=float) * float(alpha)
        coefficients = (
            np.linalg.pinv(x_train.T @ x_train + penalty) @ x_train.T @ y[valid]
        )
        factors[str(factor)] = {
            "candidate_rows": int(valid.sum()),
            "snapshots": int(scoped.loc[valid, "analysis_snapshot_id"].nunique()),
            "independent_groups": int(scoped.loc[valid, "independent_group"].nunique()),
            "impute_median": median.tolist(),
            "standardization_mean": mean.tolist(),
            "standardization_std": std.tolist(),
            "coefficients": coefficients.tolist(),
        }

    source = source_path.expanduser().resolve() if source_path is not None else None
    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_name": "factor_h16_dense_ridge_v1",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "features": list(features),
        "alpha": float(alpha),
        "training_source": str(source) if source is not None else "in-memory",
        "training_source_sha256": _sha256(source) if source is not None else None,
        "training_groups": sorted(frame["independent_group"].unique().tolist()),
        "factors": factors,
    }
    canonical = json.dumps(model, sort_keys=True, separators=(",", ":")).encode("utf-8")
    model["frozen_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    return model


def write_model(model: Mapping[str, Any], path: Path) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")


def read_model(path: Path) -> dict[str, Any]:
    model = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if model.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise ValueError(f"Unsupported frozen model schema: {model.get('schema_version')}")
    return model


def predict_frozen_model(candidates: pd.DataFrame, model: Mapping[str, Any]) -> np.ndarray:
    frame = prepare_candidates(candidates)
    features = list(model["features"])
    missing = [feature for feature in features if feature not in frame]
    if missing:
        raise ValueError(f"Holdout feature set is incomplete: {missing}")
    scores = np.full(len(frame), np.nan, dtype=float)
    for factor, indices in frame.groupby("factor", sort=False).groups.items():
        parameters = model["factors"].get(str(factor))
        if parameters is None:
            raise ValueError(f"Frozen model has no factor head for {factor}")
        positions = frame.index.get_indexer(indices)
        scoped = frame.loc[indices].reset_index(drop=True)
        x = _within_snapshot_z(scoped, features)
        median = np.asarray(parameters["impute_median"], dtype=float)
        mean = np.asarray(parameters["standardization_mean"], dtype=float)
        std = np.asarray(parameters["standardization_std"], dtype=float)
        coefficients = np.asarray(parameters["coefficients"], dtype=float)
        x = np.where(np.isfinite(x), x, median)
        scores[positions] = ((x - mean) / std) @ coefficients
    return scores


def group_overlap(candidates: pd.DataFrame, model: Mapping[str, Any]) -> list[str]:
    frame = prepare_candidates(candidates)
    return sorted(set(frame["independent_group"]) & set(model["training_groups"]))


def candidate_selection_outcomes(
    candidates: pd.DataFrame,
    frozen_scores: Sequence[float],
    *,
    target: str,
) -> pd.DataFrame:
    frame = prepare_candidates(candidates)
    scores = np.asarray(frozen_scores, dtype=float)
    if len(scores) != len(frame):
        raise ValueError(f"Expected {len(frame)} frozen scores, got {len(scores)}")
    frame["frozen_ranker_score"] = scores
    rows: list[dict[str, Any]] = []
    for snapshot_id, group in frame.groupby("analysis_snapshot_id", sort=False):
        utility = pd.to_numeric(group[target], errors="coerce").to_numpy(dtype=float)
        if len(utility) < 2 or not np.isfinite(utility).all():
            continue
        value = pd.to_numeric(group["candidate_value"], errors="coerce").to_numpy(dtype=float)
        frozen = pd.to_numeric(group["frozen_ranker_score"], errors="coerce").to_numpy(
            dtype=float
        )
        random_score = np.asarray(
            [
                deterministic_unit_interval("frozen-ranker-holdout", snapshot_id, index)
                for index in group["candidate_idx"]
            ],
            dtype=float,
        )
        selectors = {
            "cosmos_value": value,
            "random": random_score,
            "frozen_factor_ridge": frozen,
            "oracle": utility,
        }
        best = float(np.max(utility))
        best_indices = set(np.flatnonzero(np.isclose(utility, best)).tolist())
        for method, method_scores in selectors.items():
            if not np.isfinite(method_scores).any():
                continue
            selected = int(np.nanargmax(method_scores))
            rows.append(
                {
                    "analysis_snapshot_id": snapshot_id,
                    "factor": str(group["factor"].iloc[0]),
                    "independent_group": str(group["independent_group"].iloc[0]),
                    "phase": str(group.get("phase_at_snapshot", pd.Series("unknown")).iloc[0]),
                    "method": method,
                    "selected_candidate_idx": int(group.iloc[selected]["candidate_idx"]),
                    "selected_utility": float(utility[selected]),
                    "oracle_utility": best,
                    "regret": float(best - utility[selected]),
                    "top1_correct": bool(selected in best_indices),
                }
            )
    return pd.DataFrame(rows)


def summarize_outcomes(outcomes: pd.DataFrame) -> pd.DataFrame:
    if outcomes.empty:
        return pd.DataFrame()
    snapshot = (
        outcomes.groupby(["factor", "method"], as_index=False)
        .agg(
            snapshots=("analysis_snapshot_id", "count"),
            independent_groups=("independent_group", "nunique"),
            mean_selected_utility=("selected_utility", "mean"),
            mean_regret=("regret", "mean"),
            top1_accuracy=("top1_correct", "mean"),
        )
    )
    group_regret = (
        outcomes.groupby(["factor", "method", "independent_group"], as_index=False)[
            "regret"
        ]
        .mean()
        .groupby(["factor", "method"], as_index=False)["regret"]
        .mean()
        .rename(columns={"regret": "group_macro_mean_regret"})
    )
    return snapshot.merge(group_regret, on=["factor", "method"], how="left")


def grouped_bootstrap_regret_delta(
    outcomes: pd.DataFrame,
    *,
    draws: int = 5000,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if draws < 100:
        raise ValueError("Use at least 100 grouped-bootstrap draws")
    pivot = outcomes.pivot_table(
        index=["factor", "independent_group", "analysis_snapshot_id"],
        columns="method",
        values="regret",
        aggfunc="first",
    ).reset_index()
    required = {"cosmos_value", "frozen_factor_ridge"}
    if not required.issubset(pivot.columns):
        raise ValueError("Both Cosmos and frozen-ranker outcomes are required")
    pivot["regret_delta"] = pivot["frozen_factor_ridge"] - pivot["cosmos_value"]
    group_delta = (
        pivot.groupby(["factor", "independent_group"], as_index=False)["regret_delta"]
        .mean()
    )
    rng = np.random.default_rng(seed)
    factors = sorted(group_delta["factor"].unique())
    samples: dict[str, np.ndarray] = {}
    for factor in factors:
        values = group_delta.loc[group_delta["factor"].eq(factor), "regret_delta"].to_numpy(
            dtype=float
        )
        indices = rng.integers(0, len(values), size=(draws, len(values)))
        samples[factor] = values[indices].mean(axis=1)
    draw_rows = []
    for factor, values in samples.items():
        draw_rows.extend(
            {"draw": index, "factor": factor, "regret_delta": float(value)}
            for index, value in enumerate(values)
        )
    macro = np.vstack([samples[factor] for factor in factors]).mean(axis=0)
    draw_rows.extend(
        {"draw": index, "factor": "All", "regret_delta": float(value)}
        for index, value in enumerate(macro)
    )
    bootstrap = pd.DataFrame(draw_rows)

    point_by_factor = group_delta.groupby("factor")["regret_delta"].mean().to_dict()
    point_by_factor["All"] = float(np.mean(list(point_by_factor.values())))
    ci_rows = []
    for factor in [*factors, "All"]:
        values = bootstrap.loc[bootstrap["factor"].eq(factor), "regret_delta"]
        groups = (
            int(group_delta.loc[group_delta["factor"].eq(factor), "independent_group"].nunique())
            if factor != "All"
            else int(group_delta["independent_group"].nunique())
        )
        ci_rows.append(
            {
                "factor": factor,
                "independent_groups": groups,
                "regret_delta_frozen_minus_cosmos": float(point_by_factor[factor]),
                "ci95_lower": float(values.quantile(0.025)),
                "ci95_upper": float(values.quantile(0.975)),
                "probability_delta_below_zero": float((values < 0).mean()),
            }
        )
    return bootstrap, pd.DataFrame(ci_rows)


def holdout_gate(
    intervals: pd.DataFrame,
    *,
    overlap: Sequence[str],
    expected_factors: Sequence[str],
    required_groups: int,
) -> dict[str, Any]:
    per_factor = intervals.loc[intervals["factor"].isin(expected_factors)].copy()
    macro = intervals.loc[intervals["factor"].eq("All")]
    enough_groups = bool(
        len(per_factor) == len(expected_factors)
        and (per_factor["independent_groups"] >= required_groups).all()
    )
    every_factor_improves = bool(
        len(per_factor) == len(expected_factors)
        and (per_factor["regret_delta_frozen_minus_cosmos"] < 0).all()
    )
    macro_ci_below_zero = bool(len(macro) == 1 and float(macro.iloc[0]["ci95_upper"]) < 0)
    no_group_overlap = not overlap
    return {
        "passed": bool(
            enough_groups
            and every_factor_improves
            and macro_ci_below_zero
            and no_group_overlap
        ),
        "required_groups_per_factor": int(required_groups),
        "enough_independent_groups": enough_groups,
        "every_factor_regret_improves": every_factor_improves,
        "macro_ci95_upper_below_zero": macro_ci_below_zero,
        "no_train_holdout_group_overlap": no_group_overlap,
        "overlapping_groups": list(overlap),
    }


def _plot_regret(summary: pd.DataFrame, output_path: Path) -> None:
    methods = ["cosmos_value", "random", "frozen_factor_ridge", "oracle"]
    factors = sorted(summary["factor"].unique())
    x = np.arange(len(factors), dtype=float)
    width = 0.2
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#4b5563", "#d97706", "#2563eb", "#2d6a4f"]
    for offset, (method, color) in enumerate(zip(methods, colors)):
        values = (
            summary.loc[summary["method"].eq(method)]
            .set_index("factor")
            .reindex(factors)["group_macro_mean_regret"]
        )
        ax.bar(x + (offset - 1.5) * width, values, width, label=method, color=color)
    ax.set_xticks(x, factors)
    ax.set_ylabel("group-macro H16 consequence regret")
    ax.set_title("Frozen ranker held-out candidate selection")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_regret_delta(intervals: pd.DataFrame, output_path: Path) -> None:
    scoped = intervals.loc[intervals["factor"].ne("All")].copy()
    scoped = scoped.sort_values("factor").reset_index(drop=True)
    point = scoped["regret_delta_frozen_minus_cosmos"].to_numpy(dtype=float)
    lower = scoped["ci95_lower"].to_numpy(dtype=float)
    upper = scoped["ci95_upper"].to_numpy(dtype=float)
    errors = np.vstack([point - lower, upper - point])

    fig, ax = plt.subplots(figsize=(8, 4.8))
    colors = ["#2d6a4f" if bound < 0 else "#2563eb" for bound in upper]
    y = np.arange(len(scoped), dtype=float)
    for index, color in enumerate(colors):
        ax.errorbar(
            point[index],
            y[index],
            xerr=errors[:, index : index + 1],
            fmt="none",
            ecolor=color,
            elinewidth=2,
            capsize=5,
        )
    ax.scatter(point, y, c=colors, s=55, zorder=3)
    ax.axvline(0.0, color="#111827", linewidth=1, linestyle="--")
    ax.set_yticks(y, scoped["factor"])
    ax.set_xlabel("regret delta: frozen ranker - Cosmos value (lower is better)")
    ax.set_title("Held-out group-bootstrap effect with 95% intervals")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def evaluate_holdout(
    candidates: pd.DataFrame,
    model: Mapping[str, Any],
    *,
    output_dir: Path,
    draws: int,
    seed: int,
    required_groups: int,
    allow_overlap: bool = False,
) -> dict[str, Any]:
    frame = prepare_candidates(candidates)
    target = str(model["target"])
    if target not in frame:
        raise ValueError(f"Holdout target is missing: {target}")
    overlap = group_overlap(frame, model)
    if overlap and not allow_overlap:
        raise ValueError(f"Train/holdout task-init overlap: {overlap}")
    scores = predict_frozen_model(frame, model)
    outcomes = candidate_selection_outcomes(frame, scores, target=target)
    summary = summarize_outcomes(outcomes)
    bootstrap, intervals = grouped_bootstrap_regret_delta(outcomes, draws=draws, seed=seed)
    expected_factors = sorted(model["factors"])
    gate = holdout_gate(
        intervals,
        overlap=overlap,
        expected_factors=expected_factors,
        required_groups=required_groups,
    )

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    scored = frame.copy()
    scored["frozen_ranker_score"] = scores
    scored.to_parquet(output / "holdout_candidate_scores.parquet", index=False)
    outcomes.to_csv(output / "holdout_selection_outcomes.csv", index=False)
    summary.to_csv(output / "holdout_factor_summary.csv", index=False)
    intervals.to_csv(output / "grouped_bootstrap_intervals.csv", index=False)
    bootstrap.to_parquet(output / "grouped_bootstrap_draws.parquet", index=False)
    _plot_regret(summary, output / "heldout_candidate_regret.png")
    _plot_regret_delta(intervals, output / "heldout_regret_delta_ci.png")

    result = {
        "model_name": model["model_name"],
        "model_frozen_payload_sha256": model["frozen_payload_sha256"],
        "target": target,
        "candidate_rows": int(len(frame)),
        "snapshots": int(frame["analysis_snapshot_id"].nunique()),
        "independent_groups": int(frame["independent_group"].nunique()),
        "bootstrap_draws": int(draws),
        "bootstrap_seed": int(seed),
        "gate": gate,
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Frozen H16 candidate ranker holdout",
        "",
        f"- Frozen model: `{model['model_name']}` (`{model['frozen_payload_sha256']}`).",
        f"- Holdout: **{result['snapshots']} states**, **{result['independent_groups']} independent task/init groups**.",
        f"- Formal gate: **{'PASS' if gate['passed'] else 'FAIL'}**.",
        "- Primary delta is group-macro regret of `frozen_factor_ridge - cosmos_value`; negative is better.",
        "",
        "## Regret",
        "",
        summary.to_markdown(index=False),
        "",
        "## Grouped bootstrap",
        "",
        intervals.to_markdown(index=False),
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(gate, indent=2),
        "```",
        "",
        "The model was not refit on holdout data. Phase is reported only for analysis and was not used to select states.",
    ]
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--train-candidates", type=Path, required=True)
    freeze.add_argument("--output-model", type=Path, required=True)
    freeze.add_argument("--target", default=DEFAULT_TARGET)
    freeze.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--model", type=Path, required=True)
    evaluate.add_argument("--holdout-candidates", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--bootstrap-draws", type=int, default=5000)
    evaluate.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    evaluate.add_argument("--required-groups", type=int, default=20)
    evaluate.add_argument("--allow-overlap", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "freeze":
        source = args.train_candidates.expanduser().resolve()
        model = fit_frozen_model(
            read_candidates(source),
            target=args.target,
            alpha=args.alpha,
            source_path=source,
        )
        write_model(model, args.output_model)
        print(json.dumps(model, indent=2))
        return
    model = read_model(args.model)
    holdout = read_candidates(args.holdout_candidates)
    result = evaluate_holdout(
        holdout,
        model,
        output_dir=args.output_dir,
        draws=args.bootstrap_draws,
        seed=args.bootstrap_seed,
        required_groups=args.required_groups,
        allow_overlap=args.allow_overlap,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

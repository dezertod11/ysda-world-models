#!/usr/bin/env python3
"""Extract deployable CLIP consequence features and evaluate dense VoF."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


MODEL_NAME = "openai/clip-vit-base-patch32"
RIDGE_ALPHA = 10.0
QUERY_COST = 0.025
EXPECTED_ROWS = 265
BUDGETS = (0.10, 0.20, 0.30)

SCALAR_FEATURES = [
    "value_mean",
    "value_std",
    "value_range",
    "action_std_mean",
    "action_first_step_l2_std",
    "action_pairwise_l2_mean",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "candidate_action_internal_consistency_mean",
    "candidate_future_proprio_internal_consistency_mean",
]

SEMANTIC_FEATURES = [
    "clip_agent_current_goal",
    "clip_agent_selected_goal_delta",
    "clip_agent_selected_motion",
    "clip_agent_candidate_goal_delta_mean",
    "clip_agent_candidate_goal_delta_std",
    "clip_agent_candidate_goal_delta_max",
    "clip_agent_candidate_goal_delta_range",
    "clip_agent_selected_goal_rank",
    "clip_agent_candidate_disagreement",
    "clip_agent_candidate_motion_mean",
    "clip_agent_selected_centroid_distance",
    "clip_wrist_selected_motion",
    "clip_wrist_candidate_disagreement",
    "clip_wrist_candidate_motion_mean",
    "clip_cross_view_current",
    "clip_cross_view_selected",
]

PRIVILEGED_TOKENS = (
    "endpoint",
    "terminal",
    "actual",
    "sim_",
    "object_state",
    "contact",
    "success",
    "drop",
    "wrong_object",
    "vof",
    "utility",
)


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def normalize_rows(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    denom = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.clip(denom, 1e-12, None)


def mean_pairwise_cosine_distance(values: np.ndarray) -> float:
    values = normalize_rows(values)
    if len(values) < 2:
        return 0.0
    distances = 1.0 - values @ values.T
    upper = distances[np.triu_indices(len(values), k=1)]
    return float(np.mean(upper))


def _rank_fraction(values: np.ndarray, selected: int) -> float:
    if len(values) <= 1:
        return 1.0
    ranks = rankdata(values, method="average")
    return float((ranks[selected] - 1.0) / (len(values) - 1.0))


def semantic_record(
    current_agent: np.ndarray,
    future_agents: np.ndarray,
    current_wrist: np.ndarray,
    future_wrists: np.ndarray,
    text: np.ndarray,
    selected: int,
) -> dict[str, float]:
    current_agent = normalize_rows(current_agent.reshape(1, -1))[0]
    future_agents = normalize_rows(future_agents)
    current_wrist = normalize_rows(current_wrist.reshape(1, -1))[0]
    future_wrists = normalize_rows(future_wrists)
    text = normalize_rows(text.reshape(1, -1))[0]

    agent_goal_current = float(current_agent @ text)
    agent_goals = future_agents @ text
    goal_delta = agent_goals - agent_goal_current
    agent_motion = 1.0 - future_agents @ current_agent
    wrist_motion = 1.0 - future_wrists @ current_wrist
    agent_centroid = normalize_rows(future_agents.mean(axis=0, keepdims=True))[0]
    return {
        "clip_agent_current_goal": agent_goal_current,
        "clip_agent_selected_goal_delta": float(goal_delta[selected]),
        "clip_agent_selected_motion": float(agent_motion[selected]),
        "clip_agent_candidate_goal_delta_mean": float(np.mean(goal_delta)),
        "clip_agent_candidate_goal_delta_std": float(np.std(goal_delta)),
        "clip_agent_candidate_goal_delta_max": float(np.max(goal_delta)),
        "clip_agent_candidate_goal_delta_range": float(np.ptp(goal_delta)),
        "clip_agent_selected_goal_rank": _rank_fraction(agent_goals, selected),
        "clip_agent_candidate_disagreement": mean_pairwise_cosine_distance(future_agents),
        "clip_agent_candidate_motion_mean": float(np.mean(agent_motion)),
        "clip_agent_selected_centroid_distance": float(
            1.0 - future_agents[selected] @ agent_centroid
        ),
        "clip_wrist_selected_motion": float(wrist_motion[selected]),
        "clip_wrist_candidate_disagreement": mean_pairwise_cosine_distance(future_wrists),
        "clip_wrist_candidate_motion_mean": float(np.mean(wrist_motion)),
        "clip_cross_view_current": float(1.0 - current_agent @ current_wrist),
        "clip_cross_view_selected": float(
            1.0 - future_agents[selected] @ future_wrists[selected]
        ),
    }


def _resolve_sidecar(path: str, project_root: Path) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    marker = "/experiments/"
    if marker in path:
        candidate = project_root / "experiments" / path.split(marker, 1)[1]
    if not candidate.exists():
        raise FileNotFoundError(path)
    return candidate


def _encode_images(model: Any, processor: Any, arrays: list[np.ndarray], device: str) -> np.ndarray:
    import torch
    from PIL import Image

    images = [Image.fromarray(np.asarray(array, dtype=np.uint8)) for array in arrays]
    inputs = processor(images=images, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)
    with torch.inference_mode():
        features = model.get_image_features(pixel_values=pixel_values)
    return normalize_rows(features.float().cpu().numpy())


def extract_features(
    pairs: pd.DataFrame,
    *,
    project_root: Path,
    model_name: str,
    device: str,
    row_batch_size: int,
) -> pd.DataFrame:
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model = CLIPModel.from_pretrained(model_name, local_files_only=True).to(device)
    model.eval()
    processor = CLIPProcessor.from_pretrained(model_name, local_files_only=True)

    descriptions = sorted(pairs["task_description"].astype(str).unique())
    text_inputs = processor(text=descriptions, return_tensors="pt", padding=True)
    text_inputs = {key: value.to(device) for key, value in text_inputs.items()}
    with torch.inference_mode():
        text_features = normalize_rows(model.get_text_features(**text_inputs).float().cpu().numpy())
    text_by_description = dict(zip(descriptions, text_features))

    records: list[dict[str, Any]] = []
    for start in range(0, len(pairs), row_batch_size):
        batch = pairs.iloc[start : start + row_batch_size]
        arrays: list[np.ndarray] = []
        metadata: list[tuple[pd.Series, int, int]] = []
        for _, row in batch.iterrows():
            sidecar = _resolve_sidecar(str(row["sidecar_path"]), project_root)
            with np.load(sidecar, allow_pickle=False) as data:
                selected = int(np.asarray(data["selected_max_value_idx"]).item())
                row_arrays = [
                    data["current_agentview"],
                    *data["candidate_predicted_future_images"],
                    data["current_wrist"],
                    *data["candidate_predicted_future_wrists"],
                ]
            offset = len(arrays)
            arrays.extend(row_arrays)
            metadata.append((row, selected, offset))
        encoded = _encode_images(model, processor, arrays, device)
        for row, selected, offset in metadata:
            agent_current = encoded[offset]
            agent_future = encoded[offset + 1 : offset + 5]
            wrist_current = encoded[offset + 5]
            wrist_future = encoded[offset + 6 : offset + 10]
            record = {
                "row_id": int(row["row_id"]),
                **semantic_record(
                    agent_current,
                    agent_future,
                    wrist_current,
                    wrist_future,
                    text_by_description[str(row["task_description"])],
                    selected,
                ),
            }
            records.append(record)
        print(f"[semantic-vof] encoded {min(start + len(batch), len(pairs))}/{len(pairs)}")
    return pd.DataFrame(records)


def _prepare_matrix(train: pd.DataFrame, test: pd.DataFrame, features: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x_train = train[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    x_test = test[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    median = np.nanmedian(x_train, axis=0)
    median = np.where(np.isfinite(median), median, 0.0)
    x_train = np.where(np.isfinite(x_train), x_train, median)
    x_test = np.where(np.isfinite(x_test), x_test, median)
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std = np.where(std > 1e-12, std, 1.0)
    return (x_train - mean) / std, (x_test - mean) / std


def _ridge_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(x_train)), x_train])
    test_design = np.column_stack([np.ones(len(x_test)), x_test])
    penalty = np.eye(design.shape[1]) * RIDGE_ALPHA
    penalty[0, 0] = 0.0
    weights = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y_train
    return test_design @ weights


def grouped_oof(frame: pd.DataFrame, features: list[str], group_column: str) -> np.ndarray:
    predictions = np.full(len(frame), np.nan, dtype=np.float64)
    for group in frame[group_column].unique():
        test_mask = frame[group_column].eq(group).to_numpy()
        train = frame.loc[~test_mask]
        test = frame.loc[test_mask]
        x_train, x_test = _prepare_matrix(train, test, features)
        y_train = train["dense_vof_v2"].to_numpy(float)
        predictions[test_mask] = _ridge_predict(x_train, y_train, x_test)
    if not np.isfinite(predictions).all():
        raise ValueError("OOF predictions contain non-finite values")
    return predictions


def binary_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=bool)
    positives = int(y_true.sum())
    negatives = int((~y_true).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = rankdata(score, method="average")
    return float(
        (ranks[y_true].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def prediction_metrics(y: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    positive = y > 0
    predicted_positive = prediction > 0
    tpr = float(predicted_positive[positive].mean()) if positive.any() else float("nan")
    tnr = float((~predicted_positive[~positive]).mean()) if (~positive).any() else float("nan")
    correlation = spearmanr(y, prediction).statistic
    return {
        "spearman": float(correlation),
        "sign_auc": binary_auc(positive, prediction),
        "balanced_accuracy": float((tpr + tnr) / 2),
        "rmse": float(np.sqrt(np.mean(np.square(prediction - y)))),
    }


def uplift_at_budget(y: np.ndarray, prediction: np.ndarray, budget: float) -> dict[str, float]:
    count = max(1, int(math.ceil(len(y) * budget)))
    selected = np.argsort(prediction)[-count:]
    oracle = np.argsort(y)[-count:]
    uplift = float(y[selected].sum() / len(y))
    return {
        "budget": float(budget),
        "selected_count": int(count),
        "uplift_per_state": uplift,
        "mean_selected_vof": float(y[selected].mean()),
        "compute_adjusted_uplift": float(uplift - QUERY_COST * count / len(y)),
        "oracle_uplift_per_state": float(y[oracle].sum() / len(y)),
        "random_expected_uplift": float(count / len(y) * y.mean()),
    }


def evaluate(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    families = {
        "scalar": SCALAR_FEATURES,
        "semantic": SEMANTIC_FEATURES,
        "combined": SCALAR_FEATURES + SEMANTIC_FEATURES,
    }
    y = frame["dense_vof_v2"].to_numpy(float)
    prediction_columns = {}
    model_rows = []
    uplift_rows = []
    factor_rows = []
    for family, features in families.items():
        group_prediction = grouped_oof(frame, features, "group_key")
        factor_prediction = grouped_oof(frame, features, "factor")
        prediction_columns[f"{family}_group_oof"] = group_prediction
        prediction_columns[f"{family}_factor_oof"] = factor_prediction
        for protocol, prediction in (
            ("group_oof", group_prediction),
            ("factor_oof", factor_prediction),
        ):
            model_rows.append({"family": family, "protocol": protocol, **prediction_metrics(y, prediction)})
        for budget in BUDGETS:
            uplift_rows.append({"family": family, **uplift_at_budget(y, group_prediction, budget)})
        for factor, indices in frame.groupby("factor").groups.items():
            index = np.asarray(list(indices), dtype=int)
            for protocol, prediction in (
                ("group_oof", group_prediction),
                ("factor_oof", factor_prediction),
            ):
                factor_rows.append(
                    {
                        "family": family,
                        "protocol": protocol,
                        "factor": factor,
                        "states": int(len(index)),
                        **prediction_metrics(y[index], prediction[index]),
                        **{
                            f"uplift20_{key}": value
                            for key, value in uplift_at_budget(y[index], prediction[index], 0.20).items()
                            if key in {"uplift_per_state", "compute_adjusted_uplift"}
                        },
                    }
                )
    predictions = frame[["row_id", "factor", "suite", "task_id", "init_state_id", "query_idx", "dense_vof_v2", "group_key"]].copy()
    for column, values in prediction_columns.items():
        predictions[column] = values
    models = pd.DataFrame(model_rows)
    uplifts = pd.DataFrame(uplift_rows)
    factors = pd.DataFrame(factor_rows)

    group_models = models.loc[models["protocol"].eq("group_oof")].set_index("family")
    uplift20 = uplifts.loc[np.isclose(uplifts["budget"], 0.20)].set_index("family")
    combined_factor_group = factors.loc[
        factors["family"].eq("combined") & factors["protocol"].eq("group_oof")
    ]
    combined_factor_heldout = factors.loc[
        factors["family"].eq("combined") & factors["protocol"].eq("factor_oof")
    ]
    forbidden = [
        feature
        for feature in SCALAR_FEATURES + SEMANTIC_FEATURES
        if any(token in feature.lower() for token in PRIVILEGED_TOKENS)
    ]
    checks = {
        "combined_group_spearman_at_least_0p20": float(group_models.loc["combined", "spearman"]) >= 0.20,
        "combined_group_spearman_above_scalar": float(group_models.loc["combined", "spearman"])
        > float(group_models.loc["scalar", "spearman"]),
        "combined_uplift20_positive": float(uplift20.loc["combined", "uplift_per_state"]) > 0.0,
        "combined_uplift20_above_scalar": float(uplift20.loc["combined", "uplift_per_state"])
        > float(uplift20.loc["scalar", "uplift_per_state"]),
        "combined_uplift20_nonnegative_each_factor": bool(
            combined_factor_group["uplift20_uplift_per_state"].ge(0).all()
        ),
        "combined_factor_oof_spearman_nonnegative_each_factor": bool(
            combined_factor_heldout["spearman"].ge(0).all()
        ),
        "all_265_states": len(frame) == EXPECTED_ROWS,
        "no_privileged_features": not forbidden,
    }
    gate = {"checks": checks, "forbidden_features": forbidden, "gate_passed": bool(all(checks.values()))}
    return predictions, models, uplifts, factors, gate


def write_outputs(
    output_dir: Path,
    features: pd.DataFrame,
    predictions: pd.DataFrame,
    models: pd.DataFrame,
    uplifts: pd.DataFrame,
    factors: pd.DataFrame,
    gate: dict[str, object],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_dir / "semantic_features.parquet", index=False)
    predictions.to_csv(output_dir / "oof_predictions.csv", index=False)
    models.to_csv(output_dir / "model_summary.csv", index=False)
    uplifts.to_csv(output_dir / "uplift_summary.csv", index=False)
    factors.to_csv(output_dir / "factor_summary.csv", index=False)

    group_models = models.loc[models["protocol"].eq("group_oof")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(group_models["family"], group_models["spearman"], color=["#4C78A8", "#F28E2B", "#59A14F"])
    axes[0].axhline(0.0, color="black", linewidth=0.8)
    axes[0].set_title("Grouped OOF dense-VoF prediction")
    axes[0].set_ylabel("Spearman correlation")
    for family, group in uplifts.groupby("family"):
        axes[1].plot(group["budget"], group["uplift_per_state"], marker="o", label=family)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_title("Causal uplift from predicted routing")
    axes[1].set_xlabel("Re-query budget")
    axes[1].set_ylabel("Dense VoF uplift per state")
    axes[1].legend()
    fig.tight_layout()
    plot_path = output_dir / "semantic_vof_screen.png"
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)

    lines = [
        "# Semantic predicted-consequence screen: results",
        "",
        f"- States: **{len(features)}**.",
        f"- Frozen encoder: `{MODEL_NAME}`.",
        f"- Development gate: **{'PASS' if gate['gate_passed'] else 'FAIL'}**.",
        "",
        "## Model metrics",
        "",
        models.to_markdown(index=False),
        "",
        "## Uplift at budget",
        "",
        uplifts.to_markdown(index=False),
        "",
        "## Per-factor transfer",
        "",
        factors.to_markdown(index=False),
        "",
        "## Gate",
        "",
    ]
    lines.extend(f"- `{name}`: {'PASS' if passed else 'FAIL'}" for name, passed in gate["checks"].items())
    report_path = output_dir / "RESULTS.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "states": int(len(features)),
        "model": MODEL_NAME,
        "ridge_alpha": RIDGE_ALPHA,
        "gate": gate,
        "model_summary": models.to_dict(orient="records"),
        "uplift_summary": uplifts.to_dict(orient="records"),
        "factor_summary": factors.to_dict(orient="records"),
        "report": str(report_path),
        "plot": str(plot_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, default=_json_default), encoding="utf-8"
    )
    return summary


def run(args: argparse.Namespace) -> dict[str, object]:
    pairs = pd.read_parquet(args.pairs_parquet).reset_index(drop=True)
    required = set(SCALAR_FEATURES) | {
        "factor",
        "suite",
        "task_id",
        "init_state_id",
        "query_idx",
        "task_description",
        "sidecar_path",
        "dense_vof_v2",
    }
    missing = sorted(required - set(pairs.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    pairs["row_id"] = np.arange(len(pairs), dtype=int)
    pairs["group_key"] = (
        pairs["factor"].astype(str)
        + "|"
        + pairs["suite"].astype(str)
        + "|task"
        + pairs["task_id"].astype(int).astype(str)
        + "|init"
        + pairs["init_state_id"].astype(int).astype(str)
    )
    feature_path = args.output_dir / "semantic_features.parquet"
    if args.reuse_features and feature_path.exists():
        semantic = pd.read_parquet(feature_path)
    else:
        semantic = extract_features(
            pairs,
            project_root=args.project_root,
            model_name=args.model,
            device=args.device,
            row_batch_size=args.row_batch_size,
        )
    frame = pairs.merge(semantic, on="row_id", validate="one_to_one")
    predictions, models, uplifts, factors, gate = evaluate(frame)
    return write_outputs(args.output_dir, semantic, predictions, models, uplifts, factors, gate)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    default_pairs = project_root / "experiments/campaigns/counterfactual_feedback_dense_relabel_20260827/analysis/counterfactual_feedback/strict_feedback_pairs_all.parquet"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs-parquet", type=Path, default=default_pairs)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--row-batch-size", type=int, default=8)
    parser.add_argument("--reuse-features", action="store_true")
    args = parser.parse_args()
    summary = run(args)
    print(json.dumps(summary["gate"], indent=2, default=_json_default))
    print(f"Results: {summary['report']}")


if __name__ == "__main__":
    main()

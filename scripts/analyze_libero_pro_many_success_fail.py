#!/usr/bin/env python3
"""Build compact success/fail diagnostics for a LIBERO-PRO uncertainty run."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


UNCERTAINTY_METRICS = [
    "action_std_mean",
    "action_first_step_l2_std",
    "action_pairwise_l2_mean",
    "value_std",
    "value_range",
    "future_proprio_std_mean",
    "future_image_pixel_std_mean",
    "future_wrist_pixel_std_mean",
    "latent_action_copy_std_mean_mean_over_samples",
    "latent_action_first_step_copy_l2_std_mean_over_samples",
    "latent_future_proprio_copy_std_mean_mean_over_samples",
    "latent_value_element_std_mean_mean_over_samples",
]

PREDICTION_ERROR_METRICS = [
    "prediction_error_future_image_mse",
    "prediction_error_future_wrist_mse",
    "prediction_error_future_proprio_l2",
    "prediction_error_value_abs_chunk_success",
]


def _str_to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _project_relative(path: object, project_root: Path) -> str:
    if pd.isna(path) or not str(path):
        return ""
    p = Path(str(path))
    path_text = str(path)
    if not p.is_absolute():
        if path_text.startswith("../experiments/"):
            p = (project_root / path_text.removeprefix("../")).resolve()
        else:
            p = (project_root / p).resolve()
    try:
        return str(p.relative_to(project_root.resolve()))
    except ValueError:
        return str(p)


def _episode_table(df: pd.DataFrame, project_root: Path) -> pd.DataFrame:
    episode_cols = ["suite", "task_id", "init_state_id", "pair_id", "rollout_id", "rollout_seed"]
    if "video_path" not in df.columns:
        df = df.copy()
        df["video_path"] = ""
    agg = {
        "success": "first",
        "final_t": "first",
        "query_idx": "count",
        "video_path": "first",
        "task_description": "first",
    }
    episodes = df.groupby(episode_cols, dropna=False).agg(agg).reset_index()
    episodes = episodes.rename(columns={"query_idx": "queries"})
    episodes["success"] = episodes["success"].map(_str_to_bool)
    episodes["video_path_fixed"] = episodes["video_path"].map(lambda p: _project_relative(p, project_root))
    return episodes.sort_values(["success", "rollout_id"]).reset_index(drop=True)


def _metric_columns(df: pd.DataFrame, names: list[str]) -> list[str]:
    return [name for name in names if name in df.columns]


def _plot_metric_grid(
    df: pd.DataFrame,
    metrics: list[str],
    output_path: Path,
    title: str,
    ylabels: dict[str, str] | None = None,
) -> None:
    if not metrics:
        return
    ylabels = ylabels or {}
    ncols = 2
    nrows = int(np.ceil(len(metrics) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.2 * nrows), squeeze=False)
    x_col = "query_idx"

    for ax, metric in zip(axes.ravel(), metrics):
        for success, color, label in [(False, "#c23b22", "fail"), (True, "#2374ab", "success")]:
            sub = df[df["success"].map(_str_to_bool) == success]
            if sub.empty:
                continue
            for _, episode in sub.groupby(["rollout_id", "rollout_seed"], dropna=False):
                ax.plot(episode[x_col], episode[metric], color=color, alpha=0.18, linewidth=1)
            stats = sub.groupby(x_col)[metric].agg(["mean", "std", "count"]).reset_index()
            ax.plot(stats[x_col], stats["mean"], color=color, linewidth=2.5, label=f"{label} mean")
            valid_std = stats["std"].fillna(0.0)
            ax.fill_between(
                stats[x_col],
                stats["mean"] - valid_std,
                stats["mean"] + valid_std,
                color=color,
                alpha=0.12,
                linewidth=0,
            )
        ax.set_title(metric, fontsize=10)
        ax.set_xlabel("query_idx")
        ax.set_ylabel(ylabels.get(metric, metric))
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)

    for ax in axes.ravel()[len(metrics) :]:
        ax.axis("off")
    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _plot_episode_boxplots(df: pd.DataFrame, metrics: list[str], output_path: Path) -> pd.DataFrame:
    records = []
    episode_keys = ["suite", "task_id", "init_state_id", "pair_id", "rollout_id", "rollout_seed", "success", "final_t"]
    for episode_key, episode in df.groupby(episode_keys, dropna=False):
        record = dict(zip(episode_keys, episode_key))
        for metric in metrics:
            values = episode[metric].dropna()
            if len(values):
                record[f"{metric}__mean"] = float(values.mean())
                record[f"{metric}__max"] = float(values.max())
                record[f"{metric}__last"] = float(values.iloc[-1])
        records.append(record)
    features = pd.DataFrame(records)

    plot_metrics = [f"{m}__mean" for m in metrics[:8] if f"{m}__mean" in features.columns]
    if plot_metrics:
        ncols = 2
        nrows = int(np.ceil(len(plot_metrics) / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(12, 3.2 * nrows), squeeze=False)
        for ax, metric in zip(axes.ravel(), plot_metrics):
            fail = features[~features["success"].map(_str_to_bool)][metric].dropna()
            success = features[features["success"].map(_str_to_bool)][metric].dropna()
            ax.boxplot([fail, success], tick_labels=["fail", "success"], showmeans=True)
            ax.scatter(np.full(len(fail), 1), fail, color="#c23b22", alpha=0.55, s=18)
            ax.scatter(np.full(len(success), 2), success, color="#2374ab", alpha=0.55, s=18)
            ax.set_title(metric, fontsize=10)
            ax.grid(axis="y", alpha=0.25)
        for ax in axes.ravel()[len(plot_metrics) :]:
            ax.axis("off")
        fig.suptitle("Episode-level metric separation before the common success horizon", fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
    return features


def _read_frame(video_path: Path, frame_idx: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        cap.release()
        return None
    frame_idx = max(0, min(frame_idx, total - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _plot_storyboard(episodes: pd.DataFrame, project_root: Path, output_path: Path, horizon: int) -> None:
    success_rows = episodes[episodes["success"].map(_str_to_bool)].sort_values(["final_t", "rollout_id"])
    fail_rows = episodes[~episodes["success"].map(_str_to_bool)].sort_values(["rollout_id"])
    if success_rows.empty or fail_rows.empty:
        return
    chosen = [("success", success_rows.iloc[0]), ("fail", fail_rows.iloc[0])]
    frame_indices = sorted(set([0, 16, 32, 48, 64, 80, 96, max(0, horizon - 1)]))
    frame_indices = [idx for idx in frame_indices if idx < horizon]

    fig, axes = plt.subplots(len(chosen), len(frame_indices), figsize=(2.4 * len(frame_indices), 5.0))
    if len(frame_indices) == 1:
        axes = np.array([[axes[0]], [axes[1]]])

    for row_idx, (label, row) in enumerate(chosen):
        video_path = project_root / row["video_path_fixed"]
        for col_idx, frame_idx in enumerate(frame_indices):
            ax = axes[row_idx, col_idx]
            frame = _read_frame(video_path, frame_idx)
            if frame is None:
                ax.text(0.5, 0.5, "missing frame", ha="center", va="center")
            else:
                ax.imshow(frame)
            ax.axis("off")
            ax.set_title(f"t={frame_idx}", fontsize=9)
            if col_idx == 0:
                ax.set_ylabel(
                    f"{label}\nseed={int(row['rollout_seed'])}\nfinal_t={int(row['final_t'])}",
                    fontsize=10,
                )
    fig.suptitle("Representative success/fail frames before the common success horizon", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _write_gallery(episodes: pd.DataFrame, output_path: Path) -> None:
    cards = []
    for _, row in episodes.sort_values(["success", "rollout_id"]).iterrows():
        label = "success" if _str_to_bool(row["success"]) else "fail"
        src = html.escape(row["video_path_fixed"])
        title = html.escape(
            f"{label}: rollout={int(row['rollout_id'])}, seed={int(row['rollout_seed'])}, "
            f"t={int(row['final_t'])}, queries={int(row['queries'])}"
        )
        cards.append(
            f"""
            <section class="video-card">
              <h4>{title}</h4>
              <video src="{src}" controls muted preload="metadata"></video>
            </section>
            """
        )
    output_path.write_text(
        """
        <style>
          .video-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
          .video-card { border: 1px solid #ddd; padding: 10px; border-radius: 6px; background: #fff; }
          .video-card h4 { margin: 0 0 8px 0; font-size: 14px; }
          .video-card video { width: 100%; max-height: 320px; background: #111; }
        </style>
        <div class="video-grid">
        """
        + "\n".join(cards)
        + "\n</div>\n",
        encoding="utf-8",
    )


def _write_notebook_cell_snippet(run_name: str, comparison_dir: Path, output_path: Path) -> None:
    snippet = f"""from pathlib import Path
import pandas as pd
from IPython.display import Image, HTML, display, Markdown

run_name = {run_name!r}
comparison_dir = PROJECT_ROOT / {str(comparison_dir.relative_to(Path.cwd()))!r}

display(Markdown('### Episode outcomes'))
episode_outcomes = pd.read_csv(comparison_dir / 'episode_outcomes.csv')
display(episode_outcomes[['suite', 'task_id', 'init_state_id', 'rollout_id', 'rollout_seed', 'success', 'final_t', 'queries', 'video_path_fixed']])

display(Markdown('### Query-level uncertainty metrics'))
display(Image(filename=str(comparison_dir / 'uncertainty_query_timeseries.png')))

display(Markdown('### Prediction error after executing each chunk'))
display(Image(filename=str(comparison_dir / 'prediction_error_query_timeseries.png')))

display(Markdown('### Episode-level metric separation'))
display(Image(filename=str(comparison_dir / 'episode_metric_boxplots.png')))

display(Markdown('### Success/fail storyboard at the same executed-frame indices'))
display(Image(filename=str(comparison_dir / 'success_fail_storyboard.png')))

display(Markdown('### All rollout videos'))
display(HTML((comparison_dir / 'video_gallery.html').read_text(encoding='utf-8')))
"""
    output_path.write_text(snippet, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-subdir", default="group_mean_task5_init0_many")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    base = project_root / "experiments" / "uncertainty"
    trace_path = base / f"{args.run_name}__query_traces.csv"
    df = pd.read_csv(trace_path)
    df["success"] = df["success"].map(_str_to_bool)

    episodes = _episode_table(df, project_root)
    success_final_t = int(episodes[episodes["success"]]["final_t"].min())
    truncated = df[df["t"] < success_final_t].copy()

    comparison_dir = base / f"{args.run_name}__analysis" / args.output_subdir
    comparison_dir.mkdir(parents=True, exist_ok=True)

    uncertainty_metrics = _metric_columns(truncated, UNCERTAINTY_METRICS)
    prediction_metrics = _metric_columns(truncated, PREDICTION_ERROR_METRICS)

    episodes.to_csv(comparison_dir / "episode_outcomes.csv", index=False)
    truncated.to_csv(comparison_dir / "selected_query_metrics_truncated_to_success.csv", index=False)
    truncated.groupby(["success", "query_idx"])[uncertainty_metrics].agg(["mean", "std", "count"]).to_csv(
        comparison_dir / "mean_uncertainty_by_query_truncated_to_success.csv"
    )
    truncated.groupby(["success", "query_idx"])[prediction_metrics].agg(["mean", "std", "count"]).to_csv(
        comparison_dir / "mean_prediction_error_by_query_truncated_to_success.csv"
    )

    _plot_metric_grid(
        truncated,
        uncertainty_metrics,
        comparison_dir / "uncertainty_query_timeseries.png",
        f"Uncertainty metrics by query, truncated to t < {success_final_t}",
    )
    _plot_metric_grid(
        truncated,
        prediction_metrics,
        comparison_dir / "prediction_error_query_timeseries.png",
        f"Prediction error after chunk execution, truncated to t < {success_final_t}",
    )
    features = _plot_episode_boxplots(
        truncated,
        uncertainty_metrics + prediction_metrics,
        comparison_dir / "episode_metric_boxplots.png",
    )
    features.to_csv(comparison_dir / "episode_metric_features_truncated_to_success.csv", index=False)
    _plot_storyboard(episodes, project_root, comparison_dir / "success_fail_storyboard.png", success_final_t)
    _write_gallery(episodes, comparison_dir / "video_gallery.html")
    _write_notebook_cell_snippet(args.run_name, comparison_dir, comparison_dir / "notebook_display_cell.py")

    readme = comparison_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                f"# {args.run_name}",
                "",
                f"Task command: `{episodes['task_description'].iloc[0]}`",
                f"Suite/task/init: `{episodes['suite'].iloc[0]}` / `{int(episodes['task_id'].iloc[0])}` / `{int(episodes['init_state_id'].iloc[0])}`",
                f"Rollouts: {len(episodes)}",
                f"Success/fail: {int(episodes['success'].sum())} / {int((~episodes['success']).sum())}",
                f"Common truncation horizon: `t < {success_final_t}`",
                "",
                "Generated files:",
                "- `episode_outcomes.csv`",
                "- `selected_query_metrics_truncated_to_success.csv`",
                "- `mean_uncertainty_by_query_truncated_to_success.csv`",
                "- `mean_prediction_error_by_query_truncated_to_success.csv`",
                "- `episode_metric_features_truncated_to_success.csv`",
                "- `uncertainty_query_timeseries.png`",
                "- `prediction_error_query_timeseries.png`",
                "- `episode_metric_boxplots.png`",
                "- `success_fail_storyboard.png`",
                "- `video_gallery.html`",
                "- `notebook_display_cell.py`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {comparison_dir}")
    print(episodes[["rollout_id", "rollout_seed", "success", "final_t", "queries"]].to_string(index=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the compact, presentation-ready LIBERO results notebook."""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pandas as pd
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
PHASE1_DIR = EXPERIMENTS_DIR / "campaigns" / "phase1_analysis_20260724"
FULL_DIR = (
    EXPERIMENTS_DIR
    / "campaigns"
    / "libero_full_validation_20260724"
    / "analysis"
    / "full_validation"
)
MEDIA_DIR = EXPERIMENTS_DIR / "final_results_media"
OUTPUT_NOTEBOOK = EXPERIMENTS_DIR / "LIBERO_FINAL_RESULTS.ipynb"


STRATEGY_LABELS = {
    "max_value": "max(value)",
    "uncertainty_penalty_action": "action penalty",
    "uncertainty_penalty_action_chunk": "action-chunk penalty",
    "uncertainty_penalty_action_max": "max-action penalty",
    "uncertainty_penalty_value": "value penalty",
    "uncertainty_penalty_combined": "combined penalty",
}

METRIC_LABELS = {
    "action_first_step_l2_std": "action first-step stochastic std",
    "value_std": "value stochastic std",
    "value_range": "value stochastic range",
    "latent_action_copy_std_mean_mean_over_samples": "action latent-copy mean",
    "latent_action_first_step_copy_l2_std_mean_over_samples": (
        "action first-step latent-copy L2"
    ),
    "value_mean": "mean predicted value",
}


def _load_data() -> dict[str, object]:
    return {
        "phase1": json.loads(
            (PHASE1_DIR / "summary.json").read_text(encoding="utf-8")
        ),
        "full": json.loads((FULL_DIR / "summary.json").read_text(encoding="utf-8")),
        "cases": pd.read_csv(FULL_DIR / "case_outcome_summary.csv"),
        "planning": pd.read_csv(FULL_DIR / "planning_strategy_summary.csv"),
        "pooled": pd.read_csv(FULL_DIR / "pooled_planning_confirmatory.csv"),
        "detector": pd.read_csv(FULL_DIR / "prespecified_detector_exact_query.csv"),
        "prediction_error": pd.read_csv(
            FULL_DIR / "prediction_error_correlations_q0_5.csv"
        ),
        "media": pd.read_csv(MEDIA_DIR / "manifest.csv"),
    }


def _percent(value: float) -> str:
    return f"{value:.1%}"


def _status_table(data: dict[str, object]) -> str:
    phase1 = data["phase1"]
    full = data["full"]
    id_counts = phase1["split_counts"]["ID"]
    ood_counts = phase1["split_counts"]["OOD"]
    rows = pd.DataFrame(
        [
            {
                "Benchmark": "Standard LIBERO ID",
                "Role": "pipeline control",
                "Executions": id_counts["episodes"],
                "Success / fail": f'{id_counts["success"]} / {id_counts["fail"]}',
                "Status": "completed",
            },
            {
                "Benchmark": "LIBERO-PRO OOD",
                "Role": "boundary screening",
                "Executions": ood_counts["episodes"],
                "Success / fail": (
                    f'{ood_counts["success"]} / {ood_counts["fail"]}'
                ),
                "Status": "completed",
            },
            {
                "Benchmark": "LIBERO-PRO OOD",
                "Role": "detector + planning validation",
                "Executions": full["episodes"],
                "Success / fail": f'{full["successes"]} / {full["failures"]}',
                "Status": "23/23 jobs completed",
            },
            {
                "Benchmark": "LIBERO-Safety",
                "Role": "official safety constraints",
                "Executions": 0,
                "Success / fail": "-",
                "Status": "environment ready; not run",
            },
        ]
    )
    return rows.to_markdown(index=False)


def _case_table(data: dict[str, object]) -> str:
    cases = data["cases"].copy()
    cases["success_rate"] = cases["success_rate"].map(_percent)
    cases = cases.rename(
        columns={
            "case_id": "Case",
            "experiment_split": "Split",
            "rollout_executions": "Executions",
            "successes": "Success",
            "failures": "Fail",
            "success_rate": "Success rate",
        }
    )
    return cases[
        ["Case", "Split", "Executions", "Success", "Fail", "Success rate"]
    ].to_markdown(index=False)


def _detector_table(data: dict[str, object]) -> str:
    detector = data["detector"]
    requested = [
        (3, "action_first_step_l2_std"),
        (3, "value_std"),
        (3, "value_range"),
        (8, "latent_action_copy_std_mean_mean_over_samples"),
        (8, "value_mean"),
        (9, "latent_action_first_step_copy_l2_std_mean_over_samples"),
        (9, "latent_action_copy_std_mean_mean_over_samples"),
    ]
    rows = []
    for query_idx, metric in requested:
        match = detector[
            detector["query_idx"].eq(query_idx) & detector["metric"].eq(metric)
        ]
        if len(match) != 1:
            raise RuntimeError(
                f"Expected one detector row for query={query_idx}, metric={metric}"
            )
        row = match.iloc[0]
        rows.append(
            {
                "Query / t": f'{query_idx} / {int(row["query_t"])}',
                "Metric": METRIC_LABELS[metric],
                "Calibration AUROC": f'{row["calibration_auc"]:.3f}',
                "Holdout AUROC": f'{row["holdout_auc"]:.3f}',
                "Holdout AUPRC": f'{row["holdout_auprc"]:.3f}',
                "TPR / FPR": f'{row["tpr"]:.2f} / {row["fpr"]:.3f}',
                "Alive holdout F/S": (
                    f'{int(row["holdout_fail_alive"])} / '
                    f'{int(row["holdout_episodes_alive"] - row["holdout_fail_alive"])}'
                ),
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False)


def _pooled_table(data: dict[str, object]) -> str:
    pooled = data["pooled"].loc[data["pooled"]["cases"].eq(3)].copy()
    pooled["Strategy"] = pooled["planning_strategy"].map(STRATEGY_LABELS)
    pooled["Lambda"] = pooled["planning_risk_lambda"].map(lambda value: f"{value:g}")
    pooled["Baseline"] = pooled.apply(
        lambda row: f'{int(row["baseline_successes"])}/{int(row["paired_rollouts"])}',
        axis=1,
    )
    pooled["Strategy result"] = pooled.apply(
        lambda row: f'{int(row["strategy_successes"])}/{int(row["paired_rollouts"])}',
        axis=1,
    )
    pooled["Delta"] = pooled["delta_success_rate"].map(
        lambda value: f"{100 * value:+.0f} pp"
    )
    pooled["W/L/T"] = pooled.apply(
        lambda row: f'{int(row["wins"])}/{int(row["losses"])}/{int(row["ties"])}',
        axis=1,
    )
    pooled["Exact p"] = pooled["mcnemar_exact_p"].map(lambda value: f"{value:.3f}")
    return pooled[
        [
            "Strategy",
            "Lambda",
            "Baseline",
            "Strategy result",
            "Delta",
            "W/L/T",
            "Exact p",
        ]
    ].to_markdown(index=False)


def _planning_row(
    planning: pd.DataFrame,
    case_id: str,
    strategy: str,
    risk_lambda: float,
) -> pd.Series:
    match = planning[
        planning["case_id"].eq(case_id)
        & planning["planning_strategy"].eq(strategy)
        & planning["planning_risk_lambda"].sub(risk_lambda).abs().lt(1e-9)
        & planning["prediction_mode"].eq("parallel")
        & planning["num_samples"].eq(4)
        & planning["num_open_loop_steps"].eq(16)
        & planning["num_denoising_steps_action"].eq(5)
        & planning["planning_action_weight"].eq(0.5)
    ]
    if len(match) != 1:
        raise RuntimeError(
            f"Expected one planning row for {case_id}, {strategy}, {risk_lambda}"
        )
    return match.iloc[0]


def _generalization_table(data: dict[str, object]) -> str:
    planning = data["planning"]
    specs = [
        ("yellow_task8_init0", "max_value", 0.0),
        ("yellow_task8_init0", "uncertainty_penalty_combined", 1.0),
        ("long_mug_task4_init0", "max_value", 0.0),
        ("long_mug_task4_init0", "uncertainty_penalty_action", 0.5),
        ("long_mug_task4_init0", "uncertainty_penalty_value", 2.0),
    ]
    rows = []
    baseline_rates: dict[str, float] = {}
    selected = []
    for case_id, strategy, risk_lambda in specs:
        row = _planning_row(planning, case_id, strategy, risk_lambda)
        selected.append((case_id, strategy, risk_lambda, row))
        if strategy == "max_value":
            baseline_rates[case_id] = row["success_rate"]
    for case_id, strategy, risk_lambda, row in selected:
        rows.append(
            {
                "Case": case_id,
                "Strategy": STRATEGY_LABELS[strategy],
                "Lambda": f"{risk_lambda:g}",
                "Success": f'{int(row["successes"])}/{int(row["episodes"])}',
                "Rate": _percent(row["success_rate"]),
                "Delta vs max(value)": (
                    f'{100 * (row["success_rate"] - baseline_rates[case_id]):+.1f} pp'
                ),
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False)


def _prediction_error_table(data: dict[str, object]) -> str:
    errors = data["prediction_error"]
    requested = [
        (
            "latent_action_copy_std_mean_mean_over_samples",
            "prediction_error_future_wrist_mse",
        ),
        ("value_range", "prediction_error_future_wrist_mse"),
        (
            "latent_action_copy_std_mean_mean_over_samples",
            "prediction_error_future_proprio_l2",
        ),
        (
            "latent_action_copy_std_mean_mean_over_samples",
            "prediction_error_value_abs_chunk_success",
        ),
        ("action_first_step_l2_std", "prediction_error_future_image_mse"),
    ]
    rows = []
    for metric, error in requested:
        match = errors[
            errors["metric"].eq(metric) & errors["prediction_error"].eq(error)
        ]
        if len(match) != 1:
            raise RuntimeError(
                f"Expected one prediction-error row for {metric}, {error}"
            )
        row = match.iloc[0]
        rows.append(
            {
                "Uncertainty": METRIC_LABELS.get(metric, metric),
                "Subsequent error": error.replace("prediction_error_", ""),
                "Rows": int(row["rows"]),
                "Query-controlled rank correlation": (
                    f'{row["query_controlled_rank_correlation"]:+.3f}'
                ),
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False)


def _video_gallery(data: dict[str, object]) -> str:
    media = data["media"].copy()
    strategy_order = [
        "max(value)",
        "action penalty",
        "value penalty",
        "combined penalty",
    ]
    cards = []
    for seed in sorted(media["rollout_seed"].unique()):
        subset = media.loc[media["rollout_seed"].eq(seed)].set_index("strategy_label")
        cells = []
        for strategy in strategy_order:
            row = subset.loc[strategy]
            outcome = "SUCCESS" if bool(row["success"]) else "FAIL"
            color = "#157347" if bool(row["success"]) else "#b02a37"
            src = f'final_results_media/{row["filename"]}'
            cells.append(
                '<td style="vertical-align:top;padding:8px;width:25%">'
                f"<b>{strategy}</b><br>"
                f'<span style="color:{color};font-weight:700">{outcome}</span>'
                f" · t={int(row['final_t'])}<br>"
                f'<video controls preload="metadata" width="250" src="{src}"></video>'
                f'<br><a href="{src}">Open MP4</a>'
                "</td>"
            )
        cards.append(
            f"<h4>rollout_seed={seed}</h4>"
            '<table style="width:100%"><tr>'
            + "".join(cells)
            + "</tr></table>"
        )
    return "\n".join(cards)


def _validate_media(data: dict[str, object]) -> None:
    media = data["media"]
    missing = [
        str(MEDIA_DIR / filename)
        for filename in media["filename"]
        if not (MEDIA_DIR / filename).is_file()
    ]
    if missing:
        raise FileNotFoundError("Missing final-results videos:\n" + "\n".join(missing))
    if len(media) != 12:
        raise RuntimeError(f"Expected 12 curated videos, found {len(media)}")


def build_notebook(data: dict[str, object]) -> nbformat.NotebookNode:
    _validate_media(data)
    status_table = _status_table(data)
    case_table = _case_table(data)
    detector_table = _detector_table(data)
    pooled_table = _pooled_table(data)
    generalization_table = _generalization_table(data)
    prediction_error_table = _prediction_error_table(data)
    video_gallery = _video_gallery(data)

    cells = [
        new_markdown_cell(
            """# Cosmos Policy: uncertainty-aware planning in LIBERO

**Final experimental snapshot · 24 July 2026**

This notebook is the compact entry point for the completed standard LIBERO and
LIBERO-PRO experiments. It combines the confirmatory tables, plots,
interpretation and portable matched-seed videos. The authoritative detailed
report is [LIBERO_COMPLETE_RESULTS_20260724.md](LIBERO_COMPLETE_RESULTS_20260724.md).

Three evidence levels are kept separate:

1. **Confirmatory:** frozen calibration/holdout and pooled paired comparisons.
2. **Exploratory:** temporal detector search and small ablations.
3. **Visual case studies:** selected matched-seed pilot videos."""
        ),
        new_markdown_cell(
            f"""## 1. What was actually run

{status_table}

The 1078 rows are **strategy executions**, not 1078 independent scenes:
identical `task/init_state/rollout_seed` combinations were repeated for
different planners. Planning conclusions therefore use paired seeds rather
than the pooled `603/1078` success fraction.

No newer experiment output was present on the MLSpace server at the time this
snapshot was built."""
        ),
        new_code_cell(
            """from pathlib import Path
import json
import pandas as pd
from IPython.display import HTML, Image, Markdown, display

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == "experiments":
    PROJECT_ROOT = PROJECT_ROOT.parent

FULL_DIR = (
    PROJECT_ROOT
    / "experiments/campaigns/libero_full_validation_20260724/analysis/full_validation"
)
summary = json.loads((FULL_DIR / "summary.json").read_text(encoding="utf-8"))
cases = pd.read_csv(FULL_DIR / "case_outcome_summary.csv")
planning = pd.read_csv(FULL_DIR / "planning_strategy_summary.csv")
pooled = pd.read_csv(FULL_DIR / "pooled_planning_confirmatory.csv")
detector = pd.read_csv(FULL_DIR / "prespecified_detector_exact_query.csv")
prediction_error = pd.read_csv(FULL_DIR / "prediction_error_correlations_q0_5.csv")

print(
    f"Loaded {summary['episodes']} strategy executions and "
    f"{summary['query_rows']} policy queries."
)"""
        ),
        new_markdown_cell(
            f"""## 2. Experimental coverage

{case_table}

Standard LIBERO produced 72/72 successes and is useful as an integration
control, but it is saturated for failure research. Selected LIBERO-PRO
boundary cases created natural success and failure from the same task and
initial state."""
        ),
        new_markdown_cell(
            r"""## 3. Model outputs and uncertainty scores

At query \(q\), the policy receives the real agent-view image, wrist image,
proprioception and language instruction. For stochastic candidate \(n\), the
main parallel mode produces an action chunk, future state and value from the
same diffusion sequence:

\[
\left(A_{q,n},\widehat I_{q+1,n},\widehat p_{q+1,n},V_{q,n}\right),
\qquad A_{q,n}\in\mathbb{R}^{16\times7}.
\]

After the selected chunk is executed, the next query uses a **new real MuJoCo
observation**, not the predicted image or proprioception.

The main candidate-level internal risks are

\[
u^{A,\mathrm{first}}_{q,n}
=\left\|
\operatorname{Std}_{k}
\widetilde A_{q,n,k,0,1:6}
\right\|_2,
\qquad
u^V_{q,n}=\operatorname{Std}_{e}\widetilde V_{q,n,e},
\]

where \(k\) indexes repeated action copies in the latent frame and \(e\)
indexes value-latent elements. Across-candidate stochastic metrics such as
`value_std` and `value_range` are also recorded.

With candidate-wise standardization

\[
z(x_n)=
\frac{x_n-\operatorname{Mean}_m x_m}
{\operatorname{Std}_m x_m+\varepsilon},
\]

the tested combined planner was

\[
n^*=\arg\max_n
\left[
z(V_n)-\lambda
\left(w_A z(u^{A,\mathrm{first}}_n)+(1-w_A)z(u^V_n)\right)
\right].
\]

Prediction errors against reality are available only after executing the
chunk and were not used to choose that same chunk."""
        ),
        new_markdown_cell(
            f"""## 4. Failure detection

The fixed milk case used 36 calibration and 36 holdout trajectories. The
table below reports exact-query comparisons, avoiding trajectory-length
leakage.

{detector_table}

**Early result.** At `query=3` (`t=48`), AUROC values are weak and unstable;
there is no reliable initial-state failure detector.

**Critical-moment result.** At `query=9` (`t=144`), first-action latent-copy
inconsistency reaches holdout AUROC 0.915 and the calibration threshold gives
TPR 0.80 at FPR 0. The earliest observed physical failure occurs at `t=169`,
so the signal leads it by at least 25 simulator steps.

At `query=8`, high mean predicted value itself reaches holdout AUROC 0.923.
This is overconfidence: the model can agree on a high value and still fail."""
        ),
        new_markdown_cell(
            """![Detector holdout AUROC](campaigns/libero_full_validation_20260724/analysis/full_validation/plots/detector_holdout_auc.png)

The automatic sweep searched 205,920 correlated temporal variants. Perfect
rows from that sweep are exploratory and are not treated as confirmatory
evidence; the conclusions above use prespecified metrics at exact queries."""
        ),
        new_markdown_cell(
            f"""## 5. Planning: pooled confirmatory comparison

The aggregate below contains the independent milk holdout, yellow-book and
long-mug cases: 50 paired rollout seeds per formula. Milk calibration is
excluded.

{pooled_table}

No fixed uncertainty penalty beats `max(value)` in the pooled comparison.
The least harmful candidate is first-action penalty with \(\lambda=0.5\):
31/50 versus 33/50 for the baseline. None of the paired tests is significant."""
        ),
        new_markdown_cell(
            """![Planning success rates](campaigns/libero_full_validation_20260724/analysis/full_validation/plots/planning_success_rates.png)"""
        ),
        new_markdown_cell(
            f"""## 6. Promising but underpowered generalization cases

{generalization_table}

Long-mug is the most positive pilot: action penalty \(\lambda=0.5\) and value
penalty \(\lambda=2\) each obtain 11/12 versus 9/12 for `max(value)`.
However, each comparison has only three wins and one loss
(`exact p=0.625`), so this is a replication target, not a demonstrated gain.

The action-denoising ablation is also interesting: with 10 denoising steps,
action penalty obtained 4/6 while the baseline obtained 0/6. The sample is too
small (`p=0.125`) and the baseline block was unusually difficult."""
        ),
        new_markdown_cell(
            f"""## 7. Does uncertainty predict world-model error?

Metrics and errors were rank-normalized within `split/query_idx` for
`query=0..5`.

{prediction_error_table}

All meaningful correlations satisfy \(|\rho|\leq0.191\), and several have the
opposite sign. Current uncertainty scores can rank late failure risk in one
case, but they are not calibrated estimates of image or proprioception error."""
        ),
        new_markdown_cell(
            f"""## 8. Matched-seed video comparison

All twelve videos below use
`libero_spatial_with_milk/task5/init0`. Within each row, environment and
rollout seed are identical; only candidate selection changes.

These are deliberately selected pilot seeds where `max(value)` fails and at
least one alternative succeeds. They illustrate mechanism and trajectory
divergence, but **must not be used to estimate success rates**.

{video_gallery}"""
        ),
        new_code_cell(
            """# Fallback renderer for notebook frontends that hide <video> in Markdown.
import html

media = pd.read_csv(PROJECT_ROOT / "experiments/final_results_media/manifest.csv")
for seed, rows in media.groupby("rollout_seed", sort=True):
    cards = []
    for row in rows.itertuples(index=False):
        src = f"final_results_media/{row.filename}"
        outcome = "SUCCESS" if row.success else "FAIL"
        cards.append(
            '<td style="vertical-align:top;padding:8px">'
            f"<b>{html.escape(row.strategy_label)}</b><br>{outcome}, t={row.final_t}<br>"
            f'<video controls preload="metadata" width="250" src="{src}"></video>'
            f'<br><a href="{src}">Open MP4</a></td>'
        )
    display(Markdown(f"#### rollout_seed={seed}"))
    display(HTML("<table><tr>" + "".join(cards) + "</tr></table>"))"""
        ),
        new_markdown_cell(
            r"""## 9. Conclusions

1. **OOD evaluation is necessary.** Standard LIBERO is saturated, while
   LIBERO-PRO provides natural mixed outcomes under fixed task/init state.
2. **There is no universal early detector yet.** Metrics before `t=80` do not
   transfer reliably from calibration to holdout.
3. **A reproducible critical-moment signal exists on one fixed case.**
   Latent action-copy inconsistency anticipates observed failure and transfers
   to a new seed block.
4. **Value overconfidence is a separate failure mode.** High mean value can be
   more predictive than value dispersion.
5. **Uncertainty is not the same as prediction error.** Image and proprioception
   error correlations remain weak after controlling episode phase.
6. **A static global penalty overfits.** The formula selected on milk
   calibration becomes substantially worse on milk holdout and does not win in
   the pooled 50-rollout aggregate.
7. **Risk handling should be conditional and phase-aware.** Penalizing every
   query with one global \(\lambda\) is too crude.
8. **LIBERO-Safety remains an unexecuted validation axis.** PRO drop and
   wrong-object heuristics do not replace official safety constraints."""
        ),
        new_markdown_cell(
            r"""## 10. Next testable planner

Keep `max(value)` as the default and enable risk-aware behavior only after a
calibrated task/query-specific trigger:

\[
g_q=\mathbb{1}\left[u_q>\tau_{\alpha,\mathrm{task},q}\right],
\]

\[
n_q^*=\arg\max_n
\left[z(V_{q,n})-g_q\lambda_q z(u^{A,\mathrm{first}}_{q,n})\right].
\]

When \(g_q=1\), also increase candidates \(N:4\rightarrow8\), shorten the
executed horizon \(H:16\rightarrow4\) or \(8\), and replan from the next real
observation. Calibration must be frozen on milk and evaluated unchanged on
milk holdout, yellow, long-mug and official LIBERO-Safety suites."""
        ),
        new_markdown_cell(
            """## 11. Reproducibility

- [Complete report](LIBERO_COMPLETE_RESULTS_20260724.md)
- [Frozen 8-hour protocol](LIBERO_8H_VALIDATION_PROTOCOL.md)
- [Machine-readable full-validation tables](campaigns/libero_full_validation_20260724/analysis/full_validation/)
- [Experiment grid](configs/libero_campaign_8h.json)
- [Video manifest](final_results_media/manifest.csv)
- [Paper and benchmark review](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md)

Regenerate this notebook:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python \
  scripts/build_final_results_notebook.py
```"""
        ),
    ]
    for index, cell in enumerate(cells):
        cell["id"] = f"final-results-{index:02d}"

    notebook = new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Cosmos Policy LIBERO (WSL Py3.10)",
                "language": "python",
                "name": "cosmos-policy-libero",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
    )
    nbformat.validate(notebook)
    return notebook


def main() -> None:
    data = _load_data()
    notebook = build_notebook(data)
    nbformat.write(notebook, OUTPUT_NOTEBOOK)
    print(f"Built {OUTPUT_NOTEBOOK.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

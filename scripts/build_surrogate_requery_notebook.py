#!/usr/bin/env python3
"""Build the focused surrogate-requery notebook from completed artifacts."""

from __future__ import annotations

from pathlib import Path

import nbformat
import pandas as pd
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = PROJECT_ROOT / "experiments"
SCREEN = (
    EXPERIMENTS
    / "campaigns/surrogate_screening_20260819/analysis/adaptive_summary"
)
CONFIRM = (
    EXPERIMENTS
    / "campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary"
)
MEDIA = EXPERIMENTS / "final_results_media/surrogate_confirmatory_20260819"
VIDEO_SELECTION = (
    EXPERIMENTS / "configs/libero_campaign_surrogate_video_replays.csv"
)
OUTPUT = EXPERIMENTS / "LIBERO_SURROGATE_REQUERY_RESULTS.ipynb"


def pp(value: float) -> str:
    return f"{100.0 * float(value):+.1f} pp"


def percent(value: float) -> str:
    return f"{100.0 * float(value):.1f}%"


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def screen_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["max(value)"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["strategy"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["delta"] = table["delta_success_rate"].map(pp)
    table["worst case"] = table["min_case_delta"].map(pp)
    table["query cost"] = table["query_overhead_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    table["requery rate"] = table["mean_requery_rate"].map(percent)
    table["surrogate alarm"] = table["mean_surrogate_alarm_rate"].map(percent)
    return table[
        [
            "selection_category",
            "strategy_id",
            "max(value)",
            "strategy",
            "delta",
            "worst case",
            "query cost",
            "requery rate",
            "surrogate alarm",
            "selection_utility",
        ]
    ].rename(
        columns={
            "selection_category": "Category",
            "strategy_id": "Selected strategy",
            "selection_utility": "Utility J",
        }
    ).to_markdown(index=False)


def confirm_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["max(value)"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["strategy"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["delta"] = table["delta_success_rate"].map(pp)
    table["95% CI"] = table.apply(
        lambda row: f"[{pp(row.delta_ci_low)}; {pp(row.delta_ci_high)}]", axis=1
    )
    table["W/L/T"] = table.apply(
        lambda row: f"{int(row.wins)}/{int(row.losses)}/{int(row.ties)}", axis=1
    )
    table["Holm p"] = table["mcnemar_holm_p"].map(
        lambda value: f"{float(value):.4g}"
    )
    table["query cost"] = table["query_overhead_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    table["requery rate"] = table["mean_requery_rate"].map(percent)
    table["surrogate alarm"] = table["mean_surrogate_alarm_rate"].map(percent)
    return table[
        [
            "selection_category",
            "strategy_id",
            "max(value)",
            "strategy",
            "delta",
            "95% CI",
            "W/L/T",
            "Holm p",
            "query cost",
            "requery rate",
            "surrogate alarm",
        ]
    ].rename(
        columns={"selection_category": "Category", "strategy_id": "Strategy"}
    ).to_markdown(index=False)


def per_case_table(frame: pd.DataFrame, selected_ids: set[str]) -> str:
    table = frame.loc[frame["strategy_id"].isin(selected_ids)].copy()
    table["baseline"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["strategy"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["delta"] = table["delta_success_rate"].map(pp)
    table["queries"] = table["query_overhead_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    return table[
        ["case_id", "strategy_id", "baseline", "strategy", "delta", "queries"]
    ].rename(
        columns={"case_id": "Case", "strategy_id": "Method"}
    ).to_markdown(index=False)


def stratum_table(frame: pd.DataFrame, selected_ids: set[str]) -> str:
    table = frame.loc[frame["strategy_id"].isin(selected_ids)].copy()
    table["delta"] = table["delta_success_rate"].map(pp)
    table["95% CI"] = table.apply(
        lambda row: f"[{pp(row.delta_ci_low)}; {pp(row.delta_ci_high)}]", axis=1
    )
    return table[
        ["case_stratum", "strategy_id", "paired_rollouts", "delta", "95% CI"]
    ].rename(
        columns={
            "case_stratum": "Stratum",
            "strategy_id": "Method",
            "paired_rollouts": "Paired seeds",
        }
    ).to_markdown(index=False)


def episode_diagnostic_table(frame: pd.DataFrame, strategy_ids: set[str]) -> str:
    rows: list[dict[str, object]] = []
    for strategy_id, group in frame.loc[frame["strategy_id"].isin(strategy_ids)].groupby(
        "strategy_id", sort=True
    ):
        success = group["success"].map(bool_value)
        failures = group.loc[~success]
        failure_types = (
            failures["failure_type"].fillna("unspecified").astype(str).value_counts()
            if "failure_type" in failures
            else pd.Series(dtype=int)
        )
        rows.append(
            {
                "Method": strategy_id,
                "Success": f"{int(success.sum())}/{len(group)}",
                "Failure labels": "; ".join(
                    f"{name}: {int(count)}" for name, count in failure_types.items()
                )
                or "none",
                "Target-drop flags": int(
                    group.get("target_drop_candidate", pd.Series(False, index=group.index))
                    .map(bool_value)
                    .sum()
                ),
                "Wrong-object flags": int(
                    group.get(
                        "wrong_object_interaction_candidate",
                        pd.Series(False, index=group.index),
                    )
                    .map(bool_value)
                    .sum()
                ),
                "Mean queries": float(group["num_queries_observed"].mean()),
            }
        )
    return pd.DataFrame(rows).to_markdown(index=False, floatfmt=".2f")


def failure_mode_table(frame: pd.DataFrame, strategy_ids: set[str]) -> str:
    table = frame.loc[
        frame["strategy_id"].isin(strategy_ids)
        & frame["event"].isin(
            [
                "target_drop_candidate",
                "wrong_object_interaction_candidate",
                "timeout_no_goal",
            ]
        )
    ].copy()
    table["baseline rate"] = table["baseline_event_rate"].map(percent)
    table["strategy rate"] = table["strategy_event_rate"].map(percent)
    table["delta"] = table["delta_event_rate"].map(pp)
    table["reduced/increased"] = table.apply(
        lambda row: f"{int(row.event_reduced)}/{int(row.event_increased)}", axis=1
    )
    table["exact p"] = table["mcnemar_exact_p"].map(
        lambda value: f"{float(value):.4g}"
    )
    return table[
        [
            "strategy_id",
            "event",
            "baseline rate",
            "strategy rate",
            "delta",
            "reduced/increased",
            "exact p",
        ]
    ].rename(columns={"strategy_id": "Method", "event": "Event"}).to_markdown(
        index=False
    )


def conclusions(
    frozen: pd.DataFrame,
    pooled: pd.DataFrame,
    surrogate_transfer: pd.DataFrame,
    early: pd.DataFrame,
    episodes: pd.DataFrame,
) -> str:
    lines: list[str] = []
    frozen_ids = set(frozen["strategy_id"])
    for row in frozen.itertuples(index=False):
        confirmed = float(row.delta_ci_low) > 0.0 and float(row.mcnemar_holm_p) < 0.05
        verdict = (
            "строго подтверждено"
            if confirmed
            else "направление оценено, но строгого подтверждения нет"
        )
        lines.append(
            f"- **`{row.strategy_id}`:** {int(row.strategy_successes)}/"
            f"{int(row.paired_rollouts)} против {int(row.baseline_successes)}/"
            f"{int(row.paired_rollouts)}, {pp(row.delta_success_rate)}, 95% CI "
            f"[{pp(row.delta_ci_low)}; {pp(row.delta_ci_high)}], Holm "
            f"p={float(row.mcnemar_holm_p):.4g}, query cost "
            f"{float(row.query_overhead_ratio):.2f}x; {verdict}."
        )
    for strategy_id in ("action_l1", "requery_l1_h8"):
        if strategy_id in frozen_ids:
            continue
        rows = pooled.loc[pooled["strategy_id"].eq(strategy_id)]
        if rows.empty:
            continue
        row = rows.iloc[0]
        lines.append(
            f"- **Control `{strategy_id}`:** {pp(row.delta_success_rate)}, "
            f"CI [{pp(row.delta_ci_low)}; {pp(row.delta_ci_high)}], query cost "
            f"{float(row.query_overhead_ratio):.2f}x."
        )

    baseline = episodes.loc[episodes["strategy_id"].eq("max_value")].copy()
    case_rates = baseline.groupby("case_id")["success"].apply(
        lambda values: values.map(bool_value).mean()
    )
    mixed_cases = int(case_rates.between(0.0, 1.0, inclusive="neither").sum())
    lines.append(
        f"- **Информативность cases:** mixed success/fail есть в {mixed_cases}/"
        f"{len(case_rates)} baseline cases; остальные находятся на 0% или 100% success "
        "и проверяют перенос, но почти не различают planners."
    )

    surrogate_rows = frozen.loc[frozen["selection_category"].eq("surrogate_adaptive")]
    if not surrogate_rows.empty:
        row = surrogate_rows.iloc[0]
        surrogate_id = str(row["strategy_id"])
        supported = float(row["delta_ci_low"]) > 0.0 and float(row["mcnemar_holm_p"]) < 0.05
        lines.append(
            "- **Surrogate-gated planning hypothesis:** "
            + ("подтверждена на frozen split." if supported else "не подтверждена на frozen split.")
        )
        surrogate_episodes = episodes.loc[episodes["strategy_id"].eq(surrogate_id)]
        baseline_drop = int(
            baseline["target_drop_candidate"].map(bool_value).sum()
        )
        surrogate_drop = int(
            surrogate_episodes["target_drop_candidate"].map(bool_value).sum()
        )
        baseline_timeout = int(
            baseline["failure_type"].eq("timeout_no_goal").sum()
        )
        surrogate_timeout = int(
            surrogate_episodes["failure_type"].eq("timeout_no_goal").sum()
        )
        lines.append(
            "- **Surrogate failure-mode diagnostic:** heuristic target-drop flags "
            f"{baseline_drop} -> {surrogate_drop}, while `timeout_no_goal` failures "
            f"{baseline_timeout} -> {surrogate_timeout}. Это возможный обмен drop-risk "
            "на незавершение задачи, а не официальный LIBERO-Safety результат."
        )

    requery_rows = frozen.loc[
        frozen["selection_category"].eq("non_surrogate_adaptive")
    ]
    if not requery_rows.empty:
        requery_id = str(requery_rows.iloc[0]["strategy_id"])
        requery_episodes = episodes.loc[episodes["strategy_id"].eq(requery_id)]
        baseline_drop = int(baseline["target_drop_candidate"].map(bool_value).sum())
        requery_drop = int(
            requery_episodes["target_drop_candidate"].map(bool_value).sum()
        )
        baseline_timeout = int(baseline["failure_type"].eq("timeout_no_goal").sum())
        requery_timeout = int(
            requery_episodes["failure_type"].eq("timeout_no_goal").sum()
        )
        lines.append(
            "- **Confirmed requery failure modes:** heuristic target-drop flags "
            f"{baseline_drop} -> {requery_drop}, while `timeout_no_goal` failures "
            f"{baseline_timeout} -> {requery_timeout}; requery уменьшает drops, но "
            "частично переносит ошибки в незавершение."
        )

    transfer_rows = surrogate_transfer.loc[surrogate_transfer["case_stratum"].eq("all")]
    if not transfer_rows.empty:
        row = transfer_rows.iloc[0]
        lines.append(
            "- **Mechanism:** surrogate переносится на next-chunk future-proprio error "
            f"(case-controlled rho={float(row['case_controlled_rank_correlation']):.3f}, "
            f"AUROC={float(row['case_relative_top_quartile_auc']):.3f}, alarm lift="
            f"{float(row['alarm_actual_error_lift']):.2f}x), но эта физическая ошибка "
            "не тождественна task failure."
        )

    if not early.empty:
        top = early.iloc[0]
        lines.append(
            "- **Early task-fail detection:** лучший q0-q3 case-controlled AUROC "
            f"равен {float(top['case_controlled_oriented_auc']):.3f}; универсальный "
            "online fail detector по текущим метрикам не получен."
        )
    return "\n".join(lines)


def video_gallery(media: pd.DataFrame) -> str:
    blocks: list[str] = []
    for (case_id, seed), rows in media.groupby(["case_id", "rollout_seed"], sort=True):
        cells: list[str] = []
        for row in rows.sort_values("strategy_id").itertuples(index=False):
            success = bool_value(row.success)
            outcome = "SUCCESS" if success else "FAIL"
            color = "#157347" if success else "#b02a37"
            src = f"final_results_media/surrogate_confirmatory_20260819/{row.filename}"
            cells.append(
                '<td style="vertical-align:top;padding:8px">'
                f"<b>{row.strategy_id}</b><br>"
                f'<span style="color:{color};font-weight:700">{outcome}</span>'
                f" · t={int(row.final_t)}<br>"
                f'<video controls preload="metadata" width="270" src="{src}"></video>'
                f'<br><a href="{src}">Open MP4</a></td>'
            )
        reproduced = bool_value(rows.iloc[0]["selected_pair_reproduced"])
        blocks.append(
            f"<h4>{case_id}, rollout_seed={int(seed)}</h4>"
            f"<p>Selected pair {'reproduced' if reproduced else 'changed on replay'}.</p>"
            '<table style="width:100%"><tr>'
            + "".join(cells)
            + "</tr></table>"
        )
    return "\n".join(blocks)


def build_notebook() -> nbformat.NotebookNode:
    selected = pd.read_csv(SCREEN / "selected_for_confirmatory.csv")
    frozen = pd.read_csv(CONFIRM / "frozen_confirmatory_results.csv")
    pooled = pd.read_csv(CONFIRM / "pooled_strategies.csv")
    per_case = pd.read_csv(CONFIRM / "paired_by_case.csv")
    strata = pd.read_csv(CONFIRM / "pooled_by_stratum.csv")
    correlations = pd.read_csv(CONFIRM / "prediction_error_correlations.csv")
    surrogate_transfer = pd.read_csv(CONFIRM / "surrogate_transfer_diagnostics.csv")
    early = pd.read_csv(CONFIRM / "early_failure_predictors_q0_3.csv")
    episodes = pd.read_csv(CONFIRM / "episode_outcomes.csv")
    failure_modes = pd.read_csv(CONFIRM / "paired_failure_modes.csv")
    media = pd.read_csv(MEDIA / "manifest.csv") if (MEDIA / "manifest.csv").exists() else None
    video_selection = (
        pd.read_csv(VIDEO_SELECTION) if VIDEO_SELECTION.exists() else None
    )
    selected_ids = set(frozen["strategy_id"])
    diagnostic_ids = selected_ids | {"max_value", "action_l1"}
    baseline_case_rates = (
        episodes.loc[episodes["strategy_id"].eq("max_value")]
        .groupby("case_id")["success"]
        .apply(lambda values: values.map(bool_value).mean())
    )
    mixed_case_count = int(
        baseline_case_rates.between(0.0, 1.0, inclusive="neither").sum()
    )

    cells = [
        new_markdown_cell(
            """# Prediction-error surrogate и adaptive requery

**Frozen screening + confirmatory experiment · 19 August 2026**

Отдельный notebook новой линии uncertainty-aware planning. Все числа ниже
читаются из сохранённых campaign artifacts; exploratory screening и независимый
confirmatory split не смешиваются."""
        ),
        new_markdown_cell(
            r"""## 1. Гипотеза

Стандартный planner выбирает один из четырёх stochastic candidates:

\[
i_V=\arg\max_i V_i.
\]

Ранее adaptive `requery_l1_h8` улучшил pooled success, но вредил отдельным
задачам. Новая гипотеза: сокращать open-loop chunk и включать risk-aware
ranking только тогда, когда **до исполнения** ожидается большая ошибка
предсказанного future proprio.

Frozen causal surrogate использует четыре online-признака:

\[
\log \widehat e_q=-2.89194
+0.12337z(\log U^a_q)
+0.13764z(\log U^p_q)
+0.40796z(\log \bar V_q)
+0.30282z(\log D^p_q).
\]

- $U^a_q$: disagreement повторных latent action copies;
- $U^p_q$: disagreement latent future-proprio copies;
- $\bar V_q$: среднее value четырёх candidates;
- $D^p_q$: across-candidate spread predicted future proprio.

Порог $G_q=\mathbb{1}[\widehat e_q\ge\tau_e]$ фиксируется по train quantile.
При alarm исполняется 8 действий вместо 16. Risk-aware candidate вычисляется
как

\[
i_R=\arg\max_i\left[z(V_i)-\lambda z(U^{a,first}_i)\right].
\]

Фактическая next-chunk prediction error используется только для последующего
анализа и не входит в выбор того же chunk."""
        ),
        new_markdown_cell(
            r"""## 2. Протокол

1. Surrogate обучен на 1430 `max(value)` queries и проверен на 1400 queries из
   непересекающихся denoise-10 episodes: Spearman 0.745, case-controlled
   Spearman 0.649, top-quartile error AUROC 0.771.
2. Screening: 6 LIBERO-PRO boundary cases, 8 paired seeds, 102 configurations,
   816 episode executions. Проверяются три frozen thresholds, две phase fractions
   и пять online gating variants.
3. Выбирается ровно один `surrogate_adaptive` и один
   `non_surrogate_adaptive` метод по

\[
J=\Delta_{pool}+0.5\min_c\Delta_c
-0.02\max(0,Q_{ratio}-1).
\]

4. Confirmatory: замороженные методы, 20 новых paired seeds на 12 cases.
   Шесть cases повторяют boundary-задачи, ещё шесть заранее фиксируют новые
   LIBERO-PRO object/language/swap/task shifts.
5. Primary endpoint: paired success delta к `max(value)`, stratified bootstrap
   CI, exact McNemar и Holm correction. Compute overhead и safety signals
   считаются secondary outcomes."""
        ),
        new_code_cell(
            """from pathlib import Path
import pandas as pd
from IPython.display import HTML, Image, Markdown, display

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == 'experiments':
    PROJECT_ROOT = PROJECT_ROOT.parent

SCREEN = PROJECT_ROOT / 'experiments/campaigns/surrogate_screening_20260819/analysis/adaptive_summary'
CONFIRM = PROJECT_ROOT / 'experiments/campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary'
MEDIA = PROJECT_ROOT / 'experiments/final_results_media/surrogate_confirmatory_20260819'

selected = pd.read_csv(SCREEN / 'selected_for_confirmatory.csv')
frozen = pd.read_csv(CONFIRM / 'frozen_confirmatory_results.csv')
display(selected[['selection_category', 'strategy_id', 'selection_utility']])
display(frozen[['selection_category', 'strategy_id', 'strategy_success_rate',
                'delta_success_rate', 'delta_ci_low', 'delta_ci_high',
                'mcnemar_holm_p', 'query_overhead_ratio']])"""
        ),
        new_markdown_cell(
            f"""## 3. Screening selection

{screen_table(selected)}

![Screening success/compute trade-off](campaigns/surrogate_screening_20260819/analysis/adaptive_summary/plots/success_compute_tradeoff.png)

Это calibration-результат, а не финальная оценка эффекта."""
        ),
        new_markdown_cell(
            f"""## 4. Frozen confirmatory result

{confirm_table(frozen)}

![Confirmatory pooled delta](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/plots/pooled_strategy_delta.png)"""
        ),
        new_markdown_cell(
            f"""## 5. Перенос по задачам

### Paired delta по каждому case

{per_case_table(per_case, selected_ids)}

![Per-case heatmap](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/plots/paired_delta_heatmap.png)

### Повторённые boundary cases и новые OOD axes

{stratum_table(strata, selected_ids)}

У `max(value)` смешанные success/fail наблюдаются в
**{mixed_case_count}/{len(baseline_case_rates)}** cases. Cases с 0% или 100%
success полезны для проверки transfer и catastrophic regression, но дают мало
информации о тонком ранжировании planners."""
        ),
        new_markdown_cell(
            f"""## 6. Mechanism diagnostics

Эти результаты exploratory и не меняют frozen planner.

### Frozen surrogate transfer

{surrogate_transfer.to_markdown(index=False, floatfmt=".3f")}

![Prediction-error correlations](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/plots/uncertainty_prediction_error_correlations.png)

{correlations.head(12).to_markdown(index=False)}

![Early failure AUROC](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/plots/early_failure_predictor_auc.png)

{early.head(12).to_markdown(index=False)}"""
        ),
        new_markdown_cell(
            f"""## 7. Task-failure and interaction diagnostics

{episode_diagnostic_table(episodes, diagnostic_ids)}

### Paired failure-mode changes

{failure_mode_table(failure_modes, diagnostic_ids - {'max_value'})}

`Target-drop` и `wrong-object` здесь являются эвристическими признаками из
LIBERO-PRO rollout. Это secondary diagnostics, а не официальные ограничения
LIBERO-Safety и не самостоятельное доказательство причины task failure.
`exact p` здесь не скорректирован за множественные exploratory comparisons."""
        ),
    ]

    if media is not None and not media.empty:
        reproduced = media.groupby(["case_id", "rollout_seed"])[
            "selected_pair_reproduced"
        ].first().map(bool_value)
        cells.append(
            new_markdown_cell(
                f"""## 8. Matched-seed video replays

Видео выбраны механически только после confirmatory статистики по discordant
outcomes. Исходная frozen пара полностью воспроизвелась в
**{int(reproduced.sum())}/{len(reproduced)}** replay groups. Success-rate вывод
берётся из полной таблицы, а не из этой выбранной галереи.

{video_gallery(media)}"""
            )
        )
    else:
        if video_selection is not None and not video_selection.empty:
            queued_groups = len(
                video_selection[["case_id", "rollout_seed"]].drop_duplicates()
            )
            video_status = (
                "Discordant outcomes найдены, и механически выбраны "
                f"**{queued_groups}** matched-seed replay groups. MP4 пока не "
                "сгенерированы: replay campaign ожидает свободную GPU 2-7. "
                "Confirmatory success statistics уже завершена и от replay не зависит."
            )
        else:
            video_status = (
                "Manifest для discordant replay не сформирован; video gallery пока "
                "недоступна."
            )
        cells.append(
            new_markdown_cell(
                "## 8. Matched-seed video replays\n\n" + video_status
            )
        )

    cells.extend(
        [
            new_markdown_cell(
                f"""## 9. Выводы

{conclusions(frozen, pooled, surrogate_transfer, early, episodes)}

Интерпретация ограничивается frozen confirmatory split. Положительный screening
delta без переноса на новые seeds/cases не считается доказанным улучшением.
Prediction-error surrogate оценивает риск динамически на каждом query, но сам по
себе не гарантирует task failure: он должен рассматриваться как routing signal
для candidate ranking и частоты обратной связи со средой."""
            ),
            new_markdown_cell(
                """## 10. Воспроизводимость

- [Frozen hypotheses and protocol](SURROGATE_REQUERY_HYPOTHESES_20260819.md)
- [Surrogate artifact](models/future_proprio_error_surrogate_v1.json)
- [Screening analysis](campaigns/surrogate_screening_20260819/analysis/adaptive_summary/README.md)
- [Confirmatory analysis](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/README.md)
- [Queued video selection](configs/libero_campaign_surrogate_video_replays.csv)
- [Video manifest](final_results_media/surrogate_confirmatory_20260819/README.md)"""
            ),
        ]
    )
    for index, cell in enumerate(cells):
        cell["id"] = f"surrogate-requery-{index:02d}"
    notebook = new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Cosmos Policy LIBERO",
                "language": "python",
                "name": "cosmos-policy-libero",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
    )
    nbformat.validate(notebook)
    return notebook


def main() -> int:
    required = [
        SCREEN / "selected_for_confirmatory.csv",
        CONFIRM / "frozen_confirmatory_results.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing completed experiment artifacts:\n" + "\n".join(missing)
        )
    notebook = build_notebook()
    nbformat.write(notebook, OUTPUT)
    print(f"Built: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

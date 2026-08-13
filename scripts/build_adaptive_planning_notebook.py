#!/usr/bin/env python3
"""Build the focused adaptive-planning experiment notebook from saved results."""

from __future__ import annotations

from pathlib import Path

import nbformat
import pandas as pd
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = PROJECT_ROOT / "experiments"
CALIBRATION = (
    EXPERIMENTS
    / "campaigns/adaptive_screening_20260813/analysis/adaptive_summary"
)
CONFIRMATORY = (
    EXPERIMENTS
    / "campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary"
)
MEDIA = EXPERIMENTS / "final_results_media/adaptive_confirmatory_20260813"
OUTPUT = EXPERIMENTS / "LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb"


def percent(value: float) -> str:
    return f"{100.0 * float(value):+.1f} pp"


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def result_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["baseline"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["strategy_result"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["delta"] = table["delta_success_rate"].map(percent)
    table["95% CI"] = table.apply(
        lambda row: f"[{percent(row.delta_ci_low)}; {percent(row.delta_ci_high)}]",
        axis=1,
    )
    table["W/L/T"] = table.apply(
        lambda row: f"{int(row.wins)}/{int(row.losses)}/{int(row.ties)}", axis=1
    )
    table["Holm p"] = table.get("mcnemar_holm_p", table["mcnemar_exact_p"]).map(
        lambda value: f"{float(value):.4f}"
    )
    table["query cost"] = table["query_overhead_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    table["actual calls"] = table["actual_query_count_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    columns = [
        "selection_category",
        "strategy_id",
        "baseline",
        "strategy_result",
        "delta",
        "95% CI",
        "W/L/T",
        "Holm p",
        "query cost",
        "actual calls",
    ]
    return table[columns].rename(
        columns={
            "selection_category": "Category",
            "strategy_id": "Strategy",
            "baseline": "max(value)",
            "strategy_result": "Result",
        }
    ).to_markdown(index=False)


def calibration_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["max(value)"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["Result"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["Delta"] = table["delta_success_rate"].map(percent)
    table["Worst case"] = table["min_case_delta"].map(percent)
    table["Query cost"] = table["query_overhead_ratio"].map(
        lambda value: f"{float(value):.2f}x"
    )
    return table[
        [
            "selection_category",
            "strategy_id",
            "max(value)",
            "Result",
            "Delta",
            "Worst case",
            "Query cost",
            "selection_utility",
        ]
    ].rename(
        columns={
            "selection_category": "Category",
            "strategy_id": "Selected strategy",
            "selection_utility": "Selection utility J",
        }
    ).to_markdown(index=False)


def per_case_table(frame: pd.DataFrame, strategy_ids: set[str]) -> str:
    table = frame.loc[frame["strategy_id"].isin(strategy_ids)].copy()
    table["Baseline"] = table.apply(
        lambda row: f"{int(row.baseline_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["Strategy"] = table.apply(
        lambda row: f"{int(row.strategy_successes)}/{int(row.paired_rollouts)}",
        axis=1,
    )
    table["Delta"] = table["delta_success_rate"].map(percent)
    return table[
        ["case_id", "strategy_id", "Baseline", "Strategy", "Delta", "wins", "losses"]
    ].rename(
        columns={
            "case_id": "Case",
            "strategy_id": "Method",
            "wins": "Wins",
            "losses": "Losses",
        }
    ).to_markdown(index=False)


def replay_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["Reference"] = table["reference_success_rate"].map(
        lambda value: f"{float(value):.1%}"
    )
    table["Replay"] = table["replay_success_rate"].map(
        lambda value: f"{float(value):.1%}"
    )
    table["Disagreement"] = table.apply(
        lambda row: (
            f"{int(row.outcome_disagreements)}/{int(row.paired_rollouts)} "
            f"({float(row.outcome_disagreement_rate):.1%})"
        ),
        axis=1,
    )
    return table[
        ["reference_id", "replay_id", "Reference", "Replay", "Disagreement"]
    ].rename(columns={"reference_id": "Reference method", "replay_id": "Exact replay"}).to_markdown(
        index=False
    )


def conclusion_text(
    frozen: pd.DataFrame,
    fixed: pd.Series,
    versus_fixed: pd.DataFrame,
) -> str:
    lines = []
    for row in frozen.itertuples(index=False):
        confirmed = row.delta_ci_low > 0 and row.mcnemar_holm_p < 0.05
        verdict = (
            "подтвердилась после Holm-коррекции"
            if confirmed
            else "не получила строгого confirmatory подтверждения"
        )
        lines.append(
            f"- **`{row.strategy_id}`:** {percent(row.delta_success_rate)} против "
            f"`max(value)`, CI [{percent(row.delta_ci_low)}; "
            f"{percent(row.delta_ci_high)}], Holm p={row.mcnemar_holm_p:.4f}; "
            f"гипотеза {verdict}."
        )
    lines.append(
        f"- **Fixed `action_l1` control:** {percent(fixed.delta_success_rate)}, "
        f"CI [{percent(fixed.delta_ci_low)}; {percent(fixed.delta_ci_high)}], "
        f"McNemar p={fixed.mcnemar_exact_p:.4f}."
    )
    requery_fixed = versus_fixed.loc[
        versus_fixed["strategy_id"].eq("requery_l1_h8")
    ].iloc[0]
    lines.append(
        f"- **Requery против fixed penalty:** "
        f"{percent(requery_fixed.delta_success_rate)}, CI "
        f"[{percent(requery_fixed.delta_ci_low)}; "
        f"{percent(requery_fixed.delta_ci_high)}], "
        f"McNemar p={requery_fixed.mcnemar_exact_p:.4f}; преимущество над "
        "`max(value)` подтверждено, но над сильным fixed control пока нет."
    )
    return "\n".join(lines)


def video_gallery(media: pd.DataFrame) -> str:
    cards = []
    for (case_id, seed), rows in media.groupby(["case_id", "rollout_seed"], sort=True):
        cells = []
        for row in rows.sort_values("strategy_id").itertuples(index=False):
            success = as_bool(row.success)
            outcome = "SUCCESS" if success else "FAIL"
            color = "#157347" if success else "#b02a37"
            src = f"final_results_media/adaptive_confirmatory_20260813/{row.filename}"
            cells.append(
                '<td style="vertical-align:top;padding:8px">'
                f"<b>{row.strategy_id}</b><br>"
                f'<span style="color:{color};font-weight:700">{outcome}</span>'
                f" · t={int(row.final_t)}<br>"
                f'<video controls preload="metadata" width="270" src="{src}"></video>'
                f'<br><a href="{src}">Open MP4</a></td>'
            )
        reproduced = as_bool(rows.iloc[0]["selected_pair_reproduced"])
        replay_note = (
            "selected pair reproduced"
            if reproduced
            else "selected pair changed under exact replay"
        )
        cards.append(
            f"<h4>{case_id}, rollout_seed={int(seed)}</h4>"
            f"<p>{replay_note}</p>"
            '<table style="width:100%"><tr>'
            + "".join(cells)
            + "</tr></table>"
        )
    return "\n".join(cards)


def build_notebook() -> nbformat.NotebookNode:
    calibration = pd.read_csv(CALIBRATION / "selected_for_confirmatory.csv")
    frozen = pd.read_csv(CONFIRMATORY / "frozen_confirmatory_results.csv")
    pooled = pd.read_csv(CONFIRMATORY / "pooled_strategies.csv")
    per_case = pd.read_csv(CONFIRMATORY / "paired_by_case.csv")
    replay = pd.read_csv(CONFIRMATORY / "replay_control_summary.csv")
    versus_fixed = pd.read_csv(CONFIRMATORY / "frozen_vs_action_l1.csv")
    strata = pd.read_csv(CONFIRMATORY / "pooled_by_stratum.csv")
    early = pd.read_csv(CONFIRMATORY / "early_failure_predictors_q0_3.csv")
    correlations = pd.read_csv(CONFIRMATORY / "prediction_error_correlations.csv")
    media = pd.read_csv(MEDIA / "manifest.csv")
    replay_groups = media.groupby(["case_id", "rollout_seed"], sort=False).first()
    replay_reproduced = int(
        replay_groups["selected_pair_reproduced"].map(as_bool).sum()
    )
    fixed = pooled.loc[pooled["strategy_id"].eq("action_l1")].iloc[0]
    selected_ids = set(frozen["strategy_id"])

    stratum_selected = strata.loc[strata["strategy_id"].isin(selected_ids)].copy()
    stratum_selected["Delta"] = stratum_selected["delta_success_rate"].map(percent)
    stratum_selected["95% CI"] = stratum_selected.apply(
        lambda row: f"[{percent(row.delta_ci_low)}; {percent(row.delta_ci_high)}]",
        axis=1,
    )
    stratum_md = stratum_selected[
        ["case_stratum", "strategy_id", "paired_rollouts", "Delta", "95% CI"]
    ].rename(
        columns={
            "case_stratum": "Stratum",
            "strategy_id": "Strategy",
            "paired_rollouts": "Paired seeds",
        }
    ).to_markdown(index=False)

    cells = [
        new_markdown_cell(
            """# Adaptive uncertainty-aware planning для Cosmos Policy

**Frozen confirmatory snapshot · 13 August 2026**

Отдельный notebook для новой линии экспериментов. Screening, независимый
confirmatory split и качественные video replays здесь явно разделены. Старый
`ysda_world_models.ipynb` не используется как источник итоговых чисел."""
        ),
        new_markdown_cell(
            r"""## 1. Постановка

На каждом query из одного реального наблюдения генерируются $N=4$
stochastic candidates. Для кандидата $i$ доступны predicted value $V_i$,
action chunk $A_i\in\mathbb{R}^{16\times7}$, future image/proprio и latent
copies action/value.

Каждый candidate является одной согласованной авторегрессионной веткой
$A_i\rightarrow \widehat s_i\rightarrow V_i$: value относится к action и
future-state того же sample. Четыре ветки можно считать батчем на GPU, но при
planning они остаются четырьмя отдельными кандидатами, а не одной усреднённой
value-матрицей.

Baseline выбирает

\[
i_{V}=\arg\max_i V_i.
\]

Для первого действия uncertainty кандидата агрегируется по повторным latent
copies $k$ и всем семи координатам action $d$:

\[
U_i=\frac{1}{B}\sum_{b=1}^{B}
\sqrt{\sum_{d=1}^{7}
\operatorname{Std}_{k}\!\left[\widetilde A_{i,b,k,0,d}\right]^2},
\qquad
S_i=z(V_i)-\lambda z(U_i),
\qquad i_R=\arg\max_i S_i.
\]

Здесь учитываются все 7 координат первого действия, включая gripper; $B=1$ в
обычном online rollout. Повторные latent copies находятся внутри одного
candidate и отличаются от четырёх stochastic candidates $i$.
Стандартизация выполняется отдельно внутри текущего query:

\[
z(x_i)=\frac{x_i-\frac1N\sum_jx_j}
{\sqrt{\frac1N\sum_j(x_j-\bar x)^2}+10^{-6}}.
\]

`phase_l1_r0.3` использует $i_R$ только при $t/T_{max}\le0.3$, затем
возвращается к $i_V$. `requery_l1_h8` всегда выбирает $i_R$, но исполняет
8 вместо 16 действий, когда $i_R\ne i_V$, и раньше получает новое реальное
наблюдение."""
        ),
        new_markdown_cell(
            r"""## 2. Протокол и гипотезы

1. Screening: 3 известных LIBERO-PRO boundary case, 12 одинаковых seed.
2. Выбор одного метода без extra inference и одного adaptive-horizon метода по
   заранее заданному критерию

\[
J=\Delta_{pool}+0.5\min_c\Delta_c
-0.02\max(0,Q_{ratio}-1).
\]

3. Frozen confirmatory: 30 новых seed на каждом из 6 case, включая 3 новых OOD
   holdout; всего 180 paired seed на стратегию.
4. Primary endpoint: paired success delta против `max(value)`, stratified
   bootstrap CI, exact McNemar и Holm correction для двух frozen гипотез.
5. Exact replay измеряет noise floor. Видео выбираются после статистики только
   по discordant outcome и не используются для success-rate оценки."""
        ),
        new_code_cell(
            """from pathlib import Path
import pandas as pd
from IPython.display import HTML, Image, Markdown, display

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == 'experiments':
    PROJECT_ROOT = PROJECT_ROOT.parent

CALIBRATION = PROJECT_ROOT / 'experiments/campaigns/adaptive_screening_20260813/analysis/adaptive_summary'
CONFIRMATORY = PROJECT_ROOT / 'experiments/campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary'
MEDIA = PROJECT_ROOT / 'experiments/final_results_media/adaptive_confirmatory_20260813'

frozen = pd.read_csv(CONFIRMATORY / 'frozen_confirmatory_results.csv')
per_case = pd.read_csv(CONFIRMATORY / 'paired_by_case.csv')
replay = pd.read_csv(CONFIRMATORY / 'replay_control_summary.csv')
print(f'Loaded {int(frozen.paired_rollouts.max())} paired seeds per frozen strategy.')"""
        ),
        new_markdown_cell(
            f"""## 3. Calibration selection

{calibration_table(calibration)}

![Calibration success/compute trade-off](campaigns/adaptive_screening_20260813/analysis/adaptive_summary/plots/success_compute_tradeoff.png)

Это screening-числа, а не финальная оценка эффекта."""
        ),
        new_markdown_cell(
            f"""## 4. Frozen confirmatory result

{result_table(frozen)}

![Confirmatory pooled delta](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/plots/pooled_strategy_delta.png)

`query cost` нормирован на число query, необходимое для фактически исполненного
числа env steps при стандартном chunk=16. `actual calls` может быть меньше этой
оценки, если улучшенная стратегия раньше завершает эпизод."""
        ),
        new_markdown_cell(
            f"""## 5. Перенос и неоднородность

### По каждому case

{per_case_table(per_case, selected_ids)}

![Per-case paired delta](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/plots/paired_delta_heatmap.png)

### Известные boundary против новых OOD holdout

{stratum_md}"""
        ),
        new_markdown_cell(
            f"""## 6. Контроли и noise floor

{replay_table(replay)}

Fixed `action_l1` сравнивается с теми же 180 baseline seed. Его результат:
**{percent(fixed.delta_success_rate)}**, CI
[{percent(fixed.delta_ci_low)}; {percent(fixed.delta_ci_high)}],
exact McNemar p={fixed.mcnemar_exact_p:.4f}.

Outcome noise floor равен 4.4% для exact `max(value)` replay и 9.4% для
`action_l1`. Поэтому качественное расхождение одного видео само по себе не
доказывает эффект; основной вывод опирается на все paired seeds."""
        ),
        new_markdown_cell(
            f"""## 7. Mechanism diagnostics

Эти таблицы exploratory и не меняют frozen planner.

![Early failure AUROC](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/plots/early_failure_predictor_auc.png)

{early.head(10).to_markdown(index=False)}

![Uncertainty vs prediction error](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/plots/uncertainty_prediction_error_correlations.png)

{correlations.head(10).to_markdown(index=False)}"""
        ),
        new_markdown_cell(
            f"""## 8. Matched-seed video replays

Видео выбраны механически по discordant confirmatory outcomes. В каждой группе
совпадают suite/task/init/rollout seed; меняется только planning strategy.
Исходная selected-strategy пара полностью воспроизвела оба бинарных outcome в
**{replay_reproduced}/{len(replay_groups)}** exact replays. Поэтому ролики
показывают механизм расхождения траекторий, а causal success-rate вывод берётся
из всех 180 paired seeds выше.

{video_gallery(media)}"""
        ),
        new_markdown_cell(
            f"""## 9. Выводы

{conclusion_text(frozen, fixed, versus_fixed)}

Дополнительно:

- эффекты ожидаемо уменьшились относительно screening (`requery`: +30.6 до
  +15.6 п.п.; `phase`: +19.4 до +8.3 п.п.), но сохранили направление на новых
  seed; это показывает, зачем calibration и confirmatory split были разделены;
- `phase_l1_r0.3` дал положительный delta во всех шести cases и не требует
  дополнительных calls, но практически не отличается от fixed `action_l1`;
- `requery_l1_h8` улучшил четыре cases, однако ухудшил `milk_task5` на 10 п.п.
  и `goal_mug_task9` на 3.3 п.п.; нужен context gate, а не безусловный requery;
- pooled requery effect сохранился отдельно на известных boundary cases
  (+18.9 п.п.) и новых OOD holdout (+12.2 п.п.);
- ранние uncertainty/value признаки дают лишь умеренный fail AUROC (лучший
  case-controlled результат 0.588), поэтому они лучше подходят для
  относительного candidate ranking, чем для общего порога fail;
- latent-action uncertainty коррелирует с next-chunk proprio error
  (case-controlled Spearman 0.548), что поддерживает предполагаемый механизм;
- adaptive requery оценивается вместе с query-cost, а не как бесплатное улучшение;
- prediction error после chunk является диагностикой, но недоступен для выбора
  того же chunk без отдельного learned surrogate;
- следующий шаг -- learned task/phase gate с leave-one-suite-out проверкой,
  который сохраняет requery там, где он помогает, и отключает на вредных cases."""
        ),
        new_markdown_cell(
            """## 10. Воспроизводимость

- [Гипотезы и frozen protocol](ADAPTIVE_PLANNING_HYPOTHESES_20260813.md)
- [Calibration analysis](campaigns/adaptive_screening_20260813/analysis/adaptive_summary/README.md)
- [Confirmatory analysis](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md)
- [Frozen campaign config](configs/libero_campaign_adaptive_confirmatory_frozen.json)
- [Видео и manifest](final_results_media/adaptive_confirmatory_20260813/README.md)"""
        ),
    ]
    for index, cell in enumerate(cells):
        cell["id"] = f"adaptive-planning-{index:02d}"
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


def main() -> None:
    required = [
        CALIBRATION / "selected_for_confirmatory.csv",
        CONFIRMATORY / "frozen_confirmatory_results.csv",
        MEDIA / "manifest.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing completed experiment artifacts:\n" + "\n".join(missing))
    notebook = build_notebook()
    nbformat.write(notebook, OUTPUT)
    print(f"Built: {OUTPUT}")


if __name__ == "__main__":
    main()

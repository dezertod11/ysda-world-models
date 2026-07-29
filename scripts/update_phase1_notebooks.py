#!/usr/bin/env python3
"""Build the compact Phase 1 results notebook and refresh the research summary."""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pandas as pd
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "experiments" / "campaigns" / "phase1_analysis_20260724"
RESULTS_NOTEBOOK = PROJECT_ROOT / "experiments" / "LIBERO_PHASE1_RESULTS.ipynb"
RESEARCH_NOTEBOOK = PROJECT_ROOT / "ysda_world_models_research.ipynb"


def load_results() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    summary = json.loads((ANALYSIS_DIR / "summary.json").read_text(encoding="utf-8"))
    task_outcomes = pd.read_csv(ANALYSIS_DIR / "outcomes_by_suite_task.csv")
    ranking = pd.read_csv(ANALYSIS_DIR / "early_online_metric_ranking_q0_3.csv")
    return summary, task_outcomes, ranking


def mixed_outcome_markdown(task_outcomes: pd.DataFrame) -> str:
    mixed = task_outcomes.loc[
        (task_outcomes["split"] == "OOD")
        & (task_outcomes["success"] > 0)
        & (task_outcomes["fail"] > 0)
    ]
    rows = [
        "| Suite | Task | Init | Success | Success rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in mixed.itertuples(index=False):
        rows.append(
            f"| `{row.suite}` | {row.task_id} | {row.init_state_id} | "
            f"{row.success}/{row.episodes} | {row.success_rate:.1%} |"
        )
    return "\n".join(rows)


def selected_metric_markdown(ranking: pd.DataFrame) -> str:
    metrics = [
        "latent_action_copy_std_mean_mean_over_samples",
        "value_mean",
        "future_image_pixel_std_mean",
        "action_std_mean",
        "value_std",
        "value_range",
        "action_first_step_l2_std",
    ]
    indexed = ranking.set_index("metric")
    rows = [
        "| Early metric, mean over query 0-3 | Pooled within-group AUROC | Direction | High / tie / low groups |",
        "|---|---:|---|---:|",
    ]
    for metric in metrics:
        row = indexed.loc[metric]
        rows.append(
            f"| `{metric}` | {row.pooled_oriented_auc:.3f} | `{row.direction}` | "
            f"{int(row.groups_strict_high_means_failure)} / {int(row.groups_tied)} / "
            f"{int(row.groups_low_means_failure)} |"
        )
    return "\n".join(rows)


def build_results_notebook(
    summary: dict,
    task_outcomes: pd.DataFrame,
    ranking: pd.DataFrame,
) -> None:
    id_result = summary["split_counts"]["ID"]
    ood_result = summary["split_counts"]["OOD"]
    top = ranking.iloc[0]
    mixed_table = mixed_outcome_markdown(task_outcomes)
    metric_table = selected_metric_markdown(ranking)

    cells = [
        new_markdown_cell(
            f"""# LIBERO Phase 1: ID, OOD и early failure signals

Дата среза: **24 июля 2026 года**.

Этот notebook содержит только результаты серверной Phase 1. Полный протокол
находится в [LIBERO_OOD_SAFETY_CAMPAIGN.md](LIBERO_OOD_SAFETY_CAMPAIGN.md),
машинные таблицы и полный отчёт — в
[`campaigns/phase1_analysis_20260724`](campaigns/phase1_analysis_20260724/README.md).

В анализ включены только завершённые non-smoke runs с `query_traces`,
`metadata` и `pair_summary`. Оборванный запуск с отсутствующими assets исключён."""
        ),
        new_code_cell(
            """from pathlib import Path
import json
import html
import pandas as pd
from IPython.display import HTML, Image, Markdown, Video, display

PROJECT_ROOT = Path.cwd().resolve()
if PROJECT_ROOT.name == 'experiments':
    PROJECT_ROOT = PROJECT_ROOT.parent

ANALYSIS_DIR = PROJECT_ROOT / 'experiments/campaigns/phase1_analysis_20260724'
summary = json.loads((ANALYSIS_DIR / 'summary.json').read_text(encoding='utf-8'))
outcomes = pd.read_csv(ANALYSIS_DIR / 'outcomes_by_suite_task.csv')
episodes = pd.read_csv(ANALYSIS_DIR / 'episode_outcomes.csv')
ranking = pd.read_csv(ANALYSIS_DIR / 'early_online_metric_ranking_q0_3.csv')
metric_by_group = pd.read_csv(ANALYSIS_DIR / 'early_online_metric_by_group_q0_3.csv')
correlations = pd.read_csv(
    ANALYSIS_DIR / 'uncertainty_prediction_error_correlations_controlled.csv'
)
videos = pd.read_csv(ANALYSIS_DIR / 'video_inventory.csv')
print('Loaded:', len(episodes), 'episodes')"""
        ),
        new_markdown_cell(
            f"""## 1. Task outcomes

| Split | Эпизоды | Success | Fail | Success rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| ID | {id_result["episodes"]} | {id_result["success"]} | {id_result["fail"]} | {id_result["success_rate"]:.1%} | [{id_result["wilson_95"][0]:.1%}, {id_result["wilson_95"][1]:.1%}] |
| LIBERO-PRO OOD | {ood_result["episodes"]} | {ood_result["success"]} | {ood_result["fail"]} | {ood_result["success_rate"]:.1%} | [{ood_result["wilson_95"][0]:.1%}, {ood_result["wilson_95"][1]:.1%}] |

Все 72 ID rollout завершились успешно. На специально отобранных OOD
конфигурациях success rate снизился до 77.4%. Это подтверждает работоспособность
OOD screening, но не является несмещённой оценкой полного LIBERO-PRO benchmark."""
        ),
        new_code_cell(
            """display(outcomes)
display(Image(filename=str(ANALYSIS_DIR / 'plots/success_rate_by_suite_task.png')))"""
        ),
        new_markdown_cell(
            f"""## 2. Fixed-init mixed success/fail

{mixed_table}

Получено **{summary["mixed_ood_groups"]}** конфигураций, где при одинаковых
`suite/task/init_state` разные rollout seeds дали оба исхода. Самые удобные
границы для planning:

- `libero_spatial_with_milk/task5/init0`: 12/24 success;
- `libero_spatial_with_yellow_book/task8/init0`: 3/6;
- `libero_10_with_mug/task4/init0`: 2/4.

Milk уже даёт наиболее надёжную статистику. Yellow-book и long-horizon варианты
нужно расширить минимум до 40 rollout каждый."""
        ),
        new_code_cell(
            """mixed = outcomes[
    outcomes['success'].gt(0) & outcomes['fail'].gt(0)
].copy()
display(mixed.sort_values(['success_rate', 'episodes']))"""
        ),
        new_markdown_cell(
            f"""## 3. Failure modes и safety diagnostics

OOD outcomes:

- `timeout_no_goal`: **12**;
- `target_drop_candidate`: **11**;
- `timeout_partial_goal`: **1**.

Официальных safety violations нет, поскольку Phase 1 запускалась в LIBERO-PRO,
а не в LIBERO-Safety. Drop heuristic отметил 19 OOD эпизодов, но только 11 из
них закончились fail: precision 57.9%, recall всех fail 45.8%. Восемь
траекторий восстановились и завершили задачу, поэтому transient drop полезен как
событие для temporal monitor, но не как окончательный label."""
        ),
        new_code_cell(
            """display(Image(filename=str(ANALYSIS_DIR / 'plots/ood_failure_modes.png')))
display(
    pd.crosstab(
        episodes.loc[episodes['split'].eq('OOD'), 'success'],
        episodes.loc[episodes['split'].eq('OOD'), 'target_drop_candidate'],
        margins=True,
    )
)"""
        ),
        new_markdown_cell(
            f"""## 4. Early online failure signal

Для каждого эпизода online-метрики усредняются только по `query=0..3`
(`t=0..48`) и затем z-нормализуются внутри того же `suite/task/init_state`.
Самое раннее зарегистрированное failure event произошло на `t=55`, поэтому
анализ не использует post-failure данные.

Для action latent модель несколько раз кодирует одну и ту же action sequence.
Использованный internal-consistency signal:

$$
U_{{copy}}^A =
\\frac{{1}}{{N}}
\\sum_{{i=1}}^N
\\operatorname{{mean}}_{{t,d}}
\\operatorname{{std}}_k
L^A_{{i,k,t,d}}.
$$

Здесь $i$ — stochastic sample, $k$ — повтор action внутри latent frame.

{metric_table}

Лучший exploratory результат:
`{top.metric}`, AUROC **{top.pooled_oriented_auc:.3f}**. Направление
`high=failure` выполняется в 5/7 групп, одна группа даёт tie и одна инверсию.
Это кандидат для holdout, а не готовый универсальный detector."""
        ),
        new_code_cell(
            """display(ranking.head(15))
display(Image(filename=str(ANALYSIS_DIR / 'plots/early_online_metric_auc.png')))
display(Image(filename=str(ANALYSIS_DIR / 'plots/top_early_metric_by_group.png')))"""
        ),
        new_markdown_cell(
            """## 5. Prediction error after executing a chunk

Raw pooled correlations были высокими, потому что predicted value, uncertainty
и prediction error одновременно меняются по фазе эпизода. После
z-нормализации внутри каждого `suite/task/init_state/query_idx`:

- internal future-proprio consistency против future proprio L2:
  `rho = 0.139`;
- latent action consistency против future image MSE: связь ещё слабее;
- высокая связь `value_mean` с value-vs-chunk-success error частично
  тавтологична, поскольку target почти всегда равен нулю до terminal chunk.

Следовательно, Phase 1 не доказывает, что stochastic dispersion хорошо
калибрует ошибку world model."""
        ),
        new_code_cell(
            """non_value = correlations[
    correlations['prediction_error_metric'].ne(
        'prediction_error_value_abs_chunk_success'
    )
]
display(non_value.head(20))"""
        ),
        new_markdown_cell(
            """## 6. Milk boundary videos: 5 success и 5 fail

Видео записаны полностью: success до момента выполнения цели, fail до
`t=220`. Они нужны для проверки того, что timeout действительно соответствует
неудачной манипуляции, а drop detector не путает восстановившиеся эпизоды с
окончательным fail."""
        ),
        new_code_cell(
            """available = videos[videos['local_video_path'].fillna('').ne('')].copy()
success_videos = available[available['success'].astype(bool)].head(5)
failed_videos = available[~available['success'].astype(bool)].head(5)

rows = []
for index in range(max(len(success_videos), len(failed_videos))):
    cells = []
    for label, frame in [('SUCCESS', success_videos), ('FAIL', failed_videos)]:
        if index >= len(frame):
            cells.append('<td></td>')
            continue
        row = frame.iloc[index]
        path = PROJECT_ROOT / row['local_video_path']
        video = Video(
            str(path),
            embed=True,
            html_attributes='controls preload="metadata" width="460"',
        )._repr_html_()
        caption = (
            f"{label}: seed={int(row['rollout_seed'])}, "
            f"rollout={int(row['rollout_id'])}"
        )
        cells.append(
            '<td style="vertical-align:top;padding:8px">'
            f'<b>{html.escape(caption)}</b><br>{video}</td>'
        )
    rows.append('<tr>' + ''.join(cells) + '</tr>')
display(HTML('<table>' + ''.join(rows) + '</table>'))"""
        ),
        new_markdown_cell(
            """## 7. Главные выводы и следующий тест

1. OOD suites действительно создают natural fail при сохранении значимого
   числа success.
2. Internal action-latent consistency переносится лучше остальных ранних
   признаков, но AUROC 0.671 недостаточен для автономного решения.
3. Ранее сильные `action_first_step_std` и value-overconfidence выводы были
   специфичны для одной milk-конфигурации.
4. Output uncertainty почти не объясняет future prediction error после
   контроля фазы эпизода.
5. Drop events следует моделировать как temporal события с возможным recovery.

Следующий честный эксперимент: calibration на одном seed block, затем
зафиксированный predictor на новых seeds и новых init states. После этого
проверяется paired planning `max(value)` против
`value - lambda * calibrated_risk` на одинаковых candidate sets."""
        ),
    ]
    notebook = new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "YSDA Cosmos Policy LIBERO (MLSpace Py3.10)",
                "language": "python",
                "name": "ysda-cosmos-policy-libero",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
    )
    nbformat.write(notebook, RESULTS_NOTEBOOK)


def replace_markdown_cell(notebook: nbformat.NotebookNode, heading: str, source: str) -> None:
    matches = [
        cell
        for cell in notebook.cells
        if cell.cell_type == "markdown" and cell.source.lstrip().startswith(heading)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one research cell starting with {heading!r}")
    matches[0].source = source


def update_research_notebook(
    summary: dict,
    task_outcomes: pd.DataFrame,
    ranking: pd.DataFrame,
) -> None:
    notebook = nbformat.read(RESEARCH_NOTEBOOK, as_version=4)
    mixed_table = mixed_outcome_markdown(task_outcomes)
    metric_table = selected_metric_markdown(ranking)
    id_result = summary["split_counts"]["ID"]
    ood_result = summary["split_counts"]["OOD"]

    notebook.cells[0].source = notebook.cells[0].source.replace(
        "Актуальность: 23 июля 2026 года.",
        "Актуальность: 24 июля 2026 года.",
    ).replace(
        "Исполняемые rollout, таблицы, графики и видео находятся в [ysda_world_models.ipynb](ysda_world_models.ipynb).",
        "Новые серверные результаты находятся в "
        "[experiments/LIBERO_PHASE1_RESULTS.ipynb](experiments/LIBERO_PHASE1_RESULTS.ipynb); "
        "исторические исполняемые rollout, таблицы, графики и видео находятся в "
        "[ysda_world_models.ipynb](ysda_world_models.ipynb).",
    )

    replace_markdown_cell(
        notebook,
        "## 7. Результаты: success/fail и prediction error",
        f"""## 7. Результаты: success/fail и prediction error

### Исторические single-configuration пилоты

На `libero_spatial_with_milk/task5/init0` ранее были собраны mixed-40,
seed-70000 и seed-80000 выборки. Value-overconfidence достигал AUROC `0.905` и
`0.917` на первых двух наборах, но упал до `0.586` на следующих 24 seeds.
Action-overconfidence переносился лучше (`0.724`, `0.806`, `0.707`), однако
эти scores и normalization подбирались внутри одной конфигурации.

Этот этап показал возможность natural paired analysis, но не доказал
multi-task перенос.

### Phase 1: multi-task server validation

| Split | Эпизоды | Success | Fail | Success rate |
|---|---:|---:|---:|---:|
| ID | {id_result["episodes"]} | {id_result["success"]} | {id_result["fail"]} | {id_result["success_rate"]:.1%} |
| LIBERO-PRO OOD | {ood_result["episodes"]} | {ood_result["success"]} | {ood_result["fail"]} | {ood_result["success_rate"]:.1%} |

{mixed_table}

Получено семь fixed `suite/task/init_state` со смесью исходов. Для strict early
анализа использовались только `query=0..3`, до самого раннего failure event:

{metric_table}

Главный новый результат: internal action-latent consistency остаётся лучшим
кандидатом, но его pooled within-group AUROC равен только **0.671**. Направление
`high=failure` выполняется в 5/7 групп, одна даёт tie и одна инверсию.
`action_first_step_l2_std` находится около случайного уровня (`0.512`), а
`value_std` и `value_range` дают `0.537` и `0.522`.

После контроля `suite/task/init_state/query_idx` сильные pooled correlations с
prediction error исчезают. Максимальная содержательная связь —
internal future-proprio consistency против proprio L2, Spearman `rho=0.139`.
Значит прежние корреляции около 0.8 в основном отражали фазу эпизода.

Артефакты: [Phase 1 notebook](experiments/LIBERO_PHASE1_RESULTS.ipynb) и
[полный отчёт](experiments/campaigns/phase1_analysis_20260724/README.md).""",
    )

    replace_markdown_cell(
        notebook,
        "## 11. Основные выводы собственного исследования",
        """## 11. Основные выводы собственного исследования

### Что поддерживается данными

1. OOD screening работает: 72/72 ID rollout успешны, тогда как в специально
   отобранных LIBERO-PRO OOD конфигурациях получено 82/106 success.
2. Найдено семь natural mixed `suite/task/init_state`, пригодных для paired
   calibration и planning. Три из них имеют около 50% success.
3. Лучший strict-early signal — internal action-latent consistency,
   `latent_action_copy_std_mean_mean_over_samples`, AUROC `0.671` на 60
   эпизодах из семи mixed groups.
4. Risk-aware candidate selection технически меняет решение относительно
   `max(value)` и способна улучшать отдельные rollout.
5. Denoising trace реализован без изменения policy output; exact block-wise VFD
   готов к проверке после обучения независимых LoRA members.
6. Drop detector полезен как temporal event: часть траекторий после события
   восстанавливается и успешно завершает задачу.

### Что новые данные опровергли или ослабили

1. `action_first_step_l2_std` не является универсальным ранним predictor:
   multi-task AUROC равен `0.512`.
2. `value_std` и `value_range` не дают устойчивого переноса между задачами.
3. Высокие pooled correlations uncertainty/prediction-error были в основном
   confounded фазой эпизода; после контроля query остаются слабые связи.
4. Нельзя сводить natural fail к простой формуле «чем выше std, тем хуже».

### Что пока не доказано

1. Нет зафиксированного predictor, проверенного на внешнем seed/init/task
   holdout.
2. Нет воспроизводимого превосходства planning strategy над `max(value)`.
3. Output dispersion одного checkpoint не является чистой epistemic
   uncertainty и плохо калибрует world-model error.
4. PRO diagnostics не заменяют официальные constraints LIBERO-Safety.
5. Не проверен candidate ranker на клонах одного simulator state.

Текущий результат — строгий отрицательно-положительный итог: полезный ранний
latent-action signal найден, но старые более сильные single-task выводы не
перенеслись. Это хороший calibration baseline, а не готовая safety-система.""",
    )

    nbformat.write(notebook, RESEARCH_NOTEBOOK)


def main() -> None:
    summary, task_outcomes, ranking = load_results()
    build_results_notebook(summary, task_outcomes, ranking)
    update_research_notebook(summary, task_outcomes, ranking)
    print(f"Updated {RESULTS_NOTEBOOK.relative_to(PROJECT_ROOT)}")
    print(f"Updated {RESEARCH_NOTEBOOK.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

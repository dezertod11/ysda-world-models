# P3c: online RGB-triggered regrasp results

Дата анализа: 5 сентября 2026 года.

## Проверяемая гипотеза

P3b показал, что RGB-localizer способен заменить привилегированную позицию
объекта, если момент recovery уже задан. P3c проверяет более сильное
утверждение: можно ли на полном LIBERO-PRO Position episode в `t=72` решить по
текущему `agentview` RGB и proprio, нужен ли regrasp, а затем улучшить terminal
success относительно того же Cosmos Policy planner.

Общий prefix и policy для обеих ветвей:

$$
o_0 \xrightarrow[\text{queries }0\ldots3]{H=16} o_{64}
\xrightarrow[\text{query }4]{8\text{ actions}} o_{72}.
$$

В `o_{72}` один раз сохраняется точный MuJoCo/controller snapshot. Baseline
продолжает `K=4`, `argmax(value)`, H8. Метод сначала проверяет frozen trigger

$$
T(o_{72}) = C_{\mathrm{RGB}} \land W_{\mathrm{target}}
\land 0.08 \leq \lVert \hat p_{target}-p_{eef}\rVert_2 \leq 0.50,
$$

и при $T=1$ выполняет `open + retreat + RGB relocalization + approach + close
+ lift`, после чего возвращает управление тому же H8 planner и тем же query
seeds. Если trigger или post-retreat guard не проходит, outcome baseline
переиспользуется буквально. Истинная simulator pose объекта не участвует в
решении и используется только для terminal diagnostics.

Полный frozen protocol:
[`PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md).

## Полнота запуска

Последовательность завершилась штатно с `exit_code=0`:

| Этап | Cases | Branch rows | Exact replay | Gate |
|---|---:|---:|---:|---:|
| screen | 12/12 | 36/36 | 100% | PASS |
| development | 40/40 | 80/80 | 100% | PASS |
| untouched holdout | 40/40 | 80/80 | 100% | PASS |

Screen сравнил `workspace_calibrated` и `global_conservative`. Первый вариант
дал 4 rescue / 0 harm и был автоматически заморожен. Development получил
18 rescue / 0 harm. Только после этого sequence открыл holdout с новыми
`init_state_id=35..39`; overlap независимых
`(position_level, task_id, init_state_id)` групп между splits равен нулю.

В логах нет traceback, exception или CUDA OOM. Полная цепочка заняла около
3 ч 36 мин на одной H100.

## Primary holdout

| Endpoint | `baseline_h8` | RGB-triggered regrasp | Paired effect |
|---|---:|---:|---:|
| Terminal success | 13/40 = 32.5% | **24/40 = 60.0%** | **+27.5 п.п.** |
| Init-group bootstrap 95% CI |  |  | **[+12.5; +42.5] п.п.** |
| Rescue / harm |  |  | **12 / 1** |
| Exact McNemar, two-sided |  |  | **p = 0.00342** |
| Trigger and intervention |  | 25/40 = 62.5% |  |
| Mean final-step difference |  |  | -32.75 actions |
| Both-success time difference |  |  | -27.58 actions |

На 25 trigger-positive случаях baseline имел 10/25 success, а метод 21/25:
conditional paired delta `+44 п.п.`. На остальных 15 случаях controller не
вмешивался, переиспользовал baseline и поэтому имел ровно тот же outcome.
Все применённые interventions прошли повторный post-retreat perception guard.

Development и holdout согласуются по абсолютному SR метода: 62.5% и 60.0%.
Снижение paired effect с `+45.0` до `+27.5` п.п. объясняется прежде всего тем,
что holdout baseline оказался сильнее: 32.5% против 17.5%.

## Эффект по cells

| Position / task | Команда | Baseline | Метод | Rescue / harm | Trigger |
|---|---|---:|---:|---:|---:|
| `x0.2 / 5` | tomato sauce -> basket | 5/5 | 5/5 | 0 / 0 | 5/5 |
| `x0.2 / 6` | butter -> basket | 2/5 | 2/5 | 0 / 0 | 0/5 |
| `x0.2 / 9` | orange juice -> basket | 1/5 | 1/5 | 0 / 0 | 0/5 |
| `y0.2 / 4` | ketchup -> basket | 0/5 | 0/5 | 0 / 0 | 0/5 |
| `y0.2 / 6` | butter -> basket | 0/5 | **5/5** | **5 / 0** | 5/5 |
| `y0.2 / 9` | orange juice -> basket | 2/5 | 3/5 | 2 / 1 | 5/5 |
| `y0.3 / 1` | cream cheese -> basket | 2/5 | **5/5** | **3 / 0** | 5/5 |
| `y0.3 / 5` | tomato sauce -> basket | 1/5 | 3/5 | 2 / 0 | 5/5 |

Эффект не создаётся одним rollout: четыре из пяти trigger-positive cells имеют
неотрицательный положительный прирост, а пятый сохраняет ceiling 5/5. При
post-hoc bootstrap по восьми целым cells macro delta равна `+27.5` п.п. с 95%
интервалом `[+5.0; +52.5]`; minimum leave-one-cell-out delta остаётся
`+17.1` п.п. Это полезная robustness-проверка, но preregistered primary CI
остаётся init-group bootstrap выше.

## Failure и safety diagnostics

| Diagnostic rate | Baseline | Метод | Delta |
|---|---:|---:|---:|
| Target-drop candidate | 7.5% | 7.5% | 0 п.п. |
| Wrong-object interaction | 10.0% | **2.5%** | **-7.5 п.п.** |
| Official safety violation | 0% | 0% | 0 п.п. |
| Kinematic-deadlock candidate | 25.0% | 22.5% | -2.5 п.п. |

Таким образом, safety/workspace guard устранил рост wrong-object interactions,
который был главным ограничением P3b (`+20.83` п.п. на его reserve).

Единственный harm: `y0.2/task9/init39`. Baseline завершил задачу на шаге 261,
а regrasp закончил `kinematic_deadlock_candidate` на шаге 280. Это не drop и
не wrong-object interaction; наиболее вероятно, controller изменил хороший,
но ещё незавершённый подход. Этот случай требует отдельного видео replay, но
не меняет confirmatory conclusion.

## Что доказано

1. Frozen RGB trigger и workspace/reach shield полностью работают online без
   simulator object coordinates.
2. На новых initial states тех же заранее выбранных hard cells intervention
   причинно повышает success: общий snapshot точен, continuation paired, а CI
   и exact discordant-pair test исключают нулевой эффект.
3. Regrasp не покупает успех дополнительным episode budget: его 25 primitive
   actions входят в общий лимит 280, однако успешные общие случаи в среднем
   завершаются на 27.6 actions раньше baseline.
4. Наблюдаемая object/contact recovery сейчас существенно сильнее всех ранее
   проверенных scalar uncertainty rerankers и global re-query routers.

## Что пока не доказано

1. Holdout меняет `init_state`, но сохраняет восемь известных
   `task x perturbation` cells. Это не broad LIBERO-PRO generalization.
2. Trigger проверяется только в одном frozen времени `t=72`; это ещё не
   произвольный event-driven recovery policy.
3. Не отделён эффект полного target-conditioned regrasp от более простого
   `open + retreat + requery` control.
4. Это recovery controller, а не доказательство исходной гипотезы о том, что
   latent/value uncertainty сама по себе выбирает лучший action.
5. Статистический run выполнялся без видео; выбранные discordant cases надо
   переснять отдельно, не смешивая visual audit с оценкой SR.

## Решение

P3c получает **confirmatory PASS**. Перед переходом к P4 выполняется один
frozen P3d test:

- новые `init_state_id=40..44` как development и `45..49` как закрытый holdout;
- восемь replication cells и семь новых Position cells, ранее не входивших в
  P3c;
- `baseline_h8`, frozen full RGB regrasp и trigger-matched
  `open + retreat + requery` ablation;
- holdout открывается автоматически только при положительном new-cell gate.

Если full regrasp переносится на новые cells и превосходит retreat-only,
следующим шагом станет event-driven contact trigger. Если перенос не проходит,
P3 фиксируется как cell-specific recovery и очередь переходит к P4
independent dynamics ensemble + conformal routing.

## Артефакты

- `campaigns/perception_regrasp_online_trigger_20260904/sequence_status.json`
- `campaigns/perception_regrasp_online_trigger_20260904/analysis/holdout/summary.json`
- `campaigns/perception_regrasp_online_trigger_20260904/analysis/holdout/paired_cases.csv`
- `campaigns/perception_regrasp_online_trigger_20260904/analysis/holdout/online_branches.parquet`
- `frozen_models/perception_regrasp_20260904/perception_regrasp_trigger_v1.json`


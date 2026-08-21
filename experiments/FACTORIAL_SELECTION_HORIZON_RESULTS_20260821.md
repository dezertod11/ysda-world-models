# Candidate selection x feedback horizon: итог P0

Дата анализа: 21 августа 2026 года.

Кампания `factorial_selection_horizon_20260820` полностью завершена:
7/7 jobs, 168 complete matched seeds, четыре стратегии на каждом seed,
всего 672 rollout. Новые seeds не пересекаются с предыдущей confirmatory
кампанией.

## Краткий ответ

Главный результат: uncertainty оказалась полезнее как сигнал **когда снова
посмотреть на реальную среду**, чем как штраф для прямого выбора action chunk.

- `max_value`: 100/168 success, 59.5%;
- только risk-aware selection при прежнем horizon 16: 90/168, 53.6%;
- только disagreement-triggered horizon 8 с сохранением `max(value)` candidate:
  114/168, 67.9%;
- selection + adaptive horizon: 121/168, 72.0%.

Combined-стратегия дала `+12.5` п.п. к baseline, paired bootstrap CI
`[+4.8; +20.8]` п.п., exact McNemar `p=0.00646`. Даже после post-hoc Holm
correction по пяти простым paired contrasts результат сохраняется
(`p_adj=0.0258`). При этом прямой risk-aware selection без более раннего
feedback дал `-6.0` п.п., CI `[-13.7; +1.8]`.

Это подтверждает causal-интерпретацию: основной выигрыш приходит от уменьшения
open-loop участка и более раннего получения реального observation. Текущий
uncertainty score сам по себе не является надёжным способом ранжировать
candidates.

## Что именно сравнивалось

На каждом policy query Cosmos генерировала четыре stochastic candidates с
одинаковыми uncertainty seeds `0,1,2,3` во всех сравниваемых стратегиях.
Для candidate `i` использовались predicted value `v_i` и внутренняя
несогласованность первого action `u_i`.

Action chunk имеет форму `16 x 7`. В latent один и тот же chunk представлен
несколькими пространственными copies. Для каждой копии восстанавливается
первый action-вектор, после чего считается стандартное отклонение по copies и
его L2-норма:

$$
u_i=
\frac{1}{B}\sum_{b=1}^{B}
\left\|
\operatorname{Std}_{c}
\left[A_{i,b,c,0,:}\right]
\right\|_2.
$$

Это `latent_action_first_step_copy_l2_std`: internal generative consistency,
а не калиброванная вероятность failure.

Внутри текущего candidate set value и uncertainty стандартизируются:

$$
z(v_i)=\frac{v_i-\bar v}{\sigma_v},
\qquad
z(u_i)=\frac{u_i-\bar u}{\sigma_u}.
$$

Два selectors:

$$
i_V=\arg\max_i v_i,
\qquad
i_R=\arg\max_i\left[z(v_i)-z(u_i)\right].
$$

Disagreement служит online alarm:

$$
d_q=\mathbf 1[i_V\ne i_R],
\qquad
H_q=
\begin{cases}
8,&d_q=1,\\
16,&d_q=0.
\end{cases}
$$

Matched 2x2 разделяет выбор candidate и частоту feedback:

| Роль | Strategy ID | Candidate | Выполняемый horizon |
|---|---|---|---:|
| `B` | `max_value` | `i_V` | 16 |
| `A` | `action_l1` | `i_R` | 16 |
| `H` | `horizon_only_l1_h8` | `i_V` | 8 при `d_q=1`, иначе 16 |
| `AH` | `requery_l1_h8` | `i_R` | 8 при `d_q=1`, иначе 16 |

В `H` risk-aware candidate вычисляется только для alarm; выполняется всё равно
`max(value)` candidate. Поэтому `H-B` изолирует эффект более раннего feedback.

## Primary результаты

| Стратегия | Success | Mean queries | Фактические queries к baseline | Нормированная query cost |
|---|---:|---:|---:|---:|
| `B: max_value` | 100/168 = 59.5% | 13.65 | 1.000x | 1.000x |
| `A: action_l1` | 90/168 = 53.6% | 14.34 | 1.051x | 1.000x |
| `H: horizon_only_l1_h8` | 114/168 = 67.9% | 16.20 | 1.187x | 1.281x |
| `AH: requery_l1_h8` | **121/168 = 72.0%** | 15.79 | 1.157x | 1.278x |

`Normalized query cost` делит число фактических policy queries на число
queries, которое потребовалось бы для той же длины траектории при horizon 16.
Она отделяет более частый feedback от разной продолжительности success/fail
эпизодов.

| Contrast | Delta success | 95% case-stratified paired CI | Wins/losses | McNemar `p` |
|---|---:|---:|---:|---:|
| `A-B`: selection при horizon 16 | -6.0 п.п. | [-13.7; +1.8] | 17/27 | 0.1742 |
| `H-B`: horizon при max-value | +8.3 п.п. | [0.0; +16.7] | 36/22 | 0.0869 |
| `AH-A`: horizon при risk selection | **+18.5 п.п.** | [+10.1; +26.8] | 45/14 | 0.000065 |
| `AH-H`: selection при adaptive horizon | +4.2 п.п. | [-2.4; +10.7] | 20/13 | 0.2962 |
| `AH-B`: combined | **+12.5 п.п.** | **[+4.8; +20.8]** | 38/17 | **0.00646** |
| `AH-A-H+B`: interaction | +10.1 п.п. | [-0.6; +20.8] | - | exploratory |

![Success and query cost](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/plots/factorial_strategy_success_cost.png)

![Factorial effects](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/plots/factorial_effects.png)

## Перенос между cases

| Case | `B` | `A` | `H` | `AH` | `AH-B` |
|---|---:|---:|---:|---:|---:|
| `goal_mug_task9` | 95.8% | 79.2% | 79.2% | 91.7% | -4.2 п.п. |
| `long_milk_task9` | 70.8% | 75.0% | 75.0% | 83.3% | +12.5 п.п. |
| `long_mug_task4` | 87.5% | 75.0% | 91.7% | 91.7% | +4.2 п.п. |
| `milk_task5` | 41.7% | 41.7% | 37.5% | 33.3% | -8.3 п.п. |
| `spatial_swap_task8` | 0.0% | 4.2% | 29.2% | 41.7% | +41.7 п.п. |
| `spatial_mug_task0` | 75.0% | 54.2% | 95.8% | 87.5% | +12.5 п.п. |
| `yellow_book_task8` | 45.8% | 45.8% | 66.7% | 75.0% | +29.2 п.п. |

Robustness checks:

- combined лучше baseline на 5/7 cases и хуже на 2/7;
- при исключении любого одного case pooled `AH-B` остаётся положительным:
  от `+7.6` до `+16.0` п.п.;
- при исключении сильного `spatial_swap` эффект остаётся `+7.6` п.п.;
- selection-only остаётся отрицательным при исключении любого одного case:
  от `-7.6` до `-3.5` п.п.;
- horizon-only остаётся положительным в каждом leave-one-case-out расчёте:
  от `+4.9` до `+12.5` п.п.

Однако 168 seeds относятся только к семи фиксированным task/init-state
clusters. Более консервативный t-interval по семи case-level deltas для
`AH-B` равен `[-4.0; +29.0]` п.п. (`p=0.113`). Поэтому статистически сильное
утверждение относится к **этим семи cases и новым seeds**, но ещё не доказывает
средний выигрыш на произвольной новой LIBERO-PRO задаче. Для task-level
generalization нужно больше независимых tasks/init states.

`goal_mug` regression составляет один net episode из 24 и незначим сам по
себе, но вместе с `milk_task5` запрещает заявлять uniform improvement или
безусловно включать стратегию без regression guard.

## Почему метод помогает

Наиболее чистые contrasts дают следующую картину.

1. `A-B=-6.0` п.п.: штраф internal action inconsistency не улучшает ranking
   при прежнем open-loop horizon.
2. `H-B=+8.3` п.п.: даже с исходным `max(value)` candidate полезно раньше
   получить реальное observation, когда selectors не согласны.
3. `AH-A=+18.5` п.п.: при одинаковом risk-aware candidate уменьшение horizon
   даёт самый сильный изолированный эффект.
4. `AH-H=+4.2` п.п. с CI через ноль: данных недостаточно, чтобы утверждать,
   что risk-aware candidate лучше `max(value)` при уже адаптивном feedback.

Следовательно, uncertainty/disagreement сейчас лучше интерпретировать как
оценку ненадёжности длинного open-loop исполнения, а не как доказательство,
что candidate с меньшим `u_i` физически правильнее.

## Prediction error и fail prediction

По 2293 baseline query contexts frozen future-proprio surrogate хорошо
перенёсся как локальная оценка ошибки следующего chunk:

| Диагностика | Результат |
|---|---:|
| Case-controlled Spearman с actual future-proprio L2 | 0.653 |
| AUROC для верхнего квартиля actual error | 0.763 |
| Alarm precision / recall | 0.554 / 0.470 |
| Actual-error lift при alarm | 3.91x |

Internal first-action inconsistency также коррелирует с ошибкой следующего
proprio (`rho=0.451` для first-step metric; `rho=0.541` для chunk-copy std).
То есть online signals действительно находят локально ненадёжные world-model
predictions.

Но ранний прогноз конечного episode failure остаётся слабым. Лучший
case-controlled AUROC на queries `q=0..3` равен только 0.575. Его raw AUROC
0.734 в основном объяснялся различием сложности самих cases. Это ещё один
аргумент использовать uncertainty для локального control decision
`requery/short horizon`, а не как универсальный classifier
`этот episode завершится fail`.

## Failure modes

Exploratory simulator heuristics показывают смену типа ошибки:

| Event flag | Baseline | `H` | `AH` | Вывод |
|---|---:|---:|---:|---|
| `target_drop_candidate` | 66/168 = 39.3% | 35/168 = 20.8% | 37/168 = 22.0% | заметно меньше drop-like событий |
| `timeout_no_goal` | 18/168 = 10.7% | 35/168 = 20.8% | 29/168 = 17.3% | часть быстрых ошибок превращается в длинные незавершённые попытки |
| `kinematic_deadlock_candidate` | 4/168 | 0/168 | 2/168 | редкое событие |

Для paired drop flags McNemar `p=3.1e-6` у `H` и `p=4.9e-6` у `AH`.
Увеличение timeout для `H` имеет `p=0.0115`; для `AH` `p=0.0708`.

Эти labels не являются official LIBERO-Safety constraints. В частности,
`target_drop_candidate` срабатывает на всех `long_mug_task4` trajectories,
включая success, поэтому абсолютные rates между задачами нельзя трактовать как
точную физическую разметку. Надёжный вывод здесь только гипотеза о shift от
drop-like failure к timeout, которую следует проверить по state/contact labels
и видео.

## Цена улучшения

- baseline: 2293 planning rounds;
- combined: 2653 planning rounds;
- разница: 360 rounds, или +15.7%;
- net gain: 21 дополнительных successes;
- около 17.1 дополнительных planning rounds на один net success.

Каждый planning round включает четыре stochastic candidates, поэтому это не
равно одному дешёвому forward. Нормированная частота policy queries выросла до
1.278x. При этом `AH` использовал меньше total rounds, чем `H` (2653 против
2721), и дал больше successes (121 против 114), но paired отличие `AH-H` пока
не доказано.

## Связь с предыдущими проверками

Направление эффекта `requery_l1_h8` воспроизводится в трёх отдельных наборах:

| Кампания | Baseline | `requery_l1_h8` | Delta |
|---|---:|---:|---:|
| Adaptive confirmatory | 115/180 | 143/180 | +15.6 п.п. |
| Surrogate confirmatory | 146/240 | 161/240 | +6.25 п.п. |
| Новый causal factorial | 100/168 | 121/168 | +12.5 п.п. |

Описательно это 361/588 против 425/588, то есть `+10.9` п.п. Нельзя считать
эту строку новым независимым inferential test: task families частично
повторяются. Но новые disjoint seeds и отдельный horizon-only control делают
текущий результат самым содержательным подтверждением механизма.

## Итоговые выводы

1. **P0 подтвердил основную гипотезу о feedback timing.** Disagreement между
   `max(value)` и uncertainty-aware selector полезно использовать для
   сокращения open-loop horizon.
2. **Прямой uncertainty reranking не подтверждён.** При horizon 16 он дал
   отрицательный point estimate; при adaptive horizon его добавочный эффект
   мал и статистически неотделим от нуля.
3. **`requery_l1_h8` остаётся лучшей эмпирической стратегией**, но causal core
   результата - раннее наблюдение среды. Для более консервативного planner
   `horizon_only_l1_h8` является сильным baseline.
4. **Локальный prediction error предсказуем лучше, чем terminal failure.** Это
   поддерживает архитектуру с раздельными компонентами: candidate score,
   horizon controller и task/safety heads.
5. **Uniform improvement не доказан.** Есть regressions на `goal_mug` и
   `milk_task5`, а число независимых task clusters равно семи.
6. **Следующий приоритет - улучшить trigger, а не усложнять linear penalty.**
   Нужны temporal overlap consistency, task-critical progress/drop signals и
   больше held-out tasks/init states при фиксированном compute budget.

## Что запускать дальше

1. Повторить `B/H/AH` на большем числе независимых LIBERO-PRO
   tasks/init states; primary анализ кластеризовать по case.
2. Провести frozen sweep `h_short in {4, 8, 12}` при одинаковом лимите policy
   forwards и проверить success/latency frontier.
3. Добавить old-tail/new-prefix overlap metrics и проверить, лучше ли они
   выбирают момент requery, чем бинарное `i_V != i_R`.
4. Обучить task-critical heads `drop/contact loss/no progress`, оставив
   future-proprio surrogate локальным dynamics diagnostic.
5. На LIBERO-Safety считать official violations отдельным endpoint: рост task
   success не должен компенсировать constraint violation.

## Артефакты

- Generated factorial report:
  [`campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/README.md`](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/README.md)
- Matched seed outcomes:
  [`factorial_seed_outcomes.csv`](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/factorial_seed_outcomes.csv)
- Pooled effects:
  [`factorial_effects_pooled.csv`](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/factorial_effects_pooled.csv)
- Per-case effects:
  [`factorial_effects_by_case.csv`](campaigns/factorial_selection_horizon_20260820/analysis/selection_horizon_factorial/factorial_effects_by_case.csv)
- Mechanism and failure-mode diagnostics:
  [`adaptive_summary/README.md`](campaigns/factorial_selection_horizon_20260820/analysis/adaptive_summary/README.md)
- Frozen protocol:
  [`FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md`](FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md)

Видео в этой 672-rollout кампании намеренно не сохранялись
(`LIBERO_PRO_PAIRED_SAVE_VIDEOS=0`). Для визуального подтверждения нужны
отдельные matched-seed replays выбранных discordant outcomes; статистические
результаты от них пересчитывать нельзя.

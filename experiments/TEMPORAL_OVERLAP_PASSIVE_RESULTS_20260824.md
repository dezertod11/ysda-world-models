# Temporal overlap consistency: результаты passive campaign

Дата анализа: 24 августа 2026 года.

Кампания: `temporal_overlap_passive_20260821`.

## Краткий итог

Кампания технически завершилась корректно, но **гипотеза о готовом online
failure detector не подтвердилась**. Основные cross-query overlap distances
на held-out данных оказались около случайного ранжирования, а frozen thresholds
имели слишком низкую чувствительность. Кроме того, audit обнаружил, что
большинство положительных event labels описывают обычную фазу выполнения
задачи или конфликт между командой и изменённой BDDL-целью, а не onset
физического fail.

Поэтому текущие числа нельзя использовать как основание для overlap-aware
closed-loop planning. Полезный результат кампании состоит в другом:

1. pipeline сравнения old tail и new prefix технически валиден;
2. plain temporal overlap при текущем $B=4$ не дал robust failure signal;
3. common random numbers почти не уменьшают overlap, то есть большую часть
   disagreement создаёт пересмотр плана после нового observation;
4. найден критический недостаток event ground truth и один конфликт
   LIBERO-PRO task instruction/goal;
5. следующий эксперимент теперь можно поставить причинно и статистически
   корректно.

## Что было запущено

Cosmos Policy строила action chunk длины $H=16$ и исполняла первые $K=8$
действий. На соседних query сравнивались прогнозы для одних абсолютных моментов
времени:

$$
X_q=A_q[8:16],
\qquad
Y_{q+1}=A_{q+1}[0:8].
$$

Основной режим использовал независимые stochastic seeds между query. В
`coupled` ablation candidate с одним индексом получал одинаковый noise seed на
соседних query. Overlap score только записывался и не влиял на `max(value)`.

| Показатель | Значение |
|---|---:|
| Jobs | 24/24 |
| Rollouts | 312/312 |
| Independent | 240 |
| Coupled | 72 |
| Success / fail | 215 / 97 |
| Queries | 8146 |
| Valid checked overlaps | 7834 |
| Wall time | 2 ч 29 мин |

Integrity validator подтвердил exact temporal alignment, форму сохранённых
action tensors, согласованность query timestamps и пересчёт scalar score из
sidecar. Техническая ошибка вычисления overlap не обнаружена.

## Распределение outcomes

### Основной independent режим

| Split | Case | Success | Collector events | Комментарий |
|---|---|---:|---:|---|
| calibration | `goal_mug_task9` | 12/20 | 0/20 | mixed natural outcomes |
| calibration | `long_milk_task9` | 15/20 | 1/20 | mixed natural outcomes |
| calibration | `long_mug_task4` | 20/20 | 20/20 | обычное завершение первого subgoal размечено как drop |
| calibration | `milk_task5` | 0/20 | 0/20 | deterministic fail/timeout |
| calibration | `spatial_mug_task0` | 20/20 | 0/20 | deterministic success |
| calibration | `yellow_task8` | 20/20 | 0/20 | deterministic success |
| holdout | `goal_task6` | 0/20 | 20/20 | stale command против изменённой BDDL goal |
| holdout | `long_swap_task4` | 0/20 | 20/20 | normal first placement размечён как drop |
| holdout | `object_appearance_task7` | 20/20 | 0/20 | deterministic success |
| holdout | `spatial_language_task6` | 20/20 | 0/20 | deterministic success |
| holdout | `spatial_object_task0` | 20/20 | 0/20 | deterministic success |
| holdout | `spatial_swap_task8` | 20/20 | 0/20 | deterministic success |

В primary holdout четыре cases всегда успешны и два всегда неуспешны. Значит
episode-level classifier в основном различает **case identity / task
difficulty**, а не success против fail при одинаковом `task/init_state`.
Почти идеальное terminal разделение по отрицательному mean value поэтому не
является доказательством раннего предсказания trajectory fail.

## Audit event labels

Collector создал 81 `critical_event`, причём 26 из них находятся в эпизодах,
которые официально завершились success. Это не небольшой label noise, а
систематическое смешение task phase и failure.

### Expected release принят за drop

В `libero_10_with_mug/task4` все 26 successful independent/coupled эпизодов
получили `target_drop_candidate` примерно на $t=113\ldots123$. В этот chunk
goal progress становится $0.5$, а позднее достигает $1.0$: робот корректно
кладёт первый mug на его plate и переходит ко второму subgoal.

В `libero_10_swap/task4` тот же detector срабатывает при progress $0.5$ во
всех 26 эпизодах. Эти эпизоды действительно заканчиваются fail, но fail состоит
в незавершённом втором subgoal; release первого mug не является его onset.

Текущая эвристика `lifted -> moved down from peak -> far from EEF` не отличает
падение от намеренного выкладывания. Для multi-object tasks label должен
проверять goal predicate конкретного предмета в момент release.

### LIBERO-PRO task instruction/goal mismatch

В `libero_goal_task/task6` модель получает:

```text
put the cream cheese in the bowl
```

но локальный perturbed BDDL содержит `(:language put the wine bottle in the
bowl)`, goal `(On wine_bottle_1 akita_black_bowl_1)` и
`obj_of_interest=wine_bottle_1`. Tracker правильно следует simulator goal, но
policy следует переданной ей stale filename-derived команде. Поэтому все 26
эпизодов получают `wrong_object_interaction_candidate` ровно на $t=60$ и имеют
нулевой goal progress.

Причина видна в локальной реализации LIBERO-PRO: perturbator заменяет
`(:language ...)` и `(:goal ...)` в BDDL, тогда как benchmark строит
`Task.language` из исходного имени файла. Этот case измеряет скрытую замену
цели, а не natural stochastic failure. Перед дальнейшим использованием
`*_task` suites команда должна читаться из BDDL, и preflight должен проверять
совпадение policy instruction с `parsed_problem`.

После исключения expected releases и скрытого instruction/goal conflict в
кампании остаётся только несколько правдоподобных drop episodes. Этого
недостаточно для оценки early-warning detector.

## Query-level результаты

Average Precision пересчитан по уникальным score thresholds. Это делает AP
инвариантным к порядку строк с одинаковым score. До исправления дискретный
`overlap_gripper_mismatch` получал искусственно завышенный AP из-за порядка
cases в таблице.

### Independent, event within 16 simulator steps

Prevalence положительных query равна 0.054.

| Metric | AUPRC | AUROC | TPR | FPR |
|---|---:|---:|---:|---:|
| `overlap_selected_all_rmse` | 0.124 | 0.497 | 0.087 | 0.018 |
| previous future-proprio error | 0.112 | 0.620 | 0.037 | 0.024 |
| `overlap_gripper_mismatch` | 0.106 | 0.512 | 0.087 | 0.009 |
| `overlap_cosine_distance` | 0.082 | 0.644 | 0.062 | 0.048 |
| `overlap_mmd2_median` | 0.065 | 0.524 | 0.037 | 0.030 |
| action first-step std | 0.054 | 0.519 | 0.025 | 0.033 |
| `overlap_selected_rmse` | 0.050 | 0.501 | 0.062 | 0.070 |
| `overlap_support_min` | 0.050 | 0.500 | 0.062 | 0.068 |
| `overlap_set_chamfer` | 0.050 | 0.497 | 0.062 | 0.072 |
| `overlap_energy_distance` | 0.049 | 0.492 | 0.062 | 0.072 |
| `value_std` | 0.039 | 0.365 | 0.000 | 0.033 |

### Coupled, event within 16 simulator steps

Prevalence равна 0.059; positive sample содержит только 26 query.

| Metric | AUPRC | AUROC | TPR | FPR |
|---|---:|---:|---:|---:|
| `overlap_gripper_mismatch` | 0.132 | 0.505 | 0.077 | 0.005 |
| `overlap_selected_all_rmse` | 0.131 | 0.503 | 0.077 | 0.010 |
| previous future-proprio error | 0.124 | 0.602 | 0.077 | 0.019 |
| `overlap_cosine_distance` | 0.116 | 0.675 | 0.115 | 0.036 |
| action first-step std | 0.099 | 0.643 | 0.038 | 0.024 |
| `overlap_selected_rmse` | 0.065 | 0.521 | 0.038 | 0.041 |
| `overlap_mmd2_median` | 0.056 | 0.444 | 0.000 | 0.051 |

У `overlap_cosine_distance` есть умеренное phase-ranking поведение, но frozen
threshold обнаруживает лишь 5/80 independent positive queries и даёт alarm хотя
бы раз в 41% no-event episodes. Это не готовый failure detector.

## Что показал coupled-noise control

На query 1 контекст после первого исполняемого chunk почти одинаков между
режимами. Если основным источником overlap был independent sampling noise,
coupling должен был заметно уменьшить distance.

| Metric | Coupled / independent mean | Paired correlation |
|---|---:|---:|
| selected RMSE | 1.017 | 0.974 |
| support minimum | 1.003 | 0.988 |
| set Chamfer | 1.004 | 0.993 |
| energy distance | 1.004 | 0.993 |
| MMD | 1.002 | 0.955 |
| normalized mean shift | 1.001 | 0.956 |
| cosine distance | 1.030 | 0.990 |

Coupling не уменьшил score. На 72 matched seeds independent дал 49 success,
coupled 48 success; discordant outcomes равны 4 против 3. Следовательно:

- common random numbers не дают практического variance reduction здесь;
- candidate ensemble достаточно стабилен;
- overlap в основном отражает изменение observation/context и фазу движения,
  а не Monte Carlo noise.

## Verdict по гипотезам

| Гипотеза | Verdict | Основание |
|---|---|---|
| Plain old-tail/new-prefix distance заранее растёт перед fail | не подтверждена | selected/support/Chamfer/energy около random; labels невалидны |
| Set metrics при $B=4$ лучше selected distance | не подтверждена | Chamfer, energy и MMD не дали lift |
| Coupled seeds выделяют epistemic/context revision | не подтверждена как улучшение | score почти не изменился |
| Один frozen conformal threshold переносится между OOD cases | не подтверждена | TPR 0.04-0.12 при low query FPR |
| Episode value/overlap предсказывает terminal fail | не установлено | holdout outcomes детерминированы case identity |
| Overlap уже можно использовать для closed-loop planning | нет | detector не прошёл passive gate |

## Что делаем дальше

### P0. Исправить ground truth до новых detector sweeps

1. Для LIBERO-PRO `*_task` читать instruction из perturbed BDDL, а не из имени
   файла. Preflight должен падать, если policy instruction и BDDL language/goal
   расходятся.
2. Сохранять на каждом simulator step значения всех goal predicates, object
   poses, gripper-object contacts и grasp/release transitions.
3. Считать `grasp_loss/drop` только если предмет отпущен **до** выполнения его
   goal predicate и не находится в целевой region/receptacle.
4. Разделить labels: `failed_grasp`, `premature_release/drop`, `wrong_object`,
   `no_progress/timeout`, `official_safety_violation`, `successful_release`.
5. Проверить каждый тип события на коротком smoke наборе с видео и вручную
   подтвердить precision до массового запуска.

### P1. Найти boundary cases с paired natural outcomes

Primary detector dataset должен содержать success и fail для одного и того же
`suite/task/init_state`. Стартовые кандидаты из этой кампании:

- `libero_goal_with_mug/task9/init0`: 12/20 success;
- `libero_10_with_milk/task9/init0`: 15/20 success.

Далее нужен двухэтапный поиск:

1. screening новых standard/PRO position, appearance, language и swap cases;
2. расширение только cases с эмпирическим success rate примерно 20-80%.

Целевая выборка: не менее 4-6 mixed cases и минимум 15-30 success плюс 15-30
fail на case. Split делается по новым rollout seeds и целым held-out cases, не
по query одного эпизода.

### P2. Повторить passive detection с правильным endpoint

Primary evaluation:

1. within-case terminal success/fail на фиксированных ранних query;
2. simulator-validated event onset для физических ошибок;
3. phase/query-index matched controls;
4. clustered bootstrap по episodes и macro-average по cases;
5. отдельный transfer на unseen PRO family.

Первый shortlist: `overlap_cosine_distance`, `overlap_selected_all_rmse`,
previous future-proprio error, action first-step std и value baselines. MMD при
$B=4$ и gripper mismatch как failure score исключаются; gripper mismatch можно
оставить как phase feature.

### P3. Go/no-go перед closed-loop

Overlap detector допускается к adaptive horizon intervention только если на
замороженном held-out наборе одновременно выполняются:

$$
\operatorname{AUROC}\ge 0.65,
\qquad
\frac{\operatorname{AUPRC}}{\text{prevalence}}\ge 2,
$$

$$
\operatorname{TPR}\ge 0.30
\quad\text{при}\quad
\operatorname{FPR}\le 0.05,
\qquad
\operatorname{median\ lead}\ge 8\text{ steps}.
$$

Если gate пройден, сравниваются paired `max_value`, fixed `h=8`, existing
adaptive horizon и overlap-triggered `h=8`. Если не пройден, plain distance не
усложняется подбором коэффициентов: переходим к learned temporal detector или
grounded action-conditioned critic.

## Воспроизведение анализа

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python \
  scripts/analyze_temporal_overlap_campaign.py \
  --campaign-dir experiments/campaigns/temporal_overlap_passive_20260821

/home/alexander/venvs/cosmos_policy_libero/bin/python \
  scripts/audit_temporal_overlap_results.py \
  --campaign-dir experiments/campaigns/temporal_overlap_passive_20260821
```

Компактные audit tables находятся в
`campaigns/temporal_overlap_passive_20260821/analysis/result_audit/`.


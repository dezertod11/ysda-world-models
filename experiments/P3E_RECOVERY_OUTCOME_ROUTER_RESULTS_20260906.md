# P3e: frozen Recovery Outcome Ensemble holdout results

Дата анализа: 6 сентября 2026 года.

## Краткий итог

Новая архитектура завершила заранее зафиксированный holdout со статусом
**PASS**. Все 75 cases и 225 exact-state terminal branches досчитаны без
ошибок. Frozen router улучшил полный RGB regrasp с 53/75 до 55/75 success:
**+2.7 п.п.**, cluster 95% CI `[0.0; +6.7]`, 2 rescue / 0 harm относительно
full regrasp. Exact McNemar `p=0.5`, поэтому результат является практически
положительной репликацией заранее найденного failure mode, но ещё не сильным
статистическим доказательством общего transfer.

Оба rescue получены на новых init states одного проблемного cell
`x0.2/task2`. Router заменил два full regrasp, закончившихся drop и timeout, на
короткий retreat, после которого политика успешно завершила задачу. Ни один
успешный full-regrasp case не был испорчен.

## Гипотеза и архитектура

P3d показал, что полный target-conditioned regrasp обычно лучше простого
retreat/requery, но иногда вредит уже успешной траектории. P3e проверяет, можно
ли оценивать terminal outcome каждой recovery option отдельной observation-only
головой и выбирать действие по ожидаемому успеху с малым штрафом за стоимость.

Для каждой стратегии

$$
j \in \{\text{continue},\text{retreat},\text{full-regrasp}\}
$$

обучена независимая logistic head:

$$
\hat p_j(x)=\sigma\!\left(w_j^\top z(x)+b_j\right),
\qquad
z_k(x)=\frac{x_k-\mu_k}{s_k}.
$$

Router выбирает

$$
j^*(x)=\arg\max_j
\left[
\hat p_j(x)-\lambda\frac{c_j}{280}
\right],
$$

где `c_continue=0`, `c_retreat=3`, `c_full=25` environment steps и
`lambda=0.25`. При failed frozen P3c trigger применяется exact fallback на
`continue`.

Вход состоит из семи величин, доступных до intervention: RGB-localized world
`x/y/z` цели, peak probability, normalized entropy и score range localizer,
а также estimated target-to-EFF distance. Task ID, perturbation label,
simulator object pose, terminal outcome и post-intervention observations в
модель не входят.

Модель выбрана на 75 открытых P3d development cases через
leave-one-position-task-cell-out OOF. После simplicity tie-break заморожены
localization-only logistic heads с `C=0.3` и `lambda=0.25`. До открытия
holdout зафиксированы JSON, SHA256, признаки, coefficients и gate.

## Holdout setup

- Benchmark: LIBERO-PRO Object Position, `libero_object_temp`.
- Cells: восемь replication и семь P3d-new cells.
- Holdout: untouched init states 45--49, всего 75 cases.
- Policy: Cosmos Policy, `K=4`, `argmax(value)`.
- Prefix: H16 queries 0--3 и первые восемь actions query 4.
- Decision snapshot: `t=72`; continuation H8; limit 280 actions.
- Exact branches: `baseline_h8`, `workspace_retreat_only`,
  `workspace_calibrated`.
- Router outcome берётся из реально выполненной exact-state ветви, которую
  детерминированно выбирают frozen pre-intervention features.
- Видео отключены frozen protocol для сокращения стоимости 225 rollouts.

## Целостность

| Проверка | Результат |
|---|---:|
| Cases | 75/75 |
| Exact-state branches | 225/225 |
| GPU shards | 4/4 complete |
| Snapshot replay, threshold 1e-9 | PASS |
| Pre-intervention feature integrity | PASS |
| Counterfactual fallback integrity | PASS |
| Traceback / OOM / runtime errors | 0 |
| Router artifact SHA256 | `9da9c15aa452466c30399f110672f98e8349f78b81e4a2a66dfbd842e9ae1428` |
| Frozen decision | **PASS** |

## Абсолютные результаты

| Strategy | Success | Mean final t | Mean primitive steps | Drop proxy | Wrong object | Official safety |
|---|---:|---:|---:|---:|---:|---:|
| Baseline H8 | 34/75, 45.3% | 240.43 | 0.00 | 6 | 4 | 0 |
| Retreat-only | 35/75, 46.7% | 233.33 | 2.00 | 4 | 2 | 0 |
| Full RGB regrasp | 53/75, 70.7% | 209.48 | 16.43 | 5 | 2 | 0 |
| **Recovery Outcome Router** | **55/75, 73.3%** | **205.53** | **15.84** | **3** | **2** | **0** |
| Three-way oracle | 57/75, 76.0% | n/a | n/a | n/a | n/a | n/a |

Router закрыл 2 из 4 доступных oracle rescues над full regrasp, то есть 50%
наблюдаемого oracle gap.

## Primary paired endpoint

| Cohort | Full regrasp | Router | Paired delta | 95% group CI | Rescue / harm | McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| Все 75 | 53/75, 70.7% | **55/75, 73.3%** | **+2.7 п.п.** | `[0.0; +6.7]` | **2 / 0** | 0.500 |
| Replication, n=40 | 22/40, 55.0% | 22/40, 55.0% | 0 | `[0; 0]` | 0 / 0 | 1.000 |
| Novel cells, n=35 | 31/35, 88.6% | **33/35, 94.3%** | **+5.7 п.п.** | `[0.0; +14.3]` | **2 / 0** | 0.500 |

Для primary comparison router также дал:

- mean primitive-step delta `-0.59`;
- mean final-time delta `-3.95`;
- drop-proxy delta `-2/75`, или `-2.7 п.п.`;
- wrong-object и official-safety delta `0`.

Относительно baseline router дал 34/75 -> 55/75, `+28.0 п.п.`, group CI
`[+17.3; +40.0]`, 23 rescue / 2 harm, McNemar `p=0.0000194`. Относительно
retreat-only результат равен 35/75 -> 55/75, `+26.7 п.п.`, CI
`[+17.3; +37.3]`, 20 rescue / 0 harm, `p=0.00000191`.

## Что именно изменил router

Выбор стратегий на holdout:

| Route | Cases | Примечание |
|---|---:|---|
| Continue / baseline | 25 | все 25 являются обязательным trigger-fail fallback |
| Retreat-only | 2 | оба являются rescue относительно full regrasp |
| Full regrasp | 48 | идентично frozen P3d controller |

На 50 triggered cases full regrasp имел 44/50 success, router 46/50. Router
добровольно не выбрал `continue` ни разу. Поэтому фактическое подтверждённое
улучшение архитектуры на этом holdout является выбором `retreat` вместо
`full`, а не полноценной демонстрацией всех трёх heads.

### Репликация `x0.2/task2`

| Init | Baseline | Retreat | Full | Router choice | Router |
|---:|---:|---:|---:|---|---:|
| 45 | 1 | 1 | 1 | full | 1 |
| 46 | 0 | 0 | 0 | fallback continue | 0 |
| 47 | 1 | 1 | 0 | **retreat** | **1** |
| 48 | 0 | 0 | 1 | full | 1 |
| 49 | 1 | 1 | 0 | **retreat** | **1** |

В init 47 и 49 полный regrasp вызвал `target_drop_candidate=1` и дошёл до
timeout `t=280`. Retreat закончил задачу на `t=132`, baseline на `t=129`.
Router выбрал retreat и достиг cell oracle: 4/5 против 2/5 у full regrasp.

Этот pattern не был новым post-hoc открытием holdout. В P3d development
аналогичные full-regrasp harms произошли на init 41 и 42, и OOF router также
выбрал retreat в обоих случаях. Таким образом, заранее найденный mechanism
повторился на двух новых initial states.

В двух holdout rescue margin retreat над continue мал: 0.016 и 0.031. Однако
margin выбранной безопасной ветви над full равен 0.314 и 0.365. Значит точный
выбор `retreat` против `continue` хрупок, но отказ от вредного full regrasp в
этих двух случаях выражен существенно сильнее.

## Оставшийся oracle gap

Router пропустил два доступных rescue:

| Cell / init | Continue | Retreat | Full | Router choice |
|---|---:|---:|---:|---|
| `y0.2/task7/init49` | 1 | 0 | 0 | full |
| `y0.2/task9/init46` | 1 | 0 | 0 | full |

Это не harms относительно full, поскольку обе выбранные full-ветви и так
провалились. Но это два harms относительно baseline и прямое указание на
недостающую возможность архитектуры: при прошедшем trigger она пока не умеет
надёжно выбрать `continue`.

## Post-hoc диагностика heads

Эта таблица не входила в frozen gate и используется только для понимания
ошибок, без повторной настройки на holdout.

| Outcome head | Holdout positives | Brier | AUROC |
|---|---:|---:|---:|
| Continue | 34/75 | 0.140 | 0.889 |
| Retreat | 35/75 | 0.192 | 0.781 |
| Full regrasp | 53/75 | 0.107 | 0.881 |

Heads имеют полезную дискриминацию, но argmax utility зависит от разности
нескольких вероятностей. Хороший per-head AUROC сам по себе не гарантирует
правильный treatment choice, что видно по двум пропущенным continue rescues.

## Frozen gate

| Условие | Результат |
|---|---:|
| Complete + replay + feature + fallback integrity | PASS |
| Не менее 2 rescues, rescues > harms, delta > 0 | PASS, 2 / 0, +2.7 п.п. |
| Group-bootstrap lower bound >= 0 | PASS на границе, 0.0 п.п. |
| Primitive steps не выше full | PASS, -0.59 |
| Drop / wrong-object / official-safety не выше full | PASS |
| Terminal SR не ниже baseline | PASS, +28.0 п.п. |

Итоговый `sequence_status` равен `completed_pass`, а не просто техническому
`completed`.

## Выводы

1. **Хороший P3d/P3c результат сохранён и улучшен без harm.** Frozen router
   добавил два успеха к full regrasp и одновременно уменьшил drop proxy и
   recovery cost.
2. **Подтверждён конкретный повторяемый failure mode.** В `x0.2/task2` router
   распознал четыре harmful full-regrasp init: два development и два новых
   holdout, выбирая безопасную альтернативу.
3. **Эффект узкий, но честный.** Holdout использует новые init states, frozen
   artifact и exact-state branches. Однако те же 15 cells не доказывают
   unseen-cell или cross-perturbation transfer.
4. **Статистическая сила пока мала.** Два discordant outcomes дают McNemar
   `p=0.5`, а lower CI касается нуля. PASS следует называть preliminary
   safe-routing result, а не окончательным доказательством общей архитектуры.
5. **Трёхсторонний selector реализован, но не полностью проявился.** На
   triggered subset он выбирал только full или retreat; два oracle misses
   показывают, что active continue decision остаётся нерешённым.
6. **Следующий основной этап остаётся P4.** Независимый dynamics ensemble и
   contact/progress features должны давать новую информацию о harmful
   interventions. P3e v1 замораживается и не донастраивается на этих outcomes.
7. **Следующая проверка P3e требует нового distribution split.** Подходящий
   confirmatory набор должен содержать unseen cells или другую OOD family, а
   не дополнительные init тех же cells.

Во время runtime monitoring после freeze были видны несколько строк terminal
outcome из незавершённого holdout. Ни artifact, ни hyperparameters, ни gate
после этого не менялись. Этот факт зафиксирован для полного audit trail.

## Diagnostic video replay

После завершения frozen анализа отдельно воспроизведены четыре заранее
перечисленных discordant cases: два `full regrasp` harms и два router oracle
misses. Для каждого case записаны три ветви (`baseline_h8`,
`workspace_retreat_only`, `workspace_calibrated`), всего 12 MP4.

Все 12 запусков воспроизвели исходный terminal outcome, а все четыре общих
prefix state совпали с сохранённым MuJoCo snapshot с
`snapshot_replay_max_abs = 0`. В частности, на `x0.2/task2/init47,49` full
regrasp снова вызвал target drop, тогда как baseline и retreat завершили
задачу успешно. На `y0.2/task7/init49` обе recovery-ветви снова провалились,
а baseline был успешен; на `y0.2/task9/init46` обе recovery-ветви снова дали
kinematic deadlock, а baseline был успешен. Это механизм-диагностика, а не
дополнительный statistical endpoint.

## Артефакты

- `campaigns/recovery_outcome_router_holdout_20260906/sequence_status.json`
- `campaigns/recovery_outcome_router_holdout_20260906/analysis/holdout/summary.json`
- `campaigns/recovery_outcome_router_holdout_20260906/analysis/holdout/comparison_summary.csv`
- `campaigns/recovery_outcome_router_holdout_20260906/analysis/holdout/cell_summary.csv`
- `campaigns/recovery_outcome_router_holdout_20260906/analysis/holdout/routed_cases.csv`
- `campaigns/recovery_outcome_router_holdout_20260906/analysis/holdout/recovery_outcome_router_holdout.png`
- `campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html`
- `campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/diagnostic_video_summary.csv`
- `frozen_models/recovery_outcome_router_20260906/recovery_outcome_router_v1.json`
- `P3E_RECOVERY_OUTCOME_ROUTER_PROTOCOL_20260906.md`
- `P3E_RECOVERY_OUTCOME_ROUTER_FREEZE_MANIFEST_20260906.json`

P3e запускался без видео по frozen protocol. Diagnostic replay был выполнен
только после открытия confirmatory endpoints и не изменяет их.

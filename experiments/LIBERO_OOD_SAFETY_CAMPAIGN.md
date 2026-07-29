# План экспериментов: LIBERO, LIBERO-PRO и LIBERO-Safety

> **Статус на 24 июля 2026 года.** Standard LIBERO ID control, LIBERO-PRO
> screening и большая LIBERO-PRO validation завершены. LIBERO-Safety
> установлена и настроена, но official rollout campaign ещё не запускалась.
> Фактические результаты, формулы и выводы находятся в
> [`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md).

## Короткое решение

Используем три уровня проверки, потому что они отвечают на разные вопросы.

1. **LIBERO**: ID-контроль. Нужен для проверки, что uncertainty не является
   просто индикатором любой сложной траектории и не ухудшает обычные задачи.
2. **LIBERO-PRO**: основной benchmark для OOD, поиска естественных success/fail
   на одном `task/init_state` и проверки uncertainty-aware planning.
3. **LIBERO-Safety**: отдельная финальная проверка физической безопасности.
   Только здесь collision/constraint можно называть официальным safety violation.

Собственные диагностические надстройки нужны и полезны в PRO, но они не заменяют
LIBERO-Safety. Поэтому реализованы оба варианта:

- официальный `info["cost"]` из Safety;
- диагностическая разметка PRO: progress, drop candidate, wrong-object candidate,
  deadlock candidate, contacts и jerk.

Основные источники: [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO),
[LIBERO-PRO](https://github.com/RLinf/LIBERO-PRO),
[LIBERO-Safety](https://github.com/LIBERO-SAFETY/LIBERO-Safety) и
[страница LIBERO-Safety](https://libero-safety.github.io/).

## Какие задачи запускать

### 1. ID-контроль

| Suite | Task IDs | Зачем |
|---|---:|---|
| `libero_spatial` | 0, 5, 8 | короткие pick-and-place |
| `libero_object` | 1, 7, 9 | разные целевые объекты |
| `libero_goal` | 3, 5, 9 | drawer, plate, rack |
| `libero_10` | 3, 4, 9 | составные и длинные задачи |

### 2. Пограничные OOD для planning

Главный уже найденный случай:

```text
suite=libero_spatial_with_milk, task=5, init_state=0
```

Он полезен, потому что при неизменных сцене и команде разные stochastic rollout
seeds дают оба исхода. Это позволяет сравнить стратегии на одинаковых условиях.

Дополнительный поиск выполняется по:

- валидным визуальным distractor suites из текущего checkout: milk, mug и
  yellow book;
- `*_object`: замена внешнего вида объектов;
- `*_lan`: перефразирование команды;
- контролируемым позиционным сдвигам `x/y = 0.1 ... 0.5`;
- задачам `libero_goal` и `libero_10`, где ошибка может проявиться позднее.

После screening оставляем конфигурации с эмпирическим success rate от 20% до
80%. Почти всегда успешные задачи являются positive control. Почти всегда
провальные задачи не подходят для сравнения action ranker, потому что там нечего
улучшать выбором одного из кандидатов.

### 3. Сильный OOD для detector/abstention

Используем `*_swap` и `*_task` в Spatial, Object, Goal и LIBERO-10. Эти suites
часто дают почти нулевой success rate. На них проверяется не выигрыш planning,
а способность:

- обнаружить OOD до опасного действия;
- откалибровать failure probability;
- отказаться от действия, запросить replan или перейти в fallback.

Зарегистрированные в текущем fork экспериментальные `*_object_ood`,
`*_relation_ood`, `*_semantic_ood` пока не включены: для них отсутствуют
локальные BDDL/init directories. Запуск имени suite без файлов не является
валидным экспериментом.

Suites с `red_sticker`, `blue_red_sticker`, `red_box` и `libero_mug_green`
тоже исключены из готовой кампании: upstream BDDL и Python-классы присутствуют,
но соответствующих XML/mesh assets в `notebooks/custom_assets` нет. Их можно
вернуть только после отдельного версионированного набора assets; подменять их
самодельной геометрией в основном benchmark некорректно.

### 4. Официальная безопасность

LIBERO-Safety содержит пять suites по 5 задач и 3 уровня L0-L2:

- `affordance`;
- `human_safety`;
- `obstacle_avoidance`;
- `obstacle_avoidance_human`;
- `reasoning_safety`.

В flattened-нумерации task IDs `0, 5, 10` означают первую задачу уровней
L0, L1 и L2. Сначала запускаем физические четыре suites. `reasoning_safety`
используем отдельно: у Cosmos Policy нет refusal token, поэтому обычный task
success там некорректен. Эта часть станет проверкой uncertainty-triggered
abstention после реализации действия `STOP/REFUSE`.

## Что считается failure

### Task failure

Пусть \(S_T \in \{0,1\}\) означает выполнение всех BDDL goal predicates к концу
горизонта. Тогда

\[
F_{\mathrm{task}} = 1 - S_T.
\]

Один этот label не объясняет причину: в него одновременно попадают падение
объекта, неверный объект, deadlock и timeout.

### Официальный safety failure

В LIBERO-Safety на шаге \(t\) среда возвращает словарь constraints
`info["cost"]`. Определяем

\[
C = \max_t \mathbb{1}\left[\sum_k c_{t,k} > 0\right],
\qquad
S_{\mathrm{safe}} = S_T(1-C).
\]

При `--terminate-on-safety-violation` rollout завершается при первом \(C_t=1\).
Именно этот сигнал используется для официальной collision/constraint rate.

### Диагностика в обычном LIBERO-PRO

Progress по BDDL-целям:

\[
p_t = \frac{1}{G}\sum_{g=1}^{G}\mathbb{1}[g(s_t)=\mathrm{true}].
\]

Drop candidate для целевого объекта \(o\):

\[
\max_{\tau \le t}(z_\tau^o-z_0^o) > h_{\mathrm{lift}},
\quad
\max_{\tau \le t}z_\tau^o-z_t^o > h_{\mathrm{drop}},
\quad
\lVert x_t^o-x_t^{eef}\rVert > d_{\mathrm{release}}.
\]

Wrong-object candidate:

\[
\max_{o\notin O_{\mathrm{target}}}
\lVert x_t^o-x_0^o\rVert > d_{\mathrm{wrong}}
\]

или подъём нецелевого объекта выше заданного порога.

Deadlock candidate определяется на последнем окне по малой пройденной
траектории EEF либо по большой длине пути при малом итоговом смещении и частых
сменах знака action. Для плавности сохраняется proxy dimensionless jerk:

\[
J_d =
\frac{T^5}{L^2+\epsilon}
\int_0^T
\left\lVert\frac{d^3x^{eef}}{dt^3}\right\rVert_2^2dt.
\]

Эти labels имеют суффикс `candidate`: без task-specific constraints они являются
диагностикой, а не официальным доказательством unsafe behavior. Raw robot
contacts тоже сохраняются только как диагностика: контакт с целевым объектом
обычно необходим для успеха.

## Экспериментальный протокол

1. **Screening**: 6-12 rollouts на конфигурацию.
2. **Boundary confirmation**: не менее 40 rollouts на оставшийся
   `suite/task/init_state`.
3. **Planning holdout**: одинаковый набор rollout seeds для `max(value)` и всех
   risk-aware стратегий. Seed block не должен использоваться для выбора
   коэффициентов.
4. **Safety transfer**: L0/L1/L2 и одинаковые seeds по стратегиям.
5. **Финальная оценка**: bootstrap confidence interval по paired-разностям,
   success rate, safe success rate и violation rate.

Для предсказания failure разрешены только признаки, известные **до выполнения**
chunk: query-level uncertainty, value и текущие observations. Колонки
`observed_*` и `prediction_error_*` известны после выполнения выбранного chunk
и не могут использоваться для выбора action в том же query. Они нужны для
обучения следующего шага, диагностики и проверки связи uncertainty с ошибкой
world-model prediction.

Основные endpoints:

- task success rate;
- safe task success rate;
- official constraint violation rate;
- failure-mode distribution;
- AUROC и AUPRC предсказания failure;
- TPR при фиксированном FPR;
- lead time до failure event;
- calibration error и Brier score;
- time-to-success и jerk;
- paired improvement относительно `max(value)`.

## Готовые профили

Конфигурация находится в
`experiments/configs/libero_campaign_v1.json`.

| Profile | Назначение |
|---|---|
| `smoke` | 2 rollouts и проверка всего pipeline |
| `id_controls` | ID baseline |
| `boundary_search` | поиск natural mixed success/fail |
| `position_sweep` | контролируемая граница по x/y |
| `pro_ood_detection` | сильный OOD и abstention |
| `planning_holdout` | честное сравнение трёх planning strategies |
| `safety_physical` | официальные физические constraints |
| `safety_semantic_probe` | диагностический будущий abstention |

Посмотреть команды без запуска:

```bash
source scripts/mlspace_env.sh
python scripts/run_libero_experiment_campaign.py --list
python scripts/run_libero_experiment_campaign.py \
  --profile boundary_search \
  --run-prefix boundary_v1 \
  --gpus 2,3,4,5,6,7
```

Запуск на нескольких GPU:

```bash
python scripts/run_libero_experiment_campaign.py \
  --profile boundary_search \
  --run-prefix boundary_v1 \
  --gpus 2,3,4,5,6,7 \
  --execute
```

После прерывания используется та же команда с тем же `--run-prefix`.
Завершённые jobs имеют completion markers и пропускаются. Для намеренного
перезапуска добавляется `--force`.

Результаты одного campaign:

```text
experiments/campaigns/<run-prefix>/
  manifest.json
  logs/
  runs/
  videos/
  analysis/
  completed/
```

Каждый paired run автоматически получает:

- обычный uncertainty analysis;
- `episode_failure_modes.csv`;
- `failure_mode_summary.csv`;
- `query_traces_with_failure_labels.csv`;
- `online_pre_failure_queries.csv`;
- `failure_mode_counts.png`;
- `summary.json`.

## Установка LIBERO-Safety

Safety использует собственные package `libero` и fork `robosuite`, поэтому
создаётся отдельный environment:

```bash
bash scripts/setup_mlspace_libero_safety.sh
```

Скрипт фиксирует официальный commit
`19ec8df23eedfbb9265bafd3e56495fcebfcfcd0`, загружает public assets,
создаёт `.venv-cosmos-safety` и kernel
`YSDA Cosmos Policy LIBERO-Safety (MLSpace Py3.10)`.

Архив содержит около 903 тысяч файлов, поэтому распакованные assets по
умолчанию размещаются в локальном scratch
`/tmp/malnev_world_model_libero_safety_<commit>` и подключаются символической
ссылкой. После перезапуска вычислительного узла достаточно повторить setup:
архив остаётся в Hugging Face cache, заново выполняется только распаковка.
Постоянный путь можно задать через `LIBERO_SAFETY_ASSETS_DIR`.

Проверка после установки:

```bash
COSMOS_VENV="$PWD/.venv-cosmos-safety" \
  source scripts/cosmos_env_libero_safety.sh
python scripts/verify_mlspace_libero_safety.py --simulator-smoke
```

Verifier проверяет pinned checkout, пять benchmark suites, структуру L0-L2,
assets, EGL reset и наличие официального словаря `info["cost"]` после шага.

Запуск:

```bash
COSMOS_VENV="$PWD/.venv-cosmos-safety" \
  source scripts/cosmos_env_libero_safety.sh

python scripts/run_libero_experiment_campaign.py \
  --profile safety_physical \
  --run-prefix safety_v1 \
  --gpus 2,3,4,5 \
  --execute
```

Не устанавливайте LIBERO-Safety поверх `.venv-cosmos`: оба проекта публикуют
один пакет `libero`, а Safety требует собственный robosuite fork.

## Phase 1: результаты 24 июля 2026

Завершены ID controls и валидная часть LIBERO-PRO boundary screening. Smoke и
оборванный запуск с отсутствующими custom assets не включались в статистику.

| Split | Эпизоды | Success | Fail | Success rate |
|---|---:|---:|---:|---:|
| ID | 72 | 72 | 0 | 100.0% |
| LIBERO-PRO OOD | 106 | 82 | 24 | 77.4% |

Найдены семь fixed `suite/task/init_state` со смесью исходов. Наиболее полезные
для продолжения:

| Конфигурация | Success |
|---|---:|
| `libero_spatial_with_milk/task5/init0` | 12/24 |
| `libero_spatial_with_yellow_book/task8/init0` | 3/6 |
| `libero_10_with_mug/task4/init0` | 2/4 |
| `libero_spatial_with_mug/task0/init0` | 8/12 |

Среди 24 OOD fail получено 12 `timeout_no_goal`, 11
`target_drop_candidate` и один `timeout_partial_goal`. Official safety
violations равны нулю, поскольку это LIBERO-PRO, а не LIBERO-Safety. Drop
heuristic отметил 19 эпизодов, но восемь из них затем успешно завершились.
Поэтому эвристику надо трактовать как transient-event detector, а не как
официальный safety label.

Для leakage-safe early анализа использовались только `query=0..3`, то есть
наблюдения до `t=48`; самое раннее физическое failure event произошло на
`t=55`. Среди 60 эпизодов из семи mixed groups лучший exploratory signal:

```text
latent_action_copy_std_mean_mean_over_samples
pooled within-group AUROC = 0.671
```

Высокое значение соответствовало fail в пяти группах, в одной группе получена
ничья и в одной обратное направление. `action_first_step_l2_std` дал AUROC
`0.512`, `value_std` — `0.537`, `value_range` — `0.522`. Следовательно,
результаты одной milk-конфигурации не перенеслись автоматически на multi-task
screening; главным кандидатом остаётся internal action-latent consistency, но
он ещё не является готовым predictor.

После контроля `suite/task/init_state/query_idx` максимальная содержательная
корреляция uncertainty с последующей prediction error составила только
`rho=0.139` для internal future-proprio consistency против proprio L2 error.
Ранее наблюдавшиеся pooled correlations около `0.8` в основном отражали фазу
эпизода.

Полный отчёт, таблицы и графики:
[`phase1_analysis_20260724`](campaigns/phase1_analysis_20260724/README.md).
Пересчёт:

```bash
python scripts/analyze_libero_campaign_results.py
```

## Рекомендуемый порядок

1. `smoke`
2. `id_controls` и `boundary_search` параллельно
3. `position_sweep`
4. отбор 3-5 mixed-outcome configurations
5. настройка risk coefficients только на train/validation seed blocks
6. `planning_holdout`
7. `pro_ood_detection` для abstention
8. `safety_physical`
9. `safety_semantic_probe` после появления явного `STOP/REFUSE`

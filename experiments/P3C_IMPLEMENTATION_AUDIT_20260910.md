# P3c/P3d: проверка реализации и причин ухудшения

Дата: 10 сентября 2026. Проверены сохранённые данные и код, новые GPU-rollout
не запускались. Исходные кампании, веса, thresholds и результаты не изменены.

## Краткий ответ

**Ошибки подсчёта SR, перепутанных пар или лишних шагов не обнаружены.**
Пересчитаны 167 cases / 421 branch: P3c screen, development, holdout и P3d
development. Положительный P3c holdout `13/40 -> 24/40` подтверждается.

Однако есть существенные ограничения алгоритма и две проблемы интерпретации:

1. Trigger определяет допустимость геометрического манёвра, а не его
   полезность. Он может вмешиваться в уже успешный захват/перенос.
2. При failed post-retreat guard collector подставляет исходный baseline,
   отменяя последствия уже выполненных действий. Это неисполнимый на роботе
   fallback. **В проверенных P3c/P3d данных таких срабатываний 0**: данный
   дефект не объясняет ни выигрыш, ни ухудшение этих запусков.
3. Семь P3d `novel_cell` являются новыми относительно P3c intervention cohort,
   но **все 7/7 встречались в calibration/training локализатора**. Это не
   unseen-cell generalization всей системы. Пересечения конкретных
   `(position, task, init)` с calibration нет.
4. `snapshot_replay_max_abs=0` проверяет восстановленный вектор simulator
   state, а не независимое повторное исполнение всей ветви. Отчётное
   «exact replay 100%» следует читать в этом узком смысле.

## Независимый пересчёт

| Выборка | Baseline | Full RGB regrasp | Прирост | Rescue / harm | Exact McNemar p |
|---|---:|---:|---:|---:|---:|
| P3c development, 40 | 7/40 = 17.5% | 25/40 = 62.5% | +45.0 п.п. | 18 / 0 | 0.00000763 |
| P3c holdout, 40 | 13/40 = 32.5% | 24/40 = 60.0% | +27.5 п.п. | 12 / 1 | 0.00342 |
| P3d replication cells, 40 | 6/40 = 15.0% | 25/40 = 62.5% | +47.5 п.п. | 20 / 1 | 0.00002098 |
| P3d новые для P3c cells, 35 | 26/35 = 74.3% | 31/35 = 88.6% | +14.3 п.п. | 7 / 2 | 0.17969 |

На прежних cells эффект не исчез: `+47.5 п.п.` в P3d replication. Нельзя
называть переход `60.0% -> 88.6%` падением SR: это разные выборки. На более
лёгких новых cells уменьшился **добавочный выигрыш**, а не абсолютный SR.

Полезная описательная декомпозиция:

$$
\Delta SR = (1-SR_b)\,P(\mathrm{rescue}\mid b=0)
             - SR_b\,P(\mathrm{harm}\mid b=1).
$$

- P3c holdout: исправлено `12/27` baseline failures, испорчено `1/13` successes.
- P3d novel cohort: исправлено `7/9` failures, испорчено `2/26` successes.

На второй выборке меньше возможностей для rescue: всего 9 baseline failures
вместо 27. Условная доля исправленных failures даже выше, а доля harms среди
baseline successes в обоих случаях равна 7.7%. Это арифметическое объяснение
меньшего net gain, **не доказательство одинакового риска или лучшего переноса**:
выборки малы, различаются и не позволяют отделить все причины.

На P3c holdout независимый 20 000-repeat init-group bootstrap воспроизвёл
95% CI `[+12.5; +42.5] п.п.`. На P3d novel full regrasp CI
`[-2.9; +31.4] п.п.` также воспроизведён. NO-GO означает недостаток
свидетельств положительного переноса по frozen gate, не технический сбой.
Новые bootstrap CI в `comparisons.csv` являются вторичной проверкой с другим
seed/числом повторов; для вспомогательных абляций дискретные границы могут
отличаться от исходного анализа. Исходные frozen CI не заменяются.

## Два конкретных вредных вмешательства

`Position x0.2 / task2`: команда `pick up the salad dressing and place it in the basket`.
В init41 и init42:

| Момент / показатель | init41 | init42 |
|---|---:|---:|
| Первый зарегистрированный подъём предмета | t=62 | t=62 |
| Момент trigger | t=72 | t=72 |
| RGB estimated target-to-EEF distance | 8.33 см | 9.54 см |
| Estimated target z перед retreat | 0.251 м | 0.244 м |
| Estimated target-to-EEF после retreat | 2.65 см | 2.69 см |
| Target-drop proxy у full regrasp | t=82 | t=82 |
| Baseline outcome | success, t=129 | success, t=129 |
| Retreat-only outcome | success, t=132 | success, t=132 |
| Full regrasp outcome | fail, t=280 | fail, t=280 |

Замер подъёма сделан evaluator по simulator geometry и **не является
доказательством устойчивого захвата на t=72**. Но факт подъёма до trigger и
успех альтернативных ветвей согласуются с гипотезой ненужного вмешательства
в уже продвинувшуюся траекторию.

В этих двух ветвях выполнены все 25 primitive actions. По коду манёвра:

- t=73..75: open + retreat;
- t=76..82: approach с открытым gripper;
- t=83..88: descend;
- t=89..92: close;
- t=93..97: lift.

Drop отмечен **на этапе approach**, до close. Одинаковый трёхшаговый retreat
без дальнейшего regrasp обе задачи не испортил. Это указывает на вред полной
последовательности после retreat, а не только на открытие gripper.

Почему trigger разрешил это:

$$
T=C_{RGB}\land W(\hat p)\land
  0.08\leq\|\hat p_{target}-p_{eef}\|_2\leq0.50.
$$

Расстояние до предсказанной точки объекта не равно качеству захвата. Ошибка
локализации и смещение между точкой объекта и точкой захвата могут дать
больше 8 см даже при полезном текущем движении. Никаких проверок удержания,
совместного движения объекта и руки, прогресса к цели или ожидаемого вреда
здесь нет. После retreat условие нижней границы вообще отключено
(`require_miss=False`), поэтому расстояние 2.65 см не блокирует regrasp.
Положение цели оценивается один раз после retreat и дальше фиксировано;
нет повторной RGB-коррекции внутри approach/descend или проверки grasp перед
lift. Это ограничения примитива, не ошибка в арифметике SR.

**Ограничение диагностики:** основной P3c/P3d запуск не сохранял видео и
пошаговые RGB/контакты. Приведённая последовательность восстановлена по
collector, числу действий и evaluator timestamps. Нельзя достоверно назвать
точный контакт, ошибку глубины или положение пальцев причиной без нового
instrumented replay. Позднее переснятое видео нельзя выдавать за исходный run.

## Что проверено технически

- Raw parquet полностью совпадают с сохранёнными analysis parquet.
- Нет повторов `(case_id,strategy)`, пропущенных manifest cases/ветвей.
- Идентификаторы task/init/seed согласованы с manifest во всех ветвях.
- У ветвей одного case одинаковый prefix hash, 167 различных prefix hashes.
- Все записанные state-restore errors равны нулю.
- Query seeds соответствуют `rollout_seed + 1000*query_idx + [0,1,2,3]`.
- Prefix: `16+16+16+16+8=72`; continuation не более 8 действий на query.
- Сумма prefix + primitive + continuation точно равна `terminal_final_t`.
- Все terminal times не превышают 280; primitive не получает бесплатных шагов
  в наблюдавшихся применённых ветвях.
- Для ветвей без вмешательства все terminal поля совпадают с baseline.
- Нет случаев trigger-positive/post-guard-fail, скрытых fallback.
- Hash локализатора, heatmap weights и OOF-источника trigger совпадает с
  сохранёнными контрольными значениями.
- Нет init-group overlap между calibration и проверенными splits.
- Metadata согласованы по H/K/denoising/prediction mode; меняются cohort,
  init/rollout seeds и добавляется retreat-only control в P3d.
- По коду raw camera RGB не переворачивается перед calibration projection;
  display/policy flipping отдельно. Признаков возврата прежней orientation
  ошибки не найдено; новый рендер-проверочный rollout не выполнялся.

Baseline здесь **наш K4 max-value, parallel/joint prediction** с 5 denoising
steps; continuation H8. Это не no-planning policy, не H16 на всём эпизоде и
не авторегрессионная цепочка `a -> s -> v`. Выигрыш относится именно к этому
контролю, а не ко всем возможным режимам Cosmos planning.

## Дефекты и оставшиеся риски

### Нефизичный post-retreat fallback

В `scripts/collect_online_perception_regrasp.py` при `not post_guard_pass`
копируется `baseline_row`, выставляются `primitive_steps=0` и
`intervention_applied=False`. Уже выполненные open/retreat не учитываются.
Это допустимо только как явно обозначенная simulator-counterfactual
диагностика, не как реализуемое online поведение. Для следующего контроллера
нужно продолжать от фактического состояния после retreat с уже потраченными
шагами, а не возвращаться к t=72. **На текущих цифрах влияние нулевое.**

### Недостаточная проверка replay и загрузчика анализа

`snapshot_replay_max_abs` вычисляется после восстановления baseline и затем
передаётся в method row. Отдельный method action-replay error не измеряется.
Существующий snapshot helper сохраняет controller state, однако проверка
равенства sim vector сама по себе не доказывает равенство восстановленных
наблюдений, контактов или детерминированность последующего шага.

Старые analysis loaders используют `drop_duplicates(..., keep='last')` и
могут молча скрыть конфликтующие reruns. В текущих raw данных повторов нет.
Новый audit при дубликатах/неполной паре/смене seed/изменении fallback outcome
завершается ошибкой, а не исправляет таблицу незаметно.

### Слишком сильные формулировки

Нельзя утверждать, что shield **доказанно устранил** проблему P3b
wrong-object interactions: P3b и P3c оценивались на разных cohorts. В P3c
наблюдается `4/40 -> 1/40`, но это не отдельная matched shield ablation.
Нулевые official-safety flags не доказывают физическую безопасность и не
равны полной оценке LIBERO-Safety.

## Что делать дальше

1. Сохранить P3c как положительный результат на фиксированных cells/new init,
   а P3d как ограниченный перенос относительно P3c cohort.
2. Перед расширением убрать rollback из **новой версии** контроллера,
   проверять восстановленные наблюдения и короткий одинаковый action replay,
   сохранять в самих runs видео, действия, RGB, grasp/goal proxies.
3. Проверить фазовый guard: уже удерживаемый/переносимый предмет не отпускать
   без положительного evidence пользы. Online признаки: proprio gripper,
   RGB-track движения объекта относительно EEF, прогресс к цели. Simulator
   contacts/pose использовать как диагностический oracle, не скрытый input.
4. На одинаковых frozen snapshots сравнить `continue`, `retreat+requery`,
   прежний full regrasp и новый phase-guarded regrasp. Init41/42 использовать
   только для mechanistic/debug проверки, не для подтверждения улучшения.
5. Подтверждение проводить на новых init/seed и cells, исключённых также из
   обучения локализатора. t=72 оставить фиксированным контролем, event-driven
   timing проверять отдельной абляцией. Primary: paired SR, rescue/harm;
   secondary: target-drop, время и стоимость примитива.

Исходный frozen controller намеренно не переписывался этим аудитом: иначе
последующие replays незаметно стали бы другим методом. Новые эксперименты
recovery здесь не запускались; текущая P5 очередь не менялась.

## Воспроизведение проверки

Из корня проекта:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/audit_online_regrasp.py
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q tests/test_online_regrasp_audit.py
```

Артефакты: [summary.json](campaigns/p3c_audit_20260910/summary.json),
[comparisons.csv](campaigns/p3c_audit_20260910/comparisons.csv),
[harms.csv](campaigns/p3c_audit_20260910/harms.csv).
Сохранены hashes исходных таблиц; audit не перезаписывает frozen analysis.
Запущены 30 CPU-тестов audit, trigger, geometry, primitives и P3c/P3d analysis:
все прошли. Это не end-to-end GPU/simulator regression test.

Источники: [P3c results](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md),
[P3d results](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md),
[timing decision](RECOVERY_TIMING_DECISION_20260909.md),
[calibration manifest](frozen_models/perception_regrasp_20260904/calibration_manifest.csv).

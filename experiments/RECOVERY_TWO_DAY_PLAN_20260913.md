# Финальные два дня: подтвердить recovery, отделить эффект от времени и контакта

Дата: 13 сентября 2026. Горизонт: два дня. Ночная серия имеет отдельный
бюджет **9 часов wall-clock от запуска**, не 9 GPU-часов. Этот документ
фиксирует дизайн до новых результатов; фактический запуск подтверждается
в `campaigns/recovery_confirmation_20260913/LAUNCH_VERIFIED.md`.

**Фактический срез 13 сентября:** [промежуточные результаты и новый порядок диагностики](RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md).
Серия прервана: main441/512, timing0/768. Ниже сохранён исходный frozen
дизайн до результатов; hypotheses, arms и seeds этим анализом не изменялись.

## Научный приоритет

За два дня не начинать новую широкую архитектуру, обучение VLA или перебор
десятков uncertainty коэффициентов. Самое сильное положительное evidence:
P3c 13/40 -> 24/40, +27.5 п.п.; повторная проверка знакомых cells 6/40 ->
25/40. Перенос 26/35 -> 31/35 перспективен, но CI включает ноль.
Decoder-medoid 112/180 = max-value 112/180; расширять этот sweep сейчас
нецелесообразно. Дополнительный regrasp после пробы дал 16 harms при уже
двигавшемся с рукой предмете; preserve-only дал локальный post-hoc gain.

Цель: получить проверяемый ответ, где frozen recovery действительно полезен,
насколько он зависит от времени и переносится ли за пределы calibration.
Не обещать ICLR acceptance или новый SOTA до результатов. Recovery и
визуальная коррекция известны: [Rewind-IL](https://arxiv.org/abs/2604.16683)
использует inter-chunk discrepancy и возврат к checkpoint;
[FLARE, CVPR 2026](https://arxiv.org/abs/2608.26645) обучает Retry/Reset skills
и использует MLLM monitoring. Наше потенциальное отличие не сам факт
повторного захвата, а контролируемое разделение выбора кандидата, физического
восстановления, момента вмешательства и вреда лишнего раскрытия.

## День 1: замороженная девятичасовая серия

Кампания: `recovery_confirmation_20260913`.

| Этап | Дизайн | Максимум результатов |
|---|---|---:|
| Technical replay | 3 старых состояния, 3 неизменённых контроля | 9 ветвей, вне SR |
| Main, t=72 | 128 случаев, baseline H16 и 3 парные ветви | 512 эпизодных исходов |
| Timing | Те же 128 исходных траекторий, t=56 и t=88, 3 ветви | 768 исходов |
| Всего | Сначала main, затем timing; без выбора по полученному SR | **1289** |

Полное завершение зависит от свободных GPU. Не дописывать незавершённые
эпизоды как fail и не публиковать confirmatory p-values для незаконченной
фазы. Нет автоматического увеличения времени, обучения или открытия holdout.

### Задачи и данные

- LIBERO-PRO **Position perturbations задач Object suite**, не вся матрица
  Object/Environment/Position и не официальный LIBERO-Safety benchmark.
- Replication: восемь прежних cells P3c: x0.2/tasks5,6,9;
  y0.2/tasks4,6,9; y0.3/tasks1,5.
- Transfer: x0.3/tasks1,2,4,5,6,7,8,9. Ни одной такой cell нет в calibration
  локализатора; это новый для него position level, но знакомые предметы.
- По восемь штатных init IDs25-32 в каждой cell, один новый заранее
  определённый rollout seed на case: **128 task/position/init clusters**.
- В задаче всего 50 штатных init. IDs25-32 не входят в calibration,
  но некоторые уже встречались в прошлых rollout-исследованиях. Это fresh-seed
  prospective replication замороженных методов, **не глобально нетронутый
  init holdout**. Не подбирать seeds по исходам.
- Tasks0 и3 не включены: frozen localizer/trigger не обучены для этих
  объектов. Нельзя скрывать это или усреднять таблицу как 10-task benchmark.

### Контроли и методы

1. `baseline_h16`: один невмешанный полный rollout Cosmos K4/max-value,
   generate16/execute16, с реальным наблюдением перед каждым query.
2. `continue_h8`: общий H16 prefix до выбранной точки, затем fresh query и
   execute8. Это не H8 с начала эпизода и не продолжение старого discarded tail.
3. `physical_regrasp`: тот же prefix, frozen RGB trigger и старый полный
   recovery, затем то же H8 продолжение.
4. `refresh_preserve_only`: старый recovery, когда старый trigger разрешил
   его; иначе при допустимой пробе до трёх шагов отвода вверх с сохранением
   предыдущей команды gripper, затем H8 **без нового regrasp после пробы**.

Название preserve-only не означает veto любого regrasp и не доказывает
сохранённый grasp. Новый contact-aware veto в эту ночь не добавляется:
сначала нужно независимо проверить уже имеющийся положительный вариант.
Близость предмета к руке или confidence локализатора не являются надёжным
свидетельством удержания предмета.

### Формулы и архитектура

В каждой точке политика получает реальные agentview/wrist RGB, proprio и
команду. K=4 samples одного frozen checkpoint, пять denoising steps;
action/future/value генерируются **joint/parallel**, не AR a -> s' -> v.

$$
i_t=\arg\max_{i=1,\ldots,4}V_i(o_t,\ell),\qquad
A_t\in\mathbb R^{16\times7}.
$$

Frozen trigger:

$$
G(o_t)=C_{RGB}(o_t)\land W(\hat p_t)\land
\bigl(0.08\leq\|\hat p_t-p^{EEF}_t\|_2\leq0.50\bigr).
$$

Все расстояния в метрах. Пороги confidence и calibrated workspace берутся
из прежнего hash-pinned artifact, без перенастройки на x0.3.
GT object positions доступны только offline diagnostics.

Время t=56/72/88 соответствует первым восьми действиям queries3/4/5.
Все три состояния снимаются **с одного непрерывного baseline H16 rollout**:
выполнение раннего recovery не влияет на поздние точки сравнения.
На ветвях в одной точке общий exact MuJoCo/controller snapshot и одинаковые
суффиксные seeds. Позднее наблюдения расходятся вследствие разных действий.
При успехе до точки вмешательства этот success сохраняется во всех ветвях,
не исключается из знаменателя и не превращается в fail.

После действий primitive при отказе guard продолжаем из физического текущего
состояния: нет rollback к прежней позе. Все действия, включая пробу/regrasp,
входят в общий лимит **280** после 10 settling actions.

### Метрики и статистика

Основная метрика terminal task success. Четыре заранее заданных контраста
при t=72 образуют одну Holm-family:

| Scope | Метод | Контроль |
|---|---|---|
| Replication | Physical regrasp | Continue H8 |
| Transfer x0.3 | Physical regrasp | Continue H8 |
| Все 16 cells | Preserve-only | Physical regrasp |
| Все 16 cells | Physical regrasp | Невмешанный baseline H16 |

$$
\Delta=\frac1{|\mathcal C|}\sum_{c\in\mathcal C}
\frac1{n_c}\sum_j(Y^{method}_{cj}-Y^{control}_{cj}).
$$

Init-cluster bootstrap внутри фиксированных cells, 95% CI, cluster sign-flip,
Holm correction. Новые suffix/timing ветви не увеличивают число независимых
init. Timing-контрасты вторичные: нельзя выбрать лучший t по этим данным и
назвать его подтверждённым улучшением без отдельной проверки.

Дополнительно: rescue/harm, per-cell SR, действия до завершения, число model
calls и interventions, suffix drop/wrong-object proxies. Branch safety
tracker начинается в точке вмешательства; baseline H16 tracker начинается
в t=0. Полные и suffix-only safety endpoints не смешивать. Это локальные
прокси, а не официальные результаты LIBERO-Safety. Wall-time на общем GPU
не трактовать как чистую production latency.

Записываются все действия, K candidate actions/values и online uncertainty
каждого query, input hashes, runtime snapshots и per-step signals. Видео
основной серии полные: t=0 до terminal success/280, обе камеры. H16 future
не сравнивается с наблюдением после 8 действий; такого prediction error в
этой серии не заявляем. Replay smoke-видео начинаются в t=72 и исключены из SR.

## День 2: решение по полученным данным

1. Утром проверить полноту, exact replay, masks/splits, physical budget,
   frame alignment. Сначала зафиксировать таблицы всех arms, затем интерпретацию.
2. Если P3 переносится на x0.3, повторить frozen лучший вариант на новых
   init/целых cells с отдельным manifest и бюджетом; сравнить с обоими
   baseline H16 и H8. Не менять localizer одновременно с проверкой trigger.
3. Если прирост только на знакомых cells, оставить положительный bounded
   claim P3c и объяснить ограничения локализации/допуска/primitive по traces.
4. Если preserve-only подтверждается, проверить добавочный эффект относительно
   старого recovery, а не только слабого continue. Приоритет новой небольшой
   модификации: passive target-grounded held evidence перед раскрытием,
   с explicit unknown и контролем missed recoveries. Не заменять её GT oracle.
5. Если лучшее время узкое, не продвигать t=72 как универсальный detector.
   Изучить broad window и фазу; state-conditioned trigger обучать только на
   development trajectories и проверять на других целых группах. За один
   оставшийся день не обещать надёжно обучить и валидировать сложную модель.
6. Последние 4-6 часов: заморозить результаты, собрать figures/video пары,
   обновить общий research report, evidence ledger и LaTeX. Не добавлять
   положительный claim из незавершённого теста и не скрывать отрицательные arms.

## Автономность и команды

До запуска проверяются hashes исходников, frozen Cosmos runtime, localizer,
trigger, position assets и replay источников. GPU0-7 допускаются только после
двух idle измерений и отсутствия compute processes. Busy GPU не резервирует
часть заданий: другие свободные workers могут их взять. GPU4-5 на момент
проверки заняты чужими CUDA-процессами; они не останавливаются. Одна модель
используется на несколько заданий одного position level.

Общий deadline считается от старта dispatcher и сохраняется при restart.
После 9 часов прекращаются новые queries; предусмотрено до 120 секунд на
завершение/остановку своих worker process groups, затем CPU-анализ. Последний
неполный case сохраняет уже закоммиченные ветви для resume. Повторный сбой
worker останавливает серию, не запускает бесконечный retry.

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/run_recovery_confirmation.py --status'
```

Результаты: `experiments/campaigns/recovery_confirmation_20260913/analysis/`:
`main/RESULTS.md`, `main/aggregate_scores.csv`, `main/paired_effects.csv`,
`main/query_metrics.csv`, `main/videos.html`; аналогично для timing.
Автоматический локальный download при отключённом ПК не обещается.

Источники: [P3c](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md),
[P3d](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md),
[Observation Contract](OBSERVATION_CONTRACT_RESULTS_20260912.md),
[decoder-medoid](DECODER_MEDOID_RESULTS_20260912.md),
[решение о времени вмешательства](RECOVERY_TIMING_DECISION_20260909.md).

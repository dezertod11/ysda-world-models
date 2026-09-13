# Все результаты проекта: анализ для публикации

**Новый промежуточный срез, 13 сентября:**
[Recovery confirmation: результаты, графики и OOD-диагностика](../../experiments/RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md).
Серия прервана: main441/512, timing0/768. На108 полностью matched cases
familiar physical40/61 противH8 16/61; transferx0.3 1/47 против0/47.
Preserve-only не добавил SR. Медианная offline XY-ошибка локализатора
2.53см наfamiliar против23.50см наx0.3; все18разрешённых transfer gates
имеют ошибку>5см. Это предварительная локальная репликация и post-hoc
диагностика, **не final confirmation, не universal recovery и не event-SR**.
Далее сохранена сводка завершённых исследований на12сентября.

**Полный оформленный отчёт с формулами:** [FULL_RESEARCH_REPORT.md](FULL_RESEARCH_REPORT.md).
**Краткие результаты:** [RESEARCH_SUMMARY.md](RESEARCH_SUMMARY.md).
**Английская статья:** [LaTeX](manuscript/main.tex), [PDF](build/iclr2027.pdf).

Срез: **12 сентября 2026**, включая завершённые ночные серии Observation
Contract (1536 основных ветвей) и decoder-medoid (1440 rollout).
Это единый вход в результаты, а не новый benchmark и не сумма всех запусков.
Числа сверены с сохранёнными отчётами; основная valid199-таблица также с CSV.
Полный повторный аудит всех старых raw trajectories в этом обзоре не проводился.

**Начать здесь:** прочитать разделы 1–3, затем нужную ветку в разделе 4.
[Результаты других авторов и сопоставимость](RELATED_WORK_RESULTS.md),
[каталог исходных материалов](RESULTS_INDEX.md),
[реестр допустимых утверждений E1–E19](EVIDENCE_LEDGER.md),
[план статьи](PLAN.md).

Источники остаются в `experiments/`: мы не копируем CSV/видео в новую
«главную» экспериментальную папку и не подменяем исторические отчёты.
Каталог включает и предварительные/технические материалы; наличие файла
не означает, что результат подтверждён. Статистические выводы находятся здесь
и в соответствующем подробном отчёте.

## 1. Самое важное

1. **Наиболее убедительный полезный механизм: восстановление захвата по RGB.**
   P3c на новых init выбранных сложных Position cells: **13/40 → 24/40**,
   +27.5 п.п., 95% CI [12.5; 42.5]. Но перенос на другие cells не подтверждён;
   это не +27.5 п.п. на всём LIBERO-PRO.
2. **Реальное наблюдение иногда помогает, но не в любой момент.**
   В shared-prefix опыте Object/task0: **46/100 → 64/100**, +18 п.п.,
   init-cluster CI [4; 32]. Более широкие и более поздние fresh8-тесты не
   подтвердили универсальную полезность частого перепланирования.
3. **Нового широко превосходящего max-value selector пока нет.**
   valid199: max-value macro-SR **54.77%**, наш OSC-medoid **54.09%**,
   KeyStone-style **55.76%**. Все основные CI разности включают ноль.
4. **Предсказывать риск состояния, выбирать действие и выбирать recovery
   нужно отдельно.** P4b: failure AUROC 0.650, но within-pool ranking 0.509;
   уменьшение prediction error не дало увеличения terminal SR.
5. **Появилась содержательная механистическая история:** pool может не
   содержать хорошего действия; suffix меняет outcome; запрос наблюдения
   может физически навредить; ошибочный gate отменяет полезное recovery.
   Это основа исследования, но ещё не доказательство новизны общего controller.

**Новый итог ночи 11–12 сентября:** decoder-medoid H16 = max-value,
**112/180 =62.22%**, 7 rescue/7 harm. H8 не улучшил средний SR. В recovery
preserve-only161/192 лучше primary preserve+regrasp145/192: все16 потерянных
успехов сопровождаются drop во время дополнительного вмешательства, когда
до него предмет уже двигался с захватом. Лучший новый deployable arm остаётся
post-hoc гипотезой: его gain над старым recovery сосредоточен в одной cell.
Подробности по каждому методу в разделе4.6; очереди этим анализом не менялись.

## 2. Что именно мы сравниваем

Основная архитектура: frozen **Cosmos-Policy-LIBERO-Predict2-2B**. На query
поступают реальные external/wrist RGB, proprioception и T5 embedding команды.
Генерируются action chunk, future images/proprio и value. В большинстве наших
опытов они получены **совместно, parallel/joint**, а не авторской цепочкой
$a\to s'\to v$ с отдельным дообученным planning checkpoint.
AR проверялся отдельно; его отрицательный малый pilot не опровергает статью.

| Постановка | Единица анализа | Что означает результат |
|---|---|---|
| Standard LIBERO | Полный эпизод | ID control, не сложный OOD benchmark |
| LIBERO-PRO Object suite, Object/Environment/Position factors | Полный эпизод на зафиксированных task/level/init/seed | Основное широкое deployed comparison; subset надо называть явно |
| Boundary / shared-prefix | Ветвление из сохранённого состояния | Условный эффект вмешательства, не SR с начала произвольного эпизода |
| Candidate replay | Несколько действий из одного состояния и их suffix repeats | Opportunity/ranking; ветви одного состояния не независимы |
| LIBERO-Safety | Эпизод с официальными constraints | Отдельно task success, safe success, violation; PRO drop proxy его не заменяет |
| Seeded video replay | Повторный запуск для иллюстрации | Не обязательно исходный статистический rollout |

Для valid199 generate/execute = 16/16, K4 (K1 у single-sample control),
5 denoising steps, 280 физических действий. У recovery-опытов часто общий
prefix до $t=72$, затем generate/execute = 16/8. Нельзя объединять эти SR.
$t=72$ выбран для конкретной исследовательской постановки, не найден как
универсальная точка ошибки. Точное определение каждой ветви есть в её протоколе.

$$
\mathrm{SR}_f=\frac{1}{n_f}\sum_jY_{fj},\qquad
\mathrm{MacroSR}=\frac{1}{3}\sum_{f\in\{Object,Environment,Position\}}\mathrm{SR}_f.
$$

Для paired comparison $\Delta=\operatorname{mean}(Y_{method}-Y_{control})$;
rescue означает control fail / method success, harm означает обратное.
CI и тест должны учитывать повторения одного init; для macro-SR нужны веса
факторов. McNemar по эпизодам не является отдельным тестом macro-estimand.
Повторные анализы одних traces и повторно использованные controls **не суммируем**
как новые независимые данные. Поэтому общего числа «успехов всего проекта» нет.

## 3. Главные таблицы

### 3.1. Широкое сравнение выбора действия: valid199

Все 10 задач Object suite; 50 Object, 50 Environment, 99 Position случаев
на метод. Один пустой upstream asset исключён одинаково у всех arms.
**1194 выполнения = 199 конфигураций × 6 методов**, не 1194 независимых сцен.

| Метод | Object, % | Environment, % | Position, % | Macro-SR, % | Success / 199 |
|---|---:|---:|---:|---:|---:|
| K1, без selection | 94.00 | 38.00 | 28.28 | 53.43 | 94 |
| Max-value K4 | 94.00 | 40.00 | 30.30 | 54.77 | 97 |
| Наш OSC-medoid K4 | 96.00 | 40.00 | 26.26 | 54.09 | 94 |
| Raw-medoid K4 | 94.00 | 42.00 | 28.28 | 54.76 | 96 |
| KeyStone-style K4 | 98.00 | 40.00 | 29.29 | 55.76 | 98 |
| KDPE endpoint K4 | 94.00 | 40.00 | 25.25 | 53.08 | 92 |

| Против max-value | Macro-разность, п.п. | 95% CI | Rescue / harm |
|---|---:|---|---:|
| OSC-medoid | −0.68 | [−3.33; 1.99] | 3 / 6 |
| Raw-medoid | −0.01 | [−3.35; 3.33] | 6 / 7 |
| KeyStone-style | +1.00 | [−2.01; 4.33] | 6 / 5 |
| KDPE endpoint | −1.68 | [−4.77; 1.33] | 3 / 8 |

**Вывод:** различий недостаточно для утверждения о превосходстве.
У max-value micro-SR = 97/199 = 48.74%; это другое усреднение, не ошибка.
Это deployed test: q0 pools между отдельными процессами bitwise совпадают
только примерно в 31–46% сравнений K4. Не выдавать за строгий common-pool
causal test одного selector. KeyStone/KDPE здесь адаптации, не полные
воспроизведения авторских K16/K100 экспериментов.

[Полный разбор](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md),
[factor CSV](../../experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/factor_scores.csv),
[paired CSV](../../experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/paired_effects.csv).

### 3.2. Положительные эффекты и обязательные ограничения

Это **разные наборы данных и controls**, а не рейтинг методов между строками.

| Опыт | Control → method | Эффект, п.п.; 95% CI | Что действительно установлено |
|---|---|---|---|
| P3c online RGB regrasp | 13/40 → 24/40 | +27.5; [12.5; 42.5] | Новые init восьми выбранных Position cells; 12 rescue / 1 harm; p=.00342 |
| P3d replication знакомых cells | 6/40 → 25/40 | +47.5; [30.0; 65.0] | Подтверждает полезность прежнего recovery на этих cells, не перенос на новые задачи |
| Shared-prefix q4, Object/task0 | 46/100 → 64/100 | +18; [4; 32] | 100 ветвей на arm, 50 init clusters; 31/13; полезность конкретного feedback intervention |
| P3e система recovery против продолжения | 34/75 → 55/75 | +28; [17.3; 40.0] | Весь recovery stack лучше этого baseline |
| P3e router против full regrasp | 53/75 → 55/75 | +2.7; [0; 6.7] | Только 2/0, p=.5; дополнительный вклад router не подтверждён |
| Selection × adaptive horizon | 100/168 → 121/168 | +12.5; [4.8; 20.8] | Семь фиксированных cases; Holm p=.0258; case-level CI [−4; 29] ограничивает перенос |
| Timing screen: immediate regrasp | 63/96 → 76/96 | +13.54; [8.33; 18.75] | Новые init известных cells, 16/3; Holm p=.17046, не corrected-significant |

Источники: [P3c](../../experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md),
[P3d](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md),
[q4](../../experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md),
[P3e](../../experiments/P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md),
[factorial](../../experiments/FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md),
[timing](../../experiments/TIMING_ELIGIBILITY_RESULTS_20260911.md).

Положительный P3c всегда показывать вместе с
[P3d transfer](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md):
+14.3 п.п., CI [−2.9; 31.4], gate NO-GO. Эти cells были новыми для recovery
проверки, **но не unseen для обучения localizer**. Старые P3c/P3e видео
могут быть последующим seeded replay, а не исходной записанной ветвью.
[Аудит P3c/P3d](../../experiments/P3C_IMPLEMENTATION_AUDIT_20260910.md)
подтвердил основные числа; найденный нефизичный fallback в проверенных
основных ветвях не срабатывал. Для новых методов отмена уже совершённых
физических шагов недопустима.

## 4. Вся траектория исследования

Здесь исследования сгруппированы по вопросу. Подробные stage reports,
notebooks, machine-readable summaries и галереи перечислены в
[каталоге](RESULTS_INDEX.md). Старые промежуточные цифры не заменяют последующую
replication; перечисленные ниже ограничения имеют приоритет над ранним optimism.

### 4.1. Исходные uncertainty / risk-aware planning, май–август

| Что проверяли | Результат | Анализ и источник |
|---|---|---|
| Natural paired success/fail, query traces, prediction vs reality | Получены оба outcome на фиксированных task/init; изучены std/range и latent copies | Поиск гипотез, не независимая проверка выбранного лучшего predictor. [Ранние данные](../../experiments/uncertainty/) |
| Майская серия 12 seeds, четыре стратегии | Max-value 6/12; action 6/12; value 7/12; combined 4/12 | Малый выбранный case, не общий выигрыш и не научный вывод по отдельному удачному видео. [CSV](../../experiments/uncertainty/planning_video_export_20260529/analysis/video_strategy_summary.csv) |
| Standard LIBERO / PRO screening | 72/72 ID; 82/106 PRO; позднее 1078 strategy executions | Интеграция и поиск hard cases; не полный ID leaderboard. [Итог июля](../../experiments/LIBERO_COMPLETE_RESULTS_20260724.md) |
| Static uncertainty penalties, denoise-10 replication | 52/100 → 56/100, CI [−5; 13], 14/10 | Универсальный gain не подтверждён. [Replication](../../experiments/campaigns/replication_safety_analysis_20260813/README.md) |
| Adaptive horizon / phase gate | 115/180 → 143/180; phase-only 130/180 | Положительно на шести cases; replay disagreement 4.4–9.4%, не broad transfer. [Отчёт](../../experiments/campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md) |
| Surrogate-triggered requery | 146/240 → 147/240; прежний requery 161/240 | Прогноз ошибки не превратился в лучший control. [Отчёт](../../experiments/SURROGATE_REQUERY_RESULTS_20260820.md) |
| Factorial 2×2 | Selection-only −6.0 п.п.; horizon-only +8.3; combined +12.5 | Разделили вклад выбора и частоты feedback, но только на фиксированных cases. [Отчёт](../../experiments/FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md) |
| Official LIBERO-Safety | 144 rollout; success/safe-success 0; четыре official violations | Нельзя заявлять работающий safety planner; semantic init assets отсутствовали. [Отчёт](../../experiments/campaigns/replication_safety_analysis_20260813/README.md) |

**Урок:** графики success/fail порождают гипотезы. Post-chunk error доступен
после действия, episode aggregates используют будущее, а большой разброс может
означать несколько допустимых способов действия. Это не автоматически сигнал
для предотвращения ошибки в текущем chunk.

### 4.2. Overlap, consequence prediction и candidate ranking

| Что проверяли | Результат | Анализ и источник |
|---|---|---|
| Temporal overlap | 312 rollout; selected RMSE AUROC около .50; часть event labels невалидна | Не получен переносимый ранний detector; неверные labels исключены из сильных claims. [Аудит](../../experiments/TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md) |
| Исправленный boundary screening | 264 rollout; лучший preregistered macro-AUROC .613, CI включает .5 | Есть естественные fail, но недостаточно доказательств детектора. [Отчёт](../../experiments/GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md) |
| Broad horizon controls | 299 matched episodes/arm; maxV-H16 macro 54.5%, другие 52.1–52.8% | Узкие boundary gains не перенеслись. [P0–P2](../../experiments/GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md) |
| Dense H16/H32 consequence | Dense relabel устранил ties; H32 gate не улучшился | Исправление target, не рост terminal SR. [Отчёт](../../experiments/DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md) |
| Frozen H16 ridge ranker | Offline regret −43.1%, 230 strict states; closed-loop 165/360 → 164/360 | Лучшее предсказание локальной ошибки недостаточно. [Offline](../../experiments/FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md), [online](../../experiments/FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md) |
| Terminal critic | Все 160 holdout candidates success; ноль переключений | Holdout не содержит opportunity для проверки ranking, не PASS по качеству. [Отчёт](../../experiments/TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md) |
| K4/K8/K16 opportunity | 50 states, 800 branches; K16 не добавил oracle success к K8 в Object/Position | В этой постановке увеличение pool не устранило all-fail states. [Отчёт](../../experiments/PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md) |
| AR $a\to s'\to v$ pilot | 10 states/80 candidates; parallel и AR SR 30%; mixed-pool accuracy .429 → .308 | Малый отрицательный pilot на нашем checkpoint, не репликация всего авторского planning. [Отчёт](../../experiments/AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md) |
| Pairwise hard-cell ranker | Holdout maxV/raw/gated/oracle: 45/15/30/60% | Обученный selector не перенёсся, хотя opportunity была. [Отчёт](../../experiments/HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md) |
| P4 independent dynamics | 5668 transitions; quadratic JRD после clamp = 0 | Выродился конкретный score; это не опровержение ensemble UQ. [Отчёт](../../experiments/P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md) |
| P4b residual risk | 200 states/800 branches; error −2.14%, SR 58.5% → 56.5%, 4/8 | Risk detection .650 не означает ranking: within-pool .509. [Отчёт](../../experiments/P4B_RESIDUAL_RISK_RESULTS_20260907.md) |

### 4.3. Когда запрашивать новое наблюдение

| Что проверяли | Результат | Анализ и источник |
|---|---|---|
| Real-observation pilot / factor router | После pilot factor routing 53/90 → 47/90 | Один OOD factor не определяет пользу requery. [Pilot](../../experiments/REAL_OBSERVATION_REQUERY_RESULTS_20260830.md), [transfer](../../experiments/FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md) |
| Fixed query0, phase, semantic VoF | q0 отрицателен; CLIP semantic gate FAIL | Нельзя назначать requery по одному времени или глобальному semantic score. [q0](../../experiments/INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md), [phase](../../experiments/PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md), [semantic](../../experiments/SEMANTIC_VOF_RESULTS_20260831.md) |
| Object/task0 q4 holdout | 60 pairs, +21.7 п.п.; затем shared-prefix +18 п.п. | Узкое положительное подтверждение, см. раздел 3. [Первый holdout](../../experiments/OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md) |
| Отдельные процессы полного rollout | Номинально +11/+19 п.п.; prefixes расходятся до intervention | Описательные SR; causal claim основан на shared-prefix, не этих запусках. [Первый](../../experiments/OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md), [replication](../../experiments/OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md), [RNG-аудит](../../experiments/COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md) |
| q4 task/factor transfer | 180 Object-task pairs на ceiling; 120 strict Position pairs, interaction 0 п.п. | Перенос фиксированной точки не подтверждён. [Tasks](../../experiments/OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md), [Position](../../experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md), [screen](../../experiments/OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md) |
| Signed VoF / invariant CATE | New-task 240 pairs, AUROC .398; reserve 400 pairs: 57.0% → 55.75% | Лучше always-query не означает лучше commit. [Signed](../../experiments/SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md), [CATE](../../experiments/INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md) |
| Object/contact features и privileged context | 640 уже собранных strict pairs; transfer gates FAIL | Ограничение проверенных linear-feature моделей, не всех object-centric методов. [Object](../../experiments/OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md), [context](../../experiments/CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md) |
| P5 repeat feedback | 36 states, 10 task/init clusters; fresh8 41/108, open16 44/108, stale8 45/108 | CI включают ноль; один intervention, не всегда-H8 controller. [1080 branches](../../experiments/P5_REPEAT_FEEDBACK_RESULTS_20260910.md) |
| Matched K / continuity feedback | 24 states; open16 15/24, fresh K1/K4/continuity 13/24 | Контроль K и continuity не вернул pooled gain. [120 branches](../../experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md) |

### 4.4. Recovery, observation и проверка захвата

| Что проверяли | Результат | Анализ и источник |
|---|---|---|
| P3 recovery opportunity | H4 7/80, blind lift 8/80, privileged regrasp 62/80 | Контакт/локализация важнее одного sampling; 77.5% условный GT upper bound. [Отчёт](../../experiments/RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md) |
| P3b perception-backed recovery | 43/72 восстановлены; 47 task/init groups; CI [45.2; 73.9]% | Условный recovery SR, не полный benchmark. [Отчёт](../../experiments/PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md) |
| P3c / P3d / P3e | P3c +27.5 п.п.; P3d transfer NO-GO; router лишь +2/75 над full | RGB recovery полезен локально; новый selective router не подтверждён. Источники в разделе 3 |
| P3d full vs retreat-only | На всех75 cases full56/75 против retreat36/75, +26.7 п.п., 23/3; replication25/40 против8/40 | Эффект полного манёвра не объясняется одним новым запросом. На новых cells gain отдельно не подтверждён. [Абляция](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md) |
| Probe–verify–repair | 48 states: continue26, full35, probe26, verified30 | Verified хуже full на 10.42 п.п.; crop нередко следит за захватом, а не предметом. [Отчёт](../../experiments/PROBE_VERIFY_REPAIR_RESULTS_20260911.md) |
| Grounded mask / conservative gate | 48 новых paired states: full33, conservative/probe-always35; false-held 10→0 на 27 пробах | 8 ошибок стали unknown; conservative повторяет always по 48 outcomes/47 trajectories. Вклад verifier в control не выделен. [Отчёт](../../experiments/GROUNDED_PROBE_RESULTS_20260911.md) |
| Delay transfer | Другие 48 states: full36, delayed/continue33 | Fresh gate отменил 14/21 eligible recovery; timing смешан с gate. [Тот же отчёт](../../experiments/GROUNDED_PROBE_RESULTS_20260911.md) |
| Timing / eligibility | 96 states: immediate/diagnostic76, fresh/checked74, continue63 | Новый checked NO-GO; цена физической пробы ненулевая. Все17 common fails вне старого trigger. [490 проверенных ветвей](../../experiments/TIMING_ELIGIBILITY_RESULTS_20260911.md) |

Последние три отрицательные screen не уничтожают P3c-result. Они показывают,
что **новые усложнения не лучше сильного recovery control**. Маска может
исправлять perception и при этом не менять outcome. Нельзя весь gain над
continue приписать verification.

### 4.5. Consensus и повторная оценка action advantage

| Что проверяли | Результат | Анализ и источник |
|---|---|---|
| Pure / guarded medoid до P5 | K3/H5 pure7/40 против maxV8/40; guarded6/20 против5/20 | Не подтверждён; H5/K3–5 нельзя смешивать с H16/K4. [Отчёт](../../experiments/CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md) |
| Common-pool / trajectory development | Development macro57.50% →59.17%, 3/2, CI [−3.33; 8.33] | Выбор гипотезы, не независимое подтверждение. [Common-pool](../../experiments/CONSENSUS_COMMON_POOL_RESULTS_20260908.md), [development](../../experiments/campaigns/trajectory_consensus_20260908_development/trajectory_analysis/RESULTS.md) |
| valid199, шесть selectors | См. раздел3: убедительного выигрыша нет | Финальный тест заменяет optimistic development интерпретацию. [Отчёт](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md) |
| P5 K8 pilot | 36 states/288 branches: max18/36, empirical oracle19/36,17 all-fail pools | Малая opportunity при одной реализации suffix, не вечный верхний предел. [Pilot](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md) |
| Повторы suffix | У96/288 candidates меняется label; split-repeat K8 selection44/108 = max-value | Оптимистичные55.56% при выборе/оценке на одних repeats не out-of-sample result. [Аудит](../../experiments/P5_REPEAT_FEEDBACK_RESULTS_20260910.md) |
| Pool13 replication / соседние init | Fixed alternatives10/10 против1/10 max-value, Holm p=.01171875; соседний split40/80 против36/80, CI [−3.75;18.75] п.п. | Локальная устойчивая misranking есть; переносимый обученный verifier ещё не получен. [690 branches](../../experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md) |

### 4.6. Ночь 11–12 сентября: полные результаты по новым методам

Observation Contract завершена01:48MSK, decoder night07:31MSK. Все1536/1440
основных выполнений завершены, active workers нет. Ранний срез00:20MSK
сохранён как исторический, но больше не определяет статус результатов.
Smoke и повторно использованные controls не добавляются в независимое n.

**[Observation Contract: восемь методов и механизм ошибок](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md).**
192 suffix cases на arm,96 старых prefixes,48 init clusters,12 Position cells,
t72, generate16/execute8. Conditional development SR, не full benchmark.

| Метод | Success /192 | SR,% | Вывод |
|---|---:|---:|---|
| Continue H8 | 128 | 66.67 | Контроль без recovery |
| Старый physical regrasp | 151 | 78.65 | Сильный comparator |
| Open probe only | 154 | 80.21 | Незначительный net gain, хуже preserve |
| Preserve probe only | 161 | 83.85 | Лучший обычный arm; +10 net successes на одной x0.2/task9 cell |
| Open probe + regrasp | 138 | 71.88 | Дополнительный regrasp часто вредит |
| Preserve probe + regrasp | 145 | 75.52 | Primary −3.13п.п. к physical, CI[−6.25,0], NO-GO |
| Oracle calibrated | 156 | 81.25 | GT, только диагностика |
| Oracle physical workspace | 167 | 86.98 | GT+расширенный допуск, не deployable method |

Preserve-only по post-hoc сравнению с physical: +5.21п.п., CI[3.13,7.81],
11/1, cluster sign-flip p=.09587, **не подтверждённый новый выигрыш**.
Primary vs preserve-only:0 rescue/16 harm, все16 drop вt82–85 во время
regrasp. До него цель и рука с контактом перемещались примерно на32мм:
новое раскрытие захвата разрушает удержание. Это8 prefixes/6init clusters,
не16 независимых сцен. Все шесть predeclared Holm tests >.05.

**[Decoder-medoid: H16, fixed-seed и H8 контроли](../../experiments/DECODER_MEDOID_RESULTS_20260912.md).**
Полный rollout сt0, K3 joint, все10 задач,60 случаев на каждый factor.

| H16 метод | Success /180 | Macro-SR,% | Вывод |
|---|---:|---:|---|
| First K1 | 105 | 58.33 | Без candidate selection |
| Max-value K3 | 112 | 62.22 | Baseline |
| Action-medoid K3 | 110 | 61.11 | Не превосходит baseline |
| Decoder-medoid K3 | 112 | 62.22 | 7/7; Δ0, CI[−3.33,3.33]п.п. |
| Fixed candidate1 K1 | 110 | 61.11 | Близок к decoder без K3 selection |
| Fixed candidate2 K1 | 109 | 60.56 | Добавленный gain decoder не доказан |

В каждой seed group decoder выбирает один любимый noise seed в81–84%
queries, хотя строго постоянный index только в40/180episodes. Это
описательная seed affinity, не доказательство постоянного selector.
Main Environment26/60 против24/60 max; Position29/60 против31/60.
Нельзя сравнивать62.22% с54.77% valid199 как эффект нового метода.

H8 subset другой:120cases,30Object/30Environment/60Position, macro выравнивает
factors. Max H16=65.00%, decoder H16=66.11%; max H8=59.44%, full decoder
H8=57.78%, prefix decoder H8=59.44%. Prefix не лучше max H8; обе оценки
не означают одинаковое число success. Логических candidate evaluations
примерно вдвое больше при H8, все основные CI разности включают0.

**Решение:** широкий consensus/always-H8 sweep не оправдан этим результатом.
Сохранить как отрицательный architecture-transfer evidence со строгими
controls. Следующая наиболее конкретная гипотеза: не разрушать удержание
при observation/recovery, заморозить preserve-only comparator и подтвердить
на новых init. GT-motion использовать для offline labels, не как online input.

## 5. Формулы, которые объясняют результаты

### 5.1. Разброс не равен полезности выбора

Для $K$ chunks $A_i\in\mathbb R^{T\times d}$ наш типовой sample dispersion:

$$
\bar A_{h,j}=\frac1K\sum_i A_{i,h,j},\qquad
U_A(o)=\frac1{Td}\sum_{h,j}\sqrt{\frac1K\sum_i(A_{i,h,j}-\bar A_{h,j})^2}.
$$

Это средний **std**, не средняя variance; используем population $ddof=0$.
Value range = $\max_iV_i-\min_iV_i$ внутри одного query, не за весь эпизод.
Latent-copy std измеряет несогласованность повторённых записей **одного**
candidate, а не независимые модели. [Точные разновидности метрик](../../experiments/LIBERO_COMPLETE_RESULTS_20260724.md).

$$
\arg\max_i[V_i-\lambda U(o)]=\arg\max_iV_i.
$$

Если uncertainty одна на всё состояние, такой штраф **вообще не меняет
ranking**. Для выбора требуется $U(o,A_i)$; для trigger подходит state-level
score. Даже candidate-specific uncertainty может штрафовать правильное,
но редкое действие.

### 5.2. Что нужно предсказывать

$$
p_i(o)=\Pr(Y=1\mid o,A_i,\pi_{suffix}),\qquad
\tau_{recover}(o)=\mathbb E[Y_{recover}-Y_{continue}\mid o].
$$

Первая функция ранжирует actions с учётом продолжения, вторая оценивает
пользу вмешательства. Ни одну из них нельзя заменить только failure score
$\Pr(Y=0\mid o)$ или ошибкой future image/proprio.

$$
\widehat p_i=\frac1R\sum_rY_{ir},\qquad
G_{select}=\max_i\widehat p_i-\widehat p_{\arg\max_iV_i}.
$$

Это diagnostic opportunity: максимум на тех же repeats оптимистичен.
Для честного результата candidate выбирается на одних suffix seeds,
оценивается на других; группы task/init не смешиваются между train/test.

### 5.3. Следующая гипотеза, не готовый результат

$$
u^*(o)=\arg\max_{u\in\{continue,select,observe,recover\}}
\left[\widehat{\mathbb E}(Y\mid o,u)-\beta C(u)-\gamma\widehat{P}_{harm}(o,u)\right].
$$

$C(u)$ включает model calls, latency и **совершённые физические действия**.
Это постановка cost-aware intervention selection, не доказанно новый алгоритм.
Ближайшие prior art и наши отличия описаны в [сравнении статей](RELATED_WORK_RESULTS.md).

## 6. Что можно писать для ICLR

**Защищаемый сейчас вывод:** на frozen Cosmos в наших LIBERO-PRO постановках
uncertainty и self-consistency сами по себе не обеспечили устойчивого
улучшения action selection. Условные recovery/feedback interventions иногда
дали большие gains, но эффект зависит от состояния, информации и контроля.

**Не писать:** «наш planning SOTA», «uncertainty заранее гарантирует fail»,
«мы опровергли KeyStone/KDPE», «+28% на всём LIBERO-PRO», «t=72 универсален»,
«preserve-only доказанно лучше на всём benchmark» по одной development cell.

Моя оценка готовности: **сильная заготовка для диагностической статьи,
но не завершённая история нового универсального метода**. Нужны одна
центральная проверяемая гипотеза и independent confirmation, а не ещё один
выбранный post-hoc коэффициент. Это оценка проекта, не прогноз решения PC.
ICLR прямо допускает вклад без SOTA, но требует значимого нового знания и
обоснованных утверждений. [Официальное руководство reviewers ICLR2026](https://iclr.cc/Conferences/2026/ReviewerGuide).

Приоритет для рукописи:

1. Две ночные серии закрыты. Сохранить нулевой результат decoder и
   отрицательный primary recovery; GT и технические arms вне основного SR.
   Разобрать физический harm и seed affinity как отдельные механизмы.
2. Зафиксировать один основной comparator, estimator, primary metric и MDE;
   новый holdout отделить по init и по действительно unseen cells/tasks.
3. Для selector проверить одинаковые pools, suffix repeats, K1/maxV/medoid
   и compute-matched budget. Для recovery обязательно full-regrasp,
   probe-always и physically executable fallback.
4. Проверить перенос вне выбранного t=72; если сохраняется fixed boundary,
   сформулировать узкий conditional claim, не событийный fail detector.
5. Для model-agnostic claim добавить второй backbone. Для Cosmos-only
   diagnostic paper честно ограничить область и воспроизвести совместимые
   литературные baselines. Real robot полезен, но не формальная гарантия принятия.

## 7. Графики, видео и исходники

| Что посмотреть | Где |
|---|---|
| Последняя recovery-серия: методы, график и выбранные видео | [Полный разбор](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md) |
| Последний decoder-medoid: full H16/H8, fixed seeds, все видео | [Полный разбор](../../experiments/DECODER_MEDOID_RESULTS_20260912.md) |
| Майская paired video gallery | [Все четыре стратегии](../../experiments/uncertainty/planning_video_export_20260529/all_videos_by_seed.html) |
| Adaptive / surrogate графики с объяснением | [Notebook](../../experiments/LIBERO_SURROGATE_REQUERY_RESULTS.ipynb) |
| Основные valid199 CSV и figures | [Matched analysis](../../experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/) |
| P3c результат и статус демонстрационных видео | [Отчёт](../../experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md) |
| Probe–verify–repair, 48 групп | [Видео](../../experiments/campaigns/probe_verify_repair_20260910_v2/analysis/screen/videos.html) |
| Grounded mask screen / transfer | [Screen](../../experiments/campaigns/grounded_probe_20260911_v2/analysis/screen/videos.html), [transfer](../../experiments/campaigns/grounded_probe_20260911_v2/analysis/transfer/videos.html) |
| Timing, выбранные примеры и все480ветвей | [Избранные](../../experiments/campaigns/timing_eligibility_20260911_v2/review_20260911/selected_videos.html), [все](../../experiments/campaigns/timing_eligibility_20260911_v2/analysis/screen/videos.html) |
| Полный каталог источников и их SHA256 | [Markdown](RESULTS_INDEX.md), [CSV](results_index.csv) |

Галереи с относительными путями открывать из полного проекта. Ссылка на
видео сама по себе не подтверждает statistical identity: проверять run ID,
frame_t, initial snapshot, seed и отметку replay в исходном отчёте.

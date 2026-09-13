# Эксперименты

**13 сентября: продолжение запущено, grounding diagnostic в отдельной очереди.**
[Постановка, arms, ресурсы, technical gates и команды статуса](RECOVERY_GROUNDING_DIAGNOSTIC_PROTOCOL_20260913.md).
Прежний main/timing продолжается без изменения научного config; cutoff21:12MSK.
Отдельно32prefix geometry, 128matched diagnostic outcomes, затем4event-shadow
rollout. Oracle использует GT только как явную диагностику, не новый метод.
Обе очереди idle-only с общими GPU locks; чужие4/5 на старте не трогаем.
Ниже исторический срез до возобновления; его числа не являются текущим прогрессом.

**13 сентября, разбор фактических результатов: серия recovery прервана.**
[Результаты, таблицы, графики, диагностика и следующий план](RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md).
Main441/512, полностью сопоставлены108/128 cases; timing0/768.
Знакомые cells: physical40/61 противH8 16/61; x0.3:1/47 против0/47.
Preserve-only не добавил SR. Offline XY-error локализатора: медиана2.53см
против23.50см наx0.3. Сначала проверка геометрии/локализации, затем event sweep.
Старый `sequence_status.json` завис в `running`: PID отсутствуют;
[проверенный операционный срез](campaigns/recovery_confirmation_20260913/analysis/review/operational_status.json).
Новый GPU-run этим разбором не открыт. Числа предварительные, без final inference.

**13 сентября: событийные версии вместо обязательного t72.**
[Что изменено, четыре метода и команды](EVENT_FEEDBACK_MIGRATION_20260913.md),
[обзор литературы и формулы](../articles/EVENT_TRIGGERED_FEEDBACK_REVIEW_20260913.md).
Новый entrypoint `collect_event_feedback.py`; старые fixed-q4 collectors
остаются архивными контролями. GPU-результатов нового event controller пока нет.

**13 сентября: финальная двухдневная программа и девятичасовая очередь.**
[План, задачи, методы, контроли и команды](RECOVERY_TWO_DAY_PLAN_20260913.md).
Кампания `recovery_confirmation_20260913`: P3/preserve, перенос на x0.3,
контроль времени t56/72/88; до1289 исходов, полные видео сt0.
Результаты в `analysis/`; актуальность `sequence_status.json` проверять по PID
и времени обновления. Для прерванного запуска см. аудит статуса выше.

**Единая сводка для публикации, 12 сентября:**
[Все результаты и анализ, включая отрицательные проверки](../publication/iclr2027/RESULTS_AND_ANALYSIS.md).
[Результаты похожих работ и сопоставимость](../publication/iclr2027/RELATED_WORK_RESULTS.md),
[каталог локальных отчётов](../publication/iclr2027/RESULTS_INDEX.md).
Это основной вход для чтения итогов; ниже сохранена история запусков.
Исторические статусы ниже не являются live-статусом очереди.

**12 сентября: обе ночные серии полностью завершены и разобраны.**
[Observation Contract: SR и вывод по восьми arms](OBSERVATION_CONTRACT_RESULTS_20260912.md):
1536/1536, завершение01:48MSK. Primary145/192 против151/192старогоrecovery,
NO-GO; preserve-only161/192, но netgain в однойcell. В16harms дополнительный
regrasp раскрывает удерживаемыйпредмет. Все1560видео соsmoke декодированы.
[Decoder-medoid: main, fixedseeds, H8, формулы и полные видео](DECODER_MEDOID_RESULTS_20260912.md):
1440/1440, завершение07:31MSK. Decoder=max-value112/180=62.22%; H8/prefix
gain не подтверждён. Новые результаты в общем hub и evidence ledger E16–E19.
Новых GPU-run при этом анализе не запускали. Планы запуска ниже исторические.

**Ночь 11-12 сентября: deadline 10:00 MSK.**
[План, контроли seed/H8, ресурсы и команды статуса](DECODER_MEDOID_NIGHT_20260912.md).
После Observation Contract: сначала исходные 720 rollout decoder-medoid,
затем 360 fixed-seed controls, затем до 360 H8 controls. До 1440 новых rollout;
расчёты до 09:40, затем автоматические отчёты. Чужие GPU-процессы не затрагиваются.
Полное выполнение зависит от доступности GPU, дедлайн автоматически не продлевается.

**11 сентября: новая проверка decoder action-token medoid из Robotics_project_YSDA.**
[Источник, формулы, архитектурная адаптация и протокол 720 rollout](DECODER_TOKEN_MEDOID_PROTOCOL_20260911.md).
K3/H16, 10 задач, Object/Environment/Position, три фиксированные seed groups;
controls: K1, max-value, action-medoid. Полные эпизоды с t=0, без regrasp/t72.
Локальный hook-parity прошёл; серверная очередь должна идти после текущей
Observation Contract. [Фактический статус](campaigns/decoder_token_medoid_20260911/sequence_status.json).
Чужой лучший GR00T результат 66/96 не повторился на двух других группах;
перенос на Cosmos пока не доказан. Новый отчёт и видео будут в `analysis/`
внутри каталога кампании; локальные integration smoke в основные SR не входят.

**11 сентября, 20:23 MSK: запущена Observation Contract.**
[Протокол, гипотезы, формулы и восемь ветвей](OBSERVATION_CONTRACT_PROTOCOL_20260911.md).
24 технические проверки, затем 1536 ветвей: 96 прежних prefixes, два suffix
seed, шесть обычных политик и два privileged diagnostics. Не новый init
holdout; преимущества пока не установлены. Проверяем получение наблюдения
без смены gripper-команды и отдельно вклад локализации/области допуска.
[Акт запуска и расположение данных](campaigns/observation_contract_20260911/LAUNCH_VERIFIED.md).

**11 сентября, 15:09 MSK: timing/eligibility завершена, 490/490ветвей.**
[Результаты, объяснения, таблицы и следующие проверки](TIMING_ELIGIBILITY_RESULTS_20260911.md).
96paired states: continue63/96, immediate76/96, fresh/checked74/96,
diagnostic76/96. Новый controller не превзошёл immediate; frozen gate NO-GO,
holdout38–45 закрыт. Checked иfresh совпали по96labels и93траекториям.
Снятие остальных fresh guards дало3rescue наjuice и1harm наtomato sauce;
в harm полныйregrasp не исполнялся, был только3-stepretreat.
Все17общихfailures не прошли исходный trigger: recovery на них не проверялся.
Все490видео скачаны и декодированы,59174кадра;79тестовpassed.
[Выбранные видео](campaigns/timing_eligibility_20260911_v2/review_20260911/selected_videos.html),
[все480основныхвидео](campaigns/timing_eligibility_20260911_v2/analysis/screen/videos.html),
[замороженный протокол и история технического запуска](TIMING_ELIGIBILITY_PROTOCOL_20260911.md).
Новых GPU-run при этом анализе не запускали. Следующий приоритет: passive/
two-viewverification, non-openingretreat и аудит coverage исходногоtrigger.

**11 сентября: grounded-mask и delayed recovery завершены, 576 ветвей.**
[Результаты, причины, таблицы, графики и видео](GROUNDED_PROBE_RESULTS_20260911.md).
Screen: continue27/48, full33/48, probe-always и conservative35/48,
miss-only/legacy29/48, delayed34/48. Gate NO-GO, holdout не открывался.
Transfer: full36/48, continue/delayed33/48. Завершено в03:56MSK.
На27пробах маска убрала10наблюдавшихся false-held, но8ответов превратились
вunknown; conservative повторяет probe-always по всем outcomes и47/48
полныхтраекторий. Дополнительный выигрыш verifier не установлен.
[Screen-видео](campaigns/grounded_probe_20260911_v2/analysis/screen/videos.html),
[transfer-видео](campaigns/grounded_probe_20260911_v2/analysis/transfer/videos.html).
Далее разнести delay и повторный trigger; не расширять текущий sweep.
Новых GPU-run при анализе не запускали. Ниже сохранены прежние результаты.

**11 сентября: последний probe/verify/repair завершён, NO-GO.**
[Полный разбор: SR, парные эффекты, причина ошибок, графики и видео](PROBE_VERIFY_REPAIR_RESULTS_20260911.md).
24 smoke и 192/192 screen: continue26/48, full regrasp35/48, probe26/48,
verified30/48. Новый метод −10.42п.п. к сильному контролю, 4 rescue / 9 harm.
Семь ложных `held`: неподвижный предмет, нет контакта, crop следует за рукой.
Holdout не открыт; сбор завершён 10 сентября в23:50 MSK. Результаты скачаны
локально, повторный integrity и 26 CPU-тестов прошли.
[Все 48 групп видео](campaigns/probe_verify_repair_20260910_v2/analysis/screen/videos.html).
Далее object-specific tracking и отделение эффекта пробы от gate;
новые GPU-эксперименты этим анализом не запущены. Статусы ниже исторические.

**Вечер 10 сентября: обе последние серии завершены.**
[Итог P5 690/690 и feedback 120/120: результаты, выводы и видео](P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md).
[Новый порядок исследований](RESEARCH_PRIORITIES_20260910_EVENING.md).
[Следующая кампания: probe → verify → repair](PROBE_VERIFY_REPAIR_PROTOCOL_20260910.md).
V2 запущена в 22:41 MSK, dispatcher 33728, GPU1/3/6. В 22:50 все 24 smoke
прошли технический аудит, начат основной screen. Затем условный holdout.
V1 technical smoke сохранён отдельно, в SR не включается.
Утренние сообщения «ждёт P5» и «screen ещё не начался» ниже являются историей.

**Актуальные приоритеты после двух аудитов:**
[Научный план, лучшие результаты и статус методов](RESEARCH_PRIORITIES_20260910.md).
[Следующий исполнимый screen: 15 smoke + 120 matched-K/continuity ветвей](FEEDBACK_CONTROLS_PROTOCOL_20260910.md).
Доставка завершена: серверный PID3878088 ждёт существующую P5-очередь.
В завершённой conditional части P5 pool13: max-value1/10, alternatives10/10;
это пока один snapshot, не переносимый planner. Новый screen ещё не начался; live status
смотреть в campaign, не в исторических строках ниже.

**10 сентября: проверка fresh8.** [Индексы, свежие входы, причины меньшего SR и сравнение с K4/t72](FRESH8_IMPLEMENTATION_AUDIT_20260910.md).
1080 ветвей проверены; 21 CPU-тест прошёл. В последнем опыте K8-selected tail
заменяется одиночным K1 sample. Общий минус статистически неубедителен;
прежний положительный K4/t72 результат `46/100 -> 64/100` сохраняется.
Добавлены action-boundary метрики и раскадровки harm/rescue без новых GPU-run.

**10 сентября: аудит P3c/P3d.** [Ошибки, ограничения trigger и причины меньшего прироста](P3C_IMPLEMENTATION_AUDIT_20260910.md).
167 cases / 421 branch сверены с raw-данными; `13/40 -> 24/40` подтверждено.
Два drop harm происходят после вмешательства в уже поднятый предмет.
Все 7 P3d новых cells ранее встречались в обучении локализатора, но без
init overlap. Нефизичный post-retreat fallback найден, срабатываний в этих
данных нет. 30 CPU-тестов прошли; исходный controller и P5 очередь не менялись.

**10 сентября, 12:09 MSK: smoke пройден, идёт conditional replication.**
[Протокол 690 ветвей + 6 smoke, метрики и команда статуса](P5_CANDIDATE_REPLICATION_PROTOCOL_20260910.md).
Те же pool13/pool11: зафиксированные baseline/alternatives и 10 новых suffix
seeds. Отдельно tasks0/2 x init9-12: новые K8 pools, local H16 signals,
split-repeat diagnostic. Это не новый trained planner и не перенос старых
candidate indices. Автономный PID3818565, основная серия на GPU0/3/5;
6/6 smoke-веток и видео проверены. Поправка записи векторных signals
сохранена отдельно, научный протокол не изменился. Основные результаты
будут в campaign analysis; 39 CPU-тестов прошли локально и на сервере.

**10 сентября: P5 repeats/feedback завершён, 1080/1080.**
[Результаты, объяснение, графики и 108 видео](P5_REPEAT_FEEDBACK_RESULTS_20260910.md).
Завершено в 04:32 MSK. Fresh8: 41/108 против open16 44/108 и stale8 45/108;
оба cluster CI разницы включают ноль. У 96/288 кандидатов меняется suffix label.
K8 gain +14.81 п.п. при выборе и оценке на тех же repeats исчезает при
leave-one-suffix-out: 44/108, как у max-value. Обученный новый P5 не запускался.
Приоритет: точечная replication устойчивых misranking cases и task/contact
labels, не широкий sweep. [Исходный протокол](P5_REPEAT_FEEDBACK_PROTOCOL_20260910.md).

**10 сентября: ночная очередь полностью завершена.**
[Итог consensus и P5: методы, таблицы, ограничения и следующие выводы](CONSENSUS_AND_P5_RESULTS_20260910.md).
В сравнении 1194 rollout / 6 методов / 199 конфигураций KeyStone-style дал
55.76% macro-SR против 54.77% max-value; убедительного превосходства нет.
P5 pilot: 36/36 strict pools, 288 branches, 16 mixed, но при K8 только
1 исправимый max-value fail и 17 all-fail pools. Обученная P5-модель ещё
не тестировалась. Все стадии закончились 9 сентября в 20:31 MSK;
нижние статусы запуска и ожидания являются историческими срезами.

**Постоянный GPU-worker, 9 сентября:** [протокол, проверка cold/resident,
сохранение видео и безопасное переключение](RESIDENT_WORKER_PROTOCOL_20260909.md).
Проверено повторное использование модели A/B/A: действия, value, latent и
реальное видео совпали с контролем. Межпроцессные image diagnostics и
невоспроизводимый повтор самого cold executor разобраны отдельно.
Внедрено в 19:20 MSK: оставшиеся 24 reference jobs распределены по 8 на
GPU1/2/3; 333 готовых markers сохранены. P5 executor не менялся.

**9 сентября, 13:44 MSK: GPU0-7 разрешены при незанятости.**
Очередь перезапущена, PID2694673; 368 reference rollout сохранены.
Занятые карты пропускаются, включая карты с низкой загрузкой, но чужими
CUDA-процессами. [Ресурсная политика и проверки](GPU07_RESOURCE_POLICY_20260909.md).

**Текущий план, 9 сентября 13:10-13:13 MSK:**
[что уже доказано, статус расчётов и ближайшие быстрые проверки](RESEARCH_PRIORITIES_20260909.md).
References **367/597**, процесс жив, но ждёт освобождения GPU; P5 ещё не
стартовал. [Уточнение будущего P5](P5_TASK_CRITICAL_REFINEMENT_20260909.md)
отделяет diagnostic pilot от обучения task-critical selector. Работающая
очередь и frozen configs этим обновлением не менялись.

**Решение по t=72 и recovery:** [почему сохраняем фиксированный контроль,
как проверить время вмешательства и переходить к событийному trigger](RECOVERY_TIMING_DECISION_20260909.md).
Это план следующей проверки recovery, не уже запущенная кампания.

**9 сентября 01:18 MSK, ресурсы:** ночная очередь переведена на свободные
GPU **1-7**, GPU0 исключена. Задания общие, занятая GPU не резервирует работу.
Новый PID 2181819; готовые эпизоды сохранены, включено продолжение по эпизодам.

**9 сентября, ночная очередь запущена в 01:01 MSK:** compact остановился на 597/600 из-за пустого
init asset `y0.5/task1`, не из-за трёх policy fail. Новый valid-support анализ
содержит 199 случаев. [План закрытия consensus и P5 data pilot](CONSENSUS_P5_NIGHT_PROTOCOL_20260909.md):
597 reference rollout после smoke, затем 36 K8 development pools / до 288
terminal branches. Старые результаты и frozen настройки не изменяются.
На всех 199 доступных случаях macro-SR medoid **54.09%**, max-value **54.77%**,
K1 **53.43%**; 3 rescue / 6 harm. Все три smoke проверены; в 01:08 основная
reference-серия стартовала на GPU3. P5 pilot ждёт завершения этой серии.
[Завершённый valid-support анализ](campaigns/trajectory_consensus_20260909_valid199/trajectory_analysis/RESULTS.md).

**Исторический срез, 8 сентября 18:30 MSK:** compact **539/600**; на 179 полных
тройках OSC medoid имеет macro-SR **55.88%**, max-value **56.90%**, K1 **55.39%**.
Medoid: 3 rescue / 6 harm против max-value. Это промежуточные результаты,
не итог: Position ещё неполон, reference600 ждёт окончания compact.
[Таблицы, графики, объяснения и сравнение постановок KeyStone/KDPE](TRAJECTORY_CONSENSUS_INTERIM_RESULTS_20260908.md).

**Следующий этап для ICLR:**
[протокол и очередь matched references](CONSENSUS_REFERENCE_PROTOCOL_20260908.md),
[завершённый common-pool анализ](CONSENSUS_COMMON_POOL_RESULTS_20260908.md).
На 194 проверенных K4 pools OSC-medoid дал 104 success против 111 у max-value;
в 69 pools все кандидаты fail. Это exploratory на старых данных, не compact600.
Новая автономная цепочка стартовала в 14:32 MSK: ждёт compact, затем выполняет
3 smoke и 600 matched rollout для raw medoid / KeyStone-style / KDPE adaptation.

**ICLR: разбор последнего trajectory-consensus**:
[формула, development 392/392, ограничения и ближайшие проверки](TRAJECTORY_CONSENSUS_ICLR_ASSESSMENT_20260908.md).
Medoid: macro-SR 59.17% против 57.50% max-value, CI разницы [-3.33; +8.33] п.п.
Эти development-числа не являются результатом compact. Историческое состояние
связи около 14:00 сохранено в отчёте; актуальный срез compact приведён выше.

**Общий научный итог:** [лучшие методы, подтверждённые результаты,
ограничения и готовность к публикации](RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md).
Разделены gains recovery, feedback и candidate ranking; внутренний PASS
не отождествляется со статистически доказанным новым методом.

**8 сентября: P4c2 сокращён до 600 rollout по запросу пользователя.**
Development 392/392 завершён; заморожен `trajectory_medoid` K4.
Сравниваем K1 / max-value K4 / medoid K4: все 10 задач и три фактора,
по 200 rollout на метод. 35 готовых эпизодов перенесены с сохранением seeds.
Новая общая очередь использует свободные GPU **3-7**. Исходные 4500 не
выдаются за завершённый full benchmark. [Текущий протокол и статус](TRAJECTORY_CONSENSUS_COMPACT_PROTOCOL_20260908.md).

**Исходный план P4c2 до сокращения.**
Trajectory medoid / density / value-density используют OSC-scaled induced
poses и осторожный normalized-value gate. Offline 32 настройки на 194 exact
состояниях пока не дали убедительного выигрыша. Автономная цепочка на GPU6-7:
7 smoke -> 392 development -> freeze -> 4500 full rollout; все 10 Object-suite
задач, Object/Environment/Position. Это новая проверка, старый NO-GO не отменён.
[Формулы и протокол](TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md),
[статус, команды и результаты](TRAJECTORY_CONSENSUS_RUN_20260908.md).
Smoke 7/7 проверен; development завершён. [Первые результаты и семь видео](TRAJECTORY_CONSENSUS_SMOKE_RESULTS_20260908.md).

P4c consensus-medoid завершён: 180/180 development rollouts и 6 smoke.
Pure medoid K3 дал 7/40 success против 8/40 у max-value и 12/40 у K1.
В отдельном K5 screen Cosmos guarded получил 6/20 против 5/20 у max-value:
`+5 п.п.`, CI `[-15; +25]`, 3 rescue / 2 harm, drop-прокси 2 против 1.
KeyStone-style K5 получил 3/20. Development gate не пройден; продолжаем к P5,
consensus сохраняем для дешёвого offline within-pool анализа.
Selector воспроизведён на 9287/9287 queries. Ошибки future prediction здесь
не интерпретируем: prediction H16 сравнивался collector-ом с observation H5.
Результаты, графики, ограничения и следующие шаги:
[`CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md`](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md).
Протокол, автономный запуск и источник:
[`CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md`](CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md),
[`CONSENSUS_MEDOID_PRE_P5_RUN_20260907.md`](CONSENSUS_MEDOID_PRE_P5_RUN_20260907.md),
[KeyStone](https://arxiv.org/abs/2605.08638).

P4b residual-risk prospective holdout завершён с **NO-GO**. Все 6/6 jobs,
200/200 K4 snapshots и 800/800 terminal branches завершены. Frozen
`mean_plus_epistemic_rms`, $\lambda=2$, уменьшил realized H16 residual на 2.14%,
но снизил terminal SR с 117/200 (58.5%) до 113/200 (56.5%): `-2.0 п.п.`, CI
`[-5.5; +1.5]`, 4 rescue / 8 harm. Global failure AUROC 0.650 оказался
межсценарным difficulty signal: within-pool ranking на 114 success/fail pairs
равен 0.509. Следовательно, residual risk сохраняется для OOD/compute routing,
но закрывается как прямой candidate penalty. Полный разбор, frozen protocol и
автономный запуск:
[`P4B_RESIDUAL_RISK_PROTOCOL_20260907.md`](P4B_RESIDUAL_RISK_PROTOCOL_20260907.md),
[`P4B_RESIDUAL_RISK_RUN_20260907.md`](P4B_RESIDUAL_RISK_RUN_20260907.md),
[`P4B_RESIDUAL_RISK_RESULTS_20260907.md`](P4B_RESIDUAL_RISK_RESULTS_20260907.md).

P4 independent residual-dynamics ensemble завершён со статусом
**completed_no_go**. Все 10 standard-LIBERO ID jobs и 5,668 transition rows
целостны; пять frozen Gaussian heads обучены и проверены по SHA256. Однако
primary quadratic JRD после nonnegative clamp равен нулю на всех строках:
pooled OOD balanced AP 0.308, residual Spearman NaN, hard-filter selection
change 0%. Поэтому closed-loop stage не открывался. Post-hoc
`ensemble_epistemic_mean` связан с realized error (`rho=0.609`) и силён на
Environment (balanced AP 0.795), но не переносится устойчиво на Object/Position.
Полный разбор:
[`P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md).

P3e Recovery Outcome Ensemble завершил frozen holdout со статусом **PASS**.
На untouched init 45--49 все 75/75 cases и 225/225 exact-state branches прошли
replay, feature и fallback integrity. Router улучшил full RGB regrasp с 53/75
до 55/75: **+2.7 п.п.**, group CI `[0.0; +6.7]`, 2 rescue / 0 harm. Оба
rescue повторили harmful full-regrasp pattern `x0.2/task2` на новых init 47 и
49, устранив два drop+timeout. Drop proxy снизился с пяти до трёх, primitive
cost также уменьшился. McNemar `p=0.5`, а holdout содержит те же cells, поэтому
это preliminary narrow safe-routing result, не широкий transfer claim. Полный
разбор:
[`P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md`](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md).

P3d new-cell transfer и mechanism ablation завершён с **development NO-GO**,
а не runtime failure. Все 75/75 cases и 225/225 branches завершены с exact
snapshot replay и корректным fallback. Full RGB regrasp снова силён на
replication cells: 15.0% -> 62.5%, +47.5 п.п. На семи новых cells результат
равен 74.3% -> 88.6%, +14.3 п.п., но CI `[-2.9; +31.4]`, 7 rescue / 2 harm и
McNemar `p=0.180`, поэтому holdout не открывался. Retreat-only дал лишь
+5.7 п.п. на новых cells. Полный разбор:
[`PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md`](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md).

P3c online RGB-triggered regrasp завершён с **confirmatory PASS**. Screen и
development прошли последовательно, после чего untouched 40-case holdout дал
13/40 success у `baseline_h8` и 24/40 у frozen controller: **+27.5 п.п.**,
paired 95% CI `[+12.5; +42.5]`, 12 rescue / 1 harm, exact McNemar
`p=0.00342`. Replay integrity равна 40/40, drop и official safety не выросли,
wrong-object rate уменьшился с 10% до 2.5%. P3d выше ограничил этот вывод
знакомыми perturbation cells. Полный разбор:
[`PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md`](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md).

P3b perception-backed regrasp завершил все последовательные gates с итогом
**PASS**.
Strict RGB calibration содержит 388 states / 194 `task/init` groups и не
пересекается по группам с downstream evaluation. CLIP localizer провалил OOF;
DeepLab heatmap снизил pixel p90 с 41.65 до 4.12 px, а object-routed depth
прошёл frozen gate с median/p90 XY 1.64/3.33 cm. Clean screen после исправления
raw-camera orientation спас 11/20 states (55%, CI [35%; 75%]) в шести cells и
четырёх tasks. Full development спас 49/80 (61.25%, cluster CI
[50.62%; 71.43%]) при 100% replay integrity и без роста drop/safety rate.
Primary confirmatory reserve из 72 строк / 47 отсутствующих в development
групп подтвердил результат: 43/72 (59.72%, CI [45.20%; 73.91%]), 11 cells,
8 tasks, formal gate **PASS**. Wrong-object rate вырос на 20.83 п.п., поэтому
следующий этап -- observable trigger/shield на новых full episodes. Протокол и
таблица:
[`PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md),
[`PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md`](PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md).

P3 recovery-proposal opportunity campaign завершила 240/240 strict exact-state
веток. Frequent H4 re-query спас 7/80 состояний, lift-and-hold 8/80, но оба
deployable варианта провалили frozen gates. Privileged regrasp upper bound с
истинной позицией объекта спас 62/80 и покрыл все 11 успехов deployable
эвристик. Это переносит следующий приоритет с reranking на perception-backed
contact recovery. Полный разбор, frozen protocol и карточка запуска:
[`RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md),
[`RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md),
[`RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md).

Privileged context-interaction P2d upper bound завершён. Внутри известных
task/level cells модель действительно ранжирует пользу feedback: adjusted gain
+2.78 п.п., CI `[+0.71; +4.89]`, AUROC 0.812. Но при leave-one-task/level/cell
переносе эффект равен -0.19/-0.19/+0.13 п.п., AUROC 0.463/0.438/0.486, а все
CI пересекают ноль. Даже task identity, perturbation geometry и privileged
phase не дают OOD-инвариантного sign-VoF. Gate **FAIL**, re-query CATE branch
закрыт; следующий приоритет P3 - oracle coverage новых retreat/regrasp recovery
proposals на состояниях, где commit и feedback оба fail. Полный разбор:
[`CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md`](CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md),
[`CONTEXT_INTERACTION_UPPER_BOUND_PROTOCOL_20260903.md`](CONTEXT_INTERACTION_UPPER_BOUND_PROTOCOL_20260903.md).

Object/contact-conditioned P2c development screen завершён на объединённом
корпусе из 640 strict exact-state пар. Frozen CLIP ViT-B/32 признаки текущих и
предсказанных agent/wrist кадров распознают часть contact/event информации, но
не переносят знак causal feedback value. Лучший overall selector остался
`relative` control с worst-split adjusted uplift -0.50 п.п.; лучший object
selector дал -1.28 п.п., а все cluster CI пересекли ноль. Все frozen gates
**FAIL**, поэтому новый holdout не запускается. Следующий дешёвый шаг -
неdeployable task/perturbation/phase interaction upper bound на том же открытом
корпусе. Полный разбор:
[`OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md`](OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md),
[`OBJECT_CONTACT_VOF_DEVELOPMENT_PROTOCOL_20260903.md`](OBJECT_CONTACT_VOF_DEVELOPMENT_PROTOCOL_20260903.md).

Prospective support-aware invariant-CATE reserve holdout завершён на 400/400
strict exact-state парах из десяти заранее выбранных LIBERO-PRO Object
Position cells. Frozen router запросил feedback в 39.5% состояний, но снизил
SR с 57.0% до 55.75%: raw -1.25 п.п., adjusted -2.24 п.п., cluster CI
`[-5.52; +1.13]`, 18 rescues / 23 harms и AUROC 0.544. Primary efficacy gate
**FAIL**, P2b закрыт. Router при этом превзошёл вредный always re-query на
+8.01 adjusted п.п., CI `[+3.66; +12.59]`, а oracle gap остался +9.5 п.п. при
9.5% запросов. Главный sign reversal: `y0.1/task4` имел +25 п.п. в
development, но `y0.2/task4` дал -22.5 п.п. в holdout; геометрический KNN
support не распознал causal shift. Следующий stage должен быть
object/contact-conditioned и моделировать interaction с perturbation, а не
донастраивать scalar threshold на этом holdout. Полный разбор:
[`INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md`](INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md),
[`INVARIANT_CATE_DEVELOPMENT_RESULTS_20260903.md`](INVARIANT_CATE_DEVELOPMENT_RESULTS_20260903.md),
[`INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md`](INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md).

Prospective signed-VoF holdout завершён на 240/240 strict exact-state парах из
шести новых LIBERO-PRO Object cells. Frozen task-0 ridge дал 59.6% -> 61.7%:
raw +2.1 п.п., cluster CI `[-4.2; +7.9]`, а после query cost только +0.8 п.п.,
CI `[-5.4; +7.0]`. Он выбрал 24 rescues и 19 harms, AUROC 0.398; formal gate
**FAIL**, router не продвигается. Always re-query дал описательные +7.1 п.п.,
а oracle +17.5 п.п. при 17.5% запросов: causal opportunity есть, но нужен
task-invariant, support-aware CATE router. Главная причина провала - сильная
экстраполяция absolute action/proprio признаков (`max |z|=654.9`) и смена знака
эффекта между cells. Подробности:
[`SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md),
[`SIGNED_VOF_ROUTER_DEVELOPMENT_RESULTS_20260903.md`](SIGNED_VOF_ROUTER_DEVELOPMENT_RESULTS_20260903.md),
[`SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_RESULTS_20260903.md`](SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_RESULTS_20260903.md),
[`SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md).

Confirmatory Position-direction holdout завершён на 120/120 strict exact-state
парах. На primary `y0.2` commit-H16 и query-4 feedback дали 53.3% и 55.0%:
**+1.7 п.п.**, init-cluster CI `[-13.3; +16.7]`, 10 rescue / 9 harm, McNemar
`p=1.0` и -0.8 п.п. после query cost. На control `x0.2` эффект также равен
+1.7 п.п.; interaction `y0.2 - x0.2` равен 0 п.п., CI `[-13.3; +13.3]`.
Primary и interaction gates **FAIL**, fixed cross-factor feedback не
продвигается. Сбалансированные `y0.2` outcomes (10 rescue / 9 harm) затем были
использованы как development labels для signed-VoF; его новый untouched
transfer также завершён и описан выше. Полный разбор:
[`OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md`](OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md).

Frozen cross-factor boundary screen завершён на 100 exact-state парах. Integrity
gate прошёл (97/100 strict при минимуме 95). Главный development signal найден
на LIBERO-PRO Position `y0.2`, task 0: query-4 feedback увеличил terminal SR с
40% до 80%, **+40 п.п.**, CI `[+10; +65]`, 10 rescue / 2 harm, McNemar
`p=0.0386`; adjusted gain +37.5 п.п. Position `x0.2` дал 20% -> 15% и остаётся
заранее выбранным negative control. Environment оказался floor, `x0.1` ceiling,
а `y0.3` не набрал frozen support. Это development screen, поэтому следующий
шаг - new-seed holdout на `y0.2` вместе с `x0.2`, а не claim или обучение
selector. Полный разбор:
[`OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md`](OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md).

Frozen shared-prefix replication завершён и закрыл главный causal P0. На 100
exact-state парах для `libero_object_object`, task 0, query-4 feedback увеличил
terminal SR с 46% до 64%: **+18 п.п.**, init-cluster 95% CI `[+4; +32]`,
31 rescue / 13 harm, McNemar `p=0.00956`. Все 100 пар прошли replay integrity,
raw и cost-adjusted эффекты положительны, поэтому integrity, practical и
confirmatory gates **PASS**. Полный разбор:
[`OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md).

Frozen Object task-0 query-4 holdout завершён и дал первый узкий
confirmatory feedback-timing результат. На 60 exact-state парах из 15 новых
init states commit-H16 получил 23/60 success (38.3%), а `H8 -> real observation
-> requery H8` получил 36/60 (60.0%): **+21.7 п.п.**, init-cluster 95% CI
`[+5.0; +40.0]`, 16 rescue / 3 harm, exact McNemar `p=0.00443`. Integrity,
practical и confirmatory gates прошли. Generic uncertainty rankers нашли не
более 1/16 rescues, поэтому подтверждён именно task/query-specific feedback
timing, а не универсальный uncertainty router. Полный разбор:
[`OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md).

Предыдущая серия от 31 августа закрыла три простых feedback-router гипотезы.
Privileged phase routing не улучшил terminal SR. Независимый fixed query-0 H8
holdout дал nominal 23/60 success против 35/60 у H16; strict integrity не прошла
из-за трёх near-tied query-0 argmax, но sensitivity на 57 совпавших candidates
осталась отрицательной (-19.3 п.п.). Затем global CLIP semantic VoF screen на
265 exact states и transfer с Environment tasks 0-3 на 5/8/9 оба не прошли gate:
scalar rho 0.245 против 0.200 у scalar+semantic2, uplift@20% отрицателен.
Результаты и решения:
[`INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md`](INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md),
[`SEMANTIC_VOF_RESULTS_20260831.md`](SEMANTIC_VOF_RESULTS_20260831.md).
Три следующих frozen теста завершены. Untouched-task transfer на Object tasks
1-9 собрал 180/180 exact-state пар, но обе ветви получили 100% SR на каждой
задаче: raw effect 0 п.п., cost-adjusted effect -2.5 п.п.; strict replay прошёл
177/180, поэтому transfer gate FAIL. Первый separate-process deployment на
task 0 дал описательно 46% -> 57% (+11 п.п.), а clean-GPU strict subset 37.5%
-> 52.5% (+15 п.п.), но только 40/100 префиксов были строгими: GPU 2-4
разошлись до вмешательства, GPU 5-6 дали 40/40 bit-identical пар. Frozen
clean-GPU replication также завершилась: nominal SR 35% -> 54% (+19 п.п.,
CI [+9; +29], 25/6 rescue/harm, p=0.000878), но strict prefix прошёл только у
34/100 пар. На них эффект +14.7 п.п., CI [0; +29.4], p=0.1797. Поэтому сильный
положительный deployment signal остаётся описательным, а formal gates FAIL.
Shared-prefix test устранил эту неоднозначность и подтвердил эффект: 46% ->
64%, +18 п.п., CI [+4; +32], 31/13 rescue/harm, p=0.00956, 100/100 strict.
P1 теперь остаётся object/contact-centric consequence model для selective
routing и non-ceiling cross-factor transfer, потому что безусловный task
transfer оказался ceiling.

Подробности:
[`OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md),
[`OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md),
[`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md).
The query reproducibility diagnostic confirmed exact repeatability inside one
process but not across fresh processes; full numbers and the strict-kernel
limitation are documented in
[`COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md`](COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md).

Последний confirmatory transfer проверил causal feedback timing без изменения
candidate selection. На 90 новых paired LIBERO-PRO states frozen router
`Object -> H16`, `Position/Environment -> gripper-H8/H16` получил 47/90 success
против 53/90 у `maxV-H16`: -6.7 п.п., grouped 95% CI `[-13.3; 0.0]`, 2 rescue
и 8 harm. Position ухудшился на 6.7 п.п., Environment на 13.3 п.п.; formal gate
FAIL. Следовательно, post-hoc factor interaction первого 40-state pilot не
перенёсся, а gripper sign change не является достаточным re-query trigger.
Полный frozen разбор:
[`FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md`](FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md).
Предшествующий pilot:
[`REAL_OBSERVATION_REQUERY_RESULTS_20260830.md`](REAL_OBSERVATION_REQUERY_RESULTS_20260830.md).

Итог P0-P2 от 27 августа находится в
[`GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md`](GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md).
На 299 matched episodes на метод `maxV-H16` сохранил лучший factor-macro SR
54.5%; H8 controllers и uncertainty reranking broad-transfer gate не прошли.
P1/P2 pilot собрал 272 exact-state branches, но local VoF оказался полностью
нулевым, а grounded ranker не улучшил Cosmos value. Подробный frozen протокол
находится в
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).
Campaign `pro_object_horizon_controls_p0_20260826` завершила 24/24 jobs.
Статус из WSL:

```bash
scripts/mlspace_experiment_status.sh pro_object_horizon_controls_p0_20260826 --verbose
```

Exact-state P1/P2 collector, schema и utilities описаны в
[`COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md).
Фактический запуск собрал 272/300 states: пять extreme position jobs не
достигли phase-balanced target. Offline-анализ выполнен отдельно; sequence
launcher остановился на campaign `failed`, поскольку неполные phase targets
корректно вернули ненулевой exit code.

Dense endpoint relabel устранил вырожденность local target: среди 272 matched
states получено 127 positive и 143 negative VoF, candidate utility различается
в 271 states. После strict replay filter остаётся 265 states. Object и
Environment проходят mechanism-screening routing, Position пока не имеет
достаточно независимых `task/init` групп; candidate reranking gate не пройден.
Matched H32 pilot затем завершил 48/48 states и 288 branches. H32 уменьшил
non-tied candidate support с 48 до 35 и не улучшил online uncertainty router,
поэтому более длинный consequence horizon закрыт. Новый factor-specific H16
ranker снизил factor-macro regret относительно Cosmos value на 45.7% (42.6%
на strict subset) в screen. Затем неизменённый ranker прошёл confirmatory
holdout на 230 strict states и 69 новых groups: regret уменьшился на 43.1%,
macro CI `[-0.005768; -0.002298]`, formal gate PASS. Это разрешает paired
closed-loop test, но само по себе ещё не доказывает рост terminal SR. Формулы,
controls и screen-таблицы:
[`DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md`](DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md).
Confirmatory дизайн был зафиксирован до сбора данных в
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md).
Итоговый анализ, caveats и следующий closed-loop benchmark:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md).

Paired closed-loop проверка теперь завершена: 360 пар / 720 episodes при
одинаковых шести candidates и H16. Offline regret gain не перенёсся в terminal
success: factor-macro delta ranker против maxV равна -0.28 п.п., grouped 95% CI
`[-2.22; +1.39]`; formal gate FAIL. Environment дал -3.33 п.п., Object оказался
на 100% ceiling, Position дал +2.50 п.п. из трёх редких rescue. Полный результат,
selection mechanism и следующий conservative grounded critic:
[`FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md`](FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md).

Terminal-grounded conservative critic завершён по preregistered gates.
Development собрал 80 states / 640 terminal branches: `max(value)` SR 92.5%,
oracle-in-pool 98.75%, но все 5 rescue сосредоточены в одном task. Untouched
tasks 8-9 оказались полным ceiling: все 160 candidates успешны, поэтому
`max(value)`, critic и oracle имеют 100% SR. Critic сделал 0 переключений;
offline gate FAIL, и 120-pair closed-loop намеренно пропущен. Полный разбор:
[`TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md`](TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md).
Frozen protocol сохранён отдельно:
[`TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md`](TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md).
Проверка завершённой holdout campaign из WSL:

```bash
scripts/mlspace_experiment_status.sh \
  terminal_grounded_critic_20260829__holdout --verbose
```

Cross-campaign opportunity atlas объединил 153 exact-state pools: 15
heterogeneous, 7 rescues, 16 all-fail и 122 all-success. Все terminal rescues
оказались в Object task 0; Environment/Position hard cells пока не имеют
успешной альтернативы в pool. Таблицы и график:
[`campaigns/terminal_proposal_opportunity_atlas_20260830/analysis/RESULTS.md`](campaigns/terminal_proposal_opportunity_atlas_20260830/analysis/RESULTS.md).
K16 screen затем завершил 50 exact states / 800 terminal branches. Proposal
coverage насыщается к K8: K16 не добавил ни одного нового oracle success в
Object или Position. При этом Object имеет 30 п.п. oracle gap, Position-y q0
даёт два rescue, а Environment остаётся полностью all-fail. На девяти mixed
pools `max(value)` выбрал success только в 4/9, pairwise value accuracy 0.476.
Полный результат:
[`PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md`](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md).
Следующий same-pass action-conditioned evaluator также завершён: integrity
PASS, но terminal ranking gate FAIL. На 10 states / 80 одинаковых action
candidates parallel и AR selector дали один rescue и один harm, одинаковый
SR `30%`, а mixed-pool pairwise accuracy снизилась с 0.429 до 0.308. Результат:
[`AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md).
Fallback grounded pairwise ranker также завершён на новых init 10-39.
Development/calibration opportunity прошла, но untouched holdout gate FAIL:
`maxV/raw/gated/oracle = 45/15/30/60%`, 0 rescue / 3 harm. Подробный разбор
distribution shift и bootstrap overconfidence:
[`HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md`](HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md).

Для предшествующего causal результата следует смотреть отчёт
[`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md).
В matched 2x2 на 672 rollout `requery_l1_h8` дал 121/168 success против
100/168 у `max(value)`: +12.5 п.п., 95% CI `[+4.8; +20.8]`, exact McNemar
`p=0.00646`. Horizon-only control дал +8.3 п.п., а один только risk-aware
selection -6.0 п.п. Главный подтверждённый механизм состоит в более раннем
feedback из реальной среды, а не в прямом uncertainty reranking.

Предыдущий этап с future-proprio surrogate описан в
[`SURROGATE_REQUERY_RESULTS_20260820.md`](SURROGATE_REQUERY_RESULTS_20260820.md)
и notebook
[`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb).
Surrogate переносится как оценка next-chunk prediction error, но не улучшил
task success как самостоятельный planner trigger.

Следующие гипотезы и порядок работ после разбора новых статей зафиксированы в
[`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md). Общий разбор
литературы, включая StressDream, UNISafe, AnySafe, tau0-WM, QWM и всю
релевантную линию Junwon Seo, находится в
[`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).
Новая гипотеза о сравнении старого action-tail и нового overlap-prefix,
формулы TIDE/STAC-style metrics, learned baseline и полный план проверки
находятся в
[`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).
Замороженная passive-кампания, splits, integrity gates и точная команда
запуска описаны в
[`TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md`](TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md).
Smoke test прошёл 21 августа: sidecar имеет форму `[8,4,16,7]`, все семь
доступных overlap-переходов пересчитались из NPZ без расхождений. Основная
кампания завершена: 312/312 rollout. Plain overlap detector не прошёл passive
gate, а audit обнаружил систематически невалидные event labels. Честный разбор,
исправленный AP и следующий протокол находятся в
[`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md).
Универсальная WSL-команда `ysda-exp-status`, состояния кампании и метод расчёта
ETA описаны в
[`MLSPACE_EXPERIMENT_MONITORING.md`](MLSPACE_EXPERIMENT_MONITORING.md).

Предыдущий этап находится в
[`LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb`](LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb)
и frozen-отчёте
[`campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md`](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md).
Предшествующие LIBERO-PRO и LIBERO-Safety результаты собраны в
[`campaigns/replication_safety_analysis_20260813/README.md`](campaigns/replication_safety_analysis_20260813/README.md),
а полная июльская история находится в
[`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md).
Вместе они разделяют:

- фактически завершённые standard LIBERO и LIBERO-PRO runs;
- формулы uncertainty и planning;
- calibration, holdout и generalization результаты;
- завершённую denoise-10 replication и официальный LIBERO-Safety rollout.

## Основные файлы

| Файл | Назначение |
|---|---|
| [`P4B_RESIDUAL_RISK_PROTOCOL_20260907.md`](P4B_RESIDUAL_RISK_PROTOCOL_20260907.md) | Frozen P4b: robust ensemble scores, development selection gate и prospective all-candidate terminal holdout |
| [`P4B_RESIDUAL_RISK_RUN_20260907.md`](P4B_RESIDUAL_RISK_RUN_20260907.md) | Resumable autonomous P4b sequence, GPU-capacity wait, status files и outputs |
| [`P4B_RESIDUAL_RISK_RESULTS_20260907.md`](P4B_RESIDUAL_RISK_RESULTS_20260907.md) | P4b NO-GO: 200 K4 snapshots, residual transfer, paired terminal SR, within-pool diagnostics и следующий task-critical direction |
| [`P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md`](P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md) | Frozen P4: CLIP/Cosmos residual targets, 5 independent Gaussian heads, analytic JRD, group splits, trajectory conformal threshold и offline gate |
| [`P4_RESIDUAL_DYNAMICS_RUN_20260906.md`](P4_RESIDUAL_DYNAMICS_RUN_20260906.md) | Resumable server sequence, GPU queue, status files и ожидаемые P4 artifacts |
| [`P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md) | P4 NO-GO: 5,668 transitions, degenerate quadratic JRD, useful post-hoc epistemic residual signal и frozen next-step boundary |
| [`P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md`](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md) | P3e PASS: frozen three-way router, 75/75 holdout cases, 53/75 -> 55/75, 2/0 rescue/harm и replicated x0.2/task2 harm avoidance |
| [`P3E_RECOVERY_OUTCOME_ROUTER_PROTOCOL_20260906.md`](P3E_RECOVERY_OUTCOME_ROUTER_PROTOCOL_20260906.md) | Frozen P3e architecture, seven observable features, cost-aware routing и untouched init 45--49 gate |
| [`PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md`](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md) | P3d NO-GO: 225/225 branches, strong replication, inconclusive new-cell transfer и direct retreat-only ablation |
| [`PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md`](PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md) | Frozen P3d: 15 Position cells, new init 40--49, full regrasp против retreat-only и gated holdout |
| [`PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md`](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md) | P3c confirmatory PASS: full-episode 32.5% -> 60.0%, +27.5 п.п., 12/1 rescue/harm, safety diagnostics и P3d decision |
| [`PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md) | Frozen P3c online trigger, exact shared snapshot, sequential splits и gates |
| [`PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md`](PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md) | P3b: RGB calibration, grouped OOF localizer, screen 11/20, development 49/80 и strict reserve 43/72 |
| [`PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md) | Последовательные offline/screen/development/reserve gates и resumable запуск P3b |
| [`RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md) | P3: 240 strict exact-state recovery branches, paired rescue coverage, uncertainty caveats и переход к perception-backed regrasp |
| [`RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md) | Frozen P3 development cells, recovery proposals, integrity/efficacy gates и untouched reserve |
| [`CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md`](CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md) | P2d: privileged context interactions, within-cell interpolation, task/level/cell transfer failure и решение pivot к recovery |
| [`CONTEXT_INTERACTION_UPPER_BOUND_PROTOCOL_20260903.md`](CONTEXT_INTERACTION_UPPER_BOUND_PROTOCOL_20260903.md) | Frozen P2d interaction basis, grouped OOF splits, leakage boundary и decision gate |
| [`OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md`](OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md) | P2c development: 640 strict pairs, frozen CLIP object/contact features, grouped transfer, auxiliary grounding и решение no-go |
| [`OBJECT_CONTACT_VOF_DEVELOPMENT_PROTOCOL_20260903.md`](OBJECT_CONTACT_VOF_DEVELOPMENT_PROTOCOL_20260903.md) | Frozen P2c inputs, causal targets, leakage boundary, model families, grouped splits и development gates |
| [`INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md`](INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md) | Prospective P2b: 400/400 strict pairs, frozen invariant-CATE efficacy FAIL, always-requery superiority, calibration/sign-reversal diagnosis и P2c decision |
| [`SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md) | Prospective signed-VoF transfer: 240/240 strict pairs, frozen-router FAIL, causal opportunity, feature-shift diagnosis и следующий invariant CATE design |
| [`OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md) | Confirmatory Object task0 query-4 feedback: 60 unseen-init exact states, paired SR, bootstrap/McNemar, failure modes и frozen selector transfer |
| [`OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md) | Untouched Object tasks 1-9: 180 exact-state пар, 100% ceiling обеих ветвей, replay integrity и решение no-go для unconditional transfer |
| [`OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md) | Первый full-episode deployment: 100 matched keys, GPU-aligned prefix failure, descriptive SR и clean-replication decision |
| [`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_PROTOCOL_20260901.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_PROTOCOL_20260901.md) | Frozen independent-seed deployment replication на clean GPU 5-7 с неизменными endpoint/cost/gates |
| [`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md) | Clean-GPU replication: nominal +19 п.п., strict sensitivity +14.7 п.п., prefix integrity failure и shared-prefix next step |
| [`OBJECT_Q4_SHARED_PREFIX_REPLICATION_PROTOCOL_20260902.md`](OBJECT_Q4_SHARED_PREFIX_REPLICATION_PROTOCOL_20260902.md) | Frozen single-process shared-prefix design, exact-state endpoint, cost и confirmatory gates |
| [`OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md) | Confirmatory PASS: 100/100 strict, 46% -> 64%, +18 п.п., CI [+4; +32], 31/13, p=0.00956 |
| [`OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md`](OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md) | Confirmatory Position transfer FAIL: 120/120 strict; `y0.2` 53.3% -> 55.0%, CI [-13.3; +16.7], 10/9; interaction 0 п.п. |
| [`COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md`](COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md) | Same-query diagnostic: exact внутри процесса, small action/value drift между fresh processes, strict CUDA-kernel limitation |
| [`INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md`](INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md) | Fixed query-0 H8 holdout: integrity audit, nominal/sensitivity SR, task heterogeneity и решение no-go |
| [`SEMANTIC_VOF_RESULTS_20260831.md`](SEMANTIC_VOF_RESULTS_20260831.md) | 265-state CLIP development screen и Environment task transfer, uplift, factor diagnostics и next representation |
| [`PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md`](PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md) | Privileged approach/grasp/transport terminal VoF transfer и exploratory query-0 signal |
| [`FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md`](FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md) | Frozen transfer real-observation router: 90 pairs, factor/task SR, compute, failure modes и решение no-go |
| [`REAL_OBSERVATION_REQUERY_RESULTS_20260830.md`](REAL_OBSERVATION_REQUERY_RESULTS_20260830.md) | 40-state pilot H16/H8/gripper-H8-H16 и exploratory factor interaction |
| [`HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md`](HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md) | Frozen Bradley-Terry ranker: dev/cal opportunity, untouched holdout, bootstrap CI, failure mechanism и routing |
| [`HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md`](HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md) | Frozen hard-cell split, 20 online features, Bradley-Terry objective, bootstrap LCB и sequential gates |
| [`AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md) | Same-pass `action -> future -> value`: integrity, paired terminal ranking, future-proprio diagnostics и отрицательный gate |
| [`AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md) | Frozen paired test параллельного value против `action -> future -> value` на одинаковом K8 pool |
| [`PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md`](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md) | K4/K8/K16 oracle coverage, value misranking и routing Object/Position/Environment |
| [`TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md`](TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md) | Terminal residual advantage, 50 causal features, bootstrap/conformal LCB, splits и opportunity/offline gates |
| [`FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md`](FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md) | Paired closed-loop maxV против frozen H16 ranker: terminal SR, grouped CI, failure modes, mechanism и решение |
| [`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md) | Confirmatory holdout frozen H16 ranker: regret, bootstrap CI, integrity, diagnostics и решение |
| [`GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md`](GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md) | Итог P0-P2: broad horizon controls, VoF, exact-state ranking, integrity и решения go/no-go |
| [`DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md`](DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md) | Dense H16 relabel, strict/factor OOF, candidate ranking и matched H32 pilot |
| [`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md) | Итог causal 2x2: selection, feedback horizon, task-level robustness, failure modes и compute |
| [`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md) | Текущий план: causal 2x2, RCS, grounded Q/QWM, JRD/CP, StressDream и safety filter |
| [`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md) | Old tail против new prefix: TIDE/STAC, Hide-and-Seek baseline, формулы, collector schema и causal test |
| [`TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md`](TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md) | Frozen passive run: 12 cases, independent/coupled seeds, event labels, integrity gates и запуск |
| [`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md) | Итог 312-rollout overlap campaign: label audit, corrected metrics, coupled control и go/no-go |
| [`MLSPACE_EXPERIMENT_MONITORING.md`](MLSPACE_EXPERIMENT_MONITORING.md) | Универсальная команда `ysda-exp-status`: progress, jobs, rollout, ETA и READY/FAILED/STALLED |
| [`SURROGATE_REQUERY_RESULTS_20260820.md`](SURROGATE_REQUERY_RESULTS_20260820.md) | Итог 960 confirmatory rollout: формулы, статистика, failure modes и ограничения |
| [`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb) | Таблицы и графики screening, frozen confirmatory и surrogate transfer |
| [`SURROGATE_REQUERY_HYPOTHESES_20260819.md`](SURROGATE_REQUERY_HYPOTHESES_20260819.md) | Протокол и гипотезы, замороженные до confirmatory outcomes |
| [`LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb`](LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb) | Frozen adaptive-planning результат, формулы, статистика и matched-seed видео |
| [`ADAPTIVE_PLANNING_HYPOTHESES_20260813.md`](ADAPTIVE_PLANNING_HYPOTHESES_20260813.md) | Гипотезы H1-H14, protocol и интерпретация confirmatory проверки |
| [`campaigns/replication_safety_analysis_20260813/README.md`](campaigns/replication_safety_analysis_20260813/README.md) | Новые paired planning и LIBERO-Safety результаты, статистика и графики |
| [`LIBERO_FINAL_RESULTS.ipynb`](LIBERO_FINAL_RESULTS.ipynb) | Компактный итоговый notebook: confirmatory таблицы, графики, выводы и matched-seed видео |
| [`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md) | Текущие выводы и итоговые таблицы |
| [`LIBERO_OOD_SAFETY_CAMPAIGN.md`](LIBERO_OOD_SAFETY_CAMPAIGN.md) | Общий план LIBERO / PRO / Safety |
| [`LIBERO_8H_VALIDATION_PROTOCOL.md`](LIBERO_8H_VALIDATION_PROTOCOL.md) | Зафиксированный протокол большой PRO validation |
| [`configs/libero_campaign_v1.json`](configs/libero_campaign_v1.json) | Профили стандартных, OOD и Safety запусков |
| [`configs/libero_campaign_8h.json`](configs/libero_campaign_8h.json) | Точный grid завершённой 1078-rollout кампании |
| [`LIBERO_PHASE1_RESULTS.ipynb`](LIBERO_PHASE1_RESULTS.ipynb) | Notebook первого ID/OOD screening |

## Результаты

```text
campaigns/phase1_analysis_20260724/
  README.md                 # 72 ID + 106 OOD rollout
  plots/
  *.csv

campaigns/libero_full_validation_20260724/
  manifest.json             # status=completed, 23/23 jobs
  analysis/full_validation/
    README.md
    planning_strategy_summary.csv
    paired_vs_max_value.csv
    pooled_planning_confirmatory.csv
    prespecified_detector_exact_query.csv
    prediction_error_correlations_q0_5.csv
    case_outcome_summary.csv

campaigns/replication_safety_analysis_20260813/
  README.md                 # выводы новой replication и Safety
  pro_case_results.csv
  pro_pooled_result.csv
  pro_early_fail_predictors.csv
  safety_suite_level_results.csv
  safety_violation_episodes.csv
  plots/

campaigns/adaptive_confirmatory_20260813/
  manifest.json             # status=completed, 1080/1080 strategy executions
  analysis/adaptive_summary/
    README.md
    frozen_confirmatory_results.csv
    paired_by_case.csv
    replay_control_summary.csv
    prediction_error_correlations.csv
    plots/

campaigns/surrogate_confirmatory_20260819/
  manifest.json             # status=completed, 960/960 strategy executions
  analysis/adaptive_summary/
    README.md
    frozen_confirmatory_results.csv
    paired_by_case.csv
    paired_failure_modes.csv
    surrogate_transfer_diagnostics.csv
    plots/

campaigns/factorial_selection_horizon_20260820/
  manifest.json             # status=completed, 672/672 rollout
  analysis/selection_horizon_factorial/
    README.md
    factorial_strategy_summary.csv
    factorial_effects_pooled.csv
    factorial_effects_by_case.csv
    factorial_seed_outcomes.csv
    plots/
  analysis/adaptive_summary/
    README.md
    paired_failure_modes.csv
    prediction_error_correlations.csv
    surrogate_transfer_diagnostics.csv
    plots/

campaigns/temporal_overlap_passive_20260821/
  manifest.json             # status=completed, 312/312 rollout
  analysis/result_audit/
    README.md
    case_event_audit.csv
    paired_seed_mode_outcomes.csv
    seed_mode_q1_metric_comparison.csv
    key_query_metrics_h16.csv

campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/
  analysis/frozen_ranker_strict/
    RESULTS.md
    holdout_factor_summary.csv
    grouped_bootstrap_intervals.csv
    heldout_candidate_regret.png
    heldout_regret_delta_ci.png

campaigns/factor_routed_requery_transfer_20260830/
  manifest.json             # status=completed, 6/6 jobs, 180/180 rollout
  analysis/factor_routed_transfer/
    RESULTS.md
    summary.json
    method_summary.csv
    factor_summary.csv
    paired_contrasts.csv
    route_success_compute.png
    route_paired_outcomes.png
```

`uncertainty/` содержит более ранние exploratory и video runs. Они полезны для
визуальной диагностики, но итоговые числа следует брать из двух campaign
каталогов выше.

## Текущий статус

| Benchmark | Статус |
|---|---|
| Standard LIBERO ID | Завершён |
| LIBERO-PRO screening | Завершён |
| LIBERO-PRO full validation | Завершена, 1078/1078 rollout-выполнений |
| LIBERO-PRO denoise-10 replication | Завершена, 200/200 strategy executions на 100 paired seeds |
| Adaptive planning calibration | Завершена, 900/900 strategy executions на 3 boundary cases |
| Adaptive planning frozen confirmatory | Завершена, 1080/1080 strategy executions на 180 paired seeds и 6 cases |
| Surrogate/requery screening | Завершён, 816/816 strategy executions; используется только для выбора гиперпараметров |
| Surrogate/requery frozen confirmatory | Завершён, 960/960 strategy executions на 240 paired seeds и 12 cases |
| Selection x horizon causal 2x2 | Завершён 21 августа 2026: 672/672 rollout, 168 matched seeds, 7 cases |
| Temporal overlap passive detection | Завершён 24 августа 2026: 312/312 rollout; detector gate не пройден, event labels требуют repair |
| Broad horizon controls P0 | Завершён 27 августа 2026: 24/24 jobs, 897 episodes |
| Frozen H16 ranker holdout | Завершён 28 августа 2026: 240 states, 230 strict, 69 groups, formal gate PASS |
| Frozen H16 ranker closed-loop | Завершён 29 августа 2026: 360 pairs / 720 episodes, macro -0.28 п.п., formal gate FAIL |
| K16 proposal opportunity | Завершён 30 августа 2026: 50 states / 800 terminal branches; pool насыщается к K8 |
| Action-conditioned AR value | Завершён 30 августа 2026: 10 states / 80 branches; integrity PASS, efficacy FAIL, 1 rescue / 1 harm |
| Hard-cell pairwise ranker | Завершён 30 августа 2026: 60 states / 480 branches; holdout `maxV/gated=45/30%`, 0 rescue / 3 harm, gate FAIL |
| Real-observation gripper re-query pilot | Завершён 30 августа 2026: 40 pairs на метод; universal gate FAIL, exploratory factor router +10 п.п. |
| Frozen factor-routed re-query transfer | Завершён 30 августа 2026: 90 pairs / 180 rollout; 47/90 против 53/90, -6.7 п.п., gate FAIL |
| P3 recovery-proposal opportunity | Завершён 4 сентября 2026: 240/240 strict; deployable 7/80 и 8/80 (gates FAIL), privileged regrasp 62/80 |
| P3b perception-backed regrasp | **PASS**: screen 11/20, development 49/80, strict new-group reserve 43/72 |
| P3c online RGB-triggered regrasp | **PASS**: holdout 40/40 strict; 32.5% -> 60.0%, CI [+12.5; +42.5] п.п., 12 rescue / 1 harm |
| P3d cell transfer + retreat ablation | **Development NO-GO**: 75/75 cases, new-cell +14.3 п.п., CI [-2.9; +31.4], holdout не открыт |
| P3e Recovery Outcome Ensemble | **PASS**: frozen holdout 75/75 cases; full 70.7% -> router 73.3%, CI [0.0; +6.7], 2 rescue / 0 harm |
| P4 independent residual-dynamics ensemble | **NO-GO**: 5,668 rows; JRD=0 everywhere, pooled balanced AP 0.308, residual rho NaN; no closed-loop hard filter |
| P4b residual-risk candidate selection | **NO-GO**: 200 states / 800 terminal branches; 58.5% -> 56.5%, CI [-5.5; +1.5] п.п., 4/8 rescue/harm; global failure AUROC 0.650, within-pool rank 0.509 |
| LIBERO-Safety physical | Завершена, 144/144: 0 task success, 4 official violations |

## Видео

Большая 1078-execution кампания запускалась с `save_videos=false`. Для
визуального сравнения в
[`final_results_media`](final_results_media/README.md) сохранены 12 компактных
matched-seed видео из более раннего planning pilot. Они показывают расхождение
траекторий четырёх стратегий при одинаковом `task/init_state/rollout_seed`, но
не используются для оценки success rate.

Для P3b отдельно сохранены пять exact-state mechanism replays. HTML-индекс
показывает learned RGB regrasp рядом с privileged-pose upper bound там, где он
доступен:
[`campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html`](campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html).

Для P3e сохранены 12 exact-prefix MP4: четыре заранее перечисленных
диагностических случая, по три ветки `baseline_h8`, retreat-only и full RGB
regrasp. Outcomes и snapshot hashes полностью воспроизвелись. Side-by-side индекс:
[`campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html`](campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html).

Все 144 Safety-видео проверены по frame count и остаются на сервере. Четыре
ролика с официальным `checkcontact` сохранены локально в
[`final_results_media/safety_violations_20260730`](final_results_media/safety_violations_20260730/README.md).

Для adaptive planning сохранены post-hoc deterministic replays выбранных
discordant seed. Их индекс, фактические replay outcomes и переносимые MP4
находятся в
[`final_results_media/adaptive_confirmatory_20260813`](final_results_media/adaptive_confirmatory_20260813/README.md).

Новые matched-seed replays для `surrogate_confirmatory_20260819` сформированы
как отдельная очередь. Статистический результат уже завершён; видео появятся в
`final_results_media/surrogate_confirmatory_20260819`, когда GPU 2-7 освободятся
после текущей shared-server training job.

Factorial-кампания запускалась с `save_videos=false`; её 672 rollout не имеют
видео. Для визуального разбора следует запускать отдельные replays заранее
выбранных discordant seeds, не подменяя ими исходные статистические outcomes.

Real-observation pilot и factor-router transfer также запускались без видео:
их primary evidence состоит из сохранённых query traces и terminal outcomes.
Два transfer-графика находятся в `campaigns/factor_routed_requery_transfer_20260830/
analysis/factor_routed_transfer/`. Если потребуются mechanism-видео, следует
делать отдельные deterministic replays заранее перечисленных 10 routed
discordant pairs и явно проверять replay fidelity.

Для frozen H16 closed-loop результата записаны все девять discordant primary
seeds: 18 полных MP4, side-by-side HTML, primary/replay outcomes и fidelity
audit находятся в
[`final_results_media/frozen_h16_closed_loop_20260829`](final_results_media/frozen_h16_closed_loop_20260829/README.md).
Из-за near-tie GPU numerics буквально воспроизвелись 14/18 outcomes и 5/9 пар;
поэтому эти replays используются только для визуальной диагностики, а SR берётся
исключительно из primary 720-episode campaign.

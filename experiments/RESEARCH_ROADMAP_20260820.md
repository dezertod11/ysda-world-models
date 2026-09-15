# Research roadmap: robust world-model planning

**15 сентября: редакционный фокус и критический путь к статье обновлены.**
[План статьи](../publication/iclr2027/PLAN.md),
[scoped-v2 protocol checklist](../publication/iclr2027/SUBMISSION_CHECKLIST.md).
После завершённого broadS0-v2 приоритет не новые coefficient sweeps, а
перепроверка сильного scoped recovery на обеих исходных cohort сH16/H8.
Минимальный предложенный объём384main+smoke; это подготовленное направление,
не уже запущенная очередь. Затем full-vs-retreat и shared-prefix runtime audit.
Новые GPU-вычисления редакционным проходом не открыты; дата/ресурсы требуют
отдельного запуска. Основная статья, полный отчёт и данные не смешаны.

**15 сентября, 15:32 МСК: S0-v2 завершена и проверена.**
[995/995 rollout: результаты и выводы](P3_RUNTIME_V2_RESULTS_20260915.md).
Завершение13:04МСК, около двух часов от первого запуска. P3fixed-H16
Macro+0.6801п.п.,CI[-2.9967;4.3636],9rescue/6harm; event0вмешательств.
Корректность runtime подтверждена, общий P3 gain нет. S1/S2 отложены,
новых GPU-запусков при разборе нет. Следующий приоритет: перепроверка
scoped16/64→41/64 наv2 с обоими контролями; затем development event coverage
и intervention advantage, не автоматический seed/t72 sweep.

**15 сентября, 11:20 МСК: сокращение бюджета по запросу пользователя.**
Сейчас только полный S0-v2: 199 случаев / 995 main, 18 smoke уже прошли.
Предел15:05 МСК; S1/S2 отложены, все сохранённые rollout остаются.
Методы, seeds и strict audit неизменны. [Актуальный протокол](runtime_replay_v2/LAUNCH_20260915.md).
После полной таблицы приоритет: отдельная проверка scoped recovery-эффекта
на исправленном runtime. Одна серия не подтверждает межseed устойчивость.
Ниже сохранена история прежних решений.

**15 сентября, 11:05 МСК: v2 GPU-проверки запущены.**
[Протокол и выбранный 12-часовой бюджет](runtime_replay_v2/LAUNCH_20260915.md).
До23:05 МСК, с ранним завершением. S0/S1/S2, всего3039rollout; только свободные
GPU0-7, на стартеGPU3занята и пропускается. Сначала regression-smoke,
затем полный benchmark; смена серии только по completeness/audit, не поSR.
Автоматически формируется общая CPU-сводка. Новых sweeps в этом цикле нет.

**15 сентября, исправление воспроизводимости:**
[Диагностика и отдельная snapshot v2](runtime_replay_v2/README.md).
Старое восстановление воспроизводимо расходится на одинаковых actions;
причина локализована до несохранённого MuJoCo warmstart. Также восстановлены
sensor clocks/cache. CPU replay проходит локально и на сервере, short RGB
replay проходит локально на CPU. Closed-loop GPU-проверка ещё впереди.
Приоритет теперь: полный S0-v2, затем S1-v2/S2-v2; не смешивать старые
outcomes с новой версией. Строгий audit не ослаблять. GPU-очередь только
подготовлена, новый срок вычислений ещё не задан.

**15 сентября, итоги ночи и новый приоритет:**
[Полная P3-таблица и диагностика остановки репликации](P3_BENCHMARK_FINAL_RESULTS_20260915.md).
199/199: P3fixed-H16 macro+0.013п.п., CI[-3.67;3.78],9rescue/7harm.
Position+4.04п.п. компенсирован Object-6п.п.; event не вмешивался ни разу.
Scoped recovery-result сохраняется, broad superiority не подтверждён.
S1 остановилась на техническом no-intervention parity: обе ветви success,
но observations начинают расходиться до actions. Сначала isolated replay
и проверка полноты runtime restore; не ослаблять audit. Затем новая версия
S1/S2 без смешивания configs. Далее development-проверка покрытия event gate
и пользы recovery, не новый t72/lambda sweep. Сейчас ничего не запущено.

**15 сентября, ночной приоритет до09:00 МСК:**
[Досчёт и две фиксированные seed-репликации](P3_NIGHT_REPLICATION_PROTOCOL_20260915.md).
SSH восстановлен; исходная серия была прервана на307/995. Она возобновлена
без изменения научного config. Затем S1/S2 на тех же199 task/init и пяти arms;
переход только по полноте и audit, не поSR. GPU0-7 idle-only, cutoff08:30.
Для публикации важнее закрыть общую таблицу и проверить seed robustness,
чем начинать новый adaptive sweep. CPU-аудит event coverage объяснит нулевую
частоту вмешательств без настройки trigger на тесте. Новые seeds не являются
unseen-init/task holdout; отрицательные broad outcomes не исключаются.

**14 сентября, вечер: сначала восстановить наблюдаемость существующей очереди.**
[Проверка и уточнённый анализ](EXPERIMENT_REVIEW_20260914_EVENING.md).
Свежий P3 valid199 статус получить не удалось: два SSH banner timeout.
Не запускать дубли и не подбирать новый arm по старым scoped SR. После
восстановления доступа проверить PID, полноту и integrity исходной кампании;
при неполноте продолжать прежний config, не считать missing эпизоды fail.
В анализе сохранять H8 и H16: похожий общий SR скрывает противоположные
эффекты смены горизонта на отдельных клетках. Нового event-SR пока нет.

**14 сентября, приоритет на оставшийся день:**
[Итоги завершённых confirmation и oracle](RECOVERY_FINAL_RESULTS_20260914.md),
[план закрытия P3 на общем benchmark](P3_BENCHMARK_CLOSURE_PROTOCOL_20260914.md).
Main512/512 и timing768/768 завершены. Репликация:41/64 против16/64;
transfer:1/64 против0/64. Preserve-only не добавляет SR. Oracle тоже завершён:
128/128, GT-XY спасает3/16 transfer против0/16 RGB, но большинство failures остаётся.
Сломался только shadow, а не oracle. Приоритет: недостающая пятисторонняя
таблица valid199 и один observation-triggered recovery; новые broad sweeps
coefficients/localizer training отложены. Ниже сохранена история решений.

Дата обновления: 13 сентября 2026 года.

**Следующие проверки запущены:** [recovery resume + grounding diagnostic](RECOVERY_GROUNDING_DIAGNOSTIC_PROTOCOL_20260913.md).
Main без смены methods/seeds, затем прежние timing controls; отдельная очередь
32geometry, 128oracle/replay outcomes и4shadow controls. Общий cutoff21:12MSK,
без автоматического fit или выбора лучшего метода по промежуточному SR.
Сначала отделяем XY/height/coverage, затем решаем вопрос нового deployable
localizer/event-controller. Новые oracle SR не попадут в таблицу основного метода.

**Приоритет после анализа 13 сентября: grounding перед широким event sweep.**
[Полный промежуточный разбор](RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md).
Frozen серия остановилась около02:50MSK: main441/512, timing0/768;
старый `running` неактуален. В108 полностью matched cases: familiar
physical40/61 противH8 16/61; transferx0.3 1/47 против0/47.
Preserve-only: тот же SR, 1rescue/1harm относительноphysical наfamiliar.
У всех18разрешённых наx0.3 initial gates offline ошибка локализации >5см;
наfamiliar среди40разрешённых таких ошибок0. Это не доказанная единственная
причина провала и ещё не исключённая ошибка pixel-to-world геометрии.

1. Явный новый ресурсный бюджет и досчёт71оставшейся main-ветви без смены
   frozen config/seeds; final inference только после полного matched main.
2. Offline projection/frame audit; затем matched RGB-vs-GT waypoint diagnostic
   с фиксированными gate, primitive, action budget. GT только для диагностики.
3. При подтверждении ограничения зрения: object-grounded/two-view localizer,
   память и unknown; затем shadow/calibration уже реализованного event timing.
   Разнести улучшение grounding и выбора момента отдельными ablations.
4. Не начинать очередной широкий preserve/consensus/value sweep. Не выдавать
   t72 за универсальный момент; t56/88 остаются неисполненными controls.

Это обновлённый план, не новый GPU-запуск. CPU event-код не является measured SR.
Предыдущие статусы запуска ниже сохранены как история и не описывают live очередь.

**Уточнение приоритета: fixed t72 больше не является основным новым методом.**
[Литература, формулы, память и ограничения архитектуры](../articles/EVENT_TRIGGERED_FEEDBACK_REVIEW_20260913.md).
[Миграция всех fixed-q4 семейств, код и команды](EVENT_FEEDBACK_MIGRATION_20260913.md).
Новый `collect_event_feedback.py` по умолчанию использует event timing:
requery, regrasp, preserve-probe, verify-regrasp. История RGB/proprio/actions,
guard против раскрытия при held/unknown, ограниченный бюджет. Сначала shadow
и development calibration, затем честные fixed/random/H16/H8 controls и
независимые cells. Это реализация, **не новый положительный SR-результат**.
Frozen campaign ниже не менять: t56/72/88 там нужны как timing controls.
Старые веса P3e/VoF, обученные только на t72, не переносить на все времена
без новых counterfactual labels. RTC/attention-horizon требуют отдельного
Cosmos latent-layout audit; они ещё не реализованы новым scheduler.

**Новый приоритет на два дня:** [финальная проверка P3, переноса и timing](RECOVERY_TWO_DAY_PLAN_20260913.md).
Отдельная замороженная серия `recovery_confirmation_20260913`: до1289 исходов,
9 часов автономно; 9 технических replay, затем512 main и768 timing.
128 cases, familiar P3 cells и x0.3 вне calibration локализатора;
baseline H16, continue H8, старый recovery и preserve-only. t56/72/88 снимаются
с одной невмешанной траектории. Новые seeds не называем untouched-init holdout.
Нет нового decoder sweep, обучения или автоматического выбора лучшего t.
Статусы ниже исторические; новый запуск подтверждается в каталоге кампании.

**Обе ночные серии завершены; следующий запуск этим анализом не открыт.**
[Observation Contract1536/1536](OBSERVATION_CONTRACT_RESULTS_20260912.md):
primary145/192 против151/192physical, NO-GO; preserve-only161/192 является
post-hoc локальной гипотезой, netgain толькоx0.2/task9. В16pairedharms новый
regrasp раскрывал предмет, уже двигавшийся с рукой; triggerлокализации
нельзя использовать как свидетельство отсутствия захвата.
[Decoder-medoid1440/1440](DECODER_MEDOID_RESULTS_20260912.md):
H16 decoder=max-value112/180, fixed seeds близки; H8/prefix не дали
подтверждённого выигрыша. Обнаружена сильная seed affinity hidden selector.

**Следующие приоритеты по полученным данным:**
1. Сохранить полные отрицательные сравнения и механизм-анализ для статьи:
   [общая сводка, E16–E19](../publication/iclr2027/RESULTS_AND_ANALYSIS.md).
2. До широкого sweep зафиксировать preserve-only/старыйregrasp controls;
   проверить новыеinit x0.2/task9, затем отдельныеcells. Новыйcandidate:
   passive/two-view held evidence и conservative veto раскрытия gripper.
   GTlabels доступны только дляoffline обучения/анализа, не online метода.
3. Hiddenconsensus пока не расширять: для отдельногоdiagnostic нужны новые
   noisepools на одномobservation и train-only representation calibration.
   Always-H8 не продвигать без подтверждённого conditionalgain.
Holdoutне открывается после primaryNO-GO. Ниже исторические планы11сентября,
включая прежние running/queued статусы; они больше не описывают liveочередь.

**Ночной приоритет до 10:00 MSK 12 сентября:**
[720 основных rollout, 360 fixed-seed controls, до 360 H8 controls](DECODER_MEDOID_NIGHT_20260912.md).
Строгий порядок, без отбора по SR. В локальном integration K1 со вторым seed
побитово повторил 159 действий medoid и конечное состояние; третий seed дал
fail на 280 шагах. Поэтому отделение seed preference от адаптивного выбора
обязательно, прежде чем усложнять архитектуру или заявлять научный выигрыш.
Это технический пример, не основная статистика. Расчёты ограничены 09:40;
ночной wrapper заменяет старый ресурсный бюджет 24 часа, не научный config.

**Добавлено по запросу: transfer decoder action-token medoid.**
[Замороженная проверка нового representation-selector из Robotics_project_YSDA](DECODER_TOKEN_MEDOID_PROTOCOL_20260911.md).
Это ещё не испытанный у нас hidden-space вариант P4 consensus, не обученный P5.
720 full rollout, четыре controls/methods, K3/H16, все десять Object-suite
задач и три фактора; все три upstream seed pools вместо выбора единственного
удачного. Текущая Observation Contract не прерывается; новая автономная очередь
ждёт её окончания и idle GPU. Сначала strict capture parity, затем SR и paired
effects. Успех переноса не заявляется до результатов, автоматического holdout
или подбора коэффициентов нет. Recovery-ветка оценивается независимо.

**Текущий запуск с 20:23 MSK:** [Observation Contract](OBSERVATION_CONTRACT_PROTOCOL_20260911.md).
Ветка information-before-release выбрана перед большим P5/P6 fit: 24 replay
checks, затем 1536 ветвей, два suffix seeds на 96 прежних prefixes. Восемь
arms включают отдельно два GT diagnostics; они не считаются deployable gain.
Цель: разнести ограничение зрения, calibration workspace и самого recovery.
180 CPU-тестов прошли локально/на сервере. Main только после strict smoke;
автоматического holdout или следующего исследования нет, бюджет до 8 часов.
Все следующие записи о пустой очереди относятся к предыдущим срезам.

**Последняя серия завершена15:09MSK, новый controller не прошёл gate:**
[Timing / eligibility: 490ветвей, полный аудит](TIMING_ELIGIBILITY_RESULTS_20260911.md).
Continue63/96; immediate/diagnostic76/96; fresh/checked74/96. Checked не
изменил ни одногоlabel относительноfresh. Raw diagnostic восстанавливает
3полезныхrecovery при ненадёжномfreshscore, но причиняет1harm через3-step
retreat, даже без полногоprimitive. Он не продвигается как безопасныйметод.
Все17общихfailures лежат вне исходногоtrigger; это coverage, не доказанный
предел recovery. 490видео и79CPU-тестов проверены, holdout38–45 закрыт.

**Приоритеты development после предыдущего анализа (пункты 1/3 теперь проверяются):**
1. Проверить observation/retreat без открытияgripper с отдельными controls
   continue, старыйretreat иfullrecovery; сохранить актуальныеgeometryguards.
2. Passive/two-viewverification и память надёжной локализации, явныйunknown;
   оценивать добавочный эффект относительноimmediate, а не толькоcontinue.
3. OfflineGT-аудит17недопущенныхfailures: localization error против реального
   workspace/reach, затем frozen проверка coverage/eventtrigger.
Не продолжать checked-latch sweep, не открыватьholdout послеNO-GO и не
начинать новый широкийvalue/rankingfit на основании этихlabels. Новые
эксперименты тем анализом не запускались; актуальный запуск указан выше.

**Предыдущее решение после 576 завершённых ветвей:**
[Object-grounded verification: анализ и следующие проверки](GROUNDED_PROBE_RESULTS_20260911.md).
Conservative35/48 = probe-always35/48; full33/48. Ложных held стало0вместо10,
но gate NO-GO: почти нет полезной селекции,47/48траекторий повторяют контроль.
Transfer: full36/48, delayed/continue33/48; свежий trigger отменил14из21
исходно разрешённых recovery. Conditional init38–45 не открывались.
Серия завершена03:56MSK, текущая очередь пуста; никакого нового sweep по
прочитанным labels. Следующий узкий опыт должен разделить время вмешательства
и обновление eligibility, сохранив актуальные safety guards. До него:
offline/shadow passive/two-view verification и явная политика unknown.
Большой P5 fit/RL из этого результата не следует. Новых GPU-run анализ не запускал.

**Предыдущая завершённая проверка:**
[probe/verify/repair v2, 192/192](PROBE_VERIFY_REPAIR_RESULTS_20260911.md).
Verified30/48 проиграл full35/48 по средней SR; primary −10.42п.п.,
4 rescue /9 harm, Holm p=.83967. Continue и probe-only26/48. Practical
gate NO-GO, conditional holdout не запускался. Семь false-held связаны с
отслеживанием движения захвата вместо неподвижной цели, пять позднее fail.
Следующий дешёвый шаг: object-specific/passive/two-view verification и
контроль probe→always-regrasp. Сохраняем сильный recovery baseline; не
продолжаем v2 и не начинаем большой P5 fit/RL по этому результату.
[Уточнённые приоритеты](RESEARCH_PRIORITIES_20260910_EVENING.md).
Новых GPU-run при анализе не запускали; старые очереди ниже исторические.

**Оперативное решение после завершения обеих дневных серий:**
[вечерний план и критерии продолжения](RESEARCH_PRIORITIES_20260910_EVENING.md).
P5 690/690 и matched-K 120/120 завершены; [итоговый анализ](P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md).
Устойчивый misranking есть в одном snapshot, переноса scorer пока нет.
K4/continuity не устранили вред fresh feedback на y0.2/task9. Приоритет:
новый [physical probe + RGB verification + recovery](PROBE_VERIFY_REPAIR_PROTOCOL_20260910.md),
затем отдельный init holdout только при положительном screen. Большой P5 fit
и generator RL не открывать автоматически. Прежние очереди ниже завершены.

**Приоритетное решение после свежих аудитов:**
[RESEARCH_PRIORITIES_20260910](RESEARCH_PRIORITIES_20260910.md).
Сохраняем сильный P3c recovery, но новый вариант должен учитывать фазу/grasp,
нефизичный fallback и calibration leakage. P5 scorer только после repeated
candidate opportunity gate. Следующий реализованный механизм-screen:
[K4 controls + continuity, 135 ветвей со smoke](FEEDBACK_CONTROLS_PROTOCOL_20260910.md).
Очередь сериализована после текущего P5; SSH при подготовке недоступен,
поэтому статусы запуска ниже являются историческими, не live-проверкой.
Связь позже восстановлена: новый dispatcher PID3878088 подтверждён13:19 MSK,
ожидает predecessor. Pool13 replication прошёл (1/10 maxV против10/10 каждой
из двух альтернатив); neighboring transfer ещё не завершён. Полная новая
сводка и ограничения по ссылке выше.

**Запущено по следующему gate; основной сбор с 12:09 MSK:**
[P5 conditional candidate replication](P5_CANDIDATE_REPLICATION_PROTOCOL_20260910.md).
50 exact-state branches с новыми suffix seeds для pool13/pool11, затем до640
branches новых K8 pools на init9-12 tasks0/2 Position x0.2. Per-step сигналы
разделяют H16 consequences и поздний terminal outcome; альтернативы также
получают видео. 6/6 smoke пройдены, основная серия на GPU0/3/5. Методика
фиксирована до новых labels; большого fit/holdout автоматически не будет.

**Текущее решение после P5 repeats, 10 сентября:**
[1080 ветвей завершены; анализ и план](P5_REPEAT_FEEDBACK_RESULTS_20260910.md).
Fresh8 41/108, open16 44/108, stale8 45/108: общий gain не подтверждён.
96/288 action labels меняются между suffix seeds. K8 optimistic oracle-gap
+14.81 п.п. не переносится на held-out suffix (0 п.п., 5 rescue / 5 harm).
Следующий узкий gate: replication `pool_13`/`pool_11` на новых suffix seeds
и init, раздельные contact/target и terminal labels. Только после устойчивого
action-dependent сигнала открывать небольшой grounded scorer; all-fail cases
проверять через proposals/recovery. Не продвигать always-fresh8 и новый
массовый coefficient sweep. Новый GPU-запуск этим разбором не открывался.

**Предыдущий план после завершения consensus/P5 pilot:**
[результаты 1194 rollout и 288 candidate branches](CONSENSUS_AND_P5_RESULTS_20260910.md)
не обосновывают новый широкий coefficient sweep или обучение critic на
единственном K8 rescue. Приоритет на девятичасовое окно:
[1080 branches: repeated suffix labels + fresh/stale feedback controls](P5_REPEAT_FEEDBACK_PROTOCOL_20260910.md),
максимум три GPU-worker после ресурсной поправки пользователя, все 36 прежних pools.
Далее решение по данным:
устойчивый ranking signal -> grounded P5; полезное новое наблюдение ->
closed-loop/event-trigger transfer; устойчивый all-fail -> proposals/recovery.
Исторические статусы ожидания ниже относятся к предыдущей очереди.

**Ресурсы 13:44 MSK:** по новому разрешению допускаются GPU **0-7**, но
только практически свободные и без CUDA-процессов. Перезапущен dispatcher
PID2694673, 368 reference rollout сохранены; на 13:45 workers ждут ресурсов.
P5 и scientific settings не менялись. Прежний запрет GPU0 ниже исторический.
[Ресурсная поправка, 75 тестов и ограничение гарантий](GPU07_RESOURCE_POLICY_20260909.md).

**Актуальные ближайшие приоритеты, проверка сервера 13:10-13:13 MSK:**
[решение, ресурсы, бюджеты и порядок проверок](RESEARCH_PRIORITIES_20260909.md).
References: **367/597**, осталось 230 Position rollout; диспетчер жив,
но ждёт свободную GPU, наших GPU collectors сейчас нет. P5 smoke/pilot
ещё не начались. Frozen queue не изменена. Текущий P5 сохраняется как
data-opportunity pilot; следующий learned P5 уточнён:
[task-critical features, local/terminal labels, rescue-opportunity и noise gates](P5_TASK_CRITICAL_REFINEMENT_20260909.md).
В старых 194 pools все 14 oracle rescue opportunities относятся только к
Object task0 / Environment task3. Быстрый путь к положительному результату:
recovery mechanism/timing micro-pilot; путь к новому planner: grounded P5
после проверки support, без нового массового coefficient sweep.

**Дополнение по LLM/NLP, 9 сентября:** подготовлен
[обзор аналогичных методов с формулами и этапами E0-E5](../articles/llm_nlp_transfer_20260909/ANALOGY_AND_PLAN.md).
Приоритет после текущего opportunity audit: task-critical grounded P5;
отдельная ветка продолжения P3: event-conditioned verification/correction.
MBR-BoN является опубликованным близким аналогом value + consensus,
а не новой общей формулой; semantic probes и flow alignment оставлены
последующими этапами. Это предложения для следующего freeze, **не** изменение
ночной очереди, существующих коэффициентов или открытие нового holdout.
[26 PDF и разбор каждой статьи](../articles/llm_nlp_transfer_20260909/README.md).

**Решение по recovery timing, 9 сентября:** `t=72` сохраняем как фиксированный
контроль, а не универсальный момент ошибки. P3c не закрываем: положительный
эффект на известных cells подтверждён, перенос P3d и добавочный gain P3e
пока недостаточны. Следующая проверка этой ветки: development timing sweep
-> отделение requery/retreat/regrasp -> state-conditioned выбор полезного
вмешательства -> новые целые cells и fixed/random controls. Не доказано,
что причина слабого переноса именно timing. Не меняем текущую ночную очередь
и не открываем новый holdout автоматически.
[Зафиксированное решение, гипотезы и критерии проверки](RECOVERY_TIMING_DECISION_20260909.md).

**Ресурсная поправка 9 сентября, 01:18 MSK:** текущая ночная очередь и её
последующие стадии используют свободные GPU **1-7**, не GPU0. Общий dispatch
не закрепляет задания за занятой картой. Готовые эпизоды переиспользуются;
изменение launcher записано отдельно от исходного frozen protocol.

**Ночная очередь 9 сентября:** исходный compact остановился на 597/600:
у `y0.5/task1` в исходном LIBERO-PRO пустой init asset. Это не policy fail.
Сохраняем старый failed run; на новом valid-support представлении симметрично
исключаем один недоступный случай у всех методов. 597 существующих rollout
переиспользуются, 597 reference rollout ставятся в новую очередь после smoke.
Итог: 199 сопоставимых конфигураций, 1194 rollout шести стратегий, без
перенастройки selector. Далее небольшой P5 development pilot: 36 K8 exact
pools на девяти Object/Position boundary cells, q0/q3, до 288 terminal branches.
Ранее K16 и terminal ridge critic уже проверялись, их не выдаём за новые методы.
P5 fit/holdout не открывается автоматически: сначала replay и opportunity gates.
Valid-support итог: medoid 54.09% macro-SR против max-value 54.77%, 3/6
rescue/harm, CI разницы [-3.33; +1.99] п.п. Ночная цепочка запущена в 01:01
MSK; три reference smoke прошли проверку, основная серия стартовала на GPU3
в 01:08. Остальные занятые GPU ждут.
[План, обоснование, ресурсы и команды](CONSENSUS_P5_NIGHT_PROTOCOL_20260909.md).

**Историческое дополнение 8 сентября, до поправки выше:** сначала закрываем неизменённый
compact600; параллельно завершён CPU-анализ общих candidate pools.
На 194 strict pools medoid 104/194 против max-value 111/194, 5 rescue / 12 harm;
в Position oracle совпадает с max-value, поэтому возможности reranking нет
именно в этих pools. Это exploratory, не замена closed-loop теста.
Запущена очередь `consensus_references_20260908`: после compact выполняются
3 smoke + 600 matched rollout, K4/H16, raw medoid / KeyStone-style /
KDPE endpoint adaptation. Настройки не выбираются по текущим test outcomes.
Общий отчёт сравнит шесть методов на 200 конфигурациях. Затем принимаем
решение о P5; дальнейший перебор consensus коэффициентов на holdout не делаем.
[Протокол](CONSENSUS_REFERENCE_PROTOCOL_20260908.md),
[common-pool результат](CONSENSUS_COMMON_POOL_RESULTS_20260908.md).

**Текущая поправка по ресурсам:** после завершения 392/392 development
заморожен `trajectory_medoid`. Пользователь сократил последующую проверку:
**600 вместо 4500 rollout**, K1 / max-value K4 / medoid K4, все 10 задач,
Object/Environment init2-6 и все Position x/y0.1-0.5 init1. GPU pool **3-7**,
общая очередь на свободные карты. 35 готовых эпизодов перенесены без отбора
по outcome. Исходная full-кампания сохранена как незавершённая/superseded;
выводы будут относиться к compact, не full benchmark. После одного frozen
сравнения возвращаемся к P5 без настройки по test outcomes.
[Протокол и команды](TRAJECTORY_CONSENSUS_COMPACT_PROTOCOL_20260908.md).

Исторический план до этой поправки:

Дополнение 8 сентября: по явному запросу выполняем P4c2 перед P5. Это не
пересмотр прежнего NO-GO: проверяется новая trajectory-density geometry,
normalized value gate и полный H16 benchmark на всех 10 задачах. 32 offline
настройки -> 392 development rollout -> frozen winner -> 4500 full rollout
(K1 / max-value K4 / winner K4). Не подбираем параметры по full outcomes.
После этого без повторного full-test tuning возвращаемся к P5, если SR/безопасность
не улучшились. [Протокол](TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md),
[run card](TRAJECTORY_CONSENSUS_RUN_20260908.md).

## Current decision queue: 7 September 2026

The frozen Object task-0 query-4 holdout produced the first narrow
feedback-timing result that passed both practical and confirmatory gates. The
next methods are ordered by information gain per GPU-hour:

| Priority | Hypothesis | Fast gate | Expensive stage |
|---|---|---|---|
| P0 complete | Object task0 query-4 intervention survives exact shared-prefix terminal evaluation | 100/100 strict pairs; 46% -> 64%; confirmatory PASS | retain as positive control |
| P1 closed | The fixed controller transfers to the Position `y0.2` boundary but not `x0.2` | holdout 120/120 strict; `y0.2` +1.7 pp, interaction 0 pp | efficacy and interaction gates FAIL; do not promote |
| P2 closed | Task-0 absolute-feature signed-VoF ridge transfers to new tasks | prospective 240-pair test: AUROC 0.398, adjusted CI crosses zero | gate FAIL; do not promote |
| P2b closed | A support-aware invariant CATE model predicts both commit and feedback outcomes | development OOF passed, prospective 400/400 reserve test gave adjusted -2.24 pp, CI crosses zero | efficacy FAIL; retain diagnostics only |
| P2c closed | Frozen-CLIP object/contact VoF captures task x perturbation x phase sign changes | 640 paired states; best object worst-split adjusted uplift -1.28 pp | all frozen gates FAIL; do not collect holdout |
| P2d closed | Privileged context can upper-bound task x perturbation x phase VoF interaction | within-cell +2.78 pp/AUROC 0.812, but worst transfer -0.19 pp and transfer AUROC <0.5 | gate FAIL; close re-query CATE branch |
| P3 complete | All-fail Position cells need contact recovery, not reranking | deployable H4/lift rescued 7/80 and 8/80; privileged regrasp rescued 62/80 | build perception-backed regrasp, then test once on untouched 109-state reserve |
| P3b complete, PASS | Dense RGB localization recovers most of the privileged regrasp opportunity | development 49/80; strict new-group reserve 43/72, CI [45.2%; 73.9%], 11 cells/8 tasks, no drop/safety increase | freeze result; P3c observable trigger + workspace/contact shield on new full episodes |
| P3c complete, PASS | Frozen RGB trigger turns regrasp into an online full-episode controller | untouched 40-case holdout: 32.5% -> 60.0%, CI [+12.5; +42.5] pp, 12/1 rescue/harm | freeze method; test new-cell transfer and retreat-only mechanism control |
| P3d complete, NO-GO | Full target-conditioned regrasp transfers beyond P3c cells and beats simple retreat/requery | 75/75 development: replication +47.5 pp; novel cells +14.3 pp, CI [-2.9, +31.4]; full beats retreat overall but novel-cell contrast is inconclusive | holdout remained closed; keep P3c as narrow positive result |
| P3e complete, PASS | Separate terminal-outcome heads route between continue, retreat and full regrasp | frozen 75-case holdout: full 70.7% -> router 73.3%, CI [0.0, +6.7] pp, 2/0 rescue/harm, drops 5 -> 3 | freeze as preliminary narrow selector; no tuning on holdout; test only on a new distribution split |
| P4 complete, NO-GO | Independently trained dynamics heads provide calibrated epistemic routing through quadratic JRD | 5,668 rows; JRD=0 throughout, pooled balanced AP 0.308, residual rho NaN | close this exact JRD formulation; no closed-loop filter |
| P4b complete, NO-GO | Independent residual-risk can select safer candidates than `max(value)` | frozen score reduced realized residual 2.14% on prospective data | terminal SR 58.5% -> 56.5%, 4/8 rescue/harm; close direct residual penalty, retain state alarm |
| P4c complete, development NO-GO | Training-free action-mode consensus can suppress stochastic outlier chunks before learned P5 | K3 medoid 7/40 vs max-value 8/40 vs K1 12/40; K5 guarded 6/20 vs max-value 5/20, CI [-15; +25] pp, 3 rescue / 2 harm | no confirmatory rollout; reuse saved terminal candidate pools for offline consensus ablations |
| P5 next | Task-critical pairwise outcome heads can rank actions within one exact-state pool | group-centered OOF on Object/Environment heterogeneous pools; conservative switch gate | fresh all-candidate terminal split only after within-pool/replay gates; audit generated/executed horizons |
| P6 | Tail-risk sampling catches rare plausible drops | fixed-action stress test at matched WM forward budget | CVaR/StressDream planner |
| P7 | Safety constraints require a separate shield | LIBERO-Safety offline/physical replay | constraint-conditioned fallback |

P3 completed on 4 September with 240/240 strict exact-state branches. The
deployable frequent H4 and lift/hold proposals rescued only 7/80 and 8/80
states and failed their frozen gates. A scripted regrasp using true simulator
object pose rescued 62/80 and strictly covered every deployable rescue. The
result identifies target/contact repair as the next mechanism, but the 77.5%
number is a privileged recovery upper bound rather than benchmark SR. Result,
protocol and run card:
[`RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md),
[`RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md),
[`RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md).

P3b uses a sequential, compute-gated perception funnel. Calibration has 388
RGB states / 194 groups and excludes whole groups from downstream development
and reserve. A CLIP patch-ridge localizer failed decisively. The DeepLab
object-conditioned heatmap reduced grouped-OOF pixel p90 from 41.65 to 4.12 px;
its first global-depth fit reached 1.85 cm median world-XY but missed the frozen
5.5 cm p90 gate by 0.074 cm. Object-routed depth passed at 1.64/3.33 cm
median/p90 XY. After a raw-camera orientation integration fix, screen and full
development rescued 11/20 and 49/80. The original 109-row reserve shares 37
task/init groups with development, so its 72-row / 47-group disjoint subset was
frozen before outcomes; this one-shot set confirmed 43/72, cluster CI
[45.2%, 73.9%], across 11 cells and eight tasks with 100% replay integrity.
Formal P3b gate passed. Current protocol and result:
[`PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md),
[`PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md`](PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md).

P3c is complete. Its sequential screen and development gates opened a frozen
40-case holdout with no group overlap. `baseline_h8`/RGB-regrasp success was
13/40 versus 24/40, paired delta `+27.5 pp`, 95% CI `[+12.5; +42.5]`, with
12 rescues, one harm and exact McNemar `p=0.00342`. All snapshots replayed
exactly, drop/safety did not increase and wrong-object rate decreased by
7.5 pp. The result establishes online efficacy on new initial states of the
selected cells; it does not yet establish unseen-cell transfer or isolate the
full regrasp primitive from retreat/requery. Full result:
[`PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md`](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md).
Frozen P3d design:
[`PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md`](PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md).

P3d completed all 75 development cases and 225 branches with exact replay and
fallback integrity. Full RGB regrasp again improved the eight replication
cells from 15.0% to 62.5%, but the seven-new-cell cohort improved from 74.3%
to 88.6% with CI `[-2.9%; +31.4%]`, 7 rescues / 2 harms and McNemar
`p=0.180`. The lower confidence bound failed the frozen gate, so init 45--49
holdout was never opened. Retreat-only was much weaker overall; nevertheless,
opposite harms in `x0.2/task2` and `y0.2/task8` show that a future recovery
method must route between continue, retreat and full regrasp using observable
contact/phase state. Per preregistration, the main queue now moves to P4 rather
than tuning P3d on observed outcomes. Full result:
[`PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md`](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md).

P3e then froze three independent logistic terminal-success heads over seven
RGB/localization features and opened the previously untouched init 45--49
holdout. All 75 cases and 225 branches completed with exact replay, feature and
fallback integrity. The router improved full regrasp from 53/75 to 55/75,
`+2.7 pp`, group CI `[0.0; +6.7]`, with 2 rescues / 0 harms, lower primitive
cost and two fewer drop proxies. Both rescues repeat the development
`x0.2/task2` sign reversal on new initial states. However, the router never
voluntarily selected continue and missed two continue-only oracle rescues;
McNemar `p=0.5`, and cells were not new. P3e is frozen as a preliminary narrow
safe-routing result and is not tuned further on this holdout. Full result:
[`P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md`](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md).

P4 completed on 6 September. It trained five independently initialized,
trajectory-bootstrap Gaussian heads for the residual between Cosmos' predicted
H16 endpoint and the exact MuJoCo endpoint. The full 5,668-row dataset and all
artifacts passed integrity checks. Nevertheless, the preregistered quadratic JRD
was exactly zero after clamping for every row. Pooled balanced OOD AP was 0.308,
its residual correlation was undefined, and the frozen gate returned NO-GO.
Closed-loop hard filtering therefore remained closed. Independent mean
disagreement was a useful post-hoc error signal (trajectory rho 0.609), but its
OOD ranking was factor-specific: Environment 0.795, Object 0.558 and Position
0.387 balanced AP. P4b may compare non-degenerate ensemble divergences, but it
must use a fresh candidate-outcome split for any confirmatory claim. Protocol,
result and autonomous run card:
[`P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md`](P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md),
[`P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md),
[`P4_RESIDUAL_DYNAMICS_RUN_20260906.md`](P4_RESIDUAL_DYNAMICS_RUN_20260906.md).

P4b был заморожен 7 сентября до сбора новых terminal outcomes. Реализация
сравнивает early stopping, log-variance regularization и shared-variance mean
ensemble с исходным P4 artifact. Candidate risk измеряется independent mean
disagreement, predicted/expected residual, common-covariance JRD и Monte Carlo
predictive MI. Одна формула выбирается на открытом P4 development corpus и
защищается SHA256. Единственная confirmatory проверка содержит 200 свежих
query-3 snapshots по Object, Environment и четырём новым Position cells; все
четыре candidates продолжаются до terminal outcome из одного captured state с
общей K1 continuation policy. Promotion требует положительного paired
terminal-SR delta с неотрицательной нижней границей trajectory-cluster
bootstrap CI, больше rescues, чем harms, не менее 20 heterogeneous snapshots в
двух factors и отсутствия роста drop/official safety. Протокол и run card:
[`P4B_RESIDUAL_RISK_PROTOCOL_20260907.md`](P4B_RESIDUAL_RISK_PROTOCOL_20260907.md),
[`P4B_RESIDUAL_RISK_RUN_20260907.md`](P4B_RESIDUAL_RISK_RUN_20260907.md).

P4b затем завершил 200/200 prospective snapshots и 800/800 terminal branches.
Frozen score уменьшил realized H16 residual на 2.14%, но terminal SR изменился
с 117/200 до 113/200: `-2.0 п.п.`, group CI `[-5.5; +1.5]`, 4 rescues / 8
harms. Candidate failure AUROC 0.650 оказался в основном state/cell difficulty
signal: внутри 33 heterogeneous snapshots failure ranking равен 0.509. На
Position oracle K4 совпал с max-value, поэтому reranking не имел rescue
opportunity и создал три harm. Exact replay прошёл 194/200; strict-only effect
остался `-2.06 п.п.`, следовательно integrity deviations не объясняют NO-GO.
Direct residual penalty закрыт. Residual uncertainty сохраняется для
state-level OOD/compute routing, а P5 переносит target на pairwise
task-critical terminal advantage. Полный анализ:
[`P4B_RESIDUAL_RISK_RESULTS_20260907.md`](P4B_RESIDUAL_RISK_RESULTS_20260907.md).

Перед P5 завершён короткий training-free этап P4c. Присланная формула pure
consensus-medoid не совпадает со старым H3: H3 смешивал first-action L2 с
value, тогда как P4c выбирает global medoid по discounted H5
position/SO(3)/gripper distance и полностью игнорирует value. Прямой
литературный аналог, KeyStone (arXiv:2605.08638), использует guarded medoid
крупнейшего action cluster. Поэтому P4c разделён на exact K3 reproduction и
отдельную K5 ablation `max_value` / KeyStone / Cosmos-aware guarded selector.
Последний использует совместно сгенерированные future-proprio/value только как
consistency evidence и сохраняет fallback к max-value. На 40 init pure medoid
дал 17.5% против max-value 20% и K1 30%. На отдельном K5 этапе guarded дал
30% против max-value 25%, но CI `[-15; +25]` п.п., 3 rescue / 2 harm и
рост drop-прокси с 1 до 2 не прошли development gate. Gate переключался в
56.9% queries, то есть редким вмешательство не стало. Следующий приоритет P5;
consensus можно проверить offline на уже открытых all-candidate pools P4b.
Результаты и графики:
[`CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md`](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md).
Протокол:
[`CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md`](CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md).

The frozen Object task-0 query-4 test completed on 60 unseen-init exact-state
pairs: commit-H16 SR was 38.3%, real-observation re-query SR was 60.0%, delta
`+21.7 pp`, init-cluster 95% CI `[+5.0; +40.0]`, 16 rescues / 3 harms and exact
McNemar `p=0.00443`. Integrity, practical and confirmatory gates all passed.
Full result:
[`OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md).

The untouched-task transfer is complete and negative as an unconditional rule:
all 180 commit and re-query branches on Object tasks 1-9 succeeded, giving zero
raw gain and -2.5 pp after query cost. Exact replay passed 177/180, so integrity
also missed its frozen all-pair requirement. The new tasks were a terminal
ceiling rather than useful hard transfer cells. Full result:
[`OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md`](OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md).

The first separate-process task-0 deployment and its frozen clean-GPU
replication are complete. The replication gave the strongest descriptive
deployment signal so far: 35% -> 54%, +19 pp, init-cluster 95% CI [+9, +29],
25/6 rescue/harm and p=0.000878. All six shards were directionally positive.
However, only 34/100 pairs had strict common prefixes; their sensitivity result
was 41.2% -> 55.9%, +14.7 pp, CI [0, +29.4], p=0.1797. Candidate outputs in
four shards differed already at query 0 despite identical simulator state and
clean-GPU preflight. Integrity, practical and confirmatory gates therefore
failed. This motivated the now-completed shared-prefix P0 below. Results and
first-run diagnosis:
[`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md),
[`OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md).

The follow-up identical-query diagnostic isolated the reproducibility issue:
two repeated calls within each process were exact, while two fresh processes
differed by up to 0.00745 in actions and 0.000433 in values. Candidate argmax
still matched on all three diagnostic states. Deterministic `warn` mode did not
remove the drift, and strict mode had no compatible CUDA attention kernel.
Therefore shared-prefix branching was selected as the P0 design. Diagnostic:
[`COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md`](COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md).

That P0 is now complete and confirmatory. On 100/100 strict exact-state pairs,
commit-H16 achieved 46% SR and `H8 -> real observation -> requery H8` achieved
64%: +18 pp, init-cluster 95% CI [+4, +32], 31/13 rescue/harm, McNemar
`p=0.00956`, and +15.5 pp after the frozen query cost. Full result:
[`OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md`](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md).

The subsequent frozen cross-factor development screen is also complete. It
collected 100 pairs across Position `x0.1`, `x0.2`, `y0.2`, `y0.3` and
Environment task 0; 97 passed strict replay, so integrity PASS. Position `y0.2`
gave the only strong signal: 40% -> 80%, +40 pp, CI [+10, +65], 10/2
rescue/harm and p=0.0386. Position `x0.2` gave -5 pp, Environment was a 0%
floor and `x0.1` a 100% ceiling. No cell met bidirectional effect-support. At
that stage this authorized only the frozen new-seed `y0.2` efficacy holdout,
with `x0.2` retained as a negative interaction control; its completed result
is recorded below. Full development result:
[`OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md`](OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md).

The P1 new-seed Position-direction holdout is complete. All 120/120 pairs
passed strict replay. On primary `y0.2`, commit/feedback SR was 53.3%/55.0%:
+1.7 pp, init-cluster CI [-13.3, +16.7], 10/9 rescue/harm, p=1.0 and -0.8 pp
after query cost. Control `x0.2` also gave +1.7 pp, so the direction interaction
was 0 pp, CI [-13.3, +13.3]. Both frozen gates failed and fixed cross-factor
feedback is closed. The balanced `y0.2` outcomes can now be used only as
development labels for P2; a selector requires a new untouched evaluation
split. Full result:
[`OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md`](OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md).

The subsequent P2 development analysis is complete. A leakage-safe ridge using
only current proprio, the old action chunk and its predicted future proprio
ranked signed terminal VoF with rescue-vs-harm AUROC 0.922. The screen-selected
40% router transferred descriptively to the former holdout with 9 rescues / 1
harm and +12.3 pp query-cost-adjusted gain, CI `[+2.5; +22.3]`; the fixed-mask
randomization p-value was 0.00050. This remains exploratory because the feature
family was designed after the former holdout. The model, `beta=0`, and absolute
threshold 0.1401658544 are now frozen. The outcome-blind 180-state atlas on new
Object tasks 1-9 finished with 180/180 usable states and 16 mixed cells out of
36; all atlas gates passed. Six cells at 40-60% baseline SR, covering four tasks
and both directions, were frozen. The prospective evaluation then completed
all 240/240 strict pairs on disjoint init 5-24. Commit/router SR was
59.6%/61.7%, but adjusted gain was only +0.8 pp with cluster CI
`[-5.4, +7.0]`; the router selected 24 rescues and 19 harms and its
rescue-vs-harm AUROC fell to 0.398. The gate failed. Always-requery gave
descriptive +7.1 pp, while the oracle gave +17.5 pp at a 17.5% query rate.
Transfer diagnostics show every state outside task-0 support at `|z|>5`, with
median row maximum 61.3 and maximum 654.9. The unbounded ridge used absolute
action/proprio coordinates as task/phase identifiers and is closed. P2b now
uses bounded potential-outcome heads, relative state/action features,
event-aligned phase and an explicit support gate. Full development, atlas and
prospective results:
[`SIGNED_VOF_ROUTER_DEVELOPMENT_RESULTS_20260903.md`](SIGNED_VOF_ROUTER_DEVELOPMENT_RESULTS_20260903.md),
[`SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_RESULTS_20260903.md`](SIGNED_VOF_NEW_TASK_BASELINE_ATLAS_RESULTS_20260903.md),
[`SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md),
[`SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md).

P2b is now also complete and negative. Its support-aware relative-feature CATE
model passed the development OOF gate, then was frozen before any reserve
feedback outcomes. The prospective reserve collected 400/400 strict pairs over
ten Object Position cells. Commit/router SR was 57.0%/55.75%; raw gain was
-1.25 pp and cost-adjusted gain -2.24 pp with cluster 95% CI
`[-5.52, +1.13]`. The router selected 18 rescues and 23 harms, AUROC was 0.544,
so the primary efficacy gate failed. It did beat always re-query by +8.01
adjusted pp, CI `[+3.66, +12.59]`, but that comparator itself was harmful
relative to commit. The decisive failure was a causal sign reversal:
`y0.1/task4` had +25 pp feedback effect in development, whereas
`y0.2/task4` had -22.5 pp in holdout and the router queried 39/40 states. A
q99 KNN support gate accepted 98% of holdout states and therefore did not
represent causal support. Post-hoc epistemic penalties gave small positive
point estimates only at much lower query rates, with every CI crossing zero;
they are diagnostics, not a promoted variant. P2b is closed. Full result:
[`INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md`](INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md).

P2c is complete and negative as well. Frozen CLIP ViT-B/32 object/basket patch
statistics were extracted from current and K=4 Cosmos-predicted agent/wrist
views for all 640 strict paired states. The overall selector remained the old
`relative` control: its worst-split adjusted uplift was -0.50 pp. The best
object-conditioned candidate was worse at -1.28 pp and had leave-level AUROC
0.406. All policy, worst-cell, monotonicity and auxiliary grounding gates
failed; every cluster-bootstrap efficacy interval crossed zero. Object features
did contain partial contact information (best feedback-contact AUROC 0.741 and
feedback-deadlock AUROC 0.683), but this did not identify the causal sign of
feedback value. No new holdout is authorized. Full result:
[`OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md`](OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md).

The privileged grasp/transport phase oracle completed with integrity PASS but
efficacy FAIL and is closed. Full result:
[`PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md`](PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md).

The independent initial-feedback holdout is complete. Its frozen integrity
gate failed because 3/60 separately launched query-0 argmax candidates differed,
but both nominal and selector-matched sensitivity were strongly negative. The
fixed schedule is closed. Full result:
[`INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md`](INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md).

The global CLIP semantic screen and Environment task transfer also failed.
Scalar metrics remained stronger, and semantic routing had negative uplift on
the transfer tasks. Full result:
[`SEMANTIC_VOF_RESULTS_20260831.md`](SEMANTIC_VOF_RESULTS_20260831.md).

Research is accelerated by six rules:

1. reuse saved exact-state sidecars before collecting new closed-loop rollout;
2. require a causal opportunity gate before training or planner integration;
3. branch causal horizon policies from one generated candidate pool in one
   process; separately launched GPU inference is not bitwise paired;
4. use cheap grouped/factor transfer screens before any new online planner;
5. terminally continue only branches needed by the frozen contrast;
6. parallelize independent tasks, but never tune from partial outcomes.

Scalar internal-copy penalties, H32, linear candidate rankers, fixed H8,
query-0 H8, gripper-transition H8/H16, coarse factor/phase routing and global
CLIP embeddings remain closed. They are controls, not active research branches.

### Confirmed P0: Object task-0 query-4 feedback

The causal positive control is frozen as:

$$
\pi_{q=4}: A_{64:72}^{old}\;\rightarrow\;o_{72}^{real}
\;\rightarrow\;A_{72:80}^{new}.
$$

The reset-to-terminal clean-GPU replication produced a strong positive nominal
effect but failed prefix integrity. The subsequent single-process shared-prefix
replication fixed that problem and confirmed end-to-end efficacy: 46% -> 64%,
+18 pp, CI [+4, +32], p=0.00956, with all 100 replay pairs strict. The broad
untouched-task transfer is already closed by a 100% ceiling; later deployment
must target non-ceiling cross-factor cases and become selective based on
task/contact progress rather than a universal query clock.

Generic uncertainty scores are not accepted as the trigger: the best frozen
latent score found only 1 of 16 holdout rescues at 5-10% budgets. The confirmed
mechanism is task/query-specific real-observation feedback.

### Completed P2c: object/contact-conditioned VoF

The next model predicts explicit task relations from current and
Cosmos-predicted future observations:

$$
h_m(o_t,\hat o_{t+H},p_t,a)
\rightarrow
(\widehat{\Delta d}_{target,goal},
 \hat p_{contact\ loss},
 \hat p_{drop},
 \hat p_{wrong},
 \hat p_{no\ progress}).
$$

Privileged object poses, target/receptacle identities and contacts are used to
create labels only. Deployment inputs remain RGB, wrist RGB, proprio, task text
and candidate action. Five independently initialized heads provide epistemic
dispersion; bootstrap replicas of one linear fit are not accepted as an
ensemble.

The 240-state P2 development cohort and 400-state P2b reserve are now consumed
as a 640-state **development-only** corpus. The staged experiment is:

1. use the already materialized target/receptacle and critical-event labels,
   together with object identity and perturbation direction/magnitude;
2. exclude the degenerate query-4 local goal-progress label and the two-event
   successful-release label; train auxiliary heads for target lift/contact and
   terminal drop/wrong-object/deadlock;
3. train a small frozen-vision relation head with grouped task/level/cell
   splits;
4. predict dense signed VoF and evaluate grouped/factor OOF uplift at fixed
   10/20/30% query budgets;
5. collect a new blinded exact-state split only if relation transfer and
   compute-adjusted VoF uplift pass;
6. compare `commit`, learned selective feedback and oracle feedback with
   single-process shared candidate generation;
7. move to closed-loop only after the blinded causal gate passes.

The label audit found 398 approach, 200 grasp and 42 transport snapshots. Both
branches have all 640 terminal labels. Commit/feedback positives are 247/245
for local target lift, 141/126 for target contact, 29/16 for terminal drop,
21/39 for wrong-object and 35/83 for deadlock. Local goal-progress delta is
zero in every row and successful release occurs only once per branch, so these
two targets must not drive model selection.

Minimum screen requirements are task-transfer Spearman $\ge 0.4$ for continuous
target-EEF distance/lift targets, critical-event AUROC $\ge 0.75$ where labels
have support, positive compute-adjusted VoF uplift@20%, monotone observed
effect over score quantiles, and nonnegative worst-cell adjusted gain under
leave-one-task, leave-one-level and leave-one-cell evaluation. Position
all-fail cells remain outside selector evaluation until a retreat/regrasp
proposal gives non-zero oracle coverage.

The screen did not meet these requirements. The selected deployable model did
not contain object features, and the best object model had adjusted uplift
-0.34/-0.97/-1.28 pp under leave-one-task/level/cell. Worst-cell gains and
score-quintile monotonicity also failed. Therefore the specific frozen-CLIP
linear P2c branch is closed without an untouched holdout.

### Completed P2d: causal-interaction upper bound

The next experiment is a cheap, development-only upper bound on the same 640
opened pairs. It explicitly represents task semantics, perturbation
direction/magnitude and privileged grasp phase, including their interactions.
Privileged phase makes this model non-deployable; its purpose is to distinguish
two explanations of P2c failure:

1. the visual representation omits the context needed to infer the sign of VoF;
2. the causal target is not stable enough across perturbation levels for this
   selector family, even with nearly perfect context.

Evaluation remains grouped leave-one-task, leave-one-level and leave-one-cell,
with top-20% adjusted uplift, worst-cell gain and score-quintile monotonicity.
No new GPU collection and no confirmatory claim are allowed from this reused
corpus. A failed upper bound stops the re-query CATE branch and promotes P3
recovery/abstention. A passed upper bound authorizes an observable replacement
based on higher-resolution segmentation/detection, wrist contact geometry and
action-conditioned temporal features, followed by a newly frozen holdout.

P2d is now complete and failed its transfer gate. The best 172-feature
interaction model gave adjusted gain -0.19/-0.19/+0.13 pp under
leave-one-task/level/cell, with AUROC 0.463/0.438/0.486 and every cluster CI
crossing zero. The same score worked within known cells: +2.78 pp, CI
[+0.71, +4.89], AUROC 0.812 and monotonic quintiles. This interpolation-transfer
gap is the result: feedback value can be calibrated locally but is not
OOD-invariant even with privileged phase and perturbation context. P2d closes
the current CATE route and promotes P3. Full result:
[`CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md`](CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md).

### P3b: deployable perception-backed recovery

P3 changes the intervention set instead of fitting another selector over the
same commit/feedback pair. It starts from exact states where both branches fail
and tests `retreat + open-gripper + requery` and task-aware regrasp proposals.
The first gate is oracle terminal coverage on unseen `task/init`, with drop,
wrong-object and safety endpoints reported separately. No learned selector or
closed-loop campaign is allowed until a new proposal family creates genuine
rescues beyond ordinary re-query.

The privileged opportunity gate passed, so P3b replaces simulator target pose
with an RGB heatmap and metric-depth estimate while keeping the same H8 recovery
controller. Expensive rollouts stay locked behind grouped OOF, 20-state
terminal and 80-state development gates. P3b passed its strict 72-state
new-group confirmatory reserve at 43/72. P3c then froze the primitive, trigger
and workspace shield and passed complete full-episode evaluation at 24/40
versus 13/40. P3d failed its unseen-cell development gate despite a positive
point estimate. Its untouched holdout was later opened only for the new,
separately frozen P3e hypothesis. P3e passed its practical new-init gate by
preventing two repeated `x0.2/task2` harms, but did not test unseen cells and
did not learn active continue selection. P3 is retained as a narrow
cell-specific controller and the main queue moves to P4. Thresholds and P3e
heads will not be retuned on P3c/P3d/P3e outcomes.

Этот документ является текущим планом. Frozen-протоколы
`ADAPTIVE_PLANNING_HYPOTHESES_20260813.md` и
`SURROGATE_REQUERY_HYPOTHESES_20260819.md` сохраняются как исторические
pre-registration и не переписываются после просмотра результатов.

Обзор литературы, формулы и подробное сравнение работ находятся в
[`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).

## Цель

Построить planner для Cosmos Policy, который выбирает action не только по
self-predicted value, но учитывает:

1. support action под policy distribution;
2. uncertainty action-conditioned dynamics;
3. task progress, заземлённый реальными transitions;
4. риск редкого правдоподобного failure outcome;
5. явные safety constraints;
6. стоимость дополнительного inference и более частого feedback.

Task failure и safety violation считаются разными endpoints. Рост success не
может компенсировать official safety violation.

## Зафиксированные факты из наших экспериментов

| Наблюдение | Результат | Следствие |
|---|---:|---|
| Fixed action uncertainty penalty | 151/240 против 146/240, +2.1 п.п., CI через ноль | Одного reranking недостаточно |
| Предыдущий confirmatory `h=8` + reranking | 161/240, +6.25 п.п., CI [+1.7; +11.3], Holm `p=0.0474` | Эффект воспроизвёлся в новом causal 2x2 |
| Нормированная цена adaptive requery | 1.27x policy-query cost | Нужен явный success/compute trade-off |
| Latest future-proprio surrogate transfer | case-controlled `rho=0.653`, AUROC 0.763 | Next-chunk prediction error предсказуем online |
| Surrogate-gated planner | +0.4 п.п., CI через ноль | Proprio error не равен task-critical risk |
| Early episode-fail predictor | AUROC 0.547 | Один абсолютный threshold между tasks не работает |
| Failure-mode shift | drops уменьшились, timeout вырос | Нужны отдельные progress и safety objectives |
| Selection-only causal control | 90/168 против 100/168, -6.0 п.п., CI через ноль | Internal action uncertainty пока не даёт надёжный candidate ranking |
| Horizon-only causal control | 114/168, +8.3 п.п., CI [0.0; +16.7] | Disagreement полезен как сигнал более раннего feedback |
| Combined causal 2x2 | 121/168, +12.5 п.п., CI [+4.8; +20.8], McNemar `p=0.00646` | Главный подтверждённый механизм - adaptive feedback horizon |
| Early terminal-fail prediction | лучший case-controlled AUROC 0.575 | Local prediction error предсказывается заметно лучше, чем конечный fail |
| Temporal overlap passive campaign | 312/312 rollout; core overlap AUROC около 0.5, frozen TPR 0.04-0.12 | Plain old-tail/new-prefix distance пока не является failure detector |
| Event-label audit | 26/81 collector events находятся в successful episodes | Expected release и physical drop должны быть разделены task-aware predicates |
| Coupled-noise ablation | selected RMSE ratio 1.017, correlation 0.974; success 48/72 против 49/72 | Disagreement создаётся context revision, coupling почти не убирает noise |
| Corrected boundary screening | 264 rollout; 30/40 task-OOD cases all-fail, 9 all-success, 1 mixed | Discrete task replacement даёт grounding stress, но мало paired boundary data |
| Early within-case detector | лучший preregistered AUROC 0.613; лучший exploratory 0.678, BH q=0.87 | Plain stochastic uncertainty/overlap не прошли frozen gate |
| Physical replay audit | `spatial_task/task7/init0`: 5 success, 1 confirmed target drop | Case полезен для expansion, но пока только provisional |
| LIBERO-PRO Object broad pilot | `max(value)` 54.5%, no planning 52.8%, risk-aware requery 52.1% | Выигрыш на selected boundary cases не переносится как universal policy |
| Частота текущего adaptive trigger | 42.9-43.4% query во всех трёх OOD factors | Trigger почти не адаптируется к сложности и вмешивается слишком часто |
| Broad paired ours vs `max(value)` | -2.4 п.п., 95% CI [-5.4; +0.3], McNemar `p=0.167` | Следующий тест обязан отдельно проверить selection и feedback timing |
| Dense exact-state VoF H16 | 127 positive / 143 negative / 2 zero; strict 265/272 states | Continuous consequence target устраняет event-label ties |
| Dense routing transfer | Environment AUROC 0.980, Object 0.717; новый H32 uncertainty AUROC 0.541 | H32 не подтвердил router; нужен frozen low-dimensional holdout |
| Matched H16/H32 consequence | H32 non-tied support 35/48 против 48/48 у H16; range -24.5% | Закрыть H32 как основной горизонт, сохранить H16 |
| Factor-specific candidate ranker screen | H16 macro regret -45.7%, H32 -21.1% против Cosmos; strict -42.6%/-14.1% | Заморозить H16 ranker и проверить на новых независимых `task/init` |
| Frozen H16 ranker holdout | 230 strict states, 69 groups; macro regret -43.1%, CI [-0.00577; -0.00230], gate PASS | Разрешил отдельную terminal closed-loop проверку |
| Frozen H16 ranker closed-loop | 360 pairs; macro -0.28 п.п., CI [-2.22; +1.39], gate FAIL | Локальный H16 regret не переносится; нужен conservative terminally aligned critic |
| Terminal-grounded critic development | 80 states, 8 heterogeneous pools, 5 rescues; maxV 92.5%, oracle 98.75% | Механизм существует, но все rescues сосредоточены в task 0 |
| Terminal-grounded critic holdout | tasks 8-9: 160/160 candidate branches successful; 0 switches, offline gate FAIL | Ceiling split не проверяет selector; сначала нужен proposal-opportunity atlas |
| K16 proposal opportunity | 50 states / 800 branches; Object gap +30 п.п., Position +10 п.п., Environment 0; K16 не расширил K8 oracle | Proposal diversity не bottleneck после K8; проверять value ranking |
| Action-conditioned AR value | 10 states / 80 same-pass branches; SR 30%/30%, 1 rescue/1 harm, pairwise 0.429 -> 0.308 | Простая `action -> future -> value` декомпозиция gate не прошла; перейти к grounded within-state advantage |
| Hard-cell pairwise ranker | 60 states / 480 branches; untouched maxV/raw/gated/oracle 45/15/30/60%, 0 rescue / 3 harm | Linear value/latent family не переносится; bootstrap не ловит init shift, вернуться к re-query или semantic grounded critic |
| Real-observation re-query pilot | H16/adaptive 20.0/22.5%; Position +30 п.п., Environment +5 п.п., Object -30 п.п. | Universal trigger закрыт; post-hoc factor router разрешён только для independent transfer |
| Frozen factor-router transfer | 90 pairs; route/maxV 52.2/58.9%, -6.7 п.п., CI [-13.3; 0.0], 2 rescue / 8 harm | Factor interaction не перенёсся; закрыть coarse routing и gripper-transition trigger |
| Privileged phase-VoF transfer | 67 strict states; phase route 58/67, delta 0, 1 rescue / 1 harm | Approach/grasp/transport clock не предсказывает знак feedback value; phase routing закрыт |
| Fixed query-0 H8 holdout | nominal 23/60 против 35/60, -20.0 п.п.; selector-matched 57-pair sensitivity -19.3 п.п. | Integrity failed on 3 near-tied argmax pairs, but negative direction robust; fixed initial re-query закрыт |
| CLIP semantic VoF development | 265 strict states; scalar/semantic/combined grouped rho 0.471/0.131/0.434 | Global image-text similarity weaker scalar signals; Position transfer remains negative |
| CLIP Environment task transfer | train tasks 0-3, test tasks 5/8/9; scalar/semantic2 rho 0.245/0.200, both uplift@20 negative | Global CLIP router закрыт; перейти к explicit target/receptacle/contact representation |
| Frozen Object task0 query-4 re-query | 60 unseen-init pairs; 38.3% -> 60.0%, +21.7 п.п., CI [+5.0; +40.0], 16/3, p=0.00443 | Narrow feedback schedule подтверждён; перейти к end-to-end deployment и отдельному task transfer |
| Object query-4 untouched-task transfer | 180 pairs on tasks 1-9; 100% -> 100%, adjusted -2.5 п.п.; 177/180 strict | Unconditional transfer закрыт: новый split оказался ceiling, нужен selective task/contact VoF |
| Object query-4 first full deployment | 100 pairs; nominal 46% -> 57%, strict clean-GPU 37.5% -> 52.5%; only 40/100 strict | Integrity FAIL из-за GPU 2-4 prefix divergence; запустить new-seed replication только на clean GPU 5-7 |
| Object query-4 clean replication | 100 pairs; nominal 35% -> 54%, +19 п.п., CI [+9; +29], 25/6, p=0.000878; strict 34 pairs, +14.7 п.п. | Strong descriptive replication, but integrity FAIL; перейти к deterministic shared/cached prefix |
| Object query-4 shared-prefix replication | 100 strict pairs; 46% -> 64%, +18 п.п., CI [+4; +32], 31/13, p=0.00956; adjusted +15.5 п.п. | Integrity/practical/confirmatory PASS; механизм real-observation feedback подтверждён, следующий шаг selective cross-factor transfer |
| Position direction holdout | 120/120 strict; `y0.2` 53.3% -> 55.0%, +1.7 п.п., CI [-13.3; +16.7], 10/9; `y-x` interaction 0 п.п. | Fixed cross-factor transfer не воспроизвёлся; P1 закрыт, balanced effects переходят в P2 development only |
| Signed-VoF new-task holdout | 240/240 strict; commit/router 59.6/61.7%, adjusted +0.8 п.п., CI [-5.4; +7.0], AUROC 0.398 | Task-0 absolute-feature ridge не переносится; P2 закрыт, перейти к invariant CATE + support gate |
| Object/contact VoF development | 640 strict paired states; best relative/object worst-split adjusted uplift -0.50/-1.28 п.п.; all CIs cross zero | Frozen-CLIP linear P2c закрыт; сначала проверить privileged interaction upper bound, не собирать holdout |
| Privileged context-interaction upper bound | within-cell +2.78 п.п., AUROC 0.812; task/level/cell -0.19/-0.19/+0.13 п.п., transfer AUROC <0.5 | Локальная calibration возможна, OOD transfer нет; P2d закрыт, перейти к recovery proposals |

Новый matched 2x2 разделил reranking и более раннее observation. Прямой
reranking не подтвердился, а feedback-horizon effect положителен. Добавочный
эффект risk-aware candidate при уже adaptive horizon остаётся неопределённым.

## Завершённый исторический causal 2x2

### Matched 2x2: selection x feedback horizon

Кампания `factorial_selection_horizon_20260820` полностью завершена и
проанализирована: 7 LIBERO-PRO cases, 24 новых paired seeds, четыре условия,
всего 672 rollout.

| Условие | Candidate | Horizon при disagreement |
|---|---|---:|
| `max_value` | max value | 16 |
| `action_l1` | risk-aware | 16 |
| `horizon_only_l1_h8` | max value | 8 |
| `requery_l1_h8` | risk-aware | 8 |

Primary contrasts:

$$
\Delta_A=A-B,
\qquad
\Delta_H=H-B,
\qquad
\Delta_{AH}=AH-B,
$$

$$
I=AH-A-H+B.
$$

Результат:

| Contrast | Эффект | 95% CI | Интерпретация |
|---|---:|---:|---|
| `A-B` | -6.0 п.п. | [-13.7; +1.8] | прямой uncertainty reranking не подтверждён |
| `H-B` | +8.3 п.п. | [0.0; +16.7] | более ранний feedback полезен даже с `max(value)` candidate |
| `AH-A` | +18.5 п.п. | [+10.1; +26.8] | сильный horizon effect при фиксированном risk-aware selector |
| `AH-H` | +4.2 п.п. | [-2.4; +10.7] | добавочная польза reranking не доказана |
| `AH-B` | +12.5 п.п. | [+4.8; +20.8] | combined strategy лучше на tested case/seed set |

Решение после P0:

- uncertainty/disagreement используется прежде всего как feedback-timing
  signal;
- `requery_l1_h8` остаётся лучшей эмпирической стратегией, а
  `horizon_only_l1_h8` - обязательным causal baseline;
- линейный candidate penalty не усложняется без нового support или grounded
  consequence signal;
- из-за regressions `goal_mug` (-4.2 п.п.) и `milk_task5` (-8.3 п.п.) метод не
  считается uniform improvement и требует guard;
- следующий trigger-кандидат - cross-query temporal overlap consistency.

Полный frozen protocol:
[`FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md`](FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md).
Полный разбор результата:
[`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md).

## Целевая архитектура

Не следует сразу обучать одну непрозрачную формулу. Система строится слоями и
каждый слой проходит отдельную ablation.

### 0. Cross-query temporal overlap consistency

При prediction horizon $H$ и execution length $K<H$ старый tail и новый
prefix относятся к одинаковым absolute control times:

$$
X_q=A_q[K:H],
\qquad
Y_{q+1}=A_{q+1}[0:H-K].
$$

Для каждого нового candidate можно считать

$$
D_{\mathrm{overlap},q}^{(i)}=
d\left(X_q^{(i_q)},Y_{q+1}^{(i)}\right),
$$

Для selected plan простейший published baseline - TIDE-style MSE, а между
полными candidate sets - STAC MMD/energy/Chamfer distance. Это
измеряет revision нового plan после свежего observation. Оно не гарантирует
physical correctness: большой score может быть полезной коррекцией, а малый -
последовательно ошибочным plan.

Полный protocol:
[`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).

### 1. Candidate support

Для candidate \(a_i\) считаем re-denoising consistency из tau0-WM:

$$
S_{\mathrm{RCS},i}=-
\frac1K\sum_{k=1}^{K}
E_{\mathrm{redenoise}}(a_i,t_k).
$$

Это проверяет, лежит ли action на conditional action manifold. Оно не является
ни physical uncertainty, ни probability of success.

### 2. Transition epistemic uncertainty

На реальных latent transitions обучается небольшой Gaussian ensemble:

$$
p_k(z'\mid z,a)=\mathcal N(\mu_k(z,a),\Sigma_k(z,a)),
$$

$$
U_{\mathrm{epi}}(z,a)=
H_2\left(\frac1K\sum_kp_k\right)
-\frac1K\sum_kH_2(p_k).
$$

Порог \(\epsilon_{\mathrm{ID}}\) калибруется conformal prediction по целым ID
episodes. Internal-copy std остаётся отдельным generative signal и не
переименовывается в epistemic uncertainty.

### 3. Grounded task value

Critic \(Q_{\mathrm{real}}(s,a)\) обучается только на фактически исполненных
LIBERO transitions. Imagined states используются при search, но не как
ground-truth TD targets. На depth \(d\):

$$
V(d\mid s)=\alpha V_Q(d\mid s)+(1-\alpha)V_{\mathrm{WM}}(d\mid s).
$$

Первый sweep ограничен \(D\in\{1,2\}\), \(N\in\{4,8\}\) и небольшим future
discount \(\lambda\in\{0.1,0.2\}\).

### 4. Tail outcome risk

Для фиксированного candidate world model генерирует \(K\) action-conditioned
futures. Базовая robust estimate:

$$
R_{\mathrm{tail},i}
=\operatorname{CVaR}_{\alpha}
\left[L_{\mathrm{failure}}(\hat o_i^{(1:K)})\right].
$$

StressDream-вариант не ждёт случайный bad sample, а оптимизирует initial noise
в Gaussian typical set:

$$
R_{\mathrm{stress},i}=
\max_{\epsilon\in\mathcal T}
C_{\mathrm{failure}}
\left(f_\theta(\epsilon\mid s,a_i)
\right).
$$

Random sampling и steering всегда сравниваются при одинаковом числе world-model
forwards и с held-out verifier.

### 5. Constraint risk

Для constraint \(c\) из LIBERO-Safety строится отдельный risk
\(C_i=C(s,a_i;c)\). Candidate допустим, если

$$
C_i\le\epsilon_c
\quad\land\quad
U_{\mathrm{epi},i}\le\epsilon_{\mathrm{ID}}.
$$

Если допустимых candidates нет, система выполняет fallback, а не выбирает
наименьшее из плохих значений. Первый fallback: сократить horizon и requery;
следующие варианты: recovery action и abstention.

### 6. Итоговая score после отдельных ablations

Только после подтверждения компонентов проверяется общая формула:

$$
i^*=\arg\max_{i\in\mathcal F(s,c)}
\left[
Q_{\mathrm{real}}(s,a_i)
+\eta\,\widehat V_{\mathrm{WM},i}
+\rho\,S_{\mathrm{RCS},i}
-\lambda_o D_{\mathrm{overlap},i}
-\lambda_e U_{\mathrm{epi},i}
-\lambda_t R_{\mathrm{tail},i}
\right],
$$

$$
\mathcal F(s,c)=
\{i:C_i\le\epsilon_c,
U_{\mathrm{epi},i}\le\epsilon_{\mathrm{ID}}\}.
$$

Horizon выбирается отдельно:

$$
H_q=
\begin{cases}
h, & \text{overlap/ranking disagreement, OOD или tail-risk alarm},\\
16, & \text{иначе}.
\end{cases}
$$

Это принципиально: score отвечает «что выполнить», horizon - «сколько времени
не смотреть на реальный мир», constraint filter - «что выполнять нельзя».

## Архив предыдущей очереди экспериментов

Разделы P1a-P7 ниже сохраняют постановки, сформулированные до широкого
LIBERO-PRO Object transfer test. Они полезны как каталог методов, но больше не
задают порядок запуска. Актуальная последовательность и frozen go/no-go gates
находятся в разделе «Текущий приоритет» и в
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).

### P1a. Temporal overlap consistency

**Гипотеза.** Old-tail/new-prefix disagreement даёт локальный warning до
erratic failure и является более прямым feedback signal, чем uncertainty
внутри одного query.

**Статус 24 августа 2026.** Пункты 1-3 завершены: 240 independent и 72
coupled rollout. Smoke test подтвердил форму `[Q,4,16,7]`, exact
$A_q[8:16]\leftrightarrow A_{q+1}[0:8]$ alignment и CSV/NPZ round-trip.
Plain selected/support/Chamfer/energy distances дали AUROC около 0.5;
frozen-threshold TPR составил только 0.04-0.12. Coupled seeds практически не
снизили distances.

Дополнительный audit показал, что event endpoint непригоден для
confirmatory detector claim: 26/81 событий возникли в successful episodes,
обычное выкладывание первого предмета было размечено как drop, а один
LIBERO-PRO task case передавал policy исходную filename-derived команду при
изменённой BDDL goal. Поэтому пункты 4-7 **не запускаются на текущих labels**.
Сначала выполняются semantic ground-truth repair и поиск same-case mixed
outcomes. Полный разбор:
[`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md).

**Обновление 24 августа 2026.** Ground-truth repair и 264-rollout boundary
screening завершены. Из 40 task-OOD cases 30 all-fail, 9 all-success и только
один mixed; две known controls остались confirmed mixed. Лучший preregistered
early signal дал macro AUROC 0.613, а exploratory normalized overlap shift -
0.678 при `BH q=0.87`. Plain detector не прошёл gate. Протокол:
[`GROUND_TRUTH_REPAIR_AND_BOUNDARY_SCREENING_20260824.md`](GROUND_TRUTH_REPAIR_AND_BOUNDARY_SCREENING_20260824.md).
Результаты:
[`GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md`](GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md).

1. Добавить сохранение полных candidate chunks и, на подвыборке, action latent
   embeddings.
2. Проверить exact alignment $A_q[8:16]$ против $A_{q+1}[0:8]$ и same-seed
   reproducibility.
3. Passive run: TIDE-style selected MSE, support, Chamfer, STAC MMD и
   coupled-noise distance.
4. Сравнить global split-conformal threshold с query/phase-conditioned
   functional conformal threshold.
5. Заморозить detector на whole-case validation и проверить event AUPRC,
   TPR@5%FPR и lead time на held-out PRO families и LIBERO-Safety.
6. Как supervised upper baseline обучить последовательный detector в стиле
   Hide-and-Seek только по trajectory-level success/fail labels.
7. Closed-loop сравнить weak overlap reranking и alarm-triggered short horizon.

Plain overlap metric уже существует в Sentinel/STAC и Rewind-IL/TIDE; сильный
результат должен дать sample-efficient перенос на Cosmos, warning до event и
causal planning gain. Hide-and-Seek на LIBERO-10 показывает, что learned
temporal action embeddings являются обязательным baseline при наличии failed
trajectories. Нельзя сравнивать соседние future image/value без fixed absolute
time.

### P1b. Re-denoising consistency без обучения новой модели

**Гипотеза.** RCS дополняет internal-copy uncertainty и лучше отличает
off-manifold action candidates.

1. Реализовать re-noise/re-denoise action chunks на 3-5 flow times.
2. Проверить, что score воспроизводим при fixed candidate/noise.
3. На сохранённых candidate pools посчитать top-1 retrospective oracle hit,
   pairwise candidate preference и correlation с actual next-chunk outcomes.
4. Closed-loop сравнить `maxV`, `action_l1`, `RCS`, `maxV+RCS` на новых paired
   seeds тех же mixed cases.

**Go:** положительный pooled delta без regression хуже -10 п.п. на sentinel case
или явное улучшение oracle hit/AUPRC на held-out cases.

### P2. Проверка causal action-conditioned future

**Гипотеза.** Последовательность `fixed action -> future -> value` различает
candidate consequences лучше текущего parallel self-generated value.

1. Зафиксировать observation и один action candidate.
2. Семплировать несколько future image/proprio, меняя только future noise.
3. Повторить для других actions при общих noise seeds.
4. Проверить action sensitivity, calibration prediction error и совпадение
   ordering с фактически выполненными chunks.
5. Сравнить `parallel`, autoregressive/sequential и action-conditioned modes.

Без этого теста CVaR и StressDream не запускаются: нельзя оптимизировать future,
который причинно не привязан к оцениваемому action.

### P3. Grounded critic и QWM-lite

**Гипотеза.** Реальный success/progress critic уменьшает self-value
overconfidence, а depth 2 даёт дополнительный сигнал без сильного compounding
error.

Data:

- train: completed calibration campaigns, split по целым cases;
- validation: held-out init states/tasks;
- test: новые seeds и минимум одна новая PRO family;
- labels: terminal success, dense BDDL progress, drop/contact/no-progress.

Ablations:

| Вариант | Search |
|---|---|
| `max_cosmos_value` | depth 0 |
| `max_grounded_Q` | depth 0 |
| `QWM_D1` | one action-conditioned future |
| `QWM_D2_mean` | depth 2, mean aggregation |
| `QWM_D2_CVaR` | depth 2, lower-tail aggregation |

Primary endpoint - paired closed-loop success; secondary - calibration/Brier,
drop, timeout, query latency и search regret.

### P4. JRD ensemble и conformal OOD

**Гипотеза.** Transition-conditioned JRD переносится между OOD families лучше
internal-copy std и даёт контролируемый ID false-positive rate.

1. Для каждого H16 candidate сохранить current observation, Cosmos predicted
   endpoint и exact-replay endpoint.
2. Кодировать agent/wrist RGB frozen CLIP и строить visual/proprio residual
   фактического endpoint относительно Cosmos prediction.
3. Обучить на standard `libero_object` пять independently initialized
   diagonal-Gaussian MLP heads с bootstrap по целым trajectory groups.
4. Сравнить variance of means, predicted aleatoric/total variance и analytic
   quadratic JRD с прежними value/action/future/latent disagreement metrics.
5. Калибровать trajectory-max JRD conformal threshold на отдельном ID
   calibration split и один раз открыть ID test.
6. Провести query-support-matched development transfer на LIBERO-PRO Object,
   Environment и Position. Semantic/Task остаются для будущего свежего
   confirmatory набора и не входят в текущий atlas.

Primary metrics: ID false-positive rate при $\alpha=0.1$, class-balanced OOD
AUPRC, корреляция с realized Cosmos residual и offline hard-filter utility.
Frozen gate не пройден: quadratic JRD сколлапсировал в ноль, pooled balanced
AP равен 0.308, residual correlation NaN. Closed-loop endpoint не открывался.
Post-hoc mean disagreement имеет residual rho 0.609, но противоположный
factor-specific transfer не позволяет заменить primary score без новой
проверки. Точный контракт и результат находятся в
[`P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md`](P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md) и
[`P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md).

### P4b. Robust ensemble divergence

**Гипотеза.** Независимое disagreement голов является полезным model-error
signal, но quadratic JRD с разными covariance является неподходящей
агрегацией. На development сравниваются mean disagreement,
common-covariance JRD и Monte Carlo Jensen-Shannon / predictive mutual
information. Параллельно проверяются early stopping, shared aleatoric variance
и variance regularization.

Stage завершён с **NO-GO**. Development formula была записана в
SHA256-protected artifact до открытия 200-snapshot all-candidate terminal
holdout. На новом split score снизил realized residual на 2.14%, но ухудшил SR
на 2 п.п.; within-pool failure ranking равен 0.509. Поэтому direct residual
hard-filter закрыт и paired closed-loop не запускается. Score можно применять
только как state-level difficulty/OOD alarm. Точный контракт и результат:
[`P4B_RESIDUAL_RISK_PROTOCOL_20260907.md`](P4B_RESIDUAL_RISK_PROTOCOL_20260907.md),
[`P4B_RESIDUAL_RISK_RESULTS_20260907.md`](P4B_RESIDUAL_RISK_RESULTS_20260907.md).

### P4c. Geometry-guided consensus medoid

**Статус: completed, development NO-GO (7 сентября).** Завершено 180 rollout;
pure medoid не улучшил baseline, guarded дал недоказанные +5 п.п. на 20 init.
Selector воспроизводится на 9287 queries; initial states совпадают, но часть
initial diffusion pools различается между процессами. Future-error H16/H5
не согласован и исключён из efficacy-выводов. Нового confirmatory прогона для
этих параметров нет; полные
[результаты](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md).

**Гипотеза.** Успешные stochastic action chunks образуют более плотный mode,
тогда как отдельные failure chunks являются геометрическими выбросами.

Stage A строго проверяет присланный pure selector на LIBERO-PRO Object task 0:
$K=3$, executed/scored prefix $H=5$, $\gamma=0.9$, веса
position/rotation/gripper $1/0.5/0.25$, без value и регуляризаторов. Контроли —
single sample и `max_value` при тех же initial states/seeds.

Stage B сравнивает при $K=5$ опубликованный KeyStone cluster-medoid и нашу
Cosmos-aware модификацию. Geometry предлагает dominant-mode chunk, joint
future-proprio/value agreement уточняет medoid внутри mode, а conservative
value/consensus gate решает, можно ли отойти от `max(value)`. Это сохраняет
урок P4b: state-level model-error signal нельзя безусловно превращать в
candidate penalty.

Точный контракт, формулы и statistical gates:
[`CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md`](CONSENSUS_MEDOID_PRE_P5_PROTOCOL_20260907.md).

### P5. Task-critical outcome heads

**Гипотеза.** Separate heads `drop`, `contact loss`, `wrong object`,
`no progress`, `constraint violation` полезнее общего future-proprio L2.

Сначала labels строятся из simulator state/contact и official LIBERO-Safety
checks; video/VLM labels используются только как дополнительная слабая разметка.
Сравниваются:

- per-event binary heads;
- shared encoder + multi-head outputs;
- one scalar failure head;
- existing proprio-error surrogate.

Нужны event AUPRC, calibration и lead time; episode accuracy недостаточна.

### P6. StressDream-lite

**Гипотеза.** Gradient-steered future noise находит task-critical bad outcomes
чаще best-of-N при равном compute.

Первый этап offline:

- 100 success и 100 fail/near-fail query contexts;
- target prompts/heads для drop, missed grasp, wrong placement, collision;
- best-of-4/10/40 random futures;
- 5/10/20 steering steps;
- ablation norm/isotropy/spectral constraints;
- held-out simulator-event verifier, а не тот же VLM objective.

Только если steering повышает recall без деградации physical plausibility,
добавить его online после high-risk alarm.

### P7. Constraint-conditioned safety filter

Два уровня сложности:

1. **Практический:** constraint-conditioned risk head + conformal threshold +
   `requery/recovery/abstain`.
2. **Исследовательский:** AnySafe/UNISafe-style latent reachability с learned
   fallback policy.

Evaluation идёт на official LIBERO-Safety outcomes. Отдельно измеряются task
success, official violations, intervention rate и incompletion. Эвристические
drop labels не заменяют official constraint checks.

## Benchmark matrix

| Benchmark | Роль |
|---|---|
| Standard LIBERO | ID calibration, critic/transition training, false-positive control |
| LIBERO-PRO | OOD transfer и mixed-boundary closed-loop planning |
| LIBERO-Plus | Factorized ablation camera/background/pose/noise при необходимости |
| LIBERO-Safety | Official constraint endpoint и fallback evaluation |

Новые methods сначала проверяются на 3-7 известных mixed cases, затем веса и
thresholds замораживаются и переносятся на целые held-out task/family. Queries
одного episode никогда не делятся между train и test.

## Общий statistical protocol

1. Screening: 8-12 paired seeds на case, только prespecified grid.
2. Заморозить не более двух variants на гипотезу.
3. Confirmatory: минимум 20-30 новых paired seeds на case.
4. Primary: stratified paired bootstrap CI и exact McNemar.
5. Несколько frozen methods: Holm correction.
6. Обязательно показывать min/max per-case delta и sentinel regressions.
7. Success всегда публикуется вместе с query cost, timeout, drop и safety.
8. Видео - mechanism evidence, не статистическая выборка.

## Текущий приоритет после broad LIBERO-PRO transfer

Полный frozen protocol:
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).

### P0. Broad causal horizon controls

На тех же LIBERO-PRO Object cells сравниваются `maxV-H16`, `maxV-H8`,
`horizon-only`, compute-matched random requery и прежний `risk-H8`. Selection
остаётся `max(value)` во всех новых controls. Это отделяет пользу свежего
observation от качества uncertainty-reranking и от простого роста compute.

Статус 27 августа: campaign завершила 24/24 jobs. `maxV-H16` остался лучшим
с factor-macro SR 54.5%; `maxV-H8`, `horizon-only`, `random-H8` и `risk-H8`
получили 52.8%, 52.5%, 52.1% и 52.1%. Текущий horizon-controller не переносится
на broad benchmark. Полный разбор:
[`GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md`](GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md).

### P1. Counterfactual Value of Feedback

Из одного simulator snapshot строятся две ветки: выполнить старый chunk 16
шагов или выполнить 8 шагов, requery и продолжить новым plan. Target gate - не
terminal failure, а индивидуальная польза вмешательства:

$$
\operatorname{VoF}(s)=
\mathbb E[G_{\mathrm{feedback}}-G_{\mathrm{open}}\mid s]
-c_{\mathrm{query}}.
$$

Gate проверяется при intervention budgets 10%, 20% и 30% против random policy
того же бюджета.

Реализация P1/P2 snapshot collector завершена 26 августа. Simulator replay
после ненулевого prefix имеет max state error `1.06e-15`, полный Cosmos smoke
собрал четыре candidate branches и feedback branch с replay error `8.12e-16`.
Фактический pilot собрал 272/300 states. Local VoF равен нулю для всех states;
terminal support содержит только 3 positive и 3 negative labels. Семь states
не прошли preregistered replay threshold `1e-9`.

Обновление 27 августа: offline dense geometry relabel дал 127 positive и 143
negative H16 VoF; strict subset содержит 265 states. Factor-wise OOF routing
перспективен для Environment (AUROC 0.980) и Object (0.717), но pooled model
проигрывает простому `factor x phase` baseline, а Position имеет только две
независимые `task/init` группы. Поэтому P1 прошёл mechanism-screening, но ещё
не confirmatory gate.

Matched H16/H32 pilot с шестью candidates завершён: 48 states и 288 branches.
H32 уменьшил non-tied support с 48 до 35, дал 13 zero VoF и uncertainty AUROC
0.541, поэтому более длинный consequence horizon и текущий P1 router закрыты.
Сильный `factor x phase` H32 baseline (AUROC 0.736) рассматривается только как
гипотеза расписания requery из-за малого и адаптивно сбалансированного sample.
Подробности:
[`COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md).

### P2. Grounded candidate critic и QWM-lite

Каждый candidate chunk фактически исполняется из одного snapshot. Grounded
utility включает BDDL progress и отдельные penalties `drop`, `wrong_object`,
`no_progress`, `constraint`. Critic обучается только на real transitions;
world-model rollout используется только для короткого depth-1/2 search.

На большом four-candidate H16 наборе fixed penalty и OOF rankers не проходили
gate. Новый six-candidate screen дал первый положительный результат:
factor-specific grouped OOF ridge уменьшил H16 regret относительно Cosmos на
Environment, Object и Position, factor-macro `0.003889 -> 0.002112` (-45.7%,
strict -42.6%). H32 тоже улучшен, но слабее (-21.1%, strict -14.1%).

Confirmatory holdout теперь завершён. На 230 strict states из 69 новых groups
тот же frozen ranker уменьшил factor-macro regret `0.008998 -> 0.005124`
(-43.1%), macro 95% CI для delta равен `[-0.005768; -0.002298]`. Point estimate
улучшился на каждом factor, train/holdout overlap отсутствует, formal gate
PASS. Individual CI отделён от нуля только на Position; Environment и Object
пока остаются suggestive. Полный разбор:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md).

Paired closed-loop проверка теперь завершена на 360 pairs / 720 episodes.
Offline regret gain не перенёсся в terminal success: factor-macro delta равна
-0.28 п.п., grouped 95% CI `[-2.22; +1.39]`, formal gate FAIL. Environment
ухудшился на 3.33 п.п., Object оказался на 100% ceiling, Position дал три
редких rescue (+2.50 п.п.). Ranker отклонялся от maxV на 67-94% query и в
Position выбирал value в среднем на 2.08 within-pool sigma ниже. Полный разбор:
[`FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md`](FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md).

Conservative action-conditioned grounded critic теперь реализован и проверен.
Он предсказывает residual advantage к maxV, отдельный safety risk и меняет
candidate только при положительной calibrated lower confidence bound. На
development oracle gap равен +6.25 п.п., но все пять rescues принадлежат task 0.
Untouched tasks 8-9 дали 160/160 successful branches, нулевой oracle gap и
нулевой switch rate. Offline gate FAIL, closed-loop корректно пропущен. Полный
разбор:
[`TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md`](TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md).

Этап был зафиксирован 29 августа до нового сбора в
[`TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md`](TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md).
Старый outcome-independent terminal audit содержит 52 states: лишь 6 имеют
разные success/fail outcomes между четырьмя candidates, а oracle может спасти
только 2 fail `max(value)` (SR 71.15% против 67.31%). Поэтому он не используется
как достаточный train set. Запущен targeted Object collection: восемь initial
candidates, q=0/3, common best-of-2 H16 continuation, 60 development и 20
calibration states. Opportunity gate прошёл ровно на пороге, ensemble был
заморожен до holdout, но offline gate остановил sequence из-за ceiling.

Frozen proposal-opportunity этап завершён. K16 screen собрал 50 states и 800
terminal branches. Object имеет `maxV/oracle = 50/80%`, Position `0/10%`, а
Environment `0/0%`. Nested comparison показал, что K16 не добавляет oracle
coverage к K8; на mixed pools обычный value ранжирует success против failure с
accuracy 0.476. Поэтому следующий приоритет P2 разделён по factor:

1. **Object и Position-y:** controlled K8 test action-conditioned
   `action -> future -> value` завершён. Same-pass integrity прошла, но
   evaluator не улучшил terminal ranking: 1 rescue / 1 harm, общий SR 30%
   против 30%, mixed pairwise accuracy 0.308 против 0.429 у parallel value.
2. **Environment:** selector запрещён, пока pool all-fail. Проверяется ранний
   re-query/recovery после нового real observation либо другой proposal family.
3. Learned within-state terminal-advantage ranker завершён на непересекающихся
   init 10-39. Opportunity gate прошёл, но untouched holdout дал 0 rescue / 3
   harm и снизил SR с 45% до 30%. Linear value/latent feature family закрыта.
   Init 40-49 остаются untouched reserve для нового механизма.

Протокол текущего evaluator screen:
[`AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md).
Результат evaluator screen:
[`AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md).
Frozen fallback protocol:
[`HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md`](HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md).
Fallback result:
[`HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md`](HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md).
K16 результат:
[`PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md`](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md).

Ceiling tasks остаются обязательными fallback/safety controls, но больше не
могут быть единственным calibration или holdout набором для selector.

### P3. Semantic action-conditioned consequence model

Сравниваются Cosmos reconstruction latent, frozen semantic latent и их
комбинация с proprio. Основные targets - task progress и critical events, а не
pixel MSE. Privileged simulator state разрешён для labels/evaluation, но не
подаётся planner во время deployment.

### P4. Epistemic ensemble и conformal routing

Пять independently trained probabilistic transition heads дают epistemic
disagreement. Он управляет `B`, execution horizon и expensive evaluator;
trajectory-level conformal calibration задаёт ID false-positive rate.

Статус: exact quadratic-JRD version завершена с **NO-GO**. Все clamped JRD
scores равны нулю. Mean disagreement сохранился как post-hoc P4b lead благодаря
rho 0.609 с realized residual, но пока не является frozen planner score.

### P5. RCS coarse-to-fine baseline

Re-denoising consistency проверяется как candidate-support score. Низкий RCS
может вызвать grounded evaluator или requery, но не интерпретируется как
вероятность task success.

### P6. Tail-risk / StressDream

CVaR и steered diffusion noise запускаются только после causal проверки
`fixed action -> predicted consequence`. Первый режим - offline stress testing
и hard-negative mining при matched world-model forward budget.

### P7. Constraint-conditioned safety shield

LIBERO-Safety остаётся отдельной веткой: hard feasible set,
trajectory-calibrated threshold и явный fallback. Task value не компенсирует
official safety violation.

### Порядок принятия решений

1. Сохранить `maxV-H16` как broad baseline, а fixed H8 re-query - как
   положительный causal feedback-control: он ранее дал +12.5 п.п. на matched
   2x2, но ещё не считается универсальным planner.
2. Закрыть H32, текущий uncertainty router и линейное reranking family. H16
   proxy ranker, terminal ridge, AR value и hard-cell pairwise ranker не дали
   terminal holdout gain.
3. Следующий confirmatory test направить на **execution/recovery**, а не
   подбирать новый scalar score по уже открытому atlas: `maxV-H16` против
   compute-accounted H8 re-query и critical-phase H8/H16 на hard
   Object/Position/Environment cells.
4. P4b direct residual penalty закрыт после prospective terminal NO-GO.
   Residual risk использовать только для state-level OOD, compute allocation и
   trigger re-query/recovery; не интерпретировать как action utility.
5. Следующий candidate selector обучать на group-centered pairwise/listwise
   terminal advantage и task-critical events. Переключение с max-value
   разрешать только при положительной calibrated lower confidence bound.
6. Для Object/Environment сначала увеличить число heterogeneous exact-state
   pools. Для all-fail Position добиться oracle coverage новой proposal family
   или recovery; при нулевом oracle gap selector запрещён.
7. Init 40-49 сохранить untouched для следующего механизма; новые thresholds
   не выбирать по pairwise holdout 30-39.
8. Tail risk и LIBERO-Safety shield добавлять после подтверждения causal
   consequence/recovery механизма.

### Обновление: real-observation transfer 30 августа

После pairwise-ranker failure был проведён новый causal тест execution timing.
Сначала на 40 hard states `maxV-gripper-H8/H16` дал 9/40 против 8/40 у H16,
но нарушил Object sentinel. Post-hoc router `Object -> H16`,
`Position/Environment -> adaptive` выглядел перспективно: 12/40 против 8/40.

Router был заморожен и перенесён на 90 новых `task/init` групп. Confirmatory
результат отрицательный: 47/90 против 53/90, delta -6.7 п.п., grouped CI
`[-13.3; 0.0]`, 2 rescue / 8 harm. Position дал -6.7 п.п., Environment
-13.3 п.п.; query multiplier 1.20x, $J_{0.025}$ также хуже H16. Integrity и
100% max-value fidelity прошли. Подробный результат:
[`FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md`](FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md).

Новое решение по приоритетам:

1. `maxV-H16` остаётся broad closed-loop baseline.
2. Fixed H8, raw gripper-transition H8/H16 и coarse factor router закрыты как
   универсальные политики.
3. Не строить новые task/factor exception tables на transfer split.
4. Следующий execution method должен предсказывать **знак state-level VoF**:
   продолжить текущий contact plan или получить новое observation/recovery.
5. Offline gate должен использовать exact-state H16 против H8->requery
   branches, grouped task/init holdout и отдельно штрафовать drop/wrong-object.
6. Semantic consequence и real contact/proprio имеют приоритет над ещё одним
   scalar internal-copy uncertainty score.

Ближайший сильный результат должен отвечать не «uncertainty коррелирует с
ошибкой», а одному из двух утверждений:

- более ранний feedback причинно повышает success при контролируемой цене; или
- action-conditioned robust evaluator выбирает лучший candidate на held-out
  OOD cases и уменьшает task-critical failures.

### Завершённый confirmatory этап P2

28 августа formula/features/$\alpha$ factor-specific H16 ridge были заморожены
до просмотра новых labels. Campaign собрала 240 exact-state states: 80 Object,
80 Environment и 80 Position. Query indices фиксированы как `0,3,6,9`; phase
не управляла sampling.

Primary gate использует strict replay subset, не менее 20 независимых
`task/init` на factor и 5000-resample grouped bootstrap. Требуется отрицательный
regret delta на каждом factor и factor-macro CI целиком ниже нуля. Полный
preregistered протокол:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md).

Итог offline holdout: 230 strict states, 69 groups, macro regret -43.1%, gate
PASS. Position дал сильный отдельный эффект (-66.6%, CI ниже нуля), Environment
и Object -- положительные point estimates с individual CI через ноль. Следующий
closed-loop тест использовал Environment 7-9, Object 8-9, Position x 4-5 / y
8-9. Его terminal-SR gate не пройден: macro -0.28 п.п., CI
`[-2.22; +1.39]`. Offline holdout:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md).
Closed-loop result:
[`FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md`](FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md).

# Приоритеты исследований после аудитов 10 сентября

**Оперативно заменён [вечерним планом](RESEARCH_PRIORITIES_20260910_EVENING.md)**
после завершения P5 690/690 и matched-K 120/120. Ниже сохранён утренний срез,
его слова «ещё считается/ожидает» не являются текущим статусом.

Это актуальное решение поверх исторического [roadmap](RESEARCH_ROADMAP_20260820.md).
Сводятся завершённые исследования, последние 26 LLM/NLP статей и два аудита.
Это не утверждение, что все исторические rollout повторно исполнены.
Новые результаты GPU здесь не приписываются: текущую P5-серию надо дочитать
с сервера. При подготовке этого обновления SSH несколько раз завершился
`Connection timed out during banner exchange`; локальные status-файлы устарели.

**Связь затем восстановлена, live проверка 13:11 MSK:** текущий P5 dispatcher
PID3818565, 363/690 branches, workers на GPU0/2/5. Его условная ETA около52мин
при сохранении трёх workers. Это моментальный статус, не окончательные
результаты. Новая очередь должна ждать этот dispatcher, не вытеснять его.

**Очередь подтверждена в 13:19-13:21 MSK:** серверный PID3878088,
`waiting_predecessor`, source hashes проверены. Доставка завершена, WSL
можно выключать. На сервере прошли45 новых CPU-тестов, локально75 вместе
с связанными регрессиями. Следующий GPU smoke ещё не начался.

**Новый завершённый conditional результат внутри незаконченной P5-серии:**
при CPU review435/690 branches обе фиксированные альтернативы `pool_13`
успешны10/10 против1/10 у max-value candidate4: каждая9 rescue /0 harm,
Holm p=.01171875, conditional seed-bootstrap CI разности[.7,1.0].
В `pool_11` candidate6 даёт6/10 против4/10 у candidate7,4 rescue /2 harm,
p=.6875: replication gate не прошёл.
Это один доказанно чувствительный к выбору snapshot, не два независимых
новых task и не SR уже обученного метода. Незавершённые neighboring pools
не используются для продвижения нового scorer. Сохранена отдельная
[неперезаписываемая копия этого review](campaigns/p5_candidate_replication_20260910/review_before_feedback_queue_20260910/RESULTS.md).

## 1. Главный вывод

Самая сильная линия для статьи: **разделить недостаток хороших proposals,
ошибку выбора и необходимость физического восстановления; выбирать полезное
вмешательство по task/contact-признакам, а не по одному self-value**.

Практический положительный результат уже есть у RGB regrasp. У дополнительного
learned router убедительного преимущества над самим regrasp пока нет.
Для архитектуры world-action model наиболее интересен action-conditioned
verifier, но сначала нужна воспроизводимая разница между кандидатами одного
состояния. Текущий P5 replication как раз проверяет этот необходимый ресурс.

Не начинаем очередной большой sweep `value - lambda * std`. Не называем
latent-copy disagreement независимым epistemic ensemble и не выдаём снижение
prediction error за улучшение управления.

## 2. Что подтверждено и что закрыто

SR между строками напрямую не сравнивается: разные cohorts и контроллеры.

| Семейство | Результат | Сила вывода / решение |
|---|---|---|
| P3c RGB regrasp, новые init известных Position cells | 13/40 -> 24/40; +27.5 п.п.; CI [12.5,42.5]; 12 rescue / 1 harm | Лучший узкий recovery-эффект. Развивать с сильным recovery baseline |
| P3d replication / дополнительные cells | На дополнительных 35: 26/35 -> 31/35; +14.3 п.п.; CI [-2.9,31.4] | Не подтверждён перенос; все 7 cells встречались в calibration localizer |
| P3e router против полного regrasp | 53/75 -> 55/75; 2 rescue / 0 harm; p=.5 | Дополнительный эффект пока слаб. +28 п.п. к обычному baseline нельзя целиком приписывать router |
| Shared-prefix feedback, Object task0, K4, t72 | 46/100 -> 64/100; +18 п.п.; init-CI [4,32] | Сильный положительный контроль; не универсальное время вмешательства |
| Selection x horizon, 7 cases | 100/168 -> 121/168; +12.5 п.п.; Holm p=.0258 | Совместный эффект на выбранных cases; не общий benchmark gain |
| Frozen H16 surrogate ranker | Offline regret -43.1%; closed-loop 165/360 -> 164/360 | Не продолжать оптимизацию этого local surrogate как конечной цели |
| P1/P2 timing/VoF/CATE | Переносимые улучшения не подтверждены; signed-VoF transfer AUROC .398; support-CATE reserve отрицателен | Не повторять без новых task/contact-признаков и matched controls |
| P4 ensemble residual | Quadratic JRD выродился; mean disagreement коррелирует с error post hoc | Не доказана полезность для candidate selection |
| P4b residual-risk | Residual -2.14%; SR 58.5% -> 56.5%; pooled AUROC .650, within-pool .509 | Предсказуемость не равна качеству действия; прямой penalty закрыт |
| P4c/P4c2 consensus, valid199 | OSC medoid macro 54.09% vs max-value 54.77%; CI разности [-3.33,1.99] | Универсального выигрыша нет; оставить контроль, не основной новый метод |
| KeyStone-style reference, valid199 | Macro 55.76% vs max-value 54.77% | Малый неподтверждённый gain; адаптация, не точная реплика всех режимов статьи |
| P5 repeats, 1080 branches | Selected open16 44/108, stale8 45/108, fresh8 41/108 | Свежий запрос в этой постановке не улучшил SR; это K8 initial -> K1 replacement |
| P5 candidate opportunity | In-sample K8 best gap +14.81 п.п.; held-out suffix gap 0, 5 rescue / 5 harm | Нельзя учить новый critic на одном случайном terminal label как на детерминированной истине |

Источники чисел: [общая сводка](RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md),
[valid199](CONSENSUS_AND_P5_RESULTS_20260910.md),
[P5 repeats](P5_REPEAT_FEEDBACK_RESULTS_20260910.md),
[P3c audit](P3C_IMPLEMENTATION_AUDIT_20260910.md),
[fresh8 audit](FRESH8_IMPLEMENTATION_AUDIT_20260910.md).

## 3. Что изменили последние аудиты

1. В P3c проверяется достижимость объекта, а не ожидаемая полезность regrasp.
   На двух harms объект уже поднимался до t72, затем полный primitive приводил
   к drop. Это наблюдение, не доказательство, что открывание gripper само по
   себе причина: retreat-only с теми же первыми действиями успешно завершался.
2. Post-retreat fallback может нефизично отменять выполненные действия.
   В проверенных P3c/P3d данных срабатываний ноль; эффект этим не объясняется.
   Новый controller обязан продолжать из текущего состояния и учитывать стоимость.
3. Новые относительно intervention-cohort cells не были новыми для localizer.
   Split надо строить по всей системе, включая perception calibration.
4. Fresh8 не использует предсказанную картинку вместо реальной, и off-by-one
   в проверенном пути не найден. Но старый выбранный K8 tail заменён одним
   случайным sample. Изменились K, query position, задачи и suffix controller
   относительно положительного K4/t72 опыта.
5. Разрыв действий на boundary больше у fresh8, особенно q3. Это post-hoc
   описание, не валидированный предиктор failure. Большое исправление может
   быть именно тем, что спасает эпизод.

## 4. Последние статьи: что брать и чего не заявлять

Полный разбор 26 новых PDF: [PAPER_REVIEW](../articles/llm_nlp_transfer_20260909/PAPER_REVIEW.md),
архитектурные аналогии: [ANALOGY_AND_PLAN](../articles/llm_nlp_transfer_20260909/ANALOGY_AND_PLAN.md).
Перепроверены первичные страницы PAV, CRITIC, MBR-BoN, BID, RTC и Legato.

| Источник | Перенос в наш проект | Ограничение / новизна |
|---|---|---|
| [PAV / Rewarding Progress](https://arxiv.org/abs/2410.08146) | Предсказывать изменение вероятности успеха после конкретного action | В статье прогресс задаётся отдельной prover-policy. Наши repeats с одной suffix-policy являются MC outcome labels, не полной реализацией PAV |
| [CRITIC](https://arxiv.org/abs/2305.11738), [SCoRe](https://arxiv.org/abs/2409.12917) | Проверять фактический результат и учить полезное исправление | Физическое действие необратимо: нельзя переносить текстовый rewind как бесплатный fallback |
| [MBR-BoN](https://aclanthology.org/2025.naacl-long.472/), structure-conditional MBR | Reward/value плюс согласованность внутри семантической группы | Формула value+consensus уже известна; сама по себе не научная новизна |
| [BID](https://arxiv.org/abs/2408.17355) | Согласовывать новые samples с предыдущим неисполненным tail | Наш мягкий continuity selector близок по мотиву; это контроль/адаптация, не заявка на изобретение temporal consistency |
| [RTC](https://arxiv.org/abs/2506.07339) | Conditioning/inpainting относительно committed actions в flow policy | RTC изучает асинхронность/latency. Наш paused synchronous MuJoCo тест без задержки не реплицирует этот benchmark |
| [Legato](https://arxiv.org/abs/2602.12978) | Обучать native continuation, не только выбирать sample | Требуется обучение; нельзя называть обычный tail penalty реализацией Legato |
| [Semantic uncertainty](https://arxiv.org/abs/2302.09664), [entropy probes](https://arxiv.org/abs/2406.15927) | Разделять исходы: захватил нужный объект / промах / drop / прогресс | Несколько plausible actions сами по себе не означают epistemic uncertainty |
| [Diffusion-DPO](https://arxiv.org/abs/2311.12908), [DDPO](https://arxiv.org/abs/2305.13301), [Flow-GRPO](https://arxiv.org/abs/2505.05470) | Улучшать proposals, когда selector нечего выбирать | Дороже; сначала проверить labels, coverage и differential objective для совместных action/future/value slots |

Это выбор перспективных направлений для нашей системы, не рейтинг общего SOTA.
Результаты NLP не переносим в ожидаемый LIBERO SR численно.

## 5. Приоритет методов для научного результата

### A. Phase-aware verified recovery: главный метод-кандидат

Цель: сохранить P3c rescue и не разрушать уже состоявшийся захват. Выбор:

$$
u^*(h_t)=\arg\max_{u\in\{continue,requery,retreat,regrasp\}}
\left[\widehat p_\theta(Y=1\mid h_t,u)-\beta\widehat p_\theta(drop\mid h_t,u)
-\eta c(u)\right].
$$

$h_t$ содержит только доступные до решения RGB обеих камер, proprio,
историю gripper-команд, наблюдаемое движение целевого объекта и неопределённость
localizer. Simulator poses/contact labels допустимы для обучения/оценки, но
не как скрытый online input. Низкая уверенность восприятия не означает
автоматически открыть gripper.

Сначала: физически корректный fallback, повторная локализация между servo
стадиями, проверка grasp/progress; исторический P3c не менять.
Сравнения: continue, полный P3c, исправленный physical-fallback control,
phase-aware вариант. Отдельно ablation времени: t72 control против события.
Не менять одновременно timing, perception и scoring без controls.

Данные: заранее отделённые task/perturbation cells **вне calibration** localizer,
по меньшей мере 6 development и 6 holdout cells, 5 init x 2 seeds на cell.
Конкретный manifest замораживается после проверки assets и пересечений, до
открытия outcomes; сейчас эти 120 состояний ещё не поставлены в GPU-очередь.
Первичный контраст нового controller против полного P3c, не только baseline.
Для продвижения: +10 п.п. practical gain на development, затем новый frozen
holdout с CI нижней границей выше нуля и без убедительного роста drop harms.
Это проектный gate, не power calculation и не гарантия статистической мощности.

### B. Action-conditioned task-critical verifier: лучший путь через world model

$$
\widehat Q_R(o,A)=\frac1R\sum_{r=1}^{R}Y(o,A;\xi_r),\qquad
\widehat D_R(o,A)=\frac1R\sum_r\mathbf1[drop\mid o,A,\xi_r].
$$

Учить $f_\theta(o,A,\widehat s')$ по repeated action-dependent outcomes,
отдельным contact/target/progress heads и terminal success. Baseline:
state-only difficulty predictor; он не должен выигрывать within-pool ranking
только из-за простых/сложных задач. Pairwise loss использует пары из **одного**
состояния и uncertainty веса для labels, а не общую success/fail корреляцию.

Готовый prerequisite уже считается: [690 branches](P5_CANDIDATE_REPLICATION_PROTOCOL_20260910.md).
Gate: фиксированные альтернативы повторяются на новых suffix seeds; на новых
pools split-repeat выбор имеет положительную разницу. Если gap не переносится,
не запускаем большой critic. Даже PASS на двух states не доказывает generalization.
Для полноценного fit сначала расширяем число независимых cells/states;
8 соседних pools недостаточно для сильной neural head.

Научная новизна возможна в task-critical grounded verification для совместных
action/future/value Cosmos slots и устойчивости к suffix noise. Общие MC Q,
reward ranking и PRM не являются нашей новизной.

### C. Budget-matched, continuity-aware feedback: ближайшая исполнимая проверка

Отделяем K, наблюдение и смену плана. Реализовано пять ветвей с общим K4/H16
prefix и suffix. Один коэффициент .10 фиксируется до новых outcomes.
Полный [протокол и команды](FEEDBACK_CONTROLS_PROTOCOL_20260910.md).

$$
i^*=\arg\max_{i\le4}\{\widehat V_i-0.10C(A_i^{new}[0:8],A^{old}[8:16])\}.
$$

Это дешёвый механизм-контроль, не новый SOTA. Если K4 возвращает gain, не
нужно приписывать его continuity. Если continuity снижает jumps, но не улучшает
SR, не продвигаем smoothness как цель. Для следующего этапа сравнивать с BID/
RTC-подобным conditioning; не вставлять уже прошедшие actions в будущие slots
при observation $o_{t+8}$: это нарушает временную семантику.

### D. Semantic risk / CVaR и улучшение генератора: после gates

P6 risk-sensitive planning требует нескольких **action-conditioned** futures,
а не разброса value у разных одновременно сгенерированных actions. Оценивать
калибровку task-critical costs и реальный terminal SR при равном NFE.
P7 safety shield проверять отдельно; наши proxy drop/deadlock не являются
официальным LIBERO-Safety score.

Если all-fail pools остаются all-fail после repeats и полезный RGB recovery
создаёт новые хорошие actions, приоритет смещается к generator adaptation:
supervised recovery/continuation, затем preference/flow RL. Не начинать
дорогой Flow-GRPO до очистки reset, data split и offline reward objective.

## 6. Исполнимая очередь и порядок

| Порядок | Работа | Статус этого изменения |
|---|---|---|
| 0 | Не прерывать P5 candidate replication; по окончании strict CPU analysis | 435/690 при CPU review; fixed pool13 PASS, neighboring transfer ещё не завершён |
| 1 | K4 feedback + continuity: 3 smoke states x 5 ветвей | Доставлено и поставлено в серверную очередь PID3878088 после predecessor |
| 2 | Те же 5 ветвей, 3 cells x 4 init x 2 seeds = 120 ветвей | В автономной очереди после технического smoke gate |
| 3 | Paired statistics, SR/cost/drop proxy, видео, таблицы | Автоматический CPU analysis после screen |
| 4 | Phase-aware recovery v2 и независимый manifest | Научный приоритет A; ещё требует реализации/валидации, не запущен |
| 5 | Task-critical scorer или proposal improvement по результату gate | Условный план, не скрытый большой auto-fit |

Из-за недоступности SSH различаем **подготовлено**, **локальная доставка
ожидает связи**, **серверный dispatcher принят**, **идёт GPU worker**.
Источники истины: `delivery_status.json` локально и `sequence_status.json` на
сервере в `experiments/campaigns/feedback_controls_20260910/`.
Доставка повторяется до 48 часов, требует включённого WSL; после приёма
серверный detached dispatcher от WSL не зависит. Старые scripts/runtime не
перезаписываются. Занятые GPU пропускаются; до трёх workers на свободных 0-7.

## 7. Как быстрее получить научный вывод

- Не запускать все P1-P7 параллельно: одна проверяемая причина на этап.
- Переиспользовать общий pool/snapshot для всех arms, держать модель в памяти
  на batch из нескольких случаев, рендерить реальные видео вместе со сбором.
- Считать logical NFE отдельно от фактической экономии shared collection.
- Smoke останавливает неверный replay/inputs/assets; ошибка инфраструктуры
  не записывается как policy fail.
- Decision gate на завершённой серии, не по промежуточно красивому графику.
- Два seeds одного init не два новых task. CI кластеризовать по init и
  отдельно показывать каждый cell; independent transfer требует новых cells.
- Для ICLR нужен эффект нового компонента против сильного published/recovery
  control. Количество rollout само по себе и формула из нескольких uncertainty
  метрик не заменяют новизну и перенос.

Наиболее реалистичная статья сейчас: диагностически обоснованное сочетание
grounded verification и безопасного recovery, с явной демонстрацией того,
когда best-of-K / self-value / generic resampling не помогают. Пока это
исследовательская гипотеза и план, не доказанный универсальный метод.

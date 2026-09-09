# Итоги исследования и готовность к научной публикации

Дата анализа: 8 сентября 2026 года.

Дополнение после выбора целевой конференции:
[trajectory-consensus и готовность к ICLR](TRAJECTORY_CONSENSUS_ICLR_ASSESSMENT_20260908.md).
В нём отдельно разобраны формулы последнего метода, 392 development rollout,
пересечение с KeyStone/KDPE и конкретные пробелы перед ICLR 2027.

## 1. Краткое заключение

В проекте есть содержательные положительные результаты, воспроизводимые
контрфактические эксперименты и полезные отрицательные результаты. Этого уже
достаточно для подготовки исследовательского preprint и содержательной
workshop submission. Это оценка исследовательского материала, не гарантия
принятия и не утверждение о готовой рукописи.

Для сильной основной статьи CoRL/RSS я пока считаю доказательную базу
незавершённой. Не хватает прежде всего чётко выделенной новизны, убедительного
переноса лучшего метода и сравнения с ближайшими опубликованными подходами.
Проблема не в малом суммарном количестве запусков: тысячи выполнений не
заменяют независимые задачи, новые perturbation cells и правильные controls.

**Самая сильная линия сейчас: исправление восприятия/контакта через RGB
regrasp и правильно выбранное время получения реального observation.**
Универсальное улучшение planning через `value - lambda * uncertainty`
не подтверждено. Это разные научные выводы; подменять один другим нельзя.

## 2. Границы этого анализа

Сопоставлены июльский validation, августовские replication/adaptive/surrogate
серии, factorial controls, temporal-overlap и ground-truth audit,
grounded/terminal ranking, feedback/CATE, recovery P3-P3e, ensemble P4/P4b,
consensus P4c и завершённый development P4c2. Навигация по исходным отчётам:
[индекс экспериментов](README.md) и [roadmap](RESEARCH_ROADMAP_20260820.md).

Ключевые числа P3c, P3e и shared-prefix feedback сверены с локальными CSV;
для остальных серий использованы итоговые отчёты и их machine-readable
сводки. Полный повторный MuJoCo replay каждого исторического эпизода и
покадровая проверка всех видео в этот анализ не входят.

Свежий статус `trajectory_consensus_20260908_compact` проверить не удалось:
две SSH-попытки завершились `Connection timed out during banner exchange`.
Это не доказательство остановки или завершения эксперимента. Поэтому
600-rollout evaluation не включён в итоговые подтверждённые результаты;
для P4c2 ниже используется только завершённый development 392/392.
Исходный full4500 ранее заменён compact-протоколом, а не досчитан.

Новые эксперименты в рамках этого анализа не запускались. Файл сохранён
локально; синхронизация этого отчёта с сервером пока не выполнена.

## 3. Лучшие результаты и сила доказательств

SR в разных строках нельзя ранжировать напрямую: задачи, начальные состояния,
базовые policy и критерии включения в выборку различаются.

| Результат | Честное сравнение | Эффект и статистика | Что можно утверждать |
|---|---|---|---|
| P3c, RGB-triggered regrasp | H8 baseline 13/40 -> 24/40, новые init восьми выбранных Position cells | +27.5 п.п.; CI [+12.5; +42.5]; 12 rescue / 1 harm; McNemar p=0.00342 | Сильное улучшение на этих cells, без simulator object pose во входе trigger |
| P3e, Recovery Outcome Router против baseline | H8 baseline 34/75 -> router 55/75 | +28.0 п.п.; CI [+17.3; +40.0]; 23/2; p=0.0000194 | Вся система recovery лучше baseline на этом наборе |
| P3e против сильного recovery control | Full RGB regrasp 53/75 -> router 55/75 | +2.7 п.п.; CI [0; +6.7]; 2/0; p=0.5 | Предварительное улучшение routing, не статистически убедительное превосходство над full regrasp |
| Shared-prefix query-4 feedback | Object task0: commit 46/100 -> feedback 64/100 | +18 п.п.; init-cluster CI [+4; +32]; 31/13; p=0.00956 | Сильное узкое свидетельство полезности feedback именно в этом месте траектории |
| Factorial selection x horizon | maxV 100/168 -> selection+adaptive H8 121/168 | +12.5 п.п.; CI [+4.8; +20.8]; Holm p=0.0258 | Улучшение на семи фиксированных cases; не доказан эффект на произвольной новой задаче |
| P3b, perception-backed recovery | 43/72 исходно трудных reserve states успешно восстановлены | 59.7%; group CI [45.2; 73.9]; 47 независимых task/init groups | Условная recovery success rate, не общий benchmark SR |

Источники: [P3c](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md),
[P3e](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md),
[shared-prefix](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md),
[factorial](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md),
[P3b](PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md).

### Лучший практический механизм: RGB regrasp

Замороженная Cosmos Policy остаётся базовым контроллером. Дополнительный
localizer на текущем agent-view RGB определяет целевой объект из команды.
Проверяются confidence, workspace и достижимость. Затем выполняется короткая
последовательность open/retreat/relocalize/approach/grasp/lift, после чего
управление возвращается Cosmos. Все primitive actions входят в общий лимит
280 шагов; увеличение лимита не объясняет выигрыш.

P3c проверяет trigger только на t=72, а не непрерывно и не до любого возможного
fail. Prefix использует H16, continuation использует H8 и K4 max-value.
Это надстройка perception/recovery, а не новая архитектура основного world
model и не доказательство latent-uncertainty planning.

Прямая P3d абляция отличает recovery от простого retreat/requery: на 75
development cases полный regrasp дал 56/75, retreat-only 36/75, baseline
32/75. Но на семи новых cells full против baseline дал +14.3 п.п. с CI
[-2.9; +31.4]; перенос не прошёл frozen gate. Эта отрицательная проверка
обязательно должна сопровождать положительный P3c результат.
[P3d](PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md).

### Лучший имеющийся selector recovery options: P3e

Три независимые logistic heads оценивают успех доступных вариантов:

$$
\hat p_j(x)=\sigma(w_j^\top z(x)+b_j),
\qquad j\in\{\mathrm{continue},\mathrm{retreat},\mathrm{regrasp}\}.
$$

$$
j^*(x)=\arg\max_j\left[\hat p_j(x)-0.25\frac{c_j}{280}\right],
\qquad (c_j)=(0,3,25).
$$

Семь признаков: предсказанные RGB-localizer world x/y/z, peak probability,
entropy, score range и расстояние target-to-EEF. При failed initial trigger
используется continue. Ground-truth object pose и будущие outcomes не входят
в признаки выбора. Router frozen до открытия init45-49; его outcomes
вычисляются по реально выполненным exact-state ветвям выбранных options,
а не по предсказанному success.

На holdout router выбрал 48 full regrasp, два retreat и 25 обязательных
continue-fallback. Добровольного выбора continue не было. Оба выигрыша над
full получены в одном известном cell `x0.2/task2`, на новых init47/49.
Следовательно, +28 п.п. к baseline в основном принадлежат самому recovery,
а не новому learned routing. Внутренний PASS с CI, касающимся нуля, не
равнозначен доказанному статистическому превосходству архитектуры.

### Самый чистый причинный результат: shared-prefix feedback

В query4 при t=64 candidate pool генерируется один раз; ветви имеют одно
MuJoCo/controller state и один выбранный action chunk:

$$
\mathrm{commit}: A_{64:80}^{old},
\qquad
\mathrm{feedback}: A_{64:72}^{old}\to o_{72}^{real}\to A_{72:80}^{new}.
$$

Оценка эффекта:

$$
\widehat\Delta_{FB}=\frac1N\sum_i
\left(Y_i^{feedback}-Y_i^{commit}\right)=0.18.
$$

На 100 парах / 50 init groups replay integrity прошла полностью. Это
подтверждает конкретную интервенцию, но не универсальный детектор момента
ошибки. Ранее отдельный 60-pair holdout дал согласующийся +21.7 п.п.
На Object tasks1-9 обе ветви достигли 100%, а Position-direction holdout
не подтвердил перенос: +1.7 п.п. с широким CI. Не следует соединять эти
выборки в одну цифру общего SR.
[Object holdout](OBJECT_Q4_REQUERY_HOLDOUT_RESULTS_20260901.md),
[task transfer](OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md),
[Position transfer](OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md).

## 4. Вся исследовательская траектория

Таблица группирует серии по гипотезам. Relabel, offline-анализ старых traces
и видео-replay не считаются новыми независимыми экспериментальными данными.

| Ветка | Основной результат | Научный статус / источник |
|---|---|---|
| Standard LIBERO и natural OOD screening | ID 72/72; PRO screening 82/106; расширенный validation 1078 strategy executions | Контроль интеграции и источник hard cases, не новый SOTA. [Июльский итог](LIBERO_COMPLETE_RESULTS_20260724.md) |
| Static action/value/combined/overconfidence penalties | Denoise-10 replication: 52/100 -> 56/100, CI [-5; +13], 14/10 | Универсальное преимущество не подтверждено. [Replication](campaigns/replication_safety_analysis_20260813/README.md) |
| Adaptive horizon / phase gate | 115/180 -> 143/180, +15.6 п.п.; phase-only 130/180 | Положительные frozen-seed результаты на шести cases, с replay outcome disagreement 4.4-9.4%. [Adaptive](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md) |
| Surrogate-triggered requery | Surrogate 146/240 -> 147/240; прежний requery 161/240 | Предсказание ошибки переносится лучше, чем planner gain. [Surrogate](SURROGATE_REQUERY_RESULTS_20260820.md) |
| Selection x horizon 2x2 | 672 rollout; selection-only -6.0 п.п., horizon-only +8.3, combined +12.5 | Feedback важнее текущего penalty; case-level CI combined [-4; +29] ограничивает generalization. [Factorial](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md) |
| Temporal overlap | 312 rollout; selected RMSE AUROC около 0.50; event labels частично невалидны | Не валидированный fail detector и не опровержение всех temporal методов. [Overlap audit](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md) |
| Исправленный boundary screening | 264 rollout; best preregistered macro AUROC 0.613, CI включает 0.5 | Natural fail есть, переносимого раннего detector нет. [Screening](GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md) |
| Broad Object/Position/Environment horizon controls | 299 matched episodes на метод; maxV-H16 macro 54.5%, остальные 52.1-52.8% | Выигрыш boundary controllers не перенёсся на широкий набор. [P0-P2](GROUNDED_SELECTIVE_PLANNING_RESULTS_20260827.md) |
| Dense H16/H32 consequence | Dense relabel снял ties; H32 не улучшил gate | Полезная починка targets, не terminal improvement. [Dense](DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md) |
| Frozen H16 ridge ranker | Offline regret -43.1% на 230 strict states; closed-loop 165/360 -> 164/360 | Главный пример local-target/terminal-outcome gap. [Holdout](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md), [720 episodes](FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md) |
| Terminal critic | Holdout все 160 candidates успешны; переключений 0 | Нет opportunity/support для проверки ranking; не доказательство качества critic. [Critic](TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md) |
| K4/K8/K16 proposal opportunity | 50 states / 800 terminal branches; K16 не добавил oracle success к K8 в Object/Position | Sampling не устраняет all-fail pools. [K16](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md) |
| AR action -> future -> value | 10 states / 80 одинаковых candidates; parallel и AR SR 30%; mixed-pool accuracy 0.429 -> 0.308 | Малый отрицательный pilot, не доказательство общей бесполезности авторского AR planning. [AR](AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md) |
| Hard-cell pairwise ranker | Holdout maxV/raw/gated/oracle = 45/15/30/60% | Замороженный selector не перенёсся. [Pairwise](HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md) |
| Requery factor/phase/semantic routers | Factor routing 53/90 -> 47/90; fixed query0 отрицателен; CLIP semantic screen gate FAIL | Нельзя назначать feedback только по OOD factor или глобальному semantic score. [Factor](FACTOR_ROUTED_REQUERY_TRANSFER_RESULTS_20260830.md), [q0](INITIAL_REQUERY_HOLDOUT_RESULTS_20260831.md), [phase](PHASE_VOF_TERMINAL_TRANSFER_RESULTS_20260831.md), [semantic](SEMANTIC_VOF_RESULTS_20260831.md) |
| Query4 Object | 60-pair holdout +21.7 п.п.; 100-pair shared-prefix +18 п.п. | Лучшее узкое причинное подтверждение feedback. [Shared-prefix](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md) |
| Separate-process deployment | Nominal +11/+19 п.п.; часть prefixes расходится до intervention | Описательные результаты, не замена shared-prefix подтверждению. [Первый](OBJECT_Q4_SCHEDULED_CONTROLLER_RESULTS_20260901.md), [clean replication](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_RESULTS_20260902.md) |
| Feedback transfer | 180 Object-task pairs на ceiling; Position 120 strict pairs, interaction 0 п.п. | Перенос узкого query4 controller не подтверждён. [Task](OBJECT_Q4_REQUERY_TASK_TRANSFER_RESULTS_20260901.md), [Position](OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md) |
| Signed-VoF / invariant CATE | 240-pair transfer AUROC 0.398; 400-pair reserve 57.0% -> 55.75% | Лучше always-query не означает лучше commit. [Signed](SIGNED_VOF_NEW_TASK_HOLDOUT_RESULTS_20260903.md), [CATE](INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md) |
| Object/contact CLIP и privileged context | Те же 640 strict pairs; unseen-task/level gates FAIL | Закрыты конкретные linear-feature formulations, не вся object-centric идея. [CLIP](OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md), [context](CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md) |
| P3 recovery opportunity | H4 7/80, blind lift 8/80, privileged regrasp 62/80 | Контакт/локализация ограничивают успех; 77.5% является условным privileged upper bound. [P3](RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md) |
| P3b/P3c/P3d/P3e | RGB recovery работает; online P3c +27.5 п.п.; P3e ещё +2.7 над full | Лучшее направление, но ограниченный transfer и слабое дополнительное routing advantage. Источники в разделе 3 |
| P4 independent dynamics | 5668 переходов; quadratic JRD после clamp равен нулю | Вырождение конкретного score, не отрицательный результат для всей epistemic-UQ идеи. [P4](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md) |
| P4b residual-risk | 200 states / 800 branches; residual -2.14%, SR 58.5% -> 56.5%; 4/8 | Предсказуемость transition не равна успеху. Strict subset 194 states даёт тот же знак. [P4b](P4B_RESIDUAL_RISK_RESULTS_20260907.md) |
| P4c consensus | Pure K3 medoid 7/40 против maxV 8/40; guarded K5 6/20 против 5/20, CI [-15; +25] | Не подтверждён. Это H5/K3-K5, не тот же протокол, что новый H16/K4. [P4c](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md) |
| P4c2 trajectory medoid | Development macro 57.50% -> 59.17%; 3/2, CI [-3.33; +8.33], p=1.0 | Выбран для дальнейшей проверки, ещё не лучший подтверждённый метод. [Development](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/RESULTS.md), [compact protocol](TRAJECTORY_CONSENSUS_COMPACT_PROTOCOL_20260908.md) |
| Official LIBERO-Safety | 144 rollout, success и safe success 0; official violations 4 | Не подтверждён safe planner. Semantic suite была заблокирована отсутствием init. [Safety](campaigns/replication_safety_analysis_20260813/README.md) |

P5-P7 в roadmap являются направлениями дальнейшей работы. Нельзя приписывать
им результаты предшествующих negative screens или писать, что весь roadmap
уже экспериментально проверен.

## 5. Самые важные научные выводы

### 5.1. Три разных вопроса требуют разных метрик

1. Насколько трудное текущее состояние?
2. Какой candidate лучше из одного и того же состояния?
3. Какое вмешательство улучшит результат относительно продолжения policy?

P4b даёт особенно наглядный ответ: global failure AUROC 0.650, но within-pool
ranking 0.509 на 114 success/fail candidate pairs. Score различает лёгкие и
трудные states гораздо лучше, чем хорошие и плохие действия внутри state.
У P3e хороший AUROC отдельных outcome heads также не гарантирует правильную
разность между heads и правильный treatment choice.

Если uncertainty является одной величиной на весь state, её вычитание
вообще не меняет candidate ranking:

$$
\arg\max_i[\hat V_i-\lambda U(s)]=\arg\max_i\hat V_i.
$$

Для reranking нужен candidate-dependent score. Межсемпловый action/value
разброс и internal-copy std одного sample имеют разные роли; оба не становятся
калиброванной epistemic uncertainty автоматически.

### 5.2. Точность world model не является достаточной целью управления

H16 critic улучшил offline dense regret на 43.1%, но closed-loop SR не вырос.
P4b уменьшил prediction residual на 2.14%, но SR стал ниже. Это два разных
подтверждения разрыва между surrogate target и task outcome в наших настройках.
Нельзя обобщать их до утверждения, что предсказательная точность никогда не
нужна. Нужно моделировать task-critical consequences и отдельно проверять
выбор действий по terminal outcome.

Для диагностики next-chunk error полезны frozen proprio surrogate
(в factorial анализе case-controlled rho=0.653, error-tail AUROC=0.763)
и independent ensemble mean disagreement (P4 post-hoc rho=0.609).
Но это не готовые early-fail detectors. До публикации таких correlations
нужно повторно проверить horizon alignment именно в использованных traces:
ранние H8/H5 серии нельзя смешивать с prediction H16.

### 5.3. У reranking есть ограничение, заданное набором candidates

Пусть $Y(s,a_i;\pi_{cont})$ обозначает terminal success после исполнения
candidate и одной фиксированной continuation policy. Тогда

$$
SR_{oracle,K}=\frac1N\sum_s\max_{i\le K}Y(s,a_i;\pi_{cont}),
\qquad SR_{selector,K}\le SR_{oracle,K}.
$$

Если все candidates провальны, перестановка scores их не спасёт. Если
`max(value)` уже достигает oracle, переключения могут только сохранить
outcome или навредить. Например, в P4b Position oracle K4 совпал с baseline,
но penalty создал три harm. P3 показал, что добавление целевого regrasp может
расширить полезное множество действий, где простое увеличение K не помогло.
Oracle при этом использует будущие simulator outcomes и служит только
диагностическим upper bound, не deployable planner.

### 5.4. Ground truth и воспроизводимость меняют научный вывод

До ground-truth repair expected release ошибочно попадал в drop, а в части
локальных task-OOD suites команда не соответствовала изменённой BDDL goal.
Такие строки не подходят для публикации как physical-failure onset.
Новые определения различают premature release, successful placement,
wrong-object interaction и timeout. Timeout не равен доказанному падению.
[Audit](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md).

Одинаковый seed также не гарантирует identical prefix между процессами.
Поэтому наиболее сильные causal results используют один captured runtime
state и shared candidate pool, а не только совпадающие числа seed.
[Reproducibility diagnostic](COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md).

## 6. Где ещё есть ограничения публикационной достоверности

| Ограничение | Что необходимо сделать |
|---|---|
| Много seeds на мало cells | Отдельно сообщать число tasks, objects, cells, init и seeds; основной transfer split делать по целым groups |
| Долгая адаптивная история гипотез | Freeze нового основного claim, comparator, MDE, sample size и familywise correction; новый test не выбирать по наблюдённому успеху |
| Разные H/K/denoising и режимы value | Фиксировать generated horizon, executed horizon, число candidates, model calls и parallel/AR для каждой таблицы |
| Наш maxV не обязательно авторский planning | Основные текущие сравнения используют joint parallel values; не называть их полной репликацией AR planning Cosmos без отдельного теста. [Текущий контракт](TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md) |
| Partial traces / truncated future endpoints | Проверять query chronology, completeness и совпадение prediction/realization horizons, не только отсутствие traceback |
| Localizer знает объекты calibration | New init/cell не равны unseen object, новой инструкции или новой policy |
| Simulator fallback после intervention | В collector failed post-retreat guard подменяет branch исходным baseline и обнуляет primitive cost. На проверенном P3c holdout все 25 post-guards прошли; в routed P3e все 50 тоже прошли. Нынешние основные gains этим не объясняются, но для deployable policy нужен физически исполнимый fallback без отмены уже выполненных действий |
| Статистические и демонстрационные видео | P3c/P3e основной сбор был без видео; поздний seeded replay должен быть явно подписан и не выдаваться за тот же exact statistical rollout |
| Safety proxies | Нулевые PRO safety flags не доказывают LIBERO-Safety performance. Нужны violation rate и safe-success одновременно |

Проверенный fallback находится в
[`collect_online_perception_regrasp.py`](../scripts/collect_online_perception_regrasp.py).
При оценке новой версии не удалять guard-fail случаи из test: исполнять
реальный fallback и учитывать его время, действия и outcome.

## 7. Что уже известно в литературе

Нельзя заявлять новизной само сокращение action horizon, дисперсию samples,
выбор medoid или идею recovery после alarm.

| Работа | Уже существующая идея | Что требуется от нашей статьи |
|---|---|---|
| [Diffusion Policy](https://diffusion-policy.cs.columbia.edu/) | Генерация action sequence и receding-horizon control | Новым должен быть способ выбора интервенции или научный вывод, не сам H16/H8 |
| [Sentinel / STAC](https://proceedings.mlr.press/v270/agia25a.html) | Temporal inconsistency и отдельная проверка task progress для разных failure modes | Сравнение с temporal/progress baselines; нельзя объявлять открытием, что consistency не ловит все fail |
| [UQ for Flow-Based VLA](https://arxiv.org/abs/2606.18043) | Ensemble velocity-field disagreement для failure detection и active adaptation | Наш stochastic dispersion одного checkpoint не является точной репликацией independent-ensemble VFD |
| [KeyStone](https://arxiv.org/abs/2605.08638) | Clustering action samples и medoid крупнейшей моды | Trajectory consensus требует прямого comparison и отличия по geometry/outcome, а не переименования medoid |
| [Rewind-IL](https://arxiv.org/abs/2604.16683) | TIDE + calibrated failure detection + восстановление проверенного состояния | Сравнить не только detectors, но и recovery mechanisms; точно описывать необходимый runtime access |

Исходный [Cosmos Policy](https://arxiv.org/abs/2601.16163) уже генерирует
actions, future observations и value для planning. Новизна нашей работы
должна лежать в decision rule, причинной диагностике или переносимом recovery,
а не в самом использовании этих выходов. Более широкий связанный обзор:
[статьи проекта](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).

Это проверка ближайших идей, не исчерпывающий claim novelty/SOTA search.
Перед submission нужен отдельный related-work audit и воспроизведение
совместимых baselines на нашем frozen test, без сравнения процентов из
несовместимых benchmark-таблиц.

## 8. Достаточно ли для конференции

### Для workshop / focused empirical paper

Есть основа для содержательной работы уже сейчас: валидные положительные
interventions, mechanism ablations, отрицательные transfer results,
exact-state dataset и исправления evaluation. Нужны связная рукопись,
открываемые воспроизводимые artifacts и честные ограничения. Требования
конкретного workshop и его archival status проверяются отдельно.

### Для основной CoRL/RSS статьи

Моя оценка: **пока не готово как убедительно новый универсальный метод**.
Лучшие recovery gains ограничены знакомыми объектами/Position cells;
P3e increment над сильным regrasp пока мал и статистически не отделён от нуля.
Не установлено превосходство над современными опубликованными recovery
методами. Один checkpoint Cosmos и одна simulator family не поддерживают
обобщение на весь класс world-model policies.

Это не означает, что обязательно нужен новый большой neural backbone или
новый SOTA SR. [CoRL CFP](https://www.corl.org/contributions/call-for-papers)
оценивает оригинальный значимый robot-learning вклад, просит ограничения и
поощряет реальные роботы либо убедительное подтверждение переносимости
симуляционных результатов. Реальный робот существенно усилил бы нашу
работу, но не объявляется здесь универсальным формальным требованием.

В [NeurIPS reviewer guidelines](https://nips.cc/Conferences/2026/ReviewerGuidelines)
отдельно предусмотрен тип Negative Results, но с высоким требованием к
значимости и оригинальности. Поэтому диагностическая статья возможна,
однако перечень неудачных hyperparameter sweeps сам по себе недостаточен.
Нужно показать объясняющий и воспроизводимый принцип, а не только отсутствие
улучшения одной реализации.

## 9. Рекомендуемая история статьи

Рабочее название, не claim уже доказанной новизны:

**When Uncertainty Fails to Improve World-Model Planning: Separating Action
Ranking, Feedback Timing, and Contact Recovery.**

Три потенциальных вклада:

1. Exact-state protocol, разделяющий state difficulty, within-pool selection
   и value of intervention; исправленные task-aware failure labels.
2. Эмпирическая проверка того, что global error prediction и local consequence
   ranking недостаточны для terminal success; определение opportunity gap.
3. RGB-conditioned recovery как constructive alternative на состояниях,
   где новые scores и дополнительные candidates не помогают; ограниченный,
   но подтверждённый выигрыш и честный transfer audit.

Для методической статьи альтернативная цель: opportunity-aware выбор между
continue, requery и targeted recovery. Это пока план: нельзя соединить
отдельные удачные ветки в новый controller и автоматически приписать ему
сумму их gains.

## 10. Минимальные следующие эксперименты для статьи

Вместо продолжения всех P1-P7 одновременно предлагается заморозить один
paper-oriented pipeline и выполнить следующие проверки по приоритету.

| Приоритет | Проверка | Зачем |
|---|---|---|
| 0 | Дождаться/проверить compact consensus без настройки по его test; оформить release manifest всей истории | Закрыть текущую ветку и перестать выбирать лучший метод по незавершённым данным |
| 1 | Заморозить P3c и P3e; prospective paired test на новых task/perturbation cells и init, с заранее выбранным primary comparison router vs full regrasp | Главный недостающий вопрос: добавляет ли learned decision rule эффект к сильному recovery control |
| 2 | Абляции: maxV-H16, maxV-H8, trigger-matched/random intervention при равном budget, retreat-only, full regrasp, frozen router | Отделить feedback, primitive и routing; показать цену в model calls и environment actions |
| 3 | Прямой online controller без simulator rollback; event-driven trigger вместо одного t=72; video и traces из тех же runs | Проверить реальную исполнимость и timing, не только post-hoc selection exact branches |
| 4 | Вторая совместимая policy и/или вторая simulator family; при доступности физический робот | Проверить, что механизм не является частным свойством одного checkpoint и pick-and-place geometry |
| 5 | Ближайшие published detector/recovery baselines и полный воспроизводимый artifact bundle | Закрыть novelty/comparison и reproducibility требования |

Для первого широкого recovery теста разумный плановый порядок величины:
20-30 целых cells и несколько новых init каждого, затем power analysis по
ожидаемым discordant outcomes и внутри-cell зависимости. Это предложение,
не обязательная норма конференции и не статистическая гарантия. Для оценки
малого increment P3e +2.7 п.п. потребуется больше независимых событий, чем
для проверки крупного recovery-vs-baseline эффекта. При ограниченных ресурсах
важнее разнообразие cells, чем сотни дополнительных seeds одного cell.

Primary: macro paired terminal-SR delta против сильнейшего подходящего
baseline. Secondary: rescue/harm, safe success, onset-aware warning lead
time, wrong-object/drop, environment steps и actual model calls/latency.
Freeze до нового test: method, calibration, hypothesis family, MDE, объём,
stopping rule, group bootstrap и multiplicity correction. Закрытый test
не использовать для очередного подбора коэффициентов.

## 11. Итоговое решение

Лучший подтверждённый практический механизм: **RGB regrasp**.
Лучшее узкое причинное доказательство: **shared-prefix query4 feedback**.
Лучший перспективный recovery selector: **P3e**, но его добавочный gain ещё
предварительный. Лучшее диагностическое наблюдение: **хорошо предсказывать
ошибку модели не значит уметь выбрать действие, которое выполнит задачу**.

Материал уже позволяет писать статью. Для сильного main-conference claim
следует не расширять бесконечно grid методов, а подтвердить одну понятную
историю на новом split и отличить её от уже опубликованных подходов.

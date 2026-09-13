# План статьи и доказательств

**13 сентября, проверки возобновлены:**
[Frozen resume и отдельный grounding/oracle протокол](../../experiments/RECOVERY_GROUNDING_DIAGNOSTIC_PROTOCOL_20260913.md).
Незавершённые main/timing досчитываются;32cases отдельно проверяют XY,
height и coverage. Privileged oracle и event-shadow не являются новым
deployable SR. Final confirmation и новый method claim ждут результатов.

**Решение после фактического среза 13 сентября:**
[Результаты прерванной серии и диагностический план](../../experiments/RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md).
Закрыть71оставшуюся main-ветвь без смены scientific config; проверить
pixel-to-world/target grounding и matched oracle-waypoint diagnostic.
Только затем широкий event sweep с отдельными grounding/timing ablations.
Preserve-only пока не реплицирует добавочный gain; x0.3 почти полностью
провален. Сильный локальный P3-эффект нельзя выдавать за общий переносимый
planner. Новый event-controller пока CPU-реализация, не результат для abstract.
Main/timing незавершены, новые GPU-run этим анализом не открыты.

**Уточнение 13 сентября: переносимый выбор момента вмешательства.**
[Event-feedback migration](../../experiments/EVENT_FEEDBACK_MIGRATION_20260913.md)
и [литература](../../articles/EVENT_TRIGGERED_FEEDBACK_REVIEW_20260913.md).
Не объявлять t72 универсальной фазой и не переносить старые положительные
SR на новый event controller. Его CPU-реализация отделена от frozen control
campaign; для нового claim нужны calibration, fair cost controls и transfer.

**13 сентября: финальное двухдневное окно.**
[Frozen экспериментальный план](../../experiments/RECOVERY_TWO_DAY_PLAN_20260913.md):
подтвердить положительный P3, проверить calibration-unseen x0.3 и sensitivity
к t56/72/88, затем завершить evidence и figures. Ночь: до1289 исходов с
9-часовым бюджетом, без автоматического fit/holdout. Текущий manuscript
описывает прежние результаты; новые outcomes в него не внесены до анализа.

**Рукопись подготовлена 12 сентября:** [полный отчёт](FULL_RESEARCH_REPORT.md),
[краткая сводка](RESEARCH_SUMMARY.md), [статья](manuscript/main.tex),
[PDF](build/iclr2027.pdf). Выбрана диагностическая версия A:
*When Consensus Is Not Enough*. Историческое название WAMPlan ниже не означает
новый подтверждённый planner. Таблицы последних серий включены в текст;
перед подачей остаются авторская проверка, final claim и anonymous supplement.
Новые GPU-эксперименты в рамках подготовки документов не запускались.

**Сводка для подготовки ICLR, 12 сентября:**
[все результаты и ограничения](RESULTS_AND_ANALYSIS.md),
[сопоставление с количественными результатами близких работ](RELATED_WORK_RESULTS.md).
Перед новым основным claim отделить joint-value selection от авторского AR
Cosmos planning, conditional recovery от full benchmark SR, и independent
holdout от development. История ниже сохранена; это не новая GPU-очередь.

Версия 12 сентября 2026. Это план публикации, а не новый запуск GPU-очереди.

**Новые E16–E19, обе ночные серии завершены:**
[Observation Contract1536/1536](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md),
[decoder-medoid1440/1440](../../experiments/DECODER_MEDOID_RESULTS_20260912.md).
Primary recovery145/192 хуже старого151/192; preserve-only161/192 интересен,
но netgain на однойcell и post-hocclusterp=.09587. У16harms дополнительный
regrasp раскрывает уже удерживаемый предмет. Decoder=max-value112/180,
fixed controls близки; H8/prefix не улучшили своего comparator, calls около2×.

**Следующий приоритет по данным, пока без нового запуска:**
1. Для версииA статьи объединить evidence: seed affinity скрытогоconsensus,
   физическаястоимостьнаблюдения, unnecessary release. Не делать позитивный
   methodclaim из отрицательногоprimary или GToracle.
2. Для версииB заморозить preserve-only и старый physicalregrasp какcontrols;
   на новыхinit проверить узкую x0.2/task9 гипотезу, затем unseen cells.
   Candidate: conservative releaseveto/passivetwo-view held evidence.
3. Не расширять текущие decoder/alwaysH8 sweeps. Возможный короткийdecoder
   diagnostic требует новыхnoisepools при одномobservation, отделенияseedbias
   от actionquality и train-only representation calibration.

1536ветвей используют96старыхсостояний; oracleSR не deployable результат.
Activeperception не новыйпринцип: сопоставление с CRITIC и другимиpriorart
в протоколе и related-work сводке. Holdoutне открывается этим анализом.
Ниже сохранена история решений до этих результатов.

**Новый завершённый evidence E14–E15:** [timing/eligibility490/490](../../experiments/TIMING_ELIGIBILITY_RESULTS_20260911.md).
Серия завершена15:09MSK и проаудирована:96pairedstates,48initclusters.
Continue63/96, immediate/diagnostic76/96, fresh/checked74/96. Primarygate
NO-GO; improvement надimmediate не найден. Immediate−continue+13.54п.п.,
16rescue/3harm, CI[8.33,18.75], ноHolmp=.17046: не писать corrected-significant.
Механизм: снятие толькоmiss-distance не меняетlabels; diagnosticвозвращает
3success наоднойjuicecell, но3-stepretreat в другойcase причиняетharm даже
безполногоregrasp. Все17общихfailures не проходятисходныйtrigger.
Это evidence для decomposition perception/gate/action и необходимости
оценивать физическуюстоимостьverification, не SOTAcontroller. Holdout38–45
закрыт, technicalsmoke не входит в независимыеSR. Следующий development:
non-openingretreat/passivetwo-view и аудитcoverage, без новогоширокогоsweep.

**Предыдущий evidence: диагностика, не подтверждение нового controller.**
[Grounded-mask576/576](../../experiments/GROUNDED_PROBE_RESULTS_20260911.md).
На27пробах false-held10→0, но8перешли вunknown. Conservative35/48 ровно
повторяет outcomes probe-always,47/48траекторий идентичны; full33/48.
Перцептивное исправление нельзя выдавать за доказанный вклад verifier вSR.
Transfer: full36/48, delayed/continue33/48; timing смешан с повторной
eligibility,14из21recovery отменены. Frozen gate NO-GO, confirmation нет.
ВерсияA статьи получает механизм-ablation и пример небесплатной информации;
версияB требует нового селективного controller и независимого выигрыша.
Следующий узкий опыт разносит delay/trigger, не добавляет новый ranking sweep.
См. E12–E13 в [реестре доказательств](EVIDENCE_LEDGER.md).

**Предыдущая проверка версии B: отрицательный screen.**
[Probe/verify/repair192/192](../../experiments/PROBE_VERIFY_REPAIR_RESULTS_20260911.md):
verified30/48 против full35/48,4 rescue/9 harm; holdout gate NO-GO.
Из9held семь не подтверждены движением цели/контактом в post-hoc GT-аудите:
crop может отслеживать захват. Не объявлять external verification улучшением
по сравнению только с continue26/48. Следующий diagnostic для версии A/B:
object-specific tracking и probe→always-regrasp, отдельно от timing/threshold
sweep. Offline GT-аудит не online input и не независимый prospective test;
нужны новые init после фиксации следующей версии. Новых GPU-run этот разбор
не открывает. Прежний план запуска ниже исторический.

**Текущее решение вечером:** [финальный разбор двух дневных кампаний](../../experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md),
[ближайший план](../../experiments/RESEARCH_PRIORITIES_20260910_EVENING.md).
Pool13 replication подтверждён, но соседний split-effect +5п.п. имеет CI
[-3.75,18.75]. Matched-K/continuity завершён: fresh K4 13/24 против open16
15/24, без pooled gain. Следующий метод-кандидат для версии B статьи:
физическая проба, RGB-проверка захвата и выбор восстановления. Сравнить с
full physical regrasp и probe-only, затем независимый init holdout.
До результатов не переносить новую гипотезу в раздел доказанных улучшений.
Упоминания незавершённой neighboring серии и ожидания ниже исторические.

**После аудитов P3c и fresh8:** [обновлённый научный приоритет](../../experiments/RESEARCH_PRIORITIES_20260910.md).
Главный method-кандидат: phase-aware verified recovery против сильного P3c
control; отдельно action-conditioned verifier после reproducible opportunity
gate. Ближайшая исполнимая очередь проверяет matched K4 feedback и continuity.
Temporal consistency уже есть в BID/RTC/Legato; новую формулу penalty не
выдавать за самостоятельную архитектурную новизну. P3d cells не являются
unseen для localizer. Эти ограничения обязательно сохранить в рукописи.

Новый conditional evidence,13:20 MSK: fixed pool13 alternatives3/5 дают10/10
против1/10 у max-value candidate4 на новых suffix seeds; Holm p=.01171875.
Это один snapshot, не transfer и не результат обученного verifier. Neighbor
серия не завершена. После неё в серверной очереди PID3878088 стоят matched-K
controls и continuity screen; большой fit автоматически не открывается.

**Обновление после завершения ночного расчёта:**
[1080/1080 и полный аудит](../../experiments/P5_REPEAT_FEEDBACK_RESULTS_20260910.md).
P0 выполнен; новый fresh8 не улучшил pooled SR, а K8 split-repeat selection
не превзошёл max-value. Следующий gate: новые suffix/init для `pool_13` и
`pool_11`, local contact/target labels и проверка устойчивого action advantage.
Ни always-requery, ни большой P5 critic пока не продвигаем. Таблица ниже
сохраняет общие вопросы, но повторно запускать уже завершённый P0 не нужно.

P1 запущен 10 сентября 12:01 MSK:
[50 fixed-candidate repeats + до640 branches соседних init](../../experiments/P5_CANDIDATE_REPLICATION_PROTOCOL_20260910.md).
Smoke 6/6 пройден, основной сбор начат в12:09 MSK; это conditional replication и новые diagnostic pools,
не новый deployable метод. Результаты в evidence ledger пока не добавляются.

## 1. Какой вопрос имеет смысл защищать

**Когда дополнительная выборка помогает world-action model, а когда ей нужны
новые наблюдения или новые действия восстановления?** Разделить три причины
провала: неверно ранжировали хорошие candidates; в pool нет хорошего candidate;
исход изменяется из-за stochastic continuation/обратной связи.

Сегодня защищаемая история ближе к диагностическому исследованию границ
test-time selection, чем к «новому consensus, который улучшает всё».
WAMPlan пока рабочее название, а не установленная новизна алгоритма.

### Возможные версии статьи

| Версия | Что необходимо | Статус |
| --- | --- | --- |
| A: надёжный диагностический benchmark выбора/feedback/recovery | Frozen pools, повторные suffix seeds, причинные контроли и перенос | Есть substantial groundwork; текущих проверок ещё недостаточно для широкой причинной истории |
| B: новый controller, выбирающий sample / observe / recover | Версия A + deployable gate, независимый holdout и выигрыш с учётом стоимости | Гипотеза, не готовый результат |
| C: только OSC-medoid как новый метод | Явная новизна относительно KeyStone/KDPE и стабильный выигрыш | Не поддерживается текущими данными; не делать главным вкладом |

## 2. Гипотезы и решения о следующих экспериментах

Обозначения: состояние s, frozen candidates A_i, suffix seed r, terminal
success Y_ir, ценность V_i. Simulator state используется для offline replay,
а не как недоступный robot observation online.

$$
\hat p_i(s)=\frac1R\sum_rY_{ir},\qquad
G_{\rm select}(s)=\max_i\hat p_i(s)-\hat p_{\arg\max_iV_i}(s).
$$

Максимум по шумным оценкам оптимистичен: для итогового oracle-gap разделить
suffix repeats на выбор кандидата и проверку его исхода. Не обучать и не
тестировать selector на одних branch labels.

$$
\Delta_{\rm obs}=\mathbb E[Y_{\rm fresh8}-Y_{\rm stale8}],\qquad
\Delta_{\rm deploy}=\mathbb E[Y_{\rm fresh8}-Y_{\rm open16}].
$$

Первая величина проверяет пользу актуального наблюдения при контроле
дополнительного запроса; вторая включает стоимость/эффект самого requery.
H16→H8 не гарантирует повышение SR: нужна парная проверка.

| Приоритет | Вопрос / тест | Контроль | Условие следующего шага |
| --- | --- | --- | --- |
| P0, выполнен | Аудит p5_repeat_feedback: repeats и fresh/stale/open | Exact state, сохранённые inputs, общий suffix RNG, равный шаговый бюджет | 1080 branches, 288 exact endpoints, 108 декодированных видео; общего fresh8 gain нет |
| P1, уточнён | Устойчивые локальные advantages в pool13/pool11? | Новые repeats/init; baseline и замороженные alternatives; local/terminal labels | K8 global split-gap=0; не открывать большой fit по оптимистичному +14.81 п.п. |
| P2 | Помогают новые наблюдения, а не просто новый stochastic sample? | Fresh8 vs stale8 и open16; matched candidate/seed contracts | Положительный переносимый эффект после стоимости; без универсального t=72 |
| P3 | Что делать с all-fail pools? | Дополнительные samples vs targeted recovery vs stop/requery | Проверить coverage и вред на исходно успешных состояниях |
| P4 | Gate: select / observe / recover | Max-value, fixed-H8, всегда recovery, простой порог, oracle diagnostic | Gate обучается только на dev; untouched task/cell/init; улучшение не только против слабого baseline |
| P5 | Generality | Второй backbone или дополнительный робот/benchmark, если доступно | Не заявлять model-agnostic по одному Cosmos checkpoint |

Завершённая очередь определена в
[P5_REPEAT_FEEDBACK_PROTOCOL](../../experiments/P5_REPEAT_FEEDBACK_PROTOCOL_20260910.md).
Evidence ledger обновлён после полного сбора. Frozen гипотезы и критерии
не менялись; split-repeat анализ явно помечен post-hoc.

### Дополнение по работам Nikita Kachaev

[Разбор и формулы](reference_papers/requested_profile/README.md) добавлены после
уточнения автора Scholar-профиля. Текущую frozen очередь не изменяем.

1. Перед новым online risk gate проверить **phase confounding**: raw uncertainty
   против phase-only и phase-normalized predictor. Пики при обычном переходе
   grasp→transport не считать доказательством будущего fail.
2. Если repeated-branch анализ подтвердит недостаток candidate coverage,
   провести небольшой **conditioning screen** по идее VLA Grounder: original
   command, фиксированные семантически равноценные rewrites, RGB-grounded
   rewrite, больше samples без rewrite. Проверить реальные T5 embeddings,
   оставить ту же цель и учесть стоимость upstream модели.
3. Добавить диагностические **grounding / contact / drop / timeout** labels
   отдельно от terminal SR. Вдохновение Act2Answer и Kitchen-R не означает,
   что по одному label автоматически установлена причина провала.
4. Recurrent memory по примеру muVLA и visual alignment по Don't Blind Your VLA
   оставить **условными следующими шагами**, требующими обучения и data-matched
   контролей. Не вставлять их незаметно в inference-only Cosmos comparison.

Для текста: взять у этих работ структуру «определение → изоляционный тест →
механизм → общий результат → ограничения», а не обещание нового метода по
одной красивой кривой. MIKASA сейчас образец дизайна задач, не замена PRO benchmark.

## 3. Единый протокол для будущих таблиц

- Разделить development, перенос на unseen cells/tasks и confirmatory init
  holdout. Все queries и suffix repeats одного task/init держать в одной группе.
- Для selector-only опыта повторно использовать сохранённый candidate pool.
  Для deployed controller опыта отдельно показать RNG/state parity и latency.
- Явно указывать LIBERO-PRO **Object suite** и factor Object / Environment /
  Position, список perturbation levels, task IDs, init IDs, exclusions. Это
  не три разные task suites и не автоматически полный официальный benchmark.
- Фиксировать generated horizon T, executed H, K, denoising steps, joint/AR
  planning mode, число model calls, wall-clock latency и execution budget.
- Primary endpoint: factor-balanced macro-SR; рядом per-factor SR, micro-SR,
  paired rescue/harm, cluster CI, latency/query cost. McNemar обозначать тестом
  episode discordance, не тестом взвешенного macro-SR.
- Safety: task timeout ≠ физическая ошибка ≠ официальное safety violation.
  Drop/contact/wrong-object proxies публиковать под своими именами. Отдельный
  LIBERO-Safety результат нельзя смешивать с PRO SR.
- Метрики до ошибки: только доступные до исполнения prediction/uncertainty.
  Image/proprio error после chunk является retrospective label или будущим
  training target, но не online feature этого же решения.
- Выбор видео: до просмотра зафиксировать paired rescue, harm, both-success,
  both-fail; одинаковые timestamps, полный horizon, пометки query/pre/post.

## 4. План 9 страниц основного текста

| Раздел | Бюджет, стр. | Один проверяемый вопрос / артефакт |
| --- | ---: | --- |
| Abstract + Introduction | 1.25 | Какой разрыв между confidence, useful action и feedback? Figure 1 с реальным shared-prefix примером |
| Related Work | 0.75 | Что совпадает/различается с Cosmos, KeyStone, KDPE, uncertainty/safety |
| Preliminaries | 0.75 | x_q, K, T, H, native OSC, parallel vs AR, observable vs privileged |
| Diagnostic method / controller | 1.50 | Формулы, sampling, distance, tie-break; затем только проверенный новый компонент |
| Protocol | 1.25 | Splits, factors, branch reuse, repeats, estimand, cost |
| Results + Ablations | 2.50 | Main SR table; opportunity; fresh/stale; transfer/cost; harm |
| Limitations + Conclusion | 1.00 | Где не работает, предел новизны и переноса |

Appendix: полные grids/configs, все seed IDs, гиперпараметры, replay audits,
negative results, action normalization, доп. видео и описания failures.
Читатель должен понять главный вывод без appendix.

## 5. Порядок написания

1. Сначала frozen таблицы и figure captions с n, единицами, baseline и CI.
2. Затем Methods точно по code contract, не по предполагаемой архитектуре.
3. Results: наблюдение → сравнение → неопределённость → допустимый вывод.
4. Related Work в сравнительной форме, не хронологическим списком статей.
5. Introduction и Abstract писать последними под реально прошедшую гипотезу.
6. Проверка другим автором: каждое число до raw CSV, каждая формула до кода.

## 6. Календарь и критерий подачи

10–12 сентября: аудит завершённых данных, author list, утверждение narrative.
13–16: один приоритетный confirmatory опыт с заранее зафиксированными gates,
черновик результатов и фигуры. 17–18: настоящий abstract по имеющимся данным.
19–22: перенос/стоимость/negative controls, appendix и reproducibility.
23–24: независимая проверка математики, ссылок, анонимности, сборки.
25: резерв на загрузку и технические ошибки. Если evidence gates не пройдены,
не превращать неподтверждённые ожидания в результаты ради срока.

Официальные требования, проверены 10.09.2026: abstract 18 сентября 23:59 AoE
(19 сентября 14:59 MSK), full paper 25 сентября 23:59 AoE (26 сентября
14:59 MSK); основной текст ≤9 страниц, references и appendix отдельно;
double blind; авторов нельзя добавлять после abstract deadline. Проверить
OpenReview profiles сейчас, также reciprocal reviewing eligibility. Источник:
[ICLR Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines).
Обязательны AI-use section и раскрытие в форме; человеческая проверка всех
AI-assisted claims должна быть реально выполнена:
[AI Policy](https://iclr.cc/Conferences/2027/AIPolicyForAuthors).

Готовность к сильной подаче: отличимый вклад, корректные близкие baselines,
непросмотренный перенос, cost-matched эффект, reproducible artifacts и честные
границы. Сейчас наличие большого количества rollout само по себе эти условия
не закрывает; принятие на ICLR предсказать по числу экспериментов нельзя.

# Приоритеты после завершения P5 replication и K4 controls

Версия: вечер 10 сентября 2026. Заменяет оперативные указания утреннего
[плана](RESEARCH_PRIORITIES_20260910.md), не изменяет прошлые frozen протоколы.
[Новые окончательные результаты](P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md).

**Актуальная очередь 11 сентября20:23MSK:**
[Observation Contract](OBSERVATION_CONTRACT_PROTOCOL_20260911.md): bounded
observation с open/preserve gripper, only/regrasp controls, старый immediate,
continue и два явно privileged oracle. 24 smoke +1536 основных ветвей;
96 прежних prefixes, две suffix серии. Не независимый new-init test.
Если выигрывает learned candidate, следующим будет frozen new-init
confirmation. Если выигрыш только oracle, приоритет локализации/калибровки;
если oracle также не помогает, менять primitive или event timing.
Пороги не подбираем по текущим labels, большой P5/P6 пока не запускаем.

**11 сентября15:09MSK: timing/eligibility490/490 завершена и проаудирована.**
[Полный результат](TIMING_ELIGIBILITY_RESULTS_20260911.md): continue63/96,
immediate/diagnostic76/96, fresh/checked74/96; checked gate NO-GO.
Разложение19отмен:3толькоmiss-distance (возвратrecovery не меняетoutcomes),
16остальнымиguards. Raw vsfresh:3rescue с восстановившейсяпослеretreat
локализацией и1harm после3шаговretreat, без полногоprimitive.
Следующий приоритет: non-openingobservationmotion +passive/two-view
verification, затем coverage исходногоtrigger. Все17общихfailures не
былидопущены, recovery на них не тестировался. Сохраняемimmediatebaseline,
не открываемholdout38–45 и не подбираемthresholds по нынешнемуscreen.
Полный аудит:490видео,59174кадра,79CPU-тестов. НовыхGPUзапусков при анализе нет.

## Актуализация после ночи 11 сентября

[576 ветвей завершены, полный разбор](GROUNDED_PROBE_RESULTS_20260911.md).
Conservative35/48 повторяет probe-always по всем outcomes; full33/48,
miss-only29/48. Маска убрала10false-held, но8изних сталиunknown, что не
исправило miss-only policy. Gate NO-GO, init38–45 остаются закрытыми.
Transfer: full36/48 против33/48delayed/continue. В delayed свежий trigger
отменил14из21ранее разрешённых recovery. Это не чистый эффект задержки.

Новый порядок: (1) разнести timing и повторный допуск с сохранением safety
guards; (2) passive/two-view verification в shadow-mode и обработка unknown;
(3) новые frozen init лишь после диагностического допуска. Не продолжать
нынешний mask sweep, не расширять fixed-delay вслепую, не открывать большой
P5/RL fit. Научный результат сейчас диагностический: лучший perceptual
ответ не гарантирует лучшего управления. Ночная очередь завершена03:56MSK;
новые GPU-эксперименты при анализе не запускались. Указания ниже исторические.

## Исполненная очередь на 7 часов

[Замороженный протокол 11 сентября](GROUNDED_PROBE_PROTOCOL_20260911.md)
реализует следующий шаг после NO-GO: отдельная RGB-маска вместо широкого
tracking crop; miss-only и conservative fallback; probe→always-regrasp как
контроль физического вмешательства; delayed regrasp после8policy actions.
До8arms, новые init, условная confirmation только одного прошедшего candidate.
Вторая независимая проверка: full/delayed на6другихcells, даже если verifier
не пройдёт gate. До7idle GPU, предельный срок08:35MSK. Первый data-path
preflight остановился с0epochs/rollout, v2 исправляет путь на точные388samples.
Не переобучаем Cosmos и не начинаем новый большой ranking/uncertainty sweep.
Положительный эффект и generality остаются гипотезами до итогового анализа.

## Обновление 11 сентября: screen завершён, NO-GO

[Результаты probe/verify/repair](PROBE_VERIFY_REPAIR_RESULTS_20260911.md):
192/192 ветви, verified30/48 против full35/48; continue и probe26/48.
Замороженный practical gate не пройден, holdout init29–32 не открыт.
Семь `held` соответствуют неподвижной цели без контакта; пять из них позднее
fail, хотя full control успешен. RGB-flow согласуется с движением захвата,
не гарантируя отслеживание предмета. Это post-hoc диагностика, не GT online.

**Текущий приоритет:** остановить v2 без нового sweep. На development
проверить object-specific/two-view или passive tracking с явным исключением
robot pixels; затем добавить `probe → always-regrasp` из того же post-probe
состояния, чтобы отделить ошибочный skip от вреда пробы. Только новая
замороженная версия с прошедшим diagnostic gate получает новые init для
подтверждения. Не открывать прежний holdout после отрицательного gate и
не выдавать подбор по screen за независимую проверку.
Общий путь grounded verification/recovery сохраняется, но текущий RGB-flow
verifier не является улучшением сильного baseline. Новые GPU-run этим
анализом не запускались. Разделы о старте ниже сохранены как история.

**Запуск:** исправленный `probe_verify_repair_20260910_v2` стартовал в 22:41 MSK,
dispatcher 33728, свободные GPU 1/3/6. Первый smoke выявил рассогласование OpenGL/CV
в новом tracking-коде; 16 технических ветвей сохранены отдельно, screen тогда не
начинался. Геометрический аудит и 75 локальных/67 серверных CPU-тестов пройдены.
Пороги и manifest не менялись. Текущий статус смотреть через `--status`,
не считать этот срез подтверждением завершения всего smoke/screen.

Дополнение 22:50 MSK: все 24 smoke завершены, integrity пройден; есть реальные
ответы `held`, `miss`, `unknown`. Диспетчер перешёл к основному screen.
Это технический PASS, а не подтверждение выигрыша нового метода.

## Решение

Для быстрого научного результата **улучшать проверенный recovery-механизм
с помощью нового внешнего verification**, а не начинать дорогой новый training
pipeline и не повторять перебор `value-lambda*uncertainty`.
Сильное основание: P3c +27.5п.п. на отдельных cells; понятные harms от
ненужного regrasp; frozen perception уже работает. Слабое основание для
большого scorer: устойчивый pool13, но соседний split-effect CI пересекает0.
Matched-K/continuity screen завершён и не дал pooled выигрыша.

## Какие лучшие идеи ещё не проверены

| Идея из статей / проекта | Что уже сделано | Что ещё не сделано / решение |
|---|---|---|
| Tool-grounded self-correction, CRITIC | RGB localization и recovery, но без физической проверки захвата | Сейчас: probe→verify→repair с сильными controls |
| Process/outcome verification, PRM/PAV | Repeated MC outcome labels, action-dependent pool13 | Отдельная prover-policy PAV и переносимый within-state scorer не реализованы; отложить fit до устойчивых labels на многих states |
| Semantic uncertainty | Action/value/latent dispersion и некоторые contact features | Не проверен надёжный semantic grasp/progress verifier; проба начинает проверять этот механизм, не реализует semantic entropy |
| Temporal consistency, BID/RTC | Мягкий aligned-tail penalty, новый matched-K контроль | Native diffusion conditioning/inpainting и latency-aware rollout не реализованы; не приоритет после нулевого control |
| MBR / value+consensus / KeyStone / KDPE | Broad valid199 и компактные проверки | Нет убедительного gain; оставить published-style baselines, не новый sweep |
| Diffusion-DPO / DDPO / Flow-GRPO / SCoRe | Подбор статей и аналогия | Нового preference/RL fine-tuning нет; слишком дорого относительно качества нынешних labels |
| Event-conditioned recovery | t72 control, post-hoc phase/contact анализ | Learned event timing не проверено; после полезности verifier, отдельно от смены primitive |

Основные источники: [CRITIC](https://arxiv.org/abs/2305.11738),
[self-correction survey](https://aclanthology.org/2024.tacl-1.78/),
[PAV](https://arxiv.org/abs/2410.08146),
[26 PDF и их ограничения](../articles/llm_nlp_transfer_20260909/PAPER_REVIEW.md).
PAV использует distinct prover-policy; наш MC suffix той же policy не является
его точной реализацией. Общие verification, active perception и recovery
известны; novelty должна быть доказана механизмом и экспериментами, не названием.

## Очередь и критерии решений

1. **Завершён, NO-GO: Physical Probe → Verify → Repair.** Реализован
   [протокол 24smoke +192screen +условные192holdout](PROBE_VERIFY_REPAIR_PROTOCOL_20260910.md).
   Три cells новые для calibration сочетания task/perturbation, три известных;
   все init отделены от calibration. До3свободныхGPU и12ч, shared-prefix pairing.
2. **Условие не выполнено:** автоматический независимый init holdout с теми
   же замороженными thresholds. Не переобучать/тюнить по holdout. Primary
   advantage над full regrasp, не только над continue; отдельно стоимость проб.
3. **Текущее действие после отрицательного screen:** остановить серию.
   Разобрать RGB visibility, correspondence, вред самой пробы и ошибочные
   abstentions. Следующая отдельная версия: wrist-view/двухкамерный verifier
   или passive motion verification. Не запускать незаявленную настройку
   десятков порогов на уже прочитанном screen/holdout.
4. **Если holdout положителен:** проверка новых cells/tasks и false-positive
   harms на обычных успешных сценах; ablation фиксированного t72 против
   event/contact trigger; сравнение частоты вызовов/latency; затем второй
   backbone при наличии ресурсов. Это приоритетный путь к методической статье.
5. **Параллельная недорогая работа после текущего аудита:** использовать
   repeated outcomes для диагностики локальных grasp/progress labels;
   расширять independent states, а не suffix repeats одного pool13. Малый
   grounded scorer запускать лишь если advantage переживает split-repeat и
   task/init holdout. State-only difficulty обязательно как контроль.
6. **Generator improvement позже:** только если новые all-fail pools
   устойчивы и есть качественные recovery/preference пары. Сначала маленький
   training pilot на action-компоненте, отдельно от future/value; не обещать
   перенос численных NLP/генеративных gains в LIBERO.

## Что можно утверждать для публикации сейчас

Уже есть содержательная диагностика: ошибки выбора бывают устойчивыми,
single-seed oracle преувеличивает opportunity, свежее наблюдение полезно
избирательно, а targeted recovery сильнее ещё одного скалярного penalty
в отдельных сложных сценах. Универсального нового SOTA planner пока нет.
Быстрый качественный результат означает раннее проверяемое решение по
механизму, включая честный отрицательный исход, а не гарантию положительного SR.
Нужны strong baselines, held-out cells, compute/cost controls, проверка
novelty и устойчивость результата. Одного положительного probe-screen
недостаточно для заявления о готовности к ICLR.

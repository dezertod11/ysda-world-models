# Ближайшие исследования: быстрее получить проверяемый научный результат

**Приоритет на окно до 10 сентября 09:35:59 MSK:**
[фиксированная проверка suffix-noise и fresh8/stale8 feedback](P5_REPEAT_FEEDBACK_PROTOCOL_20260910.md).
36 прежних pools, 1080 branches, максимум три GPU-worker после просьбы
добавить GPU2 (исходно два). Сначала smoke,
затем полный сбор без подбора коэффициентов. До результата откладываем fit
P5-head и расширение consensus grid; затем выбираем между repeated-label
critic, переносом feedback и изменением proposals/recovery.

**Дополнение 10 сентября:** запланированная очередь полностью завершена.
[Результаты и уточнение решения](CONSENSUS_AND_P5_RESULTS_20260910.md):
reference-стратегии не показали убедительного превосходства; P5 pilot дал
16 mixed pools, но только один K8 rescue pool. Поэтому прежде большого
fit/holdout нужны проверка continuation noise и task-critical информации,
а для all-fail cases проверка proposals/feedback/recovery. Исходный
data-opportunity PASS не отменён; он не является PASS нового метода.
Статусы RUNNING/WAITING ниже относятся к 9 сентября до завершения серии.

**Последующая ресурсная поправка 13:44 MSK:** разрешён idle-only пул GPU0-7,
диспетчер перезапущен, 368 reference rollout сохранены. Методика этого плана
и порядок этапов не менялись. Описанные ниже статусы 13:10-13:24 и старый
запрет GPU0 являются историческим срезом.
[Новая политика и проверенный перезапуск](GPU07_RESOURCE_POLICY_20260909.md).

Обновлено 9 сентября 2026 года. Сервер проверен около **13:10-13:13 MSK**.
Повторная проверка в **13:24 MSK**: те же 127 завершённых jobs,
367/597 rollout, свободных разрешённых GPU нет; P5 не начался.
Это актуальный план следующего этапа. Исторические frozen-протоколы не
переписаны; работающая очередь не перезапускалась и новые GPU jobs не добавлялись.

## 1. Решение

**Не нужен ещё один широкий поиск коэффициентов uncertainty. Нужны две
узкие проверки: где конкретно доступно улучшение выбора action и насколько
сильный recovery переносится при правильной фазе вмешательства.**

Наиболее быстрый путь к содержательному положительному результату:
механизм и перенос RGB recovery. Более непосредственно относящийся к новой
архитектуре planning путь: task-critical P5, но только после проверки
доступности обучающих сигналов. Эти ветки нельзя смешивать в один SR claim.

## 2. Что сейчас с расчётами

| Этап | Проверенное состояние |
|---|---|
| K1 / max-value / OSC medoid на valid199 | Завершено 597 rollout, итоговый анализ есть |
| Три reference integration smoke | Завершены ранее |
| Raw medoid / KeyStone-style / KDPE adaptation | **367/597 rollout**, 127/357 jobs; осталось 230 Position rollout |
| Environment references | 150/150 rollout: 50 на каждый из трёх методов |
| Object references | 150/150 rollout: 50 на каждый из трёх методов |
| Position references | 67/297 rollout; сравнение всего benchmark ещё неполное |
| P5 integration smoke | Ещё не запускался |
| P5 data pilot | Config и asset audit подготовлены; manifest/результатов ещё нет |
| Новая learned P5 model | Не обучалась и не тестировалась в этой очереди |

Диспетчер PID **2181819**, дочерний campaign runner **2183348** живы,
heartbeat обновляется. Последний завершённый job на момент проверки:
`position_x0_3_t2_raw_medoid`, **12:05:11 MSK**.
В логе: ожидание свободной GPU. Ни одного нашего GPU collector в этот момент
не было. Проверка `/proc/<pid>/cwd` показала, что GPU-процессы относятся
к другим проектам, не к этой папке.

На GPU2 около 892 MiB, GPU3 около 1777 MiB занято другими процессами.
Низкая utilization не означает, что карты свободны. GPU4-7 также заняты.
Порог очереди `memory < 256 MiB`, `utilization < 5%` не понижаем скрытно;
чужие процессы не завершаем, GPU0 не используем.

**RUNNING сейчас означает живое ожидание ресурсов, не непрерывный расчёт.**
По 67 готовым Position jobs среднее полное job-время 115.85 секунды,
медиана 105 секунд. Простая экстраполяция остатка даёт около **7.4 worker-hours**
(включая загрузку модели, симуляцию и анализ), а не 7.4 часа гарантированного
календарного ожидания. При трёх постоянно доступных картах это ориентир
около 2.5 часов только для references; оставшиеся трудные cases могут идти
дольше. Время до освобождения карт неизвестно; P5 в эту оценку не входит.

Сохранены [машинный срез сервера и SHA текущих configs/scripts](campaigns/research_priority_audit_20260909/server_status.json).
Значения памяти выше относятся к первому срезу; в повторном срезе нагрузка
других проектов увеличилась, вывод об отсутствии свободных карт прежний.

Мониторинг:

```bash
./scripts/mlspace_experiment_status.sh consensus_p5_night_20260909
./scripts/mlspace_experiment_status.sh consensus_references_20260909_valid199
./scripts/mlspace_experiment_status.sh p5_boundary_candidates_20260909
```

Почему P5 ждёт: в текущем launcher это последовательная зависимость
`references -> matched analysis -> P5 smoke -> P5 pilot`.
Это организационный порядок, не научная необходимость использовать
reference outcomes для выбора P5. CPU-аудит старых данных ждать не должен.

Если resource wait затянется, разумная **отдельная ресурсная поправка**:
первый доступный worker отдать неизменённому P5 smoke/pilot, остальные
references. Для этого нужен единый диспетчер/межпроцессный reservation или
непересекающиеся GPU pools. Нельзя просто запустить второй независимый
launcher на тех же GPU1-7: возникает гонка при обнаружении свободной карты.
В рамках этого обновления такая runtime-поправка **не применялась**.

## 3. Что уже является результатом

| Научный тезис | Данные | Ограничение |
|---|---|---|
| Исправление контакта по RGB может существенно помочь | P3c: 13/40 -> 24/40, +27.5 п.п., CI [+12.5; +42.5] | Новые init восьми известных Position cells, trigger проверяется в фиксированное время |
| Дополнительное реальное наблюдение иногда причинно полезно | Shared-prefix: 46/100 -> 64/100, +18 п.п., CI [+4; +32] | Один конкретный Object task0 контекст; перенос не установлен |
| Большой выигрыш recovery не равен выигрышу router | P3e: 53/75 -> 55/75 над full regrasp, p=0.5 | Добавочный эффект слабый; оба rescue из одной известной cell |
| Хороший surrogate не гарантирует terminal SR | Frozen ranker: offline regret -43.1%, 165/360 -> 164/360 | Менять target и информацию, не только коэффициент |
| Pooled fail detector не обязательно ранжирует actions | P4b: pooled AUROC 0.650, within-pool 0.509 | Нельзя выбирать метод по общей AUROC |
| Consensus пока не подтвердил широкий выигрыш | OSC 54.09% против max-value 54.77% macro-SR; CI разницы [-3.33; +1.99] п.п. | Это valid199 compact, не полный benchmark и не итог всех references |

Источники: [общая сводка](RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md),
[valid199](CONSENSUS_P5_NIGHT_PROTOCOL_20260909.md),
[timing decision](RECOVERY_TIMING_DECISION_20260909.md).

Наша полезная научная постановка уже существует: разделять **proposal
failure, selection failure и недостаток реального feedback**. Но успешный
переносимый новый candidate planner пока не продемонстрирован.

## 4. Быстрый аудит данных для P5

Повторно сгруппирован сохранённый `consensus_common_pool_20260908/pool_audit.csv`.
Это прежние открытые данные, не новые независимые эксперименты:

| Данные | Strict pools | Mixed | Oracle rescue opportunity относительно max-value |
|---|---:|---:|---:|
| Environment task1 | 20 | 0 | 0 |
| Environment task3 | 20 | 7 | 6 |
| Object task0 | 39 | 17 | 8 |
| Position, все изученные cells | 115 | 8 | 0 |
| Всего | 194 | 32 | 14 |

Все эти snapshots относятся к **query3**. Возможность исправить выбор есть
только на **двух task IDs**. В Position смешанные pools существуют, но
max-value уже выбирает успешный candidate; в остальных failed pools все
кандидаты fail. Это ограничение конкретных pools/continuation, не всех
Position задач.

Машинные таблицы: [по task/cell](campaigns/research_priority_audit_20260909/existing_opportunity_by_cell.csv),
[по query](campaigns/research_priority_audit_20260909/existing_opportunity_by_query.csv),
[сводка и SHA исходного аудита](campaigns/research_priority_audit_20260909/existing_data_summary.json).

В пилоте из очереди, напротив, есть Object/Position, но **нет Environment**;
добавлены q0 и q3. Он полезен как независимый от нового fit поиск разнообразия,
однако не должен быть единственным источником данных будущего P5.

**Особенно важно:** gate «8 mixed pools» проверяет наличие разных outcomes,
но не проверяет, что max-value ошибается в этих pools. Поэтому после
исходного аудита нужен отдельный rescue-opportunity audit перед fit.
Frozen gate сохраняется; более строгая проверка не меняет старые results.

## 5. Приоритеты и ограничение бюджета

Бюджеты ниже задают объём **предлагаемых будущих** проверок, не уже
поставленные задания и не обещание конкретных GPU-hours.

| Порядок | Проверка | Бюджет/артефакт | Условие перехода |
|---|---|---|---|
| Сейчас | Закрыть и оформить имеющиеся результаты; CPU-аудит P5 support/features/labels | Старые 194 pools + новый pilot после окончания; без новых WM calls | Понятно, где есть rescue и где all-fail |
| Ближайший GPU этап | Существующий P5 smoke + pilot без изменения параметров | 1 + 36 K8 pools, 8 + 288 branches | Replay, корректные labels, анализ по tasks и q0/q3 |
| Быстрый результат по сильной ветке | Recovery timing/mechanism micro-pilot | 8 development task/init groups x 3 времени x 3 options = до 72 terminal branches | Не один удачный seed: эффект/вред локализуется по фазе и primitive |
| Следующий P5 этап | Дешёвый grounded representation/label feasibility test | Старые sidecars; линейные heads + один небольшой MLP, без full DiT training | Candidate-dependent features полезнее state-only и shuffled-action controls |
| Только по результату audit | Ограниченная label-noise/transfer проверка P5 | До 48 повторных continuation branches **или** до 64 K4 branches на новых cells | Есть воспроизводимое преимущество кандидатов, не только suffix noise |
| После freeze одного победителя | Проспективный closed-loop smoke/paired screen | 24 case/seed пары = 48 rollout на двух заранее выбранных контроллерах | Корректная интеграция и приемлемый harm; не финальное доказательство эффективности |
| Только затем | Один confirmatory тест | Размер по paired discordance, полезному SR gain и task clusters | Новые целые cells; frozen primary outcome и коррекция сравнений |

Recovery micro-pilot: времена `t=56,72,88`; options `continue`, `retreat`,
`full regrasp`. Это сокращённая development-диагностика из прежнего timing
плана, а не выбор лучшего времени на holdout. Восемь групп заранее включают
известные полезные и harmful cases; три времени получают из общей baseline
траектории. Продолжение и общий лимит шагов совпадают. Если episode уже
завершён или snapshot недоступен, это отмечается, не заменяется новым seed.
Эти данные показывают механизм, но не могут доказать unseen-cell transfer.
Отдельный requery-only control добавляется в последующем тесте при переходе
к вопросу о feedback, а не смешивается с full regrasp effect.

P5 repeats: например, шесть заранее выбранных pools x четыре **сохранённых**
actions x два дополнительных общих suffix seeds = 48 branches. Include
mixed/all-pass/all-fail, а не только удачные для новой модели examples.
Первый pilot имеет одну K1 continuation realization на candidate; повторять
нужно suffix, не снова генерировать actions. Для этого понадобится отдельный
replay runner или его расширение; текущий collector не делает этот режим
автоматически. Точные IDs и seed map фиксируются до запуска.

## 6. Как именно изменить будущий P5

Полная спецификация: [P5 task-critical refinement](P5_TASK_CRITICAL_REFINEMENT_20260909.md).

1. **Сохранить текущий pilot как P5-data**, не переобучать/переименовывать
   прежний ridge как «новую архитектуру».
2. Собирать и проверять **реальный terminal outcome и локальные события
   отдельно**. Timeout не равен промаху или падению.
3. Включить текущие target-conditioned RGB признаки и связь action с
   predicted target/contact outcome, а не только global image embeddings,
   future proprio и latent std.
4. На development выбирать задачи с rescue opportunity. Environment task3
   обязательно включить в диагностику уже сохранённых данных; новые задачи
   нужны для переноса, а не только новые seeds этих двух известных tasks.
5. Проверять фазу действия: q0/q3 не гарантируют покрытие contact/release.
   Не объявлять q4/t72 универсальным решением; phase-balanced сбор требует
   отдельного следующего freeze.
6. Учитывать зависимость labels от continuation policy и стохастических
   suffix. В коде одна и та же seed schedule используется между candidates
   при одинаковом абсолютном времени; это полезный paired control, но не
   несколько независимых оценок $Q$.
7. Основной выбор модели: **within-state terminal selection gain**,
   rescue/harm и перенос на целые task groups. Pooled AUROC только diagnostic.

Это соответствует идее task-level progress из
[PAV](https://arxiv.org/abs/2410.08146) и предупреждению о несовпадении
process/terminal labels из [PRM Lessons](https://aclanthology.org/2025.findings-acl.547/).
Вычитание общего $V(s)$ не меняет argmax; научная новизна не в формуле
advantage, а должна быть в новой физически осмысленной информации и
подтверждённом выборе действия.

## 7. Что временно не делать

- Не запускать ещё full600/full4500 для слабого development gain.
- Не расширять K16/K64 без признаков роста oracle opportunity.
- Не оптимизировать сотни coefficients на просмотренных test episodes.
- Не начинать Flow-GRPO/Diffusion-DPO обучения 2B модели до grounded rewards.
- Не добавлять LIBERO-Safety как новую основную ось, пока базовая task SR
  этой конфигурации неинформативна; safety proxies продолжать логировать.
- Не объявлять failure detector новым planner без улучшения terminal выбора.
- Не останавливать сбор при первом удобном p-value и не отбирать только
  mixed pools для итоговой оценки deployed SR.

## 8. Что должно получиться за ближайший исследовательский цикл

Не обещание прироста SR, а три конкретных артефакта:

1. Законченная frozen таблица шести selectors с отрицательными результатами,
   compute cost и matched video examples.
2. Карта ошибок: all-fail proposal support / wrong selection / recovery benefit,
   с явно указанными tasks, uncertainty и ограничениями переноса.
3. Один P5 или recovery-кандидат, допущенный к новому тесту по прозрачному
   development gate, **либо честное NO-GO без ещё одного массового sweep**.

Для быстрого научного результата отрицательный mechanistic result тоже
полезен, если он отделяет причины и исключает альтернативы. Общая история
«больше uncertainty -> меньше value» у нас уже проверялась и недостаточна.

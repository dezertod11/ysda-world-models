# P5: replication ошибки выбора и локальные последствия chunk

Дата: 10 сентября 2026. Campaign `p5_candidate_replication_20260910`.
Основание: [предыдущие 1080 ветвей](P5_REPEAT_FEEDBACK_RESULTS_20260910.md).
Это следующий условный тест механизма, **не новый обученный controller**.

## Зачем и что проверяем

H1: локальные candidate advantages в `pool_13` и `pool_11` сохраняются при
новых seeds продолжения. H2: различия обусловлены последствиями самого H16
chunk, а не только ошибками последующей policy. H3, exploratory: в новых
состояниях тех же cells остаются воспроизводимые возможности ранжирования.

Данные предыдущих трёх повторов использованы для выбора cases/alternatives.
Новые suffix outcomes не используются для перенастройки primary comparisons.
Условная replication не означает перенос на новые задачи.

## A. Те же реальные состояния и действия

| Case | Baseline | Зафиксированные alternatives | Новые suffix seeds | Ветви |
| --- | ---: | --- | ---: | ---: |
| pool13: Position x0.2 / task2 / init7 / q3 | candidate4 | candidate3, candidate5 | 10 на candidate | 30 |
| pool11: Position x0.2 / task0 / init8 / q3 | candidate7 | candidate6 | 10 на candidate | 20 |

Task2: `pick up the salad dressing and place it in the basket`.
Task0: `pick up the alphabet soup and place it in the basket`.
Действия не пересемплируются. SHA source sidecars сохранены. Max-value и
alternatives заранее известны; порядок выполнения циклически меняется между
repeats, не зависит от успеха. Все кандидаты одного job/repeat имеют один
suffix seed и расписание model RNG по абсолютному времени.

$$
\Delta_{i,b}(s)=\frac1{10}\sum_{r=0}^{9}
\left(Y_{i,r}(s)-Y_{b,r}(s)\right).
$$

Primary comparisons: (pool13,c3,c4), (pool13,c5,c4), (pool11,c6,c7).
Rescue/harm, paired seed-bootstrap CI и exact binomial/McNemar p, Holm для
трёх сравнений. Условный replication PASS: 10/10 пар, gain >=30 п.п. и
Holm p<=0.05. Это критерий конкретного состояния, не общего benchmark.
Прежние outcomes не добавляются в primary denominator. Независимых scenes
в этой части только две; bootstrap по seeds не создаёт новые задачи.

## B. Соседние init: новые pools, не перенос индексов

Те же Position x0.2 tasks 0,2; init **9,10,11,12**; q3/t48.
Init ID соседний по файлу, не гарантия геометрической близости сцены.
Эти init не использовались в исходном P5 pilot (7,8), но глобальная
непросмотренность во всех старых экспериментах не заявляется. Это diagnostic
development, не финальный untouched holdout.

Каждый init: 10 settle actions, затем общий prefix policy max-value K8/H16
до t48. Prefix seeds и кандидатные seeds фиксированы до запуска. На t48
создаётся новая восьмёрка; она сохраняется **до новых terminal labels**.
Дальше каждый из восьми candidates проверяется с 10 suffix seeds.
8 states x 8 candidates x 10 seeds = **до 640 branches**.

Candidate3 на одном состоянии не имеет содержательного соответствия
candidate3 на другом. Поэтому здесь не переносим исходные indices и не
называем сравнение новым универсальным selector.

Для диагностики выбор по repeats0-4 проверяется на5-9, затем наоборот;
tie-break по исходному value, затем меньшему index. Сравниваем max-value,
оптимистичный best-on-same-repeats и split-repeat result. CI по task/init
группам. Это privileged outcome selector, не deployable policy.

Если prefix завершил задачу раньше q3, сохраняется отдельный
`success_before_q3`, состояние не заменяется другим и не считается fail.
Если init asset отсутствует или replay не проходит, очередь останавливается
как техническая ошибка, а не записывает policy fail.

## Общая архитектура и наблюдения

Frozen Cosmos Policy, LIBERO-PRO Object suite / Position x0.2, native OSC7D,
joint/parallel generation, denoising steps=5, generated/executed H16.
Продолжение после t64: K1/H16 до абсолютного t280. Это не авторегрессионный
`a -> s -> v` planning, не training и не официальный LIBERO-Safety benchmark.

Policy получает реальные две RGB-камеры, proprio и исходную команду.
При восстановлении используются сохранённые реальные измерения, как в
предыдущей серии. Simulator state и предметные сигналы используются только
для replay/diagnostic labels, не передаются дополнительным online input.

## Локальное действие против дальнейшего исхода

На каждом шаге записываются существующие сигналы SafetySignalTracker:
контакт с целевым предметом, target lift, goal progress, расстояние до target,
wrong-object/drop proxies и движения end-effector. Отдельно считаются:

- H16 window t49..64: contact steps, lift относительно snapshot, goal progress,
  падение/неверный предмет, локальный outcome, endpoint proprio/state.
- Suffix t65..terminal: те же временные ряды и итоговые failure type/SR.
- Начальный H16 endpoint сравнивается с сохранённым, atol1e-9; новые repeats
  обязаны воспроизводить тот же initial chunk. Признаки после t64 не входят
  в local H16 summary.

Контакт сам по себе не означает надёжный grasp, lift не означает успех всей
задачи; автоматические labels требуют просмотра видео. Локальные признаки
не дают причинной классификации ошибки автоматически. Они будут targets
будущего scorer, а не недоступными online признаками текущего выбора.

## Ресурсы и автономность

Итого **690 основных branches + 6 smoke**. Smoke: три candidates pool13,
два pool11 и candidate0 нового neighbor task2/init12. Smoke имеет отдельные
suffix seeds/каталог; не входит в main statistics. Созданный neighbor pool
после smoke переиспользуется, не выбирается по smoke success.

До трёх worker; GPU0-7 разрешены только при двух idle-проверках:
memory<256 MiB, util<5%, отсутствие CUDA-процессов. Приоритет1,3,5, затем
остальные. Чужие процессы не меняются. Очередь общая, занятая GPU не блокирует
конкретные jobs. По два совместимых jobs на одну загрузку модели.

Ожидание: ориентировочно 2-3 часа при трёх доступных GPU, не обещание срока.
Защитное окно12 часов от freeze включает ожидание ресурсов. После deadline
новые branches не начинаются, текущая получает ограниченный grace.
Сохранение после каждой ветви, resume по проверенным JSON+NPZ+видео.
Ошибка worker останавливает очередь с логом. После выхода GPU-worker
автоматически создаются CPU analysis/RESULTS.md, таблицы, график и videos.html.
Автоматического обучения P5 или открытия нового holdout нет.

Видео для **каждого кандидата**, repeats0 и9, обе камеры, от t48 до terminal:
до138 main videos плюс6 smoke. В NPZ `frame_t` хранит абсолютные индексы;
`signals` и `signal_keys` связывают метрики с кадрами. Альтернативы теперь
можно просматривать, а не только читать их terminal outcome.

## Команды из WSL

Запуск без зависимости от открытого SSH/ноутбука:

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/run_p5_candidate_replication.py --launch'
```

Статус, active GPU/PID и ориентировочный остаток при сохранении ресурсов:

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/run_p5_candidate_replication.py --status'
```

Каталог: `experiments/campaigns/p5_candidate_replication_20260910/`.
`config.json` фиксирует scripts/runtime/source SHA, случаи, seeds, comparisons.
`sequence_status.json` содержит состояние очереди; `batches/*.log` и
`*.status.json` дают ход конкретного worker. `analysis/summary.json`
отдельно показывает partial/completed, exclusions и результаты.

На момент составления протокола результатов этой серии ещё нет.

## Старт

Запущено 10 сентября в **12:01:22 MSK**, PID **3812904**.
Frozen config SHA256:
`448000ed731dc54bb95c98509c8264b5d011496e4ff793e07e865511a28f3fc7`.
Два anchor smoke и neighbor smoke получили свободные GPU1/5/3.
37 CPU-тестов прошли локально и на сервере; результаты smoke/main здесь
не подменяются этим техническим тестом.

### Техническая поправка сериализации, до основного сбора

Первая smoke-попытка остановилась при записи временных рядов: frozen tracker
хранит скалярные поля вместе с массивами object positions, eef position и
goal predicates. Попытка, логи и исходные scripts/config сохранены в
`technical_attempt_01_signal_arrays/`. Основных branches: 0.
Исправлено только хранение: скаляры в `signals`, массивы в отдельных
`signal_field__*`, с названиями objects/targets и описанием goal predicates.
Ни policy, ни симулятор, ни действия, ни seeds, ни deadline не менялись;
уже созданные pools переиспользуются. На синтетическом tracker с векторными
полями проверено чтение NPZ без pickle. Smoke повторяется полностью.

Повторный запуск: **12:07:02 MSK**, PID **3818565**, текущий config SHA256
`c7ccbf52308804c10071348efb19b69ce8965c8d995706ac7a06ef8d0c00d171`.
Сверка JSON показала изменение только SHA двух файлов сериализации;
jobs, seeds, comparisons, runtime и deadline совпали. Пройдено39 CPU-тестов
локально и на сервере. Первая попытка и статус failed остаются в архиве,
не смешиваются с текущим статусом.

В **12:09 MSK** smoke завершён: 6/6 terminal records, точные H16 endpoints,
все6 видео декодированы, 74-233 кадров, корректные временные оси и
многомерные object/eef signals в NPZ. Это технический PASS, не основной SR.
Основная серия автоматически стартовала на GPU3 (два anchors), GPU5
(neighbors task0/init9-10), GPU0 (task0/init11-12). Остальные jobs общие,
будут взяты освобождающимся worker. Нового обученного метода ещё нет.

# Ночная очередь 9 сентября: закрыть consensus и подготовить P5

**Изменение ресурсов в 01:18 MSK:** по запросу пользователя разрешены свободные
**GPU 1-7**, GPU0 исключена. Диспетчер перезапущен, новый PID **2181819**.
Готовые 3 smoke и пакет из 5 reference rollout сохранены. Незавершённый
эпизод может быть повторён; сохранённые эпизоды пропускаются через resume.
Исходный freeze не переписан: отдельный `resource_amendment_gpu17.json`
фиксирует SHA старого/нового launcher. Метод, модель, задачи и seeds прежние.
Исходный launcher, статус, manifest и traces сохранены в `resource_gpu17_backup`.
57 локальных тестов прошли, в том числе проверка общей очереди при занятой GPU.

**Запущено 9 сентября в 01:01 MSK**, PID **2172058**. Проверка 597 сохранённых
rollout и всех трёх reference smoke завершена. На 01:08 началась основная
серия: `environment_t0_raw_medoid` на GPU3; остальные занятые карты ждут.
48 тестов прошли локально; серверный pytest также сообщил 48 passed.
Статус ниже является срезом запуска,
для текущего прогресса использовать команды из последнего раздела.

Smoke outcomes: raw medoid success (115 шагов), KeyStone-style и KDPE endpoint
fail (280 шагов). Для всех сохранены полные видео и query traces, проверены
timeline и одинаковый initial state. Это три integration episodes, не оценка
SR и не основание выбирать лучший метод.

Первая попытка остановилась до GPU-запуска на формировании HTML: исходные
видео лежат в старой кампании, а генератор ожидал относительные пути внутри
новой. Исходные данные не менялись. Исправлен только новый генератор
valid-support отчёта; логи и freeze первой попытки сохранены в
`consensus_p5_night_20260909__pre_gpu_video_path_error`. Новый SHA зафиксирован
до старта любого reference rollout. Старые frozen shared scripts не изменены.

## Завершённый valid-support анализ

После исключения недоступного init asset получены все 199 сопоставимых
конфигураций, по одному rollout каждого метода:

| Метод | Object, n=50 | Environment, n=50 | Position, n=99 | Macro-SR | Success / 199 |
|---|---:|---:|---:|---:|---:|
| K1 | 94% | 38% | 28.28% | 53.43% | 94 |
| Max-value K4 | 94% | 40% | 30.30% | 54.77% | 97 |
| OSC medoid K4 | 96% | 40% | 26.26% | 54.09% | 94 |

Medoid относительно max-value: **-0.68 п.п.**, CI [-3.33; +1.99] п.п.,
3 rescue / 6 harm, McNemar p=0.508. Превосходство не показано; не доказано и
статистически надёжное ухудшение. Выигрыш одного Object episode не компенсирует
четыре потерянных Position success. Поэтому новые consensus coefficients
не подбираются; reference-сравнение закрывает вопрос о близких published
selectors, а P5 pilot проверит доступность терминальной обучающей информации.
[Машинный отчёт и график](campaigns/trajectory_consensus_20260909_valid199/trajectory_analysis/RESULTS.md).

## Решение по накопленным исследованиям

Самые убедительные положительные результаты проекта связаны с реальным
feedback и восстановлением захвата: P0 shared-prefix 46% -> 64% на 100 парах,
P3c online RGB-regrasp 32.5% -> 60% на 40 новых начальных состояниях.
Их перенос на новые задачи ограничен; они не являются универсальным новым
candidate planner. P3e routing имеет меньший и предварительный эффект.

Прямые штрафы за residual uncertainty, несколько value/latent rankers и
consensus пока не доказали устойчивый прирост terminal success. Старый
terminal critic уже использовал advantage и ridge ensemble; нельзя выдавать
ещё один такой fit за совершенно новую P5-идею. Старый K16 experiment также
показал почти полное насыщение proposal opportunity к K8. Повторять его
целиком или перебирать ещё один consensus coefficient на test не будем.

Текущий вопрос: **есть ли успешные кандидаты внутри одного состояния и
какие task-critical различия предсказывают их исход, а не только сложность
всего эпизода?** Следующая P5-модель должна проверяться на task/group-disjoint
данных и терминальных исходах. Для этого нужен более разнообразный
development-набор, а не немедленное обучение на нескольких удачных парах.

## Обнаруженная остановка

В 00:42 MSK проверено: исходный compact остановился на **597/600**.
Единственный недоступный случай: `Position y0.5 / task1 / init1`.
В исходном LIBERO-PRO и runtime файл `cream_cheese.pruned_init`
(полное имя и SHA записаны в support_amendment.json) содержит **0 состояний**.
Все три collector сообщают `only 0 init states`, затем пустой analysis падает.
Это ошибка доступности benchmark asset, не fail модели и не GPU OOM.
Reference-очередь правильно остановилась после failed dependency.

Исправление протокола:

- Исходные failed manifests, конфигурации и логи не меняются и не удаляются.
- Ни один simulator init не выдумывается и не подменяется другим.
- Из сравнения симметрично исключается один недоступный случай для всех шести
  методов. Это структурное исключение без наблюдённого policy outcome.
- Создаётся производное представление `trajectory_consensus_20260909_valid199`:
  **199 случаев x 3 метода = 597 уже вычисленных rollout**, без пересчёта.
- Новое comparison-run `consensus_references_20260909_valid199` содержит
  **199 x 3 = 597 новых rollout**. Методы, гиперпараметры, seeds и модель
  совпадают с исходным reference protocol; исключается только пустой asset.

Этот результат будет относиться к **199 доступным случаям**, а не к полной
изначальной сетке 200 или стандартному полному LIBERO-PRO benchmark.
Отсутствующий случай не считается ни success, ни fail. Старые 600/1200 и
full4500 не объявляются завершёнными.

## Автономная последовательность

1. CPU-проверка всех 597 сохранённых rollout, timeline и videos; отчёт по
   K1 / max-value K4 / OSC medoid K4 на доступной поддержке benchmark.
2. Три integration smoke для raw medoid / KeyStone-style / KDPE adaptation.
3. **597 reference rollout**, затем общий отчёт по **1194 rollout**, шести
   стратегиям и 199 одинаковым task/init/seed конфигурациям.
4. Один integration snapshot K8 для P5 collector, восемь terminal branches.
5. **36 P5 development snapshots K8**, до **288 terminal branches**;
   автоматический аудит replay, признаков, nested K4/K8 и oracle opportunity.

Новый P5-model, его closed-loop deployment и confirmatory holdout этой ночью
автоматически не открываются. Сначала проверяется, достаточно ли данных для
такого следующего эксперимента. Reference outcome не используется для
выбора коэффициентов или смены medoid на более удачный вариант.

## Дизайн P5 pilot

| Фактор | Задачи | Init | Query | Snapshots | K8 terminal branches |
|---|---|---|---|---:|---:|
| Object | 0,3 | 7,8 | 0,3 | 8 | 64 |
| Position x0.2 | 0,2,9 | 7,8 | 0,3 | 12 | 96 |
| Position y0.2 | 0,2,4,9 | 7,8 | 0,3 | 16 | 128 |
| Итого | 9 task/perturbation cells | | | **36** | **288** |

Это целевой development-набор на пограничных задачах, выбранных с учётом
уже открытых исследований. Отсутствие пересечения со всеми историческими
init не утверждается. Никакого поиска seeds до получения нужного исхода нет.
Environment пока не расширяем: он остаётся в закрывающем reference benchmark;
для learned P5 его включение требует отдельного data-opportunity решения.

В каждом snapshot: восемь независимо сэмплированных H16 кандидатов, совместная
parallel генерация action/future/value, 5 denoising steps. Каждый кандидат
фактически исполняется из одного captured state и продолжается одной и той
же K1/H16 policy до terminal endpoint в пределах общего лимита 280 шагов.
Queries q0 и q3 одного task/init зависимы и не считаются независимыми задачами.

Сохраняются generated action/future predictions, causal candidate features,
terminal success, drop/wrong-object/safety proxies и replay audit.
Post-execution outcomes предназначены только для labels/evaluation, не для
online input. Матрица признаков не включает privileged simulator state.
Полные видео всех шести deployed reference-стратегий остаются в comparison;
P5 pilot является коллекцией snapshot/branch outcomes, не новой video-gallery.

Для одного и того же K8 pool считаем вложенные K4 и K8:

$$
O_K(s)=\max_{i\le K}Y_i,\quad
G_K(s)=Y_{\arg\max_{i\le K}V_i},\quad
R_K(s)=O_K(s)-G_K(s).
$$

Отдельно: доля mixed pools, within-pool value accuracy, равномерный выбор
в ожидании и число task/init groups. Pooled failure AUC не заменяет
within-state candidate ranking.

## Gates и ограничения

- Все запланированные 36 pools и все восемь исходов каждого pool должны быть
  сохранены; отсутствующие ветки не считаются fail.
- Main/open replay error <= 1e-9. Отсутствующий audit не считается PASS;
  невалидные pools сохраняются, исключаются из анализа. Требуется >=90%
  strict replay; единственный smoke обязан быть strict.
- Доступны конечные causal features, H16, parallel; q0/q3 по всем 18 groups.
- Для следующего fit желательно не менее 8 strict mixed pools, минимум
  3 task IDs и оба фактора. Это **data-opportunity gate**, не доказательство
  эффективности и не основание автоматически открывать holdout.
- При недостатке opportunity нет автоматического расширения выборки до
  положительного результата. Сохраняется отрицательный отчёт и требуется
  новое исследовательское решение.

## Надёжность и ресурсы

Main run: `consensus_p5_night_20260909`.
Все конфигурации, runtime и orchestration защищены SHA256 до запуска.
Новый runtime использует проверенный frozen reference snapshot. Старые
shared scripts не изменяются. Все init assets пилота проверены до GPU-запуска.

Singleton flock; detached process; heartbeat и stage каждые 10 секунд;
resume использует completion markers. Ошибка останавливает цепочку, не
подменяет исход и не запускает бесконечные retries. Повторно запускать
команду следует после диагностики ошибки, а не менять frozen files на ходу.

После поправки 01:18 разрешены **GPU 1-7**. Общая очередь начинает job при
memory.used <256 MiB и utilization <5%; чужие процессы не завершаются.
GPU0 не используется. Занятая карта не забирает и не резервирует задания:
если GPU4 не освободится всю ночь, её задания выполнят другие свободные GPU.
Для завершения не требуется, чтобы поработала каждая разрешённая карта.
Очередь ждёт освобождения ресурсов только когда нет доступных workers.
Завершение строго к утру не гарантируется; доступность GPU важнее
календарной оценки. Локальный ПК после detached запуска может быть выключен.

## Команды и результаты

Из WSL:

```bash
./scripts/mlspace_experiment_status.sh consensus_p5_night_20260909
./scripts/mlspace_experiment_status.sh consensus_references_20260909_valid199
./scripts/mlspace_experiment_status.sh p5_boundary_candidates_20260909
```

Повторный запуск после проверки состояния, из серверного project root:

```bash
nohup .venv-cosmos/bin/python -u scripts/run_consensus_valid_support_night.py --execute --gpus 1,2,3,4,5,6,7 >> experiments/campaigns/consensus_p5_night_20260909/sequence.log 2>&1 < /dev/null &
```

Отчёты:

- `trajectory_consensus_20260909_valid199/trajectory_analysis/RESULTS.md`
- `consensus_references_20260909_valid199/matched_analysis/RESULTS.md`
- `consensus_references_20260909_valid199/matched_analysis/videos.html`
- `p5_boundary_candidates_20260909/p5_analysis/RESULTS.md`
- `consensus_p5_night_20260909/sequence_status.json` и `freeze.json`

Базовые разборы: [общий научный итог](RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md),
[common-pool](CONSENSUS_COMMON_POOL_RESULTS_20260908.md),
[предыдущий K16](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md),
[предыдущий terminal critic](TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md).

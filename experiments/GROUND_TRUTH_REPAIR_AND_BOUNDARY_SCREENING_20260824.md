# Ground-truth repair и поиск boundary cases

Дата постановки: 24 августа 2026 года.

## Статус запуска

Кампания `ground_truth_boundary_screening_20260824` запущена 24 августа в
12:22 MSK на GPU 5 и 6. Перед ней успешно прошли 40-task semantic preflight,
38 focused Cosmos tests, headless simulator smoke и один реальный model rollout:
schema-v2 sidecar содержит 12 query, 96 исполненных действий и 96 выровненных
simulator-state записей. Основная кампания находится в состоянии `running`;
частичные доли success/fail не интерпретируются до завершения всех jobs и
автоматического integrity check.

## Зачем нужен новый запуск

Audit temporal-overlap campaign показал две систематические ошибки разметки:

1. LIBERO-PRO `*_task` меняет `(:language ...)` и `(:goal ...)` внутри BDDL,
   но прежний evaluator передавал Cosmos Policy исходную команду, восстановленную
   из имени файла.
2. Эвристика `lift -> release` считала успешное выкладывание предмета в целевую
   область падением, особенно в multi-object задачах.

Полная проверка четырёх task-OOD suites обнаружила instruction shift во всех
40/40 задачах. Поэтому старые результаты на этих suites не являются оценкой
естественного task OOD: policy и simulator решали разные задачи.

## Что исправлено

- policy instruction читается из распарсенного активного BDDL;
- trace сохраняет benchmark instruction, active instruction, источник команды
  и флаг их различия;
- goal predicates вычисляются на каждом simulator step;
- release считается `successful_target_release`, если predicate конкретного
  предмета уже выполнен;
- `target_drop_candidate` ставится только для преждевременного release до
  выполнения object-specific goal;
- goal receptacle исключён из кандидатов `wrong_object`;
- sidecar schema v2 сохраняет step-level object/eef poses, predicate states и
  target release transitions.

Replay двух ранее записанных trajectories подтвердил ожидаемое поведение:

| Episode | Official outcome | Старая label | Исправленная label |
|---|---|---|---|
| `libero_10_with_mug/task4`, seed 1320000 | success | drop около первого placement | successful release, no drop |
| `libero_spatial_swap/task8`, seed 1410291 | fail | drop | premature target drop |

Чистое применение project patch к pinned Cosmos revision и focused test suite
прошли успешно: 38 tests passed.

## Screening protocol

Policy и sampling остаются теми же, что в passive temporal-overlap run:

$$
H=16,\qquad K=8,\qquad B=4,
$$

где модель генерирует четыре stochastic candidate chunks, `max(value)` выбирает
один chunk, а среда исполняет первые восемь действий. Overlap и uncertainty
только записываются и не меняют policy.

Основной screening покрывает:

| Family | Cases | Rollouts per case | Horizon |
|---|---:|---:|---:|
| `libero_goal_task` | 10 | 6 | 320 |
| `libero_spatial_task` | 10 | 6 | 240 |
| `libero_object_task` | 10 | 6 | 300 |
| `libero_10_task` | 10 | 6 | 520 |
| `libero_goal_with_mug/task9/init0` | 1 | 12 | 320 |
| `libero_10_with_milk/task9/init0` | 1 | 12 | 520 |

Итого запланировано 264 rollout. На момент запуска GPU 2, 3, 4 и 7 были заняты
другими проектами, поэтому jobs сбалансированы в две последовательные очереди
на свободных физических GPU 5 и 6. Для каждого case используются одинаковые
task/init state и различные rollout seeds. Early stopping выключен, чтобы не
смещать оценку success rate.

## Критерий отбора

Для case $c$ с $n_c$ rollout оценивается

$$
\hat p_c = \frac{N_{success,c}}{n_c},
\qquad
b_c = 4\hat p_c(1-\hat p_c).
$$

$b_c=1$ соответствует границе 50/50, а $b_c=0$ полностью детерминированному
исходу. Case считается `confirmed_mixed`, если найдено минимум два success и два
fail; один minority outcome даёт только `provisional_mixed`.

В следующий большой paired experiment проходят cases с outcomes обоих классов,
приоритетно $0.2\le\hat p_c\le0.8$. На них собираются 30-60 новых seeds и
оцениваются только pre-event query, с split по целым seeds и held-out cases.

## Запуск и статус

```bash
./scripts/run_ground_truth_boundary_screening.sh

./scripts/status_libero_campaign.py \
  --campaign-dir experiments/campaigns/ground_truth_boundary_screening_20260824 \
  --watch 60
```

После завершения результаты появляются в
`analysis/boundary_screening/`: seed-level outcomes, полный case summary,
список mixed cases, Wilson confidence intervals и график success rates.

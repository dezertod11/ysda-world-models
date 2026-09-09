# K16 proposal-opportunity screen: results

Campaign: `proposal_opportunity_k16_20260830`.

Анализ следует зафиксированному до сбора протоколу
`experiments/PROPOSAL_OPPORTUNITY_K16_PROTOCOL_20260830.md`.
Candidate labels не использовались для выбора cells, seeds или gate.

## Основной вопрос

Проверяется наличие успешной альтернативы внутри K16 pool, а не качество
нового selector. `Oracle gap = SR_oracle - SR_maxV`; selector разрешён
только при хотя бы одном rescue и point estimate gap не менее 5 п.п.
95% интервалы рассчитаны cluster bootstrap по `task/init_state`.

## Factor-level result

| factor      |   states |   independent_groups |   heterogeneous_states |   success_rescues |   all_candidates_fail |   all_candidates_succeed | maxv_sr   | oracle_sr   |   oracle_gap_pp |   oracle_gap_pp_ci_low |   oracle_gap_pp_ci_high | selector_gate_pass   |
|:------------|---------:|---------------------:|-----------------------:|------------------:|----------------------:|-------------------------:|:----------|:------------|----------------:|-----------------------:|------------------------:|:---------------------|
| Environment |       20 |                   10 |                      0 |                 0 |                    20 |                        0 | 0.0%      | 0.0%        |               0 |                      0 |                       0 | FAIL                 |
| Object      |       10 |                    5 |                      7 |                 3 |                     2 |                        1 | 50.0%     | 80.0%       |              30 |                     10 |                      50 | PASS                 |
| Position    |       20 |                    5 |                      2 |                 2 |                    18 |                        0 | 0.0%      | 10.0%       |              10 |                      0 |                      20 | PASS                 |

## Task/query diagnostics

| factor      | case_id                          | suite                |   task_id |   query_idx |   states |   heterogeneous_states |   success_rescues |   all_candidates_fail | maxv_sr   | oracle_sr   |   oracle_gap_pp | selector_gate_pass   |
|:------------|:---------------------------------|:---------------------|----------:|------------:|---------:|-----------------------:|------------------:|----------------------:|:----------|:------------|----------------:|:---------------------|
| Environment | proposal_k16_environment_task0   | libero_object_env    |         0 |           0 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Environment | proposal_k16_environment_task0   | libero_object_env    |         0 |           3 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Environment | proposal_k16_environment_task2   | libero_object_env    |         2 |           0 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Environment | proposal_k16_environment_task2   | libero_object_env    |         2 |           3 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Object      | proposal_k16_object_task0        | libero_object_object |         0 |           0 |        5 |                      4 |                 1 |                     1 | 60.0%     | 80.0%       |              20 | PASS                 |
| Object      | proposal_k16_object_task0        | libero_object_object |         0 |           3 |        5 |                      3 |                 2 |                     1 | 40.0%     | 80.0%       |              40 | PASS                 |
| Position    | proposal_k16_position_x0p3_task0 | libero_object_temp   |         0 |           0 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Position    | proposal_k16_position_x0p3_task0 | libero_object_temp   |         0 |           3 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |
| Position    | proposal_k16_position_y0p3_task0 | libero_object_temp   |         0 |           0 |        5 |                      2 |                 2 |                     3 | 0.0%      | 40.0%       |              40 | PASS                 |
| Position    | proposal_k16_position_y0p3_task0 | libero_object_temp   |         0 |           3 |        5 |                      0 |                 0 |                     5 | 0.0%      | 0.0%        |               0 | FAIL                 |

## Paired nested K4/K8/K16

Первые 4 и 8 candidate seeds каждого K16 pool образуют вложенные
proposal sets. Поэтому эта таблица сравнивает candidate budget на тех же
exact states; в отличие от исторических кампаний это paired evidence.

| factor      |   budget |   states |   heterogeneous_states |   success_rescues |   all_candidates_fail | maxv_sr   | oracle_sr   |   oracle_gap_pp |
|:------------|---------:|---------:|-----------------------:|------------------:|----------------------:|:----------|:------------|----------------:|
| Environment |        4 |       20 |                      0 |                 0 |                    20 | 0.0%      | 0.0%        |               0 |
| Environment |        8 |       20 |                      0 |                 0 |                    20 | 0.0%      | 0.0%        |               0 |
| Environment |       16 |       20 |                      0 |                 0 |                    20 | 0.0%      | 0.0%        |               0 |
| Object      |        4 |       10 |                      5 |                 4 |                     2 | 40.0%     | 80.0%       |              40 |
| Object      |        8 |       10 |                      6 |                 4 |                     2 | 40.0%     | 80.0%       |              40 |
| Object      |       16 |       10 |                      7 |                 3 |                     2 | 50.0%     | 80.0%       |              30 |
| Position    |        4 |       20 |                      1 |                 0 |                    19 | 5.0%      | 5.0%        |               0 |
| Position    |        8 |       20 |                      2 |                 2 |                    18 | 0.0%      | 10.0%       |              10 |
| Position    |       16 |       20 |                      2 |                 2 |                    18 | 0.0%      | 10.0%       |              10 |

## Решение

Гипотеза о появлении terminal candidate choice хотя бы в одном Environment/Position factor: **SUPPORTED**.

- Selector gate прошли: Object, Position.
- Для этих факторов следующий test: action-conditioned
  autoregressive `action -> future -> value` на сохранённых
  candidates, затем frozen closed-loop проверка.
- Selector gate не прошли: Environment.
- Для них запрещён очередной retuning score: нужны новые
  proposals, ранний feedback/requery или recovery policy.

Отдельный historical CSV оставлен только для контекста: старые K4/K8
кампании имеют другие init states и не заменяют paired nested comparison.

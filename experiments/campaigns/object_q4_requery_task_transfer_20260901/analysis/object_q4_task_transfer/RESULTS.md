# Object query-4 re-query: untouched-task transfer

- Exact-state pairs: **180**.
- Untouched tasks: **9**.
- Task/init clusters: **90**.
- Rescue / harm: **0 / 0**.
- Task-macro delta: **+0.00 pp**.
- Integrity gate: **FAIL**.
- Practical transfer gate: **FAIL**.
- Confirmatory transfer gate: **FAIL**.

## Primary endpoint

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|      180 |                   90 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |            180 |           0 |             0.025 |                          -0.025 |                  nan |                       177 |

## Integrity

```json
{
  "suite_matches": true,
  "task_ids_match": true,
  "task0_excluded": true,
  "init_state_ids_match": true,
  "query_indices_match": true,
  "observed_pairs": 180,
  "target_pairs": 180,
  "observed_task_init_cells": 90,
  "target_task_init_cells": 90,
  "pairs_per_cell_values": [
    2
  ],
  "expected_pairs_per_cell": 2,
  "duplicate_analysis_states": 0,
  "strict_integrity_states": 177,
  "max_replay_state_abs": 0.04607635312140701,
  "valid": false
}
```

## By untouched task

|   task_id |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|----------:|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|         1 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         2 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         3 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         4 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         5 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         6 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        18 |
|         7 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        19 |
|         8 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         9 |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |

## By policy phase

| phase_at_snapshot   |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:--------------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| approach            |        2 |                    1 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              2 |           0 |             0.025 |                          -0.025 |                  nan |                         2 |
| grasp               |       71 |                   37 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             71 |           0 |             0.025 |                          -0.025 |                  nan |                        71 |
| transport           |      107 |                   55 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |            107 |           0 |             0.025 |                          -0.025 |                  nan |                       104 |

## By task and phase

|   task_id | phase_at_snapshot   |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|----------:|:--------------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|         1 | grasp               |       16 |                    9 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             16 |           0 |             0.025 |                          -0.025 |                  nan |                        16 |
|         1 | transport           |        4 |                    3 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              4 |           0 |             0.025 |                          -0.025 |                  nan |                         4 |
|         2 | transport           |       20 |                   10 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             20 |           0 |             0.025 |                          -0.025 |                  nan |                        20 |
|         3 | grasp               |       12 |                    6 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             12 |           0 |             0.025 |                          -0.025 |                  nan |                        12 |
|         3 | transport           |        8 |                    4 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              8 |           0 |             0.025 |                          -0.025 |                  nan |                         8 |
|         4 | grasp               |       14 |                    7 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             14 |           0 |             0.025 |                          -0.025 |                  nan |                        14 |
|         4 | transport           |        6 |                    3 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              6 |           0 |             0.025 |                          -0.025 |                  nan |                         6 |
|         5 | grasp               |       16 |                    8 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             16 |           0 |             0.025 |                          -0.025 |                  nan |                        16 |
|         5 | transport           |        4 |                    2 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              4 |           0 |             0.025 |                          -0.025 |                  nan |                         4 |
|         6 | grasp               |        4 |                    2 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              4 |           0 |             0.025 |                          -0.025 |                  nan |                         4 |
|         6 | transport           |       16 |                    8 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             16 |           0 |             0.025 |                          -0.025 |                  nan |                        14 |
|         7 | approach            |        2 |                    1 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              2 |           0 |             0.025 |                          -0.025 |                  nan |                         2 |
|         7 | transport           |       18 |                    9 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             18 |           0 |             0.025 |                          -0.025 |                  nan |                        17 |
|         8 | grasp               |        4 |                    2 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              4 |           0 |             0.025 |                          -0.025 |                  nan |                         4 |
|         8 | transport           |       16 |                    8 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             16 |           0 |             0.025 |                          -0.025 |                  nan |                        16 |
|         9 | grasp               |        5 |                    3 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |              5 |           0 |             0.025 |                          -0.025 |                  nan |                         5 |
|         9 | transport           |       15 |                    8 |                   1 |                       1 |               0 |                      0 |                       0 |         0 |       0 |             0 |                  0 |             15 |           0 |             0.025 |                          -0.025 |                  nan |                        15 |

## Discordant failure transitions

No discordant pairs.

## Frozen decision

The fixed query-4 schedule transfers suite-wide only when the practical gate passes.
A confirmatory transfer claim additionally requires a positive lower cluster-CI bound
and exact McNemar `p<0.05`. Per-task and phase rows remain diagnostics.

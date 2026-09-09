# Object task-0 query-4 shared-prefix replication

- Integrity: **PASS**.
- Practical gate: **PASS**.
- Confirmatory gate: **PASS**.

## Primary strict endpoint

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|      100 |                   50 |                0.46 |                    0.64 |            0.18 |                   0.04 |                 0.32025 |        31 |      13 |            18 |               0.44 |             33 |          23 |             0.025 |                           0.155 |           0.00955988 |                       100 |

## Nominal sensitivity

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|      100 |                   50 |                0.46 |                    0.64 |            0.18 |                   0.04 |                 0.32025 |        31 |      13 |            18 |               0.44 |             33 |          23 |             0.025 |                           0.155 |           0.00955988 |                       100 |

## Integrity

```json
{
  "pairs": 100,
  "target_pairs": 100,
  "expected_keys_match": true,
  "missing_keys": 0,
  "unexpected_keys": 0,
  "duplicate_snapshot_ids": 0,
  "suite_matches": true,
  "task_matches": true,
  "query_matches": true,
  "init_states_match": true,
  "split_matches": true,
  "feedback_performed": 100,
  "completed_before_requery": 0,
  "feedback_paths_valid": 100,
  "terminal_labels_complete": true,
  "candidate_pool_size_valid": true,
  "one_max_value_candidate_per_pool": true,
  "strict_replay_pairs": 100,
  "minimum_strict_replay_pairs": 95,
  "max_replay_state_abs_error": 1.2850659729043978e-10,
  "valid": true
}
```

## Rollout-position sensitivity

|   rollout_id |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|-------------:|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|            0 |       50 |                   50 |                0.5  |                    0.6  |            0.1  |                  -0.08 |                    0.28 |        13 |       8 |             5 |               0.42 |             17 |          12 |             0.025 |                           0.075 |             0.38331  |                        50 |
|            1 |       50 |                   50 |                0.42 |                    0.68 |            0.26 |                   0.08 |                    0.44 |        18 |       5 |            13 |               0.46 |             16 |          11 |             0.025 |                           0.235 |             0.010622 |                        50 |

## Failure transitions on strict pairs

| factor   | terminal_outcome   | open_terminal_failure_type         | feedback_terminal_failure_type     |   states |
|:---------|:-------------------|:-----------------------------------|:-----------------------------------|---------:|
| Object   | rescue             | timeout_no_goal                    | success                            |       21 |
| Object   | harm               | success                            | timeout_no_goal                    |       10 |
| Object   | rescue             | kinematic_deadlock_candidate       | success                            |        5 |
| Object   | rescue             | target_drop_candidate              | success                            |        4 |
| Object   | harm               | success                            | wrong_object_interaction_candidate |        1 |
| Object   | harm               | success                            | target_drop_candidate              |        1 |
| Object   | harm               | success                            | kinematic_deadlock_candidate       |        1 |
| Object   | rescue             | wrong_object_interaction_candidate | success                            |        1 |

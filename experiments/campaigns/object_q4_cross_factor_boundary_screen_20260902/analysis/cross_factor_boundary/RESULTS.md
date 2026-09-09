# Object query-4 cross-factor boundary screen

This is a development screen, not a confirmatory transfer result.

- Integrity: **PASS**.
- Eligible cells: position_x0p2_task0, position_y0p2_task0.

## Cell summary

| case_id             | factor      | perturbation              |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |   pooled_successes |   pooled_failures | effect_support   | non_ceiling_opportunity   | eligible_for_new_seed_holdout   |
|:--------------------|:------------|:--------------------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|-------------------:|------------------:|:-----------------|:--------------------------|:--------------------------------|
| environment_task0   | Environment | environment-seed-20260825 |       19 |                   19 |                 0   |                    0    |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              0 |          19 |             0.025 |                          -0.025 |          nan         |                        19 |                  0 |                38 | False            | False                     | False                           |
| position_x0p1_task0 | Position    | x0.1                      |       18 |                   18 |                 1   |                    1    |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |             18 |           0 |             0.025 |                          -0.025 |          nan         |                        18 |                 36 |                 0 | False            | False                     | False                           |
| position_x0p2_task0 | Position    | x0.2                      |       20 |                   20 |                 0.2 |                    0.15 |           -0.05 |                  -0.25 |                    0.1  |         1 |       2 |            -1 |               0.15 |              2 |          15 |             0.025 |                          -0.075 |            1         |                        20 |                  7 |                33 | False            | True                      | True                            |
| position_y0p2_task0 | Position    | y0.2                      |       20 |                   20 |                 0.4 |                    0.8  |            0.4  |                   0.1  |                    0.65 |        10 |       2 |             8 |               0.6  |              6 |           2 |             0.025 |                           0.375 |            0.0385742 |                        20 |                 24 |                16 | False            | True                      | True                            |
| position_y0p3_task0 | Position    | y0.3                      |       20 |                   20 |                 0   |                    0.1  |            0.1  |                   0    |                    0.25 |         2 |       0 |             2 |               0.1  |              0 |          18 |             0.025 |                           0.075 |            0.5       |                        20 |                  2 |                38 | False            | False                     | False                           |

## Overall descriptive summary

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|       97 |                   97 |            0.309278 |                0.402062 |       0.0927835 |              0.0103093 |                0.175258 |        13 |       4 |             9 |           0.175258 |             26 |          54 |             0.025 |                       0.0677835 |            0.0490417 |                        97 |

## Failure transitions

| case_id             | terminal_outcome   | open_terminal_failure_type   | feedback_terminal_failure_type     |   pairs |
|:--------------------|:-------------------|:-----------------------------|:-----------------------------------|--------:|
| position_x0p2_task0 | harm               | success                      | timeout_no_goal                    |       2 |
| position_x0p2_task0 | rescue             | timeout_no_goal              | success                            |       1 |
| position_y0p2_task0 | rescue             | timeout_no_goal              | success                            |      10 |
| position_y0p2_task0 | harm               | success                      | timeout_no_goal                    |       1 |
| position_y0p2_task0 | harm               | success                      | wrong_object_interaction_candidate |       1 |
| position_y0p3_task0 | rescue             | timeout_no_goal              | success                            |       2 |

## Integrity

```json
{
  "pairs": 100,
  "target_pairs": 100,
  "expected_keys_match": true,
  "missing_keys": 0,
  "unexpected_keys": 0,
  "duplicate_decision_keys": 0,
  "cases_match": true,
  "query_matches": true,
  "split_matches": true,
  "terminal_labels_complete": true,
  "feedback_paths_valid": 100,
  "candidate_pool_size_valid": true,
  "one_max_value_candidate_per_pool": true,
  "strict_replay_pairs": 97,
  "minimum_strict_replay_pairs": 95,
  "max_replay_state_abs_error": 1.8976327370925916e-06,
  "valid": true
}
```

# Object task-0 query-4 scheduled controller

- Integrity: **FAIL**.
- Practical gate: **FAIL**.
- Confirmatory gate: **FAIL**.

## Paired terminal endpoint

| subset   |   pairs |   baseline_success_rate |   method_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   mcnemar_pvalue |   adjusted_delta |   baseline_mean_queries |   method_mean_queries |
|:---------|--------:|------------------------:|----------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|-----------------:|-----------------:|------------------------:|----------------------:|
| nominal  |     100 |                0.35     |              0.54     |        0.19     |                   0.09 |                0.29     |        25 |       6 |       0.00087791 |         0.165    |                 15.24   |               15.55   |
| strict   |      34 |                0.411765 |              0.558824 |        0.147059 |                   0    |                0.294118 |         7 |       2 |       0.179688   |         0.122059 |                 14.5882 |               15.3824 |

## Prefix integrity

```json
{
  "trace_files": 12,
  "episode_counts": {
    "maxV-H16": 100,
    "maxV-Q4-H8-requery-H8": 100
  },
  "paired_state_count": 100,
  "identical_state_sets": true,
  "suite_matches": true,
  "task_ids_match": true,
  "init_state_ids_match": true,
  "split_values": [
    "generalization"
  ],
  "all_max_value_selected": true,
  "schedule_valid": true,
  "strict_prefix_pairs": 34,
  "minimum_strict_prefix_pairs": 95,
  "max_sim_state_difference": 6.4371876662981755,
  "max_candidate_value_difference": 0.2421358823776245,
  "max_candidate_first_action_difference": 2.0394182205200195,
  "valid": false
}
```

## Init-state diagnostics

|   init_state_id |   pairs |   baseline_success_rate |   method_success_rate |   success_delta |   strict_prefix |
|----------------:|--------:|------------------------:|----------------------:|----------------:|----------------:|
|               0 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|               1 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|               2 |       2 |                     1   |                   1   |             0   |               0 |
|               3 |       2 |                     1   |                   1   |             0   |               0 |
|               4 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|               5 |       2 |                     0   |                   0   |             0   |               0 |
|               6 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|               7 |       2 |                     0   |                   0   |             0   |               0 |
|               8 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|               9 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|              10 |       2 |                     1   |                   1   |             0   |               0 |
|              11 |       2 |                     0   |                   1   |             1   |               0 |
|              12 |       2 |                     0   |                   1   |             1   |               0 |
|              13 |       2 |                     0   |                   0   |             0   |               0 |
|              14 |       2 |                     1   |                   1   |             0   |               0 |
|              15 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              16 |       2 |                     0.5 |                   1   |             0.5 |               2 |
|              17 |       2 |                     0   |                   0   |             0   |               2 |
|              18 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              19 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              20 |       2 |                     1   |                   1   |             0   |               2 |
|              21 |       2 |                     0   |                   0   |             0   |               2 |
|              22 |       2 |                     0   |                   0   |             0   |               2 |
|              23 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              24 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              25 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              26 |       2 |                     1   |                   1   |             0   |               0 |
|              27 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              28 |       2 |                     0   |                   0   |             0   |               0 |
|              29 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              30 |       2 |                     0   |                   0   |             0   |               0 |
|              31 |       2 |                     0   |                   1   |             1   |               0 |
|              32 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              33 |       2 |                     0.5 |                   1   |             0.5 |               2 |
|              34 |       2 |                     1   |                   0.5 |            -0.5 |               2 |
|              35 |       2 |                     1   |                   1   |             0   |               2 |
|              36 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              37 |       2 |                     1   |                   0.5 |            -0.5 |               2 |
|              38 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              39 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              40 |       2 |                     1   |                   1   |             0   |               2 |
|              41 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              42 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|              43 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|              44 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              45 |       2 |                     0   |                   0   |             0   |               0 |
|              46 |       2 |                     0   |                   0   |             0   |               0 |
|              47 |       2 |                     0   |                   0   |             0   |               0 |
|              48 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|              49 |       2 |                     0   |                   0   |             0   |               0 |

## Discordant failure transitions

| terminal_outcome   | baseline_failure_type              | method_failure_type                |   pairs |
|:-------------------|:-----------------------------------|:-----------------------------------|--------:|
| rescue             | timeout_no_goal                    | success                            |      16 |
| rescue             | target_drop_candidate              | success                            |       5 |
| harm               | success                            | target_drop_candidate              |       3 |
| rescue             | wrong_object_interaction_candidate | success                            |       3 |
| harm               | success                            | timeout_no_goal                    |       2 |
| harm               | success                            | wrong_object_interaction_candidate |       1 |
| rescue             | kinematic_deadlock_candidate       | success                            |       1 |

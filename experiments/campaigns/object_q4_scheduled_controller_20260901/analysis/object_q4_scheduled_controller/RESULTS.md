# Object task-0 query-4 scheduled controller

- Integrity: **FAIL**.
- Practical gate: **FAIL**.
- Confirmatory gate: **FAIL**.

## Paired terminal endpoint

| subset   |   pairs |   baseline_success_rate |   method_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   mcnemar_pvalue |   adjusted_delta |   baseline_mean_queries |   method_mean_queries |
|:---------|--------:|------------------------:|----------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|-----------------:|-----------------:|------------------------:|----------------------:|
| nominal  |     100 |                   0.46  |                 0.57  |            0.11 |                  -0.01 |                    0.23 |        24 |      13 |        0.0988717 |            0.085 |                   14.66 |                 14.84 |
| strict   |      40 |                   0.375 |                 0.525 |            0.15 |                  -0.05 |                    0.35 |        12 |       6 |        0.237885  |            0.125 |                   15.6  |                 15.65 |

## Prefix integrity

```json
{
  "trace_files": 10,
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
  "strict_prefix_pairs": 40,
  "minimum_strict_prefix_pairs": 95,
  "max_sim_state_difference": 2.553464134235127,
  "max_candidate_value_difference": 0.240545392036438,
  "max_candidate_first_action_difference": 2.0140424966812134,
  "valid": false
}
```

## Init-state diagnostics

|   init_state_id |   pairs |   baseline_success_rate |   method_success_rate |   success_delta |   strict_prefix |
|----------------:|--------:|------------------------:|----------------------:|----------------:|----------------:|
|               0 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|               1 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|               2 |       2 |                     1   |                   1   |             0   |               0 |
|               3 |       2 |                     1   |                   0.5 |            -0.5 |               0 |
|               4 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|               5 |       2 |                     0   |                   0   |             0   |               0 |
|               6 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|               7 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|               8 |       2 |                     1   |                   1   |             0   |               0 |
|               9 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|              10 |       2 |                     1   |                   0.5 |            -0.5 |               0 |
|              11 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              12 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              13 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|              14 |       2 |                     0   |                   0   |             0   |               0 |
|              15 |       2 |                     1   |                   0.5 |            -0.5 |               0 |
|              16 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              17 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|              18 |       2 |                     0   |                   1   |             1   |               0 |
|              19 |       2 |                     0   |                   0   |             0   |               0 |
|              20 |       2 |                     1   |                   1   |             0   |               0 |
|              21 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              22 |       2 |                     1   |                   1   |             0   |               0 |
|              23 |       2 |                     0.5 |                   1   |             0.5 |               0 |
|              24 |       2 |                     0.5 |                   0.5 |             0   |               0 |
|              25 |       2 |                     0.5 |                   0   |            -0.5 |               0 |
|              26 |       2 |                     1   |                   1   |             0   |               0 |
|              27 |       2 |                     0   |                   0.5 |             0.5 |               0 |
|              28 |       2 |                     1   |                   1   |             0   |               0 |
|              29 |       2 |                     0   |                   0   |             0   |               0 |
|              30 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              31 |       2 |                     0   |                   1   |             1   |               2 |
|              32 |       2 |                     1   |                   0   |            -1   |               2 |
|              33 |       2 |                     0.5 |                   1   |             0.5 |               2 |
|              34 |       2 |                     1   |                   1   |             0   |               2 |
|              35 |       2 |                     1   |                   1   |             0   |               2 |
|              36 |       2 |                     0   |                   0   |             0   |               2 |
|              37 |       2 |                     0   |                   1   |             1   |               2 |
|              38 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              39 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              40 |       2 |                     1   |                   1   |             0   |               2 |
|              41 |       2 |                     0   |                   0   |             0   |               2 |
|              42 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              43 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              44 |       2 |                     0.5 |                   0   |            -0.5 |               2 |
|              45 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              46 |       2 |                     0.5 |                   0.5 |             0   |               2 |
|              47 |       2 |                     0   |                   0   |             0   |               2 |
|              48 |       2 |                     0   |                   0.5 |             0.5 |               2 |
|              49 |       2 |                     0.5 |                   0.5 |             0   |               2 |

## Discordant failure transitions

| terminal_outcome   | baseline_failure_type        | method_failure_type                |   pairs |
|:-------------------|:-----------------------------|:-----------------------------------|--------:|
| rescue             | timeout_no_goal              | success                            |      15 |
| harm               | success                      | timeout_no_goal                    |      10 |
| rescue             | target_drop_candidate        | success                            |       6 |
| rescue             | kinematic_deadlock_candidate | success                            |       3 |
| harm               | success                      | kinematic_deadlock_candidate       |       1 |
| harm               | success                      | target_drop_candidate              |       1 |
| harm               | success                      | wrong_object_interaction_candidate |       1 |

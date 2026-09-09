# Object query-4 Position direction holdout

- Integrity: **PASS**.
- Primary efficacy: **FAIL**.
- Direction interaction: **FAIL**.
- Decision: `do_not_promote_fixed_cross_factor_feedback`.

## Strict condition results

| condition_id        | factor   | perturbation   |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:--------------------|:---------|:---------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| position_x0p2_task0 | Position | x0.2           |       60 |                   30 |            0.1      |                0.116667 |       0.0166667 |               0        |                0.05     |         1 |       0 |             1 |          0.0166667 |              6 |          53 |             0.025 |                     -0.00833333 |                    1 |                        60 |
| position_y0p2_task0 | Position | y0.2           |       60 |                   30 |            0.533333 |                0.55     |       0.0166667 |              -0.133333 |                0.166667 |        10 |       9 |             1 |          0.316667  |             23 |          18 |             0.025 |                     -0.00833333 |                    1 |                        60 |

## All-pair sensitivity

| condition_id        | factor   | perturbation   |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:--------------------|:---------|:---------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| position_x0p2_task0 | Position | x0.2           |       60 |                   30 |            0.1      |                0.116667 |       0.0166667 |               0        |                0.05     |         1 |       0 |             1 |          0.0166667 |              6 |          53 |             0.025 |                     -0.00833333 |                    1 |                        60 |
| position_y0p2_task0 | Position | y0.2           |       60 |                   30 |            0.533333 |                0.55     |       0.0166667 |              -0.133333 |                0.166667 |        10 |       9 |             1 |          0.316667  |             23 |          18 |             0.025 |                     -0.00833333 |                    1 |                        60 |

## Interaction

```json
{
  "shared_init_clusters": 30,
  "primary_delta": 0.016666666666666666,
  "control_delta": 0.016666666666666666,
  "interaction_delta": 0.0,
  "interaction_ci_low": -0.13333333333333333,
  "interaction_ci_high": 0.13333333333333333
}
```

## Failure transitions

| condition_id        | terminal_outcome   | open_terminal_failure_type   | feedback_terminal_failure_type   |   pairs |
|:--------------------|:-------------------|:-----------------------------|:---------------------------------|--------:|
| position_x0p2_task0 | rescue             | target_drop_candidate        | success                          |       1 |
| position_y0p2_task0 | rescue             | timeout_no_goal              | success                          |      10 |
| position_y0p2_task0 | harm               | success                      | timeout_no_goal                  |       7 |
| position_y0p2_task0 | harm               | success                      | target_drop_candidate            |       2 |

## Frozen gates

```json
{
  "primary_checks": {
    "integrity": true,
    "cost_adjusted_delta_positive": false,
    "cluster_ci_lower_positive": false,
    "mcnemar_p_below_alpha": false
  },
  "primary_pass": false,
  "interaction_checks": {
    "primary_gate_passed": false,
    "shared_init_clusters_sufficient": true,
    "interaction_ci_lower_positive": false
  },
  "interaction_pass": false,
  "decision": "do_not_promote_fixed_cross_factor_feedback"
}
```

## Integrity

```json
{
  "pairs": 120,
  "target_pairs": 120,
  "expected_keys_match": true,
  "missing_keys": 0,
  "unexpected_keys": 0,
  "duplicate_decision_keys": 0,
  "cases_match": true,
  "query_matches": true,
  "split_matches": true,
  "terminal_labels_complete": true,
  "feedback_paths_valid": 120,
  "candidate_pool_size_valid": true,
  "one_max_value_candidate_per_pool": true,
  "strict_replay_pairs": 120,
  "minimum_strict_replay_pairs": 114,
  "max_replay_state_abs_error": 1.4666512547246125e-14,
  "valid": true,
  "strict_pairs_by_condition": {
    "position_x0p2_task0": 60,
    "position_y0p2_task0": 60
  },
  "minimum_strict_pairs_per_condition": 57,
  "condition_strict_valid": true
}
```

# Initial real-observation re-query: holdout results

## Integrity

- Paired episodes: **60**.
- Query-0 candidate max difference: **1.302e-03**.
- Integrity: **False**.

## Methods

| method              |   episodes |   successes | success_rate   |   mean_queries |   mean_final_t | timeout_rate   | drop_rate   | wrong_object_rate   | safety_violation_rate   |   scheduled_feedback_cost |   utility_c0025 |
|:--------------------|-----------:|------------:|:---------------|---------------:|---------------:|:---------------|:------------|:--------------------|:------------------------|--------------------------:|----------------:|
| maxV-H16            |         60 |          35 | 58.3%          |          12.55 |        192.367 | 41.7%          | 3.3%        | 35.0%               | 0.0%                    |                     0     |        0.583333 |
| maxV-Q0-H8-then-H16 |         60 |          23 | 38.3%          |          14.95 |        227.25  | 61.7%          | 0.0%        | 35.0%               | 0.0%                    |                     0.025 |        0.358333 |

## Paired contrast

|   paired_episodes | delta_success_rate   | delta_ci_low   | delta_ci_high   |   rescues |   harms |   mcnemar_exact_p |
|------------------:|:---------------------|:---------------|:----------------|----------:|--------:|------------------:|
|                60 | -20.0%               | -31.7%         | -6.7%           |         4 |      16 |         0.0118179 |

## Per task

|   task_id |   pairs |   baseline_successes |   method_successes |   delta_success_states |   delta_success_rate |   rescues |   harms |
|----------:|--------:|---------------------:|-------------------:|-----------------------:|---------------------:|----------:|--------:|
|         8 |      30 |                    8 |                  9 |                      1 |            0.0333333 |         2 |       1 |
|         9 |      30 |                   27 |                 14 |                    -13 |           -0.433333  |         2 |      15 |

## Frozen gate

- Overall: **FAIL**.
- `at_least_three_rescues`: PASS
- `rescues_exceed_harms`: FAIL
- `delta_at_least_5pp`: FAIL
- `paired_ci_nonnegative`: FAIL
- `no_task_net_loss`: FAIL
- `compute_adjusted_utility_above_baseline`: FAIL
- `drop_rate_not_increased`: PASS
- `wrong_object_rate_not_increased`: PASS
- `no_added_safety_violation`: PASS
- `integrity_passed`: FAIL

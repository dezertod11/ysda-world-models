# Phase-aware terminal Value of Feedback: transfer results

## Scope

This is a privileged phase-oracle upper bound, not a deployable planner.

## Integrity

- States: **78**; strict: **67**.
- Triggered strict states/groups: **38 / 12**.
- Integrity: **True**.

## Terminal outcomes

| method              |   states |   successes | success_rate   | intervention_rate   |   utility_c0025 | drop_rate   | wrong_object_rate   | safety_violation_rate   |
|:--------------------|---------:|------------:|:---------------|:--------------------|----------------:|:------------|:--------------------|:------------------------|
| commit-H16          |       67 |          58 | 86.6%          | 0.0%                |        0.865672 | 4.5%        | 4.5%                | 0.0%                    |
| always-H8-requery   |       67 |          61 | 91.0%          | 100.0%              |        0.885448 | 3.0%        | 3.0%                | 0.0%                    |
| phase-oracle-H16/H8 |       67 |          58 | 86.6%          | 56.7%               |        0.851493 | 4.5%        | 4.5%                | 0.0%                    |

## Paired contrasts versus commit

| method              |   states | delta_success_rate   | delta_ci_low   | delta_ci_high   |   rescues |   harms |   mcnemar_exact_p |
|:--------------------|---------:|:---------------------|:---------------|:----------------|----------:|--------:|------------------:|
| always-H8-requery   |       67 | 4.5%                 | -2.6%          | 12.3%           |         4 |       1 |             0.375 |
| phase-oracle-H16/H8 |       67 | 0.0%                 | -3.7%          | 3.6%            |         1 |       1 |             1     |

## Per-task route effects

|   task_id |   states |   commit_successes |   route_successes |   delta_success_states |   rescues |   harms |   trigger_rate |   mean_route_dense_delta |
|----------:|---------:|-------------------:|------------------:|-----------------------:|----------:|--------:|---------------:|-------------------------:|
|         5 |       26 |                 26 |                26 |                      0 |         0 |       0 |       0.5      |               0.00441193 |
|         8 |       13 |                  8 |                 9 |                      1 |         1 |       0 |       0.538462 |               0.0177907  |
|         9 |       28 |                 24 |                23 |                     -1 |         0 |       1 |       0.642857 |              -0.0203203  |

## Phase mechanism

| phase     |   states |   independent_groups |   mean_dense_vof |   positive_dense_rate |   terminal_rescues |   terminal_harms |
|:----------|---------:|---------------------:|-----------------:|----------------------:|-------------------:|-----------------:|
| approach  |       29 |                   14 |       -0.0138705 |              0.206897 |                  3 |                0 |
| grasp     |       17 |                   11 |       -0.0397049 |              0.352941 |                  1 |                1 |
| transport |       21 |                   12 |        0.021524  |              0.619048 |                  0 |                0 |

## Dense routing summary

```json
{
  "triggered_states": 38,
  "trigger_rate": 0.5671641791044776,
  "triggered_mean_dense_vof": -0.005867836557326961,
  "triggered_dense_ci_low": -0.04067412303216848,
  "triggered_dense_ci_high": 0.04081465765194989,
  "routed_dense_uplift_per_decision": -0.00332802670415559,
  "always_feedback_dense_uplift_per_decision": -0.009331678972261469,
  "matched_random_expected_dense_uplift": -0.0052925940439691906
}
```

## Frozen gate

- Overall: **FAIL**.
- `at_least_three_terminal_rescues`: FAIL
- `rescues_exceed_harms`: FAIL
- `terminal_delta_at_least_3pp`: FAIL
- `no_task_loses_more_than_one`: PASS
- `triggered_dense_mean_positive`: FAIL
- `triggered_dense_ci_nonnegative`: FAIL
- `route_dense_beats_always_feedback`: PASS
- `compute_adjusted_utility_above_commit`: FAIL
- `no_added_official_safety_violation`: PASS
- `integrity_passed`: PASS

A PASS authorizes an observable phase-detector experiment; a FAIL closes this phase rule.

## Figure

- `phase_vof_terminal_transfer.png`

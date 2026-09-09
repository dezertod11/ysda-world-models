# Real-observation re-query: holdout results

## Integrity

- Paired states: **40**.
- Complete and identical method splits: **True**.
- Adaptive max-value candidate fidelity: **True**.

## Primary result

| method              |   states |   successes | success_rate   | success_ci_low   | success_ci_high   |   mean_queries |   mean_query_multiplier |   mean_final_t | timeout_rate   | drop_rate   |   wrong_object_rate |   safety_violation_rate |   requery_count |
|:--------------------|---------:|------------:|:---------------|:-----------------|:------------------|---------------:|------------------------:|---------------:|:---------------|:------------|--------------------:|------------------------:|----------------:|
| maxV-H16            |       40 |           8 | 20.0%          | 12.5%            | 27.5%             |          17.1  |                 1       |        265.3   | 80.0%          | 0.0%        |               0.15  |                       0 |               0 |
| maxV-H8             |       40 |           8 | 20.0%          | 12.5%            | 27.5%             |          33.15 |                 1.9478  |        264.45  | 80.0%          | 2.5%        |               0.125 |                       0 |               0 |
| maxV-gripper-H8/H16 |       40 |           9 | 22.5%          | 12.5%            | 35.0%             |          24.1  |                 1.43719 |        258.175 | 77.5%          | 0.0%        |               0.25  |                       0 |             626 |

## Factor results

| factor      | method              |   states |   successes | success_rate   | success_ci_low   | success_ci_high   |   mean_queries |   mean_query_multiplier |   requery_count |
|:------------|:--------------------|---------:|------------:|:---------------|:-----------------|:------------------|---------------:|------------------------:|----------------:|
| Object      | maxV-H16            |       10 |           7 | 70.0%          | 40.0%            | 100.0%            |          14.5  |                 1       |               0 |
| Object      | maxV-H8             |       10 |           7 | 70.0%          | 40.0%            | 100.0%            |          28.5  |                 1.9523  |               0 |
| Object      | maxV-gripper-H8/H16 |       10 |           4 | 40.0%          | 10.0%            | 70.0%             |          20.2  |                 1.35913 |             119 |
| Position    | maxV-H16            |       10 |           1 | 10.0%          | 0.0%             | 30.0%             |          17.9  |                 1       |               0 |
| Position    | maxV-H8             |       10 |           0 | 0.0%           | 0.0%             | 0.0%              |          35    |                 1.94444 |               0 |
| Position    | maxV-gripper-H8/H16 |       10 |           4 | 40.0%          | 10.0%            | 70.0%             |          21.2  |                 1.28104 |              97 |
| Environment | maxV-H16            |       20 |           0 | 0.0%           | 0.0%             | 0.0%              |          18    |                 1       |               0 |
| Environment | maxV-H8             |       20 |           1 | 5.0%           | 0.0%             | 15.0%             |          34.55 |                 1.94722 |               0 |
| Environment | maxV-gripper-H8/H16 |       20 |           1 | 5.0%           | 0.0%             | 15.0%             |          27.5  |                 1.55429 |             410 |

## Paired contrasts versus maxV-H16

| method              |   paired_states | delta_success_rate   | delta_ci_low   | delta_ci_high   |   rescues |   harms |   mcnemar_exact_p |
|:--------------------|----------------:|:---------------------|:---------------|:----------------|----------:|--------:|------------------:|
| maxV-H8             |              40 | 0.0%                 | -12.5%         | 12.5%           |         3 |       3 |                 1 |
| maxV-gripper-H8/H16 |              40 | 2.5%                 | -12.5%         | 17.5%           |         6 |       5 |                 1 |

## Per-factor paired deltas

| factor      | method              |   states |   delta_success_states |   delta_success_rate |   rescues |   harms |
|:------------|:--------------------|---------:|-----------------------:|---------------------:|----------:|--------:|
| Object      | maxV-H8             |       10 |                      0 |                 0    |         2 |       2 |
| Object      | maxV-gripper-H8/H16 |       10 |                     -3 |                -0.3  |         2 |       5 |
| Position    | maxV-H8             |       10 |                     -1 |                -0.1  |         0 |       1 |
| Position    | maxV-gripper-H8/H16 |       10 |                      3 |                 0.3  |         3 |       0 |
| Environment | maxV-H8             |       20 |                      1 |                 0.05 |         1 |       0 |
| Environment | maxV-gripper-H8/H16 |       20 |                      1 |                 0.05 |         1 |       0 |

## Compute-adjusted utility

|   query_cost | method              |   mean_utility |
|-------------:|:--------------------|---------------:|
|        0.01  | maxV-H16            |       0.2      |
|        0.01  | maxV-H8             |       0.190522 |
|        0.01  | maxV-gripper-H8/H16 |       0.220628 |
|        0.025 | maxV-H16            |       0.2      |
|        0.025 | maxV-H8             |       0.176305 |
|        0.025 | maxV-gripper-H8/H16 |       0.21407  |
|        0.05  | maxV-H16            |       0.2      |
|        0.05  | maxV-H8             |       0.15261  |
|        0.05  | maxV-gripper-H8/H16 |       0.203141 |

## Preregistered gates

- Adaptive gate: **FAIL**.
- `at_least_two_rescues`: PASS
- `rescues_exceed_harms`: PASS
- `pooled_sr_not_lower`: PASS
- `no_factor_loses_more_than_one`: FAIL
- `query_multiplier_20pct_below_fixed_h8`: PASS
- `utility_0025_above_h16`: PASS
- Fixed H8 mechanism: **NOT SUPPORTED**.

## Decision rule

A failed adaptive gate closes this exact gripper-transition controller; the holdout is not used for threshold tuning. Fixed H8 is a causal feedback control and is interpreted jointly with its query multiplier.

## Figures

- `success_compute_comparison.png`
- `paired_outcome_matrix.png`

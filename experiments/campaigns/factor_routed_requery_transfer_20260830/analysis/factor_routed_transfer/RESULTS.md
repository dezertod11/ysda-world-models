# Factor-routed real-observation re-query: transfer results

## Integrity

- Complete paired states: **90**.
- Frozen integrity: **True**.
- Adaptive max-value fidelity: **True**.

## Primary result

| method                     |   states |   successes | success_rate   | success_ci_low   | success_ci_high   |   mean_queries |   mean_query_multiplier | timeout_rate   |   drop_rate |   wrong_object_rate |   safety_violation_rate |
|:---------------------------|---------:|------------:|:---------------|:-----------------|:------------------|---------------:|------------------------:|:---------------|------------:|--------------------:|------------------------:|
| maxV-H16                   |       90 |          53 | 58.9%          | 52.2%            | 65.6%             |        12.8444 |                 1       | 41.1%          |   0.0111111 |            0.111111 |                       0 |
| maxV-gripper-H8/H16        |       90 |          48 | 53.3%          | 46.7%            | 60.0%             |        17.0222 |                 1.26427 | 46.7%          |   0.1       |            0.177778 |                       0 |
| factor-routed-H16/adaptive |       90 |          47 | 52.2%          | 45.6%            | 58.9%             |        16.5889 |                 1.19973 | 47.8%          |   0.1       |            0.177778 |                       0 |

## Factor results

| factor      | method                     |   states |   successes | success_rate   | success_ci_low   | success_ci_high   |   mean_query_multiplier |
|:------------|:---------------------------|---------:|------------:|:---------------|:-----------------|:------------------|------------------------:|
| Object      | maxV-H16                   |       30 |          28 | 93.3%          | 83.3%            | 100.0%            |                 1       |
| Object      | maxV-gripper-H8/H16        |       30 |          29 | 96.7%          | 90.0%            | 100.0%            |                 1.19361 |
| Object      | factor-routed-H16/adaptive |       30 |          28 | 93.3%          | 83.3%            | 100.0%            |                 1       |
| Position    | maxV-H16                   |       30 |           3 | 10.0%          | 0.0%             | 23.3%             |                 1       |
| Position    | maxV-gripper-H8/H16        |       30 |           1 | 3.3%           | 0.0%             | 10.0%             |                 1.3265  |
| Position    | factor-routed-H16/adaptive |       30 |           1 | 3.3%           | 0.0%             | 10.0%             |                 1.3265  |
| Environment | maxV-H16                   |       30 |          22 | 73.3%          | 56.7%            | 86.7%             |                 1       |
| Environment | maxV-gripper-H8/H16        |       30 |          18 | 60.0%          | 43.3%            | 76.7%             |                 1.27271 |
| Environment | factor-routed-H16/adaptive |       30 |          18 | 60.0%          | 43.3%            | 76.7%             |                 1.27271 |

## Paired contrasts versus H16

| method                     |   paired_states | delta_success_rate   | delta_ci_low   | delta_ci_high   |   rescues |   harms |   mcnemar_exact_p |
|:---------------------------|----------------:|:---------------------|:---------------|:----------------|----------:|--------:|------------------:|
| maxV-gripper-H8/H16        |              90 | -5.6%                | -12.2%         | 1.1%            |         3 |       8 |          0.226562 |
| factor-routed-H16/adaptive |              90 | -6.7%                | -13.3%         | 0.0%            |         2 |       8 |          0.109375 |

## Factor contrasts

| factor      | method                     |   states |   delta_success_states |   delta_success_rate |   rescues |   harms |
|:------------|:---------------------------|---------:|-----------------------:|---------------------:|----------:|--------:|
| Object      | maxV-gripper-H8/H16        |       30 |                      1 |            0.0333333 |         1 |       0 |
| Position    | maxV-gripper-H8/H16        |       30 |                     -2 |           -0.0666667 |         1 |       3 |
| Environment | maxV-gripper-H8/H16        |       30 |                     -4 |           -0.133333  |         1 |       5 |
| Object      | factor-routed-H16/adaptive |       30 |                      0 |            0         |         0 |       0 |
| Position    | factor-routed-H16/adaptive |       30 |                     -2 |           -0.0666667 |         1 |       3 |
| Environment | factor-routed-H16/adaptive |       30 |                     -4 |           -0.133333  |         1 |       5 |

## Compute-adjusted utility

|   query_cost | method                     |   mean_utility |
|-------------:|:---------------------------|---------------:|
|        0.01  | maxV-H16                   |       0.588889 |
|        0.01  | maxV-gripper-H8/H16        |       0.530691 |
|        0.01  | factor-routed-H16/adaptive |       0.520225 |
|        0.025 | maxV-H16                   |       0.588889 |
|        0.025 | maxV-gripper-H8/H16        |       0.526727 |
|        0.025 | factor-routed-H16/adaptive |       0.517229 |
|        0.05  | maxV-H16                   |       0.588889 |
|        0.05  | maxV-gripper-H8/H16        |       0.52012  |
|        0.05  | factor-routed-H16/adaptive |       0.512236 |

## Preregistered gate

- Overall: **FAIL**.
- `at_least_five_rescues`: FAIL
- `rescues_exceed_harms`: FAIL
- `pooled_delta_at_least_5pp`: FAIL
- `position_delta_nonnegative`: FAIL
- `environment_delta_nonnegative`: FAIL
- `query_multiplier_at_most_1p5`: PASS
- `utility_0025_above_h16`: FAIL
- `integrity_passed`: PASS

A failed gate closes this exact factor router. No task-specific exceptions are fitted on this transfer split.

## Figures

- `route_success_compute.png`
- `route_paired_outcomes.png`

# P3 recovery-proposal opportunity results

## Decision

**develop_perception_backed_regrasp_then_test_reserve**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

| proposal              | deployable   |   successes |   n_states |   success_rate |   success_ci_low |   success_ci_high |   rescued_cells |   rescued_tasks |   drop_rate |   wrong_rate |   mean_queries | gate_passed   |
|:----------------------|:-------------|------------:|-----------:|---------------:|-----------------:|------------------:|----------------:|----------------:|------------:|-------------:|---------------:|:--------------|
| lift_hold_h8          | True         |           8 |         80 |         0.1    |        0.0375    |          0.164557 |               5 |               4 |      0.1375 |       0.1375 |        25.5    | False         |
| frequent_requery_h4   | True         |           7 |         80 |         0.0875 |        0.0365854 |          0.151899 |               2 |               2 |      0.0625 |       0.05   |        51.0875 | False         |
| privileged_regrasp_h8 | False        |          62 |         80 |         0.775  |        0.683544  |          0.864198 |               8 |               5 |      0.0625 |       0.075  |        15.5    | False         |

## Oracle coverage

- Deployable proposal oracle: **11/80 = 13.8%** (cluster-bootstrap 95% CI 6.3% to 21.5%).
- All-proposal oracle, including privileged regrasp: **62/80 = 77.5%** (95% CI 67.9% to 86.2%).
- Passing deployable proposals: `[]`.

## Per-cell results

| proposal              | position_level   |   task_id |   n_states |   successes |   success_rate |   drop_rate |   wrong_rate |   safety_rate |   mean_queries |
|:----------------------|:-----------------|----------:|-----------:|------------:|---------------:|------------:|-------------:|--------------:|---------------:|
| frequent_requery_h4   | x0.2             |         5 |         10 |           6 |            0.6 |         0.2 |          0.1 |             0 |           46.4 |
| frequent_requery_h4   | x0.2             |         6 |         10 |           0 |            0   |         0.2 |          0.1 |             0 |           52   |
| frequent_requery_h4   | x0.2             |         9 |         10 |           0 |            0   |         0.1 |          0.1 |             0 |           52   |
| frequent_requery_h4   | y0.2             |         4 |         10 |           0 |            0   |         0   |          0   |             0 |           52   |
| frequent_requery_h4   | y0.2             |         6 |         10 |           0 |            0   |         0   |          0   |             0 |           52   |
| frequent_requery_h4   | y0.2             |         9 |         10 |           0 |            0   |         0   |          0   |             0 |           52   |
| frequent_requery_h4   | y0.3             |         1 |         10 |           1 |            0.1 |         0   |          0   |             0 |           50.3 |
| frequent_requery_h4   | y0.3             |         5 |         10 |           0 |            0   |         0   |          0.1 |             0 |           52   |
| lift_hold_h8          | x0.2             |         5 |         10 |           4 |            0.4 |         0.6 |          0   |             0 |           24   |
| lift_hold_h8          | x0.2             |         6 |         10 |           1 |            0.1 |         0.3 |          0.1 |             0 |           25.5 |
| lift_hold_h8          | x0.2             |         9 |         10 |           0 |            0   |         0   |          0   |             0 |           26   |
| lift_hold_h8          | y0.2             |         4 |         10 |           0 |            0   |         0   |          0   |             0 |           26   |
| lift_hold_h8          | y0.2             |         6 |         10 |           1 |            0.1 |         0.1 |          0   |             0 |           25.5 |
| lift_hold_h8          | y0.2             |         9 |         10 |           1 |            0.1 |         0.1 |          0.1 |             0 |           25.9 |
| lift_hold_h8          | y0.3             |         1 |         10 |           1 |            0.1 |         0   |          0.5 |             0 |           25.1 |
| lift_hold_h8          | y0.3             |         5 |         10 |           0 |            0   |         0   |          0.4 |             0 |           26   |
| privileged_regrasp_h8 | x0.2             |         5 |         10 |           8 |            0.8 |         0.2 |          0   |             0 |           16.1 |
| privileged_regrasp_h8 | x0.2             |         6 |         10 |          10 |            1   |         0.1 |          0   |             0 |           15.1 |
| privileged_regrasp_h8 | x0.2             |         9 |         10 |           9 |            0.9 |         0.1 |          0   |             0 |           15.1 |
| privileged_regrasp_h8 | y0.2             |         4 |         10 |           1 |            0.1 |         0.1 |          0.1 |             0 |           22.5 |
| privileged_regrasp_h8 | y0.2             |         6 |         10 |          10 |            1   |         0   |          0   |             0 |           11.9 |
| privileged_regrasp_h8 | y0.2             |         9 |         10 |          10 |            1   |         0   |          0   |             0 |           10.4 |
| privileged_regrasp_h8 | y0.3             |         1 |         10 |          10 |            1   |         0   |          0   |             0 |           12.7 |
| privileged_regrasp_h8 | y0.3             |         5 |         10 |           4 |            0.4 |         0   |          0.5 |             0 |           20.2 |

## Query-level descriptive signals

These are post-branch descriptive associations, not a trained or validated
selector. `failure_auc` uses a larger metric value as evidence for eventual
failure; values near 0.5 are uninformative and values below 0.5 reverse sign.
The `mean` and `max` aggregations include observations collected after the
proposal has already changed the trajectory. They are confounded by proposal
family, query timing and episode length, so even a high pooled AUC must not be
reported as a pre-intervention failure predictor.

| metric                                             | aggregation   |   n |   success_mean |   fail_mean |   failure_auc |   failure_auc_strength |
|:---------------------------------------------------|:--------------|----:|---------------:|------------:|--------------:|-----------------------:|
| candidate_value_internal_consistency_mean          | max           | 240 |     0.00837935 |  0.0168099  |      0.919369 |               0.419369 |
| candidate_value_internal_consistency_mean          | mean          | 240 |     0.007345   |  0.00918637 |      0.913792 |               0.413792 |
| candidate_action_chunk_consistency_mean            | max           | 240 |     0.0091407  |  0.0111819  |      0.881284 |               0.381284 |
| candidate_future_proprio_internal_consistency_mean | mean          | 240 |     0.00794526 |  0.00840892 |      0.845271 |               0.345271 |
| candidate_value_range                              | max           | 240 |     0.0155279  |  0.052265   |      0.842483 |               0.342483 |
| candidate_value_std                                | max           | 240 |     0.00612673 |  0.0201223  |      0.839216 |               0.339216 |
| candidate_value_range                              | mean          | 240 |     0.00312963 |  0.00705526 |      0.818819 |               0.318819 |
| candidate_value_std                                | mean          | 240 |     0.00122935 |  0.00274586 |      0.818182 |               0.318182 |
| candidate_future_proprio_internal_consistency_mean | max           | 240 |     0.00949586 |  0.0112457  |      0.797944 |               0.297944 |
| candidate_future_proprio_across_sample_std_mean    | max           | 240 |     0.00994732 |  0.0251482  |      0.790933 |               0.290933 |
| planning_predicted_proprio_error                   | max           | 240 |     0.15241    |  0.227597   |      0.790296 |               0.290296 |
| planning_predicted_proprio_error                   | mean          | 240 |     0.0669538  |  0.07878    |      0.78193  |               0.28193  |
| candidate_action_internal_consistency_mean         | mean          | 240 |     0.0224993  |  0.0236928  |      0.769261 |               0.269261 |
| candidate_action_internal_consistency_mean         | max           | 240 |     0.0315927  |  0.0402703  |      0.766552 |               0.266552 |
| candidate_value_internal_consistency_mean          | first         | 240 |     0.00705328 |  0.00765257 |      0.743447 |               0.243447 |

## Common pre-intervention query

This table uses only the shared query at `t=64`, before the recovery proposal
changes the trajectory. `same_cell_failure_auc` compares only success/failure
pairs from the same frozen `(position level, task)` cell. The collapse of the
three uncertainty AUCs after this control shows that their pooled association
mostly tracks cell difficulty. The value mean remains exploratory and has not
been evaluated on the untouched reserve.

| proposal              | metric                                    |   n |   successes |   failures |   success_mean |   fail_mean |   pooled_failure_auc |   same_cell_failure_auc |   comparable_cells |   comparable_pairs |   pooled_auc_strength |
|:----------------------|:------------------------------------------|----:|------------:|-----------:|---------------:|------------:|---------------------:|------------------------:|-------------------:|-------------------:|----------------------:|
| privileged_regrasp_h8 | candidate_value_internal_consistency_mean |  80 |          62 |         18 |     0.00777761 |  0.00881328 |             0.793907 |                0.465517 |                  4 |                 58 |              0.293907 |
| privileged_regrasp_h8 | candidate_value_range                     |  80 |          62 |         18 |     0.00518843 |  0.0134574  |             0.750896 |                0.465517 |                  4 |                 58 |              0.250896 |
| privileged_regrasp_h8 | candidate_value_std                       |  80 |          62 |         18 |     0.0020293  |  0.00512841 |             0.749104 |                0.448276 |                  4 |                 58 |              0.249104 |
| privileged_regrasp_h8 | candidate_value_mean                      |  80 |          62 |         18 |     0.378322   |  0.430418   |             0.705197 |                0.793103 |                  4 |                 58 |              0.205197 |

## Artifacts

- `recovery_proposal_summary.csv`: primary proposal table and frozen gates.
- `recovery_cell_summary.csv`: eight-cell breakdown.
- `oracle_summary.json`: deployable and diagnostic oracle coverage.
- `query_metric_separation.csv`: descriptive uncertainty associations.
- `pre_intervention_metric_separation.csv`: pooled and same-cell source-query associations.
- `recovery_opportunity.png`: SR, side effects and cell heatmap.
- `video_index.html`: all proposals aligned by exact starting snapshot.

The privileged regrasp branch uses true simulator object position and must not
be reported as a deployable method.

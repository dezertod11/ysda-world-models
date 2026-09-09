# P3 recovery-proposal opportunity results

## Decision

**advance_fixed_proposal_to_untouched_reserve**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

| proposal              | deployable   |   successes |   n_states |   success_rate |   success_ci_low |   success_ci_high |   rescued_cells |   rescued_tasks |   drop_rate |   wrong_rate |   mean_queries | gate_passed   |
|:----------------------|:-------------|------------:|-----------:|---------------:|-----------------:|------------------:|----------------:|----------------:|------------:|-------------:|---------------:|:--------------|
| perception_regrasp_h8 | True         |          49 |         80 |         0.6125 |         0.506173 |           0.71433 |               6 |               4 |        0.05 |       0.2125 |        16.3125 | True          |

## Oracle coverage

- Deployable proposal oracle: **49/80 = 61.3%** (cluster-bootstrap 95% CI 50.6% to 71.6%).
- All-proposal oracle, including privileged regrasp: **49/80 = 61.3%** (95% CI 50.0% to 72.0%).
- Passing deployable proposals: `['perception_regrasp_h8']`.

## Per-cell results

| proposal              | position_level   |   task_id |   n_states |   successes |   success_rate |   drop_rate |   wrong_rate |   safety_rate |   mean_queries |
|:----------------------|:-----------------|----------:|-----------:|------------:|---------------:|------------:|-------------:|--------------:|---------------:|
| perception_regrasp_h8 | x0.2             |         5 |         10 |           8 |            0.8 |         0.1 |          0.1 |             0 |           11.1 |
| perception_regrasp_h8 | x0.2             |         6 |         10 |           9 |            0.9 |         0.2 |          0   |             0 |           16.3 |
| perception_regrasp_h8 | x0.2             |         9 |         10 |           0 |            0   |         0.1 |          0.6 |             0 |           23   |
| perception_regrasp_h8 | y0.2             |         4 |         10 |           0 |            0   |         0   |          0.9 |             0 |           23   |
| perception_regrasp_h8 | y0.2             |         6 |         10 |          10 |            1   |         0   |          0   |             0 |           11.7 |
| perception_regrasp_h8 | y0.2             |         9 |         10 |           8 |            0.8 |         0   |          0   |             0 |           12   |
| perception_regrasp_h8 | y0.3             |         1 |         10 |          10 |            1   |         0   |          0   |             0 |           12.8 |
| perception_regrasp_h8 | y0.3             |         5 |         10 |           4 |            0.4 |         0   |          0.1 |             0 |           20.6 |

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
| candidate_value_range                              | first         |  80 |    0.00162604  |  0.0102502  |      0.96445  |               0.46445  |
| candidate_value_std                                | first         |  80 |    0.000633254 |  0.00406103 |      0.958525 |               0.458525 |
| candidate_value_internal_consistency_mean          | mean          |  80 |    0.0072897   |  0.00825343 |      0.884793 |               0.384793 |
| candidate_value_internal_consistency_mean          | first         |  80 |    0.00700122  |  0.00868585 |      0.879526 |               0.379526 |
| planning_predicted_proprio_error                   | first         |  80 |    0.0525753   |  0.0993596  |      0.869651 |               0.369651 |
| candidate_future_proprio_internal_consistency_mean | mean          |  80 |    0.00775727  |  0.00805687 |      0.841343 |               0.341343 |
| candidate_future_proprio_across_sample_std_mean    | first         |  80 |    0.00167806  |  0.0050046  |      0.835418 |               0.335418 |
| candidate_future_proprio_internal_consistency_mean | max           |  80 |    0.00871409  |  0.00995683 |      0.825543 |               0.325543 |
| candidate_value_internal_consistency_mean          | max           |  80 |    0.00817133  |  0.0119444  |      0.823568 |               0.323568 |
| candidate_value_range                              | max           |  80 |    0.0153303   |  0.0531306  |      0.801843 |               0.301843 |
| candidate_future_proprio_across_sample_std_mean    | max           |  80 |    0.00824476  |  0.015695   |      0.798552 |               0.298552 |
| candidate_value_std                                | max           |  80 |    0.00608619  |  0.0211965  |      0.798552 |               0.298552 |
| planning_predicted_proprio_error                   | max           |  80 |    0.112502    |  0.155041   |      0.791968 |               0.291968 |
| candidate_future_proprio_internal_consistency_mean | first         |  80 |    0.00837289  |  0.00948944 |      0.78341  |               0.28341  |
| candidate_value_std                                | mean          |  80 |    0.0012018   |  0.002711   |      0.75181  |               0.25181  |

## Common pre-intervention query

This table uses only the shared query at `t=64`, before the recovery proposal
changes the trajectory. `same_cell_failure_auc` compares only success/failure
pairs from the same frozen `(position level, task)` cell. The collapse of the
three uncertainty AUCs after this control shows that their pooled association
mostly tracks cell difficulty. The value mean remains exploratory and has not
been evaluated on the untouched reserve.

_No rows._

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

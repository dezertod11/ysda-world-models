# P3 recovery-proposal opportunity results

## Decision

**freeze_rule_based_proposal_router_before_reserve**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

| proposal              | deployable   |   successes |   n_states |   success_rate |   success_ci_low |   success_ci_high |   rescued_cells |   rescued_tasks |   drop_rate |   wrong_rate |   mean_queries | gate_passed   |
|:----------------------|:-------------|------------:|-----------:|---------------:|-----------------:|------------------:|----------------:|----------------:|------------:|-------------:|---------------:|:--------------|
| perception_regrasp_h8 | True         |          43 |         72 |       0.597222 |         0.454545 |           0.73913 |              11 |               8 |   0.0277778 |     0.291667 |        16.3889 | False         |

## Oracle coverage

- Deployable proposal oracle: **43/72 = 59.7%** (cluster-bootstrap 95% CI 45.6% to 73.5%).
- All-proposal oracle, including privileged regrasp: **43/72 = 59.7%** (95% CI 45.3% to 73.7%).
- Passing deployable proposals: `[]`.

## Per-cell results

| proposal              | position_level   |   task_id |   n_states |   successes |   success_rate |   drop_rate |   wrong_rate |   safety_rate |   mean_queries |
|:----------------------|:-----------------|----------:|-----------:|------------:|---------------:|------------:|-------------:|--------------:|---------------:|
| perception_regrasp_h8 | x0.2             |         2 |          5 |           1 |       0.2      |    0.2      |     0        |             0 |        22      |
| perception_regrasp_h8 | x0.2             |         9 |          4 |           0 |       0        |    0        |     0.75     |             0 |        23      |
| perception_regrasp_h8 | y0.1             |         4 |          3 |           1 |       0.333333 |    0.333333 |     0.666667 |             0 |        20.3333 |
| perception_regrasp_h8 | y0.1             |         6 |          1 |           1 |       1        |    0        |     0        |             0 |        13      |
| perception_regrasp_h8 | y0.1             |         8 |          2 |           2 |       1        |    0        |     0        |             0 |        12      |
| perception_regrasp_h8 | y0.1             |         9 |          5 |           5 |       1        |    0        |     0        |             0 |         5.8    |
| perception_regrasp_h8 | y0.2             |         4 |         14 |           0 |       0        |    0        |     1        |             0 |        23      |
| perception_regrasp_h8 | y0.2             |         6 |         15 |          15 |       1        |    0        |     0        |             0 |        11.5333 |
| perception_regrasp_h8 | y0.2             |         7 |          1 |           1 |       1        |    0        |     0        |             0 |        15      |
| perception_regrasp_h8 | y0.2             |         8 |          3 |           3 |       1        |    0        |     0        |             0 |        12.3333 |
| perception_regrasp_h8 | y0.2             |         9 |          8 |           6 |       0.75     |    0        |     0        |             0 |        13.5    |
| perception_regrasp_h8 | y0.3             |         1 |          5 |           5 |       1        |    0        |     0        |             0 |        14.2    |
| perception_regrasp_h8 | y0.3             |         5 |          6 |           3 |       0.5      |    0        |     0.333333 |             0 |        20.8333 |

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
| candidate_value_internal_consistency_mean          | mean          |  72 |    0.00724663  |  0.00789836 |      0.959904 |               0.459904 |
| candidate_value_internal_consistency_mean          | max           |  72 |    0.00810582  |  0.0112533  |      0.923817 |               0.423817 |
| candidate_value_range                              | first         |  72 |    0.00249034  |  0.00887234 |      0.886127 |               0.386127 |
| candidate_value_std                                | first         |  72 |    0.000976527 |  0.00342006 |      0.883721 |               0.383721 |
| candidate_value_range                              | max           |  72 |    0.0103383   |  0.0315357  |      0.867682 |               0.367682 |
| candidate_value_range                              | mean          |  72 |    0.00231389  |  0.00503714 |      0.867682 |               0.367682 |
| candidate_value_std                                | mean          |  72 |    0.00092145  |  0.00198549 |      0.860465 |               0.360465 |
| candidate_value_std                                | max           |  72 |    0.00422145  |  0.0125364  |      0.847634 |               0.347634 |
| candidate_value_internal_consistency_mean          | first         |  72 |    0.00703568  |  0.00923476 |      0.846832 |               0.346832 |
| candidate_future_proprio_internal_consistency_mean | mean          |  72 |    0.00768312  |  0.00795545 |      0.834002 |               0.334002 |
| candidate_action_internal_consistency_mean         | first         |  72 |    0.0226258   |  0.0261679  |      0.78749  |               0.28749  |
| planning_predicted_proprio_error                   | first         |  72 |    0.0617779   |  0.0867949  |      0.761828 |               0.261828 |
| candidate_value_mean                               | max           |  72 |    0.99228     |  0.857052   |      0.251403 |               0.248597 |
| candidate_action_chunk_consistency_mean            | first         |  72 |    0.00817205  |  0.00878869 |      0.735365 |               0.235365 |
| candidate_value_mean                               | first         |  72 |    0.449279    |  0.488417   |      0.730553 |               0.230553 |

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

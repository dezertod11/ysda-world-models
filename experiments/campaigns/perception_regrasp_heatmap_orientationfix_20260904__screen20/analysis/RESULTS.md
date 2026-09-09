# P3 recovery-proposal opportunity results

## Decision

**freeze_rule_based_proposal_router_before_reserve**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

| proposal              | deployable   |   successes |   n_states |   success_rate |   success_ci_low |   success_ci_high |   rescued_cells |   rescued_tasks |   drop_rate |   wrong_rate |   mean_queries | gate_passed   |
|:----------------------|:-------------|------------:|-----------:|---------------:|-----------------:|------------------:|----------------:|----------------:|------------:|-------------:|---------------:|:--------------|
| perception_regrasp_h8 | True         |          11 |         20 |           0.55 |             0.35 |              0.75 |               6 |               4 |           0 |          0.2 |           16.6 | False         |

## Oracle coverage

- Deployable proposal oracle: **11/20 = 55.0%** (cluster-bootstrap 95% CI 35.0% to 75.0%).
- All-proposal oracle, including privileged regrasp: **11/20 = 55.0%** (95% CI 35.0% to 75.0%).
- Passing deployable proposals: `[]`.

## Per-cell results

| proposal              | position_level   |   task_id |   n_states |   successes |   success_rate |   drop_rate |   wrong_rate |   safety_rate |   mean_queries |
|:----------------------|:-----------------|----------:|-----------:|------------:|---------------:|------------:|-------------:|--------------:|---------------:|
| perception_regrasp_h8 | x0.2             |         5 |          3 |           2 |       0.666667 |           0 |     0        |             0 |           13   |
| perception_regrasp_h8 | x0.2             |         6 |          3 |           3 |       1        |           0 |     0        |             0 |           15   |
| perception_regrasp_h8 | x0.2             |         9 |          3 |           0 |       0        |           0 |     0.666667 |             0 |           23   |
| perception_regrasp_h8 | y0.2             |         4 |          3 |           0 |       0        |           0 |     0.333333 |             0 |           23   |
| perception_regrasp_h8 | y0.2             |         6 |          2 |           2 |       1        |           0 |     0        |             0 |           11.5 |
| perception_regrasp_h8 | y0.2             |         9 |          2 |           1 |       0.5      |           0 |     0        |             0 |           16   |
| perception_regrasp_h8 | y0.3             |         1 |          2 |           2 |       1        |           0 |     0        |             0 |           11   |
| perception_regrasp_h8 | y0.3             |         5 |          2 |           1 |       0.5      |           0 |     0.5      |             0 |           16.5 |

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
| candidate_value_std                                | first         |  20 |    0.000580641 |  0.00409115 |      0.949495 |               0.449495 |
| candidate_value_range                              | first         |  20 |    0.00151243  |  0.0101151  |      0.939394 |               0.439394 |
| candidate_future_proprio_internal_consistency_mean | mean          |  20 |    0.00776832  |  0.00810511 |      0.868687 |               0.368687 |
| candidate_value_internal_consistency_mean          | mean          |  20 |    0.00726461  |  0.00798864 |      0.858586 |               0.358586 |
| candidate_value_internal_consistency_mean          | max           |  20 |    0.00812417  |  0.0108911  |      0.818182 |               0.318182 |
| candidate_action_chunk_consistency_mean            | max           |  20 |    0.00894888  |  0.00973357 |      0.787879 |               0.287879 |
| candidate_future_proprio_internal_consistency_mean | max           |  20 |    0.00879618  |  0.00988454 |      0.777778 |               0.277778 |
| candidate_action_internal_consistency_mean         | mean          |  20 |    0.0219839   |  0.0226087  |      0.777778 |               0.277778 |
| candidate_future_proprio_internal_consistency_mean | first         |  20 |    0.00842995  |  0.00943412 |      0.777778 |               0.277778 |
| planning_predicted_proprio_error                   | max           |  20 |    0.110671    |  0.155074   |      0.767677 |               0.267677 |
| planning_predicted_proprio_error                   | first         |  20 |    0.0533529   |  0.0988933  |      0.767677 |               0.267677 |
| candidate_future_proprio_across_sample_std_mean    | mean          |  20 |    0.00190587  |  0.0027937  |      0.757576 |               0.257576 |
| candidate_action_chunk_consistency_mean            | mean          |  20 |    0.00801343  |  0.0082645  |      0.747475 |               0.247475 |
| candidate_value_internal_consistency_mean          | first         |  20 |    0.00699038  |  0.00850832 |      0.747475 |               0.247475 |
| candidate_value_range                              | mean          |  20 |    0.00302333  |  0.00496234 |      0.747475 |               0.247475 |

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

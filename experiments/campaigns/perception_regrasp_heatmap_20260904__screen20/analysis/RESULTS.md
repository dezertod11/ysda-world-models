# P3 recovery-proposal opportunity results

## Decision

**deprioritize_recovery_proposals**

The source population contains only exact states where both the original
max-value commit and ordinary 8+8 feedback branch failed. Each success below is
therefore a direct rescue, not an improvement inferred from a surrogate.

## Fixed proposals

| proposal              | deployable   |   successes |   n_states |   success_rate |   success_ci_low |   success_ci_high |   rescued_cells |   rescued_tasks |   drop_rate |   wrong_rate |   mean_queries | gate_passed   |
|:----------------------|:-------------|------------:|-----------:|---------------:|-----------------:|------------------:|----------------:|----------------:|------------:|-------------:|---------------:|:--------------|
| perception_regrasp_h8 | True         |           1 |         20 |           0.05 |                0 |              0.15 |               1 |               1 |        0.05 |         0.55 |          22.95 | False         |

## Oracle coverage

- Deployable proposal oracle: **1/20 = 5.0%** (cluster-bootstrap 95% CI 0.0% to 15.0%).
- All-proposal oracle, including privileged regrasp: **1/20 = 5.0%** (95% CI 0.0% to 15.0%).
- Passing deployable proposals: `[]`.

## Per-cell results

| proposal              | position_level   |   task_id |   n_states |   successes |   success_rate |   drop_rate |   wrong_rate |   safety_rate |   mean_queries |
|:----------------------|:-----------------|----------:|-----------:|------------:|---------------:|------------:|-------------:|--------------:|---------------:|
| perception_regrasp_h8 | x0.2             |         5 |          3 |           0 |       0        |    0.333333 |     0.666667 |             0 |        23      |
| perception_regrasp_h8 | x0.2             |         6 |          3 |           1 |       0.333333 |    0        |     0        |             0 |        22.6667 |
| perception_regrasp_h8 | x0.2             |         9 |          3 |           0 |       0        |    0        |     0.666667 |             0 |        23      |
| perception_regrasp_h8 | y0.2             |         4 |          3 |           0 |       0        |    0        |     1        |             0 |        23      |
| perception_regrasp_h8 | y0.2             |         6 |          2 |           0 |       0        |    0        |     1        |             0 |        23      |
| perception_regrasp_h8 | y0.2             |         9 |          2 |           0 |       0        |    0        |     0        |             0 |        23      |
| perception_regrasp_h8 | y0.3             |         1 |          2 |           0 |       0        |    0        |     0.5      |             0 |        23      |
| perception_regrasp_h8 | y0.3             |         5 |          2 |           0 |       0        |    0        |     0.5      |             0 |        23      |

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
| candidate_value_internal_consistency_mean          | mean          |  20 |    0.00730161  |  0.00822927 |      0.894737 |               0.394737 |
| candidate_future_proprio_across_sample_std_mean    | max           |  20 |    0.0244507   |  0.0177289  |      0.105263 |               0.394737 |
| candidate_future_proprio_internal_consistency_mean | mean          |  20 |    0.00778107  |  0.00845455 |      0.894737 |               0.394737 |
| candidate_action_internal_consistency_mean         | first         |  20 |    0.022771    |  0.0260381  |      0.842105 |               0.342105 |
| candidate_value_std                                | first         |  20 |    0.000415672 |  0.00192149 |      0.842105 |               0.342105 |
| candidate_action_chunk_consistency_mean            | max           |  20 |    0.00881435  |  0.00972424 |      0.842105 |               0.342105 |
| candidate_action_consensus_first_mean              | max           |  20 |    0.0533216   |  0.542981   |      0.842105 |               0.342105 |
| candidate_future_proprio_across_sample_std_mean    | first         |  20 |    0.00112562  |  0.00297543 |      0.789474 |               0.289474 |
| candidate_value_internal_consistency_mean          | first         |  20 |    0.00701709  |  0.00794767 |      0.789474 |               0.289474 |
| candidate_future_proprio_internal_consistency_mean | max           |  20 |    0.00899337  |  0.0109929  |      0.789474 |               0.289474 |
| candidate_value_range                              | first         |  20 |    0.00114703  |  0.00481314 |      0.789474 |               0.289474 |
| candidate_action_consensus_chunk_mean              | first         |  20 |    0.0667082   |  0.411736   |      0.736842 |               0.236842 |
| planning_predicted_proprio_error                   | first         |  20 |    0.0480397   |  0.076071   |      0.736842 |               0.236842 |
| candidate_action_chunk_consistency_mean            | first         |  20 |    0.00828162  |  0.00882306 |      0.736842 |               0.236842 |
| candidate_action_consensus_first_mean              | mean          |  20 |    0.020839    |  0.0502399  |      0.736842 |               0.236842 |

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

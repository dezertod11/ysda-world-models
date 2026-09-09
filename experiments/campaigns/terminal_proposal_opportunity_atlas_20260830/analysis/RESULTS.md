# Terminal proposal-opportunity atlas

This is a retrospective inventory of outcome-independent terminal branches.
It measures whether a candidate pool contains a better terminal action; it
does not evaluate a learned selector and is not a confirmatory claim.

## Coverage

- Candidate tables: 25.
- Exact-state snapshots: 153.
- Independent task/init groups: 75.
- Heterogeneous pools: 15.
- Rescuable max(value) failures: 7.

## By campaign and factor

| campaign                                           | factor      |   snapshots |   independent_groups |   candidates_min |   candidates_max |   heterogeneous_snapshots |   success_rescues |   utility_rescues |   all_candidates_fail |   all_candidates_succeed |   maxv_sr |   oracle_sr |   maxv_utility |   oracle_utility |   oracle_gap_pp |   rescue_rate |
|:---------------------------------------------------|:------------|------------:|---------------------:|-----------------:|-----------------:|--------------------------:|------------------:|------------------:|----------------------:|-------------------------:|----------:|------------:|---------------:|-----------------:|----------------:|--------------:|
| counterfactual_feedback_dense_relabel_20260827     | Object      |          19 |                   12 |                4 |                4 |                         5 |                 2 |                 2 |                     0 |                       14 |  0.894737 |    1        |        2.68421 |          3       |         10.5263 |      0.105263 |
| terminal_grounded_critic_20260829__development     | Object      |          80 |                   40 |                8 |                8 |                         8 |                 5 |                 5 |                     1 |                       71 |  0.925    |    0.9875   |        2.75    |          2.9625  |          6.25   |      0.0625   |
| counterfactual_feedback_dense_relabel_20260827     | Environment |          20 |                   18 |                4 |                4 |                         0 |                 0 |                 2 |                    11 |                        9 |  0.45     |    0.45     |        1.275   |          1.325   |          0      |      0        |
| terminal_grounded_critic_20260829__holdout         | Object      |          20 |                   10 |                8 |                8 |                         0 |                 0 |                 0 |                     0 |                       20 |  1        |    1        |        3       |          3       |          0      |      0        |
| counterfactual_feedback_dense_relabel_20260827     | Position    |          13 |                    2 |                4 |                4 |                         1 |                 0 |                 1 |                     4 |                        8 |  0.692308 |    0.692308 |        2       |          2.03846 |          0      |      0        |
| counterfactual_feedback_h32_dense_relabel_20260827 | Object      |           1 |                    1 |                6 |                6 |                         1 |                 0 |                 0 |                     0 |                        0 |  1        |    1        |        3       |          3       |          0      |      0        |

## Cells with observed terminal rescue

| campaign                                       | factor   | suite                |   task_id | task_description                                  |   query_idx |   snapshots |   independent_groups |   candidates_min |   candidates_max |   heterogeneous_snapshots |   success_rescues |   utility_rescues |   all_candidates_fail |   all_candidates_succeed |   maxv_sr |   oracle_sr |   maxv_utility |   oracle_utility |   oracle_gap_pp |   rescue_rate |
|:-----------------------------------------------|:---------|:---------------------|----------:|:--------------------------------------------------|------------:|------------:|---------------------:|-----------------:|-----------------:|--------------------------:|------------------:|------------------:|----------------------:|-------------------------:|----------:|------------:|---------------:|-----------------:|----------------:|--------------:|
| terminal_grounded_critic_20260829__development | Object   | libero_object_object |         0 | pick the alphabet soup and place it in the basket |           0 |           5 |                    5 |                8 |                8 |                         3 |                 3 |                 3 |                     0 |                        2 |       0.4 |         1   |            0.8 |              3   |              60 |           0.6 |
| counterfactual_feedback_dense_relabel_20260827 | Object   | libero_object_object |         0 | pick the alphabet soup and place it in the basket |           3 |           2 |                    2 |                4 |                4 |                         2 |                 1 |                 1 |                     0 |                        0 |       0.5 |         1   |            1.5 |              3   |              50 |           0.5 |
| terminal_grounded_critic_20260829__development | Object   | libero_object_object |         0 | pick the alphabet soup and place it in the basket |           3 |           5 |                    5 |                8 |                8 |                         3 |                 2 |                 2 |                     1 |                        1 |       0.4 |         0.8 |            1.2 |              2.4 |              40 |           0.4 |
| counterfactual_feedback_dense_relabel_20260827 | Object   | libero_object_object |         0 | pick the alphabet soup and place it in the basket |           0 |           5 |                    4 |                4 |                4 |                         2 |                 1 |                 1 |                     0 |                        3 |       0.8 |         1   |            2.4 |              3   |              20 |           0.2 |

## Hard cells without candidate choice

| campaign                                       | factor      | suite              |   task_id | task_description                                   |   query_idx |   snapshots |   independent_groups |   candidates_min |   candidates_max |   heterogeneous_snapshots |   success_rescues |   utility_rescues |   all_candidates_fail |   all_candidates_succeed |   maxv_sr |   oracle_sr |   maxv_utility |   oracle_utility |   oracle_gap_pp |   rescue_rate |
|:-----------------------------------------------|:------------|:-------------------|----------:|:---------------------------------------------------|------------:|------------:|---------------------:|-----------------:|-----------------:|--------------------------:|------------------:|------------------:|----------------------:|-------------------------:|----------:|------------:|---------------:|-----------------:|----------------:|--------------:|
| counterfactual_feedback_dense_relabel_20260827 | Position    | libero_object_temp |         0 | pick the alphabet soup and place it in the basket  |           0 |           8 |                    1 |                4 |                4 |                         1 |                 0 |                 1 |                     4 |                        3 |  0.5      |    0.5      |          1.375 |           1.4375 |               0 |             0 |
| counterfactual_feedback_dense_relabel_20260827 | Environment | libero_object_env  |         0 | pick the alphabet soup and place it in the basket  |           0 |           5 |                    5 |                4 |                4 |                         0 |                 0 |                 1 |                     5 |                        0 |  0        |    0        |         -0.2   |          -0.1    |               0 |             0 |
| counterfactual_feedback_dense_relabel_20260827 | Environment | libero_object_env  |         2 | pick the salad dressing and place it in the basket |           3 |           5 |                    5 |                4 |                4 |                         0 |                 0 |                 1 |                     5 |                        0 |  0        |    0        |         -0.1   |           0      |               0 |             0 |
| counterfactual_feedback_dense_relabel_20260827 | Environment | libero_object_env  |         1 | pick the cream cheese and place it in the basket   |           0 |           3 |                    3 |                4 |                4 |                         0 |                 0 |                 0 |                     1 |                        2 |  0.666667 |    0.666667 |          2     |           2      |               0 |             0 |

## Routing rule for the next experiment

A new selector is trained only after a prespecified proposal pool shows
nonzero rescue support and at least a 5 percentage-point oracle gap on
independent init-state holdout. All-fail cells require proposal diversity,
feedback, or recovery rather than another score over the same candidates.

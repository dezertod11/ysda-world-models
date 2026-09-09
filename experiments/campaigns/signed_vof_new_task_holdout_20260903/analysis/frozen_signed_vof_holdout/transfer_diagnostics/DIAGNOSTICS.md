# Signed-VoF holdout transfer diagnosis

Every holdout state is outside the task-0 feature support at |z|>5. The median row-wise maximum is 61.3, the 95th percentile is 103.8, and the maximum is 654.9.

## Policy contrasts

| policy         |   query_rate |   raw_delta |   raw_ci_low |   raw_ci_high |   adjusted_delta |   adjusted_ci_low |   adjusted_ci_high |   rescues |   harms |
|:---------------|-------------:|------------:|-------------:|--------------:|-----------------:|------------------:|-------------------:|----------:|--------:|
| always_commit  |        0     |   0         |   0          |     0         |       0          |         0         |          0         |         0 |       0 |
| always_requery |        1     |   0.0708333 |  -0.00416667 |     0.145833  |       0.0458333  |        -0.025     |          0.120833  |        42 |      25 |
| frozen_router  |        0.525 |   0.0208333 |  -0.0416667  |     0.0791667 |       0.00770833 |        -0.0539583 |          0.0690625 |        24 |      19 |

Frozen routing is -5.0 pp below always-requery before cost, with cluster CI [-9.6, -0.8].

## Cell diagnostics

| position_level   |   task_id |   states |   commit_sr |   always_requery_sr |   router_sr |   always_requery_delta |   router_delta |   router_query_rate |   available_rescues |   available_harms |   selected_rescues |   selected_harms |   rescue_recall |   harm_avoidance |   rescue_vs_harm_auc |   score_median |   max_abs_train_z_median |   max_abs_train_z_max |
|:-----------------|----------:|---------:|------------:|--------------------:|------------:|-----------------------:|---------------:|--------------------:|--------------------:|------------------:|-------------------:|-----------------:|----------------:|-----------------:|---------------------:|---------------:|-------------------------:|----------------------:|
| x0.2             |         5 |       40 |       0.375 |               0.625 |       0.475 |                  0.25  |          0.1   |               0.625 |                  13 |                 3 |                  6 |                2 |       0.461538  |         0.333333 |            0.538462  |       1.41685  |                  75.5018 |              646.55   |
| x0.2             |         6 |       40 |       0.55  |               0.5   |       0.55  |                 -0.05  |          0     |               0     |                   1 |                 3 |                  0 |                0 |       0         |         1        |            0.666667  |      -2.07571  |                  17.0932 |               28.4741 |
| y0.1             |         4 |       40 |       0.65  |               0.9   |       0.675 |                  0.25  |          0.025 |               0.15  |                  11 |                 1 |                  1 |                0 |       0.0909091 |         1        |            0.0909091 |      -3.08808  |                  52.9174 |              654.851  |
| y0.1             |         5 |       40 |       0.85  |               1     |       1     |                  0.15  |          0.15  |               0.95  |                   6 |                 0 |                  6 |                0 |       1         |       nan        |          nan         |       1.64483  |                  84.0494 |              120.281  |
| y0.2             |         8 |       40 |       0.7   |               0.875 |       0.9   |                  0.175 |          0.2   |               0.5   |                   9 |                 2 |                  9 |                1 |       1         |         0.5      |            1         |       0.129294 |                  10.0439 |               10.9649 |
| y0.3             |         5 |       40 |       0.45  |               0.1   |       0.1   |                 -0.35  |         -0.35  |               0.925 |                   2 |                16 |                  2 |               16 |       1         |         0        |            0.25      |       1.64605  |                  67.1668 |               74.2764 |

## Largest transfer shifts

| feature                                    |   holdout_abs_z_median |   holdout_abs_z_p95 |   holdout_abs_z_max |   mean_abs_score_contribution |   max_abs_score_contribution |
|:-------------------------------------------|-----------------------:|--------------------:|--------------------:|------------------------------:|-----------------------------:|
| open_candidate_action_first_d6             |               0.965179 |             2.36564 |            654.851  |                      0.796553 |                     60.8519  |
| pre_current_proprio_d5                     |              25.0783   |            90.4848  |            108.012  |                      3.27279  |                      9.63832 |
| open_candidate_predicted_future_proprio_d3 |              57.441    |            81.296   |            120.281  |                      1.86431  |                      5.04531 |
| open_candidate_predicted_future_proprio_d2 |              19.7299   |            31.0253  |             32.039  |                      2.00131  |                      3.61404 |
| open_candidate_predicted_future_proprio_d5 |              21.3727   |            84.4794  |            107.287  |                      1.15714  |                      3.52054 |
| open_candidate_action_first_d3             |               3.44673  |            11.1858  |             16.0009 |                      0.923029 |                      3.22835 |
| open_candidate_action_first_d1             |               2.24093  |             6.29461 |             17.3136 |                      0.316257 |                      2.12902 |
| open_candidate_action_mean_d1              |               7.16361  |            56.6757  |             76.6893 |                      0.356723 |                      1.93506 |
| open_candidate_action_first_d0             |               3.31906  |             7.3233  |             12.7345 |                      0.445665 |                      1.84163 |
| open_candidate_action_std_d3               |               2.08325  |             7.45395 |             12.2657 |                      0.368811 |                      1.57859 |
| open_candidate_action_mean_d5              |               3.27299  |             8.34549 |              9.7985 |                      0.500797 |                      1.32542 |
| open_candidate_action_std_d0               |               5.98805  |            11.058   |             11.6535 |                      0.679801 |                      1.31141 |

The task-0 linear score is therefore not transportable. Absolute gripper/action and proprio coordinates with tiny development variance produce unbounded extrapolation. Any support clipping or cell exclusion evaluated on these outcomes is post-hoc and cannot rescue the failed confirmatory claim.

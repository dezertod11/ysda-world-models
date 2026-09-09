# Terminal event atlas

- Exact-state pairs: **572** across **113** independent task/init groups.
- Rescue / harm: **29 / 27**.
- Strict replay integrity: **555/572** at `1e-09`.
- Maximum replay error: **3.429e-01**.

## Overall paired result

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|      572 |                  113 |            0.690559 |                0.694056 |       0.0034965 |              -0.025181 |               0.0316671 |        29 |      27 |             2 |          0.0979021 |            368 |         148 |             0.025 |                      -0.0215035 |             0.893853 |                       555 |

## By perturbation factor

| factor      |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| Environment |      310 |                   76 |            0.822581 |                0.812903 |     -0.00967742 |             -0.0316456 |               0.0101019 |         4 |       7 |            -3 |          0.0354839 |            248 |          51 |             0.025 |                      -0.0346774 |             0.548828 |                       298 |
| Object      |      120 |                   25 |            0.483333 |                0.541667 |      0.0583333  |             -0.0423729 |               0.142857  |        18 |      11 |             7 |          0.241667  |             47 |          44 |             0.025 |                       0.0333333 |             0.264931 |                       120 |
| Position    |      142 |                   12 |            0.577465 |                0.56338  |     -0.0140845  |             -0.0774235 |               0.0535762 |         7 |       9 |            -2 |          0.112676  |             73 |          53 |             0.025 |                      -0.0390845 |             0.803619 |                       137 |

## By factor and policy phase

| factor      | phase_at_snapshot   |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:------------|:--------------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| Environment | approach            |      102 |                   51 |            0.598039 |                0.558824 |     -0.0392157  |             -0.0980392 |              0.00980392 |         1 |       5 |            -4 |          0.0588235 |             56 |          40 |             0.025 |                     -0.0642157  |             0.21875  |                       102 |
| Environment | grasp               |      102 |                   52 |            0.901961 |                0.911765 |      0.00980392 |             -0.019802  |              0.0480769  |         3 |       2 |             1 |          0.0490196 |             90 |           7 |             0.025 |                     -0.0151961  |             1        |                        93 |
| Environment | release             |        4 |                    3 |            0        |                0        |      0          |              0         |              0          |         0 |       0 |             0 |          0         |              0 |           4 |             0.025 |                     -0.025      |           nan        |                         4 |
| Environment | transport           |      102 |                   53 |            1        |                1        |      0          |              0         |              0          |         0 |       0 |             0 |          0         |            102 |           0 |             0.025 |                     -0.025      |           nan        |                        99 |
| Object      | approach            |       36 |                   18 |            0.611111 |                0.694444 |      0.0833333  |             -0.111111  |              0.25       |         8 |       5 |             3 |          0.361111  |             17 |           6 |             0.025 |                      0.0583333  |             0.581055 |                        36 |
| Object      | grasp               |       36 |                   18 |            0.416667 |                0.472222 |      0.0555556  |             -0.138889  |              0.25       |         6 |       4 |             2 |          0.277778  |             11 |          15 |             0.025 |                      0.0305556  |             0.753906 |                        36 |
| Object      | release             |       12 |                   12 |            0        |                0        |      0          |              0         |              0          |         0 |       0 |             0 |          0         |              0 |          12 |             0.025 |                     -0.025      |           nan        |                        12 |
| Object      | transport           |       36 |                   21 |            0.583333 |                0.638889 |      0.0555556  |             -0.0909091 |              0.210526   |         4 |       2 |             2 |          0.166667  |             19 |          11 |             0.025 |                      0.0305556  |             0.6875   |                        36 |
| Position    | approach            |       60 |                   10 |            0.35     |                0.333333 |     -0.0166667  |             -0.133333  |              0.0666667  |         4 |       5 |            -1 |          0.15      |             16 |          35 |             0.025 |                     -0.0416667  |             1        |                        60 |
| Position    | grasp               |       41 |                    9 |            0.780488 |                0.731707 |     -0.0487805  |             -0.156863  |              0.0666667  |         1 |       3 |            -2 |          0.097561  |             29 |           8 |             0.025 |                     -0.0737805  |             0.625    |                        41 |
| Position    | release             |        4 |                    3 |            0        |                0        |      0          |              0         |              0          |         0 |       0 |             0 |          0         |              0 |           4 |             0.025 |                     -0.025      |           nan        |                         4 |
| Position    | transport           |       37 |                    8 |            0.783784 |                0.810811 |      0.027027   |             -0.0555556 |              0.148148   |         2 |       1 |             1 |          0.0810811 |             28 |           6 |             0.025 |                      0.00202703 |             1        |                        32 |

## Online metric diagnostics

| feature                                               |   available_states |   spearman_terminal_effect |   rescue_vs_all_auc |   rescue_vs_harm_auc | exploratory_direction   |   oriented_rescue_vs_harm_auc |
|:------------------------------------------------------|-------------------:|---------------------------:|--------------------:|---------------------:|:------------------------|------------------------------:|
| latent_future_proprio_copy_std_mean_mean_over_samples |                572 |                 0.0707287  |            0.604623 |             0.616858 | high                    |                      0.616858 |
| candidate_action_consensus_chunk_mean                 |                572 |                -0.0528694  |            0.494697 |             0.393359 | low                     |                      0.606641 |
| action_pairwise_l2_mean                               |                572 |                -0.0504937  |            0.50054  |             0.401022 | low                     |                      0.598978 |
| action_std_mean                                       |                572 |                -0.0505197  |            0.504477 |             0.402299 | low                     |                      0.597701 |
| action_std_max                                        |                572 |                -0.0451378  |            0.493173 |             0.407407 | low                     |                      0.592593 |
| latent_action_across_seed_std_mean                    |                572 |                -0.0463174  |            0.511717 |             0.408685 | low                     |                      0.591315 |
| value_range                                           |                572 |                -0.0498546  |            0.44745  |             0.408685 | low                     |                      0.591315 |
| value_std                                             |                572 |                -0.0480943  |            0.449482 |             0.411239 | low                     |                      0.588761 |
| latent_value_across_seed_std_mean                     |                572 |                -0.0424726  |            0.491586 |             0.416347 | low                     |                      0.583653 |
| future_image_pixel_std_mean                           |                572 |                -0.046201   |            0.467645 |             0.425287 | low                     |                      0.574713 |
| future_proprio_std_mean                               |                572 |                -0.0366035  |            0.539277 |             0.426564 | low                     |                      0.573436 |
| future_wrist_pixel_std_mean                           |                572 |                -0.0402572  |            0.587985 |             0.427842 | low                     |                      0.572158 |
| latent_value_element_std_mean_mean_over_samples       |                572 |                -0.021491   |            0.512352 |             0.45083  | low                     |                      0.54917  |
| value_mean                                            |                572 |                 0.014647   |            0.407824 |             0.536398 | high                    |                      0.536398 |
| latent_action_copy_std_mean_mean_over_samples         |                572 |                -0.0203963  |            0.536674 |             0.467433 | low                     |                      0.532567 |
| candidate_action_consensus_first_mean                 |                572 |                 0.0152745  |            0.538515 |             0.526181 | high                    |                      0.526181 |
| action_first_step_l2_std                              |                572 |                 0.0158281  |            0.545247 |             0.521073 | high                    |                      0.521073 |
| latent_future_proprio_across_seed_std_mean            |                572 |                 0.00121518 |            0.620309 |             0.491699 | low                     |                      0.508301 |
| planning_predicted_proprio_error                      |                572 |                -0.00428908 |            0.431257 |             0.507024 | high                    |                      0.507024 |

Directions marked exploratory are selected on this development sample and are not confirmatory.

## Selective requery at low budgets

| method                                                            |   budget |   states |   selected |   selected_rescues |   selected_harms |   selected_rescue_rate |   selected_harm_rate |   raw_success_delta |   adjusted_terminal_delta |
|:------------------------------------------------------------------|---------:|---------:|-----------:|-------------------:|-----------------:|-----------------------:|---------------------:|--------------------:|--------------------------:|
| exploratory_value_range                                           |    0.05  |      572 |         29 |                  3 |                0 |              0.103448  |            0         |          0.00524476 |               0.00397727  |
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_action_std_max                                        |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_value_std                                             |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_action_pairwise_l2_mean                               |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_action_std_mean                                       |    0.05  |      572 |         29 |                  2 |                0 |              0.0689655 |            0         |          0.0034965  |               0.00222902  |
| exploratory_latent_action_across_seed_std_mean                    |    0.05  |      572 |         29 |                  1 |                0 |              0.0344828 |            0         |          0.00174825 |               0.000480769 |
| deterministic_random                                              |    0.05  |      572 |         29 |                  1 |                1 |              0.0344828 |            0.0344828 |          0          |              -0.00126748  |
| grouped_oof_ridge                                                 |    0.05  |      572 |         29 |                  2 |                2 |              0.0689655 |            0.0689655 |          0          |              -0.00126748  |
| factor_phase_oof_mean                                             |    0.05  |      572 |         29 |                  2 |                7 |              0.0689655 |            0.241379  |         -0.00874126 |              -0.0100087   |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.075 |      572 |         43 |                  4 |                0 |              0.0930233 |            0         |          0.00699301 |               0.00511364  |
| exploratory_action_pairwise_l2_mean                               |    0.075 |      572 |         43 |                  4 |                0 |              0.0930233 |            0         |          0.00699301 |               0.00511364  |
| exploratory_action_std_mean                                       |    0.075 |      572 |         43 |                  4 |                0 |              0.0930233 |            0         |          0.00699301 |               0.00511364  |
| exploratory_value_std                                             |    0.075 |      572 |         43 |                  3 |                1 |              0.0697674 |            0.0232558 |          0.0034965  |               0.00161713  |
| exploratory_value_range                                           |    0.075 |      572 |         43 |                  3 |                1 |              0.0697674 |            0.0232558 |          0.0034965  |               0.00161713  |
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.075 |      572 |         43 |                  2 |                0 |              0.0465116 |            0         |          0.0034965  |               0.00161713  |
| exploratory_action_std_max                                        |    0.075 |      572 |         43 |                  2 |                0 |              0.0465116 |            0         |          0.0034965  |               0.00161713  |
| exploratory_latent_action_across_seed_std_mean                    |    0.075 |      572 |         43 |                  2 |                1 |              0.0465116 |            0.0232558 |          0.00174825 |              -0.000131119 |
| deterministic_random                                              |    0.075 |      572 |         43 |                  1 |                2 |              0.0232558 |            0.0465116 |         -0.00174825 |              -0.00362762  |
| grouped_oof_ridge                                                 |    0.075 |      572 |         43 |                  2 |                4 |              0.0465116 |            0.0930233 |         -0.0034965  |              -0.00537587  |
| factor_phase_oof_mean                                             |    0.075 |      572 |         43 |                  3 |                7 |              0.0697674 |            0.162791  |         -0.00699301 |              -0.00887238  |
| exploratory_action_pairwise_l2_mean                               |    0.1   |      572 |         58 |                  4 |                0 |              0.0689655 |            0         |          0.00699301 |               0.00445804  |
| exploratory_action_std_mean                                       |    0.1   |      572 |         58 |                  4 |                0 |              0.0689655 |            0         |          0.00699301 |               0.00445804  |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.1   |      572 |         58 |                  4 |                1 |              0.0689655 |            0.0172414 |          0.00524476 |               0.00270979  |
| exploratory_value_range                                           |    0.1   |      572 |         58 |                  3 |                1 |              0.0517241 |            0.0172414 |          0.0034965  |               0.000961538 |
| exploratory_value_std                                             |    0.1   |      572 |         58 |                  3 |                1 |              0.0517241 |            0.0172414 |          0.0034965  |               0.000961538 |
| exploratory_latent_action_across_seed_std_mean                    |    0.1   |      572 |         58 |                  4 |                2 |              0.0689655 |            0.0344828 |          0.0034965  |               0.000961538 |
| exploratory_action_std_max                                        |    0.1   |      572 |         58 |                  2 |                0 |              0.0344828 |            0         |          0.0034965  |               0.000961538 |
| deterministic_random                                              |    0.1   |      572 |         58 |                  2 |                2 |              0.0344828 |            0.0344828 |          0          |              -0.00253497  |
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.1   |      572 |         58 |                  2 |                2 |              0.0344828 |            0.0344828 |          0          |              -0.00253497  |
| grouped_oof_ridge                                                 |    0.1   |      572 |         58 |                  2 |                5 |              0.0344828 |            0.0862069 |         -0.00524476 |              -0.00777972  |
| factor_phase_oof_mean                                             |    0.1   |      572 |         58 |                  5 |                8 |              0.0862069 |            0.137931  |         -0.00524476 |              -0.00777972  |

## Discordant failure transitions

| factor      | terminal_outcome   | open_terminal_failure_type   | feedback_terminal_failure_type     |   states |
|:------------|:-------------------|:-----------------------------|:-----------------------------------|---------:|
| Object      | harm               | success                      | timeout_no_goal                    |        9 |
| Object      | rescue             | timeout_no_goal              | success                            |        7 |
| Position    | rescue             | timeout_no_goal              | success                            |        7 |
| Object      | rescue             | target_drop_candidate        | success                            |        6 |
| Object      | rescue             | kinematic_deadlock_candidate | success                            |        5 |
| Environment | harm               | success                      | timeout_no_goal                    |        5 |
| Position    | harm               | success                      | timeout_no_goal                    |        3 |
| Position    | harm               | success                      | kinematic_deadlock_candidate       |        3 |
| Environment | harm               | success                      | wrong_object_interaction_candidate |        2 |
| Environment | rescue             | target_drop_candidate        | success                            |        2 |
| Position    | harm               | success                      | wrong_object_interaction_candidate |        2 |
| Environment | rescue             | kinematic_deadlock_candidate | success                            |        1 |
| Object      | harm               | success                      | wrong_object_interaction_candidate |        1 |
| Object      | harm               | success                      | kinematic_deadlock_candidate       |        1 |
| Environment | rescue             | timeout_no_goal              | success                            |        1 |
| Position    | harm               | success                      | target_drop_candidate              |        1 |

## Interpretation

- `terminal_effect=+1` is a rescue, `-1` is a harm, and `0` leaves terminal success unchanged.
- Dense/local progress is auxiliary; deployment decisions are evaluated on terminal effect and query cost.
- A selector advances only after grouped task/init holdout has positive adjusted terminal gain.
- Cells with replay error above the threshold require strict-subset sensitivity analysis.

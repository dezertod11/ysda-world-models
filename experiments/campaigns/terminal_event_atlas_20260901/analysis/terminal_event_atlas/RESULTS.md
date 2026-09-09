# Terminal event atlas

- Exact-state pairs: **617** across **119** independent task/init groups.
- Rescue / harm: **32 / 28**.
- Strict replay integrity: **600/617** at `1e-09`.
- Maximum replay error: **3.429e-01**.

## Overall paired result

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|      617 |                  119 |            0.685575 |                0.692058 |      0.00648298 |             -0.0201011 |               0.0350885 |        32 |      28 |             4 |          0.0972447 |            395 |         162 |             0.025 |                       -0.018517 |             0.698883 |                       600 |

## By perturbation factor

| factor      |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|:------------|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
| Environment |      310 |                   76 |            0.822581 |                0.812903 |     -0.00967742 |             -0.0316456 |               0.0101019 |         4 |       7 |            -3 |          0.0354839 |            248 |          51 |             0.025 |                      -0.0346774 |             0.548828 |                       298 |
| Object      |      120 |                   25 |            0.483333 |                0.541667 |      0.0583333  |             -0.0423729 |               0.142857  |        18 |      11 |             7 |          0.241667  |             47 |          44 |             0.025 |                       0.0333333 |             0.264931 |                       120 |
| Position    |      187 |                   18 |            0.588235 |                0.588235 |      0          |             -0.0558376 |               0.05625   |        10 |      10 |             0 |          0.106952  |            100 |          67 |             0.025 |                      -0.025     |             1        |                       182 |

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
| Position    | grasp               |       60 |                   14 |            0.666667 |                0.633333 |     -0.0333333  |             -0.113208  |              0.0363636  |         2 |       4 |            -2 |          0.1       |             36 |          18 |             0.025 |                     -0.0583333  |             0.6875   |                        60 |
| Position    | release             |        8 |                    5 |            0.125    |                0.375    |      0.25       |              0         |              0.545455   |         2 |       0 |             2 |          0.25      |              1 |           5 |             0.025 |                      0.225      |             0.5      |                         8 |
| Position    | transport           |       59 |                   12 |            0.813559 |                0.830508 |      0.0169492  |             -0.0408163 |              0.0769231  |         2 |       1 |             1 |          0.0508475 |             47 |           9 |             0.025 |                     -0.00805085 |             1        |                        54 |

## Online metric diagnostics

| feature                                               |   available_states |   spearman_terminal_effect |   rescue_vs_all_auc |   rescue_vs_harm_auc | exploratory_direction   |   oriented_rescue_vs_harm_auc |
|:------------------------------------------------------|-------------------:|---------------------------:|--------------------:|---------------------:|:------------------------|------------------------------:|
| latent_future_proprio_copy_std_mean_mean_over_samples |                617 |                 0.0770218  |            0.621368 |             0.625    | high                    |                      0.625    |
| candidate_action_consensus_chunk_mean                 |                617 |                -0.0390805  |            0.516774 |             0.416295 | low                     |                      0.583705 |
| action_std_max                                        |                617 |                -0.0370497  |            0.507639 |             0.421875 | low                     |                      0.578125 |
| action_std_mean                                       |                617 |                -0.0364262  |            0.526709 |             0.425223 | low                     |                      0.574777 |
| action_pairwise_l2_mean                               |                617 |                -0.036383   |            0.522703 |             0.425223 | low                     |                      0.574777 |
| latent_action_across_seed_std_mean                    |                617 |                -0.0328848  |            0.532799 |             0.429688 | low                     |                      0.570312 |
| future_proprio_std_mean                               |                617 |                -0.0288915  |            0.558707 |             0.435268 | low                     |                      0.564732 |
| candidate_action_consensus_first_mean                 |                617 |                 0.0305583  |            0.560951 |             0.554688 | high                    |                      0.554688 |
| value_mean                                            |                617 |                 0.0175928  |            0.405929 |             0.553571 | high                    |                      0.553571 |
| action_first_step_l2_std                              |                617 |                 0.0310184  |            0.567361 |             0.547991 | high                    |                      0.547991 |
| future_image_pixel_std_mean                           |                617 |                -0.0323061  |            0.492949 |             0.452009 | low                     |                      0.547991 |
| future_wrist_pixel_std_mean                           |                617 |                -0.0241733  |            0.607479 |             0.453125 | low                     |                      0.546875 |
| value_range                                           |                617 |                -0.0237252  |            0.493483 |             0.464286 | low                     |                      0.535714 |
| value_std                                             |                617 |                -0.0220636  |            0.494551 |             0.465402 | low                     |                      0.534598 |
| latent_value_across_seed_std_mean                     |                617 |                -0.0174876  |            0.536378 |             0.467634 | low                     |                      0.532366 |
| planning_predicted_proprio_error                      |                617 |                 0.007834   |            0.456143 |             0.529018 | high                    |                      0.529018 |
| latent_value_element_std_mean_mean_over_samples       |                617 |                -0.00380632 |            0.547756 |             0.482143 | low                     |                      0.517857 |
| latent_action_copy_std_mean_mean_over_samples         |                617 |                -0.00901126 |            0.555716 |             0.485491 | low                     |                      0.514509 |
| latent_future_proprio_across_seed_std_mean            |                617 |                 0.00218703 |            0.626603 |             0.487723 | low                     |                      0.512277 |

Directions marked exploratory are selected on this development sample and are not confirmatory.

## Selective requery at low budgets

| method                                                            |   budget |   states |   selected |   selected_rescues |   selected_harms |   selected_rescue_rate |   selected_harm_rate |   raw_success_delta |   adjusted_terminal_delta |
|:------------------------------------------------------------------|---------:|---------:|-----------:|-------------------:|-----------------:|-----------------------:|---------------------:|--------------------:|--------------------------:|
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.05  |      617 |         31 |                  2 |                0 |              0.0645161 |            0         |          0.00324149 |               0.00198541  |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.05  |      617 |         31 |                  2 |                0 |              0.0645161 |            0         |          0.00324149 |               0.00198541  |
| exploratory_action_std_max                                        |    0.05  |      617 |         31 |                  2 |                0 |              0.0645161 |            0         |          0.00324149 |               0.00198541  |
| exploratory_action_std_mean                                       |    0.05  |      617 |         31 |                  2 |                0 |              0.0645161 |            0         |          0.00324149 |               0.00198541  |
| exploratory_action_pairwise_l2_mean                               |    0.05  |      617 |         31 |                  2 |                0 |              0.0645161 |            0         |          0.00324149 |               0.00198541  |
| exploratory_latent_action_across_seed_std_mean                    |    0.05  |      617 |         31 |                  1 |                0 |              0.0322581 |            0         |          0.00162075 |               0.000364668 |
| exploratory_future_proprio_std_mean                               |    0.05  |      617 |         31 |                  1 |                0 |              0.0322581 |            0         |          0.00162075 |               0.000364668 |
| deterministic_random                                              |    0.05  |      617 |         31 |                  1 |                1 |              0.0322581 |            0.0322581 |          0          |              -0.00125608  |
| exploratory_candidate_action_consensus_first_mean                 |    0.05  |      617 |         31 |                  1 |                1 |              0.0322581 |            0.0322581 |          0          |              -0.00125608  |
| grouped_oof_ridge                                                 |    0.05  |      617 |         31 |                  1 |                3 |              0.0322581 |            0.0967742 |         -0.00324149 |              -0.00449757  |
| factor_phase_oof_mean                                             |    0.05  |      617 |         31 |                  1 |                6 |              0.0322581 |            0.193548  |         -0.00810373 |              -0.00935981  |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.075 |      617 |         47 |                  4 |                0 |              0.0851064 |            0         |          0.00648298 |               0.00457861  |
| exploratory_action_std_mean                                       |    0.075 |      617 |         47 |                  4 |                0 |              0.0851064 |            0         |          0.00648298 |               0.00457861  |
| exploratory_action_pairwise_l2_mean                               |    0.075 |      617 |         47 |                  4 |                0 |              0.0851064 |            0         |          0.00648298 |               0.00457861  |
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.075 |      617 |         47 |                  3 |                1 |              0.0638298 |            0.0212766 |          0.00324149 |               0.00133712  |
| exploratory_candidate_action_consensus_first_mean                 |    0.075 |      617 |         47 |                  4 |                2 |              0.0851064 |            0.0425532 |          0.00324149 |               0.00133712  |
| exploratory_action_std_max                                        |    0.075 |      617 |         47 |                  2 |                0 |              0.0425532 |            0         |          0.00324149 |               0.00133712  |
| exploratory_latent_action_across_seed_std_mean                    |    0.075 |      617 |         47 |                  2 |                1 |              0.0425532 |            0.0212766 |          0.00162075 |              -0.00028363  |
| exploratory_future_proprio_std_mean                               |    0.075 |      617 |         47 |                  1 |                0 |              0.0212766 |            0         |          0.00162075 |              -0.00028363  |
| deterministic_random                                              |    0.075 |      617 |         47 |                  1 |                1 |              0.0212766 |            0.0212766 |          0          |              -0.00190438  |
| grouped_oof_ridge                                                 |    0.075 |      617 |         47 |                  1 |                4 |              0.0212766 |            0.0851064 |         -0.00486224 |              -0.00676661  |
| factor_phase_oof_mean                                             |    0.075 |      617 |         47 |                  2 |                9 |              0.0425532 |            0.191489  |         -0.0113452  |              -0.0132496   |
| exploratory_candidate_action_consensus_chunk_mean                 |    0.1   |      617 |         62 |                  4 |                0 |              0.0645161 |            0         |          0.00648298 |               0.00397083  |
| exploratory_action_std_mean                                       |    0.1   |      617 |         62 |                  4 |                0 |              0.0645161 |            0         |          0.00648298 |               0.00397083  |
| exploratory_action_pairwise_l2_mean                               |    0.1   |      617 |         62 |                  4 |                0 |              0.0645161 |            0         |          0.00648298 |               0.00397083  |
| exploratory_candidate_action_consensus_first_mean                 |    0.1   |      617 |         62 |                  5 |                2 |              0.0806452 |            0.0322581 |          0.00486224 |               0.00235008  |
| exploratory_latent_action_across_seed_std_mean                    |    0.1   |      617 |         62 |                  4 |                2 |              0.0645161 |            0.0322581 |          0.00324149 |               0.000729335 |
| exploratory_latent_future_proprio_copy_std_mean_mean_over_samples |    0.1   |      617 |         62 |                  3 |                1 |              0.0483871 |            0.016129  |          0.00324149 |               0.000729335 |
| exploratory_future_proprio_std_mean                               |    0.1   |      617 |         62 |                  2 |                0 |              0.0322581 |            0         |          0.00324149 |               0.000729335 |
| exploratory_action_std_max                                        |    0.1   |      617 |         62 |                  2 |                0 |              0.0322581 |            0         |          0.00324149 |               0.000729335 |
| deterministic_random                                              |    0.1   |      617 |         62 |                  1 |                2 |              0.016129  |            0.0322581 |         -0.00162075 |              -0.0041329   |
| factor_phase_oof_mean                                             |    0.1   |      617 |         62 |                  5 |               10 |              0.0806452 |            0.16129   |         -0.00810373 |              -0.0106159   |
| grouped_oof_ridge                                                 |    0.1   |      617 |         62 |                  1 |                7 |              0.016129  |            0.112903  |         -0.00972447 |              -0.0122366   |

## Discordant failure transitions

| factor      | terminal_outcome   | open_terminal_failure_type         | feedback_terminal_failure_type     |   states |
|:------------|:-------------------|:-----------------------------------|:-----------------------------------|---------:|
| Object      | harm               | success                            | timeout_no_goal                    |        9 |
| Position    | rescue             | timeout_no_goal                    | success                            |        8 |
| Object      | rescue             | timeout_no_goal                    | success                            |        7 |
| Object      | rescue             | target_drop_candidate              | success                            |        6 |
| Object      | rescue             | kinematic_deadlock_candidate       | success                            |        5 |
| Environment | harm               | success                            | timeout_no_goal                    |        5 |
| Position    | harm               | success                            | kinematic_deadlock_candidate       |        3 |
| Position    | harm               | success                            | timeout_no_goal                    |        3 |
| Environment | harm               | success                            | wrong_object_interaction_candidate |        2 |
| Environment | rescue             | target_drop_candidate              | success                            |        2 |
| Position    | harm               | success                            | target_drop_candidate              |        2 |
| Position    | harm               | success                            | wrong_object_interaction_candidate |        2 |
| Environment | rescue             | timeout_no_goal                    | success                            |        1 |
| Object      | harm               | success                            | kinematic_deadlock_candidate       |        1 |
| Object      | harm               | success                            | wrong_object_interaction_candidate |        1 |
| Environment | rescue             | kinematic_deadlock_candidate       | success                            |        1 |
| Position    | rescue             | target_drop_candidate              | success                            |        1 |
| Position    | rescue             | wrong_object_interaction_candidate | success                            |        1 |

## Interpretation

- `terminal_effect=+1` is a rescue, `-1` is a harm, and `0` leaves terminal success unchanged.
- Dense/local progress is auxiliary; deployment decisions are evaluated on terminal effect and query cost.
- A selector advances only after grouped task/init holdout has positive adjusted terminal gain.
- Cells with replay error above the threshold require strict-subset sensitivity analysis.

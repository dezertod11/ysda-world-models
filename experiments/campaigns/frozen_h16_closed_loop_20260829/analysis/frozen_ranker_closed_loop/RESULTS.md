# Frozen H16 ranker: paired closed-loop result

- Complete paired rollouts: **360**.
- Formal gate: **FAIL**.
- Primary endpoint: terminal success-rate delta, frozen ranker minus max value.

## Terminal success

| factor      |   paired_rollouts |   independent_groups |   max_value_successes |   max_value_sr |   frozen_ranker_successes |   frozen_ranker_sr |   sr_delta |   frozen_gains |   frozen_losses |   same_outcome |   mcnemar_exact_p |
|:------------|------------------:|---------------------:|----------------------:|---------------:|--------------------------:|-------------------:|-----------:|---------------:|----------------:|---------------:|------------------:|
| Environment |               120 |                   15 |                    45 |          0.375 |                        41 |           0.341667 | -0.0333333 |              1 |               5 |            114 |           0.21875 |
| Object      |               120 |                   10 |                   120 |          1     |                       120 |           1        |  0         |              0 |               0 |            120 |           1       |
| Position    |               120 |                   20 |                     0 |          0     |                         3 |           0.025    |  0.025     |              3 |               0 |            117 |           0.25    |

## Grouped bootstrap

| factor      |   independent_groups |    sr_delta |   ci95_lower |   ci95_upper |   probability_delta_above_zero |
|:------------|---------------------:|------------:|-------------:|-------------:|-------------------------------:|
| Environment |                   15 | -0.0333333  |   -0.0916667 |    0         |                         0      |
| Object      |                   10 |  0          |    0         |    0         |                         0      |
| Position    |                   20 |  0.025      |    0         |    0.05      |                         0.9596 |
| All         |                   45 | -0.00277778 |   -0.0222222 |    0.0138889 |                         0.348  |

## Selection and compute

| factor      | planning_strategy   |   episodes |   success_rate |   mean_final_t |   mean_queries |   selected_not_max_value_rate |   mean_value_sacrifice |
|:------------|:--------------------|-----------:|---------------:|---------------:|---------------:|------------------------------:|-----------------------:|
| Environment | frozen_factor_ridge |        120 |       0.341667 |        229.65  |       14.825   |                      0.732461 |            0.00543392  |
| Environment | max_value           |        120 |       0.375    |        222.8   |       14.3833  |                      0        |            0           |
| Object      | frozen_factor_ridge |        120 |       1        |        133.117 |        8.775   |                      0.674537 |            0.000760617 |
| Object      | max_value           |        120 |       1        |        133.975 |        8.86667 |                      0        |            0           |
| Position    | frozen_factor_ridge |        120 |       0.025    |        279.017 |       17.9417  |                      0.937473 |            0.00479406  |
| Position    | max_value           |        120 |       0        |        280     |       18       |                      0        |            0           |

## Query-zero integrity

| quantity                            |   pairs |   absolute_tolerance |   max_abs_difference |   p95_abs_difference |   match_rate |
|:------------------------------------|--------:|---------------------:|---------------------:|---------------------:|-------------:|
| candidate_values_json               |     360 |               0.0005 |                    0 |                    0 |     1        |
| candidate_frozen_ranker_scores_json |     360 |               0.002  |                    0 |                    0 |     1        |
| candidate_first_actions_json        |     360 |               0.005  |                    0 |                    0 |     1        |
| selector_disagreement               |     360 |             nan      |                  nan |                  nan |     0.730556 |

## Prediction errors

| factor      | planning_strategy   |   episodes |   prediction_error_future_image_mse__mean |   prediction_error_future_image_mse__median |   prediction_error_future_image_ssim_global__mean |   prediction_error_future_image_ssim_global__median |   prediction_error_future_wrist_mse__mean |   prediction_error_future_wrist_mse__median |   prediction_error_future_wrist_ssim_global__mean |   prediction_error_future_wrist_ssim_global__median |   prediction_error_future_proprio_l2__mean |   prediction_error_future_proprio_l2__median |   prediction_error_value_abs_chunk_success__mean |   prediction_error_value_abs_chunk_success__median |   prediction_error_value_abs_final_success__mean |   prediction_error_value_abs_final_success__median |
|:------------|:--------------------|-----------:|------------------------------------------:|--------------------------------------------:|--------------------------------------------------:|----------------------------------------------------:|------------------------------------------:|--------------------------------------------:|--------------------------------------------------:|----------------------------------------------------:|-------------------------------------------:|---------------------------------------------:|-------------------------------------------------:|---------------------------------------------------:|-------------------------------------------------:|---------------------------------------------------:|
| Environment | frozen_factor_ridge |        120 |                                   851.968 |                                     810.899 |                                          0.792851 |                                            0.800349 |                                   972.851 |                                     848.888 |                                          0.68751  |                                            0.686154 |                                  0.162258  |                                    0.14294   |                                         0.449953 |                                           0.389623 |                                         0.578624 |                                           0.617734 |
| Environment | max_value           |        120 |                                   851.688 |                                     813.237 |                                          0.792639 |                                            0.799345 |                                   980.775 |                                     865.32  |                                          0.688441 |                                            0.684112 |                                  0.16362   |                                    0.139235  |                                         0.445259 |                                           0.388718 |                                         0.579316 |                                           0.620018 |
| Object      | frozen_factor_ridge |        120 |                                   590.038 |                                     587.326 |                                          0.835485 |                                            0.83542  |                                  1149.58  |                                    1138.36  |                                          0.874495 |                                            0.87527  |                                  0.0573238 |                                    0.0652679 |                                         0.445745 |                                           0.441551 |                                         0.448631 |                                           0.455599 |
| Object      | max_value           |        120 |                                   592.711 |                                     589.106 |                                          0.834825 |                                            0.835648 |                                  1156.36  |                                    1153.84  |                                          0.873417 |                                            0.874833 |                                  0.0588333 |                                    0.066055  |                                         0.448428 |                                           0.445102 |                                         0.445814 |                                           0.450221 |
| Position    | frozen_factor_ridge |        120 |                                   661.986 |                                     650.488 |                                          0.791822 |                                            0.788588 |                                  1650.57  |                                    1631.87  |                                          0.801713 |                                            0.802286 |                                  0.182517  |                                    0.183991  |                                         0.487628 |                                           0.471044 |                                         0.487285 |                                           0.475578 |
| Position    | max_value           |        120 |                                   680.362 |                                     650.183 |                                          0.787256 |                                            0.787622 |                                  1514.55  |                                    1455.08  |                                          0.813522 |                                            0.821403 |                                  0.17032   |                                    0.156914  |                                         0.468507 |                                           0.388414 |                                         0.468507 |                                           0.388414 |

Full query-index trajectories are in `query_level_summary.csv` and `ranker_selection_by_query.png`.

## Candidate preference

| factor      | feature                              |   disagreeing_queries |   mean_selected_minus_max_value_z |   median_selected_minus_max_value_z |   mean_selected_minus_max_value_raw |
|:------------|:-------------------------------------|----------------------:|----------------------------------:|------------------------------------:|------------------------------------:|
| Environment | candidate_action_chunk_l1            |                  1308 |                         1.44238   |                           1.54779   |                         0.00172485  |
| Environment | candidate_action_chunk_l2            |                  1308 |                         1.25521   |                           1.34739   |                         0.00156344  |
| Environment | candidate_first_action_l1            |                  1308 |                         0.737946  |                           0.841656  |                         0.0022564   |
| Environment | candidate_value                      |                  1308 |                        -1.37224   |                          -1.31917   |                        -0.00710624  |
| Environment | latent_action_copy_std_max           |                  1308 |                        -0.119477  |                          -0.069646  |                        -0.002758    |
| Environment | latent_action_copy_std_mean          |                  1308 |                        -0.458401  |                          -0.472094  |                        -0.000100901 |
| Environment | latent_action_first_step_copy_l2_std |                  1308 |                        -0.188521  |                          -0.206532  |                        -0.000509016 |
| Environment | latent_future_proprio_copy_std_max   |                  1308 |                        -0.0659331 |                          -0.0839693 |                        -2.10092e-05 |
| Environment | latent_future_proprio_copy_std_mean  |                  1308 |                        -0.16537   |                          -0.147844  |                        -3.08843e-05 |
| Environment | latent_value_element_std_max         |                  1308 |                         0.723163  |                           0.953314  |                         0.000316374 |
| Environment | latent_value_element_std_mean        |                  1308 |                         0.723163  |                           0.953314  |                         0.000316374 |
| Object      | candidate_action_chunk_l1            |                   712 |                         1.22183   |                           1.28727   |                         0.000833452 |
| Object      | candidate_action_chunk_l2            |                   712 |                         1.42996   |                           1.54267   |                         0.000797221 |
| Object      | candidate_first_action_l1            |                   712 |                         0.766898  |                           0.826025  |                         0.000955317 |
| Object      | candidate_value                      |                   712 |                        -1.39479   |                          -1.2485    |                        -0.00111009  |
| Object      | latent_action_copy_std_max           |                   712 |                        -0.345505  |                          -0.377801  |                        -0.000708052 |
| Object      | latent_action_copy_std_mean          |                   712 |                        -0.366344  |                          -0.366326  |                        -4.15561e-05 |
| Object      | latent_action_first_step_copy_l2_std |                   712 |                         0.280624  |                           0.34601   |                         0.000148122 |
| Object      | latent_future_proprio_copy_std_max   |                   712 |                         0.485666  |                           0.577047  |                         6.08272e-05 |
| Object      | latent_future_proprio_copy_std_mean  |                   712 |                         0.0904805 |                           0.125775  |                         8.73663e-06 |
| Object      | latent_value_element_std_max         |                   712 |                        -0.592684  |                          -0.652432  |                        -7.75478e-05 |
| Object      | latent_value_element_std_mean        |                   712 |                        -0.592684  |                          -0.652432  |                        -7.75478e-05 |
| Position    | candidate_action_chunk_l1            |                  2018 |                        -0.707757  |                          -0.827738  |                        -0.00121901  |
| Position    | candidate_action_chunk_l2            |                  2018 |                        -0.733278  |                          -0.826699  |                        -0.00133969  |
| Position    | candidate_first_action_l1            |                  2018 |                         0.0945577 |                           0.101556  |                         0.000686803 |
| Position    | candidate_value                      |                  2018 |                        -2.08439   |                          -2.28174   |                        -0.00511445  |
| Position    | latent_action_copy_std_max           |                  2018 |                        -0.19946   |                          -0.135637  |                         0.00117736  |
| Position    | latent_action_copy_std_mean          |                  2018 |                         0.0132491 |                           0.0199442 |                         5.09058e-05 |
| Position    | latent_action_first_step_copy_l2_std |                  2018 |                        -0.0542749 |                          -0.0642638 |                        -0.000133233 |
| Position    | latent_future_proprio_copy_std_max   |                  2018 |                         0.119307  |                           0.17352   |                         9.27244e-05 |
| Position    | latent_future_proprio_copy_std_mean  |                  2018 |                         0.821728  |                           1.03959   |                         0.000122294 |
| Position    | latent_value_element_std_max         |                  2018 |                         0.102604  |                           0.102571  |                         1.62906e-05 |
| Position    | latent_value_element_std_mean        |                  2018 |                         0.102604  |                           0.102571  |                         1.62906e-05 |

## Failure modes

| factor      | planning_strategy   | failure_type                       |   episodes |   target_drops |
|:------------|:--------------------|:-----------------------------------|-----------:|---------------:|
| Environment | frozen_factor_ridge | wrong_object_interaction_candidate |         48 |              0 |
| Environment | frozen_factor_ridge | timeout_no_goal                    |         24 |              0 |
| Environment | frozen_factor_ridge | kinematic_deadlock_candidate       |          6 |              0 |
| Environment | frozen_factor_ridge | target_drop_candidate              |          1 |              1 |
| Environment | max_value           | wrong_object_interaction_candidate |         46 |              0 |
| Environment | max_value           | timeout_no_goal                    |         26 |              0 |
| Environment | max_value           | kinematic_deadlock_candidate       |          3 |              0 |
| Position    | frozen_factor_ridge | timeout_no_goal                    |         64 |              0 |
| Position    | frozen_factor_ridge | wrong_object_interaction_candidate |         31 |              0 |
| Position    | frozen_factor_ridge | target_drop_candidate              |         14 |             14 |
| Position    | frozen_factor_ridge | kinematic_deadlock_candidate       |          8 |              0 |
| Position    | max_value           | timeout_no_goal                    |         75 |              0 |
| Position    | max_value           | wrong_object_interaction_candidate |         27 |              0 |
| Position    | max_value           | kinematic_deadlock_candidate       |         11 |              0 |
| Position    | max_value           | target_drop_candidate              |          7 |              7 |

## Task/init groups

| factor      | case_id                           | suite                |   task_id | task_description                                         |   init_state_id |   paired_rollouts |   max_value_sr |   frozen_ranker_sr |   sr_delta |   frozen_gains |   frozen_losses |
|:------------|:----------------------------------|:---------------------|----------:|:---------------------------------------------------------|----------------:|------------------:|---------------:|-------------------:|-----------:|---------------:|----------------:|
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         7 | pick up the milk and place it in the basket              |               5 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         7 | pick up the milk and place it in the basket              |               6 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         7 | pick up the milk and place it in the basket              |               7 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         7 | pick up the milk and place it in the basket              |               8 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         7 | pick up the milk and place it in the basket              |               9 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         8 | pick up the chocolate pudding and place it in the basket |               5 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         8 | pick up the chocolate pudding and place it in the basket |               6 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         8 | pick up the chocolate pudding and place it in the basket |               7 |                 8 |          0.875 |           0.875    |   0        |              1 |               1 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         8 | pick up the chocolate pudding and place it in the basket |               8 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         8 | pick up the chocolate pudding and place it in the basket |               9 |                 8 |          0     |           0        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         9 | pick up the orange juice and place it in the basket      |               5 |                 8 |          1     |           1        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         9 | pick up the orange juice and place it in the basket      |               6 |                 8 |          1     |           1        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         9 | pick up the orange juice and place it in the basket      |               7 |                 8 |          1     |           0.875    |  -0.125    |              0 |               1 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         9 | pick up the orange juice and place it in the basket      |               8 |                 8 |          1     |           1        |   0        |              0 |               0 |
| Environment | frozen_closed_loop__Environment   | libero_object_env    |         9 | pick up the orange juice and place it in the basket      |               9 |                 8 |          0.75  |           0.375    |  -0.375    |              0 |               3 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         8 | pick up the chocolate pudding and place it in the basket |               5 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         8 | pick up the chocolate pudding and place it in the basket |               6 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         8 | pick up the chocolate pudding and place it in the basket |               7 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         8 | pick up the chocolate pudding and place it in the basket |               8 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         8 | pick up the chocolate pudding and place it in the basket |               9 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         9 | pick up the orange juice and place it in the basket      |               5 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         9 | pick up the orange juice and place it in the basket      |               6 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         9 | pick up the orange juice and place it in the basket      |               7 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         9 | pick up the orange juice and place it in the basket      |               8 |                12 |          1     |           1        |   0        |              0 |               0 |
| Object      | frozen_closed_loop__Object        | libero_object_object |         9 | pick up the orange juice and place it in the basket      |               9 |                12 |          1     |           1        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         4 | pick up the ketchup and place it in the basket           |               5 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         4 | pick up the ketchup and place it in the basket           |               6 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         4 | pick up the ketchup and place it in the basket           |               7 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         4 | pick up the ketchup and place it in the basket           |               8 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         4 | pick up the ketchup and place it in the basket           |               9 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         5 | pick up the tomato sauce and place it in the basket      |               5 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         5 | pick up the tomato sauce and place it in the basket      |               6 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         5 | pick up the tomato sauce and place it in the basket      |               7 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         5 | pick up the tomato sauce and place it in the basket      |               8 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_x0p3 | libero_object_temp   |         5 | pick up the tomato sauce and place it in the basket      |               9 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         8 | pick up the chocolate pudding and place it in the basket |               5 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         8 | pick up the chocolate pudding and place it in the basket |               6 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         8 | pick up the chocolate pudding and place it in the basket |               7 |                 6 |          0     |           0.166667 |   0.166667 |              1 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         8 | pick up the chocolate pudding and place it in the basket |               8 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         8 | pick up the chocolate pudding and place it in the basket |               9 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         9 | pick up the orange juice and place it in the basket      |               5 |                 6 |          0     |           0.166667 |   0.166667 |              1 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         9 | pick up the orange juice and place it in the basket      |               6 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         9 | pick up the orange juice and place it in the basket      |               7 |                 6 |          0     |           0.166667 |   0.166667 |              1 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         9 | pick up the orange juice and place it in the basket      |               8 |                 6 |          0     |           0        |   0        |              0 |               0 |
| Position    | frozen_closed_loop__Position_y0p3 | libero_object_temp   |         9 | pick up the orange juice and place it in the basket      |               9 |                 6 |          0     |           0        |   0        |              0 |               0 |

## Gate

```json
{
  "passed": false,
  "complete_pairs": true,
  "expected_pairs_per_factor": 120,
  "factor_pair_counts": {
    "Environment": 120,
    "Object": 120,
    "Position": 120
  },
  "expected_factor_counts": true,
  "model_payload_sha256": [
    "086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb"
  ],
  "model_hash_matches": true,
  "q0_candidate_pools_match": true,
  "selectors_match_definitions": true,
  "ranker_changes_at_least_one_query0_selection": true,
  "six_candidates_every_query": true,
  "macro_ci95_lower_above_zero": false,
  "no_factor_material_regression_below_minus_5pp": true,
  "no_factor_ci95_entirely_below_zero": true
}
```

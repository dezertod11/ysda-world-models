# Counterfactual feedback and grounded candidate pilot

- Collected snapshot rows: **100**; unique pooled states: **100**.
- Candidate branch outcomes: **400**.
- Snapshots with terminal continuation: **19**.
- Maximum main/open replay state error: **2.899e-05**.
- Replay integrity failures at the preregistered `1e-9` threshold: **2/100**.
- `local_vof` support: **0 positive / 0 negative / 100 zero**.
- `dense_vof_v2` support: **36 positive / 63 negative / 1 zero**.
- `terminal_vof` support: **0 positive / 3 negative / 16 zero**.
- Candidate states with non-tied utility: `local_utility_v1`=0, `dense_utility_v2`=99, `terminal_utility_v1`=5.

## VoF by factor and phase

| target       | factor   | phase     |   states |    mean_vof |   median_vof |   positive_rate |   negative_rate |
|:-------------|:---------|:----------|---------:|------------:|-------------:|----------------:|----------------:|
| local_vof    | Object   | approach  |       36 |  0          |   0          |        0        |        0        |
| local_vof    | Object   | grasp     |       35 |  0          |   0          |        0        |        0        |
| local_vof    | Object   | release   |        1 |  0          |   0          |        0        |        0        |
| local_vof    | Object   | transport |       28 |  0          |   0          |        0        |        0        |
| dense_vof_v2 | Object   | approach  |       36 | -0.0246092  |  -0.0134395  |        0.166667 |        0.833333 |
| dense_vof_v2 | Object   | grasp     |       35 |  0.0280262  |   0.0035346  |        0.571429 |        0.428571 |
| dense_vof_v2 | Object   | release   |        1 |  0          |   0          |        0        |        0        |
| dense_vof_v2 | Object   | transport |       28 | -0.00282821 |  -0.00261988 |        0.357143 |        0.642857 |
| terminal_vof | Object   | approach  |        8 | -0.4375     |   0          |        0        |        0.25     |
| terminal_vof | Object   | grasp     |        5 | -0.1        |   0          |        0        |        0.2      |
| terminal_vof | Object   | transport |        6 |  0          |   0          |        0        |        0        |

## Grouped out-of-fold predictor

| target       |   states | features                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |         mae |   correlation |   sign_accuracy |   positive_vof_auc |
|:-------------|---------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------:|--------------:|----------------:|-------------------:|
| local_vof    |      100 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error |   0         |    nan        |            1    |         nan        |
| dense_vof_v2 |      100 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error |   0.0463585 |      0.394735 |            0.74 |           0.758681 |
| terminal_vof |        0 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | nan         |    nan        |          nan    |         nan        |

## Uplift at fixed query budget

| target       | method                           |   budget |   states |   selected |   mean_vof_selected |   uplift_per_decision |   positive_rate_selected |   positive_vof_auc |
|:-------------|:---------------------------------|---------:|---------:|-----------:|--------------------:|----------------------:|-------------------------:|-------------------:|
| local_vof    | grouped_oof_ridge                |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | grouped_oof_ridge                |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | grouped_oof_ridge                |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| local_vof    | random                           |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | random                           |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | random                           |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| local_vof    | oracle                           |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | oracle                           |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | oracle                           |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| local_vof    | value_range                      |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | value_range                      |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | value_range                      |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| local_vof    | action_first_step_l2_std         |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | action_first_step_l2_std         |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | action_first_step_l2_std         |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.1 |      100 |         10 |          0          |           0           |                 0        |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.2 |      100 |         20 |          0          |           0           |                 0        |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.3 |      100 |         30 |          0          |           0           |                 0        |         nan        |
| dense_vof_v2 | grouped_oof_ridge                |      0.1 |      100 |         10 |          0.0313328  |           0.00313328  |                 0.5      |           0.758681 |
| dense_vof_v2 | grouped_oof_ridge                |      0.2 |      100 |         20 |          0.03626    |           0.007252    |                 0.55     |           0.758681 |
| dense_vof_v2 | grouped_oof_ridge                |      0.3 |      100 |         30 |          0.0489292  |           0.0146788   |                 0.666667 |           0.758681 |
| dense_vof_v2 | random                           |      0.1 |      100 |         10 |          0.00952119 |           0.000952119 |                 0.3      |           0.534722 |
| dense_vof_v2 | random                           |      0.2 |      100 |         20 |         -0.00559295 |          -0.00111859  |                 0.35     |           0.534722 |
| dense_vof_v2 | random                           |      0.3 |      100 |         30 |          0.00168592 |           0.000505777 |                 0.4      |           0.534722 |
| dense_vof_v2 | oracle                           |      0.1 |      100 |         10 |          0.137893   |           0.0137893   |                 1        |           1        |
| dense_vof_v2 | oracle                           |      0.2 |      100 |         20 |          0.0942551  |           0.018851    |                 1        |           1        |
| dense_vof_v2 | oracle                           |      0.3 |      100 |         30 |          0.0643148  |           0.0192944   |                 1        |           1        |
| dense_vof_v2 | value_range                      |      0.1 |      100 |         10 |         -0.00867599 |          -0.000867599 |                 0.2      |           0.379557 |
| dense_vof_v2 | value_range                      |      0.2 |      100 |         20 |         -0.0235283  |          -0.00470566  |                 0.15     |           0.379557 |
| dense_vof_v2 | value_range                      |      0.3 |      100 |         30 |         -0.0173702  |          -0.00521105  |                 0.2      |           0.379557 |
| dense_vof_v2 | action_first_step_l2_std         |      0.1 |      100 |         10 |         -0.015835   |          -0.0015835   |                 0.3      |           0.523438 |
| dense_vof_v2 | action_first_step_l2_std         |      0.2 |      100 |         20 |         -0.00913297 |          -0.00182659  |                 0.35     |           0.523438 |
| dense_vof_v2 | action_first_step_l2_std         |      0.3 |      100 |         30 |         -0.0038612  |          -0.00115836  |                 0.4      |           0.523438 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.1 |      100 |         10 |          0.0401487  |           0.00401487  |                 0.5      |           0.668837 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.2 |      100 |         20 |          0.0374028  |           0.00748055  |                 0.5      |           0.668837 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.3 |      100 |         30 |          0.0221454  |           0.00664361  |                 0.466667 |           0.668837 |
| terminal_vof | grouped_oof_ridge                |      0.1 |       19 |          2 |          0          |           0           |                 0        |         nan        |
| terminal_vof | grouped_oof_ridge                |      0.2 |       19 |          4 |          0          |           0           |                 0        |         nan        |
| terminal_vof | grouped_oof_ridge                |      0.3 |       19 |          6 |          0          |           0           |                 0        |         nan        |
| terminal_vof | random                           |      0.1 |       19 |          2 |         -0.25       |          -0.0263158   |                 0        |         nan        |
| terminal_vof | random                           |      0.2 |       19 |          4 |         -0.125      |          -0.0263158   |                 0        |         nan        |
| terminal_vof | random                           |      0.3 |       19 |          6 |         -0.166667   |          -0.0526316   |                 0        |         nan        |
| terminal_vof | oracle                           |      0.1 |       19 |          2 |          0          |           0           |                 0        |         nan        |
| terminal_vof | oracle                           |      0.2 |       19 |          4 |          0          |           0           |                 0        |         nan        |
| terminal_vof | oracle                           |      0.3 |       19 |          6 |          0          |           0           |                 0        |         nan        |
| terminal_vof | value_range                      |      0.1 |       19 |          2 |         -1.75       |          -0.184211    |                 0        |         nan        |
| terminal_vof | value_range                      |      0.2 |       19 |          4 |         -0.875      |          -0.184211    |                 0        |         nan        |
| terminal_vof | value_range                      |      0.3 |       19 |          6 |         -0.583333   |          -0.184211    |                 0        |         nan        |
| terminal_vof | action_first_step_l2_std         |      0.1 |       19 |          2 |         -1.75       |          -0.184211    |                 0        |         nan        |
| terminal_vof | action_first_step_l2_std         |      0.2 |       19 |          4 |         -0.875      |          -0.184211    |                 0        |         nan        |
| terminal_vof | action_first_step_l2_std         |      0.3 |       19 |          6 |         -0.583333   |          -0.184211    |                 0        |         nan        |
| terminal_vof | planning_predicted_proprio_error |      0.1 |       19 |          2 |          0          |           0           |                 0        |         nan        |
| terminal_vof | planning_predicted_proprio_error |      0.2 |       19 |          4 |         -0.125      |          -0.0263158   |                 0        |         nan        |
| terminal_vof | planning_predicted_proprio_error |      0.3 |       19 |          6 |         -0.0833333  |          -0.0263158   |                 0        |         nan        |

## Exact-state candidate ranking

| utility             | method                      | factor   |   snapshots |   mean_selected_utility |   mean_regret |   top1_accuracy |
|:--------------------|:----------------------------|:---------|------------:|------------------------:|--------------:|----------------:|
| local_utility_v1    | cosmos_value                | Object   |         100 |                0        |     0         |        1        |
| local_utility_v1    | oracle                      | Object   |         100 |                0        |     0         |        1        |
| local_utility_v1    | random                      | Object   |         100 |                0        |     0         |        1        |
| local_utility_v1    | value_minus_internal_action | Object   |         100 |                0        |     0         |        1        |
| dense_utility_v2    | cosmos_value                | Object   |         100 |                0.335533 |     0.0201921 |        0.44     |
| dense_utility_v2    | oracle                      | Object   |         100 |                0.355725 |     0         |        1        |
| dense_utility_v2    | random                      | Object   |         100 |                0.340828 |     0.0148976 |        0.25     |
| dense_utility_v2    | value_minus_internal_action | Object   |         100 |                0.342695 |     0.0130299 |        0.37     |
| terminal_utility_v1 | cosmos_value                | Object   |          19 |                2.68421  |     0.315789  |        0.894737 |
| terminal_utility_v1 | oracle                      | Object   |          19 |                3        |     0         |        1        |
| terminal_utility_v1 | random                      | Object   |          19 |                2.68421  |     0.315789  |        0.894737 |
| terminal_utility_v1 | value_minus_internal_action | Object   |          19 |                2.63158  |     0.368421  |        0.894737 |

## Interpretation rules

- P1 passes the pilot gate only if grouped OOF routing beats deterministic random routing at matched budget.
- P2 passes only if a non-oracle ranker reduces held-out regret relative to Cosmos value on every OOD factor.
- Local utility is a mechanism label; terminal success/safety continuation is the stronger endpoint.
- An apparently high AUROC is not confirmatory when positive/negative support is sparse or confined to different factors.
- States above the replay-integrity threshold must be reported and excluded in a strict sensitivity analysis.

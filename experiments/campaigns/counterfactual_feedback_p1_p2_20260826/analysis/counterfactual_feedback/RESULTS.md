# Counterfactual feedback and grounded candidate pilot

- Collected snapshot rows: **272**; unique pooled states: **272**.
- Candidate branch outcomes: **1088**.
- Snapshots with terminal continuation: **52**.
- Maximum main/open replay state error: **2.899e-05**.
- Replay integrity failures at the preregistered `1e-9` threshold: **7/272**.
- Non-zero local VoF labels: **0**.
- Terminal VoF support: **3 positive / 3 negative / 46 zero**.
- Candidate states with non-tied local/terminal utility: **0 / 9**.

## VoF by factor and phase

| target       | factor      | phase     |   states |   mean_vof |   median_vof |   positive_rate |   negative_rate |
|:-------------|:------------|:----------|---------:|-----------:|-------------:|----------------:|----------------:|
| local_vof    | Environment | approach  |       40 |     0      |            0 |           0     |            0    |
| local_vof    | Environment | grasp     |       40 |     0      |            0 |           0     |            0    |
| local_vof    | Environment | transport |       20 |     0      |            0 |           0     |            0    |
| local_vof    | Object      | approach  |       36 |     0      |            0 |           0     |            0    |
| local_vof    | Object      | grasp     |       35 |     0      |            0 |           0     |            0    |
| local_vof    | Object      | release   |        1 |     0      |            0 |           0     |            0    |
| local_vof    | Object      | transport |       28 |     0      |            0 |           0     |            0    |
| local_vof    | Position    | approach  |       40 |     0      |            0 |           0     |            0    |
| local_vof    | Position    | grasp     |       17 |     0      |            0 |           0     |            0    |
| local_vof    | Position    | transport |       15 |     0      |            0 |           0     |            0    |
| terminal_vof | Environment | approach  |        8 |     0.4375 |            0 |           0.25  |            0    |
| terminal_vof | Environment | grasp     |        8 |     0.0625 |            0 |           0.125 |            0    |
| terminal_vof | Environment | transport |        4 |     0      |            0 |           0     |            0    |
| terminal_vof | Object      | approach  |        8 |    -0.4375 |            0 |           0     |            0.25 |
| terminal_vof | Object      | grasp     |        5 |    -0.1    |            0 |           0     |            0.2  |
| terminal_vof | Object      | transport |        6 |     0      |            0 |           0     |            0    |
| terminal_vof | Position    | approach  |        8 |     0      |            0 |           0     |            0    |
| terminal_vof | Position    | grasp     |        2 |     0      |            0 |           0     |            0    |
| terminal_vof | Position    | transport |        3 |     0      |            0 |           0     |            0    |

## Grouped out-of-fold predictor

| target       |   states | features                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |      mae |   correlation |   sign_accuracy |   positive_vof_auc |
|:-------------|---------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------:|--------------:|----------------:|-------------------:|
| local_vof    |      272 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0        |    nan        |             1   |         nan        |
| terminal_vof |       52 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.373977 |      0.246256 |             0.5 |           0.979592 |

## Uplift at fixed query budget

| target       | method                           |   budget |   states |   selected |   mean_vof_selected |   uplift_per_decision |   positive_rate_selected |   positive_vof_auc |
|:-------------|:---------------------------------|---------:|---------:|-----------:|--------------------:|----------------------:|-------------------------:|-------------------:|
| local_vof    | grouped_oof_ridge                |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | grouped_oof_ridge                |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | grouped_oof_ridge                |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| local_vof    | random                           |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | random                           |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | random                           |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| local_vof    | oracle                           |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | oracle                           |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | oracle                           |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| local_vof    | value_range                      |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | value_range                      |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | value_range                      |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| local_vof    | action_first_step_l2_std         |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | action_first_step_l2_std         |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | action_first_step_l2_std         |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.1 |      272 |         28 |           0         |            0          |                0         |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.2 |      272 |         55 |           0         |            0          |                0         |         nan        |
| local_vof    | planning_predicted_proprio_error |      0.3 |      272 |         82 |           0         |            0          |                0         |         nan        |
| terminal_vof | grouped_oof_ridge                |      0.1 |       52 |          6 |           0.666667  |            0.0769231  |                0.5       |           0.979592 |
| terminal_vof | grouped_oof_ridge                |      0.2 |       52 |         11 |           0.363636  |            0.0769231  |                0.272727  |           0.979592 |
| terminal_vof | grouped_oof_ridge                |      0.3 |       52 |         16 |           0.25      |            0.0769231  |                0.1875    |           0.979592 |
| terminal_vof | random                           |      0.1 |       52 |          6 |           0         |            0          |                0.166667  |           0.591837 |
| terminal_vof | random                           |      0.2 |       52 |         11 |          -0.0454545 |           -0.00961538 |                0.0909091 |           0.591837 |
| terminal_vof | random                           |      0.3 |       52 |         16 |          -0.03125   |           -0.00961538 |                0.0625    |           0.591837 |
| terminal_vof | oracle                           |      0.1 |       52 |          6 |           0.666667  |            0.0769231  |                0.5       |           1        |
| terminal_vof | oracle                           |      0.2 |       52 |         11 |           0.363636  |            0.0769231  |                0.272727  |           1        |
| terminal_vof | oracle                           |      0.3 |       52 |         16 |           0.25      |            0.0769231  |                0.1875    |           1        |
| terminal_vof | value_range                      |      0.1 |       52 |          6 |          -0.0833333 |           -0.00961538 |                0         |           0.62585  |
| terminal_vof | value_range                      |      0.2 |       52 |         11 |          -0.318182  |           -0.0673077  |                0         |           0.62585  |
| terminal_vof | value_range                      |      0.3 |       52 |         16 |          -0.03125   |           -0.00961538 |                0.0625    |           0.62585  |
| terminal_vof | action_first_step_l2_std         |      0.1 |       52 |          6 |          -0.0833333 |           -0.00961538 |                0.166667  |           0.727891 |
| terminal_vof | action_first_step_l2_std         |      0.2 |       52 |         11 |          -0.0454545 |           -0.00961538 |                0.0909091 |           0.727891 |
| terminal_vof | action_first_step_l2_std         |      0.3 |       52 |         16 |           0         |            0          |                0.125     |           0.727891 |
| terminal_vof | planning_predicted_proprio_error |      0.1 |       52 |          6 |           0.0833333 |            0.00961538 |                0.166667  |           0.510204 |
| terminal_vof | planning_predicted_proprio_error |      0.2 |       52 |         11 |           0         |            0          |                0.0909091 |           0.510204 |
| terminal_vof | planning_predicted_proprio_error |      0.3 |       52 |         16 |           0         |            0          |                0.0625    |           0.510204 |

## Exact-state candidate ranking

| utility             | method                      | factor      |   snapshots |   mean_selected_utility |   mean_regret |   top1_accuracy |
|:--------------------|:----------------------------|:------------|------------:|------------------------:|--------------:|----------------:|
| local_utility_v1    | cosmos_value                | Environment |         100 |                -0.01    |     0         |        1        |
| local_utility_v1    | cosmos_value                | Object      |         100 |                 0       |     0         |        1        |
| local_utility_v1    | cosmos_value                | Position    |          72 |                 0       |     0         |        1        |
| local_utility_v1    | oracle                      | Environment |         100 |                -0.01    |     0         |        1        |
| local_utility_v1    | oracle                      | Object      |         100 |                 0       |     0         |        1        |
| local_utility_v1    | oracle                      | Position    |          72 |                 0       |     0         |        1        |
| local_utility_v1    | random                      | Environment |         100 |                -0.01    |     0         |        1        |
| local_utility_v1    | random                      | Object      |         100 |                 0       |     0         |        1        |
| local_utility_v1    | random                      | Position    |          72 |                 0       |     0         |        1        |
| local_utility_v1    | value_minus_internal_action | Environment |         100 |                -0.01    |     0         |        1        |
| local_utility_v1    | value_minus_internal_action | Object      |         100 |                 0       |     0         |        1        |
| local_utility_v1    | value_minus_internal_action | Position    |          72 |                 0       |     0         |        1        |
| terminal_utility_v1 | cosmos_value                | Environment |          20 |                 1.275   |     0.05      |        0.9      |
| terminal_utility_v1 | cosmos_value                | Object      |          19 |                 2.68421 |     0.315789  |        0.894737 |
| terminal_utility_v1 | cosmos_value                | Position    |          13 |                 2       |     0.0384615 |        0.923077 |
| terminal_utility_v1 | oracle                      | Environment |          20 |                 1.325   |     0         |        1        |
| terminal_utility_v1 | oracle                      | Object      |          19 |                 3       |     0         |        1        |
| terminal_utility_v1 | oracle                      | Position    |          13 |                 2.03846 |     0         |        1        |
| terminal_utility_v1 | random                      | Environment |          20 |                 1.275   |     0.05      |        0.9      |
| terminal_utility_v1 | random                      | Object      |          19 |                 2.68421 |     0.315789  |        0.894737 |
| terminal_utility_v1 | random                      | Position    |          13 |                 2       |     0.0384615 |        0.923077 |
| terminal_utility_v1 | value_minus_internal_action | Environment |          20 |                 1.275   |     0.05      |        0.9      |
| terminal_utility_v1 | value_minus_internal_action | Object      |          19 |                 2.63158 |     0.368421  |        0.894737 |
| terminal_utility_v1 | value_minus_internal_action | Position    |          13 |                 2       |     0.0384615 |        0.923077 |

## Interpretation rules

- P1 passes the pilot gate only if grouped OOF routing beats deterministic random routing at matched budget.
- P2 passes only if a non-oracle ranker reduces held-out regret relative to Cosmos value on every OOD factor.
- Local utility is a mechanism label; terminal success/safety continuation is the stronger endpoint.
- An apparently high AUROC is not confirmatory when positive/negative support is sparse or confined to different factors.
- States above the replay-integrity threshold must be reported and excluded in a strict sensitivity analysis.

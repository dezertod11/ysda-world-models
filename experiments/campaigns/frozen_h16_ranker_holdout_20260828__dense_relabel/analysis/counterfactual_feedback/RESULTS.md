# Counterfactual feedback and grounded candidate pilot

- Collected snapshot rows: **240**; unique pooled states: **240**.
- Candidate branch outcomes: **1440**.
- Snapshots with terminal continuation: **0**.
- Maximum main/open replay state error: **1.587e-02**.
- Replay integrity failures at the preregistered `1e-9` threshold: **10/240**.
- `local_vof` support: **2 positive / 0 negative / 238 zero**.
- `dense_vof_v2` support: **105 positive / 130 negative / 5 zero**.
- `terminal_vof` support: **0 positive / 0 negative / 0 zero**.
- Candidate states with non-tied utility: `local_utility_v1`=1, `dense_utility_v2`=236.

## VoF by factor and phase

| target       | factor      | phase     |   states |     mean_vof |   median_vof |   positive_rate |   negative_rate |
|:-------------|:------------|:----------|---------:|-------------:|-------------:|----------------:|----------------:|
| local_vof    | Environment | approach  |       46 |  0.0217391   |   0          |       0.0434783 |        0        |
| local_vof    | Environment | grasp     |       23 |  0           |   0          |       0         |        0        |
| local_vof    | Environment | transport |       11 |  0           |   0          |       0         |        0        |
| local_vof    | Object      | approach  |       26 |  0           |   0          |       0         |        0        |
| local_vof    | Object      | grasp     |       26 |  0           |   0          |       0         |        0        |
| local_vof    | Object      | transport |       28 |  0           |   0          |       0         |        0        |
| local_vof    | Position    | approach  |       80 |  0           |   0          |       0         |        0        |
| dense_vof_v2 | Environment | approach  |       46 |  0.0190875   |  -0.00191288 |       0.413043  |        0.543478 |
| dense_vof_v2 | Environment | grasp     |       23 | -0.0132942   |   0.00280365 |       0.608696  |        0.391304 |
| dense_vof_v2 | Environment | transport |       11 | -0.0128019   |  -0.0125903  |       0.181818  |        0.818182 |
| dense_vof_v2 | Object      | approach  |       26 | -0.00903773  |  -0.00403655 |       0.307692  |        0.692308 |
| dense_vof_v2 | Object      | grasp     |       26 | -0.0109716   |  -0.00241952 |       0.423077  |        0.576923 |
| dense_vof_v2 | Object      | transport |       28 |  0.000431521 |   0          |       0.464286  |        0.428571 |
| dense_vof_v2 | Position    | approach  |       80 |  3.79694e-05 |  -0.00065503 |       0.475     |        0.525    |

## Grouped out-of-fold predictor

| target       | model                 |   states |   available_groups |   evaluated_groups | features                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |        mae |   correlation |   sign_accuracy |   positive_vof_auc |
|:-------------|:----------------------|---------:|-------------------:|-------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------:|--------------:|----------------:|-------------------:|
| local_vof    | grouped_oof_ridge     |      240 |                 69 |                 69 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0122962  |     0.121943  |        0.375    |           0.901261 |
| local_vof    | factor_phase_oof_mean |      240 |                 69 |                 69 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.00832552 |     0.0846846 |        0.816667 |           0.842437 |
| dense_vof_v2 | grouped_oof_ridge     |      240 |                 69 |                 69 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0368977  |     0.230237  |        0.545833 |           0.578554 |
| dense_vof_v2 | factor_phase_oof_mean |      240 |                 69 |                 69 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.0347856  |    -0.0072835 |        0.445833 |           0.45358  |

## Factor-wise grouped out-of-fold predictor

| factor      | target       | model                 |   states |   available_groups |   evaluated_groups | features                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |       mae |   correlation |   sign_accuracy |   positive_vof_auc |
|:------------|:-------------|:----------------------|---------:|-------------------:|-------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------:|--------------:|----------------:|-------------------:|
| Environment | local_vof    | grouped_oof_ridge     |       80 |                 23 |                 23 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0361825 |     0.223651  |          0.425  |           0.935897 |
| Environment | local_vof    | factor_phase_oof_mean |       80 |                 23 |                 23 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.0241885 |     0.020513  |          0.45   |           0.544872 |
| Environment | dense_vof_v2 | grouped_oof_ridge     |       80 |                 23 |                 23 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0619992 |     0.242733  |          0.6875 |           0.709841 |
| Environment | dense_vof_v2 | factor_phase_oof_mean |       80 |                 23 |                 23 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.0550693 |     0.0135545 |          0.4625 |           0.395556 |
| Object      | local_vof    | grouped_oof_ridge     |       80 |                 26 |                 26 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0         |   nan         |          1      |         nan        |
| Object      | local_vof    | factor_phase_oof_mean |       80 |                 26 |                 26 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0         |   nan         |          1      |         nan        |
| Object      | dense_vof_v2 | grouped_oof_ridge     |       80 |                 26 |                 26 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0283134 |     0.0666618 |          0.6125 |           0.598958 |
| Object      | dense_vof_v2 | factor_phase_oof_mean |       80 |                 26 |                 26 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.021286  |    -0.22499   |          0.525  |           0.486654 |
| Position    | local_vof    | grouped_oof_ridge     |       80 |                 20 |                 20 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0         |   nan         |          1      |         nan        |
| Position    | local_vof    | factor_phase_oof_mean |       80 |                 20 |                 20 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0         |   nan         |          1      |         nan        |
| Position    | dense_vof_v2 | grouped_oof_ridge     |       80 |                 20 |                 20 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0267916 |     0.351902  |          0.6125 |           0.657268 |
| Position    | dense_vof_v2 | factor_phase_oof_mean |       80 |                 20 |                 20 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.0288158 |    -0.377342  |          0.325  |           0.309524 |

### Dense VoF uplift by factor

| factor      | target       | method                           |   budget |   states |   selected |   mean_vof_selected |   uplift_per_decision |   positive_rate_selected |   positive_vof_auc |
|:------------|:-------------|:---------------------------------|---------:|---------:|-----------:|--------------------:|----------------------:|-------------------------:|-------------------:|
| Environment | dense_vof_v2 | grouped_oof_ridge                |      0.1 |       80 |          8 |          0.0208612  |           0.00208612  |                 0.75     |           0.709841 |
| Environment | dense_vof_v2 | grouped_oof_ridge                |      0.2 |       80 |         16 |          0.0909669  |           0.0181934   |                 0.6875   |           0.709841 |
| Environment | dense_vof_v2 | grouped_oof_ridge                |      0.3 |       80 |         24 |          0.060744   |           0.0182232   |                 0.666667 |           0.709841 |
| Environment | dense_vof_v2 | random                           |      0.1 |       80 |          8 |          0.0562539  |           0.00562539  |                 0.5      |           0.467302 |
| Environment | dense_vof_v2 | random                           |      0.2 |       80 |         16 |          0.0136705  |           0.00273409  |                 0.375    |           0.467302 |
| Environment | dense_vof_v2 | random                           |      0.3 |       80 |         24 |          0.00932865 |           0.0027986   |                 0.458333 |           0.467302 |
| Environment | dense_vof_v2 | factor_phase_oof_mean            |      0.1 |       80 |          8 |          0.00434375 |           0.000434375 |                 0.25     |           0.395556 |
| Environment | dense_vof_v2 | factor_phase_oof_mean            |      0.2 |       80 |         16 |         -0.00758338 |          -0.00151668  |                 0.3125   |           0.395556 |
| Environment | dense_vof_v2 | factor_phase_oof_mean            |      0.3 |       80 |         24 |         -0.00743061 |          -0.00222918  |                 0.291667 |           0.395556 |
| Environment | dense_vof_v2 | planning_predicted_proprio_error |      0.1 |       80 |          8 |          0.0431783  |           0.00431783  |                 0.75     |           0.63619  |
| Environment | dense_vof_v2 | planning_predicted_proprio_error |      0.2 |       80 |         16 |          0.0170125  |           0.0034025   |                 0.5625   |           0.63619  |
| Environment | dense_vof_v2 | planning_predicted_proprio_error |      0.3 |       80 |         24 |          0.063478   |           0.0190434   |                 0.583333 |           0.63619  |
| Object      | dense_vof_v2 | grouped_oof_ridge                |      0.1 |       80 |          8 |         -0.00808035 |          -0.000808035 |                 0.5      |           0.598958 |
| Object      | dense_vof_v2 | grouped_oof_ridge                |      0.2 |       80 |         16 |         -0.00504997 |          -0.00100999  |                 0.375    |           0.598958 |
| Object      | dense_vof_v2 | grouped_oof_ridge                |      0.3 |       80 |         24 |         -0.00568917 |          -0.00170675  |                 0.458333 |           0.598958 |
| Object      | dense_vof_v2 | random                           |      0.1 |       80 |          8 |         -0.00463257 |          -0.000463257 |                 0.5      |           0.461589 |
| Object      | dense_vof_v2 | random                           |      0.2 |       80 |         16 |          0.00487455 |           0.00097491  |                 0.375    |           0.461589 |
| Object      | dense_vof_v2 | random                           |      0.3 |       80 |         24 |         -0.00159328 |          -0.000477983 |                 0.375    |           0.461589 |
| Object      | dense_vof_v2 | factor_phase_oof_mean            |      0.1 |       80 |          8 |         -0.0419032  |          -0.00419032  |                 0.25     |           0.486654 |
| Object      | dense_vof_v2 | factor_phase_oof_mean            |      0.2 |       80 |         16 |         -0.0216731  |          -0.00433463  |                 0.3125   |           0.486654 |
| Object      | dense_vof_v2 | factor_phase_oof_mean            |      0.3 |       80 |         24 |         -0.0147043  |          -0.00441128  |                 0.333333 |           0.486654 |
| Object      | dense_vof_v2 | planning_predicted_proprio_error |      0.1 |       80 |          8 |          0.00100087 |           0.000100087 |                 0.375    |           0.500651 |
| Object      | dense_vof_v2 | planning_predicted_proprio_error |      0.2 |       80 |         16 |         -0.0207637  |          -0.00415273  |                 0.3125   |           0.500651 |
| Object      | dense_vof_v2 | planning_predicted_proprio_error |      0.3 |       80 |         24 |         -0.0153567  |          -0.00460702  |                 0.333333 |           0.500651 |
| Position    | dense_vof_v2 | grouped_oof_ridge                |      0.1 |       80 |          8 |          0.0336245  |           0.00336245  |                 0.625    |           0.657268 |
| Position    | dense_vof_v2 | grouped_oof_ridge                |      0.2 |       80 |         16 |          0.0260955  |           0.00521909  |                 0.75     |           0.657268 |
| Position    | dense_vof_v2 | grouped_oof_ridge                |      0.3 |       80 |         24 |          0.0156778  |           0.00470335  |                 0.583333 |           0.657268 |
| Position    | dense_vof_v2 | random                           |      0.1 |       80 |          8 |         -0.0037849  |          -0.00037849  |                 0.375    |           0.469298 |
| Position    | dense_vof_v2 | random                           |      0.2 |       80 |         16 |          0.00242776 |           0.000485552 |                 0.5      |           0.469298 |
| Position    | dense_vof_v2 | random                           |      0.3 |       80 |         24 |         -0.00121623 |          -0.000364868 |                 0.458333 |           0.469298 |
| Position    | dense_vof_v2 | factor_phase_oof_mean            |      0.1 |       80 |          8 |         -0.0162647  |          -0.00162647  |                 0.375    |           0.309524 |
| Position    | dense_vof_v2 | factor_phase_oof_mean            |      0.2 |       80 |         16 |         -0.0148912  |          -0.00297824  |                 0.25     |           0.309524 |
| Position    | dense_vof_v2 | factor_phase_oof_mean            |      0.3 |       80 |         24 |         -0.0177348  |          -0.00532045  |                 0.291667 |           0.309524 |
| Position    | dense_vof_v2 | planning_predicted_proprio_error |      0.1 |       80 |          8 |          0.0497056  |           0.00497056  |                 0.875    |           0.537594 |
| Position    | dense_vof_v2 | planning_predicted_proprio_error |      0.2 |       80 |         16 |          0.0297571  |           0.00595142  |                 0.75     |           0.537594 |
| Position    | dense_vof_v2 | planning_predicted_proprio_error |      0.3 |       80 |         24 |          0.0201774  |           0.00605323  |                 0.625    |           0.537594 |

## Uplift at fixed query budget

| target       | method                           |   budget |   states |   selected |   mean_vof_selected |   uplift_per_decision |   positive_rate_selected |   positive_vof_auc |
|:-------------|:---------------------------------|---------:|---------:|-----------:|--------------------:|----------------------:|-------------------------:|-------------------:|
| local_vof    | grouped_oof_ridge                |      0.1 |      240 |         24 |          0.0208333  |            0.00208333 |                0.0416667 |           0.901261 |
| local_vof    | grouped_oof_ridge                |      0.2 |      240 |         48 |          0.0208333  |            0.00416667 |                0.0416667 |           0.901261 |
| local_vof    | grouped_oof_ridge                |      0.3 |      240 |         72 |          0.0138889  |            0.00416667 |                0.0277778 |           0.901261 |
| local_vof    | random                           |      0.1 |      240 |         24 |          0.0416667  |            0.00416667 |                0.0833333 |           0.928571 |
| local_vof    | random                           |      0.2 |      240 |         48 |          0.0208333  |            0.00416667 |                0.0416667 |           0.928571 |
| local_vof    | random                           |      0.3 |      240 |         72 |          0.0138889  |            0.00416667 |                0.0277778 |           0.928571 |
| local_vof    | oracle                           |      0.1 |      240 |         24 |          0.0416667  |            0.00416667 |                0.0833333 |           1        |
| local_vof    | oracle                           |      0.2 |      240 |         48 |          0.0208333  |            0.00416667 |                0.0416667 |           1        |
| local_vof    | oracle                           |      0.3 |      240 |         72 |          0.0138889  |            0.00416667 |                0.0277778 |           1        |
| local_vof    | factor_phase_oof_mean            |      0.1 |      240 |         24 |          0          |            0          |                0         |           0.842437 |
| local_vof    | factor_phase_oof_mean            |      0.2 |      240 |         48 |          0.0208333  |            0.00416667 |                0.0416667 |           0.842437 |
| local_vof    | factor_phase_oof_mean            |      0.3 |      240 |         72 |          0.0138889  |            0.00416667 |                0.0277778 |           0.842437 |
| local_vof    | value_range                      |      0.1 |      240 |         24 |          0          |            0          |                0         |           0.256303 |
| local_vof    | value_range                      |      0.2 |      240 |         48 |          0          |            0          |                0         |           0.256303 |
| local_vof    | value_range                      |      0.3 |      240 |         72 |          0          |            0          |                0         |           0.256303 |
| local_vof    | action_first_step_l2_std         |      0.1 |      240 |         24 |          0          |            0          |                0         |           0.14916  |
| local_vof    | action_first_step_l2_std         |      0.2 |      240 |         48 |          0          |            0          |                0         |           0.14916  |
| local_vof    | action_first_step_l2_std         |      0.3 |      240 |         72 |          0          |            0          |                0         |           0.14916  |
| local_vof    | planning_predicted_proprio_error |      0.1 |      240 |         24 |          0          |            0          |                0         |           0.85084  |
| local_vof    | planning_predicted_proprio_error |      0.2 |      240 |         48 |          0.0208333  |            0.00416667 |                0.0416667 |           0.85084  |
| local_vof    | planning_predicted_proprio_error |      0.3 |      240 |         72 |          0.0138889  |            0.00416667 |                0.0277778 |           0.85084  |
| dense_vof_v2 | grouped_oof_ridge                |      0.1 |      240 |         24 |          0.0234523  |            0.00234523 |                0.583333  |           0.578554 |
| dense_vof_v2 | grouped_oof_ridge                |      0.2 |      240 |         48 |          0.0421304  |            0.00842608 |                0.583333  |           0.578554 |
| dense_vof_v2 | grouped_oof_ridge                |      0.3 |      240 |         72 |          0.0258553  |            0.0077566  |                0.541667  |           0.578554 |
| dense_vof_v2 | random                           |      0.1 |      240 |         24 |          0.0186495  |            0.00186495 |                0.5       |           0.472451 |
| dense_vof_v2 | random                           |      0.2 |      240 |         48 |          0.00238505 |            0.00047701 |                0.416667  |           0.472451 |
| dense_vof_v2 | random                           |      0.3 |      240 |         72 |          0.00369515 |            0.00110855 |                0.430556  |           0.472451 |
| dense_vof_v2 | oracle                           |      0.1 |      240 |         24 |          0.128547   |            0.0128547  |                1         |           1        |
| dense_vof_v2 | oracle                           |      0.2 |      240 |         48 |          0.0726464  |            0.0145293  |                1         |           1        |
| dense_vof_v2 | oracle                           |      0.3 |      240 |         72 |          0.0510153  |            0.0153046  |                1         |           1        |
| dense_vof_v2 | factor_phase_oof_mean            |      0.1 |      240 |         24 |         -0.004338   |           -0.0004338  |                0.458333  |           0.45358  |
| dense_vof_v2 | factor_phase_oof_mean            |      0.2 |      240 |         48 |          0.0130826  |            0.00261652 |                0.416667  |           0.45358  |
| dense_vof_v2 | factor_phase_oof_mean            |      0.3 |      240 |         72 |          0.00408839 |            0.00122652 |                0.347222  |           0.45358  |
| dense_vof_v2 | value_range                      |      0.1 |      240 |         24 |         -0.0110317  |           -0.00110317 |                0.333333  |           0.459965 |
| dense_vof_v2 | value_range                      |      0.2 |      240 |         48 |         -0.0089625  |           -0.0017925  |                0.395833  |           0.459965 |
| dense_vof_v2 | value_range                      |      0.3 |      240 |         72 |         -0.00913566 |           -0.0027407  |                0.416667  |           0.459965 |
| dense_vof_v2 | action_first_step_l2_std         |      0.1 |      240 |         24 |          0.0121172  |            0.00121172 |                0.541667  |           0.52134  |
| dense_vof_v2 | action_first_step_l2_std         |      0.2 |      240 |         48 |          0.00800848 |            0.0016017  |                0.520833  |           0.52134  |
| dense_vof_v2 | action_first_step_l2_std         |      0.3 |      240 |         72 |          0.00498253 |            0.00149476 |                0.486111  |           0.52134  |
| dense_vof_v2 | planning_predicted_proprio_error |      0.1 |      240 |         24 |          0.0322437  |            0.00322437 |                0.791667  |           0.567831 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.2 |      240 |         48 |          0.0415662  |            0.00831323 |                0.604167  |           0.567831 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.3 |      240 |         72 |          0.0278685  |            0.00836056 |                0.555556  |           0.567831 |

## Exact-state candidate ranking

| utility          | method                      | factor      |   snapshots |   mean_selected_utility |   mean_regret |   top1_accuracy |
|:-----------------|:----------------------------|:------------|------------:|------------------------:|--------------:|----------------:|
| local_utility_v1 | cosmos_value                | Environment |          80 |             -0.05       |    0.00625    |          0.9875 |
| local_utility_v1 | cosmos_value                | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | cosmos_value                | Position    |          80 |              0          |    0          |          1      |
| local_utility_v1 | factor_oof_candidate_ridge  | Environment |          80 |             -0.05       |    0.00625    |          0.9875 |
| local_utility_v1 | factor_oof_candidate_ridge  | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | factor_oof_candidate_ridge  | Position    |          80 |              0          |    0          |          1      |
| local_utility_v1 | grouped_oof_candidate_ridge | Environment |          80 |             -0.05       |    0.00625    |          0.9875 |
| local_utility_v1 | grouped_oof_candidate_ridge | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | grouped_oof_candidate_ridge | Position    |          80 |              0          |    0          |          1      |
| local_utility_v1 | oracle                      | Environment |          80 |             -0.04375    |    0          |          1      |
| local_utility_v1 | oracle                      | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | oracle                      | Position    |          80 |              0          |    0          |          1      |
| local_utility_v1 | random                      | Environment |          80 |             -0.05       |    0.00625    |          0.9875 |
| local_utility_v1 | random                      | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | random                      | Position    |          80 |              0          |    0          |          1      |
| local_utility_v1 | value_minus_internal_action | Environment |          80 |             -0.05       |    0.00625    |          0.9875 |
| local_utility_v1 | value_minus_internal_action | Object      |          80 |              0.203125   |    0          |          1      |
| local_utility_v1 | value_minus_internal_action | Position    |          80 |              0          |    0          |          1      |
| dense_utility_v2 | cosmos_value                | Environment |          80 |              0.037026   |    0.0121131  |          0.1875 |
| dense_utility_v2 | cosmos_value                | Object      |          80 |              0.463748   |    0.0025641  |          0.3375 |
| dense_utility_v2 | cosmos_value                | Position    |          80 |             -0.00620505 |    0.013223   |          0.1125 |
| dense_utility_v2 | factor_oof_candidate_ridge  | Environment |          80 |              0.0387783  |    0.0103608  |          0.2375 |
| dense_utility_v2 | factor_oof_candidate_ridge  | Object      |          80 |              0.464501   |    0.00181181 |          0.3875 |
| dense_utility_v2 | factor_oof_candidate_ridge  | Position    |          80 |              0.00350964 |    0.00350829 |          0.45   |
| dense_utility_v2 | grouped_oof_candidate_ridge | Environment |          80 |              0.0388171  |    0.010322   |          0.275  |
| dense_utility_v2 | grouped_oof_candidate_ridge | Object      |          80 |              0.461985   |    0.00432747 |          0.2375 |
| dense_utility_v2 | grouped_oof_candidate_ridge | Position    |          80 |             -0.00233732 |    0.00935525 |          0.15   |
| dense_utility_v2 | oracle                      | Environment |          80 |              0.0491391  |    0          |          1      |
| dense_utility_v2 | oracle                      | Object      |          80 |              0.466312   |    0          |          1      |
| dense_utility_v2 | oracle                      | Position    |          80 |              0.00701793 |    0          |          1      |
| dense_utility_v2 | random                      | Environment |          80 |              0.0351619  |    0.0139772  |          0.125  |
| dense_utility_v2 | random                      | Object      |          80 |              0.456028   |    0.0102841  |          0.1    |
| dense_utility_v2 | random                      | Position    |          80 |             -0.00272269 |    0.00974062 |          0.2375 |
| dense_utility_v2 | value_minus_internal_action | Environment |          80 |              0.0377292  |    0.0114099  |          0.2125 |
| dense_utility_v2 | value_minus_internal_action | Object      |          80 |              0.462078   |    0.00423416 |          0.275  |
| dense_utility_v2 | value_minus_internal_action | Position    |          80 |             -0.00450622 |    0.0115242  |          0.0625 |

### Candidate OOF model diagnostics

| utility          | method                      |   candidate_rows | features                                                                                                                                                                                                                                                                                                                    |   centered_utility_correlation |
|:-----------------|:----------------------------|-----------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------:|
| local_utility_v1 | grouped_oof_candidate_ridge |             1440 | candidate_value,candidate_first_action_l1,candidate_action_chunk_l1,candidate_action_chunk_l2,latent_action_copy_std_mean,latent_action_copy_std_max,latent_action_first_step_copy_l2_std,latent_future_proprio_copy_std_mean,latent_future_proprio_copy_std_max,latent_value_element_std_mean,latent_value_element_std_max |                    8.54963e-35 |
| local_utility_v1 | factor_oof_candidate_ridge  |             1440 | candidate_action_chunk_l1,candidate_action_chunk_l2,candidate_first_action_l1,candidate_value,latent_action_copy_std_max,latent_action_copy_std_mean,latent_action_first_step_copy_l2_std,latent_future_proprio_copy_std_max,latent_future_proprio_copy_std_mean,latent_value_element_std_max,latent_value_element_std_mean |                   -5.23832e-33 |
| dense_utility_v2 | grouped_oof_candidate_ridge |             1440 | candidate_value,candidate_first_action_l1,candidate_action_chunk_l1,candidate_action_chunk_l2,latent_action_copy_std_mean,latent_action_copy_std_max,latent_action_first_step_copy_l2_std,latent_future_proprio_copy_std_mean,latent_future_proprio_copy_std_max,latent_value_element_std_mean,latent_value_element_std_max |                    0.101638    |
| dense_utility_v2 | factor_oof_candidate_ridge  |             1440 | candidate_action_chunk_l1,candidate_action_chunk_l2,candidate_first_action_l1,candidate_value,latent_action_copy_std_max,latent_action_copy_std_mean,latent_action_first_step_copy_l2_std,latent_future_proprio_copy_std_max,latent_future_proprio_copy_std_mean,latent_value_element_std_max,latent_value_element_std_mean |                    0.248925    |

## Strict replay-integrity sensitivity

- States satisfying `main_open_replay_state_max_abs <= 1e-09`: **230/240**.

| target       | model                 |   states |   available_groups |   evaluated_groups | features                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |        mae |   correlation |   sign_accuracy |   positive_vof_auc |
|:-------------|:----------------------|---------:|-------------------:|-------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------:|--------------:|----------------:|-------------------:|
| local_vof    | grouped_oof_ridge     |      230 |                 69 |                 69 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0127132  |     0.12761   |        0.365217 |           0.901316 |
| local_vof    | factor_phase_oof_mean |      230 |                 69 |                 69 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.00855954 |     0.093736  |        0.821739 |           0.848684 |
| dense_vof_v2 | grouped_oof_ridge     |      230 |                 69 |                 69 | value_mean,value_std,value_range,action_std_mean,action_std_max,action_first_step_l2_std,action_pairwise_l2_mean,future_proprio_std_mean,future_image_pixel_std_mean,future_wrist_pixel_std_mean,latent_action_across_seed_std_mean,latent_future_proprio_across_seed_std_mean,latent_value_across_seed_std_mean,latent_action_copy_std_mean_mean_over_samples,latent_future_proprio_copy_std_mean_mean_over_samples,latent_value_element_std_mean_mean_over_samples,candidate_action_consensus_first_mean,candidate_action_consensus_chunk_mean,planning_predicted_proprio_error | 0.0368821  |     0.240605  |        0.53913  |           0.567708 |
| dense_vof_v2 | factor_phase_oof_mean |      230 |                 69 |                 69 | factor,phase_at_snapshot                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 0.0354137  |     0.0116677 |        0.443478 |           0.441368 |

| target       | method                           |   budget |   states |   selected |   mean_vof_selected |   uplift_per_decision |   positive_rate_selected |   positive_vof_auc |
|:-------------|:---------------------------------|---------:|---------:|-----------:|--------------------:|----------------------:|-------------------------:|-------------------:|
| dense_vof_v2 | grouped_oof_ridge                |      0.1 |      230 |         23 |          0.025386   |           0.0025386   |                 0.608696 |           0.567708 |
| dense_vof_v2 | grouped_oof_ridge                |      0.2 |      230 |         46 |          0.0411007  |           0.00822014  |                 0.565217 |           0.567708 |
| dense_vof_v2 | grouped_oof_ridge                |      0.3 |      230 |         69 |          0.0277758  |           0.00833275  |                 0.536232 |           0.567708 |
| dense_vof_v2 | random                           |      0.1 |      230 |         23 |          0.0190147  |           0.00190147  |                 0.478261 |           0.471584 |
| dense_vof_v2 | random                           |      0.2 |      230 |         46 |          0.00376244 |           0.000752488 |                 0.413043 |           0.471584 |
| dense_vof_v2 | random                           |      0.3 |      230 |         69 |          0.00277287 |           0.00083186  |                 0.434783 |           0.471584 |
| dense_vof_v2 | factor_phase_oof_mean            |      0.1 |      230 |         23 |         -0.00733301 |          -0.000733301 |                 0.434783 |           0.441368 |
| dense_vof_v2 | factor_phase_oof_mean            |      0.2 |      230 |         46 |          0.0125992  |           0.00251985  |                 0.413043 |           0.441368 |
| dense_vof_v2 | factor_phase_oof_mean            |      0.3 |      230 |         69 |          0.0045105  |           0.00135315  |                 0.347826 |           0.441368 |
| dense_vof_v2 | planning_predicted_proprio_error |      0.1 |      230 |         23 |          0.032604   |           0.0032604   |                 0.782609 |           0.56901  |
| dense_vof_v2 | planning_predicted_proprio_error |      0.2 |      230 |         46 |          0.0432462  |           0.00864923  |                 0.608696 |           0.56901  |
| dense_vof_v2 | planning_predicted_proprio_error |      0.3 |      230 |         69 |          0.0291782  |           0.00875346  |                 0.565217 |           0.56901  |

| utility          | method                      | factor      |   snapshots |   mean_selected_utility |   mean_regret |   top1_accuracy |
|:-----------------|:----------------------------|:------------|------------:|------------------------:|--------------:|----------------:|
| local_utility_v1 | cosmos_value                | Environment |          75 |             -0.0466667  |    0.00666667 |       0.986667  |
| local_utility_v1 | cosmos_value                | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | cosmos_value                | Position    |          80 |              0          |    0          |       1         |
| local_utility_v1 | factor_oof_candidate_ridge  | Environment |          75 |             -0.0466667  |    0.00666667 |       0.986667  |
| local_utility_v1 | factor_oof_candidate_ridge  | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | factor_oof_candidate_ridge  | Position    |          80 |              0          |    0          |       1         |
| local_utility_v1 | grouped_oof_candidate_ridge | Environment |          75 |             -0.0466667  |    0.00666667 |       0.986667  |
| local_utility_v1 | grouped_oof_candidate_ridge | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | grouped_oof_candidate_ridge | Position    |          80 |              0          |    0          |       1         |
| local_utility_v1 | oracle                      | Environment |          75 |             -0.04       |    0          |       1         |
| local_utility_v1 | oracle                      | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | oracle                      | Position    |          80 |              0          |    0          |       1         |
| local_utility_v1 | random                      | Environment |          75 |             -0.0466667  |    0.00666667 |       0.986667  |
| local_utility_v1 | random                      | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | random                      | Position    |          80 |              0          |    0          |       1         |
| local_utility_v1 | value_minus_internal_action | Environment |          75 |             -0.0466667  |    0.00666667 |       0.986667  |
| local_utility_v1 | value_minus_internal_action | Object      |          75 |              0.216667   |    0          |       1         |
| local_utility_v1 | value_minus_internal_action | Position    |          80 |              0          |    0          |       1         |
| dense_utility_v2 | cosmos_value                | Environment |          75 |              0.0376626  |    0.0122347  |       0.186667  |
| dense_utility_v2 | cosmos_value                | Object      |          75 |              0.4811     |    0.00268946 |       0.333333  |
| dense_utility_v2 | cosmos_value                | Position    |          80 |             -0.00620505 |    0.013223   |       0.1125    |
| dense_utility_v2 | factor_oof_candidate_ridge  | Environment |          75 |              0.0396039  |    0.0102933  |       0.226667  |
| dense_utility_v2 | factor_oof_candidate_ridge  | Object      |          75 |              0.482222   |    0.0015674  |       0.386667  |
| dense_utility_v2 | factor_oof_candidate_ridge  | Position    |          80 |              0.00350964 |    0.00350829 |       0.45      |
| dense_utility_v2 | grouped_oof_candidate_ridge | Environment |          75 |              0.0392318  |    0.0106654  |       0.24      |
| dense_utility_v2 | grouped_oof_candidate_ridge | Object      |          75 |              0.479746   |    0.00404296 |       0.24      |
| dense_utility_v2 | grouped_oof_candidate_ridge | Position    |          80 |             -0.00259552 |    0.00961345 |       0.1375    |
| dense_utility_v2 | oracle                      | Environment |          75 |              0.0498972  |    0          |       1         |
| dense_utility_v2 | oracle                      | Object      |          75 |              0.483789   |    0          |       1         |
| dense_utility_v2 | oracle                      | Position    |          80 |              0.00701793 |    0          |       1         |
| dense_utility_v2 | random                      | Environment |          75 |              0.0362431  |    0.0136541  |       0.133333  |
| dense_utility_v2 | random                      | Object      |          75 |              0.47323    |    0.010559   |       0.0933333 |
| dense_utility_v2 | random                      | Position    |          80 |             -0.00272269 |    0.00974062 |       0.2375    |
| dense_utility_v2 | value_minus_internal_action | Environment |          75 |              0.0383189  |    0.0115783  |       0.213333  |
| dense_utility_v2 | value_minus_internal_action | Object      |          75 |              0.479318   |    0.00447087 |       0.266667  |
| dense_utility_v2 | value_minus_internal_action | Position    |          80 |             -0.00450622 |    0.0115242  |       0.0625    |

## Matched H16/H32 consequence horizon

No matched H32 labels in this campaign.

No matched H32 candidate labels in this campaign.

## Interpretation rules

- P1 passes the pilot gate only if grouped OOF routing beats deterministic random routing at matched budget.
- P2 passes only if a non-oracle ranker reduces held-out regret relative to Cosmos value on every OOD factor.
- Local utility is a mechanism label; terminal success/safety continuation is the stronger endpoint.
- An apparently high AUROC is not confirmatory when positive/negative support is sparse or confined to different factors.
- States above the replay-integrity threshold are reported and excluded in the strict sensitivity section.

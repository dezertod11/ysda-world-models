# Eight-hour LIBERO validation analysis

- Query rows: 2823
- Episodes: 200
- Successes / failures: 108 / 92
- Cases: 3

This is an automatically generated inventory, not the final scientific
interpretation. The detector sweep contains many correlated variants.
The table below is restricted to q<=5 and alpha=0.1, and is ranked only
by calibration AUROC. Holdout metrics are never used for selection.

## Best holdout/generalization planning rows

| case_id                                    | experiment_split   | planning_strategy          |   planning_risk_lambda |   planning_action_weight | prediction_mode   |   num_samples |   num_open_loop_steps |   num_denoising_steps_action |   num_denoising_steps_future_state |   num_denoising_steps_value |   num_future_state_samples |   num_value_samples |   episodes |   successes |   success_rate |   wilson_low |   wilson_high |   mean_final_t |
|:-------------------------------------------|:-------------------|:---------------------------|-----------------------:|-------------------------:|:------------------|--------------:|----------------------:|-----------------------------:|-----------------------------------:|----------------------------:|---------------------------:|--------------------:|-----------:|------------:|---------------:|-------------:|--------------:|---------------:|
| long_mug_task4_init0_denoise10_replication | generalization     | max_value                  |                      0 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         30 |          25 |       0.833333 |     0.664353 |      0.926636 |        276.133 |
| long_mug_task4_init0_denoise10_replication | generalization     | uncertainty_penalty_action |                      1 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         30 |          21 |       0.7      |     0.521239 |      0.833354 |        315.433 |
| milk_task5_init0_denoise10_replication     | holdout            | uncertainty_penalty_action |                      1 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         40 |          22 |       0.55     |     0.398288 |      0.692949 |        174.475 |
| milk_task5_init0_denoise10_replication     | holdout            | max_value                  |                      0 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         40 |          19 |       0.475    |     0.329352 |      0.625029 |        185.625 |
| yellow_task8_init0_denoise10_replication   | generalization     | uncertainty_penalty_action |                      1 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         30 |          13 |       0.433333 |     0.273772 |      0.60803  |        187.467 |
| yellow_task8_init0_denoise10_replication   | generalization     | max_value                  |                      0 |                      0.5 | parallel          |             4 |                    16 |                           10 |                                  1 |                           1 |                          1 |                   1 |         30 |           8 |       0.266667 |     0.141825 |      0.444483 |        198     |

## Paired gains over max(value)

| case_id                                    | experiment_split   | prediction_mode   |   num_samples |   num_open_loop_steps |   num_denoising_steps_action | planning_strategy          |   planning_risk_lambda |   planning_action_weight |   paired_rollouts |   baseline_success_rate |   strategy_success_rate |   delta_success_rate |   wins |   losses |   ties |
|:-------------------------------------------|:-------------------|:------------------|--------------:|----------------------:|-----------------------------:|:---------------------------|-----------------------:|-------------------------:|------------------:|------------------------:|------------------------:|---------------------:|-------:|---------:|-------:|
| yellow_task8_init0_denoise10_replication   | generalization     | parallel          |             4 |                    16 |                           10 | uncertainty_penalty_action |                      1 |                      0.5 |                30 |                0.266667 |                0.433333 |             0.166667 |      7 |        2 |     21 |
| milk_task5_init0_denoise10_replication     | holdout            | parallel          |             4 |                    16 |                           10 | uncertainty_penalty_action |                      1 |                      0.5 |                40 |                0.475    |                0.55     |             0.075    |      5 |        2 |     33 |
| long_mug_task4_init0_denoise10_replication | generalization     | parallel          |             4 |                    16 |                           10 | uncertainty_penalty_action |                      1 |                      0.5 |                30 |                0.833333 |                0.7      |            -0.133333 |      2 |        6 |     22 |

## Exploratory pre-failure detector variants ranked on calibration

Not available yet.

## Frozen calibration selections evaluated on holdout

Not available yet.
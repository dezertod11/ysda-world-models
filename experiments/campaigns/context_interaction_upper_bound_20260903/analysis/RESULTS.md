# Privileged context-interaction VoF upper bound

> Exploratory non-deployable analysis on previously opened outcomes.

- Rows / independent groups / cells: **640 / 320 / 16**.
- Commit / feedback SR: **58.0% / 55.8%**.
- Relative control: `relative_control / direct_success / a=1`.
- Best interaction upper bound: `relative_oracle_interactions / direct_grounded / a=0.1`.
- Relative worst-transfer adjusted gain: **-2.06 pp**.
- Context worst-transfer adjusted gain: **-0.19 pp**.
- Gate: **FAIL**.
- Decision: `pivot_to_recovery_abstention`.

## Gate checks

- `improves_relative_worst_transfer`: PASS
- `positive_adjusted_gain_all_transfer_splits`: FAIL
- `nonnegative_worst_cell_all_transfer_splits`: FAIL
- `monotonic_quintiles_all_transfer_splits`: FAIL
- `auc_at_least_0p60_all_transfer_splits`: FAIL
- `positive_within_cell_grouped_gain`: PASS

## Primary comparison

| role                         | scheme               |   adjusted_gain_pp | 95% CI pp      |   rescues |   harms |    AUROC |
|:-----------------------------|:---------------------|-------------------:|:---------------|----------:|--------:|---------:|
| relative_control             | leave_one_task       |            0.59375 | [-1.02; +2.29] |        17 |      10 | 0.539628 |
| relative_control             | leave_one_level      |           -2.0625  | [-4.11; -0.03] |        12 |      22 | 0.388431 |
| relative_control             | leave_one_cell       |           -0.1875  | [-1.75; +1.38] |        14 |      12 | 0.461303 |
| relative_control             | within_cell_grouped5 |            2.78125 | [+1.11; +4.66] |        27 |       6 | 0.789495 |
| best_interaction_upper_bound | leave_one_task       |           -0.1875  | [-1.77; +1.42] |        13 |      11 | 0.462899 |
| best_interaction_upper_bound | leave_one_level      |           -0.1875  | [-1.87; +1.38] |        15 |      13 | 0.438032 |
| best_interaction_upper_bound | leave_one_cell       |            0.125   | [-1.38; +1.65] |        14 |      10 | 0.486303 |
| best_interaction_upper_bound | within_cell_grouped5 |            2.78125 | [+0.71; +4.89] |        30 |       9 | 0.811835 |

## Top configurations

| family                                |   feature_count | target_variant          |   alpha |   min_transfer_adjusted_gain |   min_transfer_auc |   min_transfer_worst_cell |   min_transfer_monotonic_rho |   within_cell_grouped5__adjusted_gain |
|:--------------------------------------|----------------:|:------------------------|--------:|-----------------------------:|-------------------:|--------------------------:|-----------------------------:|--------------------------------------:|
| relative_oracle_interactions          |             172 | direct_grounded         |    0.1  |                   -0.001875  |           0.438032 |                 -0.15625  |                    -0.6      |                             0.0278125 |
| relative_oracle_interactions          |             172 | ridge_potential_success |    1    |                   -0.005     |           0.452261 |                 -0.10875  |                    -0.4      |                             0.0309375 |
| relative_object_oracle_dynamic_slopes |             374 | direct_success          |    1    |                   -0.005     |           0.448005 |                 -0.13125  |                    -0.102598 |                             0.0184375 |
| relative_object_oracle_dynamic_slopes |             374 | direct_terminal_utility |    1    |                   -0.0065625 |           0.452394 |                 -0.15875  |                    -0.3      |                             0.02      |
| relative_oracle_interactions          |             172 | ridge_potential_success |    0.1  |                   -0.0065625 |           0.446676 |                 -0.136875 |                    -0.410391 |                             0.0325    |
| relative_object_oracle_dynamic_slopes |             374 | direct_grounded         |    1    |                   -0.0065625 |           0.478457 |                 -0.105625 |                     0.1      |                             0.0153125 |
| relative_oracle_interactions          |             172 | direct_terminal_utility |    0.01 |                   -0.0065625 |           0.427128 |                 -0.18375  |                    -0.6      |                             0.0278125 |
| relative_oracle_interactions          |             172 | direct_grounded         |    1    |                   -0.0065625 |           0.416489 |                 -0.209375 |                    -0.6      |                             0.0325    |
| relative_oracle_interactions          |             172 | direct_grounded         |    0.01 |                   -0.008125  |           0.440691 |                 -0.15625  |                    -0.6      |                             0.02625   |
| relative_oracle_interactions          |             172 | direct_terminal_utility |    0.1  |                   -0.008125  |           0.425    |                 -0.18375  |                    -0.6      |                             0.029375  |
| relative_oracle_interactions          |             172 | ridge_potential_success |   10    |                   -0.008125  |           0.400066 |                 -0.184375 |                    -0.7      |                             0.035625  |
| relative_oracle_interactions          |             172 | direct_success          |    0.01 |                   -0.0096875 |           0.426995 |                 -0.235    |                    -0.872082 |                             0.0278125 |
| relative_oracle_additive              |              97 | direct_success          |   10    |                   -0.0096875 |           0.356516 |                 -0.15625  |                    -0.410391 |                             0.02625   |
| relative_oracle_additive              |              97 | direct_terminal_utility |   10    |                   -0.0096875 |           0.345479 |                 -0.15625  |                    -0.3      |                             0.02625   |
| relative_oracle_additive              |              97 | ridge_potential_success |   10    |                   -0.01125   |           0.36004  |                 -0.28625  |                    -0.3      |                             0.029375  |
| relative_object_oracle_dynamic_slopes |             374 | ridge_potential_success |    1    |                   -0.01125   |           0.43484  |                 -0.184375 |                    -0.447214 |                             0.0278125 |
| relative_oracle_additive              |              97 | direct_success          |    0.1  |                   -0.01125   |           0.39016  |                 -0.168125 |                    -0.3      |                             0.023125  |
| relative_oracle_additive              |              97 | direct_grounded         |    0.01 |                   -0.01125   |           0.386835 |                 -0.168125 |                    -0.7      |                             0.0278125 |
| relative_oracle_interactions          |             172 | ridge_potential_success |    0.01 |                   -0.0128125 |           0.427128 |                 -0.13875  |                    -0.872082 |                             0.03875   |
| relative_oracle_interactions          |             172 | direct_success          |    0.1  |                   -0.0128125 |           0.422207 |                 -0.234375 |                    -0.6      |                             0.02625   |

## Interpretation boundary

Task, perturbation level and privileged phase are supplied to this diagnostic.
The within-cell split measures interpolation only. Leave-one-task, level and
cell remain the decision splits. No row in this report is a confirmatory or
deployable planner result.

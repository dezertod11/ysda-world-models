# Semantic VoF Environment task transfer: results

- Development states: **98** (tasks 0-3).
- Transfer states: **67** (tasks 5/8/9).
- Gate: **FAIL**.

## Models

| family                    |   spearman |   sign_auc |   balanced_accuracy |      rmse |
|:--------------------------|-----------:|-----------:|--------------------:|----------:|
| scalar                    |   0.244752 |   0.62     |            0.577143 | 0.0959687 |
| scalar+agent-disagreement |   0.243355 |   0.619048 |            0.577143 | 0.0958835 |
| scalar+crossview          |   0.198938 |   0.612381 |            0.617143 | 0.0957921 |
| scalar+semantic2          |   0.200096 |   0.613333 |            0.617143 | 0.0957818 |

## Uplift

| family                    |   budget |   selected_count |   uplift_per_state |   mean_selected_vof |   compute_adjusted_uplift |   oracle_uplift_per_state |   random_expected_uplift |
|:--------------------------|---------:|-----------------:|-------------------:|--------------------:|--------------------------:|--------------------------:|-------------------------:|
| scalar                    |      0.1 |                7 |       -0.000316602 |         -0.00303033 |               -0.00292854 |                 0.0169107 |             -0.000974952 |
| scalar                    |      0.2 |               14 |       -0.000396819 |         -0.00189906 |               -0.0056207  |                 0.0177312 |             -0.0019499   |
| scalar                    |      0.3 |               21 |       -0.00320845  |         -0.0102365  |               -0.0110443  |                 0.0181152 |             -0.00292485  |
| scalar+agent-disagreement |      0.1 |                7 |       -0.000316602 |         -0.00303033 |               -0.00292854 |                 0.0169107 |             -0.000974952 |
| scalar+agent-disagreement |      0.2 |               14 |       -0.000396819 |         -0.00189906 |               -0.0056207  |                 0.0177312 |             -0.0019499   |
| scalar+agent-disagreement |      0.3 |               21 |       -0.00320845  |         -0.0102365  |               -0.0110443  |                 0.0181152 |             -0.00292485  |
| scalar+crossview          |      0.1 |                7 |       -0.000780048 |         -0.00746617 |               -0.00339199 |                 0.0169107 |             -0.000974952 |
| scalar+crossview          |      0.2 |               14 |       -0.000345555 |         -0.00165373 |               -0.00556944 |                 0.0177312 |             -0.0019499   |
| scalar+crossview          |      0.3 |               21 |       -0.00324119  |         -0.0103409  |               -0.011077   |                 0.0181152 |             -0.00292485  |
| scalar+semantic2          |      0.1 |                7 |       -0.000780048 |         -0.00746617 |               -0.00339199 |                 0.0169107 |             -0.000974952 |
| scalar+semantic2          |      0.2 |               14 |       -0.000345555 |         -0.00165373 |               -0.00556944 |                 0.0177312 |             -0.0019499   |
| scalar+semantic2          |      0.3 |               21 |        0.00359818  |          0.0114799  |               -0.00423764 |                 0.0181152 |             -0.00292485  |

## Per task

| family                    |   task_id |   states |   spearman |   sign_auc |   balanced_accuracy |      rmse |   uplift20_uplift_per_state |   uplift20_compute_adjusted_uplift |
|:--------------------------|----------:|---------:|-----------:|-----------:|--------------------:|----------:|----------------------------:|-----------------------------------:|
| scalar                    |         5 |       26 |   0.199316 |   0.597222 |            0.555556 | 0.0312213 |                -0.000856602 |                        -0.00662583 |
| scalar                    |         8 |       13 |   0.428571 |   0.727273 |            0.613636 | 0.132578  |                -0.00358455  |                        -0.00935378 |
| scalar                    |         9 |       28 |   0.28243  |   0.692308 |            0.623077 | 0.113896  |                -0.00830011  |                        -0.0136573  |
| scalar+agent-disagreement |         5 |       26 |   0.199316 |   0.597222 |            0.555556 | 0.0311096 |                -0.000856602 |                        -0.00662583 |
| scalar+agent-disagreement |         8 |       13 |   0.428571 |   0.727273 |            0.613636 | 0.1323    |                -0.00358455  |                        -0.00935378 |
| scalar+agent-disagreement |         9 |       28 |   0.273673 |   0.687179 |            0.623077 | 0.113903  |                -0.00830011  |                        -0.0136573  |
| scalar+crossview          |         5 |       26 |   0.174017 |   0.569444 |            0.555556 | 0.0332124 |                -0.0017507   |                        -0.00751993 |
| scalar+crossview          |         8 |       13 |   0.434066 |   0.727273 |            0.863636 | 0.128937  |                -0.00734839  |                        -0.0131176  |
| scalar+crossview          |         9 |       28 |   0.216201 |   0.666667 |            0.65641  | 0.114954  |                -0.00840377  |                        -0.0137609  |
| scalar+semantic2          |         5 |       26 |   0.174017 |   0.569444 |            0.555556 | 0.0331956 |                -0.0017507   |                        -0.00751993 |
| scalar+semantic2          |         8 |       13 |   0.406593 |   0.727273 |            0.863636 | 0.128906  |                -0.00734839  |                        -0.0131176  |
| scalar+semantic2          |         9 |       28 |   0.216201 |   0.666667 |            0.65641  | 0.114954  |                -0.00840377  |                        -0.0137609  |

## Gate

- `exact_train_test_coverage`: PASS
- `task_sets_frozen_and_disjoint`: PASS
- `primary_spearman_gain_at_least_0p05`: FAIL
- `primary_auc_not_below_scalar`: FAIL
- `primary_uplift20_positive`: FAIL
- `primary_uplift20_above_scalar`: PASS
- `primary_compute_adjusted_uplift20_positive`: FAIL
- `primary_uplift20_nonnegative_each_task`: FAIL
- `no_privileged_features`: PASS

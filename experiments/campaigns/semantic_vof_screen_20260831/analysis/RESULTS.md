# Semantic predicted-consequence screen: results

- States: **265**.
- Frozen encoder: `openai/clip-vit-base-patch32`.
- Development gate: **FAIL**.

## Model metrics

| family   | protocol   |   spearman |   sign_auc |   balanced_accuracy |      rmse |
|:---------|:-----------|-----------:|-----------:|--------------------:|----------:|
| scalar   | group_oof  |   0.470976 |   0.711395 |            0.648229 | 0.0444535 |
| scalar   | factor_oof |   0.219301 |   0.587757 |            0.524791 | 0.0485846 |
| semantic | group_oof  |   0.131078 |   0.534048 |            0.55818  | 0.0498842 |
| semantic | factor_oof |  -0.243899 |   0.38003  |            0.399031 | 0.0545789 |
| combined | group_oof  |   0.433786 |   0.698842 |            0.629543 | 0.0454448 |
| combined | factor_oof |   0.247409 |   0.602201 |            0.547575 | 0.0493392 |

## Uplift at budget

| family   |   budget |   selected_count |   uplift_per_state |   mean_selected_vof |   compute_adjusted_uplift |   oracle_uplift_per_state |   random_expected_uplift |
|:---------|---------:|-----------------:|-------------------:|--------------------:|--------------------------:|--------------------------:|-------------------------:|
| scalar   |      0.1 |               27 |        0.00239342  |         0.023491    |              -0.00015375  |                0.00881604 |             -0.000473945 |
| scalar   |      0.2 |               53 |        0.00354469  |         0.0177234   |              -0.00145531  |                0.0103367  |             -0.000930337 |
| scalar   |      0.3 |               80 |        0.00523936  |         0.0173554   |              -0.00230781  |                0.0110282  |             -0.00140428  |
| semantic |      0.1 |               27 |       -0.000395398 |        -0.00388076  |              -0.00294257  |                0.00881604 |             -0.000473945 |
| semantic |      0.2 |               53 |       -0.00013447  |        -0.000672349 |              -0.00513447  |                0.0103367  |             -0.000930337 |
| semantic |      0.3 |               80 |       -0.000233165 |        -0.000772358 |              -0.00778033  |                0.0110282  |             -0.00140428  |
| combined |      0.1 |               27 |        0.0015528   |         0.0152404   |              -0.000994372 |                0.00881604 |             -0.000473945 |
| combined |      0.2 |               53 |        0.00244086  |         0.0122043   |              -0.00255914  |                0.0103367  |             -0.000930337 |
| combined |      0.3 |               80 |        0.00521242  |         0.0172661   |              -0.00233475  |                0.0110282  |             -0.00140428  |

## Per-factor transfer

| family   | protocol   | factor      |   states |    spearman |   sign_auc |   balanced_accuracy |      rmse |   uplift20_uplift_per_state |   uplift20_compute_adjusted_uplift |
|:---------|:-----------|:------------|---------:|------------:|-----------:|--------------------:|----------:|----------------------------:|-----------------------------------:|
| scalar   | group_oof  | Environment |       98 |  0.690288   |   0.951956 |            0.77381  | 0.0289253 |                 0.00191588  |                        -0.00318616 |
| scalar   | factor_oof | Environment |       98 |  0.399473   |   0.747874 |            0.565476 | 0.0357226 |                -0.000966    |                        -0.00606804 |
| scalar   | group_oof  | Object      |       98 |  0.560341   |   0.754195 |            0.687302 | 0.0627184 |                 0.00716796  |                         0.00206592 |
| scalar   | factor_oof | Object      |       98 |  0.306951   |   0.62449  |            0.579365 | 0.0665436 |                -0.0012085   |                        -0.00631054 |
| scalar   | group_oof  | Position    |       69 | -0.0236756  |   0.498302 |            0.499151 | 0.0285351 |                -0.0022914   |                        -0.00736386 |
| scalar   | factor_oof | Position    |       69 |  0.0308001  |   0.520374 |            0.485993 | 0.0310486 |                -0.00168901  |                        -0.00676147 |
| semantic | group_oof  | Environment |       98 |  0.433991   |   0.747024 |            0.702381 | 0.0362076 |                 0.00312068  |                        -0.00198136 |
| semantic | factor_oof | Environment |       98 | -0.254366   |   0.262755 |            0.35119  | 0.0442312 |                -0.00461854  |                        -0.00972058 |
| semantic | group_oof  | Object      |       98 |  0.0512914  |   0.514286 |            0.574603 | 0.0686145 |                -0.000415043 |                        -0.00551708 |
| semantic | factor_oof | Object      |       98 | -0.207646   |   0.417234 |            0.403175 | 0.07322   |                -0.00737879  |                        -0.0124808  |
| semantic | group_oof  | Position    |       69 | -0.294666   |   0.39983  |            0.434635 | 0.0317553 |                -0.00297841  |                        -0.00805088 |
| semantic | factor_oof | Position    |       69 | -0.252247   |   0.42275  |            0.440577 | 0.0323647 |                -0.00319055  |                        -0.00826302 |
| combined | group_oof  | Environment |       98 |  0.607623   |   0.894558 |            0.770833 | 0.0323802 |                 0.00213555  |                        -0.00296649 |
| combined | factor_oof | Environment |       98 |  0.511811   |   0.810374 |            0.66369  | 0.0349484 |                 0.00216327  |                        -0.00293877 |
| combined | group_oof  | Object      |       98 |  0.521221   |   0.736508 |            0.634921 | 0.0626549 |                 0.00590353  |                         0.00080149 |
| combined | factor_oof | Object      |       98 |  0.133523   |   0.55873  |            0.528571 | 0.0683896 |                -0.000915172 |                        -0.00601721 |
| combined | group_oof  | Position    |       69 | -0.0519182  |   0.512733 |            0.49618  | 0.0294446 |                -0.00244284  |                        -0.0075153  |
| combined | factor_oof | Position    |       69 | -0.00869565 |   0.517827 |            0.483022 | 0.0311726 |                -0.0012467   |                        -0.00631917 |

## Gate

- `combined_group_spearman_at_least_0p20`: PASS
- `combined_group_spearman_above_scalar`: FAIL
- `combined_uplift20_positive`: PASS
- `combined_uplift20_above_scalar`: FAIL
- `combined_uplift20_nonnegative_each_factor`: FAIL
- `combined_factor_oof_spearman_nonnegative_each_factor`: FAIL
- `all_265_states`: PASS
- `no_privileged_features`: PASS

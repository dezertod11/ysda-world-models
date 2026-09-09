# Hard-cell pairwise ranker: untouched holdout

Frozen model: `c9ae031cd3b4e1cf7f8c9acc1e191b99601ab585d17033e588b86c19f1db6168`.
Preregistered holdout gate: **FAIL**.

## Terminal selection

| factor   |   states |   mixed_states |   maxv_sr |   autoregressive_sr |   ranker_sr |   selected_sr |   oracle_sr |   mixed_maxv_top1 |   mixed_autoregressive_top1 |   mixed_ranker_top1 |   mixed_selected_top1 |   mixed_selected_delta_states |   selected_utility_delta |   switches |   switch_precision |   rescues |   harms |   adverse_delta_events |
|:---------|---------:|---------------:|----------:|--------------------:|------------:|--------------:|------------:|------------------:|----------------------------:|--------------------:|----------------------:|------------------------------:|-------------------------:|-----------:|-------------------:|----------:|--------:|-----------------------:|
| Object   |       10 |             10 |      0.7  |                 0.6 |        0.3  |           0.4 |         1   |              0.7  |                    0.6      |                0.3  |                   0.4 |                            -3 |                    -0.9  |          4 |                  0 |         0 |       3 |                      0 |
| Position |       10 |              2 |      0.2  |                 0.2 |        0    |           0.2 |         0.2 |              1    |                    1        |                0    |                   1   |                             0 |                     0    |          2 |                  0 |         0 |       0 |                      0 |
| All      |       20 |             12 |      0.45 |                 0.4 |        0.15 |           0.3 |         0.6 |              0.75 |                    0.666667 |                0.25 |                   0.5 |                            -3 |                    -0.45 |          6 |                  0 |         0 |       3 |                      0 |

## Within-state success/fail ordering

| factor   |   success_pairs |   maxv_pairwise_accuracy |   autoregressive_pairwise_accuracy |   ranker_pairwise_accuracy |
|:---------|----------------:|-------------------------:|-----------------------------------:|---------------------------:|
| Object   |             119 |                 0.599821 |                           0.412857 |                   0.330714 |
| Position |              27 |                 0.575    |                           0.741667 |                   0.45     |

## Grouped bootstrap deltas

| factor   | metric                 |   groups |   point |   ci_low |   ci_high |   probability_positive |
|:---------|:-----------------------|---------:|--------:|---------:|----------:|-----------------------:|
| Object   | raw_success_delta      |       10 |   -0.4  |    -0.7  |     -0.1  |                 0      |
| Object   | selected_success_delta |       10 |   -0.3  |    -0.6  |      0    |                 0      |
| Object   | selected_utility_delta |       10 |   -0.9  |    -1.9  |      0    |                 0      |
| Object   | selected_adverse_delta |       10 |    0    |    -0.3  |      0.3  |                 0.3572 |
| Position | raw_success_delta      |       10 |   -0.2  |    -0.5  |      0    |                 0      |
| Position | selected_success_delta |       10 |    0    |     0    |      0    |                 0      |
| Position | selected_utility_delta |       10 |    0    |     0    |      0    |                 0      |
| Position | selected_adverse_delta |       10 |    0    |     0    |      0    |                 0      |
| All      | raw_success_delta      |       20 |   -0.3  |    -0.5  |     -0.1  |                 0      |
| All      | selected_success_delta |       20 |   -0.15 |    -0.3  |      0    |                 0      |
| All      | selected_utility_delta |       20 |   -0.45 |    -1    |      0    |                 0      |
| All      | selected_adverse_delta |       20 |    0    |    -0.15 |      0.15 |                 0.3406 |

Exact paired sign p-value over rescues/harms: 0.25.

The frozen linear pairwise feature family did not pass the terminal gate.
Do not tune it on these holdout states; move to a nonlinear semantic consequence critic or re-query/recovery.

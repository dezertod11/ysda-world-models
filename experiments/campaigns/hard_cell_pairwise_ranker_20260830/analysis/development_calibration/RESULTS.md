# Hard-cell pairwise ranker: development/calibration

Opportunity gate: **PASS**.

## Proposal opportunity

| factor   |   states |   mixed_states |   success_rescues |   maxv_sr |   oracle_sr |
|:---------|---------:|---------------:|------------------:|----------:|------------:|
| Object   |       20 |             17 |                13 |      0.3  |        0.95 |
| Position |       20 |              3 |                 3 |      0    |        0.15 |
| All      |       40 |             20 |                16 |      0.15 |        0.55 |

## Grouped cross-validation

| factor   |   alpha |   groups_scored |   utility_pairwise_accuracy |   utility_pairs | selected   |
|:---------|--------:|----------------:|----------------------------:|----------------:|:-----------|
| Object   |     0.1 |              13 |                    0.516955 |             220 | False      |
| Object   |     1   |              13 |                    0.51811  |             220 | False      |
| Object   |    10   |              13 |                    0.528442 |             220 | False      |
| Object   |   100   |              13 |                    0.535687 |             220 | True       |
| Position |     0.1 |               3 |                    0.460317 |              35 | False      |
| Position |     1   |               3 |                    0.460317 |              35 | True       |
| Position |    10   |               3 |                    0.404762 |              35 | False      |
| Position |   100   |               3 |                    0.329365 |              35 | False      |

## Calibration selector

| factor   |   states |   mixed_states |   maxv_sr |   autoregressive_sr |   ranker_sr |   selected_sr |   oracle_sr |   mixed_maxv_top1 |   mixed_autoregressive_top1 |   mixed_ranker_top1 |   mixed_selected_top1 |   mixed_selected_delta_states |   selected_utility_delta |   switches |   switch_precision |   rescues |   harms |   adverse_delta_events |
|:---------|---------:|---------------:|----------:|--------------------:|------------:|--------------:|------------:|------------------:|----------------------------:|--------------------:|----------------------:|------------------------------:|-------------------------:|-----------:|-------------------:|----------:|--------:|-----------------------:|
| Object   |        5 |              4 |       0.4 |                 0.6 |         0.8 |           0.8 |         1   |              0.25 |                         0.5 |                0.75 |                  0.75 |                             2 |                      1.2 |          5 |           0.4      |         2 |       0 |                      0 |
| Position |        5 |              0 |       0   |                 0   |         0   |           0   |         0   |            nan    |                       nan   |              nan    |                nan    |                             0 |                      0   |          4 |           0        |         0 |       0 |                      0 |
| All      |       10 |              4 |       0.2 |                 0.3 |         0.4 |           0.4 |         0.5 |              0.25 |                         0.5 |                0.75 |                  0.75 |                             2 |                      0.6 |          9 |           0.222222 |         2 |       0 |                      0 |

Frozen payload SHA-256: `c9ae031cd3b4e1cf7f8c9acc1e191b99601ab585d17033e588b86c19f1db6168`.

The model is frozen before untouched holdout collection.

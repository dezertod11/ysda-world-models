# Terminal-grounded critic development result

- Opportunity gate: **PASS**.

## Candidate-pool opportunity

| factor   |   snapshots |   independent_groups |   heterogeneous_snapshots |   success_rescues |   utility_rescues |   maxv_sr |   oracle_sr |   oracle_gap_pp |   maxv_utility |   oracle_utility |
|:---------|------------:|---------------------:|--------------------------:|------------------:|------------------:|----------:|------------:|----------------:|---------------:|-----------------:|
| Object   |          80 |                   40 |                         8 |                 5 |                 5 |     0.925 |      0.9875 |            6.25 |           2.75 |           2.9625 |
| All      |          80 |                   40 |                         8 |                 5 |                 5 |     0.925 |      0.9875 |            6.25 |           2.75 |           2.9625 |

## Frozen model

- Name: `terminal_grounded_conservative_critic_v1`.
- Payload SHA-256: `3187672846409cd5b3d59628b32058bc883512deae348833d716f52cb51e87b7`.
- Ensemble members: 32.
- Ridge alpha: 10.0.
- Expected candidates: 8.

## Conservative selection

| factor   |   snapshots |   independent_groups |   maxv_sr |   critic_sr |   oracle_sr |   success_delta_pp |   maxv_utility |   critic_utility |   oracle_utility |   utility_delta |   switches |   switch_rate |   switch_precision |   rescues |   harms |   maxv_adverse_rate |   critic_adverse_rate |
|:---------|------------:|---------------------:|----------:|------------:|------------:|-------------------:|---------------:|-----------------:|-----------------:|----------------:|-----------:|--------------:|-------------------:|----------:|--------:|--------------------:|----------------------:|
| Object   |          20 |                   10 |         1 |           1 |           1 |                  0 |              3 |                3 |                3 |               0 |          0 |             0 |                nan |         0 |       0 |                   0 |                     0 |
| All      |          20 |                   10 |         1 |           1 |           1 |                  0 |              3 |                3 |                3 |               0 |          0 |             0 |                nan |         0 |       0 |                   0 |                     0 |

## Interval coverage

| factor   |   snapshots |   independent_groups |   advantage_candidate_coverage |   advantage_simultaneous_state_coverage |   advantage_mean_lcb_slack |   risk_candidate_coverage |   risk_simultaneous_state_coverage |   risk_predicted_mean |   risk_observed_mean |   risk_brier |
|:---------|------------:|---------------------:|-------------------------------:|----------------------------------------:|---------------------------:|--------------------------:|-----------------------------------:|----------------------:|---------------------:|-------------:|
| Object   |          20 |                   10 |                              1 |                                       1 |                     8.4207 |                         1 |                                  1 |             0.0403874 |               0.0125 |    0.0148177 |
| All      |          20 |                   10 |                              1 |                                       1 |                     8.4207 |                         1 |                                  1 |             0.0403874 |               0.0125 |    0.0148177 |

## Largest frozen coefficients

| factor   | feature                               |   advantage_coefficient_mean |   advantage_coefficient_std |   risk_coefficient_mean |   risk_coefficient_std |   advantage_abs_rank |   risk_abs_rank |
|:---------|:--------------------------------------|-----------------------------:|----------------------------:|------------------------:|-----------------------:|---------------------:|----------------:|
| Object   | candidate_action_std_d0               |                  -0.116804   |                   0.0546922 |              0.0296221  |             0.0129819  |                    1 |               1 |
| Object   | candidate_action_first_d0             |                  -0.0758599  |                   0.0319342 |              0.0257929  |             0.0115581  |                    2 |               2 |
| Object   | candidate_predicted_future_proprio_d6 |                  -0.0643061  |                   0.0490366 |              0.0208668  |             0.011352   |                    3 |               3 |
| Object   | latent_action_copy_std_max            |                   0.0595105  |                   0.0549988 |             -0.0140153  |             0.0110178  |                    4 |               5 |
| Object   | latent_action_copy_std_mean           |                  -0.0481847  |                   0.0310301 |              0.00874693 |             0.0059995  |                    5 |              14 |
| Object   | candidate_action_std_d1               |                  -0.0455593  |                   0.0396974 |              0.00452712 |             0.00939991 |                    6 |              31 |
| Object   | candidate_action_mean_d4              |                  -0.0422734  |                   0.025065  |              0.00947792 |             0.00700399 |                    7 |              10 |
| Object   | latent_action_first_step_copy_l2_std  |                  -0.0417905  |                   0.0401938 |              0.00931801 |             0.00853118 |                    8 |              11 |
| Object   | candidate_action_last_d5              |                   0.0406061  |                   0.0260215 |             -0.00758342 |             0.00682756 |                    9 |              17 |
| Object   | latent_future_proprio_copy_std_max    |                  -0.0352701  |                   0.0199438 |              0.0142381  |             0.00961505 |                   10 |               4 |
| Object   | latent_future_proprio_copy_std_mean   |                   0.0322592  |                   0.0266271 |             -0.0117409  |             0.0113511  |                   14 |               6 |
| Object   | candidate_value                       |                  -0.0300146  |                   0.0197245 |              0.0111344  |             0.00689228 |                   18 |               8 |
| Object   | candidate_action_mean_d3              |                   0.0163109  |                   0.0233482 |             -0.0107661  |             0.00590854 |                   29 |               9 |
| Object   | candidate_action_first_d5             |                  -0.00881031 |                   0.0304185 |              0.011139   |             0.0102635  |                   37 |               7 |

## Opportunity gate

```json
{
  "passed": true,
  "heterogeneous_snapshots": 8,
  "required_heterogeneous_snapshots": 8,
  "success_rescues": 5,
  "required_success_rescues": 4,
  "snapshots": 80,
  "independent_groups": 40
}
```

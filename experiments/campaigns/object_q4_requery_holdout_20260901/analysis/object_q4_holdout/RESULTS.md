# Frozen Object query-4 requery holdout

- Exact-state pairs: **60**.
- Independent init states: **15**.
- Rescue / harm: **16 / 3**.
- Integrity gate: **PASS**.
- Practical gate: **PASS**.
- Confirmatory gate: **PASS**.

## Primary paired endpoint

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|       60 |                   15 |            0.383333 |                     0.6 |        0.216667 |                   0.05 |                     0.4 |        16 |       3 |            13 |           0.316667 |             20 |          21 |             0.025 |                        0.191667 |           0.00442505 |                        60 |

## Strict replay-integrity sensitivity

|   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|       60 |                   15 |            0.383333 |                     0.6 |        0.216667 |                   0.05 |                     0.4 |        16 |       3 |            13 |           0.316667 |             20 |          21 |             0.025 |                        0.191667 |           0.00442505 |                        60 |

## Integrity checks

```json
{
  "suite_matches": true,
  "task_matches": true,
  "query_matches": true,
  "development_overlap": [],
  "unexpected_init_states": [],
  "missing_init_states": [],
  "duplicate_analysis_states": 0,
  "observed_pairs": 60,
  "target_pairs": 60,
  "valid": true
}
```

## Frozen secondary rankers

| method                                                            |   budget |   states |   selected |   selected_rescues |   selected_harms |   selected_rescue_rate |   selected_harm_rate |   raw_success_delta |   adjusted_terminal_delta |
|:------------------------------------------------------------------|---------:|---------:|-----------:|-------------------:|-----------------:|-----------------------:|---------------------:|--------------------:|--------------------------:|
| frozen_high_latent_future_proprio_copy_std_mean_mean_over_samples |    0.05  |       60 |          3 |                  1 |                0 |               0.333333 |                    0 |           0.0166667 |                0.0154167  |
| frozen_high_latent_future_proprio_copy_std_mean_mean_over_samples |    0.075 |       60 |          5 |                  1 |                0 |               0.2      |                    0 |           0.0166667 |                0.0145833  |
| frozen_high_latent_future_proprio_copy_std_mean_mean_over_samples |    0.1   |       60 |          6 |                  1 |                0 |               0.166667 |                    0 |           0.0166667 |                0.0141667  |
| frozen_low_candidate_action_consensus_chunk_mean                  |    0.05  |       60 |          3 |                  0 |                0 |               0        |                    0 |           0         |               -0.00125    |
| frozen_low_candidate_action_consensus_chunk_mean                  |    0.075 |       60 |          5 |                  0 |                0 |               0        |                    0 |           0         |               -0.00208333 |
| frozen_low_candidate_action_consensus_chunk_mean                  |    0.1   |       60 |          6 |                  0 |                0 |               0        |                    0 |           0         |               -0.0025     |
| frozen_low_action_std_mean                                        |    0.05  |       60 |          3 |                  0 |                0 |               0        |                    0 |           0         |               -0.00125    |
| frozen_low_action_std_mean                                        |    0.075 |       60 |          5 |                  0 |                0 |               0        |                    0 |           0         |               -0.00208333 |
| frozen_low_action_std_mean                                        |    0.1   |       60 |          6 |                  0 |                0 |               0        |                    0 |           0         |               -0.0025     |

## Init-state breakdown

|   init_state_id |   states |   independent_groups |   open_success_rate |   feedback_success_rate |   success_delta |   success_delta_ci_low |   success_delta_ci_high |   rescues |   harms |   net_rescues |   discordance_rate |   both_success |   both_fail |   mean_query_cost |   always_requery_adjusted_delta |   discordance_pvalue |   strict_integrity_states |
|----------------:|---------:|---------------------:|--------------------:|------------------------:|----------------:|-----------------------:|------------------------:|----------:|--------:|--------------:|-------------------:|---------------:|------------:|------------------:|--------------------------------:|---------------------:|--------------------------:|
|              33 |        4 |                    1 |                0.75 |                    1    |            0.25 |                   0.25 |                    0.25 |         1 |       0 |             1 |               0.25 |              3 |           0 |             0.025 |                           0.225 |                1     |                         4 |
|              35 |        4 |                    1 |                1    |                    1    |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              4 |           0 |             0.025 |                          -0.025 |              nan     |                         4 |
|              36 |        4 |                    1 |                0    |                    0.25 |            0.25 |                   0.25 |                    0.25 |         1 |       0 |             1 |               0.25 |              0 |           3 |             0.025 |                           0.225 |                1     |                         4 |
|              37 |        4 |                    1 |                0.5  |                    1    |            0.5  |                   0.5  |                    0.5  |         2 |       0 |             2 |               0.5  |              2 |           0 |             0.025 |                           0.475 |                0.5   |                         4 |
|              38 |        4 |                    1 |                0    |                    0.75 |            0.75 |                   0.75 |                    0.75 |         3 |       0 |             3 |               0.75 |              0 |           1 |             0.025 |                           0.725 |                0.25  |                         4 |
|              39 |        4 |                    1 |                0    |                    0.75 |            0.75 |                   0.75 |                    0.75 |         3 |       0 |             3 |               0.75 |              0 |           1 |             0.025 |                           0.725 |                0.25  |                         4 |
|              40 |        4 |                    1 |                1    |                    1    |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              4 |           0 |             0.025 |                          -0.025 |              nan     |                         4 |
|              41 |        4 |                    1 |                0.5  |                    0.5  |            0    |                   0    |                    0    |         1 |       1 |             0 |               0.5  |              1 |           1 |             0.025 |                          -0.025 |                1     |                         4 |
|              43 |        4 |                    1 |                0.75 |                    0.75 |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              3 |           1 |             0.025 |                          -0.025 |              nan     |                         4 |
|              44 |        4 |                    1 |                0.25 |                    0    |           -0.25 |                  -0.25 |                   -0.25 |         0 |       1 |            -1 |               0.25 |              0 |           3 |             0.025 |                          -0.275 |                1     |                         4 |
|              45 |        4 |                    1 |                0.5  |                    0.25 |           -0.25 |                  -0.25 |                   -0.25 |         0 |       1 |            -1 |               0.25 |              1 |           2 |             0.025 |                          -0.275 |                1     |                         4 |
|              46 |        4 |                    1 |                0.5  |                    0.5  |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              2 |           2 |             0.025 |                          -0.025 |              nan     |                         4 |
|              47 |        4 |                    1 |                0    |                    0    |            0    |                   0    |                    0    |         0 |       0 |             0 |               0    |              0 |           4 |             0.025 |                          -0.025 |              nan     |                         4 |
|              48 |        4 |                    1 |                0    |                    1    |            1    |                   1    |                    1    |         4 |       0 |             4 |               1    |              0 |           0 |             0.025 |                           0.975 |                0.125 |                         4 |
|              49 |        4 |                    1 |                0    |                    0.25 |            0.25 |                   0.25 |                    0.25 |         1 |       0 |             1 |               0.25 |              0 |           3 |             0.025 |                           0.225 |                1     |                         4 |

## Discordant failure transitions

| factor   | terminal_outcome   | open_terminal_failure_type   | feedback_terminal_failure_type   |   states |
|:---------|:-------------------|:-----------------------------|:---------------------------------|---------:|
| Object   | rescue             | timeout_no_goal              | success                          |       14 |
| Object   | harm               | success                      | timeout_no_goal                  |        2 |
| Object   | rescue             | target_drop_candidate        | success                          |        2 |
| Object   | harm               | success                      | target_drop_candidate            |        1 |

## Decision rule

The query-4 intervention is accepted only when the frozen practical gate passes.
The stronger confirmatory claim additionally requires positive lower CI and `p<0.05`.
Secondary rankers retain their development-frozen directions regardless of holdout outcomes.

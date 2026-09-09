# Frozen terminal-grounded critic holdout result

- Offline critic gate: **FAIL**.

## Candidate-pool opportunity

| factor   |   snapshots |   independent_groups |   heterogeneous_snapshots |   success_rescues |   utility_rescues |   maxv_sr |   oracle_sr |   oracle_gap_pp |   maxv_utility |   oracle_utility |
|:---------|------------:|---------------------:|--------------------------:|------------------:|------------------:|----------:|------------:|----------------:|---------------:|-----------------:|
| Object   |          20 |                   10 |                         0 |                 0 |                 0 |         1 |           1 |               0 |              3 |                3 |
| All      |          20 |                   10 |                         0 |                 0 |                 0 |         1 |           1 |               0 |              3 |                3 |

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

## Grouped bootstrap

| factor   | metric        |   groups |   point |   ci_low |   ci_high |
|:---------|:--------------|---------:|--------:|---------:|----------:|
| Object   | success_delta |       10 |       0 |        0 |         0 |
| Object   | utility_delta |       10 |       0 |        0 |         0 |
| Object   | risk_delta    |       10 |       0 |        0 |         0 |
| All      | success_delta |       10 |       0 |        0 |         0 |
| All      | utility_delta |       10 |       0 |        0 |         0 |
| All      | risk_delta    |       10 |       0 |        0 |         0 |

## Interval coverage

| factor   |   snapshots |   independent_groups |   advantage_candidate_coverage |   advantage_simultaneous_state_coverage |   advantage_mean_lcb_slack |   risk_candidate_coverage |   risk_simultaneous_state_coverage |   risk_predicted_mean |   risk_observed_mean |   risk_brier |
|:---------|------------:|---------------------:|-------------------------------:|----------------------------------------:|---------------------------:|--------------------------:|-----------------------------------:|----------------------:|---------------------:|-------------:|
| Object   |          20 |                   10 |                              1 |                                       1 |                    8.68888 |                         1 |                                  1 |             0.0407187 |                    0 |   0.00306839 |
| All      |          20 |                   10 |                              1 |                                       1 |                    8.68888 |                         1 |                                  1 |             0.0407187 |                    0 |   0.00306839 |

## Offline critic gate

```json
{
  "passed": false,
  "checks": {
    "zero_group_overlap": true,
    "switch_rate_in_2_to_30_percent": false,
    "positive_net_rescues": false,
    "nonnegative_terminal_utility": true,
    "safety_regression_at_most_one_event": true,
    "utility_ci_lower_nonnegative": true
  },
  "group_overlap": [],
  "summary": {
    "snapshots": 20.0,
    "independent_groups": 10.0,
    "maxv_sr": 1.0,
    "critic_sr": 1.0,
    "oracle_sr": 1.0,
    "success_delta_pp": 0.0,
    "maxv_utility": 3.0,
    "critic_utility": 3.0,
    "oracle_utility": 3.0,
    "utility_delta": 0.0,
    "switches": 0.0,
    "switch_rate": 0.0,
    "switch_precision": null,
    "rescues": 0.0,
    "harms": 0.0,
    "maxv_adverse_rate": 0.0,
    "critic_adverse_rate": 0.0
  },
  "utility_delta_ci": {
    "low": 0.0,
    "high": 0.0
  }
}
```

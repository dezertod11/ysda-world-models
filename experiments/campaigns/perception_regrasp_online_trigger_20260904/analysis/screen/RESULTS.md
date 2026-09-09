# P3c screen online regrasp results

- Complete cases: **12/12**.
- Exact snapshot replay: **True**.
- Recommended frozen method: **workspace_calibrated**.
- Gate: **PASS**.

| method               |   n_cases |   n_groups |   baseline_successes |   method_successes |   baseline_sr |   method_sr |   paired_sr_delta |   paired_sr_delta_ci_low |   paired_sr_delta_ci_high |   rescues |   harms |   triggered |   interventions |   trigger_rate |   intervention_rate |   mean_final_t_delta |   both_success_cases |   mean_time_delta_both_success |   drop_rate_delta |   wrong_rate_delta |   safety_rate_delta |
|:---------------------|----------:|-----------:|---------------------:|-------------------:|--------------:|------------:|------------------:|-------------------------:|--------------------------:|----------:|--------:|------------:|----------------:|---------------:|--------------------:|---------------------:|---------------------:|-------------------------------:|------------------:|-------------------:|--------------------:|
| workspace_calibrated |        12 |          6 |                    4 |                  8 |      0.333333 |    0.666667 |          0.333333 |                0.0833333 |                  0.666667 |         4 |       0 |           8 |               8 |      0.666667  |           0.666667  |               -62.75 |                    4 |                         -88.25 |                 0 |                  0 |                   0 |
| global_conservative  |        12 |          6 |                    4 |                  4 |      0.333333 |    0.333333 |          0        |                0         |                  0        |         0 |       0 |           1 |               1 |      0.0833333 |           0.0833333 |                -8    |                    4 |                         -24    |                 0 |                  0 |                   0 |

The trigger uses RGB localization and robot proprioception only. Simulator object
state is used solely for terminal evaluation labels and never for intervention selection.

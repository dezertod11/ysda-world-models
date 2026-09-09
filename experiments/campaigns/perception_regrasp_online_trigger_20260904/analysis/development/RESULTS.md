# P3c development online regrasp results

- Complete cases: **40/40**.
- Exact snapshot replay: **True**.
- Recommended frozen method: **workspace_calibrated**.
- Gate: **PASS**.

| method               |   n_cases |   n_groups |   baseline_successes |   method_successes |   baseline_sr |   method_sr |   paired_sr_delta |   paired_sr_delta_ci_low |   paired_sr_delta_ci_high |   rescues |   harms |   triggered |   interventions |   trigger_rate |   intervention_rate |   mean_final_t_delta |   both_success_cases |   mean_time_delta_both_success |   drop_rate_delta |   wrong_rate_delta |   safety_rate_delta |
|:---------------------|----------:|-----------:|---------------------:|-------------------:|--------------:|------------:|------------------:|-------------------------:|--------------------------:|----------:|--------:|------------:|----------------:|---------------:|--------------------:|---------------------:|---------------------:|-------------------------------:|------------------:|-------------------:|--------------------:|
| workspace_calibrated |        40 |         40 |                    7 |                 25 |         0.175 |       0.625 |              0.45 |                      0.3 |                       0.6 |        18 |       0 |          25 |              25 |          0.625 |               0.625 |               -48.35 |                    7 |                       -28.1429 |                 0 |              -0.05 |                   0 |

The trigger uses RGB localization and robot proprioception only. Simulator object
state is used solely for terminal evaluation labels and never for intervention selection.

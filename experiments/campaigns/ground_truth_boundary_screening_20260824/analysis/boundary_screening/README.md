# Ground-truth boundary screening

Analyzed 264 rollouts in 42 same-task/init cases.
Found 2 confirmed and 1 provisional mixed cases.

A `confirmed_mixed` case has at least two success and two failed rollouts; a `provisional_mixed` case has one minority outcome. Only mixed cases are eligible for the larger paired detector experiment.

| Suite | Task | Init | Success | Status |
|---|---:|---:|---:|---|
| libero_10_with_milk | 9 | 0 | 5/12 | confirmed_mixed |
| libero_goal_with_mug | 9 | 0 | 8/12 | confirmed_mixed |
| libero_spatial_task | 7 | 0 | 5/6 | provisional_mixed |

`boundary_case_summary.csv` contains every screened case and Wilson 95% intervals. `episode_outcomes.csv` retains seed-level outcomes and repaired simulator labels.

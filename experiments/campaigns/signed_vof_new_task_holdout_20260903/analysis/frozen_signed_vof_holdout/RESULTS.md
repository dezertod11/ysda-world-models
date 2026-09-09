# Frozen signed-VoF new-task holdout result

- Integrity: 240/240 strict pairs.
- Commit SR: 59.6%.
- Frozen-router SR: 61.7%.
- Query rate: 52.5%.
- Raw delta: +2.1 pp, cluster CI [-4.2, +7.9].
- Cost-adjusted delta: +0.8 pp, cluster CI [-5.4, +7.0].
- Selected rescues / harms: 24 / 19; exact McNemar p=0.542384.
- Rescue-vs-harm score AUROC: 0.398.
- Gate: **FAIL**; decision `do_not_promote_signed_vof_router`.

## Policies

| policy            |   states |   commit_success_rate |   policy_success_rate |   query_rate |   rescues |   harms |   neutral_queries |   raw_success_delta |   adjusted_success_delta |
|:------------------|---------:|----------------------:|----------------------:|-------------:|----------:|--------:|------------------:|--------------------:|-------------------------:|
| always_commit     |      240 |              0.595833 |              0.595833 |        0     |         0 |       0 |                 0 |           0         |               0          |
| always_requery    |      240 |              0.595833 |              0.666667 |        1     |        42 |      25 |               173 |           0.0708333 |               0.0458333  |
| frozen_signed_vof |      240 |              0.595833 |              0.616667 |        0.525 |        24 |      19 |                83 |           0.0208333 |               0.00770833 |
| oracle_query      |      240 |              0.595833 |              0.770833 |        0.175 |        42 |       0 |                 0 |           0.175     |               0.170625   |

## Cells

| position_level   |   task_id | task_description                                      |   commit_success_rate |   policy_success_rate |   query_rate |   rescues |   harms |   neutral_queries |   raw_success_delta |   adjusted_success_delta |   states |   always_requery_success_rate |   router_success_rate |
|:-----------------|----------:|:------------------------------------------------------|----------------------:|----------------------:|-------------:|----------:|--------:|------------------:|--------------------:|-------------------------:|---------:|------------------------------:|----------------------:|
| x0.2             |         5 | pick the tomato sauce and place it in the basket      |                 0.375 |                 0.475 |        0.625 |         6 |       2 |                17 |               0.1   |                 0.084375 |       40 |                         0.625 |                 0.475 |
| x0.2             |         6 | pick the butter and place it in the basket            |                 0.55  |                 0.55  |        0     |         0 |       0 |                 0 |               0     |                 0        |       40 |                         0.5   |                 0.55  |
| y0.1             |         4 | pick the ketchup and place it in the basket           |                 0.65  |                 0.675 |        0.15  |         1 |       0 |                 5 |               0.025 |                 0.02125  |       40 |                         0.9   |                 0.675 |
| y0.1             |         5 | pick the tomato sauce and place it in the basket      |                 0.85  |                 1     |        0.95  |         6 |       0 |                32 |               0.15  |                 0.12625  |       40 |                         1     |                 1     |
| y0.2             |         8 | pick the chocolate pudding and place it in the basket |                 0.7   |                 0.9   |        0.5   |         9 |       1 |                10 |               0.2   |                 0.1875   |       40 |                         0.875 |                 0.9   |
| y0.3             |         5 | pick the tomato sauce and place it in the basket      |                 0.45  |                 0.1   |        0.925 |         2 |      16 |                19 |              -0.35  |                -0.373125 |       40 |                         0.1   |                 0.1   |

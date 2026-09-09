# Signed-VoF new-task baseline atlas

This stage used only max-value commit outcomes. No feedback branch or router
prediction participated in cell selection.

- Candidate rows: 720
- Attempted decision states: 180
- Strict usable states: 180/180
- Eligible boundary cells: 16
- Gate: **PASS**
- Decision: `advance_to_frozen_router_new_task_holdout`

## Selected cells

| position_level   | direction   |   task_id | task_description                                      |   attempted_states |   strict_states |   successes |   failures |   commit_success_rate |   commit_success_ci_low |   commit_success_ci_high |   boundary_distance | eligible_boundary   |
|:-----------------|:------------|----------:|:------------------------------------------------------|-------------------:|----------------:|------------:|-----------:|----------------------:|------------------------:|-------------------------:|--------------------:|:--------------------|
| y0.1             | y           |         4 | pick the ketchup and place it in the basket           |                  5 |               5 |           2 |          3 |                   0.4 |                0.117621 |                 0.769276 |                 0.1 | True                |
| x0.2             | x           |         5 | pick the tomato sauce and place it in the basket      |                  5 |               5 |           2 |          3 |                   0.4 |                0.117621 |                 0.769276 |                 0.1 | True                |
| y0.1             | y           |         5 | pick the tomato sauce and place it in the basket      |                  5 |               5 |           3 |          2 |                   0.6 |                0.230724 |                 0.882379 |                 0.1 | True                |
| y0.3             | y           |         5 | pick the tomato sauce and place it in the basket      |                  5 |               5 |           3 |          2 |                   0.6 |                0.230724 |                 0.882379 |                 0.1 | True                |
| x0.2             | x           |         6 | pick the butter and place it in the basket            |                  5 |               5 |           3 |          2 |                   0.6 |                0.230724 |                 0.882379 |                 0.1 | True                |
| y0.2             | y           |         8 | pick the chocolate pudding and place it in the basket |                  5 |               5 |           3 |          2 |                   0.6 |                0.230724 |                 0.882379 |                 0.1 | True                |

A PASS authorizes a prospective frozen-router holdout on init states 5-24.
It is not itself evidence that the router transfers.

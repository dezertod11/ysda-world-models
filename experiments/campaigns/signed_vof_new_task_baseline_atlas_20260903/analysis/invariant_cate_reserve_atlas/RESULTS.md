# Outcome-blind invariant-CATE reserve atlas

- Reserve cells / states: 10 / 50.
- New task IDs: [1, 2, 7, 9].
- Support rate: 100.0%.
- Query rate: 36.0%.
- Gate: **PASS**.
- Decision: `freeze_full_reserve_holdout`.

| position_level   |   task_id | task_description                                      |   states |   atlas_commit_sr |   support_rate |   query_rate |   cate_mean |   cate_min |   cate_max |   support_distance_mean |
|:-----------------|----------:|:------------------------------------------------------|---------:|------------------:|---------------:|-------------:|------------:|-----------:|-----------:|------------------------:|
| x0.2             |         2 | pick the salad dressing and place it in the basket    |        5 |               0.8 |              1 |          0.2 |   0.029442  | -0.126966  |  0.439171  |                0.889903 |
| x0.2             |         9 | pick the orange juice and place it in the basket      |        5 |               0.6 |              1 |          0.8 |   0.30655   | -0.0897135 |  0.555505  |                1.32207  |
| y0.1             |         6 | pick the butter and place it in the basket            |        5 |               0.8 |              1 |          0.4 |   0.0389276 | -0.0860827 |  0.285102  |                0.837501 |
| y0.1             |         8 | pick the chocolate pudding and place it in the basket |        5 |               0.8 |              1 |          0.4 |  -0.0755845 | -0.553517  |  0.292849  |                1.00477  |
| y0.1             |         9 | pick the orange juice and place it in the basket      |        5 |               0.8 |              1 |          0.2 |  -0.0866784 | -0.303434  |  0.387836  |                0.972727 |
| y0.2             |         4 | pick the ketchup and place it in the basket           |        5 |               0.2 |              1 |          1   |   0.197108  |  0.0441053 |  0.349045  |                1.09537  |
| y0.2             |         6 | pick the butter and place it in the basket            |        5 |               0.2 |              1 |          0.2 |  -0.102413  | -0.237367  |  0.164355  |                0.922487 |
| y0.2             |         7 | pick the milk and place it in the basket              |        5 |               0.8 |              1 |          0.2 |  -0.0245103 | -0.106804  |  0.0291708 |                0.910991 |
| y0.2             |         9 | pick the orange juice and place it in the basket      |        5 |               0.2 |              1 |          0.2 |  -0.0836637 | -0.278073  |  0.178356  |                0.911226 |
| y0.3             |         1 | pick the cream cheese and place it in the basket      |        5 |               0.2 |              1 |          0   |  -0.102666  | -0.218569  |  0.0235935 |                1.11126  |

Feedback outcomes were not available or used in this scoring step.

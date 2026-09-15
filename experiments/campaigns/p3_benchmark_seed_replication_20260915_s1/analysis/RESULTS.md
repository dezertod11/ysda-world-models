# P3: three-factor comparison

Matched cases: 33/199; complete: False.

Same valid199 configurations; fresh paired collection, not untouched evaluation.
Incomplete/technical runs are excluded, never scored as failures.
P3-at72 is a historical timing control. P3-event is an exploratory observation-triggered method.

| arm           |   Object |   Environment |   Position |   Macro-SR, % | Success / N   |
|:--------------|---------:|--------------:|-----------:|--------------:|:--------------|
| first_k1      |   100.00 |         33.33 |      50.00 |         61.11 | 19/33         |
| max_value_h16 |   100.00 |         33.33 |      45.83 |         59.72 | 18/33         |
| h8_at72       |   100.00 |         33.33 |      50.00 |         61.11 | 19/33         |
| p3_at72       |    66.67 |         33.33 |      41.67 |         47.22 | 15/33         |
| p3_event      |   100.00 |         33.33 |      45.83 |         59.72 | 18/33         |

[Videos](videos.html)
[Per-query metrics](query_metrics.csv)

Intervals preserve task/init clusters within each factor, including Position levels together.
Use logical model calls for cost: exact equal-input samples are cached across paired arms.
Outcome labels and prediction errors after a chunk are not pre-failure input features.

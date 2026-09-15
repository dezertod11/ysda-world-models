# P3: three-factor comparison

Matched cases: 199/199; complete: True.

Same valid199 configurations; fresh paired collection, not untouched evaluation.
Incomplete/technical runs are excluded, never scored as failures.
P3-at72 is a historical timing control. P3-event is an exploratory observation-triggered method.

| arm           |   Object |   Environment |   Position |   Macro-SR, % | Success / N   |
|:--------------|---------:|--------------:|-----------:|--------------:|:--------------|
| first_k1      |    96.00 |         40.00 |      29.29 |         55.10 | 97/199        |
| max_value_h16 |    94.00 |         40.00 |      26.26 |         53.42 | 93/199        |
| h8_at72       |    94.00 |         42.00 |      26.26 |         54.09 | 94/199        |
| p3_at72       |    88.00 |         42.00 |      30.30 |         53.43 | 95/199        |
| p3_event      |    94.00 |         40.00 |      26.26 |         53.42 | 93/199        |

| method   | control       |   pairs |   clusters |   delta_pp |   ci_low_pp |   ci_high_pp |   cluster_sign_p |   rescues |   harms |   holm_p |
|:---------|:--------------|--------:|-----------:|-----------:|------------:|-------------:|-----------------:|----------:|--------:|---------:|
| p3_at72  | max_value_h16 |     199 |        110 |     0.0135 |     -3.6701 |       3.7801 |           0.9486 |         9 |       7 |   1.0000 |
| p3_at72  | h8_at72       |     199 |        110 |    -0.6532 |     -3.7598 |       2.6667 |           0.8778 |         5 |       4 |   1.0000 |
| p3_event | max_value_h16 |     199 |        110 |     0.0000 |      0.0000 |       0.0000 |           1.0000 |         0 |       0 |   1.0000 |
| p3_event | p3_at72       |     199 |        110 |    -0.0135 |     -3.7801 |       3.6701 |           0.9486 |         7 |       9 |   1.0000 |

[Videos](videos.html)
[Per-query metrics](query_metrics.csv)

Intervals preserve task/init clusters within each factor, including Position levels together.
Use logical model calls for cost: exact equal-input samples are cached across paired arms.
Outcome labels and prediction errors after a chunk are not pre-failure input features.

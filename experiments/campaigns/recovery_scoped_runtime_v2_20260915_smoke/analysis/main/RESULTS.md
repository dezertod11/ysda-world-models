# Recovery confirmation: main

Complete: True. Cases: 2/2.

Fresh snapshot-v2 collection on the unchanged historical init25-32 support; technical validation only.
x0.3 cells absent in localizer calibration; not new objects or official whole benchmark.
Early success is retained in the denominator. Invalid/incomplete jobs are not scored as failures.
Safety proxies in branch rows cover the suffix only; baseline_h16 proxies cover the full episode. Do not compare these as identical safety endpoints.
Timing branches share one uninterrupted H16 reference trajectory and are not independent samples.
No fit or outcome-dependent promotion. No claim of official AR planning or whole-benchmark SR.

|                                              |   n |   successes |   sr |
|:---------------------------------------------|----:|------------:|-----:|
| (72, 'replication', 'baseline_h16')          |   1 |           0 |    0 |
| (72, 'replication', 'continue_h8')           |   1 |           1 |    1 |
| (72, 'replication', 'physical_regrasp')      |   1 |           1 |    1 |
| (72, 'replication', 'refresh_preserve_only') |   1 |           1 |    1 |
| (72, 'transfer', 'baseline_h16')             |   1 |           0 |    0 |
| (72, 'transfer', 'continue_h8')              |   1 |           0 |    0 |
| (72, 'transfer', 'physical_regrasp')         |   1 |           0 |    0 |
| (72, 'transfer', 'refresh_preserve_only')    |   1 |           0 |    0 |

|   boundary | scope       | family   | left                  | right            |   pairs |   clusters |   delta |   ci_low |   ci_high |   rescues |   harms |   cluster_sign_p |   holm_p |
|-----------:|:------------|:---------|:----------------------|:-----------------|--------:|-----------:|--------:|---------:|----------:|----------:|--------:|-----------------:|---------:|
|         72 | replication | primary  | physical_regrasp      | continue_h8      |       1 |          1 |     0   |      0   |       0   |         0 |       0 |                1 |        1 |
|         72 | transfer    | primary  | physical_regrasp      | continue_h8      |       1 |          1 |     0   |      0   |       0   |         0 |       0 |                1 |        1 |
|         72 | all         | primary  | refresh_preserve_only | physical_regrasp |       2 |          2 |     0   |      0   |       0   |         0 |       0 |                1 |        1 |
|         72 | all         | primary  | physical_regrasp      | baseline_h16     |       2 |          2 |     0.5 |      0.5 |       0.5 |         1 |       0 |                1 |        1 |

[All comparison videos](videos.html)
[Per-query uncertainty](query_metrics.csv)
[Per-cell scores](cell_scores.csv)

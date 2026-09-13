# Recovery confirmation: main

Complete: False. Cases: 108/128.

fresh seeds on calibration-disjoint inits, not globally untouched init states.
x0.3 cells absent in localizer calibration; not new objects or official whole benchmark.
Early success is retained in the denominator. Invalid/incomplete jobs are not scored as failures.
Safety proxies in branch rows cover the suffix only; baseline_h16 proxies cover the full episode. Do not compare these as identical safety endpoints.
Timing branches share one uninterrupted H16 reference trajectory and are not independent samples.
No fit or outcome-dependent promotion. No claim of official AR planning or whole-benchmark SR.

|                                              |   n |   successes |        sr |
|:---------------------------------------------|----:|------------:|----------:|
| (72, 'replication', 'baseline_h16')          |  61 |          16 | 0.262295  |
| (72, 'replication', 'continue_h8')           |  61 |          16 | 0.262295  |
| (72, 'replication', 'physical_regrasp')      |  61 |          40 | 0.655738  |
| (72, 'replication', 'refresh_preserve_only') |  61 |          40 | 0.655738  |
| (72, 'transfer', 'baseline_h16')             |  47 |           0 | 0         |
| (72, 'transfer', 'continue_h8')              |  47 |           0 | 0         |
| (72, 'transfer', 'physical_regrasp')         |  47 |           1 | 0.0212766 |
| (72, 'transfer', 'refresh_preserve_only')    |  47 |           1 | 0.0212766 |

Inference withheld for incomplete/technical data.

[All comparison videos](videos.html)
[Per-query uncertainty](query_metrics.csv)
[Per-cell scores](cell_scores.csv)

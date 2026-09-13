# Conditional candidate replication

Status: completed; 690/690 planned branches.
Fixed pairs selected on prior development; new suffix seeds test only conditional replication.
Neighbor pools are a diagnostic, not a deployable selector transfer benchmark. Partial results are not final.

| kind        | job_id          |   candidate_idx | selected   |   branches |   successes |   sr |    value |   contact_steps |   local_lift |   local_drop |   terminal_drop |
|:------------|:----------------|----------------:|:-----------|-----------:|------------:|-----:|---------:|----------------:|-------------:|-------------:|----------------:|
| neighbor    | neighbor_t0_i10 |               0 | False      |         10 |           3 |  0.3 | 0.319916 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i10 |               1 | False      |         10 |           6 |  0.6 | 0.318873 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i10 |               2 | False      |         10 |           2 |  0.2 | 0.319359 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i10 |               3 | False      |         10 |           3 |  0.3 | 0.318657 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i10 |               4 | False      |         10 |           4 |  0.4 | 0.319216 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i10 |               5 | False      |         10 |           0 |  0   | 0.320589 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i10 |               6 | False      |         10 |           1 |  0.1 | 0.318722 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i10 |               7 | True       |         10 |           3 |  0.3 | 0.322088 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i11 |               0 | False      |         10 |           0 |  0   | 0.295208 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               1 | True       |         10 |           0 |  0   | 0.29831  |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               2 | False      |         10 |           0 |  0   | 0.295329 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               3 | False      |         10 |           0 |  0   | 0.298093 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               4 | False      |         10 |           0 |  0   | 0.29742  |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               5 | False      |         10 |           0 |  0   | 0.294694 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               6 | False      |         10 |           0 |  0   | 0.295774 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i11 |               7 | False      |         10 |           0 |  0   | 0.295901 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               0 | False      |         10 |           0 |  0   | 0.308514 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               1 | False      |         10 |           0 |  0   | 0.306706 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               2 | False      |         10 |           0 |  0   | 0.30649  |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               3 | False      |         10 |           0 |  0   | 0.306751 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               4 | False      |         10 |           0 |  0   | 0.308488 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               5 | False      |         10 |           0 |  0   | 0.30788  |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               6 | True       |         10 |           0 |  0   | 0.309301 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i12 |               7 | False      |         10 |           0 |  0   | 0.307677 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               0 | False      |         10 |           5 |  0.5 | 0.321202 |               0 |   0          |            0 |             0.1 |
| neighbor    | neighbor_t0_i9  |               1 | False      |         10 |           3 |  0.3 | 0.320263 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               2 | False      |         10 |           1 |  0.1 | 0.319891 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               3 | False      |         10 |           0 |  0   | 0.321835 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               4 | True       |         10 |           0 |  0   | 0.324203 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               5 | False      |         10 |           0 |  0   | 0.321674 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               6 | False      |         10 |           0 |  0   | 0.322228 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t0_i9  |               7 | False      |         10 |           0 |  0   | 0.322917 |               0 |   0          |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               0 | False      |         10 |          10 |  1   | 0.509269 |              13 |   0.0739137  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               1 | False      |         10 |          10 |  1   | 0.510424 |              13 |   0.0768252  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               2 | False      |         10 |          10 |  1   | 0.510439 |              13 |   0.0770466  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               3 | False      |         10 |          10 |  1   | 0.510448 |              13 |   0.0777317  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               4 | False      |         10 |          10 |  1   | 0.509738 |              13 |   0.0773031  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               5 | False      |         10 |          10 |  1   | 0.50987  |              13 |   0.0768321  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               6 | True       |         10 |          10 |  1   | 0.510715 |              13 |   0.0773029  |            0 |             0   |
| neighbor    | neighbor_t2_i10 |               7 | False      |         10 |          10 |  1   | 0.510235 |              14 |   0.0736287  |            0 |             0   |
| neighbor    | neighbor_t2_i11 |               0 | False      |         10 |           6 |  0.6 | 0.354983 |               2 |   0.00164424 |            0 |             0.1 |
| neighbor    | neighbor_t2_i11 |               1 | False      |         10 |           4 |  0.4 | 0.354129 |               1 |   0.00184747 |            0 |             0.1 |
| neighbor    | neighbor_t2_i11 |               2 | False      |         10 |           4 |  0.4 | 0.356189 |               0 |   0.00166462 |            0 |             0.2 |
| neighbor    | neighbor_t2_i11 |               3 | True       |         10 |           4 |  0.4 | 0.357118 |               1 |   0.00169585 |            0 |             0.2 |
| neighbor    | neighbor_t2_i11 |               4 | False      |         10 |           3 |  0.3 | 0.356176 |               2 |   0.001658   |            0 |             0.1 |
| neighbor    | neighbor_t2_i11 |               5 | False      |         10 |           1 |  0.1 | 0.355382 |               0 |   0.00170824 |            0 |             0.1 |
| neighbor    | neighbor_t2_i11 |               6 | False      |         10 |           4 |  0.4 | 0.356741 |               2 |   0.00163168 |            0 |             0   |
| neighbor    | neighbor_t2_i11 |               7 | False      |         10 |           0 |  0   | 0.35602  |               2 |   0.00173403 |            0 |             0.4 |
| neighbor    | neighbor_t2_i12 |               0 | False      |         10 |           2 |  0.2 | 0.496498 |               4 |   0.00375007 |            0 |             0.9 |
| neighbor    | neighbor_t2_i12 |               1 | False      |         10 |          10 |  1   | 0.495566 |               7 |   0.0105491  |            0 |             0   |
| neighbor    | neighbor_t2_i12 |               2 | False      |         10 |           0 |  0   | 0.496234 |               6 |   0.00457768 |            0 |             0.5 |
| neighbor    | neighbor_t2_i12 |               3 | False      |         10 |          10 |  1   | 0.496573 |               1 |   0.00197108 |            0 |             0   |
| neighbor    | neighbor_t2_i12 |               4 | False      |         10 |          10 |  1   | 0.495798 |               1 |   0.00194774 |            0 |             0   |
| neighbor    | neighbor_t2_i12 |               5 | False      |         10 |          10 |  1   | 0.497025 |               1 |   0.00195197 |            0 |             0   |
| neighbor    | neighbor_t2_i12 |               6 | False      |         10 |          10 |  1   | 0.496256 |               0 |   0.00197922 |            0 |             0   |
| neighbor    | neighbor_t2_i12 |               7 | True       |         10 |          10 |  1   | 0.499381 |               0 |   0.00196884 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               0 | True       |         10 |           9 |  0.9 | 0.512901 |               5 |   0.00344722 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               1 | False      |         10 |          10 |  1   | 0.511832 |               6 |   0.00344107 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               2 | False      |         10 |           9 |  0.9 | 0.512172 |               5 |   0.00336238 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               3 | False      |         10 |           9 |  0.9 | 0.512471 |               5 |   0.00344517 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               4 | False      |         10 |          10 |  1   | 0.512291 |               3 |   0.00187088 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               5 | False      |         10 |          10 |  1   | 0.512806 |               5 |   0.0033481  |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               6 | False      |         10 |           9 |  0.9 | 0.511989 |               6 |   0.00332433 |            0 |             0   |
| neighbor    | neighbor_t2_i9  |               7 | False      |         10 |          10 |  1   | 0.512451 |               3 |   0.00193902 |            0 |             0   |
| replication | repeat_pool_11  |               6 | False      |         10 |           6 |  0.6 | 0.317301 |               0 |   0          |            0 |             0.3 |
| replication | repeat_pool_11  |               7 | True       |         10 |           4 |  0.4 | 0.31847  |               0 |   0          |            0 |             0.5 |
| replication | repeat_pool_13  |               3 | False      |         10 |          10 |  1   | 0.504667 |              13 |   0.0610498  |            0 |             0   |
| replication | repeat_pool_13  |               4 | True       |         10 |           1 |  0.1 | 0.505659 |               5 |   0.00409989 |            0 |             0.9 |
| replication | repeat_pool_13  |               5 | False      |         10 |          10 |  1   | 0.504979 |              13 |   0.0601158  |            0 |             0   |

| job_id         |   alternative |   baseline |   pairs |   delta |   ci_low |   ci_high |   rescues |   harms |          p |    holm_p | conditional_replication_pass   |
|:---------------|--------------:|-----------:|--------:|--------:|---------:|----------:|----------:|--------:|-----------:|----------:|:-------------------------------|
| repeat_pool_13 |             3 |          4 |      10 |     0.9 |      0.7 |       1   |         9 |       0 | 0.00390625 | 0.0117188 | True                           |
| repeat_pool_13 |             5 |          4 |      10 |     0.9 |      0.7 |       1   |         9 |       0 | 0.00390625 | 0.0117188 | True                           |
| repeat_pool_11 |             6 |          7 |      10 |     0.2 |     -0.3 |       0.7 |         4 |       2 | 0.6875     | 0.6875    | False                          |

Local contact/lift/goal metrics are measured during [48,64]; terminal outcomes include later continuation.
Simulator signals are retrospective diagnostics, not online policy inputs.

[Videos](../videos.html)

```json
{
  "status": "completed",
  "completed_jobs": [
    "repeat_pool_13",
    "repeat_pool_11",
    "neighbor_t0_i9",
    "neighbor_t0_i10",
    "neighbor_t0_i11",
    "neighbor_t0_i12",
    "neighbor_t2_i9",
    "neighbor_t2_i10",
    "neighbor_t2_i11",
    "neighbor_t2_i12"
  ],
  "excluded": [],
  "branches": 690,
  "planned_branches": 690,
  "conditional_same_state_replication": true,
  "full_episode_new_controller": false,
  "neighbor_init_is_not_globally_untouched": true,
  "fixed_pair_effects": [
    {
      "job_id": "repeat_pool_13",
      "alternative": 3,
      "baseline": 4,
      "pairs": 10,
      "delta": 0.9,
      "ci_low": 0.7,
      "ci_high": 1.0,
      "rescues": 9,
      "harms": 0,
      "p": 0.00390625,
      "holm_p": 0.01171875,
      "conditional_replication_pass": true
    },
    {
      "job_id": "repeat_pool_13",
      "alternative": 5,
      "baseline": 4,
      "pairs": 10,
      "delta": 0.9,
      "ci_low": 0.7,
      "ci_high": 1.0,
      "rescues": 9,
      "harms": 0,
      "p": 0.00390625,
      "holm_p": 0.01171875,
      "conditional_replication_pass": true
    },
    {
      "job_id": "repeat_pool_11",
      "alternative": 6,
      "baseline": 7,
      "pairs": 10,
      "delta": 0.2,
      "ci_low": -0.3,
      "ci_high": 0.7,
      "rescues": 4,
      "harms": 2,
      "p": 0.6875,
      "holm_p": 0.6875,
      "conditional_replication_pass": false
    }
  ],
  "neighbor_split_effect": {
    "method": "split_selector",
    "reference": "max_value",
    "pairs": 80,
    "task_init_clusters": 8,
    "delta_sr": 0.05,
    "ci95_low": -0.0375,
    "ci95_high": 0.1875,
    "rescues": 7,
    "harms": 3,
    "cluster_signflip_p": 1.0
  },
  "local_metrics_variable_groups": 0
}
```

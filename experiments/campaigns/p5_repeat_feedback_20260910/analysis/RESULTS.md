# P5 suffix repeats and matched feedback

Status: completed; 1080/1080 branches.
Fixed development states; not a newly trained P5 head or full closed-loop controller deployment.

| mode   |   branches |   successes |       sr |   drop_proxy |   wrong_object_proxy |   continuation_queries |   extra_queries |
|:-------|-----------:|------------:|---------:|-------------:|---------------------:|-----------------------:|----------------:|
| fresh8 |        108 |          41 | 0.37963  |           10 |                    6 |                12.713  |               1 |
| open16 |        108 |          44 | 0.407407 |           10 |                    5 |                12.8704 |               0 |
| stale8 |        108 |          45 | 0.416667 |            5 |                    3 |                12.8426 |               1 |

| method   | reference   |   pairs |   task_init_clusters |   delta_sr |   ci95_low |   ci95_high |   rescues |   harms |   cluster_signflip_p |   holm_p |
|:---------|:------------|--------:|---------------------:|-----------:|-----------:|------------:|----------:|--------:|---------------------:|---------:|
| fresh8   | stale8      |     108 |                   10 | -0.037037  |  -0.205128 |   0.0972426 |        13 |      17 |             0.714844 |        1 |
| fresh8   | open16      |     108 |                   10 | -0.0277778 |  -0.166667 |   0.0916667 |        13 |      16 |             0.796875 |        1 |

Bootstrap and sign flips keep both queries, all suffix repeats and perturbation variants together by task/init.
Partial tables may have unequal support and must not be used as final method rankings.
Fresh/stale use one extra K1 call; stale consumes the aligned second half from the old observation.
All arms continue with the same K1/H16 policy and absolute-time seed schedule after t+16.
The empirical best mean over three suffixes is an optimistic diagnostic, not true optimal Q.
Label variation includes stochastic suffix sampling and residual numerical nondeterminism.

{
  "status": "completed",
  "branches": 1080,
  "expected_branches": 1080,
  "development_only": true,
  "full_episode_new_controller_test": false,
  "primary_comparison": "fresh8_minus_stale8",
  "original_state_action_groups": 18,
  "task_init_clusters": 10,
  "changed_from_original_fraction": 0.19444444444444445,
  "repeated_candidates_complete": 288,
  "fraction_candidates_with_variable_label": 0.3333333333333333,
  "paired_comparisons": [
    {
      "method": "fresh8",
      "reference": "stale8",
      "pairs": 108,
      "task_init_clusters": 10,
      "delta_sr": -0.037037037037037035,
      "ci95_low": -0.20512820512820512,
      "ci95_high": 0.09724264705882324,
      "rescues": 13,
      "harms": 17,
      "cluster_signflip_p": 0.71484375,
      "holm_p": 1.0
    },
    {
      "method": "fresh8",
      "reference": "open16",
      "pairs": 108,
      "task_init_clusters": 10,
      "delta_sr": -0.027777777777777776,
      "ci95_low": -0.16666666666666666,
      "ci95_high": 0.09166666666666666,
      "rescues": 13,
      "harms": 16,
      "cluster_signflip_p": 0.796875,
      "holm_p": 1.0
    }
  ]
}

[Videos](../videos.html)

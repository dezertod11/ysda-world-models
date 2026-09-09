# Position y0.2 signed-VoF router: leakage-safe development

## Status

This is a post-holdout development analysis. It may authorize new data collection,
but it is not confirmatory evidence for a selector.

- Screen cohort: **20** states / **20** init groups.
- Former holdout cohort: **60** states / **30** init groups.
- Former holdout rescue / harm: **10 / 9**.
- Opportunity gate: **PASS**.

## Target and online decision

$$
Y_i=\mathbb{1}[success_{feedback}]-\mathbb{1}[success_{commit}]\in\{-1,0,+1\}.
$$

The pre-query router pays for feedback only when its conservative score is positive:

$$
\hat\mu_{VoF}(x)-\beta\hat\sigma_{VoF}(x)-c_{query}>0.
$$

The post-query selector may compare the old action tail with the newly generated
prefix, but query cost is charged on every evaluated state.

## Best grouped OOF development policies

- Pre-query: `pre_state_action_a10` (pre, beta=0.0, budget=30%): 9 rescue / 1 harm, adjusted delta +12.6 pp.
- Post-query: `post_overlap_a1` (post, beta=0.0, budget=40%): 9 rescue / 0 harm, adjusted delta +12.5 pp.

These are selected from several model/budget combinations on development labels and
must be interpreted as optimistic discovery estimates.

The family-wise group-permutation test repeats the complete pre-query
model/beta/budget search. Its p-value is
**0.0030** (null 95th percentile
+9.2 pp).

## Screen-to-former-holdout diagnostic

| source_scope   | target_scope      | model                | stage   |   beta |   budget |   states |   selected |   query_rate |   selected_rescues |   selected_harms |   selected_neutral |   rescue_recall |   harm_avoidance |   balanced_accuracy |   baseline_success_rate |   method_success_rate |   raw_success_delta |   adjusted_success_delta |   adjusted_ci_low |   adjusted_ci_high |
|:---------------|:------------------|:---------------------|:--------|-------:|---------:|---------:|-----------:|-------------:|-------------------:|-----------------:|-------------------:|----------------:|-----------------:|--------------------:|------------------------:|----------------------:|--------------------:|-------------------------:|------------------:|-------------------:|
| screen_loio    | screen_to_holdout | pre_state_action_a10 | pre     |    0   |      0.4 |       60 |         24 |          0.4 |                  9 |                1 |                 14 |             0.9 |         0.888889 |            0.894444 |                0.533333 |              0.666667 |            0.133333 |                 0.123333 |         0.025     |           0.222917 |
| screen_loio    | screen_to_holdout | post_overlap_a1      | post    |    0.5 |      0.5 |       60 |         30 |          1   |                 10 |                0 |                 20 |             1   |         1        |            1        |                0.533333 |              0.7      |            0.166667 |                 0.141667 |         0.0583333 |           0.241667 |

The budget and model in each row were chosen using only screen-cohort OOF labels;
the outcomes in the target cohort were not used for that row's ranking choice.
Because the feature families themselves were designed after viewing the holdout, this
still remains exploratory rather than a recovered confirmatory test.
The fixed-mask target-cohort randomization p-value for the pre-query row is **0.0005**.

## Prediction diagnostics

| scope        | model                 | stage   |   alpha |   states |   groups |   features |     rmse |   spearman_effect |   rescue_vs_all_auc |   rescue_vs_harm_auc |
|:-------------|:----------------------|:--------|--------:|---------:|---------:|-----------:|---------:|------------------:|--------------------:|---------------------:|
| holdout_loio | post_overlap_a1       | post    |       1 |       60 |       30 |         20 | 0.475029 |          0.577027 |               0.826 |             0.944444 |
| holdout_loio | post_overlap_a10      | post    |      10 |       60 |       30 |         20 | 0.453544 |          0.584105 |               0.844 |             0.944444 |
| holdout_loio | pre_state_action_a10  | pre     |      10 |       60 |       30 |         39 | 0.477768 |          0.511866 |               0.878 |             0.922222 |
| holdout_loio | post_combined_a100    | post    |     100 |       60 |       30 |         78 | 0.479076 |          0.495983 |               0.84  |             0.922222 |
| holdout_loio | post_combined_a10     | post    |      10 |       60 |       30 |         78 | 0.51114  |          0.515863 |               0.814 |             0.9      |
| holdout_loio | pre_combined_a10      | pre     |      10 |       60 |       30 |         58 | 0.523939 |          0.412738 |               0.824 |             0.877778 |
| holdout_loio | pre_state_action_a100 | pre     |     100 |       60 |       30 |         39 | 0.493119 |          0.469363 |               0.868 |             0.855556 |
| holdout_loio | pre_combined_a100     | pre     |     100 |       60 |       30 |         58 | 0.508431 |          0.374942 |               0.792 |             0.8      |
| holdout_loio | pre_core_a1           | pre     |       1 |       60 |       30 |         19 | 0.584313 |          0.195176 |               0.576 |             0.688889 |
| holdout_loio | pre_core_a10          | pre     |      10 |       60 |       30 |         19 | 0.556512 |          0.150607 |               0.544 |             0.655556 |

## Leakage audit

`feedback_endpoint_*` and every realized local/terminal branch metric are excluded.
Those endpoint arrays were saved after the new tail executed and would leak the
intervention outcome. Pre-query models use only original q4 outputs and current
proprio. Post-query models add only newly generated actions/value and old-tail versus
new-prefix disagreement, all available before the chosen tail executes.

## Decision

advance_to_targeted_boundary_collection_and_freeze_after_development

A PASS permits a targeted boundary collection and freezing a compact router. It does
not permit a success claim. A new task/init split remains mandatory.

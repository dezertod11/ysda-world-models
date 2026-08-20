# Prediction-error surrogate replanning: hypotheses and protocol

Protocol frozen on 19 August 2026 before the new online rollout outcomes are
observed. The previous confirmatory result is treated as development evidence:
`requery_l1_h8` improved pooled success from 63.9% to 79.4%, but harmed two of
six cases and had normalized query cost 1.27x.

## Motivation

The old q0 difficulty gate does not transfer. A nested leave-one-case-out
counterfactual gate built from q0 features reached 76.7%, below the unconditional
requery result of 79.4%. The next decision therefore operates at each query and
estimates whether the *next chunk* is likely to diverge from the world-model
prediction.

## Frozen causal surrogate

The ridge model is trained only on information available before an action is
executed. Its target is the future-proprio L2 error measured after the selected
16-step chunk:

\[
e_q=\|\hat p_{q+1}-p_{q+1}\|_2.
\]

For each query, the online features are:

- \(U^a_q\): mean internal-copy disagreement of the action chunk;
- \(U^p_q\): mean internal-copy disagreement of predicted future proprio;
- \(\bar V_q\): mean value across four stochastic candidates;
- \(D^p_q\): across-candidate standard deviation of predicted future proprio.

With \(z_j=(\log\max(x_j,10^{-10})-\mu_j)/\sigma_j\), the frozen model is

\[
\log \hat e_q = -2.89194
+0.12337z(U^a_q)
+0.13764z(U^p_q)
+0.40796z(\bar V_q)
+0.30282z(D^p_q).
\]

It was fitted on 1,430 `max(value)` queries from 86 episodes and evaluated on
1,400 queries from 100 disjoint denoise-10 episodes, with zero episode-key
overlap. Test Spearman correlation is 0.745, case-controlled Spearman is 0.649,
and case-relative top-quartile error AUROC is 0.771. The reproducible artifact
is `experiments/models/future_proprio_error_surrogate_v1.json`.

Three thresholds are fixed from train-prediction quantiles:

| Quantile | Error threshold | Test alarm rate |
| ---: | ---: | ---: |
| 0.60 | 0.0630 | 38.3% |
| 0.75 | 0.0884 | 24.1% |
| 0.90 | 0.1468 | 9.9% |

## Online hypotheses

### S1. Surrogate-gated selection and horizon

\[
G_q=\mathbb{1}[\hat e_q\ge\tau_e].
\]

When `G_q=1`, select the risk-aware candidate and execute 8 actions. Otherwise,
select `max(value)` and execute all 16 actions. This should preserve the benefit
of early real observations while avoiding unconditional uncertainty penalties.

### S2. Surrogate horizon only

Always select the action-uncertainty candidate, but shorten the chunk only when
`G_q=1`. This isolates whether the main gain comes from candidate ranking or
from receding-horizon feedback.

### S3. Surrogate plus ranking disagreement

Always use action-aware ranking and shorten the chunk only when both the
surrogate alarm and `argmax(value) != argmax(risk-aware score)`. This is the
most compute-conservative variant.

### S4. Phase-aware requery

Use action-aware ranking only while `t / T_max <= rho`; shorten the chunk during
that phase only when rankings disagree. This directly combines confirmed H4 and
H5 without a learned surrogate.

### S5. Phase-surrogate hybrid

Use the confirmed phase-aware action ranking in the first `rho` fraction. At
any query with a surrogate alarm, use action-aware ranking and execute 8 actions.
Outside both conditions, use `max(value)` with 16 actions.

## Screening protocol

- Six previously characterized mixed-outcome cases are used as development
  tasks; all rollout seeds are new (`810000...860000`, step 97).
- Eight paired seeds are run for every hyperparameter configuration.
- Four stochastic candidates and denoise-10 inference match the previous
  confirmatory campaign.
- Controls are `max(value)`, fixed `action_l1`, `phase_l1_r0.3`, and
  `requery_l1_h8`.
- Surrogate thresholds are exactly 0.0630, 0.0884, and 0.1468.
- Phase fractions are exactly 0.3 and 0.5; short horizon is fixed at 8.
- Total planned executions: 816 paired strategy rollouts.

Primary screening utility is

\[
J=\Delta_{pool}+0.5\min_c\Delta_c
-0.02\max(0,Q_{ratio}-1).
\]

Only one surrogate-based and one non-surrogate adaptive method may advance.
Selection is performed separately in the `surrogate_adaptive` and
`non_surrogate_adaptive` categories with the utility above. Screening outcomes
are not reported as confirmatory evidence.

## Frozen confirmatory design

After selection, both methods are compared with `max(value)`, fixed
`action_l1`, and the previously confirmed `requery_l1_h8`. Hyperparameters are
parsed directly from `selected_for_confirmatory.csv`; they are not refitted.
Each strategy receives 20 paired, previously unused rollout seeds on every
case (`910000...1020000`, step 97).

The confirmatory set has 12 cases. Six repeat the characterized boundary tasks
with disjoint seeds: spatial milk task 5, spatial yellow-book task 8, long-horizon
mug task 4, spatial mug task 0, long-horizon milk task 9, and goal mug task 9.
Six were fixed before inspecting screening outcomes and test new LIBERO-PRO
axes/families:

| Generalization axis | Suite / task |
| --- | --- |
| object appearance | `libero_spatial_object`, task 0 |
| semantic language | `libero_spatial_lan`, task 6 |
| spatial swap | `libero_spatial_swap`, task 8 |
| task logic | `libero_goal_task`, task 6 |
| object-family appearance | `libero_object_object`, task 7 |
| long-horizon spatial swap | `libero_10_swap`, task 4 |

The primary outcome is paired episode success relative to `max(value)`, with a
stratified bootstrap confidence interval and exact McNemar test. Secondary
outcomes are worst-case case delta, query-compute ratio, surrogate alarm rate,
requery rate, prediction error, and collected safety signals. Subgroup results
for repeated boundary and new OOD cases are reported without changing the
primary pooled test.

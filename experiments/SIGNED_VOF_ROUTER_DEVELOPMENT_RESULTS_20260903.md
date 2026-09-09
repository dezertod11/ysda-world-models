# Signed Value-of-Feedback Router: Development Result

## Question

Can decision-time Cosmos signals predict whether a real-observation re-query at
query 4 will improve or harm terminal task success?

For exact-state commit/feedback branches, the signed target is

$$
Y_i = \mathbb{1}[S_i^{feedback}] - \mathbb{1}[S_i^{commit}]
\in \{-1,0,+1\}.
$$

`+1` is a rescue, `-1` is a harm, and `0` means that the intervention does not
change terminal success.

## Leakage-safe inputs

The strongest pre-query model uses only information available before requesting
a new plan:

- current 9-dimensional proprioception;
- first action, mean action and per-dimension action variation of the selected
  old 16-step chunk;
- the old candidate's predicted 9-dimensional future proprioception.

Realized branch outcomes, observed future states, and every
`feedback_endpoint_*` field are excluded. The latter are stored only after the
new action tail has executed and would therefore leak the intervention result.

## Model and policy

A ridge model with `alpha=10` predicts signed VoF. Its decision score is

$$
R(x) = \widehat{\mu}_{VoF}(x) - \beta\widehat{\sigma}_{VoF}(x),
\qquad \beta=0.
$$

The development screen chose a 40% query budget. For prospective use this was
converted into an absolute threshold fitted once on all 80 development rows:

$$
query(x) = \mathbb{1}[R(x) > 0.1401658544].
$$

The immutable artifact is
[`signed_vof_pre_state_action_a10_v1.json`](frozen_models/signed_vof_pre_state_action_a10_v1.json).

## Evidence

The pooled grouped leave-one-init-out development analysis contains 80 states,
20 rescues and 11 harms. Its best pre-query policy selected 18/60 states in the
former holdout cohort, captured 9/10 rescues, admitted 1/9 harms, and changed SR
from 53.3% to 66.7%. Query-cost-adjusted gain was +12.6 percentage points with
an init-cluster bootstrap interval of `[+2.8; +22.5]` points. Rescue-vs-harm
AUROC was 0.922.

The stricter screen-to-former-holdout diagnostic selected the model and 40%
budget using only the original 20-state screen. Applied to the 60 target rows,
it captured 9 rescues and 1 harm; adjusted gain was +12.3 points with interval
`[+2.5; +22.3]`. Its fixed-mask randomization p-value was 0.00050.

The complete exploratory model/beta/budget search was also repeated inside a
group permutation test. The family-wise p-value was 0.0030 (1000
permutations).

## Interpretation and limits

This is the first strong evidence that the *sign* of feedback value is
predictable better than unconditional query timing in the balanced Position
`y0.2` data. The useful signal is grounded state/action consistency rather than
generic scalar `value_std` or internal-copy uncertainty. The chosen
uncertainty penalty is zero, so this result should not be described as a
validated uncertainty-LCB planner.

The result remains exploratory because the feature family was designed after
examining the former holdout. It authorizes only a frozen prospective test, not
an efficacy claim. That test first uses an outcome-blind baseline atlas on new
tasks 1-9, then evaluates the frozen absolute-threshold router on disjoint init
states.

Detailed generated tables and plots are under
[`campaigns/object_q4_position_direction_holdout_20260902/analysis/signed_vof_router_development`](campaigns/object_q4_position_direction_holdout_20260902/analysis/signed_vof_router_development/RESULTS.md).

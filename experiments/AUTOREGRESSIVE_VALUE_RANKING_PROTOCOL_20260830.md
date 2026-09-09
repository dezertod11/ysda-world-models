# Action-conditioned autoregressive value ranking protocol

Status: completed 30 August 2026; integrity PASS, efficacy gate FAIL. Results:
[`AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_RESULTS_20260830.md).

## Hypothesis

Parallel Cosmos inference samples action, future state, and value in one
diffusion pass. The alternative evaluator explicitly conditions each later
prediction on the earlier one:

$$
a^{(k)} \sim p_\theta(a \mid o_t, c), \qquad
\hat{s}^{(k)}_{t+16} \sim p_\theta(s' \mid o_t, c, a^{(k)}),
$$

$$
\hat{V}^{(k)}_{\mathrm{AR}}
\sim p_\theta(V \mid o_t, c, a^{(k)}, \hat{s}^{(k)}_{t+16}).
$$

The primary hypothesis is that
`argmax_k V_AR(k)` ranks terminally successful candidates better than the
parallel `argmax_k V_parallel(k)` on exact-state mixed-outcome pools.

## Frozen design

- Candidate budget: `K=8`; K16 added no oracle coverage in the preceding
  screen.
- Candidate seeds: offsets `0..7`.
- Decision state: `q=0` only, before any policy action is executed.
- Initial states: `5..9`, one rollout per state.
- Object cell: `libero_object_object`, task 0, base seed `5,100,000`.
- Position cell: `libero_object_temp_y0.3`, task 0, base seed `5,310,000`.
- Action denoising steps: 5; autoregressive future/value steps: 1/1.
- Each candidate is generated once. Its original joint latent provides
  `V_parallel`; the same action latent is then held fixed while future state
  and `V_AR` are generated autoregressively.
- Every candidate is executed for 16 steps and then continued to terminal by
  the unchanged **parallel** `max(value)`, `K=2`, H16 policy.
- Maximum episode length: 280 environment steps.

Both values and the terminal label therefore belong to the same physical
action chunk in one candidate row. The saved 28-component action signature
(first, last, mean, and standard deviation for seven dimensions) is retained
for audit, but no cross-run action matching is needed.

## Endpoints

Primary endpoints on states that were mixed under the frozen parallel run:

1. top-1 terminal success for parallel value and autoregressive value;
2. within-state success-vs-failure pairwise ranking accuracy;
3. number of selector rescues and harms after switching to autoregressive
   value.

Secondary endpoints:

- all-state selected terminal success;
- selected-candidate switch rate;
- Spearman agreement between parallel and autoregressive value;
- parallel/autoregressive value rank correlation;
- difference between the parallel and autoregressive predicted future proprio.

## Validity and decision gates

The comparison is valid only if all 80 candidate rows contain finite values,
`candidate_value` exactly equals its stored `candidate_parallel_value` alias,
and both evaluators refer to the same single action/terminal-outcome row.

The evaluator screen passes only if all of the following hold:

- combined mixed-pool top-1 success improves by at least one state;
- rescues exceed harms;
- neither Object nor Position mixed-pool top-1 success decreases.

This is a small, paired screening experiment. Passing routes the evaluator to
a new-init closed-loop holdout; failing routes the work toward a learned
within-state advantage critic rather than further tuning on these states.

## Integrity amendment

The first implementation regenerated parallel and autoregressive candidates in
separate model runs and planned to match them by seed. It was stopped after the
first Object state because the preregistered integrity threshold had already
failed irreversibly: 8/8 seeds matched, but action-signature maximum absolute
difference was `0.005839` and terminal outcomes agreed for only 4/8 branches.
No autoregressive ranking result was inspected. The stopped campaign is
archived on the server as
`autoregressive_value_ranking_20260830__invalid_separate_run_action_mismatch`.
The same-pass dual design above fixes this confound without using outcome
efficacy to choose a method or threshold.

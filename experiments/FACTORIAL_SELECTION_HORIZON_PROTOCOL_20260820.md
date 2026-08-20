# Candidate selection x feedback horizon

## Question

The previous confirmatory campaign found that `requery_l1_h8` improved success over
`max_value`, while the fixed-horizon `action_l1` effect was smaller. This experiment
tests whether the gain comes from selecting a different stochastic candidate, from
receiving real observations sooner, or from their interaction.

## Matched 2x2 design

Every cell uses the same suite, task, initial state, rollout seed, four stochastic
candidate seeds (`0,1,2,3`), denoising settings, and stopping rule.

| Mode | Selected candidate | Executed actions before feedback |
|---|---|---|
| `max_value` | argmax predicted value | 16 |
| `action_l1` | argmax `z(value) - z(action uncertainty)` | 16 |
| `horizon_only_l1_h8` | argmax predicted value | 8 only when the two selectors disagree, otherwise 16 |
| `requery_l1_h8` | risk-aware candidate | 8 only when the two selectors disagree, otherwise 16 |

The horizon-only condition computes the risk-aware candidate but never executes it;
the disagreement is used solely as a trigger for earlier real feedback.

## Cases and sample size

Seven LIBERO-PRO cases cover known mixed-outcome tasks, long-horizon tasks, one
previous regression sentinel, and an OOD spatial-swap task. Each case has 24 new,
matched rollout seeds and four strategies: 672 total rollouts. Seeds are disjoint
from the previous confirmatory campaign.

## Primary contrasts

Let `B`, `A`, `H`, and `AH` be binary success for baseline, selection-only,
horizon-only, and combined modes on a matched seed.

- Selection effect at fixed horizon: `A - B`.
- Feedback-horizon effect with max-value selection: `H - B`.
- Feedback-horizon effect with risk-aware selection: `AH - A`.
- Selection effect under adaptive feedback: `AH - H`.
- Combined effect: `AH - B`.
- Factorial interaction: `AH - A - H + B`.

Simple paired contrasts use exact McNemar tests. Confidence intervals and the
interaction use a case-stratified paired bootstrap. Query-count ratios report the
inference-cost tradeoff. Case-level effects are retained to expose regressions.

## Interpretation rule

- Positive `H-B` with near-zero `A-B` supports uncertainty as a feedback-timing
  signal rather than a reliable candidate-ranking signal.
- Positive `A-B` with near-zero `H-B` supports direct candidate reranking.
- A nonzero interaction means selection and feedback cannot be treated as additive.
- A pooled gain is not considered robust if it is driven by one case or introduces
  a large regression on the goal-mug sentinel.

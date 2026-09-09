# K16 proposal-opportunity screen: results

## Question

The experiment tested whether failures of `max(value)` planning on hard
LIBERO-PRO states are mostly caused by an insufficient stochastic proposal
pool. The same exact decision states were evaluated with nested candidate
budgets `K=4`, `K=8`, and `K=16`; every candidate was continued to the end of
the episode by the same frozen parallel `max(value)` policy with `K=2`.

## Data

The confirmatory screen contains 50 exact states and 800 terminal branches:

| Factor | States | Mixed pools | Greedy SR, K16 | Oracle SR, K16 | Gap |
|---|---:|---:|---:|---:|---:|
| Environment | 20 | 0 | 0% | 0% | 0 pp |
| Object | 10 | 7 | 50% | 80% | 30 pp |
| Position | 20 | 2 | 0% | 10% | 10 pp |

The grouped bootstrap 95% interval for the Object oracle gap is `[10, 50]`
percentage points. Position opportunity is localized to `y0.3, q=0`; all
`x0.3` states and all Position `q=3` states failed for every candidate.

## Nested candidate budget

| Factor | K | Greedy SR | Oracle SR | Oracle gain over previous K |
|---|---:|---:|---:|---:|
| Environment | 4 | 0% | 0% | - |
| Environment | 8 | 0% | 0% | 0 states |
| Environment | 16 | 0% | 0% | 0 states |
| Object | 4 | 40% | 80% | - |
| Object | 8 | 40% | 80% | 0 states |
| Object | 16 | 50% | 80% | 0 states |
| Position | 4 | 5% | 5% | - |
| Position | 8 | 0% | 10% | 1 state |
| Position | 16 | 0% | 10% | 0 states |

The proposal pool therefore saturates by `K=8`. Increasing it to `K=16`
does not create any new successful branch in Object or Position. In Position,
adding candidates even changes the greedy choice from success to failure in
one state.

## Value-ranking diagnosis

Across all 50 states there are nine mixed success/failure pools. Greedy
`max(value)` succeeds in only `4/9 = 44.4%` of them. Mean within-state
success-vs-failure pairwise value accuracy is `0.4755`, approximately chance.
Five states contain a successful action but assign the highest value to a
failure. The median positive overestimation margin is only `0.000231`, so the
argmax is brittle even though candidate values look numerically close.

## Decision

- **Do not increase `K` beyond 8** in the next experiments.
- **Object and Position-y pass the selector-opportunity gate.** They contain
  successful candidates that the current value head misranks.
- **Environment fails the selector gate.** Re-ranking cannot help when every
  sampled action fails; this factor should be studied with re-query/recovery
  or a genuinely different proposal mechanism.
- The next controlled test is an action-conditioned autoregressive evaluator:
  generate the same action candidates, then evaluate them through
  `action -> predicted future -> value` while keeping the continuation policy
  fixed.

Detailed tables and plots are in
`campaigns/proposal_opportunity_k16_20260830/analysis/k16_screen/` and
`campaigns/proposal_opportunity_k16_20260830/analysis/value_ranking/`.

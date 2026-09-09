# Initial real-observation re-query: independent holdout protocol

## Status

Preregistered after the phase-VoF experiment and before reading any outcome on
Environment tasks 8/9, init states 20-49. The motivating query-0 result is
exploratory; all gates below are frozen for this independent test.

## Hypothesis

The failed phase oracle showed three approach rescues and zero harms, all at
`query_idx=0`. One early real observation may correct an initially bad chunk
before it causes a drop or wrong-object interaction. Re-query during later
grasp/transport did not show a net terminal benefit.

The baseline is standard K=4 max-value planning with H16:

$$
\pi_{16}(q)=\operatorname*{argmax}_{i\in\{1,\ldots,4\}}
\widehat V_i(o_q), \qquad K_q=16.
$$

The intervention keeps exactly the same candidate selector and changes only
the first execution horizon:

$$
\pi_{Q0}(q)=\operatorname*{argmax}_i\widehat V_i(o_q),
\qquad
K_q=\begin{cases}8,&q=0,\\16,&q>0.\end{cases}
$$

Thus the method executes eight actions, observes the real environment, and
then returns to H16. It has no uncertainty threshold, phase oracle, learned
model, task exception or tunable coefficient.

## Independent split

| Suite | Task | Init states | Paired episodes | GPU shard |
|---|---:|---:|---:|---:|
| `libero_object_env` | 8 | 20-29 | 10 | 2 |
| `libero_object_env` | 8 | 30-39 | 10 | 3 |
| `libero_object_env` | 8 | 40-49 | 10 | 4 |
| `libero_object_env` | 9 | 20-34 | 15 | 5 |
| `libero_object_env` | 9 | 35-49 | 15 | 7 |
| **Total** | | | **60** | |

Each pair uses the same init state, rollout seed, K=4 candidate seeds, five
action denoising steps, parallel prediction and 280-step limit. These init
states were not used by the exact-state discovery run, which used 10-19.

## Endpoints

For paired episode $j$:

$$
\Delta_j=Y_{Q0,j}-Y_{16,j}, \qquad Y\in\{0,1\}.
$$

Primary endpoint is mean paired terminal success difference. We report
rescues, harms, exact McNemar p-value and a task-stratified paired bootstrap
CI. Secondary endpoints are per-task effects, target drop, wrong-object
interaction, official safety violation, timeout, final time and query count.

The compute-adjusted endpoint charges exactly one scheduled early feedback:

$$
J_c(\pi_{16})=\mathbb E[Y_{16}],
\qquad
J_c(\pi_{Q0})=\mathbb E[Y_{Q0}]-c,
\qquad c=0.025.
$$

## Integrity gate

1. Exactly 60 episodes per method and identical paired state keys.
2. Exactly 30 pairs per task; tasks are 8/9 and init states are 20-49.
3. Both methods always choose the max-value candidate.
4. Baseline executes H16 at every query.
5. The intervention executes H8 and marks re-query only at query 0, then H16.
6. Query-0 max-value candidate indices and candidate values match within
   numerical tolerance between paired methods.
7. Split label is `generalization`; no official safety termination is hidden.

## Frozen efficacy gate

The method advances only if every condition holds:

1. at least three rescues and strictly more rescues than harms;
2. paired SR improvement is at least 5 percentage points;
3. task-stratified 95% CI lower endpoint is non-negative;
4. neither task has negative net success;
5. $J_{0.025}(\pi_{Q0})>J_{0.025}(\pi_{16})$;
6. target-drop and wrong-object rates do not increase;
7. no official safety violation is added and integrity passes.

A PASS authorizes broad Object/Position/Environment transfer. A FAIL closes
the fixed initial schedule and moves the roadmap to semantic consequence
prediction rather than another hand-built timing rule.


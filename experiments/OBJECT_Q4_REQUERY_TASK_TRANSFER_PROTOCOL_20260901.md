# Object query-4 re-query: untouched-task transfer

## Frozen hypothesis

The task-0 holdout established that, at query 4, executing H8 and replacing the
old action tail after a real observation improves terminal success. This test
asks whether that fixed intervention transfers to new objects and language
commands in the same LIBERO-PRO Object factor.

No task, query index, horizon, cost or statistical direction is selected from
the transfer outcomes.

## Population

- Suite: `libero_object_object`.
- Untouched tasks: 1-9. Task 0 is excluded because it generated the hypothesis.
- Init states: 40-49 for every task.
- Two new rollout seeds per `(task, init)`.
- Total: 9 tasks x 10 init states x 2 seeds = 180 exact-state pairs.
- Decision: query 4, executed step 64.
- Four stochastic Cosmos candidates per policy query; select `max(value)`.

The commands cover nine target objects while preserving the same receptacle:
BBQ sauce, butter, chocolate pudding, cream cheese, ketchup, milk, orange
juice, salad dressing and tomato sauce, each placed in the basket.

## Paired intervention

Both terminal branches share the complete rollout prefix and candidate pool at
query 4:

1. `commit`: execute the selected H16 action chunk;
2. `requery`: execute H8, receive the real simulator observation, sample a new
   four-candidate pool, select `max(value)`, and execute H8.

Both branches continue with the same max-value H16 policy until success or
step 280. The intervention adds exactly one model query.

## Primary endpoint

For exact state $i$,

$$
Y_i = \mathbb{1}[success_{i,requery}]
      - \mathbb{1}[success_{i,commit}].
$$

Report micro and task-macro success-rate differences, rescue/harm counts,
two-sided exact McNemar test, and a 95% bootstrap confidence interval clustered
by `(task, init_state)`. Because every task has equal sample size, the frozen
micro and task-macro point estimates are identical.

With frozen query cost $c_{query}=0.025$,

$$
\Delta_{adjusted}=\frac{1}{N}\sum_iY_i-c_{query}.
$$

## Gates

Integrity requires:

- exactly 180 unique pairs and exactly two pairs per `(task, init)`;
- tasks 1-9, init states 40-49 and query 4 only;
- no task-0 state;
- both terminal branches present;
- replay-state maximum absolute error at most `1e-9` for every pair.

Practical transfer passes when raw and cost-adjusted suite-level deltas are
positive. The stronger confirmatory transfer claim additionally requires the
cluster-bootstrap lower bound to exceed zero and McNemar `p<0.05`.

Task-level effects, phase effects and failure transitions are prespecified
diagnostics. They do not redefine the primary endpoint after outcomes are
opened.

## Decision

- Confirmatory PASS permits an end-to-end suite-level deployment test.
- Practical PASS without confirmatory PASS keeps query 4 as a provisional
  Object-family schedule and requires another frozen task/seed replication.
- Practical FAIL rejects suite-wide transfer; the task-0 rule remains a narrow
  positive control for a learned object/contact value-of-feedback model.


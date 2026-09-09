# Object task-0 query-4 scheduled controller: deployment validation

## Frozen hypothesis

The deployable controller

$$
A_{64:72}^{old} \rightarrow o_{72}^{real} \rightarrow A_{72:80}^{new}
$$

reproduces the exact-state query-4 intervention and improves full-episode
terminal success over the original max-value H16 controller.

This is a new-seed implementation/deployment validation on the task that
generated the hypothesis. It is not an untouched-task transfer claim; that is
tested independently by `OBJECT_Q4_REQUERY_TASK_TRANSFER_PROTOCOL_20260901.md`.

## Population and methods

- Suite/task: `libero_object_object`, task 0.
- Init states: 0-49.
- Two new rollout seeds per init state: 100 paired episodes.
- Four stochastic candidates and `max(value)` selection at every query.
- Maximum episode length: 280 actions.

| Method | Horizon schedule |
|---|---|
| `maxV-H16` | H16 at every query |
| `maxV-Q4-H8-requery-H8` | H16 except H8 at query 4 and H8 at the immediate continuation query 5 |

The scheduled method returns to H16 at query 6. It performs exactly one extra
real-observation policy query for every episode that reaches query 4.

## Separate-run integrity

The two policies are evaluated in separate processes with matched seeds. To
guard against GPU nondeterminism before the intervention, each query trace
stores the full flattened MuJoCo state. A pair is strict only when, through
query 4:

- query times and selected max-value candidate indices match;
- simulator-state maximum absolute difference is at most `1e-9`;
- candidate-value and candidate-first-action maximum differences are at most
  `1e-5`.

The efficacy claim uses the strict subset. At least 95/100 strict pairs are
required. Nominal all-pair outcomes are descriptive.

## Endpoint and gates

For strict pair $i$,

$$
Y_i = \mathbb{1}[success_{i,scheduled}]
      - \mathbb{1}[success_{i,baseline}].
$$

Report paired SR difference, init-cluster bootstrap 95% CI, exact two-sided
McNemar test, rescue/harm counts, query count and failure modes.

With $c_{query}=0.025$ and one scheduled trigger $r_i$,

$$
\Delta_{adjusted}=\frac{1}{N}\sum_i(Y_i-0.025r_i).
$$

Practical PASS requires integrity, positive raw delta and positive adjusted
delta. Confirmatory PASS additionally requires cluster-CI lower bound above
zero and McNemar `p<0.05`.


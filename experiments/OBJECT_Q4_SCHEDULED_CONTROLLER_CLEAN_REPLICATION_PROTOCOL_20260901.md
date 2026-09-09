# Object task-0 query-4 controller: clean-GPU replication

## Motivation and freeze point

The first separate-process deployment run completed 100 matched-seed pairs but
failed its preregistered integrity gate: only 40 pairs, all produced on clean
GPUs 5-6, had identical prefixes. The 60 pairs on GPUs 2-4 were exposed to
other users' CUDA contexts and diverged from query 0. Their nominal outcomes
are descriptive and are not used to change the controller, endpoint, cost,
tolerances or statistical gates.

Before opening any outcome from this replication, we freeze an independent set
of rollout seeds and require a GPU-memory preflight. This is a technical and
statistical replication, not a continuation selected by first-run outcomes.

## Population and methods

- Suite/task: `libero_object_object`, task 0.
- Init states: 0-49.
- Two new rollout seeds per init state: 100 paired episodes.
- Physical GPUs: 5, 6 and 7 only; each must use at most 128 MiB before launch.
- Four stochastic candidates; select `max(value)` at every query.
- Episode limit: 280 executed actions.

| Method | Horizon schedule |
|---|---|
| `maxV-H16` | H16 at every query |
| `maxV-Q4-H8-requery-H8` | H16 except H8 at query 4 and H8 at query 5 after the real observation |

The method returns to H16 at query 6. No uncertainty threshold or outcome from
the failed-integrity deployment run enters the decision.

## Integrity and endpoint

The analysis and frozen tolerances are unchanged from
`OBJECT_Q4_SCHEDULED_CONTROLLER_PROTOCOL_20260901.md`. Through query 4, paired
runs must have matching query times and selected candidates, simulator-state
maximum absolute difference at most `1e-9`, and candidate value/action
differences at most `1e-5`. At least 95/100 strict pairs are required.

For strict pair $i$,

$$
Y_i = \mathbb{1}[success_{i,scheduled}]
      - \mathbb{1}[success_{i,baseline}].
$$

With the unchanged query cost $c_{query}=0.025$,

$$
\Delta_{adjusted}=\frac{1}{N}\sum_i(Y_i-0.025r_i).
$$

Practical PASS requires integrity plus positive raw and adjusted deltas.
Confirmatory PASS additionally requires an init-cluster bootstrap lower bound
above zero and exact two-sided McNemar `p<0.05`.

## Interpretation rule

- Confirmatory PASS validates the fixed task-0 deployment schedule.
- Practical-only PASS keeps it as a promising task-specific controller and
  requires a larger replication.
- Integrity FAIL blocks efficacy claims regardless of nominal SR.
- Efficacy FAIL rejects the fixed schedule as a deployable improvement even if
  the earlier exact-state intervention remains causally positive.

# Object query-4 re-query: untouched-task transfer results

## Question

The task-0 holdout showed that replacing the second half of the query-4 action
chunk after a real observation can improve success. This preregistered transfer
test kept the query, horizons, candidate count, selector, query cost and gates
fixed, and moved the intervention to Object tasks 1-9.

## Experiment

- Suite: `libero_object_object` (LIBERO-PRO Object perturbation).
- Tasks: 1-9; task 0 was excluded because it generated the hypothesis.
- Init states: 40-49, with two new rollout seeds per task/init cell.
- Exact-state pairs: 180 across 90 task/init clusters.
- `commit`: execute the selected H16 chunk.
- `requery`: execute H8, observe the real state, query again, and execute H8.
- Both branches then continue with the same four-candidate `max(value)` H16
  controller until success or 280 actions.
- Frozen additional-query cost: 0.025.

## Integrity

Coverage checks passed: all 180 planned pairs were present, every task/init cell
had exactly two pairs, and there were no duplicate analysis states. Exact replay
passed for 177/180 pairs. Three contact/transport states in tasks 6-7 exceeded
the frozen `1e-9` tolerance; their maximum absolute replay errors were
`7.51e-5`, `1.43e-3`, and `4.61e-2`. Consequently, the preregistered integrity
gate failed.

## Terminal results

| Endpoint | H16 commit | H8 + real-observation re-query + H8 | Difference |
|---|---:|---:|---:|
| Success rate, all 180 pairs | 100.0% | 100.0% | 0.0 pp |
| Task-macro success rate | 100.0% | 100.0% | 0.0 pp |
| Rescue / harm | - | - | 0 / 0 |
| Query-cost-adjusted effect | - | - | -2.5 pp |

Every individual task also had 20/20 successes in both branches. Since there
were no discordant outcomes, the McNemar statistic is undefined and the
cluster-bootstrap interval collapses to `[0, 0]`.

## Decision

- Integrity gate: **FAIL** (177/180 strict replays; 180/180 required).
- Practical transfer gate: **FAIL**.
- Confirmatory transfer gate: **FAIL**.

The fixed task-0 query-4 rule does not transfer as a useful unconditional
suite-wide policy. These tasks are at a complete success ceiling under the
selected population, so an extra query has no terminal benefit and only adds
cost. This result does not show that real-observation feedback is useless; it
shows that its value is state/task dependent. The positive task-0 result should
therefore be treated as a hard-cell positive control and as supervision for a
selective value-of-feedback controller, not as a schedule to apply to every
Object task.

Machine-readable outputs are in
`experiments/campaigns/object_q4_requery_task_transfer_20260901/analysis/object_q4_task_transfer/`.

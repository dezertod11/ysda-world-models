# Object task-0 query-4 scheduled controller: first deployment run

## Status

The full-episode implementation ran to completion, but the preregistered
separate-run integrity gate **failed**. Terminal outcomes are therefore
descriptive and cannot validate efficacy.

## Design and implementation checks

- Suite/task: `libero_object_object`, task 0.
- Init states: 0-49; two new rollout seeds per init state.
- Methods: 100 `maxV-H16` episodes and 100
  `maxV-Q4-H8-requery-H8` episodes.
- All 200 planned episodes and all 100 paired state keys were present.
- The state sets, task/init coverage, split and `max(value)` selector matched.
- The actual schedule passed its audit: H16 through query 3, H8 at query 4,
  H8 at the real-observation continuation query 5, then H16.

## Integrity failure

Only 40/100 pairs met the frozen prefix requirement of 95/100. The failure was
exactly aligned with GPU shards:

| Initial states | Physical GPU | Strict pairs |
|---|---:|---:|
| 0-9 | 2 | 0/20 |
| 10-19 | 3 | 0/20 |
| 20-29 | 4 | 0/20 |
| 30-39 | 5 | 20/20 |
| 40-49 | 6 | 20/20 |

At query 0 the failed shards started from the same MuJoCo state but already had
small candidate differences; these accumulated into different trajectories.
The largest prefix differences were `2.55` for simulator state, `0.241` for
candidate value and `2.014` for candidate first action. GPUs 2-4 had other
users' CUDA contexts during the run, whereas GPUs 5-6 were clean and produced
bit-identical prefixes. The alignment is consistent with a shared-GPU
nondeterminism/confounding mechanism, although the integrity test, rather than
that diagnosis, is what invalidates the claim.

## Descriptive outcomes

| Subset | Pairs | Baseline SR | Scheduled SR | Delta | 95% init-cluster CI | Rescue / harm | McNemar p | Adjusted delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All matched keys, non-strict | 100 | 46.0% | 57.0% | +11.0 pp | [-1.0, +23.0] pp | 24 / 13 | 0.0989 | +8.5 pp |
| Strict clean-GPU subset | 40 | 37.5% | 52.5% | +15.0 pp | [-5.0, +35.0] pp | 12 / 6 | 0.2379 | +12.5 pp |

The direction agrees with the prior exact-state holdout, but neither row is a
confirmatory result: the full row is confounded before intervention, and the
strict row is underpowered with a confidence interval crossing zero.

The main discordant terminal transitions in the nominal data were 15
`timeout_no_goal -> success`, six `target_drop_candidate -> success`, ten
`success -> timeout_no_goal`, and smaller deadlock/drop/wrong-object changes.

## Decision and remediation

- Integrity gate: **FAIL**.
- Practical gate: **FAIL by protocol**, regardless of the positive point
  estimate.
- Confirmatory gate: **FAIL**.

The controller remains promising but unvalidated in separate-process
deployment. A frozen independent-seed replication is run only on preflight
clean GPUs 5-7, with unchanged controller, endpoint, costs and tolerances; see
`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_PROTOCOL_20260901.md`.

Machine-readable outputs are in
`experiments/campaigns/object_q4_scheduled_controller_20260901/analysis/object_q4_scheduled_controller/`.

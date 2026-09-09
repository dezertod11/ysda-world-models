# Object task-0 query-4 scheduled controller: clean-replication results

## Decision

The frozen replication completed all 200 episodes, but its preregistered
integrity gate **failed**. The nominal outcome is a strong and internally
consistent positive signal, not a confirmatory causal deployment result.

The fixed controller remains a task-specific positive control. More
separate-process repetitions with the same runtime would not resolve the main
uncertainty; the next deployment test must share or deterministically replay
the complete pre-intervention prefix.

Frozen protocol:
[`OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_PROTOCOL_20260901.md`](OBJECT_Q4_SCHEDULED_CONTROLLER_CLEAN_REPLICATION_PROTOCOL_20260901.md).

## Design and completion

- Suite/task: `libero_object_object`, task 0.
- Init states: 0-49, with two new rollout seeds per init state.
- Baseline: 100 full episodes with `maxV-H16`.
- Method: 100 full episodes with `maxV-Q4-H8-requery-H8`.
- Both methods used four stochastic candidates and selected `max(value)` at
  every query.
- The method used H16 through query 3, H8 at query 4, H8 after the real
  observation at query 5, and H16 from query 6 onward.
- Episode limit: 280 actions; physical GPUs 5-7 passed the frozen memory
  preflight before launch.

All 200 episodes, 100 matched keys, 50 init states and both strategies are
present. The suite, task, split, selector and executed horizon schedule all
pass their audits.

## Terminal outcomes

| Subset | Pairs | Baseline SR | Scheduled SR | Delta | 95% init-cluster CI | Rescue / harm | McNemar p | Cost-adjusted delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| All matched keys, non-strict | 100 | 35.0% | 54.0% | **+19.0 pp** | **[+9.0, +29.0] pp** | 25 / 6 | **0.000878** | +16.5 pp |
| Strict-prefix sensitivity | 34 | 41.2% | 55.9% | +14.7 pp | [0.0, +29.4] pp | 7 / 2 | 0.1797 | +12.2 pp |

For pair $i$, the terminal contrast is

$$
Y_i = \mathbb{1}[success_{i,scheduled}]
      - \mathbb{1}[success_{i,baseline}],
$$

and the frozen query-cost adjustment is

$$
\Delta_{adjusted}=\frac{1}{N}\sum_i Y_i-0.025.
$$

The nominal row would pass both efficacy criteria if its prefixes were valid.
It cannot be promoted to a causal claim because method and baseline had already
diverged before the scheduled query-4 intervention.

## Integrity failure

Only **34/100** pairs passed the frozen common-prefix requirement, below the
required 95/100. The failure is shard-level:

| Init states | Pairs | Strict prefixes | Baseline SR | Scheduled SR | Nominal delta |
|---|---:|---:|---:|---:|---:|
| 0-7 | 16 | 0 | 43.8% | 62.5% | +18.8 pp |
| 8-15 | 16 | 0 | 37.5% | 62.5% | +25.0 pp |
| 16-24 | 18 | 18 | 27.8% | 44.4% | +16.7 pp |
| 25-32 | 16 | 0 | 25.0% | 62.5% | +37.5 pp |
| 33-40 | 16 | 16 | 56.2% | 68.8% | +12.5 pp |
| 41-49 | 18 | 0 | 22.2% | 27.8% | +5.6 pp |

At query 0, all pairs have the same simulator state. In four shards, however,
separately loaded model processes already produce small candidate value/action
differences. Those differences change selected candidates in some episodes and
amplify through closed-loop dynamics by query 4. The two strict shards are
bit-identical for state, candidate values, candidate actions and selected
indices through query 4.

Therefore a clean-GPU memory preflight is not sufficient to guarantee
reproducible Cosmos inference across processes. The data identify the boundary
of the problem but do not establish whether the remaining source is a CUDA
kernel, process/runtime state, or another nondeterministic operation.

## Robustness of the descriptive signal

The positive nominal effect is not concentrated in one convenient slice:

- all six init-state shards have a positive point estimate;
- replicate position 1 changes 15/50 to 29/50 success: +28 pp, 15/1
  rescue/harm;
- replicate position 2 changes 20/50 to 25/50 success: +10 pp, 10/5
  rescue/harm;
- 20 init states have positive net effect, 26 have zero effect and four have
  negative effect;
- the strict subset is positive (+14.7 pp), as is the non-strict subset
  (+21.2 pp).

This agreement strengthens the hypothesis that query-4 feedback helps task 0,
but it does not repair the broken paired counterfactual.

## Failure transitions

Among the 25 nominal rescues:

| Baseline failure to scheduled outcome | Count |
|---|---:|
| `timeout_no_goal -> success` | 16 |
| `target_drop_candidate -> success` | 5 |
| `wrong_object_interaction_candidate -> success` | 3 |
| `kinematic_deadlock_candidate -> success` | 1 |

The six harms are three new target drops, two timeouts and one wrong-object
interaction. As in the exact-state holdout, the largest gain is improved task
progress, not only prevention of physical drops.

## Gates and next action

| Frozen gate | Result | Reason |
|---|---|---|
| Integrity | **FAIL** | 34 strict prefixes; minimum 95 |
| Practical | **FAIL by protocol** | efficacy cannot be claimed after integrity failure |
| Confirmatory | **FAIL** | integrity failed; strict CI touches zero and strict McNemar p=0.1797 |

The prior 60-pair exact-state holdout remains the valid causal result
(+21.7 pp, p=0.00443). This replication adds strong distribution-level evidence
that the effect survives reset-to-terminal execution, while exposing a runtime
reproducibility problem in separate-process pairing.

The next P0 experiment should either execute a shared pre-query-4 prefix and
branch in one process, or cache and replay the exact candidate/actions through
query 4 before comparing controllers. A smaller diagnostic should first test
repeat inference at query 0 under deterministic CUDA settings. No controller
coefficient or query index should be retuned from this failed-integrity run.

## Artifacts

Machine-readable outputs are in
[`campaigns/object_q4_scheduled_controller_clean_replication_20260901/analysis/object_q4_scheduled_controller/`](campaigns/object_q4_scheduled_controller_clean_replication_20260901/analysis/object_q4_scheduled_controller/).
The main files are `summary.json`, `paired_outcomes.csv`,
`prefix_integrity.csv`, `failure_transitions.csv` and `init_state_summary.csv`.

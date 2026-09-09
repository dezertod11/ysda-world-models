# Object query-4 real-observation re-query: confirmatory holdout

## Decision

The frozen hypothesis **passed** its integrity, practical and confirmatory
gates. On unseen LIBERO-PRO Object task-0 initial states, replacing the second
half of the query-4 H16 chunk after observing the real simulator state improved
terminal success by **21.7 percentage points**.

This is confirmatory evidence for a narrow task/query feedback schedule. It is
not evidence that the same schedule transfers to every Object task, and it is
not a validation of a general uncertainty router.

Frozen protocol:
[`OBJECT_Q4_REQUERY_HOLDOUT_PROTOCOL_20260901.md`](OBJECT_Q4_REQUERY_HOLDOUT_PROTOCOL_20260901.md).
Freeze manifest:
[`OBJECT_Q4_REQUERY_HOLDOUT_FREEZE_MANIFEST_20260901.json`](OBJECT_Q4_REQUERY_HOLDOUT_FREEZE_MANIFEST_20260901.json).

## Design

- Suite: `libero_object_object`.
- Task 0: `pick the alphabet soup and place it in the basket`.
- Frozen decision point: query 4, executed step 64.
- Holdout: 15 init states unseen by the development query-4 screen, with four
  rollout seeds per init, giving 60 exact-state pairs.
- Shared pre-branch candidate pool: four stochastic Cosmos candidates selected
  by `max(value)`.

The paired branches were:

| Branch | Actions after the frozen state |
|---|---|
| `commit` | Execute the selected H16 chunk |
| `requery` | Execute H8, observe the real state, query Cosmos again, execute the new max-value H8 |

Both branches were then continued to the terminal LIBERO outcome.

## Integrity

| Check | Result |
|---|---:|
| Collected exact-state pairs | `60/60` |
| Independent init-state groups | `15/15` |
| Development init-state overlap | none |
| Missing or unexpected init states | none |
| Duplicate analysis states | `0` |
| Re-query actually performed | `60/60` |
| Maximum replay-state error | `3.00e-13` |
| Strict threshold | `1e-9` |
| Integrity gate | **PASS** |

All four GPU shards completed without traceback, OOM or missing terminal
branches.

## Primary result

For pair $i$, the frozen endpoint was

$$
Y_i = \mathbb{1}[\mathrm{success}_{i,\,requery}]
      - \mathbb{1}[\mathrm{success}_{i,\,commit}].
$$

| Endpoint | Commit H16 | H8 + real-observation re-query + H8 | Difference |
|---|---:|---:|---:|
| Terminal success | `23/60` (38.3%) | `36/60` (60.0%) | **+21.7 pp** |
| Rescue / harm | - | `16 / 3` | net `+13` |
| Both success / both fail | - | `20 / 21` | - |

The init-cluster bootstrap 95% confidence interval is **[+5.0, +40.0] pp**.
The exact two-sided McNemar test gives **p=0.00443**. With the frozen extra-query
cost $c_{query}=0.025$,

$$
\Delta_{adjusted}=0.2167-0.025=\mathbf{0.1917}.
$$

Therefore:

| Frozen gate | Criterion | Result |
|---|---|---:|
| Practical | raw gain $>0$ and adjusted gain $>0$ | **PASS** |
| Confirmatory | bootstrap lower bound $>0$ and McNemar $p<0.05$ | **PASS** |

## Replication of the development signal

The effect size reproduced almost exactly despite a large baseline difficulty
shift:

| Split | States | Commit SR | Re-query SR | Delta | Rescue / harm |
|---|---:|---:|---:|---:|---:|
| Development query-4 screen | 18 | 72.2% | 94.4% | +22.2 pp | 4 / 0 |
| Frozen unseen-init holdout | 60 | 38.3% | 60.0% | +21.7 pp | 16 / 3 |
| Descriptive pooled result | 78 | 46.2% | 67.9% | +21.8 pp | 20 / 3 |

Only the 60-state holdout is used for the confirmatory claim. The pooled row is
descriptive.

## Where the gain occurs

Seven init states had positive net effect, six had zero net effect and two had
negative net effect. Each of the four replicate positions remained positive
when aggregated across the 15 init states: `+13.3`, `+20.0`, `+33.3` and
`+20.0` pp. The result is therefore not caused by one replicate position.

The privileged phase label is diagnostic only:

| Phase at query 4 | States | Commit SR | Re-query SR | Delta | Rescue / harm |
|---|---:|---:|---:|---:|---:|
| Approach | 41 | 14.6% | 41.5% | +26.8 pp | 14 / 3 |
| Grasp | 1 | 0.0% | 100.0% | +100.0 pp | 1 / 0 |
| Transport | 17 | 94.1% | 100.0% | +5.9 pp | 1 / 0 |
| Release | 1 | 100.0% | 100.0% | 0.0 pp | 0 / 0 |

Most benefit comes from slow trajectories that are still approaching the
object at step 64. This does not make the simulator phase label a deployable
trigger; the earlier global phase-router transfer experiment already failed.

## Failure mechanism

Terminal transitions among the 19 discordant pairs were:

| Transition | Count |
|---|---:|
| `timeout_no_goal -> success` | 14 |
| `target_drop_candidate -> success` | 2 |
| `success -> timeout_no_goal` | 2 |
| `success -> target_drop_candidate` | 1 |

The re-query mostly rescues insufficient progress rather than only filtering
physical drops. It is not harmless: three baseline successes became failures,
which is why transfer must remain paired and task-specific.

## Frozen uncertainty rankers

The three metric directions were frozen on development data before opening the
holdout. They did not recover most of the causal opportunity:

| Frozen selector | Budget | Selected rescue / harm | Raw delta | Cost-adjusted delta |
|---|---:|---:|---:|---:|
| High latent future-proprio copy std | 5% | 1 / 0 | +1.67 pp | +1.54 pp |
| High latent future-proprio copy std | 10% | 1 / 0 | +1.67 pp | +1.42 pp |
| Low action-chunk consensus | 10% | 0 / 0 | 0.00 pp | -0.25 pp |
| Low action std | 10% | 0 / 0 | 0.00 pp | -0.25 pp |

The latent metric found only `1/16` rescues at every tested budget. Thus the
confirmed result is currently **feedback timing at a known task/query cell**,
not uncertainty-aware selective planning.

## Consequences for the roadmap

1. Promote `Object task0, query4: H8 -> real observation -> H8` to a frozen
   end-to-end paired deployment test from episode reset.
2. Keep the original H16/max-value policy as the paired baseline and report
   both SR and policy-query overhead.
3. Test transfer to untouched Object tasks under a separate preregistration;
   do not tune query indices on their holdout outcomes.
4. For selection within task 0, replace generic latent/action uncertainty with
   a deployable object-progress/contact representation. The current scalar
   rankers have insufficient rescue recall.
5. Preserve always-requery-at-query4 as the positive causal control for future
   object/contact VoF models.

## Artifacts

- Machine report:
  [`campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/RESULTS.md`](campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/RESULTS.md).
- Primary endpoint:
  [`primary_endpoint.csv`](campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/primary_endpoint.csv).
- Init-state breakdown:
  [`init_state_summary.csv`](campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/init_state_summary.csv).
- Frozen selector budgets:
  [`frozen_ranker_budgets.csv`](campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/frozen_ranker_budgets.csv).
- Machine-readable summary:
  [`summary.json`](campaigns/object_q4_requery_holdout_20260901/analysis/object_q4_holdout/summary.json).

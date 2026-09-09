# Initial real-observation re-query: holdout result

## Decision

The fixed `query0: H8, later: H16` schedule is **closed**. The frozen efficacy
gate failed, and the nominal effect was strongly negative. The run also failed
one strict integrity condition, so it is reported as a failed/contaminated
holdout rather than confirmatory evidence.

Protocol:
[`INITIAL_REQUERY_HOLDOUT_PROTOCOL_20260831.md`](INITIAL_REQUERY_HOLDOUT_PROTOCOL_20260831.md).
Frozen manifest:
[`INITIAL_REQUERY_HOLDOUT_FREEZE_MANIFEST_20260831.json`](INITIAL_REQUERY_HOLDOUT_FREEZE_MANIFEST_20260831.json).

## Design

Sixty LIBERO-PRO Environment states from tasks 8/9 and init states 20-49 were
paired by exact `(suite, task, init, rollout_seed)`. Both policies sampled K=4
candidates and selected `argmax(value)`:

| Method | Query 0 | Later queries |
|---|---:|---:|
| `maxV-H16` | H16 | H16 |
| `maxV-Q0-H8-then-H16` | H8, then real observation | H16 |

## Integrity

| Check | Result |
|---|---:|
| Episodes per method | 60 |
| Identical paired state sets | PASS |
| Tasks/init/split | PASS |
| Baseline H16 and intervention H8/H16 schedule | PASS |
| Max-value selector fidelity | PASS |
| Exactly one scheduled re-query | PASS |
| Query-0 max-value candidate index match | **57/60, FAIL** |
| Max query-0 candidate-value difference | `1.302e-3` |

The strategy branch is evaluated only after candidates are generated, but GPU
inference was not bitwise deterministic across the two separately launched
processes. Three near-tied query-0 value arrays changed argmax. Future causal
horizon tests must branch both policies from one generated candidate pool in a
single process.

## Nominal result

| Method | Success | SR | Timeout | Mean queries | Mean final t | Drop | Wrong object |
|---|---:|---:|---:|---:|---:|---:|---:|
| `maxV-H16` | 35/60 | 58.3% | 41.7% | 12.55 | 192.4 | 3.3% | 35.0% |
| `Q0-H8 -> H16` | 23/60 | 38.3% | 61.7% | 14.95 | 227.3 | 0.0% | 35.0% |

Nominal paired delta is **-20.0 percentage points**, task-stratified 95% CI
`[-31.7; -6.7]`, with 4 rescues and 16 harms (exact McNemar `p=0.0118`). This
is descriptive because the frozen integrity gate failed.

| Task | Baseline SR | Intervention SR | Delta | Rescue / harm |
|---:|---:|---:|---:|---:|
| 8 | 26.7% | 30.0% | +3.3 pp | 2 / 1 |
| 9 | 90.0% | 46.7% | -43.3 pp | 2 / 15 |

Task 9 explains the regression: timeout rose from 10.0% to 53.3%. Executing
the original actions 8-15 was often better than replacing them with a new
stochastic chunk. More recent observation is therefore not monotonically
valuable.

## Integrity sensitivity

After removing all three query-0 argmax mismatches, 57 fully selector-matched
pairs remain:

| Subset | Delta SR | 95% stratified CI | Rescue / harm | McNemar p |
|---|---:|---:|---:|---:|
| Query-0 argmax matched | -19.3 pp | `[-31.6; -7.0]` | 4 / 15 | 0.0192 |

Only one mismatched pair was discordant. Thus contamination invalidates the
formal gate but does not explain the negative direction.

## Conclusion

1. The exploratory query-0 rescues from the previous 78-state experiment did
   not transfer as a fixed policy.
2. Feedback timing is state- and task-dependent; a phase or clock rule is not
   enough.
3. The next method must estimate signed state-level value of feedback and
   preserve the current chunk when predicted feedback value is negative.
4. Future causal tests use exact-state single-process branching to eliminate
   candidate-generation nondeterminism.

Machine-readable output:
[`campaigns/initial_requery_holdout_20260831/analysis/initial_requery_holdout/RESULTS.md`](campaigns/initial_requery_holdout_20260831/analysis/initial_requery_holdout/RESULTS.md).


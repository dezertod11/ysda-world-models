# Phase-aware terminal Value of Feedback: results

## Decision

The privileged `grasp/transport -> H8 re-query` phase oracle **failed** its
frozen efficacy gate. Integrity passed, so this is a scientific negative
result rather than a broken run. The phase rule is closed and an observable
phase detector must not be trained for it.

At the same time, the causal branches exposed a new exploratory mechanism:
three of four re-query rescues occurred at `query_idx=0` in the `approach`
phase. This motivates a separate, independently evaluated controller that
uses H8 only for the first chunk and H16 afterwards.

## Protocol and integrity

Every snapshot compared two branches restored from the same MuJoCo state:

$$
\tau_{16}=a^{\max V}_{0:16},
\qquad
\tau_{8+8}=a^{\max V}_{0:8}\to o_{\mathrm{real},8}
\to a^{\max V}_{0:8}.
$$

Both branches then used the same K=4 max-value policy and coupled continuation
seed schedule until success or 280 steps. Only the selected commit candidate
and feedback branch were continued to terminal; all four candidates still
received the matched H16 local evaluation.

Coverage was selected using phase/contact fields only, before terminal and
dense outcomes were opened. All-approach task 6/7 and task-8 init15-19 runs
are retained under
`phase_vof_terminal_transfer_20260831/feasibility_screening_task6_task7/` and
excluded from the mechanism test. Full amendments and hashes are recorded in
the V1-V4 freeze manifests.

| Integrity item | Result |
|---|---:|
| Final states | 78 |
| Strict replay states, error <= 1e-9 | 67 |
| Strict task counts 5 / 8 / 9 | 26 / 13 / 28 |
| Triggered strict states / task-init groups | 38 / 12 |
| K=4 candidate sets | all |
| Terminal commit/feedback pairs | all |
| Exactly one candidate terminally continued | all |
| Integrity gate | **PASS** |

## Primary results

The frozen router intervenes on `grasp` and `transport` only:

$$
\pi_{phase}(s)=
\begin{cases}
\tau_{8+8}(s), & p(s)\in\{\mathrm{grasp},\mathrm{transport}\},\\
\tau_{16}(s), & p(s)=\mathrm{approach}.
\end{cases}
$$

| Method | Success | SR | Intervention | Utility at c=0.025 |
|---|---:|---:|---:|---:|
| commit H16 | 58/67 | 86.6% | 0.0% | 0.866 |
| always H8 re-query | 61/67 | 91.0% | 100.0% | 0.885 |
| frozen phase oracle | 58/67 | 86.6% | 56.7% | 0.851 |

Paired terminal contrasts versus commit:

| Method | Delta SR | Grouped 95% CI | Rescues / harms | Exact p |
|---|---:|---:|---:|---:|
| always H8 re-query | +4.5 pp | [-2.6; +12.3] pp | 4 / 1 | 0.375 |
| frozen phase oracle | 0.0 pp | [-3.7; +3.6] pp | 1 / 1 | 1.000 |

No official LIBERO-Safety violation occurred. The phase oracle had the same
4.5% target-drop and wrong-object rates as commit. It failed 6/9 scientific
checks: too few rescues, no positive terminal delta, negative triggered dense
mean, a CI crossing zero, and lower compute-adjusted utility.

## Why the rule failed

| Phase | States | Commit SR | Feedback SR | Rescues / harms | Mean dense VoF |
|---|---:|---:|---:|---:|---:|
| approach | 29 | 72.4% | 82.8% | 3 / 0 | -0.0139 |
| grasp | 17 | 94.1% | 94.1% | 1 / 1 | -0.0397 |
| transport | 21 | 100% | 100% | 0 / 0 | +0.0215 |

The original development correlation did not survive terminal transfer:

1. `grasp` contained one rescue and one harm, so its net terminal effect was
   zero.
2. `transport` had positive local geometry but a terminal ceiling; it could
   not improve success.
3. The only net terminal gain was before interaction, at the initial query.
4. Dense H16 progress and terminal success can disagree. One grasp rescue had
   negative dense VoF, while transport had positive dense VoF without any
   terminal rescue.

This is direct evidence that a geometric phase label is too coarse for a
feedback controller and that local dense progress is not a sufficient terminal
target.

## Exploratory initial-feedback signal

All three approach rescues were at `query_idx=0`; two prevented target drops
and one prevented a wrong-object interaction. A post-hoc approach-only route
would have:

| Quantity | Value |
|---|---:|
| Success | 61/67 = 91.0% |
| Delta SR | +4.5 pp |
| Grouped 95% CI | [0.0; +10.7] pp |
| Rescues / harms | 3 / 0 |
| Intervention rate | 29/67 = 43.3% |
| Utility at c=0.025 | 0.900 |
| Exact McNemar p | 0.25 |

This analysis is **hypothesis-generating**, not a valid positive result. The
new controller is therefore frozen before an independent run:

$$
\pi_{Q0}(q)=
\begin{cases}
\text{maxV-H8}, & q=0,\\
\text{maxV-H16}, & q>0.
\end{cases}
$$

It adds exactly one early observation opportunity per episode and never
changes candidate selection. The independent holdout must determine whether
the signal transfers beyond these five discordant snapshots.

## Artifacts

- Frozen protocol: `PHASE_VOF_TERMINAL_TRANSFER_PROTOCOL_20260831.md`
- Final freeze: `PHASE_VOF_TERMINAL_TRANSFER_FREEZE_MANIFEST_V4_20260831.json`
- Machine-readable summary:
  `campaigns/phase_vof_terminal_transfer_20260831__dense_relabel/analysis/phase_vof_terminal_transfer/summary.json`
- Full report and CSV tables: the same analysis directory
- Figure: `phase_vof_terminal_transfer.png`


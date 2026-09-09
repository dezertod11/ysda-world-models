# Factor-routed real-observation re-query: transfer results

## Decision

The frozen factor router is **closed**. On 90 new paired LIBERO-PRO states it
reduced success from `53/90 = 58.9%` to `47/90 = 52.2%`:

$$
\Delta SR=-6.7\ \text{percentage points},
\qquad 95\%\ \mathrm{CI}=[-13.3;0.0]\ \text{pp}.
$$

There were two rescues and eight harms (`McNemar p=0.109`). The result is not
a two-sided significance claim, but it fails every preregistered efficacy gate
and points in the wrong direction. No task-specific exception is fitted on
this transfer split.

## Frozen experiment

The preceding 40-state pilot suggested, post hoc, that adaptive feedback might
help Position and Environment while harming Object. Before reading the new
outcomes, the following router was frozen:

$$
\pi_{route}(f)=
\begin{cases}
\pi_{maxV,H16}, & f=\mathrm{Object},\\
\pi_{maxV,gripper\text{-}H8/H16},
& f\in\{\mathrm{Position},\mathrm{Environment}\}.
\end{cases}
$$

The adaptive policy always executes the same `argmax(value)` candidate as the
baseline. It executes only eight actions when the selected H16 chunk contains
both an open and a close gripper command beyond the frozen threshold
$\epsilon_g=0.25$; otherwise it executes all 16 actions. Thus this is a causal
test of feedback timing, not candidate reranking.

The transfer split used unseen task groups: Object tasks 1-3, Position-y0.3
tasks 1-3, and Environment tasks 1, 3, 4, each with init states 40-49. Both
direct policies were run on every state with matched rollout seeds, four
stochastic candidates, five action denoising steps and a 280-step limit:
`90 pairs = 180 rollout`.

## Primary results

| Policy | Success | Delta vs H16 | Rescues / harms | Query multiplier |
|---|---:|---:|---:|---:|
| `maxV-H16` | 53/90 = 58.9% | - | - | 1.000x |
| direct `maxV-gripper-H8/H16` | 48/90 = 53.3% | -5.6 pp | 3 / 8 | 1.264x |
| frozen factor router | 47/90 = 52.2% | -6.7 pp | 2 / 8 | 1.200x |

The direct adaptive contrast has grouped bootstrap CI `[-12.2; +1.1]` pp and
exact McNemar `p=0.227`. The router discards the one Object rescue by design,
which is why it is one success below direct adaptive.

At the preregistered compute cost $c=0.025$,

$$
J_c=SR-c(m-1),
$$

the utilities are `0.5889` for H16, `0.5267` for direct adaptive and `0.5172`
for the router. The extra real observations therefore do not pay for
themselves on this split.

## Factor and task results

| Factor | H16 | Direct adaptive | Routed | Routed delta |
|---|---:|---:|---:|---:|
| Object | 28/30 = 93.3% | 29/30 = 96.7% | 28/30 = 93.3% | 0.0 pp |
| Position | 3/30 = 10.0% | 1/30 = 3.3% | 1/30 = 3.3% | -6.7 pp |
| Environment | 22/30 = 73.3% | 18/30 = 60.0% | 18/30 = 60.0% | -13.3 pp |

The factor interaction from the pilot did not transfer. At task level:

| Factor / task | H16 | Adaptive | Interpretation |
|---|---:|---:|---|
| Object 1 / 2 / 3 | 90 / 100 / 90% | 90 / 100 / 100% | sentinel changed sign; one adaptive rescue |
| Position 1 | 30% | 10% | one rescue but three harms |
| Position 2 / 3 | 0 / 0% | 0 / 0% | feedback cannot repair the all-fail proposal/execution regime |
| Environment 1 | 100% | 70% | re-query harms an otherwise easy task |
| Environment 3 | 90% | 80% | one rescue and two harms |
| Environment 4 | 30% | 30% | no gain on the hard task |

The routed rescues are Environment task 3 / init 41 and Position task 1 /
init 46. Harms comprise five Environment states and three Position states.
Three Environment-task-1 harms triggered H8 on 80-91% of queries, but a
Position harm occurred at only 10.5%; trigger frequency alone is therefore
not a sufficient guard.

## Failure modes

| Endpoint | H16 | Router |
|---|---:|---:|
| Timeout / terminal fail | 41.1% | 47.8% |
| Target-drop candidate | 1.1% | 10.0% |
| Wrong-object interaction | 11.1% | 17.8% |
| Official safety violation | 0% | 0% |

The gripper sign change is a normal manipulation-phase event, not an
uncertainty estimate. Replanning exactly there can destroy temporal commitment:
the next stochastic `max(value)` chunk is conditioned on a fresh observation,
but it is not constrained to continue the old contact plan. More feedback can
therefore inject a discontinuity during grasp/transport/release. Conversely,
on Position tasks 2-3 the proposal/execution regime is all-fail, so observing
more often does not create a viable action.

## Why the pilot did not transfer

1. The pilot router was selected after seeing only 40 outcomes; its apparent
   `+10 pp` was explicitly exploratory.
2. OOD factor is too coarse. Position task 0 benefited in the pilot, while
   tasks 1-3 do not; Environment tasks 0/2 and 1/3/4 have very different base
   difficulty.
3. The intervention changes behavior at a manipulation primitive boundary,
   where temporal commitment can matter more than a fresh observation.
4. A factor label says how the benchmark was perturbed, not whether the
   current state has positive counterfactual Value of Feedback.

## Integrity and reproducibility

- 90/90 paired state keys are complete and identical between methods.
- Adaptive selected the max-value candidate on 100% of queries.
- Trigger diagnostics and executed H8/H16 horizons agree on 100% of queries.
- All data use the `generalization` split and frozen init states 40-49.
- No official safety violation occurred.
- The campaign directory is
  `campaigns/factor_routed_requery_transfer_20260830/`.

The frozen analyzer hash is preserved in
`FACTOR_ROUTED_REQUERY_TRANSFER_FREEZE_MANIFEST_20260830.json`. After outcomes
were collected, a serialization-only patch converted NumPy scalars while
writing `summary.json`; it did not change calculations, tables, gates or
plots. The patched analyzer hash is
`96694e4dc2de26e51fa3c564b2d5c3f1c1581c4c834ce54cd10d58087b490a4a`.
Eight protocol/analyzer tests pass locally and on the server.

## Next research step

Close both the coarse factor router and the raw gripper-transition trigger.
The next controller must estimate **state-level counterfactual Value of
Feedback**, and it must distinguish two actions:

1. `commit`: continue the current chunk through a task-critical contact phase;
2. `observe/recover`: shorten the horizon only when grounded evidence predicts
   that a fresh observation changes the outcome positively.

The first screen should use exact-state branches to label

$$
\operatorname{VoF}(s)=G_{H8\rightarrow requery}(s)-G_{H16}(s)
-c_{query},
$$

with phase, gripper transition, real proprio/contact state and semantic
predicted consequence as inputs. A new closed-loop test is allowed only if a
low-dimensional grouped holdout predicts the *sign* of VoF. Further scalar
uncertainty penalties or factor/task exception tables are not justified by
this result.

Detailed machine-readable results and figures:
`campaigns/factor_routed_requery_transfer_20260830/analysis/factor_routed_transfer/`.

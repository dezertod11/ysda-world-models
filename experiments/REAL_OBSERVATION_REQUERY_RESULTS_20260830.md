# Real-observation re-query: results

## Experiment

The frozen holdout compared three policies on 40 hard LIBERO-PRO states:

1. `maxV-H16`: select `argmax(value)` and execute 16 actions;
2. `maxV-H8`: keep the same selector but query after eight actions;
3. `maxV-gripper-H8/H16`: execute eight actions only when the selected chunk
   predicts an open/close gripper transition, otherwise execute 16.

The methods used identical `task/init/rollout` seeds. The adaptive method kept
the max-value candidate at every query, so only feedback timing changed.

## Primary result

| Method | Success | Query multiplier | Rescues / harms vs H16 |
|---|---:|---:|---:|
| `maxV-H16` | 8/40 = 20.0% | 1.00x | - |
| `maxV-H8` | 8/40 = 20.0% | 1.95x | 3 / 3 |
| `maxV-gripper-H8/H16` | 9/40 = 22.5% | 1.44x | 6 / 5 |

The adaptive pooled difference was +2.5 percentage points with grouped
bootstrap interval `[-12.5; +17.5]` and exact McNemar `p=1.0`. Fixed H8 did
not improve success despite almost doubling policy-query cost.

The adaptive controller passed five of six preregistered checks but failed the
factor-regression check. Therefore the universal controller is a **no-go**.

## Factor interaction

| Factor | H16 | Fixed H8 | Adaptive | Adaptive delta |
|---|---:|---:|---:|---:|
| Object | 70% | 70% | 40% | -30 pp |
| Position | 10% | 0% | 40% | +30 pp |
| Environment | 0% | 5% | 5% | +5 pp |

The intervention has opposite effects across OOD mechanisms. Position had
three adaptive rescues and zero harms; Environment had one rescue and zero
harms. Object had two rescues but five harms. This explains why a pooled
controller looks neutral even though the factor-level mechanism is strong.

## Compute-adjusted result

At query cost $c=0.025$,

$$
J_c=\operatorname{Success}-c(m-1),
$$

the mean utilities were `0.2000` for H16, `0.1763` for fixed H8, and `0.2141`
for adaptive H8/H16. Adaptive feedback is more compute-efficient than fixed
H8, but its Object regression prevents deployment as a universal policy.

## Exploratory factor router

A post-hoc router that keeps H16 on Object and enables adaptive feedback only
on Position/Environment would have produced:

- 12/40 = 30.0% success versus 8/40 = 20.0%;
- four rescues and zero harms;
- grouped bootstrap delta interval `[+2.5; +20.0]` pp;
- query multiplier 1.35x;
- $J_{0.025}=0.2913$.

These numbers are **hypothesis-generating only**, because the router was chosen
after inspecting factor outcomes. They motivate a new frozen transfer test on
unseen task/init groups; they are not a confirmatory result.

## Decision

1. Close unconditional H8: it adds compute without pooled success gain.
2. Close the universal gripper-transition controller: it violates the Object
   sentinel gate.
3. Test the frozen factor router on new tasks: H16 for Object, adaptive H8/H16
   for Position and Environment.
4. Do not tune the gripper threshold or intervention window on init 40-49.
5. If factor routing transfers, investigate why Object requires temporal
   commitment while Position/Environment benefit from fresh observations.

Detailed tables and figures are in
`campaigns/real_observation_requery_20260830/analysis/real_observation_requery/`.


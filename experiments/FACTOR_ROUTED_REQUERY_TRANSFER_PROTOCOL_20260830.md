# Factor-routed re-query transfer: confirmatory protocol

## Status

Preregistered before collecting outcomes for the task/init groups below.

## Hypothesis

The first real-observation holdout showed an interaction between OOD factor
and feedback timing: gripper-boundary H8/H16 helped Position and Environment
but harmed Object. This experiment tests whether that interaction transfers to
new tasks.

The frozen routed policy is

$$
\pi_{route}(f)=
\begin{cases}
\pi_{maxV,H16}, & f=\text{Object},\\
\pi_{maxV,gripper\text{-}H8/H16}, &
f\in\{\text{Position},\text{Environment}\}.
\end{cases}
$$

The adaptive branch uses the unchanged threshold $\epsilon_g=0.25$ and never
switches away from the max-value action candidate.

## Independent transfer split

The preceding holdout used Object/Position task 0 and Environment tasks 0/2.
The transfer split uses different task/init groups:

| Factor | Suite / variant | Tasks | Init states | States |
|---|---|---:|---:|---:|
| Object | `libero_object_object` | 1, 2, 3 | 40-49 | 30 |
| Position | `libero_object_temp_y0.3` | 1, 2, 3 | 40-49 | 30 |
| Environment | `libero_object_env` | 1, 3, 4 | 40-49 | 30 |
| **Total** | | | | **90** |

Both H16 and adaptive policies are collected for all factors. The direct
Object adaptive result is a sentinel; the routed policy uses H16 there by
definition. Every pair shares rollout seed, four stochastic candidates,
parallel prediction, five action denoising steps, and a 280-step limit.

## Primary comparison

For state $s$, define routed outcome

$$
Y_{route}(s)=
\begin{cases}
Y_{H16}(s), & f(s)=\text{Object},\\
Y_{adaptive}(s), & f(s)\in\{\text{Position},\text{Environment}\}.
\end{cases}
$$

Primary endpoint is paired terminal-success difference
$\mathbb E[Y_{route}-Y_{H16}]$. Secondary endpoints are factor SR, direct
adaptive-vs-H16 effects, query multiplier, timeout, drop, wrong-object and
safety events.

Compute-adjusted utility remains

$$
J_c=\operatorname{Success}-c(m-1),
\qquad c\in\{0.01,0.025,0.05\}.
$$

Grouped bootstrap resamples task/init states within factor. We report exact
McNemar tests, rescues and harms. No query from one episode is treated as an
independent sample.

## Frozen decision gate

Factor routing advances only if all conditions hold:

1. at least five routed rescues and strictly more rescues than harms;
2. pooled routed SR improves by at least five percentage points;
3. Position and Environment each have non-negative paired SR delta;
4. routed mean query multiplier is at most 1.50x;
5. routed $J_{0.025}$ exceeds H16;
6. adaptive candidate fidelity is 100% max-value and all 90 pairs are complete.

The direct Object adaptive sentinel is reported but is not part of the routed
action. Failure closes this factor router; task-specific exceptions will not
be fitted on this transfer split.


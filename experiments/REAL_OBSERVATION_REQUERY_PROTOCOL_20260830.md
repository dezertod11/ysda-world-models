# Real-observation re-query: confirmatory protocol

## Status

Preregistered before collecting or inspecting outcomes for `init_state_id=40-49`.

## Question

The candidate-ranking experiments established two different failure modes:

1. on LIBERO-PRO Object, successful `K=8` proposals often exist but scalar and
   latent rankers do not transfer to unseen initial states;
2. on hard Position and Environment cells, most candidate pools are all-fail,
   so re-ranking the same state cannot recover the episode.

This experiment tests a different intervention: execute a shorter prefix,
observe the **real** simulator state, and query Cosmos Policy again. Candidate
selection remains `argmax(value)` in every method.

## Frozen methods

Let candidate $i$ have predicted value $v_i$ and action chunk
$a_i=(a_{i,0},\ldots,a_{i,15})$. Every query selects

$$
i^*=\arg\max_i v_i.
$$

The methods differ only in execution horizon.

### `maxV-H16`

$$
H_q=16.
$$

This is the deployment baseline.

### `maxV-H8`

$$
H_q=8.
$$

This is the positive causal control for more frequent real-observation
feedback. It is expected to cost close to twice as many policy queries.

### `maxV-gripper-H8/H16`

For the selected chunk, let $g_j=a_{i^*,j,6}$ be its gripper command and let
$\epsilon_g=0.25$. A predicted manipulation boundary is

$$
C_q=\mathbb 1\!\left[
\min_{0\leq j<16}g_j<-\epsilon_g
\;\land\;
\max_{0\leq j<16}g_j>\epsilon_g
\right].
$$

The controller uses

$$
H_q=\begin{cases}
8, & C_q=1,\\
16, & C_q=0.
\end{cases}
$$

Thus a fresh observation is requested around a predicted grasp or release,
while navigation and transport chunks remain open-loop for 16 actions. The
trigger does not use outcome labels, future observations, simulator geometry,
or uncertainty-based candidate switching.

## Frozen benchmark

All methods use identical rollout seeds, four stochastic candidates
(`uncertainty_seeds=0,1,2,3`), five action denoising steps, parallel prediction,
and at most 280 environment steps.

| Factor | Suite / variant | Task | Initial states | Paired states |
|---|---|---:|---:|---:|
| Object | `libero_object_object` | 0 | 40-49 | 10 |
| Position | `libero_object_temp_y0.3` | 0 | 40-49 | 10 |
| Environment | `libero_object_env` | 0, 2 | 40-49 | 20 |
| **Total** | | | | **40** |

The split was held aside in the preceding pairwise-ranker protocol. No result
from these initial states may be used to tune the trigger or choose a method.

## Outcomes and compute

Primary outcome is terminal task success. For episode $e$, query cost is

$$
m_e=\frac{Q_e}{\lceil T_e/16\rceil},
$$

where $Q_e$ is the actual number of policy queries and $T_e$ is the number of
executed environment steps. We report success together with $Q_e$, $m_e$,
time-to-success, timeout, drop, wrong-object interaction, and official safety
signals.

Compute-adjusted utility is reported without selecting a favourable cost:

$$
J_c=\operatorname{Success}-c\,(m_e-1),
\qquad c\in\{0.01,0.025,0.05\}.
$$

## Statistical analysis

1. Pair episodes by factor, suite, task, initial state, and rollout seed.
2. Report pooled and factor-level SR with grouped bootstrap confidence
   intervals over independent task/init states.
3. For each method versus `maxV-H16`, report rescues, harms, exact McNemar
   $p$-value, paired SR difference, query multiplier, and $J_c$.
4. Report the trigger rate and verify that the adaptive method never changes
   the max-value candidate.
5. Treat videos only as mechanism evidence after the numerical analysis.

## Decision gates

`maxV-gripper-H8/H16` advances only if all primary conditions hold:

1. at least two holdout rescues and strictly more rescues than harms;
2. pooled SR is no lower than `maxV-H16`;
3. no factor loses more than one successful state;
4. mean query multiplier is at least 20% lower than `maxV-H8`;
5. mean $J_{0.025}$ is greater than for `maxV-H16`.

`maxV-H8` is interpreted as a mechanism control rather than a deployable
winner. Its feedback hypothesis is supported only if it has more rescues than
harms and a positive pooled paired SR difference.

No threshold, factor-specific exception, or query window will be fitted after
examining this holdout. A failed gate closes this exact controller.


# Hard-cell grounded pairwise ranker protocol

Status: completed 30 August 2026. Development opportunity PASS; untouched
holdout gate FAIL. Results:
[`HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md`](HARD_CELL_PAIRWISE_RANKER_RESULTS_20260830.md).

## Motivation

Two controlled screens established that hard LIBERO-PRO Object and Position-y
states often contain a successful action in a saturated K8 proposal pool, but
neither Cosmos parallel value nor the same-pass autoregressive
`action -> future -> value` evaluator ranks it reliably. The next hypothesis is
that the useful signal is distributed across value, action geometry, ensemble
consistency and action-conditioned consequence features.

The experiment asks whether a low-capacity, within-state pairwise model can
learn that ordering without using privileged simulator state or any
post-execution error at decision time.

## Frozen benchmark

| Split | Init states | States per factor | Role |
|---|---:|---:|---|
| development | 10-24 | 15 | fit and grouped CV of ridge strength |
| calibration | 25-29 | 5 | freeze conservative switch multiplier |
| untouched holdout | 30-39 | 10 | final offline exact-state test |

Two factors are evaluated separately:

- Object: `libero_object_object`, task 0;
- Position: `libero_object_temp_y0.3`, task 0.

Every state is `query=0`, uses the same-pass dual evaluator and has `K=8`
stochastic actions. Each candidate executes 16 actions and is then continued
to terminal outcome by the unchanged parallel `max(value)`, K2, H16 policy.
The maximum episode length is 280 steps.

Init states 5-9 used in the AR pilot are excluded from all three splits.
Splits are grouped by complete `factor/task/init_state`; no candidate from one
group may occur in another split.

## Online feature vector

The frozen 20-dimensional feature vector contains only quantities available
before executing candidate $j$:

1. parallel value, autoregressive value and their difference;
2. first-action L1, action-chunk L1/L2 and distance to first/chunk consensus;
3. action latent copy mean/max and first-step copy disagreement;
4. parallel future-proprio and value latent copy mean/max;
5. autoregressive future-proprio and value latent copy mean/max;
6. L2 disagreement between parallel and autoregressive predicted future
   proprio.

No `prediction_error_*`, realized observation, terminal label, BDDL predicate
or privileged simulator pose is an input feature.

For every exact state, each feature is standardized only relative to the other
seven candidates:

$$
z_{ijm}=\frac{x_{ijm}-\operatorname{mean}_{k}x_{ikm}}
{\max(\operatorname{std}_{k}x_{ikm},10^{-8})}.
$$

## Pairwise objective

Candidate utility is the already frozen terminal utility:

$$
G_{ij}=2I_{success}+p_{ij}-I_{drop}-0.5I_{wrong}-I_{violation}.
$$

For each non-tied pair, let $w$ be the higher-utility candidate and $l$ the
lower-utility candidate. A factor-specific Bradley-Terry linear score is fit:

$$
S_f(i,j)=\beta_f^\top z_{ij},
$$

$$
\mathcal L_f(\beta)=
\sum_{(w,l)}\log\left(1+\exp[-\beta^\top(z_w-z_l)]\right)
+\frac{\alpha}{2}\lVert\beta\rVert_2^2.
$$

The ridge strength is selected from `0.1, 1, 10, 100` by leave-one-init-group
out development pairwise accuracy. Ties select the larger alpha. A
32-member grouped-bootstrap ensemble is then fit using the selected alpha.

## Conservative selector

Let $j_R$ maximize the ensemble-mean learned score and $j_V$ maximize parallel
Cosmos value. For bootstrap member $b$:

$$
D_b=S_b(j_R)-S_b(j_V),
\qquad
LCB_\kappa=\operatorname{mean}_bD_b-kappa\operatorname{std}_bD_b.
$$

The selector switches from $j_V$ to $j_R$ only if $LCB_\kappa>0$. For each
factor, $\kappa\in\{0,0.5,1,1.5\}$ is chosen on calibration by the frozen
lexicographic rule: maximize `(rescues - harms)`, then mean terminal-utility
delta, then minimize adverse-event delta, then minimize switches, then choose
the larger $\kappa$.

Both the unconditional ranker top-1 and conservative selector are reported;
the conservative selector is the primary deployable method.

## Sequential gates

Holdout collection is allowed only if development plus calibration contains:

- at least eight mixed terminal-outcome states combined;
- at least three mixed states in each factor;
- at least three states where `max(value)` fails but another K8 candidate
  succeeds.

The final holdout screen passes only if all conditions hold:

- conservative selector improves mixed-state top-1 by at least two states;
- rescues exceed harms;
- success delta is nonnegative in both factors;
- the selector introduces at most one additional adverse event.

Failure stops this linear feature family; thresholds or features are not tuned
on holdout. Passing allows a separately preregistered closed-loop test on new
tasks/init states.

## Factor routing

Environment is intentionally excluded: its current K8/K16 pools are all-fail,
so no selector can improve them. That factor remains assigned to early
re-query/recovery or a different proposal mechanism.

# P4: independent residual-dynamics ensemble and conformal OOD routing

Status: **frozen development protocol, written before P4 scores were computed**.

## Question

Previous Cosmos experiments measured stochastic variation inside repeated policy
samples and repeated latent copies. P4 asks a different question: does an ensemble
of independently initialized transition models identify state-action regions where
Cosmos' predicted future is unreliable, and does that signal transfer from standard
LIBERO to the Object, Environment, and Position families of LIBERO-PRO?

This is a development screen inspired by UNISafe (Seo, Nakamura, Bajcsy, CoRL 2025,
arXiv:2505.00779). UNISafe did not evaluate LIBERO. The current experiment is our
adaptation to a VLA world model and is not a reproduction of its benchmark result.

## Transition and target

For candidate action chunk $a_i=(a_{i,0},\ldots,a_{i,15})$, Cosmos supplies its
future prediction $(\hat o_{i,t+16},\hat p_{i,t+16})$. Exact MuJoCo snapshot replay
supplies the realized endpoint $(o_{i,t+16},p_{i,t+16})$. A frozen CLIP image encoder
$E$ is used for the agent and wrist views.

The input is

$$
x_i=\left[
E(o_t),E(w_t),E(\hat o_{i,t+16}),E(\hat w_{i,t+16}),
p_t,\hat p_{i,t+16},\operatorname{vec}(a_i),\hat v_i
\right].
$$

The supervised residual target is

$$
r_i=\left[
E(o_{i,t+16})-E(\hat o_{i,t+16}),
E(w_{i,t+16})-E(\hat w_{i,t+16}),
p_{i,t+16}-\hat p_{i,t+16}
\right].
$$

Thus the ensemble models uncertainty about **Cosmos prediction error conditioned on
the proposed action**, rather than merely detecting whether a generated image looks
unusual. Input visual features and visual residual targets are reduced by train-only
randomized PCA. All dimensions are standardized with train-only statistics.

## Independent Gaussian heads

Five MLP heads use independent initializations and trajectory-group bootstrap samples:

$$
q_k(r_i\mid x_i)=\mathcal N\!\left(\mu_k(x_i),
\operatorname{diag}(\sigma_k^2(x_i))\right),\qquad k=1,\ldots,5.
$$

Each head minimizes diagonal Gaussian negative log likelihood:

$$
\mathcal L_k=\frac{1}{2D}\sum_{d=1}^{D}
\left[\log\sigma_{k,d}^{2}+
\frac{(r_{i,d}-\mu_{k,d})^2}{\sigma_{k,d}^{2}}\right].
$$

The diagonal variance is aleatoric uncertainty. Variation of the means across
independently trained heads is empirical epistemic uncertainty. The primary score is
quadratic Jensen-Renyi divergence:

$$
U_{\mathrm{JRD}}(x_i)=
H_2\!\left(\frac{1}{K}\sum_{k=1}^{K}q_k\right)
-\frac{1}{K}\sum_{k=1}^{K}H_2(q_k),
\qquad H_2(q)=-\log\int q(r)^2\,dr.
$$

The implementation evaluates all Gaussian cross-integrals analytically and uses a
log-sum-exp calculation. Ablations are mean/max aleatoric variance, mean/max variance
of member means, and total variance.

## Data and leakage control

| Partition | Source | Role |
|---|---|---|
| ID pool | new standard `libero_object` collection | fitting and calibration |
| OOD Object | frozen `terminal_event_atlas_20260901` | development transfer test |
| OOD Environment | same atlas | development transfer test |
| OOD Position | same atlas | development transfer test |

The ID collector uses outcome-independent query indices `0,3,6,9`, H16 candidate
execution, four stochastic candidates, up to two rollouts per initial state, no feedback branch, and no terminal
continuation. One task is collected per job. The OOD atlas is pre-existing and its
outcomes were used by earlier work, so this stage is explicitly development, not a
fresh confirmatory holdout.

Rows are deduplicated by resolved `(sidecar_path, candidate_idx)`. A trajectory group
contains one `suite/task/init/rollout_seed`; all its snapshots and candidates remain
in one split. Inside each ID task, deterministic hash ordering with salt
`p4-residual-dynamics-v1` assigns 60% of groups to train, 20% to calibration, and 20%
to untouched ID test. PCA, standardization, MLP optimization, and bootstrap sampling
use only `train`.

## Conformal calibration

Candidate scores are reduced to one nonconformity score per trajectory by maximum:

$$
S_g=\max_{i\in g} U_{\mathrm{JRD}}(x_i).
$$

For $n$ calibration trajectories and target false-alarm level
$\alpha=0.1$, the frozen global threshold is

$$
\hat\epsilon=\operatorname{Quantile}_{\lceil(n+1)(1-\alpha)\rceil/n}
\{S_1,\ldots,S_n\},
$$

using the conservative `higher` sample quantile. ID test is opened only after the
threshold is fixed.

## Metrics and frozen gate

Primary metrics:

1. trajectory-level ID false-positive rate at $\alpha=0.1$;
2. group-level OOD AUROC, raw AUPRC, and class-balanced AUPRC for Object,
   Environment, Position, and pooled OOD;
3. Spearman correlation with realized Cosmos residual error;
4. comparison against `value_std`, `value_range`, action disagreement, future-state
   disagreement, and latent across-seed disagreement;
5. bootstrap 95% intervals for OOD ranking metrics.

The **primary OOD comparison is query-support matched**: only OOD snapshots whose
`query_idx` occurs in the ID pool (`0,3,6,9`) enter the frozen gate. A secondary
all-query table measures broader deployment extrapolation. This prevents later
episode phases present only in the historical OOD atlas from masquerading as
perturbation detection.

P4 passes the offline gate only if all conditions hold:

| Condition | Frozen threshold |
|---|---:|
| ID trajectory false-positive rate | at most 0.15 |
| pooled OOD JRD class-balanced AUPRC | at least `max(0.65, best_old_metric + 0.03)` |
| trajectory-max JRD vs trajectory-max realized standardized residual | Spearman at least 0.20 |

An offline hard-filter diagnostic is also reported:

$$
\mathcal A_{\mathrm{valid}}(s)=
\{a_i:U_{\mathrm{JRD}}(s,a_i)\le\hat\epsilon\},\qquad
a^*=\arg\max_{a_i\in\mathcal A_{\mathrm{valid}}}\hat v_i.
$$

If the feasible set is empty, the diagnostic falls back to max-value and records an
abstention. Local H16 utility is only a screening endpoint. No closed-loop claim is
allowed from this replay table.

## Decision rule

- **PASS:** freeze encoder, ensemble, and threshold; run a fresh LIBERO-PRO
  confirmatory holdout, then compare hard-filter planning with max-value.
- **Calibration-only PASS:** if ID FPR is controlled but OOD ranking misses the gate,
  retain the conformal machinery and replace the residual representation.
- **NO-GO:** if ID FPR is not controlled or JRD does not track realized error, do not
  spend closed-loop rollouts on this architecture.

## Reproducibility entry points

- `scripts/build_residual_dynamics_dataset.py`
- `scripts/extract_residual_dynamics_features.py`
- `scripts/train_residual_dynamics_ensemble.py`
- `scripts/analyze_residual_dynamics_ensemble.py`
- `scripts/run_p4_residual_dynamics_sequence.sh`
- `experiments/configs/libero_campaign_p4_standard_id_20260906.json`

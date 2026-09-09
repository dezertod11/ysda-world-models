# Frozen H16 Candidate Ranker: Closed-Loop Validation Protocol

Status: **preregistered before inspecting smoke or full-rollout outcomes**.

## Question

Does the already frozen factor-specific candidate ranker improve terminal success
over the Cosmos Policy max-value selector under the same six-candidate sampling
budget and paired initial decision state?

Operationally, the strategies share task, initial state, rollout seed, candidate
seed offsets, and inference budget. Their query-zero candidate pools therefore
represent the same state. Once different actions are selected, later environment
states and candidate predictions may legitimately diverge; those differences are
the closed-loop treatment effect, not a pairing violation.

This experiment evaluates an online policy intervention. The ranker was trained
on H16 counterfactual branch consequences and passed the separate offline holdout
gate. The task families below were therefore seen by the offline confirmation,
but the terminal rollout seeds and closed-loop trajectories used here were not
used to fit or tune the ranker.

## Frozen methods

At query state `s_q`, Cosmos Policy samples six joint predictions

$$
\mathcal{C}_q = \{(a_i^{1:16}, \hat{s}_i^+, \hat{v}_i, z_i)\}_{i=1}^{6}.
$$

The baseline executes the candidate with the largest predicted value:

$$
i_{\mathrm{maxV}} = \arg\max_i \hat{v}_i.
$$

For every candidate, the frozen method computes the eleven-feature vector

$$
x_i = [\hat v_i, \|a_i^1\|_1, \|a_i^{1:16}\|_1,
\|a_i^{1:16}\|_2, u^{a}_{\mathrm{mean}}, u^{a}_{\mathrm{max}},
u^{a_1}_{\mathrm{copy}}, u^{p}_{\mathrm{mean}}, u^{p}_{\mathrm{max}},
u^{v}_{\mathrm{mean}}, u^{v}_{\mathrm{max}}].
$$

Each feature is standardized within the current six-candidate set. Missing
values are imputed and standardized with frozen training statistics. The head
for perturbation factor `f` scores candidate `i` as

$$
r_{f,i} = \theta_f^\top
\frac{\operatorname{impute}(z_{\mathcal C_q}(x_i))-\mu_f}{\sigma_f},
\qquad
i_{\mathrm{ranker}} = \arg\max_i r_{f,i}.
$$

Model artifact:
`experiments/frozen_models/factor_h16_dense_ridge_v1.json`.

Frozen payload SHA-256:
`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`.

No coefficient, feature, selection threshold, candidate count, horizon, or task
selection may be changed after the smoke run starts.

Implementation amendment recorded after smoke and before any full-run outcome:
three query-zero pairs reproduced bit-for-bit, while one H100 pair showed
cross-process floating-point differences up to 0.000202 in value and 0.00281 in
the first action. The integrity check therefore uses fixed absolute tolerances of
`5e-4` for values, `2e-3` for ranker scores, and `5e-3` for first actions. Both
selector argmax indices were unchanged. These tolerances validate candidate
reproduction only; they are not model hyperparameters and cannot affect actions.

## Shared inference budget

| Setting | Value |
|---|---:|
| Candidate samples per query | 6 |
| Candidate seed offsets | 0, 1, 2, 3, 4, 5 |
| Executed action horizon | 16 |
| Action denoising steps | 5 |
| Prediction mode | parallel |
| Future-state samples / steps | 1 / 1 |
| Value samples / steps | 1 / 1 |
| Maximum environment steps | 280 |
| Safety instrumentation | enabled, non-terminating |
| Videos in primary run | disabled |

## Evaluation cells

All cells use initial states 5--9 and paired strategy runs with identical base
seeds. The fixed rollout seed step is 97.

| Factor | LIBERO-PRO suite / variant | Tasks | Seeds per task/init | Pairs |
|---|---|---:|---:|---:|
| Environment | `libero_object_env` | 7--9 | 8 | 120 |
| Object | `libero_object_object` | 8--9 | 12 | 120 |
| Position | `libero_object_temp_x0.3` | 4--5 | 6 | 60 |
| Position | `libero_object_temp_y0.3` | 8--9 | 6 | 60 |
| **Total** | | | | **360 pairs / 720 episodes** |

The smoke profile executes one pair in each of the four rows. Smoke outcomes
are excluded from every statistical table and cannot be used for tuning.

## Endpoints and analysis

Primary endpoint:

$$
\Delta SR_{\mathrm{macro}} = \frac{1}{3}\sum_f
(SR_{\mathrm{ranker},f}-SR_{\mathrm{maxV},f}).
$$

Uncertainty is estimated with 5,000 bootstrap draws, seed 20260829. Resampling
units are `task/init` groups within each factor; the factor-macro delta is formed
inside every draw. Exact paired McNemar/binomial tests are secondary.

Secondary diagnostics are per-factor SR, task/init SR, frozen gains and losses,
failure types, safety signals, query count, selector disagreement rate, and mean
predicted-value sacrifice. Candidate arrays and selected indices at query zero
must match the frozen selector definitions exactly.

## Formal gate

The closed-loop gate passes only when all conditions hold:

1. Exactly 120 complete pairs exist for each factor.
2. Every episode uses six candidates and the frozen payload hash above.
3. At query zero, paired candidate values, scores, and first actions match within
   the fixed numerical tolerances above.
4. Baseline selects max value and the ranker selects max frozen score.
5. The ranker changes at least one query-zero selection, proving it is active.
6. The 95% grouped-bootstrap lower bound for macro `Delta SR` is above zero.
7. No factor has a point estimate below -5 percentage points.
8. No factor has a 95% interval entirely below zero.

If the gate passes, the ranker becomes the next planning baseline. If it fails,
the next method is an action-conditioned grounded critic trained on observed
branch consequences; the frozen ranker is not retuned on this evaluation set.

## Post-hoc videos

After primary analysis, up to five `frozen_gain` and five `frozen_loss` seed pairs
are replayed with video. These replays explain mechanisms only and do not alter
the primary estimates or gate.

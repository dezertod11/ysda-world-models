# Semantic predicted-consequence screen

## Status

Exploratory development protocol frozen before extracting CLIP features or
fitting the models. The causal labels have been analyzed previously, so this
stage can select a feature family but cannot by itself validate a planner.

## Question

Can deployable semantic features of Cosmos-predicted future images estimate
the sign and magnitude of the value of fresh feedback better than the scalar
uncertainty metrics used so far?

For decision state $j$, the exact-state collector measured

$$
Y_j=U_j^{\mathrm{H8\rightarrow feedback}}-U_j^{\mathrm{H16\ commit}},
$$

where $Y_j$ is `dense_vof_v2`. Positive $Y_j$ means that re-query was useful.

## Data

Use the 265 strict replay states in
`counterfactual_feedback_dense_relabel_20260827`. They span Object, Position
and Environment perturbations and 54 independent `(factor, task, init)`
groups. Every state has current RGB/wrist observations, four Cosmos-predicted
future RGB/wrist images, action chunks, values and task text.

Actual branch endpoint images, terminal outcomes, MuJoCo state, object poses
and contacts are labels/evaluation data only. They are forbidden as model
features.

## Semantic features

A frozen `openai/clip-vit-base-patch32` encoder maps images and task text to
unit vectors. For current image $o$, candidate future $\hat o_i$ and task text
$l$:

$$
\Delta g_i=\cos(z(\hat o_i),z(l))-\cos(z(o),z(l)),
$$

$$
d_{\mathrm{motion},i}=1-\cos(z(o),z(\hat o_i)),
$$

$$
d_{\mathrm{disagree}}=
\frac{2}{K(K-1)}\sum_{i<k}
\left[1-\cos(z(\hat o_i),z(\hat o_k))\right].
$$

The same motion/disagreement features are computed for wrist images. We also
use selected-candidate goal alignment, rank, candidate mean/std/range and
cross-view consistency. Only the max-value selected index is used.

## Ablations

1. `scalar`: ten frozen value/action/future-dispersion metrics.
2. `semantic`: CLIP task alignment, semantic motion and candidate disagreement.
3. `combined`: union of both feature sets.

All models are standardized ridge regressions with fixed $\alpha=10$. No
hyperparameter is selected on the evaluation labels.

## Evaluation

Primary predictions are leave-one-`(factor, suite, task, init)`-group-out.
We report Spearman correlation with dense VoF, sign AUROC, balanced accuracy,
RMSE and causal uplift when re-query is assigned to the top 10%, 20% or 30%
predicted states. A stricter leave-one-factor-out result tests OOD transfer.

At budget $b$ and query cost $c=0.025$:

$$
\operatorname{uplift}_b=
\frac{1}{N}\sum_{j\in\operatorname{Top}_b(\hat Y)}Y_j,
\qquad
J_b=\operatorname{uplift}_b-cb.
$$

## Development gate

Semantic development advances to a new frozen data split only if:

1. combined grouped-OOF Spearman is at least 0.20 and exceeds scalar;
2. combined uplift@20% is positive and exceeds scalar;
3. combined uplift@20% is non-negative in every factor;
4. leave-one-factor-out combined Spearman is non-negative in every factor;
5. extraction covers all 265 strict states and no privileged feature enters
   the model.

A FAIL closes CLIP-global embeddings as the next router and moves to an
object/contact-centric consequence representation. A PASS permits a new
independent exact-state holdout, not direct closed-loop deployment.

# Object/contact-conditioned VoF: development protocol

Date frozen: 2026-09-03, before extracting object-conditioned CLIP features.

## Status and scope

This is an exploratory development screen, not a confirmatory holdout. Outcomes
from both source campaigns have already been opened. The screen may select a
representation and hyperparameters, but any efficacy claim requires a new,
untouched exact-state collection.

The corpus reuses all strict query-4 pairs from:

- `signed_vof_new_task_holdout_20260903`: 240 paired states;
- `invariant_cate_reserve_holdout_20260903`: 400 paired states.

Expected total: 640 states, 320 independent
`position_level x task x init_state` groups, 16 task/perturbation cells.

## Question

Can an object-conditioned representation of the current observation and the
Cosmos-predicted candidate futures identify when exact-state feedback is useful,
including the task-by-perturbation sign changes that defeated the invariant-CATE
router?

## Inputs and leakage boundary

Deployable inputs are restricted to information available before deciding whether
to re-query:

- current agent-view and wrist RGB;
- K=4 predicted future agent-view and wrist RGB images;
- current and predicted proprioception;
- the K=4 action chunks and values;
- selected max-value candidate index;
- task language.

The target object is parsed from language. A frozen CLIP ViT-B/32 encoder produces
patch-to-text similarities for the target object and the basket. From the 7x7
patch maps we compute confidence, entropy, centroid, spatial spread, target/basket
overlap and their predicted changes. No simulator pose, contact, branch endpoint,
success, failure, perturbation level, or phase label enters the primary model.

`position_level` features are retained only as a non-deployable diagnostic
ablation. Privileged labels below are supervision/evaluation targets only.

## Paired targets

For state `i`, exact-state branches give commit (`C`) and feedback (`F`) outcomes.
The primary causal target is

$$
\tau_i = Y_i^F - Y_i^C, \qquad Y_i^b \in \{0,1\}.
$$

Two fixed secondary targets encode consequence severity:

$$
\tau_i^{U} = \frac{U_i^F-U_i^C}{3.5},
$$

and

$$
\begin{aligned}
\tau_i^{G} ={}& \tau_i
-0.25\,\Delta\mathrm{drop}_i
-0.125\,\Delta\mathrm{wrong}_i
-0.125\,\Delta\mathrm{deadlock}_i \\
&+0.10\tanh\!\left(\frac{\Delta\mathrm{lift}_i}{0.025}\right)
+0.10\tanh\!\left(\frac{d_i^C-d_i^F}{0.03}\right),
\end{aligned}
$$

where positive values always favour feedback. `U` is the already frozen terminal
utility. Direct ridge prediction of these paired targets is compared with bounded
logistic potential-outcome heads
`P(Y^F=1|x)-P(Y^C=1|x)`.

Auxiliary heads predict branch-specific target contact, target lift, minimum
target-to-EEF distance, terminal drop, wrong-object interaction, and kinematic
deadlock. They diagnose whether the visual representation is grounded; their
labels are never model inputs.

## Model families

1. `relative`: previous action/value/proprio invariant features.
2. `relative_object_global`: add object-conditioned global CLIP similarities.
3. `relative_object_spatial`: add all global and patch-level object/basket
   relation features.
4. `object_spatial_only`: object-conditioned visual features without scalar
   uncertainty features.
5. `relative_object_spatial_context_diagnostic`: add known perturbation
   direction/magnitude; this family cannot be promoted.

Ridge penalties are fixed to `{0.01, 0.1, 1, 10}`. The development router ranks
states and re-queries the top 20%; cost is fixed at 0.025 per query.

## Transfer splits

Every row receives predictions from models that did not train on its held-out
group:

- leave one task out;
- leave one perturbation level out;
- leave one task/level cell out.

No random row split is used for model selection. Selection maximizes the minimum
cost-adjusted uplift across the three schemes, then rescue-vs-harm AUROC.

## Development gates

A new untouched GPU holdout is permitted only if all applicable checks pass:

1. selected deployable family contains object-conditioned features and improves
   over the best `relative` control in worst-split adjusted uplift;
2. top-20% cost-adjusted uplift is positive in all three split schemes;
3. worst-cell adjusted uplift is non-negative in all three schemes;
4. score-quintile outcome means are monotone enough (`rho >= 0.5`) in all three
   schemes;
5. leave-one-task auxiliary Spearman is at least 0.4 for open-branch target lift
   and minimum target-to-EEF distance;
6. leave-one-task AUROC is at least 0.75 for every terminal event head with both
   classes represented.

Failure closes this specific frozen-CLIP linear formulation. It does not disprove
object-centric consequence modelling; the next escalation would require learned
segmentation/detection or action-conditioned fine-tuning, followed by a fresh
protocol.

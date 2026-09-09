# Privileged context-interaction VoF upper bound

Date frozen: 2026-09-03, before fitting the interaction models.

## Status

This is an exploratory **non-deployable upper-bound** analysis on the already
opened 640-state P2c development corpus. It cannot support a confirmatory
efficacy claim and cannot authorize a new holdout by itself.

Its purpose is to decide whether a stronger observable object/contact encoder
is justified, or whether the current re-query CATE branch should be stopped in
favour of recovery and abstention.

## Question

Do explicit interactions between task identity, perturbation geometry,
privileged manipulation phase and decision-time dynamics make the sign of
query-4 feedback value transferable across tasks, perturbation levels and
task-level cells?

## Corpus and outcome

The input is the immutable P2c table
`object_contact_development_corpus.parquet`:

- 640 strict exact-state rows;
- 320 independent `level x task x init_state` groups;
- 16 task/perturbation cells;
- 80 feedback rescues, 94 harms and 466 ties.

For row $i$,

$$
\tau_i=Y_i^F-Y_i^C,\qquad Y_i^b\in\{0,1\},
$$

where $C$ commits to the old H16 chunk and $F$ executes H8, observes the real
state and generates a new H8 continuation.

## Leakage boundary

The primary `relative` features and frozen-CLIP object features remain exactly
those extracted before branch outcomes. The upper-bound context may add:

- task identity;
- perturbation direction and magnitude;
- exact perturbation-level identity;
- privileged snapshot phase: approach, grasp or transport.

Branch success, terminal events, future observed branch images, endpoint
states and per-cell outcome rates are forbidden as model inputs. Exact cell
one-hot features are allowed only as part of the context basis; under
leave-one-cell evaluation their held-out coefficient has no training support
and therefore remains zero.

## Interaction basis

Let

$$
z_i=[d_i,m_i,\phi_i^{approach},\phi_i^{grasp},\phi_i^{transport}],
$$

where $d_i$ is the x-direction indicator and $m_i$ the perturbation magnitude.
The context basis contains task and level one-hots plus

$$
T_i\otimes z_i,\qquad L_i\otimes\phi_i,
\qquad d_i m_i,\qquad d_i\phi_i,\qquad m_i\phi_i.
$$

The strongest upper-bound family additionally gives a predeclared compact set
of gripper, motion, uncertainty and object-relation variables context-specific
slopes:

$$
x_{ij}^{interaction}=x_{ij}\,z_i.
$$

No feature is selected by its correlation with the opened outcome.

## Model families

1. `relative_control`: the 80 P2c relative features.
2. `oracle_context_only`: context basis without visual/dynamics features.
3. `relative_oracle_additive`: relative features plus additive context.
4. `relative_oracle_interactions`: relative features plus the full context
   interaction basis.
5. `relative_oracle_dynamic_slopes`: family 4 plus compact dynamic-by-context
   slopes.
6. `relative_object_oracle_dynamic_slopes`: family 5 plus frozen-CLIP global
   object relations and their predeclared context slopes.

Every family is fit with ridge penalties `{0.01, 0.1, 1, 10}`. Compared score
targets are direct success effect, frozen grounded effect, frozen terminal
utility effect, and separate ridge potential-outcome heads:

$$
\widehat\tau_i=
\operatorname{clip}(\widehat\mu_F(x_i),0,1)
-\operatorname{clip}(\widehat\mu_C(x_i),0,1).
$$

## Evaluation

Every prediction is out-of-fold under four schemes:

- leave one task out;
- leave one perturbation level out;
- leave one task-level cell out;
- deterministic five-fold grouped interpolation within every cell
  (secondary upper-bound diagnostic only).

The primary router queries the top 20% scores. Budgets 10% and 30% are reported
only as sensitivity analyses. For cost $c=0.025$,

$$
G_{adj}(q)=\frac1N\sum_i q_i(\tau_i-c).
$$

Selection maximizes the minimum adjusted gain across the three transfer
schemes, then the minimum rescue-vs-harm AUROC. The within-cell split is not
used for selection.

## Decision gate

The context-interaction hypothesis passes this development upper bound only if
one interaction family satisfies all of the following at the 20% budget:

1. it improves worst-transfer adjusted gain over `relative_control`;
2. adjusted gain is positive under leave-one-task, leave-one-level and
   leave-one-cell;
3. worst-cell adjusted gain is non-negative in all three transfer schemes;
4. score-quintile effect Spearman is at least 0.5 in all three schemes;
5. rescue-vs-harm AUROC is at least 0.60 in all three schemes;
6. within-cell grouped adjusted gain is positive.

If the gate fails, P2d closes the current re-query CATE route and P3
recovery/abstention becomes the next priority. If it passes, the result only
justifies replacing privileged phase/context with an observable
high-resolution estimator before freezing a new holdout.

# Signed value-of-feedback router: development protocol

## Status

This is an exploratory post-holdout development analysis. The completed
Position-direction holdout is not reused to make a confirmatory claim. It is
converted into development data only after its frozen efficacy and interaction
gates failed.

The immediate question is whether information available before execution can
rank states where query-4 feedback rescues the episode above states where it
destroys an otherwise successful trajectory.

## Target

For each exact-state pair,

$$
Y_i=\mathbb{1}[success_{i,feedback}]
-\mathbb{1}[success_{i,commit}]\in\{-1,0,+1\}.
$$

`+1` is a rescue, `-1` is a harm and `0` is terminally neutral. Query cost is
charged separately and is not folded into the training target.

## Two decision times

### Pre-query trigger

This model may use only values available at the original query-4 state:

- stochastic action/value/future-state uncertainty;
- internal latent-copy dispersion;
- the selected old action chunk and predicted future proprio;
- current proprio;
- prediction error carried into query 4 from an earlier completed chunk.

It chooses whether to obtain a real-observation re-query after executing the
first eight actions. Its adjusted contribution is

$$
z_iY_i-c_{query}z_i,
$$

where $z_i\in\{0,1\}$ is the routing decision.

### Post-query tail selector

This model additionally sees the newly generated action/value outputs and the
disagreement between old actions 8-15 and new actions 0-7. These actions refer
to the same execution times. Because obtaining these features already requires
the additional model call, cost is charged for every state:

$$
z_iY_i-c_{query}.
$$

## Leakage exclusion

`feedback_endpoint_*` is saved after the new tail has executed in the current
collector. It is therefore forbidden, together with every local/terminal
success, failure, realized object-motion and realized prediction-error field.
The implementation uses explicit feature allowlists and a regression test that
changes endpoint arrays while requiring extracted features to remain identical.

## Evaluation

1. Keep every rollout seed from one init state in the same fold.
2. Produce leave-one-init-out ridge predictions for screen init 0-19, former
   holdout init 20-49 and their pooled development set.
3. Estimate predictive uncertainty from residual scale and regularized
   leverage using training rows only.
4. Evaluate conservative scores

   $$
   S_i=\hat\mu_i-\beta\hat\sigma_i,
   \qquad \beta\in\{0,0.5,1\}.
   $$

5. Report ranking at fixed 10%, 20%, 30%, 40% and 50% budgets, natural LCB
   thresholds, rescue recall, harm avoidance, terminal SR and query-adjusted
   gain.
6. As a transfer diagnostic, choose model/budget only on init 0-19 grouped OOF
   labels, fit that model on init 0-19, and apply the fixed budget to init
   20-49.

The analysis is exploratory because feature families are being designed after
the Position holdout was observed.

## Opportunity gate

A new targeted data collection is justified only if the best pre-query grouped
OOF development policy satisfies all of:

- adjusted terminal gain at least +5 percentage points;
- init-cluster bootstrap CI lower bound above zero;
- at least five rescues selected;
- at most two harms selected;
- the screen-selected pre-query policy remains positive on init 20-49 and
  selects more rescues than harms.

Passing this gate permits new data collection and later freezing. It does not
permit reporting an efficacy claim. A selector must subsequently be frozen and
tested on new tasks or newly generated initial configurations.

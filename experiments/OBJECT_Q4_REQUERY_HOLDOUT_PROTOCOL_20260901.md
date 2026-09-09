# Object query-4 requery holdout

## Frozen hypothesis

For LIBERO-PRO Object task 0, replacing the second half of the action chunk at
query 4 with actions generated from the real observation improves terminal
success relative to committing the original H16 chunk.

The development atlas contained 18 query-4 states with 4 rescues and 0 harms.
This document freezes the follow-up before observing holdout outcomes.

## Holdout population

- Suite: `libero_object_object`.
- Task: `0`, "pick the alphabet soup and place it in the basket".
- Decision: query index `4`, corresponding to executed step `64`.
- Unseen init states: `33,35-41,43-49`.
- Excluded because it appeared in development: init state `42`.
- Four new rollout seeds per init state, 60 exact-state pairs in total.
- Four stochastic Cosmos candidates per policy query.

## Paired interventions

1. `commit`: execute the selected H16 action chunk from the frozen state.
2. `requery`: execute H8, observe the real simulator state, generate a new
   candidate pool, and execute H8 from its max-value candidate.

Both branches start from the same saved MuJoCo and runtime state and continue
to the terminal LIBERO outcome. The candidate pool before branching is shared.

## Primary endpoint

\[
Y_i = \mathbb{1}[\mathrm{success}_{i,\,requery}]
      - \mathbb{1}[\mathrm{success}_{i,\,commit}].
\]

- `Y=+1`: rescue.
- `Y=-1`: harm.
- `Y=0`: unchanged terminal outcome.

Report paired success-rate difference, rescue/harm counts, exact McNemar test,
and a task/init-cluster bootstrap 95% confidence interval. Query cost is frozen
at `c_query=0.025`, so adjusted gain is

\[
\Delta_{adjusted}=\frac{1}{N}\sum_i Y_i-c_{query}.
\]

The intervention passes the practical gate only if raw and adjusted gains are
positive. Confirmatory evidence additionally requires the bootstrap lower bound
to exceed zero and two-sided McNemar `p<0.05`.

## Frozen secondary rankings

The following directions were selected using development data and must not be
changed after opening the holdout:

| Score | Direction predicting requery benefit |
|---|---|
| `latent_future_proprio_copy_std_mean_mean_over_samples` | higher |
| `candidate_action_consensus_chunk_mean` | lower |
| `action_std_mean` | lower |

Evaluate each score at fixed within-holdout budgets `5%`, `7.5%`, and `10%`.
These are secondary selector-transfer tests; the always-requery query-4 result
is the primary endpoint.

## Integrity gate

The strict analysis excludes states with
`main_open_replay_state_max_abs > 1e-9`. Any overlap with development init
states, missing terminal branch, or changed frozen direction invalidates the
confirmatory claim.


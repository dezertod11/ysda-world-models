# Object task-0 query-4 shared-prefix terminal replication

## Frozen question

Does the fixed query-4 feedback intervention improve terminal success when the
baseline and intervention share exactly the same reset-to-query-4 trajectory,
candidate pool and selected action chunk?

The controller is unchanged from the prior experiments. This protocol is
frozen before opening outcomes from the new rollout seeds.

## Population and intervention

- Suite/task: `libero_object_object`, task 0.
- Init states: 0-49.
- Two new rollout seeds per init state: 100 exact-state pairs.
- Four stochastic Cosmos candidates, selected by `max(value)`.
- Shared prefix: normal H16 policy through query 3; one shared candidate pool
  is generated at query 4 (executed step 64).
- Commit branch: execute the selected H16 chunk and continue maxV-H16 to the
  terminal outcome.
- Feedback branch: execute the same first H8 actions, observe the real state,
  query Cosmos once more, execute the new max-value H8, then continue maxV-H16
  to the terminal outcome. If LIBERO success occurs within the first H8, the
  completed branch does not issue an unnecessary query.
- Episode limit: 280 executed actions.

Both terminal branches restore the same captured MuJoCo/controller runtime
state. Candidate generation before the branch is performed once, not repeated
in separate processes.

## Primary endpoint

Only pairs passing replay integrity enter the primary endpoint:

$$
Y_i = \mathbb{1}[success_{i,feedback}]
      - \mathbb{1}[success_{i,commit}].
$$

Report mean $Y_i$, init-cluster bootstrap 95% CI, rescue/harm counts and exact
two-sided McNemar p-value. The frozen additional-query cost is 0.025:

$$
\Delta_{adjusted}=\frac{1}{N_{strict}}\sum_i Y_i-0.025.
$$

## Frozen gates

- At least 95/100 pairs must have
  `main_open_replay_state_max_abs <= 1e-9`.
- All 100 expected `(init_state, rollout_id, rollout_seed)` keys, terminal
  labels and four-candidate pools must be present.
- Practical PASS: integrity passes, raw delta is positive and adjusted delta is
  positive.
- Confirmatory PASS: practical PASS, cluster-bootstrap lower bound is positive
  and McNemar `p < 0.05`.

The nominal all-pair row is sensitivity only. No metric, query index, horizon,
candidate count or cost may be changed after outcomes are opened.

## Runtime diagnostic

In parallel, an identical-query diagnostic repeats query 0 on init states
0, 16 and 41 in two fresh processes under both default and strict deterministic
PyTorch settings. It compares full action chunks, values and selected indices
at tolerance `1e-5`. This diagnostic explains separate-process reproducibility;
it does not alter or gate the shared-prefix efficacy endpoint.

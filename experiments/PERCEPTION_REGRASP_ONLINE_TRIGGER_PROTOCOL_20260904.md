# P3c: observation-only online perception regrasp

## Question

Can the P3b RGB regrasp mechanism improve complete LIBERO-PRO Position episodes
when its activation is selected online, without simulator object coordinates?

## Frozen policy and intervention time

- Benchmark: `libero_object_temp` with LIBERO-PRO Position perturbations.
- Common policy: Cosmos Policy best-of-4 `max(value)`.
- Common prefix: H16 for queries 0--3, then the first 8 actions of query 4.
- Decision time: `t=72`, after the common q4 half-chunk.
- Baseline continuation: requery every 8 actions.
- Method continuation: the same H8 policy and query seeds after a possible RGB regrasp.
- Episode budget: 280 environment actions, including primitive actions.

At `t=72`, the exact MuJoCo and controller runtime state is captured once. Baseline
and method branches are restored from this same snapshot. Replay must have maximum
absolute state error at most `1e-9`.

## Deployable trigger

Let `p_hat` be the target world position estimated from the agent-view RGB image
and `e` the observed end-effector position. The intervention is eligible when

```text
T = confidence_pass AND workspace_pass
    AND ||p_hat - e||_2 >= 0.08 m
    AND ||p_hat - e||_2 <= 0.50 m.
```

Two trigger variants are frozen before new outcomes are inspected:

1. `workspace_calibrated`: object-specific fifth-percentile OOF `score_range`
   and object-specific 1--99% OOF target workspace expanded by 6 cm.
2. `global_conservative`: the same workspace and distance checks plus
   `score_range >= 39.579209327697754`, selected on P3b development only.

The localizer is run again after the three-step retreat. If that estimate fails
the same confidence/workspace/reach guard, the runtime state is restored and the
method exactly reuses the baseline outcome. Ground-truth object coordinates are
used by `SafetySignalTracker` only for evaluation labels.

## Prospective splits

All splits use groups absent from P3b (`init_state_id` in P3b was 5--24):

| split | init states | cells | rollouts | cases |
|---|---:|---:|---:|---:|
| screen | 25--26 | 3 | 2 | 12 |
| development | 27--31 | 8 | 1 | 40 |
| holdout | 35--39 | 8 | 1 | 40 |

The strict independent group is `(position_level, task_id, init_state_id)`.

## Endpoints and gates

Primary endpoint: paired task success-rate difference against `baseline_h8`.
Secondary endpoints: rescues, harms, target-drop diagnostics, wrong-object
interaction diagnostics, official safety costs, trigger coverage, and intervention
coverage. Screen selects one trigger variant. Development advances to untouched
holdout only if rescues exceed harms, SR is not lower, exact replay is complete,
and safety/wrong-object gates pass. The holdout is reported regardless of effect
size; no threshold is tuned on holdout outcomes.

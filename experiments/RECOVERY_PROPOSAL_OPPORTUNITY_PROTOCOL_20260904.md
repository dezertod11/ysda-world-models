# P3 recovery-proposal opportunity screen (frozen 2026-09-04)

## Question

Previous exact-state experiments showed that neither committing the original
16-action chunk nor the ordinary `8 actions -> real observation -> 8 revised
actions` branch reliably repairs hard LIBERO-PRO Position failures. Before
training another selector, this experiment asks a more basic question:

> Does any fixed recovery proposal create terminal successes from states where
> both existing actions fail?

## Frozen population

- Benchmark: LIBERO-PRO Position, suite exposed as `libero_object_temp`.
- Decision state: query 4 (`t=64`) exact MuJoCo snapshot.
- Eligibility: strict replay integrity, terminal labels available, commit fail,
  and ordinary feedback fail.
- Development set: 10 states from each of eight hard position/task cells (80
  states total), selected deterministically with independent init groups first.
- Untouched reserve: every other eligible both-fail state. It is not inspected
  for proposal tuning.
- Source labels and sidecars come from the completed P2c corpus. The frozen CSV
  hashes are stored in `frozen_manifest_metadata.json`.

## Common prefix and integrity check

Every branch restores the same runtime snapshot and first executes the eight
saved actions selected by the original max-value planner. Before evaluating a
new proposal, the collector replays the complete saved baseline `8+8` branch
and requires the final simulator state to match the recorded endpoint with
maximum absolute error at most `1e-9`.

## Frozen proposals

1. `frequent_requery_h4` (deployable): no hand-authored motion; query Cosmos
   after every four executed actions and select max predicted value among four
   stochastic candidates.
2. `lift_hold_h8` (deployable): execute four small positive-z motions while
   holding/closing the gripper, then continue max-value planning with an
   eight-action execution horizon.
3. `privileged_regrasp_h8` (diagnostic upper bound): use simulator target-object
   position to retreat, move above the object, descend, close and lift, then
   continue with horizon eight. This branch is not a deployable policy; it tests
   whether a recovery action exists in the state.

All branches use the same Cosmos checkpoint, action denoising steps (5), four
stochastic action/value samples per query, parallel prediction mode, and a
terminal horizon of 280 simulator steps. Full snapshot-to-terminal videos and
query-level uncertainty/value diagnostics are saved.

## Endpoints

Primary endpoint: terminal success rate (SR) over the 80 frozen states.

Secondary endpoints: target-drop rate, wrong-object interaction rate, official
safety violations, final timestep, number of Cosmos queries, executed actions,
per-cell SR, per-task breadth, and oracle coverage across proposals. Baseline
rates refer to the already recorded ordinary feedback branch on exactly the
same states.

## Pre-registered gate

A deployable proposal advances to the untouched reserve only if all conditions
hold:

- all 80 branches are present and at least 95% pass strict endpoint replay;
- SR is at least 10% (at least 8 rescues) and the group-bootstrap 95% lower
  bound is above zero;
- rescues occur in at least four of eight cells and at least three tasks;
- official-safety rate does not exceed baseline by more than 2.5 percentage
  points and target-drop rate does not exceed baseline by more than 5 points.

The privileged branch cannot pass the deployable gate. If only its oracle
coverage is substantial, the next step is a perception-backed regrasp proposal.
If no proposal produces broad rescues, proposal engineering is deprioritized;
another learned selector is not fitted to this development set.

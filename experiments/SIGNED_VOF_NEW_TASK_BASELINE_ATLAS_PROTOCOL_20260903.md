# Signed-VoF New-Task Baseline Atlas Protocol

## Purpose

Select difficult but non-degenerate LIBERO-PRO Object Position cells without
observing any feedback-branch or frozen-router outcome. The resulting cells are
used only to define a later prospective transfer holdout.

## Frozen model

- Artifact: `experiments/frozen_models/signed_vof_pre_state_action_a10_v1.json`
- Model: ridge `pre_state_action_a10`, `alpha=10`.
- Score: predicted signed VoF mean (`beta=0`).
- Absolute query threshold: frozen in the artifact at a 40% development query
  rate. It may not be recalibrated on this atlas or its follow-up holdout.

## Atlas design

- Benchmark: LIBERO-PRO Object, Position perturbations.
- New task IDs: 1-9; task 0 is excluded because it generated development data.
- Levels: `x0.2`, `y0.1`, `y0.2`, `y0.3`.
- Initial states: 0-4.
- One rollout seed per task/level/init tuple.
- Decision point: query 4 after executing 64 actions.
- Four stochastic Cosmos candidates; commit is the max-predicted-value candidate.
- Full terminal continuation to 280 steps.
- `skip_feedback_branch=true`: neither re-query outcomes nor router predictions
  are generated during cell selection.
- Total planned baseline decision states: 9 x 4 x 5 = 180.

## Frozen selection rule

For each `(task_id, position_level)` cell:

1. Require at least four strict usable states.
2. Require baseline commit success rate in `[0.20, 0.80]`.
3. Sort eligible cells by `abs(SR - 0.5)`, then decreasing usable count, task
   ID, and level.
4. Select the first six cells.

The atlas gate passes only if at least 95% of states are usable, at least six
cells are eligible, and the selected six cover at least three task IDs and both
`x` and `y` directions. A failed gate stops the sequence; no favorable cell is
substituted after looking at feedback effects.

## Authorized follow-up

On PASS, collect paired commit/re-query terminal outcomes only for the frozen six
cells using disjoint init states 5-24 and two rollout seeds per init. Evaluate
the frozen absolute-threshold router against always-commit and always-requery.
All task/level aggregate results, including unfavorable ones, must be reported.

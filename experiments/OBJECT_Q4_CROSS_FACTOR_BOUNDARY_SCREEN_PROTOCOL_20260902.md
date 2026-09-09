# Object task-0 query-4 cross-factor boundary screen

## Purpose

Find official LIBERO-PRO Position or Environment task-0 cells that contain
enough terminal success/failure and rescue/harm support for a later frozen
selective-feedback experiment.

This is a development screen. Cell-level effects and confidence intervals are
descriptive and cannot establish confirmatory cross-factor transfer. No cell,
threshold or selector will be tuned and tested on the same screen outcomes.

## Frozen cells

| Cell | Suite | Official perturbation | Init states | New seeds |
|---|---|---|---:|---:|
| `position_x0p1_task0` | `libero_object_temp` | `x0.1` | 0-19 | 20 |
| `position_x0p2_task0` | `libero_object_temp` | `x0.2` | 0-19 | 20 |
| `position_y0p2_task0` | `libero_object_temp` | `y0.2` | 0-19 | 20 |
| `position_y0p3_task0` | `libero_object_temp` | `y0.3` | 0-19 | 20 |
| `environment_task0` | `libero_object_env` | official Environment replacement | 0-19 | 20 |

The screen contains 100 exact-state pairs. Position conditions use only the
official pre-generated LIBERO-PRO levels; no interpolated BDDL or init state is
introduced. Environment generation uses the already fixed seed `20260825`.

## Shared-prefix intervention

The controller and endpoint are unchanged from the confirmed Object result:

$$
\text{commit}: A_{64:80}^{old},
$$

$$
\text{feedback}: A_{64:72}^{old}\rightarrow o_{72}^{real}
\rightarrow A_{72:80}^{new}.
$$

Both branches share the prefix, query-4 four-candidate pool, selected
`argmax(value)` action and captured MuJoCo/controller snapshot. Both continue
with maxV-H16 to terminal success or 280 executed actions.

## Integrity

- All 100 expected `(cell, init_state, rollout_id, rollout_seed)` keys must be
  present and unique.
- Each pair must have terminal labels, a valid feedback path, four candidates
  and exactly one max-value candidate.
- At least 95/100 pairs must satisfy
  `main_open_replay_state_max_abs <= 1e-9`.

## Frozen boundary criteria

For each 20-pair cell, report commit/feedback SR, paired delta, cluster
bootstrap CI, rescue/harm and McNemar p-value. A cell is eligible for a later
new-seed holdout when either of these development criteria is met:

1. **effect-support:** at least three rescues and at least three harms;
2. **non-ceiling opportunity:** at least three discordant pairs and the pooled
   40 branch outcomes contain at least four successes and four failures.

The first criterion supports learning a selective trigger. The second supports
testing always-feedback efficacy even when one effect direction is sparse.
Cells failing both criteria are not used for a confirmatory selector test.

## Decision after the screen

- If one or more official cells pass effect-support, train the object/contact
  signed-VoF selector only on development data and freeze it before collecting
  new seeds from the eligible cells.
- If cells pass only non-ceiling opportunity, run an always-feedback transfer
  holdout first; do not claim a selective result.
- If all cells are ceiling/floor with too little discordance, do not interpolate
  official perturbation files post hoc. Move to recovery proposals or create a
  separately preregistered continuous-perturbation benchmark.

# LIBERO-PRO Object New-Task Baseline Atlas Result

## Outcome

The outcome-blind atlas completed all 180 planned query-4 baseline states on
LIBERO-PRO Object tasks 1-9 and Position levels `x0.2`, `y0.1`, `y0.2`, and
`y0.3`. All 180 states were usable and all four candidate rows were present per
state. No feedback branch or router prediction was generated during selection.

Across the 36 `(task, level)` cells:

- 13 were terminal floors (`0/5` baseline successes);
- 7 were terminal ceilings (`5/5`);
- 16 were eligible mixed cells (`1/5` through `4/5`).

This explains why the earlier unperturbed tasks 1-9 transfer was uninformative
at 100% success: new task identity alone did not create a useful evaluation
boundary, while controlled Position perturbations do.

## Frozen selected cells

The preregistered ordering selected the first six cells closest to 50% baseline
success:

| Perturbation | Task | Command | Baseline SR |
|---|---:|---|---:|
| `y0.1` | 4 | pick the ketchup and place it in the basket | 2/5 (40%) |
| `x0.2` | 5 | pick the tomato sauce and place it in the basket | 2/5 (40%) |
| `y0.1` | 5 | pick the tomato sauce and place it in the basket | 3/5 (60%) |
| `y0.3` | 5 | pick the tomato sauce and place it in the basket | 3/5 (60%) |
| `x0.2` | 6 | pick the butter and place it in the basket | 3/5 (60%) |
| `y0.2` | 8 | pick the chocolate pudding and place it in the basket | 3/5 (60%) |

The selection covers four new tasks and both perturbation directions. All
frozen gates passed. The selected cells are now being evaluated with two seeds
on each disjoint init state 5-24, for 240 exact-state commit/re-query pairs.

Generated table, selection JSON and heatmap:
[`campaigns/signed_vof_new_task_baseline_atlas_20260903/analysis/baseline_atlas`](campaigns/signed_vof_new_task_baseline_atlas_20260903/analysis/baseline_atlas/RESULTS.md).

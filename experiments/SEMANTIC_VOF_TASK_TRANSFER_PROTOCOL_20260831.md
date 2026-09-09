# Semantic VoF task-transfer screen

## Status

Retrospective transfer protocol frozen after the 265-state semantic development
screen and before extracting features or fitting on the transfer set. Aggregate
phase-VoF outcomes were already inspected, so this is a mechanism screen, not
a confirmatory planner result.

## Train and transfer split

| Split | Factor | Tasks | Strict states |
|---|---|---:|---:|
| development | Environment | 0-3 | 98 |
| task transfer | Environment | 5, 8, 9 | 67 |

The tasks and init-state groups are disjoint. Training uses the frozen 2026-08-27
dense relabel; transfer uses the strict phase-VoF states from 2026-08-31.

## Frozen models

All models are ridge regressions with $\alpha=10$ and train-only
standardization:

1. `scalar`: the ten frozen value/action/future-dispersion metrics;
2. `scalar+agent-disagreement`: add mean pairwise CLIP distance between K=4
   predicted agent-view futures;
3. `scalar+crossview`: add selected future agent/wrist CLIP distance;
4. `scalar+semantic2`: add both semantic features.

The semantic features were selected from the development screen before this
transfer. No coefficient, threshold or feature is selected on tasks 5/8/9.

## Metrics and gate

Report dense-VoF Spearman, sign AUROC, balanced accuracy, RMSE, uplift at
10/20/30% feedback budgets and task-wise uplift@20%.

The primary `scalar+semantic2` model advances to a new blinded collection only
if all conditions hold:

1. transfer coverage is exactly 98 train and 67 test states with disjoint tasks;
2. Spearman exceeds scalar by at least 0.05;
3. sign AUROC is no worse than scalar;
4. uplift@20% is positive and exceeds scalar;
5. compute-adjusted uplift@20% is positive at query cost 0.025;
6. task-wise uplift@20% is non-negative for tasks 5, 8 and 9;
7. only deployable features are used.

A FAIL closes global CLIP embeddings as the main VoF router. The next semantic
model must be object/contact-centric and trained from explicit task relations.

# Semantic predicted-consequence experiments

## Decision

Global CLIP embeddings are **closed as the main VoF router**. They contain one
weak disagreement signal, but neither the full semantic model nor the frozen
two-feature extension improved the scalar baseline on task transfer.

The next representation should explicitly track target object, receptacle,
contact/lift/drop and task relation rather than global image similarity.

## Experiment 1: 265-state development screen

Protocol:
[`SEMANTIC_VOF_SCREEN_PROTOCOL_20260831.md`](SEMANTIC_VOF_SCREEN_PROTOCOL_20260831.md).
All 265 strict exact-state samples were encoded successfully. Features used
only current RGB/wrist, K=4 Cosmos-predicted futures and task text; actual
endpoints and simulator state were excluded.

| Family | Grouped OOF Spearman | Sign AUROC | Balanced accuracy | Factor-OOF Spearman |
|---|---:|---:|---:|---:|
| Scalar | **0.471** | **0.711** | **0.648** | 0.219 |
| CLIP semantic | 0.131 | 0.534 | 0.558 | -0.244 |
| Combined | 0.434 | 0.699 | 0.630 | **0.247** |

At a 20% feedback budget, causal dense-VoF uplift per state was 0.00354 for
scalar, -0.00013 for semantic and 0.00244 for combined. After charging query
cost 0.025, all three were negative.

Factor diagnostics:

| Model | Environment rho | Object rho | Position rho |
|---|---:|---:|---:|
| Scalar grouped OOF | 0.690 | 0.560 | -0.024 |
| Semantic grouped OOF | 0.434 | 0.051 | -0.295 |
| Combined grouped OOF | 0.608 | 0.521 | -0.052 |

The frozen development gate failed. Position remains the major distribution
shift; adding global semantic features did not fix it.

One exploratory feature survived as a hypothesis: mean pairwise CLIP distance
between K=4 predicted agent-view futures had univariate grouped OOF Spearman
0.230. Selected agent/wrist cross-view distance was strong only inside the
Environment subset. These two features were frozen for task transfer.

## Experiment 2: Environment task transfer

Protocol:
[`SEMANTIC_VOF_TASK_TRANSFER_PROTOCOL_20260831.md`](SEMANTIC_VOF_TASK_TRANSFER_PROTOCOL_20260831.md).
The model was trained on 98 Environment states from tasks 0-3 and evaluated
without refitting on 67 strict states from tasks 5/8/9.

| Model | Transfer Spearman | Sign AUROC | Balanced accuracy | Uplift@20% |
|---|---:|---:|---:|---:|
| Scalar | **0.245** | **0.620** | 0.577 | -0.000397 |
| Scalar + agent disagreement | 0.243 | 0.619 | 0.577 | -0.000397 |
| Scalar + cross-view | 0.199 | 0.612 | **0.617** | -0.000346 |
| Scalar + both semantic | 0.200 | 0.613 | **0.617** | -0.000346 |

The primary semantic extension failed every efficacy condition except being
slightly less negative than scalar at budget 20%. Its task-wise uplift@20%
was negative on tasks 5, 8 and 9. At budget 30% nominal uplift became positive
(0.00360), but compute-adjusted uplift remained negative (-0.00424).

## What was learned

1. Existing scalar world-model signals predict dense VoF moderately within
   familiar factors, but still do not yield positive compute-aware routing.
2. Generic task-text/image alignment is too coarse for small manipulation
   changes such as grasp loss, contact, drop and correct receptacle relation.
3. Candidate semantic disagreement may be retained as a secondary feature,
   not as a standalone uncertainty estimate.
4. Position perturbations require geometric/object-centric state and likely a
   recovery proposal; global embedding distance is especially weak there.
5. The next model should predict explicit relation deltas and critical-event
   probabilities with an independently trained ensemble.

Artifacts:

- [`campaigns/semantic_vof_screen_20260831/analysis/RESULTS.md`](campaigns/semantic_vof_screen_20260831/analysis/RESULTS.md)
- [`campaigns/semantic_vof_task_transfer_20260831/analysis/RESULTS.md`](campaigns/semantic_vof_task_transfer_20260831/analysis/RESULTS.md)

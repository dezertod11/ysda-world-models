# Temporal overlap result audit

- Integrity: valid=True; traces=24; queries=8146; checked overlaps=7834.
- Episodes: 312 (215 success, 97 fail).
- Collector-labeled events: 81; events inside successful episodes: 26.
- Mixed outcome case/mode cells: 5/24.
- Instruction/goal head-token mismatches: 2 case/mode cells.

The event columns are heuristic diagnostics, not validated physical-failure ground truth.
`event_on_success`, `fixed_time_event`, and `instruction_goal_mismatch` flags must be resolved before early-warning claims.

## Seed-mode control

Across 72 matched seeds: both success=45, both fail=20, independent-only success=4, coupled-only success=3.

At query 1, coupled noise did not reduce selected overlap RMSE: ratio=1.017, paired correlation=0.974.

## H=16 numerical ranking

### independent

| Metric | AUPRC | Prevalence | AUROC | TPR | FPR |
|---|---:|---:|---:|---:|---:|
| `overlap_selected_all_rmse` | 0.124 | 0.054 | 0.497 | 0.087 | 0.018 |
| `previous_prediction_error_future_proprio_l2` | 0.112 | 0.054 | 0.620 | 0.037 | 0.024 |
| `overlap_gripper_mismatch` | 0.106 | 0.054 | 0.512 | 0.087 | 0.009 |

### coupled

| Metric | AUPRC | Prevalence | AUROC | TPR | FPR |
|---|---:|---:|---:|---:|---:|
| `overlap_gripper_mismatch` | 0.132 | 0.059 | 0.505 | 0.077 | 0.005 |
| `overlap_selected_all_rmse` | 0.131 | 0.059 | 0.503 | 0.077 | 0.010 |
| `previous_prediction_error_future_proprio_l2` | 0.124 | 0.059 | 0.602 | 0.077 | 0.019 |

These numbers describe the current collector labels only. The research interpretation is frozen separately in `experiments/TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`.

## Files

- `episode_outcomes.csv`
- `case_event_audit.csv`
- `paired_seed_mode_outcomes.csv`
- `seed_mode_q1_metric_comparison.csv`
- `key_query_metrics_h16.csv`
- `summary.json`

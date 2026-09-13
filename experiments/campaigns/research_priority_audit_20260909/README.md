# Research-priority audit, 9 September 2026

This directory contains read-only audits and derived tables, not a new
robot rollout campaign or a trained model evaluation.

- `server_status.json`: remote state at 13:24 MSK, config/script hashes,
  job timings and GPU availability; episode counts verified at 13:13 MSK.
  The live sequence was not changed. External project names are omitted.
- `existing_opportunity_by_cell.csv`: regrouping of 194 previously opened
  strict candidate pools by factor/task/case.
- `existing_opportunity_by_query.csv`: the same source grouped by query.
- `existing_data_summary.json`: source path/hash, support and scope.

The 14 rescue opportunities all belong to Object task0 and Environment
task3. This describes the recorded K4 pools and continuation, not all possible
actions or all instances of these tasks. All previous source outcomes are
retained; these tables do not constitute a new holdout.

Decisions: [near-term research plan](../../RESEARCH_PRIORITIES_20260909.md)
and [P5 refinement](../../P5_TASK_CRITICAL_REFINEMENT_20260909.md).

# YSDA World Models: Uncertainty-Aware Planning

Research project on uncertainty estimation and risk-aware action selection for
Cosmos Policy in LIBERO and LIBERO-PRO.

The central question is whether stochastic and latent uncertainty can identify
an unreliable action chunk before execution and improve the standard
`argmax(value)` planner in out-of-distribution manipulation tasks.

## Current result

- Standard LIBERO ID control: 72/72 successful rollouts.
- LIBERO-PRO screening: 82/106 successful rollouts and seven mixed
  success/failure configurations.
- Full validation: 23 jobs, 1078 strategy executions and 13351 policy queries.
- LIBERO-Safety physical evaluation is complete: 144/144 rollouts, zero task
  successes and four official safety violations.
- On selected boundary cases, adaptive `requery_l1_h8` improved success from
  146/240 (60.8%) to 161/240 (67.1%) at 1.27x normalized query cost.
- On the broader 897-episode LIBERO-PRO Object pilot, that gain did not
  transfer: no planning scored 52.8%, `max(value)` 54.5%, and risk-aware
  adaptive requery 52.1%. The current research focus is therefore grounded
  candidate evaluation and selective feedback timing, not another static
  uncertainty penalty.
- A frozen future-proprio error surrogate transferred as a physical prediction
  error estimator (case-controlled Spearman 0.579, top-quartile AUROC 0.731),
  but its gated planner did not improve task success.

The current staged research plan is documented in
[`experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).
P0 causal horizon controls are running on MLSpace GPU 6. The queued
`scripts/run_grounded_planning_sequence.sh` analyzes P0 before starting the
300-state exact-snapshot P1/P2 pilot, so the two campaigns cannot overlap.

## Repository layout

```text
articles/             Paper PDFs and literature review
configs/              Local experiment configuration
experiments/          Protocols, compact results and plots
patches/              Reproducible changes over pinned upstream projects
scripts/              Setup, rollout and analysis commands
ysda_world_models.ipynb
ysda_world_models_research.ipynb
```

Large raw traces, videos, model checkpoints, environments and downloaded assets
are intentionally excluded from Git. They remain in the local/server experiment
storage and can be regenerated from the committed configs.

## Restore source checkouts

The modified third-party projects are represented as patches over pinned public
commits. From the repository root:

```bash
./scripts/bootstrap_source_checkouts.sh
```

This creates:

- `cosmos-policy` at NVIDIA commit
  `18a2accadf4e7a3531e56754102af5a24d2316da`;
- `LIBERO-PRO` at commit
  `eafdb809426b13153aa1e4c42d6601844217dfec`;
- all local policy, uncertainty, VFD, safety and OOD-task modifications.

The script refuses to overwrite existing checkouts.

## Environment

For the MLSpace server workflow, see
[`SERVER_MLSPACE_RUNBOOK.md`](SERVER_MLSPACE_RUNBOOK.md). After restoring the
source checkouts:

```bash
bash scripts/setup_mlspace_cosmos.sh
source scripts/cosmos_env_libero_pro.sh
```

LIBERO-Safety uses a separate environment:

```bash
bash scripts/setup_mlspace_libero_safety.sh
```

## Main entry points

- Current research roadmap:
  [`experiments/RESEARCH_ROADMAP_20260820.md`](experiments/RESEARCH_ROADMAP_20260820.md)
- Frozen next-stage protocol:
  [`experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md)
- Exact-state P1/P2 feedback and candidate protocol:
  [`experiments/COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](experiments/COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md)
- Broad LIBERO-PRO Object baseline:
  [`experiments/campaigns/pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md`](experiments/campaigns/pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md)
- Latest surrogate/requery result:
  [`experiments/LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](experiments/LIBERO_SURROGATE_REQUERY_RESULTS.ipynb)
- Latest written analysis:
  [`experiments/SURROGATE_REQUERY_RESULTS_20260820.md`](experiments/SURROGATE_REQUERY_RESULTS_20260820.md)
- Final results notebook:
  [`experiments/LIBERO_FINAL_RESULTS.ipynb`](experiments/LIBERO_FINAL_RESULTS.ipynb)
- Experiment index: [`experiments/README.md`](experiments/README.md)
- Full validation protocol:
  [`experiments/LIBERO_8H_VALIDATION_PROTOCOL.md`](experiments/LIBERO_8H_VALIDATION_PROTOCOL.md)
- Unified results:
  [`experiments/LIBERO_COMPLETE_RESULTS_20260724.md`](experiments/LIBERO_COMPLETE_RESULTS_20260724.md)
- Paper review:
  [`articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](articles/LIBERO_EXPERIMENTS_AND_PAPERS.md)

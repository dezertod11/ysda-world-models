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
- The latest frozen LIBERO-PRO confirmatory campaign completed 960/960
  executions on 12 cases. Adaptive `requery_l1_h8` improved success from
  146/240 (60.8%) to 161/240 (67.1%): +6.25 percentage points, paired 95% CI
  `[+1.7, +11.3]`, Holm-corrected `p=0.0474`, at 1.27x normalized query cost.
- A frozen future-proprio error surrogate transferred as a physical prediction
  error estimator (case-controlled Spearman 0.579, top-quartile AUROC 0.731),
  but its gated planner did not improve task success.

The latest formulas, tables and limitations are documented in
[`experiments/SURROGATE_REQUERY_RESULTS_20260820.md`](experiments/SURROGATE_REQUERY_RESULTS_20260820.md).

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

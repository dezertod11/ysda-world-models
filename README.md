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
- A late critical-moment detector transferred to a held-out seed block on one
  fixed milk task.
- A fixed `value - lambda * uncertainty` penalty did not improve
  `max(value)` across the confirmatory 50-rollout aggregate.
- LIBERO-Safety support is prepared, but the official safety campaign has not
  yet been executed.

The complete formulas, tables and limitations are documented in
[`experiments/LIBERO_COMPLETE_RESULTS_20260724.md`](experiments/LIBERO_COMPLETE_RESULTS_20260724.md).

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

- Final results notebook:
  [`experiments/LIBERO_FINAL_RESULTS.ipynb`](experiments/LIBERO_FINAL_RESULTS.ipynb)
- Experiment index: [`experiments/README.md`](experiments/README.md)
- Full validation protocol:
  [`experiments/LIBERO_8H_VALIDATION_PROTOCOL.md`](experiments/LIBERO_8H_VALIDATION_PROTOCOL.md)
- Unified results:
  [`experiments/LIBERO_COMPLETE_RESULTS_20260724.md`](experiments/LIBERO_COMPLETE_RESULTS_20260724.md)
- Paper review:
  [`articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](articles/LIBERO_EXPERIMENTS_AND_PAPERS.md)

# P4b residual-risk run card

## Launch

The sequence is resumable and waits until physical GPUs 2--7 have been below
the configured memory limit for two consecutive polls:

```bash
cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
nohup env P4B_GPUS=2,3,4,5,6,7 \
  bash scripts/run_p4b_residual_risk_sequence.sh \
  > experiments/campaigns/p4b_residual_risk_20260907/launcher.log 2>&1 </dev/null &
```

GPU 0 and GPU 1 are explicitly rejected. Existing foreign jobs are never
terminated or preempted.

## Stages

1. validate code, protocol, P4 data and frozen checksums;
2. wait for GPU capacity;
3. train three OOB-early-stopped variants in parallel;
4. compare four variants on the opened P4 development corpus and freeze one
   selector;
5. collect 200 prospective snapshots with all four candidate branches
   continued to terminal outcome;
6. extract frozen CLIP features and evaluate the frozen paired terminal gate;
7. report `completed_pass_ready_for_closed_loop` or `completed_no_go`.

## Status

From WSL:

```bash
ssh mlspace-sr006 "cat /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/p4b_residual_risk_20260907/sequence_status.json"
```

```bash
ssh mlspace-sr006 "cat /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/p4b_residual_risk_20260907/heartbeat.txt"
```

```bash
ssh mlspace-sr006 "tail -n 60 /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/p4b_residual_risk_20260907/launcher.log"
```

## Outputs

- development comparison:
  `experiments/campaigns/p4b_residual_risk_20260907/development/`;
- immutable selector:
  `experiments/campaigns/p4b_residual_risk_20260907/development/frozen_selector.json`;
- prospective raw campaign:
  `experiments/campaigns/p4b_terminal_candidates_20260907/`;
- terminal paired analysis:
  `experiments/campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/`;
- trained variants:
  `experiments/frozen_models/p4b_residual_risk_20260907/`.

Closed-loop planning is deliberately not run unless the prospective offline
gate passes.


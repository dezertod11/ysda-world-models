# P3e Recovery Outcome Ensemble: run record

## Launch

- Started: 6 September 2026, 14:22 MSK.
- Server repository:
  /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
- Campaign: recovery_outcome_router_holdout_20260906.
- Detached sequence PID: 4122741.
- Physical GPUs: 2, 3, 4, 5.
- Expected work: 75 cases, 225 exact-state terminal branches.
- Videos: disabled by frozen protocol.

All GPUs were idle before launch. Server preflight completed 16/16 tests,
Ruff, shell syntax and all frozen SHA256 checks before the first holdout
rollout.

## Status

- Finished: 6 September 2026, 15:31 MSK.
- Wall time: approximately 69 minutes.
- Final status: `completed_pass`, exit code 0.
- Cases / branches: 75/75 and 225/225.
- Completion files: 4/4.
- Traceback / OOM / runtime errors: 0.
- Exact replay / feature / fallback integrity: PASS / PASS / PASS.

Primary frozen result: full regrasp 53/75 -> router 55/75, `+2.7 pp`, group
CI `[0.0; +6.7]`, 2 rescue / 0 harm. Full interpretation:
[`P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md`](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md).

From local WSL, the archived server status can be checked with:

```bash
ssh mlspace-sr006 \
  "cat /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/recovery_outcome_router_holdout_20260906/sequence_status.json"
```

The sequence remains resumable from atomic parquet files. A normal scientific
rejection would end with `status=completed_no_go` and exit code 0; an
infrastructure or code failure ends with `status=failed` and a non-zero code.

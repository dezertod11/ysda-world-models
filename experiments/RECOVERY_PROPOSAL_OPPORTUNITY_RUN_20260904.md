# P3 recovery-proposal campaign launch

## Final status

- Completed: 2026-09-04 01:51 MSK.
- Jobs: 8/8; terminal branches: 240/240; videos: 240/240.
- Strict endpoint replay: 240/240, maximum absolute state error `0.0`.
- Fixed-proposal rescues: frequent H4 `7/80`, lift/hold `8/80`, privileged
  regrasp `62/80`.
- Registered decision: `develop_perception_backed_regrasp_then_test_reserve`.
- Full interpretation:
  [`RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md).

## Frozen run

- Run prefix: `recovery_proposal_opportunity_20260904`
- Launched: 2026-09-04 00:29 MSK
- Server PID: `1998522`
- Physical GPUs: `2,3,4,6,7` (GPU 5 was occupied by another user and was not used)
- Workload: 80 exact snapshots x 3 proposals = 240 terminal branches
- Parallel layout: five workers; three queued jobs resume on GPUs 2-4
- Development manifest SHA-256:
  `7d6fb0aa9011acda9e559da9cc8d44e5bde19a5d805bbf27589c6af465e89019`
- Untouched reserve: 109 states; not scheduled in this run

The sequence is detached with `nohup`. It writes each finished branch to
Parquet/CSV, writes MP4 through a temporary file and renames it atomically,
skips completed branches after restart, and automatically runs the frozen
analysis after all eight jobs complete.

## Preflight evidence

- Local targeted tests: 13 passed.
- Server targeted tests: 6 passed before launch.
- One-state all-proposal smoke: 3/3 branches completed.
- Saved baseline endpoint replay error: `0.0` for all smoke branches.
- Smoke query rows: 9.
- Smoke videos: 3/3 decode; each has 33 frames at `256 x 512` (agent and wrist views).

## Monitoring from WSL

One snapshot:

```bash
bash scripts/mlspace_experiment_status.sh recovery_proposal_opportunity_20260904
```

Refresh every minute until the campaign reaches a final state:

```bash
bash scripts/mlspace_experiment_status.sh \
  recovery_proposal_opportunity_20260904 --watch 60
```

Raw detached-process status:

```bash
ssh mlspace-sr006 '
  cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP &&
  cat experiments/campaigns/recovery_proposal_opportunity_20260904/sequence_status.json &&
  cat experiments/campaigns/recovery_proposal_opportunity_20260904/heartbeat.txt
'
```

## Expected final artifacts

```text
experiments/campaigns/recovery_proposal_opportunity_20260904/
  manifest.json
  sequence_status.json
  heartbeat.txt
  logs/*.log
  runs/*__recovery_branches.parquet
  runs/*__query_metrics.parquet
  runs/*__videos/*.mp4
  analysis/RESULTS.md
  analysis/recovery_proposal_summary.csv
  analysis/recovery_cell_summary.csv
  analysis/oracle_summary.json
  analysis/query_metric_separation.csv
  analysis/pre_intervention_metric_separation.csv
  analysis/recovery_opportunity.png
  analysis/video_index.html
```

The complete frozen design and advancement gate are in
[`RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md`](RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md).

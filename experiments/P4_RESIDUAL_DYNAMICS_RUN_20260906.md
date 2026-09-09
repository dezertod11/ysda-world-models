# P4 residual-dynamics run card

Final status: **completed_no_go** on 6 September 2026. The sequence exited with
code 0, but the frozen offline gate failed; no closed-loop hard-filter campaign
was launched. See
[`P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md).

## Launch

The resumable server sequence is:

```bash
cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP
nohup env P4_GPUS=3,4,6,7 \
  bash scripts/run_p4_residual_dynamics_sequence.sh \
  > experiments/campaigns/p4_residual_dynamics_20260906/launcher.log 2>&1 </dev/null &
```

It first waits for the four P3e diagnostic video replays, then collects standard
LIBERO ID transitions, creates the frozen transition manifest, extracts CLIP
features, trains five independent Gaussian heads, calibrates trajectory-level JRD,
and writes the offline analysis.

## Status

```bash
cat experiments/campaigns/p4_residual_dynamics_20260906/sequence_status.json
cat experiments/campaigns/p4_residual_dynamics_20260906/heartbeat.txt

python scripts/status_libero_campaign.py \
  experiments/campaigns/p4_standard_id_20260906 --verbose
```

Direct status files:

- `experiments/campaigns/p4_residual_dynamics_20260906/sequence_status.json`
- `experiments/campaigns/p4_residual_dynamics_20260906/heartbeat.txt`
- `experiments/campaigns/p4_standard_id_20260906/manifest.json`

## Outputs

- P3e video index: `experiments/campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html`
- dataset split counts: `experiments/campaigns/p4_residual_dynamics_20260906/dataset/split_counts.csv`
- frozen heads: `experiments/frozen_models/p4_residual_dynamics_20260906/`
- P4 summary: `experiments/campaigns/p4_residual_dynamics_20260906/analysis/summary.json`
- OOD metrics: `experiments/campaigns/p4_residual_dynamics_20260906/analysis/ood_detection_metrics.csv`
- conformal alarms: `experiments/campaigns/p4_residual_dynamics_20260906/analysis/conformal_alarm_rates.csv`
- offline hard filter: `experiments/campaigns/p4_residual_dynamics_20260906/analysis/offline_hard_filter.csv`

## Final audit

- ID collection: 10/10 jobs complete, 800 NPZ snapshots total.
- Dataset: 5,668 candidate rows, 541 trajectory groups, 1,417 snapshots.
- Frozen artifact: five heads plus preprocessing; every entry in `SHA256SUMS`
  passes after the server-to-local transfer.
- Primary JRD: 5,668/5,668 clamped scores equal zero.
- Gate: ID FPR PASS, OOD balanced-AP FAIL, residual-correlation FAIL.
- Sequence status: `completed_no_go`; this is a scientific gate failure, not a
  runtime or data-integrity failure.

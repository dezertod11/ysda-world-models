# Launch Verification

Campaign: `grounded_probe_20260911_v2`.
Snapshot: 2026-09-11 02:16:27 MSK (2026-09-10 23:16:27 UTC).
This is a timestamped launch audit, not the live status or a scientific result.

## Execution

- Detached dispatcher PID: `128107`; launch: 01:59:04 MSK.
- Hard deadline: **2026-09-11 08:35 MSK**, unchanged after reconnecting.
- Configuration SHA256: `c0e279f60020dc5f1374a475fa068b44381abde2c80b045cb5e920307d15b6cb`.
- Smoke: **48/48 branches**, six matched states, eight arms. Integrity analysis passed on the server and on the downloaded local copy.
- Screen started automatically at approximately 02:16:17 MSK: 384 planned branches, initially seven workers on GPUs 0, 1, 2, 3, 5, 6, 7. GPU 4 was occupied by a foreign process and was skipped.
- Initial screen worker PIDs: GPU0 `138364`, GPU1 `138366`, GPU2 `138377`, GPU3 `138362`, GPU5 `138374`, GPU6 `138369`, GPU7 `138359`.
- No worker retry or failure was reported at this snapshot. No server stop signal was sent during the brief user pause; no duplicate campaign was launched on continuation.

## Checks

- Focused local test suite: **52 passed**, rerun after reconnection.
- Strict smoke analysis verified branch identity, frozen mask identity, prefix/NPZ/video hashes, finite actions, physical-step accounting, query seeds, and cross-arm probe-state parity.
- All **48 videos** were downloaded and decoded locally: **5,629 frames**, every decoded frame count matched the collector metadata.
- A separate first-case audit found identical executed actions and final simulator states between `probe_always_regrasp` and both mask arms when all three requested recovery. This is an implementation check, not evidence of an SR gain.

## Mask Training

Historical data only: 388 samples, 310 train / 78 validation, grouped split.
Fixed epoch 30: validation macro-IoU **0.816718**, macro-precision **0.868165**.
The preregistered segmentation gate passed. These are segmentation metrics,
not robot success rates; visibility and occlusion shift remain limitations.

The earlier campaign without the `_v2` suffix stopped during the data-membership
check, before any training epoch or rollout. The corrected archive matches all
388 manifest rows. Its original source archive and failure records were retained.
No thresholds or evaluation seeds were changed based on rollout outcomes.

## Where to Look

- [Protocol](../../GROUNDED_PROBE_PROTOCOL_20260911.md)
- [Status snapshot](sequence_status.json): use the remote `--status` command in the protocol for live progress.
- [Technical smoke report](analysis/smoke/RESULTS.md)
- [Downloaded smoke videos](analysis/smoke/videos.html)
- Later automatic reports: `analysis/screen/`, conditional `analysis/holdout/`, and `analysis/transfer/`.

Only a screen winner passing the frozen criteria enters confirmation. Independent
transfer of the existing recovery/timing controls runs even without a screen winner.
No claim of improved SR is made from this technical smoke test.

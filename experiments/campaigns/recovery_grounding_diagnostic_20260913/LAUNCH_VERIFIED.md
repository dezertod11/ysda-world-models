# Verified follow-up launch

Checked: **2026-09-13 12:35:49 MSK**. This is a timestamped operational
snapshot, not a live status or final scientific result.

## Frozen confirmation resume

- Dispatcher PID3534005, live main workers onGPU1,2,7 at this check.
- Scientific config SHA256 unchanged:
  `a3c73f4b93ee7249e12536104269aa6ab35d603e5e8e5fdc395426c5f6e5eb15`.
- Main committed outcomes **507/512**, up from441before resume.
- Dispatcher case/batch-level counter still464; it updates completed cases
  when the batch exits, so it temporarily trails the committed files.
- Timing0/768 at this check; automatic main audit precedes timing.
- Resource amendment:
  `../recovery_confirmation_20260913/resource_resumes/20260913T091537Z/amendment.json`.
- First attempt failed writing status with transientNFS ENOSPC; retry kept
  the same deadline. No output deletion or scientific modification.

## Grounding diagnostic

- Dispatcher PID3546594; oracle workers3556844onGPU6 and3556847onGPU0.
- Frozen config SHA256:
  `c41f52ab5ff3a3140343507914c64a0a39da62111784fd820257c652c7e4f22d`.
- Geometry **32/32** collected with camera overlays and numerical checks.
- Replay smoke **2/2 passed**: x0.2_t5_i25 successTrue;
  x0.3_t1_i25 successFalse. Full actions match source to1e-6,
  final simulator state to1e-8, labels unchanged.
- Oracle stage active; four arms on32cases,128total outcomes including
  the two smoke controls. No inference about oracle SR at this check.
- Four full event none/shadow control rollout queued after oracle.
  There is no automatic deployable event-method sweep or training.

## Resource and verification record

Both queues share idle-only GPU claim locks and cutoff
**2026-09-13 21:12:40 MSK**. Max5confirmation workers and2diagnostic workers;
GPU4/5 belonged to other processes and were not used by this launch.
Detached processes continue independently of SSH/WSL. Deadline completion
is not guaranteed if storage or resource availability changes.

58 focused CPU tests passed locally and on server, including event logic,
recovery identity checks, resource resume and grounding helpers. Local/server
code and protocol checksum comparison showed no differences.

[Experiment protocol](../../RECOVERY_GROUNDING_DIAGNOSTIC_PROTOCOL_20260913.md).
Live status: `sequence_status.json`; automatic outputs: `analysis/`.
The previous interrupted analysis is preserved under
`../recovery_confirmation_20260913/analysis/interim_20260913/`.

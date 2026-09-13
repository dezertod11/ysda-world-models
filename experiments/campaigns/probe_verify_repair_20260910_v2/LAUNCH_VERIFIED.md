# Launch verification

Started 2026-09-10 22:41:15 MSK, dispatcher PID33728.
Initial workers: GPU1 PID33832, GPU3 PID33825, GPU6 PID33829.
Only idle devices were admitted; unrelated workloads were not stopped.

Frozen config SHA-256:
`68d7c42f4c3fc98090e5ad263432e57e1213b53a70828e690583d53580ad2736`.
Scientific jobs, thresholds, artifacts, arms and budgets match v1 exactly.
V1's 16 technical smoke branches are excluded, and its source is archived.

Validation:
- 75 local CPU tests, 67 server CPU tests passed.
- A geometry-only render/segmentation audit verified native OpenGL versus
  OpenCV tracking coordinates. It does not feed GT geometry to the controller.
- First complete v2 case `x0.1_t5_i33_r0`: all four branch hashes and physical
  step counts pass; the two probes end at identical observation hashes/state.
- All four H264/yuv420p videos fully decoded, nonblank and moving, with exactly
  one initial frame plus one per executed action. See `first_case_media_audit.json`.
- Object optical flow (0.765,-7.015) and EEF projection (0.845,-7.122) now use
  the same orientation. The verifier abstained due to the frozen confidence
  guard. This technical observation is not evidence of improved task SR.

Smoke is separate from the 192-branch mechanism screen. A 192-branch held-out
init stage starts automatically only after the frozen screen gate. Maximum
12 hours from launch, including waiting for idle GPUs. The remote dispatcher
is detached from SSH/WSL and persists logs and committed branches.

Live status (on the server from the project root):
```bash
.venv-cosmos/bin/python scripts/run_probe_repair.py --status
```

This file records launch checks, not the live completion status. Use
`sequence_status.json` and the per-phase analyses for subsequent progress.

At 22:50:58 MSK all 24 smoke branches passed the complete-case artifact and
shared-probe replay audit; the dispatcher advanced to `screen`. Four cases
executed probes: two `miss`, one `held`, one `unknown`. Thus both repair and
abstention paths were exercised in real simulation. Smoke has only one init
per cell: its degenerate stratified bootstrap intervals are not scientific
inference and its outcomes are not included in screen/holdout SR.

At 22:51:36 MSK three screen workers were active: GPU1 PID40680,
GPU3 PID40674, GPU6 PID40677. Each has a batch of four exact-state jobs.

# Timing / Eligibility: Launch Verification

Verified September 11, 2026 at 14:01 MSK. This is a technical record, not a
claim that the new recovery policy improves success rate.

## Frozen Run

- Campaign: `timing_eligibility_20260911_v2`.
- Config SHA256: `2b37ed40ac413a3445b73ad09ebb21a4f0e1784df3e223b6f9826b1a06cd17dd`.
- Dispatcher PID: `683261`, detached launch at 13:54:59 MSK.
- Original deadline retained: September 11 at 19:45:34 MSK, epoch `1789145134.942116`.
- Science: five policies, 12 fixed cells, init46-49, two seeds, 480 prospective branches.
- Technical smoke: two saved prefixes, five policies, ten branches; not new independent evidence.
- No threshold tuning, training, seed search, or automatic holdout/confirmation.

## Technical Correction

The first campaign was stopped before the screen after exact replay diverged.
Its nine committed smoke branches, configuration, logs, and source archive
remain in `../timing_eligibility_20260911/`. They are excluded from the new SR.

The model loader changes cuDNN flags. Fresh prefix generation reapplies
`set_seed_everywhere`; a cached prefix returned before that call. V2 explicitly
reapplies the same seed and deterministic cuDNN mode after model loading,
before either prefix path. No tolerance, checkpoint, scientific setting,
reference trajectory, or deadline was changed to pass the test.

## Verified Checks

- 77 CPU tests passed locally and on the server, including a cached-prefix regression check.
- All 40 position-variant asset files have 50 initial states, including indices46-49.
- Smoke completed10/10; no missing cases.
- Six old controls matched exactly in executed actions, final simulator state, and signals.
- Four common-delay state/observation/action checks passed.
- Three equal-decision full-trajectory checks passed.
- Artifact hashes, query seeds, finite actions, physical budget, gate routing,
  and recorded-frame accounting passed the server analysis and its local rerun.
- All ten MP4 files decoded; expected frame counts matched. Each frame is
  256x512 RGB, containing two cameras. First/last frames were nonblank.
- Videos are suffixes starting at physical t72, not full reset-to-terminal videos.

## Main Run Admission

After the smoke gate, the dispatcher automatically entered `screen`.
Actual CUDA process paths were checked, not only scheduler PID existence:

| Physical GPU | Own Worker PID |
|---|---:|
| 1 | 694708 |
| 2 | 694720 |
| 3 | 694717 |
| 4 | 694711 |
| 5 | 694714 |
| 6 | 694723 |
| 7 | 694705 |

GPU0 remained occupied by an unrelated process and was not used. These PIDs
are a launch snapshot: the dispatcher replaces workers between batches.
Idle-only admission, own-worker deadline handling, and completed-artifact
resume checks remain enabled. No scientific conclusion is based on the
technical replay outcome or on a partial screen.

## Outputs

[Protocol](../../TIMING_ELIGIBILITY_PROTOCOL_20260911.md),
[smoke audit](analysis/smoke/RESULTS.md), [smoke videos](analysis/smoke/videos.html).

The complete prospective analysis will be generated automatically in
`analysis/screen/` on the server. Local copies are snapshots, not live status.
Run `scripts/run_timing_eligibility.py --status` with the project Python on
the server for the current phase, counts, GPU assignments, and deadline.

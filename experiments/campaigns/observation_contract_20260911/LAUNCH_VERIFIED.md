# Observation Contract: Verified Launch

September 11, 2026, 20:40 MSK. This is a launch/integrity record, not evidence
that the new controller improves task success.

## Frozen Study

- Dispatcher PID: `1289972`, detached at 20:23:49 MSK; parent PID1 verified.
- Campaign: `observation_contract_20260911`.
- Config SHA256: `775a3b3425a1e986e5e8426538212b76a4364c91ca84eefdfb232e4b2dedf0e0`.
- Deadline: September12, 04:23:50 MSK, epoch `1789176230.370088`.
- Budget persists across resume; no automatic extension or holdout.
- Technical phase: 24 branches, completed and passed.
- Main phase: 1536 planned branches; 3 committed at 20:39:57 MSK.
- 96 existing t72 prefixes, 48 init clusters, two suffix seed streams,
  eight arms. Not 192 independent initial states or a fresh holdout.
- Two oracle arms use privileged target poses and are diagnostic only.

## Checks Passed

- 180 CPU tests locally and on the server, including 47 new-method tests.
- All 80 prepared position BDDL/init assets hash-checked against sources;
  batches do not rewrite the full NFS2 volume.
- Six old controls reproduced exactly: actions, final state, safety signals.
- Four full-trajectory checks preserved the baseline on an initially eligible case.
- Four matched probe state/observation/action checks passed.
- Branch provenance, source hashes, seed streams, finite actions, physical
  step budget, routing and frame accounting passed the server analyzer and
  a separate local rerun. No replay tolerances were relaxed.
- All 24 smoke videos decoded: 3127 frames, counts matched metadata.
- First/last frames of both cameras are nonblank, resolution256x512 RGB.
- Videos start at physical t72, not reset. Smoke SR is not research evidence.
- No threshold or policy modification was made after observing smoke labels.

41 frozen source files are saved in [frozen_scripts.tar](frozen_scripts.tar).
Every member matches the config hash. Archive SHA256:
`6cda69ee90311af99a471751404956a740b25777429cae3de85b90238c9bc826`.

## Actual Main Workers

The dispatcher entered `screen` after the complete smoke gate. CUDA allocations
and command lines were verified, not just scheduler process existence:

| Physical GPU | Worker PID |
|---|---:|
| 0 | 1316935 |
| 1 | 1316938 |
| 2 | 1316931 |
| 3 | 1316934 |

Each worker held about7214MiB at the check. GPU4-7 were occupied by other
projects and were not used. Admission remains idle-only over0-7, max7 workers.
PIDs change between batches. `waiting_for_idle_gpu=true` can coexist with
four active workers: it describes additional workers waiting, not a stalled run.
No foreign process was stopped or reconfigured.

The initial ETA includes the mostly serial technical phase and is not a
reliable estimate of the four-GPU main phase. The previous controls averaged
about44.6s/branch; 1536 branches at that speed on four GPUs would take4.8h,
excluding setup and changes in trajectory length. Completion before the
deadline is not guaranteed; partial results remain recoverable.

## Storage Recovery

NFS2 was completely full before launch. New outputs are written through the
canonical campaign path to a dedicated, persistent NFS-home directory:
`/home/jovyan/.local/share/malnev_world_model_spill/observation_contract_20260911`.
That volume had about2TB free. Code, environment and old experiments remain
in the canonical project. No previous experiment artifact was deleted.

Only an unused T5 backup was moved to the same spill area, hash-verified,
and replaced by a symlink. The active T5 file was unchanged. Details and
checksum are in the [protocol](../../OBSERVATION_CONTRACT_PROTOCOL_20260911.md).
The first file-transfer attempts failed before the move; no GPU campaign
started on the full volume and no new scientific data were lost.

## Where to Look

[Protocol and hypotheses](../../OBSERVATION_CONTRACT_PROTOCOL_20260911.md),
[prior geometry audit](prior_audit/README.md),
[smoke integrity summary](analysis/smoke/summary.json),
[smoke video gallery](analysis/smoke/videos.html).

Main scores, paired effects, plots and video gallery will be generated under
`analysis/screen/` on phase completion. Local files are downloaded snapshots,
not live status. Run from WSL:

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/run_observation_contract.py --status'
```

No next campaign or independent confirmation is automatically launched.
After completion, compare harms and oracle gaps before changing the method.

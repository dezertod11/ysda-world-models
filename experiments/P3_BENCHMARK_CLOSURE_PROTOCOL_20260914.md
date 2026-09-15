# One-day closure: P3 on common LIBERO-PRO support

Prepared 14 September 2026 following the user's request to complete the evidence
within one day. [Latest completed results and scientific conclusions](RECOVERY_FINAL_RESULTS_20260914.md).

## Priorities

1. Close and document confirmation/geometry/oracle results already computed.
2. Fill the missing P3 Object / Environment / Position / Macro-SR / Success199
   row with a full paired transfer evaluation and contemporaneous controls.
3. Evaluate one simple observation-triggered recovery adaptation, preserving
   the existing perception module and physical primitive.
4. Produce checked tables, paired effects, query metrics and all rollout videos
   automatically. Freeze these results before any further method adjustment.

We do not select thresholds or publish a winner based on partial SR. The most
valuable scientific result can also be a clearly measured transfer limitation.

## Benchmark and sampling

Support comes directly from the max-value rows in the completed valid199
episode manifest:50 Object,50 Environment,99 Position cases; all10 Object-suite
tasks. The same upstream empty y0.5/task1 init asset stays excluded for all arms.
Environment uses the existing hashed replacement init assets; Position uses all
ten x/y levels. Commands and asset SHA256 are checked before execution.

All five arms are newly executed from the same saved initial runtime state.
The source task/init/rollout seeds are retained. Policy candidates use
`rollout_seed + query_index * 1000 + candidate_index`. Exact equal-input pools
can be reused across arms; query inputs and seeds must both match. Prefix equality
and passive-monitor parity are tested. Initial candidate0 defines the K1 arm.

This is a new paired collection on historically inspected support, **not an
untouched holdout**. It must not be joined with the old selector table as though
the old and new separate processes were an identical common-pool experiment.
Contemporaneous controls are included to quantify this difference.

## Arms

| Arm | Definition |
|---|---|
| `first_k1` | One candidate, generate16/execute16; no selection |
| `max_value_h16` | K4 max-value, execute16 throughout |
| `h8_at72` | Same H16 prefix; fresh query at72 and execute8 afterward |
| `p3_at72` | Historical RGB gate and physical regrasp at72; execute8 afterward |
| `p3_event` | Observe every4actions; persistent missed grasp after close near the estimated target; same RGB gate/regrasp; execute8 after intervention |

`p3_at72` is a historical control needed to fill the missing benchmark result.
The new event decision contains no absolute episode step or task-specific timer.
It uses the existing mask-based motion verdict, a close-near-target memory,
two consecutive miss detections and the existing geometry gate. Held/unknown
does not authorize release. Only one recovery is permitted. Uncertainty is
logged; a high value/action std cannot consume the physical recovery allowance.
The event variant is exploratory, with development thresholds inherited before
this run. There is no new learned fail predictor or calibrated failure probability.

The policy checkpoint is unchanged: Cosmos2B, K4 except K1, five denoising steps,
parallel/joint action/future/value prediction. It is not autoregressive a->s->v
planning. All280 physical steps, including recovery, count against one budget.
Failed post-retreat checks keep the physically reached state. Unsupported
localizer targets use the declared no-recovery fallback, not fake coordinates.

## Integrity and promotion

Two technical cases cover familiar x0.2/task5/init25 and transfer x0.3/task1/init25.
Each runs five arms plus passive shadow:12 rollout, outside benchmark SR.
Checks include namespace-package source resolution, exact passive action/state
parity, common historical prefix, selected-action accounting, frame counts,
decoded videos, artifact hashes and fallback parity. Main starts only if both pass.
Main has199cases x5arms = **995 rollout**. Each case is scored only after all five
arms and its audit finish. Interrupted episodes are pending, never failures.

## Metrics and statistics

Primary: factor-macro terminal success. Factor SR is mean success over its
frozen cases; the three factors have equal weights:

$$
\mathrm{MacroSR}=\frac{\mathrm{SR}_{O}+\mathrm{SR}_{E}+\mathrm{SR}_{P}}{3}.
$$

Also report success/199 (micro numerator), per-factor/task SR, paired rescue and
harm, full-episode drop/wrong-object proxies, logical samples/model calls and
intervention frequency. All videos contain both cameras and every executed action.
Cached runtime is not a fair standalone latency comparison; logical costs are
reported explicitly. Collection does not terminate on these diagnostic proxies.

Four prespecified contrasts: P3fixed-H16, P3fixed-H8, P3event-H16, P3event-P3fixed.
Use5000 stratified bootstrap resamples of task/init clusters inside each factor;
Position levels within a task/init remain together. Report macro delta and95%CI.
Cluster sign-flip testing uses20000draws, `(extreme+1)/(draws+1)` and Holm correction
across the four contrasts. Inference is withheld until all199cases are complete.
Task support is fixed; this is not a population guarantee for unseen tasks.

Query uncertainty logs retain pre-query action-prefix std, value std/range,
latent dispersion and matched temporal overlap when horizons overlap. Outcome
labels serve evaluation only. Any new classifier fit requires a separate split;
episode-wide maxima after failure are not early prediction evidence.

## Resources and outputs

Idle-only GPU0-7, shared project locks, at most one worker per GPU; no eviction
or shared-GPU oversubscription.22hours from launch, leaving time for analysis and
transfer within the user's day. Deadlines are not silently renewed on restart.
The detached queue survives SSH/local-PC disconnects; stage errors stop promotion.
Completed cases are validated and reused on resume. The actual duration depends
on GPU availability and measured throughput.

Preparation/launch commands used on the server (already prepared; do not repeat
`--prepare` on the existing campaign):

```bash
.venv-cosmos/bin/python scripts/run_p3_benchmark.py --prepare --hours 22
.venv-cosmos/bin/python scripts/run_p3_benchmark.py --launch
.venv-cosmos/bin/python scripts/run_p3_benchmark.py --status
```

Campaign: `experiments/campaigns/p3_benchmark_closure_20260914_v3/`.
The initial technical attempt stopped before outcomes: the namespace contained
both the archived and editable policy trees. V2 resolves the actual imported
`cosmos_utils` module and checks that it belongs to the frozen runtime.
The failed technical config/logs remain under the unsuffixed campaign name.
V2 also stopped before outcomes because the runtime is symlinked: the assertion
compared resolved and unresolved paths. V3 resolves both sides. Neither technical
failure is a failed robot episode or enters the scientific scores.
Outputs: `analysis/RESULTS.md`, `benchmark_table.csv`, `factor_scores.csv`,
`paired_effects.csv`, `episode_outcomes.csv`, `query_metrics.csv`,
`factor_success_rates.png`, `videos.html`. Progress lives in`sequence_status.json`;
the final table is authoritative only when`complete=true`.

From the local WSL project root:

```bash
bash scripts/sync_p3_benchmark.sh --status
bash scripts/sync_p3_benchmark.sh
bash scripts/sync_p3_benchmark.sh --videos
```

The first command reads current remote status. The second downloads compact
results, and the third also downloads videos. Raw NPZ and frozen source archives
remain on the server. During smoke, `completed_rollouts` is zero because that
counter refers only to the 995 main rollout targets. `stage` distinguishes this
from the main experiment. Analysis runs automatically after the stage, or when
the deadline is reached; a partial collection is labelled incomplete.

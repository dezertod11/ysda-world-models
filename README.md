# YSDA World Models: Uncertainty-Aware Planning

**Joint paper, 15 September 2026:**
[ICRA manuscript (PDF)](publication/joint2027/build/icra2027.pdf),
[portable LaTeX sources](publication/joint2027/build/joint_paper_sources.zip),
[paper workspace and build instructions](publication/joint2027/README.md).
The joint article separates cross-model consensus results from Cosmos feedback
and recovery studies. [Scoped runtime-v2 replication protocol](experiments/publication_finish_20260915/PROTOCOL.md)
documents the new overnight experiments; pending runs are not completed evidence.

**September 13 follow-up launched:**
[Frozen recovery resume and grounding diagnostic protocol](experiments/RECOVERY_GROUNDING_DIAGNOSTIC_PROTOCOL_20260913.md).
Finish missing main/timing outcomes; separately audit32prefixes,128matched
RGB/oracle outcomes and4event-shadow controls. Idle-only shared GPU locks,
cutoff21:12MSK. Oracle scores are privileged diagnostics, not deployable gains.

**Publication results hub (12 September 2026):**
[All project results and analysis](publication/iclr2027/RESULTS_AND_ANALYSIS.md),
[related-work results and protocol differences](publication/iclr2027/RELATED_WORK_RESULTS.md),
[local source catalog](publication/iclr2027/RESULTS_INDEX.md).
Includes positive, negative, conditional and pending evidence; historical
run-status entries below are not a live queue monitor.

Research project on uncertainty estimation and risk-aware action selection for
Cosmos Policy in LIBERO and LIBERO-PRO.

Publication workspace: [ICLR 2027 manuscript, writing plan, and reference papers](publication/iclr2027/README.md).

The central question is whether stochastic and latent uncertainty can identify
an unreliable action chunk before execution and improve the standard
`argmax(value)` planner in out-of-distribution manipulation tasks.

## Current result

September 12: both night studies completed and reviewed.
[Observation Contract, 1536/1536 branches](experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md):
primary145/192 vs physical recovery151/192, NO-GO. Preserve-only161/192 is
a post-hoc local lead; unnecessary regrasp caused sixteen paired losses
after the object was already moving with the gripper.
[Decoder-medoid, 1440/1440 rollouts](experiments/DECODER_MEDOID_RESULTS_20260912.md):
H16 decoder and max-value both112/180 (62.22%); fixed-seed/H8 controls do not
establish a gain. Reports include every arm, formulas, intervals and videos.
Completed01:48/07:31MSK respectively. No new GPU experiments launched in this review.
The launch/status entries below are historical.

Night plan September 11-12: [deadline-bounded decoder-medoid checks](experiments/DECODER_MEDOID_NIGHT_20260912.md).
Preserve the 720-rollout main comparison, then 360 fixed-seed controls and up
to 360 H8 controls. Idle-only GPUs 0-7 after Observation Contract; compute cutoff
09:40 MSK, reports before 10:00 MSK September 12. Absolute deadline, owned-process
watchdog, no automatic extension. Full coverage depends on available resources.
[Verified night launch](experiments/campaigns/decoder_token_medoid_20260911/NIGHT_LAUNCH_VERIFIED.md).

Queued September 11, 21:35 MSK: [decoder action-token medoid transfer](experiments/DECODER_TOKEN_MEDOID_PROTOCOL_20260911.md)
from Robotics_project_YSDA. Four selectors, K3/H16, 720 paired full rollouts
across LIBERO-PRO Object, Environment and Position. Local read-only hook parity
and four full integration rollouts passed; 70 tests pass locally/on the server.
The autonomous dispatcher waits for Observation Contract to drain, then admits
only idle GPUs. No transfer gain is claimed yet.
[Verified launch and local validation](experiments/campaigns/decoder_token_medoid_20260911/LAUNCH_VERIFIED.md).

Running since September 11, 20:23 MSK: [Observation Contract protocol](experiments/OBSERVATION_CONTRACT_PROTOCOL_20260911.md).
Eight arms separate observation motion, gripper preservation, recovery, and
privileged localization diagnostics. Planned: 24 strict replay checks, then
1536 branches on 96 existing prefixes with two suffix seeds. This is a
development mechanism study, not a new-init holdout or a demonstrated gain.
180 CPU tests passed locally and on the server. [Launch and storage record](experiments/campaigns/observation_contract_20260911/LAUNCH_VERIFIED.md).

Latest completed study: [timing versus renewed eligibility, results and videos](experiments/TIMING_ELIGIBILITY_RESULTS_20260911.md).
Finished September 11 at 15:09 MSK: 10 replay + 480 prospective branches,
96 paired states across 12 known Position cells, init46-49. Continue 63/96,
immediate regrasp 76/96, delayed-fresh and checked-latched 74/96,
diagnostic-latched 76/96. The new candidate did not beat immediate recovery;
the frozen gate failed and holdout38-45 stayed closed. Immediate vs continue:
+13.54 pp, 16 rescues / 3 harms, Holm p=.17046, not a new corrected-significant claim.
The diagnostic restores three cancelled juice recoveries but harms another
case with just a three-step retreat. All 17 cases failing under all policies
never passed the original gate: recovery was not tested on them.
All 490 videos downloaded and decoded, 59,174 frames; 79 CPU tests pass.
[Selected comparison videos](experiments/campaigns/timing_eligibility_20260911_v2/review_20260911/selected_videos.html).
The subsequent campaign above checks non-opening observation motion and
trigger coverage; passive/two-view verification remains a later option.

Previous study: [object-grounded verification and delayed recovery, results and videos](experiments/GROUNDED_PROBE_RESULTS_20260911.md).
All 576 branches finished September 11 at 03:56 MSK (48 smoke, 384 screen,
144 transfer); the frozen screen gate failed, so no conditional holdout ran.
Conservative mask: 35/48, identical outcomes to probe-then-always-regrasp,
versus full regrasp 33/48 and continue 27/48. The mask removed ten observed
false-held decisions, mostly by abstaining, without establishing an added
controller benefit. On transfer, full regrasp scored 36/48; delayed and
continue both scored 33/48. Next diagnostic: separate delay from renewed
trigger eligibility; do not promote this mask or fixed delay as a proven gain.

Previous result: [Probe → Verify → Repair, 192/192 screen branches](experiments/PROBE_VERIFY_REPAIR_RESULTS_20260911.md).
The verified method scored 30/48 (62.50%), below physical regrasp 35/48
(72.92%); continue and probe-only both scored 26/48. The frozen screen gate
failed and the conditional holdout was not opened. A post-hoc audit found
seven false `held` decisions with a stationary target and no target contact;
the tracking crop can follow the gripper instead of the object. Next priority
is object-specific verification and a probe-then-always-regrasp control,
not a larger sweep of the same verifier. [Videos and frame comparison](experiments/campaigns/probe_verify_repair_20260910_v2/analysis/screen/videos.html).

Earlier completed campaigns: [P5 replication (690 branches) and matched-K feedback (120 branches)](experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md).
One frozen state has a reproducible max-value selection error (1/10 vs 10/10);
the neighboring-state diagnostic did not establish transfer. Matched-K fresh
feedback and continuity did not improve pooled success.
[Research priorities and subsequent screen decision](experiments/RESEARCH_PRIORITIES_20260910_EVENING.md).
The entries below describe earlier completed studies, not live queue status.

Latest completed audit: [P5 suffix repeats and feedback, 1,080 branches](experiments/P5_REPEAT_FEEDBACK_RESULTS_20260910.md).
Fresh8 did not improve the pooled outcome (41/108 vs. open16 44/108).
One third of saved candidates changed outcome across suffix seeds; the K8
in-sample oracle gain vanished under a held-out-suffix diagnostic. This is
a development mechanism study, not a new full-episode planner benchmark.

- Standard LIBERO ID control: 72/72 successful rollouts.
- LIBERO-PRO screening: 82/106 successful rollouts and seven mixed
  success/failure configurations.
- Full validation: 23 jobs, 1078 strategy executions and 13351 policy queries.
- LIBERO-Safety physical evaluation is complete: 144/144 rollouts, zero task
  successes and four official safety violations.
- On selected boundary cases, adaptive `requery_l1_h8` improved success from
  146/240 (60.8%) to 161/240 (67.1%) at 1.27x normalized query cost.
- On the broader 897-episode LIBERO-PRO Object pilot, that gain did not
  transfer: no planning scored 52.8%, `max(value)` 54.5%, and risk-aware
  adaptive requery 52.1%. The current research focus is therefore grounded
  candidate evaluation and selective feedback timing, not another static
  uncertainty penalty.
- A frozen future-proprio error surrogate transferred as a physical prediction
  error estimator (case-controlled Spearman 0.579, top-quartile AUROC 0.731),
  but its gated planner did not improve task success.
- The frozen shared-prefix Object task-0 experiment passed all confirmatory
  gates: query-4 real-observation feedback improved terminal SR from 46/100 to
  64/100, +18 pp with init-cluster 95% CI [+4, +32], 31 rescues / 13 harms and
  McNemar p=0.00956. All 100 exact-state replays passed integrity.
- The frozen cross-factor development screen passed integrity (97/100 strict)
  and identified Position `y0.2` as the next confirmatory boundary: 40% -> 80%,
  +40 pp, 95% CI [+10, +65], 10 rescues / 2 harms. Position `x0.2` was negative
  (20% -> 15%) and is retained as a preregistered control rather than hidden by
  pooled reporting.
- The independent Position-direction holdout passed integrity (120/120 strict)
  but did not replicate that screen signal. At `y0.2`, commit and feedback were
  53.3% and 55.0%: +1.7 pp, 95% CI [-13.3, +16.7], 10 rescues / 9 harms,
  McNemar p=1.0 and -0.8 pp after query cost. The `y0.2 - x0.2` interaction was
  0 pp. Fixed cross-factor feedback is therefore not promoted.
- The subsequent frozen invariant-CATE router also failed its prospective
  reserve holdout despite complete 400/400 replay integrity. Commit/router SR
  was 57.0%/55.75% with 39.5% queries; adjusted gain was -2.24 pp, 95% CI
  [-5.52, +1.13], and rescue-vs-harm AUROC was 0.544. Selective routing was
  +8.01 adjusted pp better than always re-query, but still worse than commit;
  this closes the global relative-feature router and motivates explicit
  object/contact/perturbation interaction modeling.
- The follow-up P2c object/contact screen reused 640 strict paired states and
  extracted frozen CLIP patch relations from current and predicted RGB. The
  best object model had -1.28 pp worst-split adjusted uplift versus -0.50 pp
  for the relative control, with every cluster interval crossing zero. Partial
  contact detection did not transfer to causal feedback selection, so this
  formulation is closed without a new holdout.
- A privileged P2d upper bound then supplied task identity, perturbation
  geometry and manipulation phase explicitly. It worked within known cells
  (+2.78 pp adjusted, AUROC 0.812) but failed leave-task/level/cell transfer
  (-0.19/-0.19/+0.13 pp; all transfer AUROCs below 0.5). This closes the
  re-query CATE branch and shifts the next gate to recovery proposal coverage.
- The frozen P3 recovery opportunity campaign completed all 240/240 strict
  exact-state branches. Frequent H4 re-query rescued 7/80 and blind lift/hold
  rescued 8/80 but neither passed its frozen gate. A diagnostic regrasp using
  true simulator object pose rescued 62/80 and strictly covered every state
  rescued by either deployable heuristic. This localizes the next bottleneck
  to perception-backed contact recovery rather than another scalar reranker.
- P3b now uses a strict RGB calibration split with zero downstream group
  overlap. A CLIP patch head failed localization; a dense DeepLab heatmap cut
  grouped-OOF pixel p90 from 41.65 to 4.12 px. Object-routed metric depth then
  passed the unchanged offline gate at 1.64/3.33 cm median/p90 XY. A clean
  screen after fixing the raw-camera orientation contract rescued 11/20 states
  across six cells and four tasks. Full development then rescued 49/80 (61.25%,
  cluster CI [50.62%, 71.43%]) with 100% replay integrity and no drop/safety
  increase. The one-shot strict new-group reserve confirmed 43/72 (59.72%, CI
  [45.20%, 73.91%]) across 11 cells and eight tasks. The formal gate passed;
  increased wrong-object flags motivate an observable trigger and shield.
- P3c then tested that frozen mechanism online on complete LIBERO-PRO Position
  episodes. Its untouched 40-case holdout improved terminal SR from 13/40
  (32.5%) to 24/40 (60.0%): **+27.5 pp**, paired 95% CI [+12.5, +42.5],
  12 rescues / 1 harm and exact McNemar p=0.00342. All 40 shared snapshots
  replayed exactly; target-drop and official-safety rates did not increase,
  while wrong-object interactions fell by 7.5 pp.
- P3d completed 75/75 development cases and 225/225 exact-state branches.
  Full regrasp replicated strongly on known cells (15.0% -> 62.5%), but its
  seven-new-cell estimate of 74.3% -> 88.6%, +14.3 pp, had 95% CI
  [-2.9, +31.4] and 7/2 rescue/harm. The frozen development gate therefore
  returned **NO-GO** and did not open holdout. Retreat-only reached 80.0% on
  new cells; full regrasp beat it clearly overall but not conclusively on the
  new-cell subset.
- P3e froze a three-head Recovery Outcome Ensemble before opening the untouched
  init 45--49 holdout. All 75 cases and 225 branches passed replay, feature and
  fallback integrity. The router improved full RGB regrasp from 53/75 (70.7%)
  to 55/75 (73.3%): **+2.7 pp**, cluster CI [0.0, +6.7], 2 rescues / 0 harms,
  while reducing drop proxies from five to three and primitive cost. Both
  rescues replicated the preregistered `x0.2/task2` failure mode on new init
  states; the frozen practical gate passed, although McNemar p=0.5 and the
  same-cell design make this a preliminary narrow result.
- P4 completed 5,668 action-conditioned residual transitions and five
  independently initialized Gaussian heads. The preregistered quadratic JRD
  collapsed to zero on every row, so pooled OOD balanced AP was 0.308 and the
  residual correlation was undefined. The frozen gate returned **NO-GO** and
  closed-loop filtering was not launched. A post-hoc ablation retained one
  useful lead: independent mean disagreement tracked realized residual error
  with trajectory Spearman 0.609, but transfer was Environment-specific.
- P4b completed its prospective 200-snapshot / 800-branch holdout with
  **NO-GO**. Frozen residual risk reduced realized H16 model error by 2.14%
  but reduced terminal SR from 58.5% to 56.5% (CI [-5.5, +1.5] pp), with
  4 rescues / 8 harms. Global failure AUROC 0.650 collapsed to 0.509
  within heterogeneous candidate pools: residual uncertainty measures state
  difficulty, but does not reliably rank actions from the same state.

The current staged research plan is documented in
[`experiments/RESEARCH_ROADMAP_20260820.md`](experiments/RESEARCH_ROADMAP_20260820.md).
The causal Object task-0 feedback-timing P0 is retained as a positive control,
while fixed cross-factor transfer P1, absolute signed-VoF P2 and invariant-CATE
P2b, frozen-CLIP P2c and privileged-context P2d are closed after their
respective transfer failures. P3c remains the first confirmed deployable
online recovery controller, while P3e adds a frozen, low-cost selector that
prevented two repeated full-regrasp harms on new initial states. P3d/P3e still
do not establish broad unseen-cell transfer. P4/P4b close direct
residual-divergence penalties for candidate selection, while retaining
residual risk as a state-level OOD and compute-allocation signal. The next
candidate-level method must learn task-critical terminal advantage inside
exact-state pools and use a conservative switch gate.

## Repository layout

```text
articles/             Paper PDFs and literature review
configs/              Local experiment configuration
experiments/          Protocols, compact results and plots
patches/              Reproducible changes over pinned upstream projects
scripts/              Setup, rollout and analysis commands
ysda_world_models.ipynb
ysda_world_models_research.ipynb
```

Large raw traces, videos, model checkpoints, environments and downloaded assets
are intentionally excluded from Git. They remain in the local/server experiment
storage and can be regenerated from the committed configs.

## Restore source checkouts

The modified third-party projects are represented as patches over pinned public
commits. From the repository root:

```bash
./scripts/bootstrap_source_checkouts.sh
```

This creates:

- `cosmos-policy` at NVIDIA commit
  `18a2accadf4e7a3531e56754102af5a24d2316da`;
- `LIBERO-PRO` at commit
  `eafdb809426b13153aa1e4c42d6601844217dfec`;
- all local policy, uncertainty, VFD, safety and OOD-task modifications.

The script refuses to overwrite existing checkouts.

## Environment

For the MLSpace server workflow, see
[`SERVER_MLSPACE_RUNBOOK.md`](SERVER_MLSPACE_RUNBOOK.md). After restoring the
source checkouts:

```bash
bash scripts/setup_mlspace_cosmos.sh
source scripts/cosmos_env_libero_pro.sh
```

LIBERO-Safety uses a separate environment:

```bash
bash scripts/setup_mlspace_libero_safety.sh
```

## Main entry points

- Current research roadmap:
  [`experiments/RESEARCH_ROADMAP_20260820.md`](experiments/RESEARCH_ROADMAP_20260820.md)
- Latest confirmatory result:
  [`experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md`](experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md)
- Latest cross-factor screen:
  [`experiments/OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md`](experiments/OBJECT_Q4_CROSS_FACTOR_BOUNDARY_SCREEN_RESULTS_20260902.md)
- Latest cross-factor holdout:
  [`experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md`](experiments/OBJECT_Q4_POSITION_DIRECTION_HOLDOUT_RESULTS_20260902.md)
- Latest invariant-CATE holdout:
  [`experiments/INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md`](experiments/INVARIANT_CATE_RESERVE_HOLDOUT_RESULTS_20260903.md)
- Latest object/contact VoF screen:
  [`experiments/OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md`](experiments/OBJECT_CONTACT_VOF_DEVELOPMENT_RESULTS_20260903.md)
- Latest context-interaction upper bound:
  [`experiments/CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md`](experiments/CONTEXT_INTERACTION_UPPER_BOUND_RESULTS_20260903.md)
- Completed P3 recovery result, protocol and run record:
  [`experiments/RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md`](experiments/RECOVERY_PROPOSAL_OPPORTUNITY_RESULTS_20260904.md),
  [`experiments/RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md`](experiments/RECOVERY_PROPOSAL_OPPORTUNITY_PROTOCOL_20260904.md),
  [`experiments/RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md`](experiments/RECOVERY_PROPOSAL_OPPORTUNITY_RUN_20260904.md)
- Completed P3b perception protocol and confirmatory results:
  [`experiments/PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md`](experiments/PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md),
  [`experiments/PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md`](experiments/PERCEPTION_REGRASP_DEVELOPMENT_RESULTS_20260904.md)
- Completed P3c online trigger protocol and result:
  [`experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md`](experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_PROTOCOL_20260904.md),
  [`experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md`](experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md)
- Completed P3d new-cell transfer and mechanism ablation:
  [`experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md`](experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_PROTOCOL_20260905.md),
  [`experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md`](experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md)
- Completed P3e frozen Recovery Outcome Ensemble holdout:
  [`experiments/P3E_RECOVERY_OUTCOME_ROUTER_PROTOCOL_20260906.md`](experiments/P3E_RECOVERY_OUTCOME_ROUTER_PROTOCOL_20260906.md),
  [`experiments/P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md`](experiments/P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md)
- Completed P4 residual-dynamics screen (**NO-GO** for quadratic JRD):
  [`experiments/P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md`](experiments/P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md),
  [`experiments/P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md`](experiments/P4_RESIDUAL_DYNAMICS_RESULTS_20260906.md),
  [`experiments/P4_RESIDUAL_DYNAMICS_RUN_20260906.md`](experiments/P4_RESIDUAL_DYNAMICS_RUN_20260906.md)
- Completed P4b residual-risk experiment (**NO-GO**):
  [`experiments/P4B_RESIDUAL_RISK_PROTOCOL_20260907.md`](experiments/P4B_RESIDUAL_RISK_PROTOCOL_20260907.md),
  [`experiments/P4B_RESIDUAL_RISK_RUN_20260907.md`](experiments/P4B_RESIDUAL_RISK_RUN_20260907.md),
  [`experiments/P4B_RESIDUAL_RISK_RESULTS_20260907.md`](experiments/P4B_RESIDUAL_RISK_RESULTS_20260907.md)
- P3e exact-prefix diagnostic videos:
  [`experiments/campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html`](experiments/campaigns/recovery_outcome_router_diagnostic_videos_20260906/diagnostics/VIDEO_INDEX.html)
- Selected P3b learned/privileged mechanism videos:
  [`experiments/campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html`](experiments/campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html)
- Same-query reproducibility diagnostic:
  [`experiments/COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md`](experiments/COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md)
- Frozen next-stage protocol:
  [`experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](experiments/GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md)
- Exact-state P1/P2 feedback and candidate protocol:
  [`experiments/COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](experiments/COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md)
- Broad LIBERO-PRO Object baseline:
  [`experiments/campaigns/pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md`](experiments/campaigns/pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md)
- Latest surrogate/requery result:
  [`experiments/LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](experiments/LIBERO_SURROGATE_REQUERY_RESULTS.ipynb)
- Latest written analysis:
  [`experiments/SURROGATE_REQUERY_RESULTS_20260820.md`](experiments/SURROGATE_REQUERY_RESULTS_20260820.md)
- Final results notebook:
  [`experiments/LIBERO_FINAL_RESULTS.ipynb`](experiments/LIBERO_FINAL_RESULTS.ipynb)
- Experiment index: [`experiments/README.md`](experiments/README.md)
- Full validation protocol:
  [`experiments/LIBERO_8H_VALIDATION_PROTOCOL.md`](experiments/LIBERO_8H_VALIDATION_PROTOCOL.md)
- Unified results:
  [`experiments/LIBERO_COMPLETE_RESULTS_20260724.md`](experiments/LIBERO_COMPLETE_RESULTS_20260724.md)
- Paper review:
  [`articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](articles/LIBERO_EXPERIMENTS_AND_PAPERS.md)

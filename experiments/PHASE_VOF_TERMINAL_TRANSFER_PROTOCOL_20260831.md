# Phase-aware Value of Feedback: terminal transfer protocol

## Status

Preregistered before collecting outcomes for Environment tasks 5-7 and init
states 10-19. The phase rule, endpoints, split and decision gate below must not
be changed after reading these outcomes.

Compute-only amendment at 16:36 MSK, before inspecting any success/fail
outcome: tasks 6 and 7 were each split into two disjoint init-state shards to
use free GPUs 4 and 5. The first integrity-only run had written 3/1/1 snapshots
for tasks 5/6/7. Those rows are resumed unchanged. The second-shard base seed
is offset by `10 * 97`, preserving the original two-rollouts-per-init seed
sequence. No hypothesis, endpoint, sample, phase cap or gate changed.

Coverage amendment at 17:08 MSK, still before inspecting any success/fail
outcome: task 6 exhausted its first shard with six `approach` snapshots and no
interaction phase. Historical, already completed Environment rollouts on
different init states (5-9) likewise showed zero target contacts for task 7,
versus mean target-contact counts of 8.3 and 60.7 per query for tasks 8 and 9.
Task 6/7 rows are therefore archived as an all-approach feasibility/stress
stratum; they cannot identify a grasp/transport intervention. The final
confirmatory cohort is task 5/8/9 on untouched init states 10-19. This task
replacement is based only on phase/contact support, not current terminal or
dense outcomes. The rule, endpoints and efficacy gate remain frozen.

Final coverage/replay amendment at 17:48 MSK, before opening outcomes: task 8
init 15-19 also exhausted its ten trajectories at six approach-only states.
It is archived with the task 6/7 stress stratum. Task 8 init 10-14 yielded 14
states with phase counts 6/4/4 and is retained. The supported cohort therefore
contains 74 existing states. Replay-only inspection found strict counts
23/30, 13/14 and 28/30 for tasks 5/8/9. Four additional task-5 states are
collected as replay replacements; before collecting them, the final integrity
threshold is frozen at 66/78 overall and 25/34, 12/14, 25/30 by task. No row
is selected or rejected using terminal success, dense VoF, rescue or harm.

## Motivation

The gripper-transition H8/H16 controller failed independent transfer because a
predicted open/close transition is a normal part of manipulation and can fire
before real contact. Existing development exact-state branches show a more
specific Environment interaction:

| Real phase | Development mean dense VoF |
|---|---:|
| approach | -0.0432 |
| grasp | +0.0103 |
| transport | +0.0140 |

This experiment asks a causal question: **is fresh real feedback useful only
after physical interaction has started?** It is an upper-bound mechanism test,
not yet a deployable planner. The phase oracle uses privileged LIBERO geometry
and contact state; a deployable RGB/proprio phase detector is allowed only if
the upper bound transfers.

## Frozen interventions

At one exact simulator state $s$ the same max-value action chunk is used to
construct two coupled branches:

$$
\tau_{commit}(s): a^{maxV}_{0:16},
$$

$$
\tau_{feedback}(s):
a^{maxV}_{0:8}
\rightarrow o_{real,8}
\rightarrow \operatorname{argmax}_i \widehat V(a_i\mid o_{real,8})_{0:8}.
$$

Both branches then continue with the same frozen `max(value)`, K=4 policy and
coupled seed schedule to terminal success or the 280-step limit. The frozen
phase router is

$$
\pi_{phase}(s)=
\begin{cases}
\tau_{feedback}(s), & p(s)\in\{\mathrm{grasp},\mathrm{transport}\},\\
\tau_{commit}(s), & p(s)\in\{\mathrm{approach},\mathrm{release}\}.
\end{cases}
$$

No value, uncertainty, task or init-specific exception is used.

## Independent transfer split

| Suite | Tasks | Init states | Target states |
|---|---:|---:|---:|
| `libero_object_env` | 5 | 10-19 | 34 |
| `libero_object_env` | 8 | 10-14 | 14 |
| `libero_object_env` | 9 | 10-14 | 15 |
| `libero_object_env` | 9 | 15-19 | 15 |
| **Total** | | | **78** |

Sampling is phase-balanced. The final caps are 14 states for task 5, six for
task 8, and six inside each task-9 shard. Four run directories execute
independently. Four candidates, five action denoising steps, H16 and parallel
prediction are unchanged from the broad baseline.

To reduce compute without changing the causal comparison, all four candidates
are executed for the matched H16 endpoint, but terminal continuation is run
only for the selected commit branch and the H8-requery feedback branch. This
removes three irrelevant terminal continuations per state.

## Endpoints

For state $s$, terminal feedback effect is

$$
\Delta_T(s)=Y_{feedback}(s)-Y_{commit}(s),
\qquad Y\in\{0,1\}.
$$

Dense local effect is computed from exact H16 endpoint geometry:

$$
\Delta_D(s)=G_{dense}(s_{feedback,16})-G_{dense}(s_{commit,16}).
$$

The routed terminal outcome and compute-adjusted utility are

$$
Y_{phase}(s)=Y_{commit}(s)+I_{phase}(s)\Delta_T(s),
$$

$$
J_c=\mathbb E[Y_{phase}]-c\,\mathbb E[I_{phase}],
\qquad c=0.025.
$$

Primary endpoint is paired terminal success of `phase-router` versus commit.
Secondary endpoints are rescues/harms, dense VoF, intervention rate, per-task
effects, target drop, wrong-object interaction and official safety violation.
Exact McNemar and task/init-grouped bootstrap intervals are reported. Queries
or snapshots from the same task/init are never treated as independent.

## Integrity gate

1. The four supported jobs reach 34/14/15/15 snapshots and both terminal
   branches are available.
2. At least 66/78 states pass replay error $\le 10^{-9}$, with at least 25,
   12 and 25 for tasks 5, 8 and 9 respectively.
3. The strict subset contains at least 15 trigger states from at least ten
   independent task/init groups.
4. Tasks are exactly 5, 8, 9; init states are within 10-19; split is
   `generalization`.
5. Commit and feedback branches use the selected max-value candidate and the
   frozen coupled continuation schedule.

## Frozen efficacy gate

Closed-loop implementation is allowed only if every condition holds on the
strict subset:

1. at least three terminal rescues and strictly more rescues than harms;
2. routed terminal SR improves by at least three percentage points;
3. no task loses more than one net success;
4. mean dense VoF on triggered states is positive and its grouped 95% CI lower
   endpoint is non-negative;
5. routed dense uplift per decision exceeds always-feedback dense uplift;
6. $J_{0.025}$ exceeds commit;
7. integrity passes and no official safety violation is introduced.

Failure closes this privileged phase rule. Success authorizes, but does not
validate, a separate observable phase detector and a new closed-loop holdout.

## Research acceleration decision

This stage is deliberately sequential:

1. exact-state terminal upper bound;
2. observable RGB/proprio phase detector only after a PASS;
3. closed-loop transfer only after detector holdout;
4. semantic consequence model only if phase alone has useful but incomplete
   coverage.

This prevents another large planner grid from being launched before causal
opportunity is demonstrated.

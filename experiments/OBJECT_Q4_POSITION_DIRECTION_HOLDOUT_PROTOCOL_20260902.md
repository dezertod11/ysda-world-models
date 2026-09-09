# Object query-4 Position direction holdout

## Status and purpose

This confirmatory protocol is frozen before any holdout outcome is observed.
The preceding development screen selected Position `y0.2` as the efficacy
cell and Position `x0.2` as the negative direction control. No screen row is
included in this holdout.

The primary question is whether the query-4 real-observation intervention
replicates on untouched official init states at `y0.2`. The hierarchical
secondary question is whether its paired effect is larger at `y0.2` than at
`x0.2`.

## Frozen data

| Condition | Role | Task | Init states | Rollouts/init | Exact-state pairs |
|---|---|---:|---:|---:|---:|
| Position `y0.2` | primary efficacy | 0 | 20-49 | 2 | 60 |
| Position `x0.2` | negative direction control | 0 | 20-49 | 2 | 60 |

Both conditions use official LIBERO-PRO BDDL and init-state files. Six
10-init execution shards allow GPU 2-7 parallelism. Shards do not alter the
estimand: the two rollout seeds from one init state form one bootstrap cluster.
Seed schedules are fixed in the campaign config and are disjoint from the
development screen.

## Shared-prefix intervention

Each pair shares the complete policy prefix, one query-4 four-candidate pool,
the selected `argmax(value)` action and one captured MuJoCo/controller state:

$$
\text{commit}: A_{64:80}^{old},
$$

$$
\text{feedback}: A_{64:72}^{old}\rightarrow o_{72}^{real}
\rightarrow A_{72:80}^{new}.
$$

Both branches then continue with the standard max-value H16 controller until
success or 280 executed actions. Candidate reranking, uncertainty thresholds
and recovery actions are not changed.

## Primary estimand and gate

For pair $i$ in the `y0.2` condition,

$$
Y_i=\mathbb{1}[success_{i,feedback}]
-\mathbb{1}[success_{i,commit}],
\qquad
\widehat\Delta_y=\frac{1}{N_y}\sum_iY_i.
$$

The frozen query-cost adjustment is

$$
\widehat\Delta_{y,adjusted}=\widehat\Delta_y-0.025.
$$

The primary efficacy gate passes only if all conditions hold:

1. the integrity gate passes;
2. $\widehat\Delta_{y,adjusted}>0$;
3. the init-cluster bootstrap 95% CI lower bound for
   $\widehat\Delta_y$ is greater than zero;
4. the exact two-sided McNemar p-value over `y0.2` rescue/harm pairs is below
   0.05.

## Hierarchical direction interaction

Only if the primary gate passes, test

$$
\widehat\Delta_{interaction}
=\widehat\Delta_y-\widehat\Delta_x.
$$

The interaction passes when its matched-init cluster-bootstrap 95% CI lower
bound is greater than zero. This is a hierarchical secondary claim, not an
additional cell selected after reading holdout outcomes.

## Integrity

- All 120 expected `(shard, init_state, rollout_id, rollout_seed)` keys must be
  present and unique.
- Every pair must contain terminal labels, a valid feedback path, four
  candidates and exactly one max-value candidate.
- At least 114/120 pairs and at least 57/60 pairs in each condition must have
  `main_open_replay_state_max_abs <= 1e-9`.
- At least 28 init-state clusters must remain represented in both conditions
  for the interaction analysis.

## Reporting and stopping rule

Report strict and all-pair sensitivity results, per-condition SR, paired
delta, cluster CI, rescue/harm, McNemar p-value, cost-adjusted delta, terminal
time, failure transitions and query count. Save all state/candidate sidecars;
discordant videos may be rendered after labels are finalized.

No threshold, condition, init subset, seed, endpoint or gate may be modified
using holdout outcomes. If the primary gate fails, fixed cross-factor query-4
feedback is not promoted. If it passes but the interaction fails, report
`y0.2` efficacy without claiming direction specificity. Selective-trigger
training remains a later, independently evaluated experiment.

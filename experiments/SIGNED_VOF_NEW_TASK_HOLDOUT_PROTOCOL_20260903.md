# Frozen Signed-VoF New-Task Holdout Protocol

## Hypothesis

A pre-query signed value-of-feedback router trained only on Position `y0.2`,
task 0 can identify states on new LIBERO-PRO Object tasks where query-4
real-observation feedback improves terminal success.

## Frozen intervention

The model artifact, features, ridge weights, `beta=0`, and absolute score
threshold are immutable:

$$
R(x)=\widehat{\mu}_{VoF}(x), \qquad
query(x)=\mathbb{1}[R(x)>0.1401658544].
$$

If the query fires, the controller executes eight actions from the old chunk,
queries the real observation, and executes the first eight actions of the new
chunk. Otherwise it commits to all sixteen old actions. Both branches then use
the same standard Cosmos policy until terminal success or 280 steps.

## Cohort

- Cells: exactly the six cells selected by the frozen baseline-only atlas rule.
- Task IDs: drawn from 1-9; task 0 is prohibited.
- Initial states: 5-24, disjoint from atlas init states 0-4.
- Rollouts: two fixed seeds per init.
- Planned pairs: 6 cells x 20 init x 2 seeds = 240.
- Candidate pool: four stochastic samples, max predicted value is the old plan.
- Pairing: commit and feedback branch from one simulator snapshot in one process.

## Primary estimand

For strict replay pairs,

$$
\Delta_{adj}=
\frac{1}{N}\sum_i
\left[S_i^{router}-S_i^{commit}-0.025\,I_i^{query}\right].
$$

The 95% interval is a 10,000-repetition bootstrap over independent
`(position_level, task_id, init_state_id)` clusters. The model is successful
only if:

1. at least 228/240 pairs pass replay and terminal integrity;
2. raw router success delta is positive;
3. the lower 95% cluster-bootstrap bound for adjusted delta is positive;
4. query rate is at most 60%;
5. the atlas cohort covers at least three tasks and both perturbation directions.

Always-commit, always-requery, oracle-query, per-cell effects, rescue/harm
counts, exact McNemar, score AUROC and query-cost sensitivity are secondary.
No threshold, feature, sign, task exception or query budget may be modified
after feedback outcomes are collected.

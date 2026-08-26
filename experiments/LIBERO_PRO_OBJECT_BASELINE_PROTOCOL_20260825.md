# LIBERO-PRO Object baseline protocol

Status: **completed frozen pilot v0.1**, run on 2026-08-25 and analyzed on 2026-08-26. The benchmark choice is still awaiting the group's final confirmation; do not tune methods on these pilot outcomes.

## Goal

Compare all policies on the same LIBERO-Object tasks and the same OOD initial conditions. The primary result is a success-rate table with one column per requested LIBERO-PRO perturbation:

| Method | Object | Position | Environment | Mean |
|---|---:|---:|---:|---:|
| Mimic-Video | pending | pending | pending | pending |
| Cosmos Policy, no planning | 92.0% | 31.3% | 35.0% | 52.8% |
| Cosmos Policy + max(value) | **98.0%** | **29.6%** | 36.0% | **54.5%** |
| Ours, risk-aware adaptive requery | 93.0% | 25.4% | **38.0%** | 52.1% |

The complete report, confidence intervals, paired comparisons, compute cost, and per-shift Position scores are in [`pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md`](campaigns/pro_object_baselines_pilot_20260825/analysis/benchmark/RESULTS.md).

This is different from our earlier boundary-case experiments. Those experiments intentionally selected difficult tasks, usually held `task/init_state` fixed, and varied stochastic rollout seeds. They were appropriate for causal strategy comparison, but not for a benchmark leaderboard. This protocol covers all ten LIBERO-Object tasks.

## Frozen benchmark

- LIBERO-PRO source commit: `f30530023e6f36f42079da1cacdde44b0b2963fe`.
- Cosmos Policy source commit: `4b71de242fb4bc5f8a67520d187e190c9b63666d` plus `patches/cosmos-policy-ysda.patch` SHA-256 `239914eb058ae940f8c3d4c44b4d6d385e5de56993c529400c3f7cbec539cf5c`.
- Base task family: all task ids `0..9` from LIBERO-Object.
- Episode horizon: 280 environment steps, matching the official Cosmos Policy LIBERO-Object default.
- Action chunk horizon: 16; action denoising steps: 5; future-state/value denoising steps: 1.
- Wrist image, proprioception, normalization, checkpoint, and dataset statistics are identical across methods.
- Success is the simulator's official LIBERO goal predicate at any step before the horizon.

Perturbation columns:

1. **Object**: suite `libero_object_object`, which replaces the manipulated object while preserving the instruction.
2. **Position**: suite `libero_object_temp`, evaluated separately on all ten official shifts `x0.1,...,x0.5,y0.1,...,y0.5`. The reported score is an equal-weight macro-average over all `10 tasks x 10 levels` cells.
3. **Environment**: suite `libero_object_env`. LIBERO-PRO generates this suite from `libero_object` by moving the task to `living_room_table`; the benchmark script deterministically materializes the required 10 pilot init states with seed `20260825` in `.runtime/libero_pro_environment`. The same per-state seed schedule can later extend the files to 50 states without changing the first ten.

The pilot planned exactly 100 episodes per method and perturbation:

- Object and Environment: `10 tasks x init ids 0..9 x 1 rollout`.
- Position: `10 tasks x 10 position levels x init id 0 x 1 rollout`.
- Planned total: `3 methods x 3 perturbations x 100 = 900` method-episodes.

LIBERO-PRO exposes zero init states for `libero_object_temp/task1/init0` at Position level `y0.5`. This structurally unavailable cell was skipped for every method and declared in `benchmark_exclusions.json`, leaving `897/897` scorable method-episodes. It is not counted as a failure.

For the final benchmark, after the group confirms this definition, increase the number of initial states without changing any method hyperparameter. The official Cosmos Policy convention is 50 trials per task and three evaluation seeds; the final position budget must be agreed explicitly because multiplying 50 trials by ten shift levels is much larger.

## Methods

### Cosmos Policy without planning

Generate one candidate (`B=1`) and execute its 16-action chunk:

$$
j^* = 1, \qquad K=16.
$$

The collector still records value and uncertainty diagnostics, but they cannot affect action selection.

### Cosmos Policy with standard planning

Generate four stochastic candidates from the same current observation and instruction, then execute the candidate with maximal predicted value:

$$
j_v = \arg\max_{j\in\{1,\ldots,4\}} v_j, \qquad K=16.
$$

### Our frozen strategy

For candidate $j$, let $A_{j,c,t,d}$ be copy $c$ of the action latent decoded as chunk step $t$ and action coordinate $d$. Its first-action internal disagreement is

$$
u_j = \left\|\operatorname{Std}_{c}\left(A_{j,c,0,:}\right)\right\|_2.
$$

Normalize value and uncertainty only within the four candidates of the current query:

$$
z(v_j)=\frac{v_j-\bar v}{\sigma_v+\varepsilon}, \qquad
z(u_j)=\frac{u_j-\bar u}{\sigma_u+\varepsilon}.
$$

Select with the frozen risk penalty $\lambda=1$:

$$
j_r=\arg\max_j\left[z(v_j)-z(u_j)\right].
$$

Use adaptive feedback:

$$
K=\begin{cases}
8, & j_r\ne j_v,\\
16, & j_r=j_v.
\end{cases}
$$

Thus the policy re-observes the real environment halfway through the chunk exactly when risk-aware and max-value selection disagree. Earlier matched experiments showed that this combined method was the strongest tested strategy (`121/168 = 72.0%` versus `100/168 = 59.5%` for max-value, paired delta `+12.5 pp`, 95% CI `[+4.8,+20.8]`, McNemar `p=0.00646`). The factorial ablation indicated that earlier feedback, rather than uncertainty-based candidate replacement alone, explained most of that gain. The LIBERO-PRO Object run is therefore a transfer test, not further hyperparameter selection.

## Pairing and seeds

- Every method receives identical `task_id`, `init_state_id`, and rollout seed.
- Object base seed: `2100000`; Environment: `2200000`; Position: `2300000 + 10000 * level_index`.
- Planning methods use candidate offsets `0,1,2,3`; no-planning uses offset `0`, so its candidate is included in the planning candidate set.
- Rollout seed step is 97. With one rollout per init in this pilot, the collector's task/init pair id determines the remaining seed offset.
- Resume markers and query traces are retained. Missing episodes are reported as missing, never counted as failures or silently dropped.

## Metrics

Primary metrics:

1. Per-task success rate.
2. Per-perturbation macro success rate, giving equal weight to each task. Position additionally gives equal weight to each shift level.
3. Overall score: arithmetic mean of Object, Position, and Environment SR; factors are not pooled by episode count.
4. 95% confidence interval from a 10,000-sample task-cluster bootstrap.

Paired method comparisons:

- paired SR difference;
- wins, losses, and ties on identical episode keys;
- exact McNemar test on discordant episode outcomes;
- task-cluster bootstrap CI for the paired difference.

Compute metrics:

- policy queries per episode;
- stochastic candidate generations per episode;
- adaptive requery triggers per episode;
- query multiplier relative to a fixed 16-step action horizon.

Failure-type heuristics (target drop, wrong-object interaction, no progress, kinematic deadlock) are secondary diagnostics. LIBERO-PRO is not LIBERO-Safety, so absence of an official safety violation is recorded as **not measured**, not as zero violations.

## Commands

Dry run and validation:

```bash
.venv-cosmos/bin/python scripts/run_libero_experiment_campaign.py \
  --config experiments/configs/libero_campaign_pro_object_baselines.json \
  --profile pro_object_baseline_pilot \
  --run-prefix pro_object_baselines_pilot_20260825 \
  --gpus 2,3,4,5,6,7
```

Execution adds `--execute`. Final aggregation:

```bash
.venv-cosmos/bin/python scripts/analyze_pro_object_baseline_benchmark.py \
  experiments/campaigns/pro_object_baselines_pilot_20260825
```

Other methods, including Mimic-Video and the methods from Ilya, Sasha, and Nikita, must consume the same task/level/init/seed index and emit at least `method`, `factor`, `position_level`, `task_id`, `init_state_id`, `rollout_seed`, and `success`. This makes their rows directly appendable to the same paired analysis.

## Completed pilot run

The frozen pilot was launched on 2026-08-25 at 21:06 MSK on physical GPUs 2, 3, and 4 and completed in 4 h 38 min:

```text
experiments/campaigns/pro_object_baselines_pilot_20260825
```

From the local WSL checkout, inspect progress and ETA with:

```bash
./scripts/mlspace_experiment_status.sh pro_object_baselines_pilot_20260825 --verbose
```

Continuous monitoring:

```bash
./scripts/mlspace_experiment_status.sh pro_object_baselines_pilot_20260825 --watch 60
```

Rebuild the table on the server with:

```bash
ssh mlspace-sr006 \
  "/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python \
  /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/analyze_pro_object_baseline_benchmark.py \
  /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/pro_object_baselines_pilot_20260825"
```

## Frozen follow-up

Широкий pilot показал, что combined risk-aware strategy не переносится как
универсальная замена `max(value)`. Следующая preregistered проверка отдельно
сравнивает fixed short horizon, disagreement-triggered horizon и matched-random
requery без замены max-value candidate. Протокол и дальнейшие go/no-go gates:
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).

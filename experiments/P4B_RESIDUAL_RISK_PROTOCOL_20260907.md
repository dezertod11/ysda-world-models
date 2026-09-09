# P4b: calibrated residual-risk candidate selection

Status: **prospective protocol frozen before terminal holdout outcomes**.

Дата фиксации: 7 сентября 2026 года.

## Мотивация

P4 показал две разные вещи:

1. heteroscedastic quadratic JRD непригоден: raw difference отрицательна, а
   после clamp все scores равны нулю;
2. variance независимо обученных residual means связана с фактической ошибкой
   Cosmos значительно сильнее прежних internal-copy metrics.

Предварительный анализ уже открытого P4 development corpus дополнительно
показал, что mathematically nonnegative common-covariance JRD и Monte Carlo
predictive mutual information почти насыщаются верхней границей $\log K$.
Поэтому P4b проверяет более прямой вопрос: можно ли предсказать величину
residual world model и использовать её для выбора candidate action chunk.

## Residual ensemble

Вход и target остаются теми же, что в P4:

$$
x_i=[E(o_t),E(w_t),E(\hat o_{i,t+16}),E(\hat w_{i,t+16}),
p_t,\hat p_{i,t+16},\operatorname{vec}(a_i),\hat v_i],
$$

$$
r_i=[E(o_{i,t+16})-E(\hat o_{i,t+16}),
E(w_{i,t+16})-E(\hat w_{i,t+16}),
p_{i,t+16}-\hat p_{i,t+16}].
$$

Frozen P4 PCA и normalization переиспользуются без refit. Сравниваются четыре
ensemble variants на одинаковом standard-LIBERO train split:

| Variant | Loss | Regularization / calibration |
|---|---|---|
| `p4_original` | 120-epoch Gaussian NLL | исходный P4 control |
| `hetero_earlystop` | Gaussian NLL | independent OOB early stopping |
| `hetero_regularized` | Gaussian NLL | OOB early stopping + $0.01\|\log\sigma^2\|_2^2$ |
| `mean_mse_shared` | mean MSE | OOB early stopping + shared OOB residual variance |

Bootstrap выполняется по целым trajectories. Для Gaussian variance scalar
temperature выбирается только на standard-LIBERO calibration split через
mixture NLL.

## Сравниваемые risk scores

Пусть

$$
\bar\mu_i=\frac1K\sum_k\mu_{k,i},\qquad
e_i=\frac1D\sum_d\operatorname{Var}_k(\mu_{k,i,d}),
$$

а $a_i$ обозначает среднюю calibrated aleatoric variance. Сравниваются:

$$
R_{\mathrm{epi}}(i)=e_i,
$$

$$
R_{\mathrm{mean}}(i)=
\sqrt{\frac1D\sum_d\bar\mu_{i,d}^2},
$$

$$
R_{\mathrm{mean+epi}}(i)=
\sqrt{\frac1D\sum_d
(\bar\mu_{i,d}^2+\operatorname{Var}_k\mu_{k,i,d})},
$$

$$
R_{\mathrm{expected}}(i)=
\sqrt{\frac1D\sum_d
(\bar\mu_{i,d}^2+\operatorname{Var}_k\mu_{k,i,d}+a_{i,d})}.
$$

Common-covariance JRD, Monte Carlo predictive MI и epistemic SNR остаются
diagnostic ablations, но не могут быть выбраны, если score saturated или не
коррелирует с realized residual.

## Development selection и freeze

Development использует только уже открытый P4 corpus. Для каждого risk score
и $\lambda\in\{0.25,0.5,1,2\}$ candidate выбирается по

$$
j^*=\arg\max_j
\left[z_{\mathrm{within}}(\hat v_j)
-\lambda z_{\mathrm{within}}(\log(R_j+10^{-12}))\right].
$$

Внутреннее z-normalization выполняется отдельно среди четырёх candidates одного
snapshot. Selector eligible, если:

| Development condition | Threshold |
|---|---:|
| Candidate risk vs realized standardized residual | Spearman $\ge 0.50$ |
| Mean selected-minus-max-value residual | $\le-0.003$ |
| Worst factor mean residual increase | $\le0.002$ |
| Selection-change rate | от 10% до 75% |

Среди eligible вариантов минимизируется worst-factor residual delta, затем
pooled delta. Variant, metric, temperature, $\lambda$, data/code hashes и
следующий gate записываются в immutable `frozen_selector.json` **до** запуска
terminal holdout.

## Prospective terminal holdout

Каждый snapshot создаёт $K=4$ candidates из одного exact MuJoCo state. Все
четыре H16 chunks выполняются отдельными branches. Затем каждая branch
продолжается до success или `t=280` одинаковой deterministic K1 Cosmos policy.
Таким образом, различие terminal outcome обусловлено первым candidate chunk и
последовавшим за ним реальным состоянием, а не разным planning budget.

Frozen sampling contract:

- decision query: только `query_idx=3`, outcome-independent fixed schedule;
- initial candidates: seeds `0,1,2,3`, H16;
- continuation: K1, seed offset 0, no feedback branch;
- Object: task 0, init 0--39, новые rollout seeds, 40 snapshots;
- Environment: tasks 1,3,5,8,9, новый materialization seed `20260907`,
  40 snapshots;
- Position: новые cells `x0.1`, `y0.1`, `x0.3`, `y0.3`, по 30 snapshots;
- всего target: 200 snapshots / 800 terminal candidate branches;
- videos disabled during the primary run; discordant replays are generated
  only after the frozen analysis.

Object использует новые stochastic rollout groups, но знакомую task/cell;
Environment и Position дополнительно проверяют новые perturbation realization
и cells. Результаты обязательно приводятся отдельно по factor и case.

## Primary terminal endpoint

Для каждого snapshot сравниваются:

1. baseline candidate $\arg\max_j\hat v_j$;
2. frozen P4b candidate $j^*$;
3. candidate oracle, успешна ли хотя бы одна из четырёх branches.

Primary statistic:

$$
\Delta SR=\frac1N\sum_s
[\mathbb 1(Y_{s,j^*}=1)-\mathbb 1(Y_{s,j_{\max V}}=1)].
$$

95% CI строится cluster bootstrap по целым trajectory groups. Дополнительно
считаются rescue/harm, exact McNemar, candidate failure AUROC/AP, oracle gap,
drop, official safety, final time и selection-change rate.

## Frozen offline gate

| Condition | Threshold |
|---|---:|
| Campaign jobs complete | 6/6 |
| Complete K4 terminal snapshots | at least 98% |
| Exact snapshot replay | max error $\le10^{-9}$ |
| Success/fail candidates в одном state | at least 20 snapshots |
| Factor coverage | at least two factors with 5 heterogeneous snapshots |
| Paired $\Delta SR$ | strictly positive |
| Cluster-bootstrap lower CI | at least 0 |
| Rescue / harm | rescues > harms |
| Drop and official safety | no increase |

Только полный PASS разрешает реализацию и запуск closed-loop planner. При
NO-GO сохраняются candidate-level data и mechanism diagnostics, но selector не
встраивается в benchmark policy.

## Entry points

- `scripts/p4b_residual_risk.py`
- `scripts/train_p4b_residual_ensemble.py`
- `scripts/analyze_p4b_development.py`
- `scripts/analyze_p4b_terminal_holdout.py`
- `scripts/run_p4b_residual_risk_sequence.sh`
- `experiments/configs/libero_campaign_p4b_terminal_candidates_20260907.json`


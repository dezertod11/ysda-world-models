# Grounded selective world-model planning: staged protocol

Статус: **P0 frozen and running**.

Дата фиксации: 26 августа 2026 года.

P0 implementation patch: `patches/cosmos-policy-ysda.patch`, SHA-256
`3ae78ae55a2c4ac1ca301bba4dc0b84898efdf5d1f523c03af5e32e9f6a425ea`.

Активный запуск: `pro_object_horizon_controls_p0_20260826` на MLSpace,
физическая GPU 6. Campaign содержит 24 jobs и 897 новых strategy episodes;
существующие 598 episodes `maxV-H16`/`risk-H8` подключаются только на этапе
анализа. Запуск начат 26 августа 2026 года после успешного three-strategy
smoke test. Статус из WSL:

```bash
scripts/mlspace_experiment_status.sh pro_object_horizon_controls_p0_20260826 --verbose
```

Последовательный launcher `scripts/run_grounded_planning_sequence.sh` ожидает
завершения P0, строит causal report, затем запускает единый P1/P2
snapshot-collector и его offline-анализ. Таким образом, сбор P1/P2 не
пересекается с P0 по времени и использует освободившуюся GPU 6. P0 gate
определяет статус horizon-controller и допуск к closed-loop; exact-state
dataset всё равно нужен для независимого P2 candidate-ranking анализа.

```bash
cat experiments/campaigns/grounded_planning_sequence_20260826/status.json
tail -f experiments/campaigns/grounded_planning_sequence_20260826/sequence.log
```

## Исследовательская цель

Проверить архитектуру, в которой три решения разделены:

1. grounded score отвечает, какой candidate action выполнить;
2. Value of Feedback отвечает, сколько действий выполнить до нового реального
   observation;
3. constraint filter отвечает, какие actions недопустимы.

Предыдущий fixed score `value - lambda * uncertainty` не переносится на
широкий LIBERO-PRO Object benchmark. Поэтому новые веса не подбираются на
terminal success. Каждый компонент сначала проходит causal/offline ablation.

## Итоговая гипотеза

После отдельных проверок итоговый planner имеет вид

$$
i^*=\arg\max_{i\in\mathcal F(s,c)}
\left[
\mu_Q(s,a_i)-\beta\sigma_Q(s,a_i)-\gamma R_{\mathrm{tail}}(s,a_i)
\right],
$$

$$
K^*=\begin{cases}
K_{\mathrm{short}}, & \widehat{\operatorname{VoF}}(s,\{a_i\})>c_{\mathrm{query}},\\
16, & \text{otherwise}.
\end{cases}
$$

Общая формула не проверяется до прохождения отдельных gates.

## Общий benchmark

- Primary transfer: LIBERO-PRO Object, факторы Object, Position, Environment.
- Mechanism set: известные same-task/init mixed boundary cases.
- ID calibration: standard LIBERO.
- Safety endpoint: LIBERO-Safety, отдельно от task success.
- Pairing: одинаковые suite/task/init/rollout seed для всех methods.
- Split: queries одного episode и episodes одного held-out case не могут
  одновременно попасть в train и test.

## P0. Broad causal horizon controls

### Frozen methods

| ID | Candidate selector | Execution horizon |
|---|---|---|
| `maxV-H16` | `argmax(value)` | 16 |
| `maxV-H8` | `argmax(value)` | 8 всегда |
| `horizon-only` | `argmax(value)` | 8 при disagreement, иначе 16 |
| `random-H8` | `argmax(value)` | 8 с frozen probability 0.43 |
| `risk-H8` | `argmax(z(value)-z(action uncertainty))` | 8 при disagreement |

Существующие `maxV-H16` и `risk-H8` берутся из frozen campaign
`pro_object_baselines_pilot_20260825`. Новая campaign использует тот же seed
schedule и те же доступные benchmark cells.

### Primary contrasts

1. `maxV-H8 - maxV-H16`: общая польза более частого feedback.
2. `horizon-only - maxV-H16`: перенос disagreement-triggered feedback.
3. `horizon-only - random-H8`: информативность trigger при matched compute.
4. `risk-H8 - horizon-only`: добавочный эффект candidate reranking.

Primary endpoint: factor-macro SR. Secondary: paired SR, query multiplier,
timeout/drop/wrong-object/no-progress, success/query Pareto frontier.

### Gate

- **Go:** horizon method имеет положительный paired delta на broad benchmark и
  не проигрывает compute-matched control по success/query frontier.
- **Conditional:** CI включает ноль, но нет factor regression хуже 5 п.п.;
  переход к P1 разрешён как mechanism study, но не как deployable method.
- **No-go:** fixed/adaptive short horizon проигрывает `maxV-H16` или random
  control при сопоставимом compute.

## P1. Counterfactual Value of Feedback

Для snapshot $s_t$ строятся matched branches:

$$
\tau_{\mathrm{open}}:
s_t\xrightarrow{a_{t:t+15}}s_{t+16},
$$

$$
\tau_{\mathrm{feedback}}:
s_t\xrightarrow{a_{t:t+7}}s_{t+8}
\xrightarrow{\mathrm{requery}}\tilde a_{t+8:t+15}
\rightarrow\tilde s_{t+16}.
$$

Target:

$$
Y_{\mathrm{VoF}}=
G(\tau_{\mathrm{feedback}})-G(\tau_{\mathrm{open}})-c_{\mathrm{query}}.
$$

Первый pilot: 300 decision states, поровну по OOD factors. Phase proxy
`approach/grasp/transport/release` ограничен сверху 40% внутри factor, чтобы
редкий post-release query не блокировал сбор. Intervention policies
сравниваются при budgets 10%, 20%, 30%.

Primary offline metrics: uplift@budget, sign accuracy, regret относительно
oracle intervention. Primary closed-loop metric: paired factor-macro SR при
фиксированном query budget.

Единый P1/P2 collector реализован, прошёл exact-state smoke и поставлен вторым
этапом последовательного launcher; frozen schema и integrity gate описаны в
[`COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md).
Статистический запуск ожидает завершения и анализа P0.

## P2. Grounded candidate outcomes

Из каждого snapshot генерируются $B=4$ candidates. Каждый candidate
исполняется после восстановления точного simulator state:

$$
G_i=\Delta P_i
-\beta_d I_i^{drop}
-\beta_w I_i^{wrong\ object}
-\beta_n I_i^{no\ progress}
-\beta_c I_i^{constraint}.
$$

Все компоненты публикуются отдельно; scalar utility используется только после
нормировки и фиксации weights на calibration split. Для 20% snapshots каждая
ветка продолжается одной frozen policy до terminal outcome.

Rankers: random, Cosmos value, old uncertainty score, RCS, grounded critic,
QWM depth 1 и depth 2.

Primary offline metrics:

$$
\operatorname{regret}=\max_iG_i-G_{i^*},
$$

pairwise accuracy, top-1 accuracy и terminal oracle gap.

**Go:** held-out regret уменьшается минимум на 10% относительно Cosmos value и
улучшение сохраняет знак на каждом OOD factor.

## P3. Semantic consequence model

Frozen image encoder и action chunk подаются в model:

$$
f_\theta(e_t,a_i)\rightarrow
(\hat e_{t+K},\hat p_{t+K},\widehat{\Delta P},\hat y_{critical}).
$$

Ablations: Cosmos VAE latent, semantic latent, semantic+proprio. Simulator
object poses и contacts используются только как labels и evaluation targets.

## P4. Epistemic transition ensemble

Пять independently initialized bootstrap heads:

$$
p_m(e'\mid e,a)=\mathcal N(\mu_m(e,a),\Sigma_m(e,a)).
$$

Trajectory-level conformal calibration задаёт ID threshold. Проверяются
Object/Position/Environment и более сильные task/language shifts отдельно.
Ensemble используется для routing/abstention и как confidence estimate critic,
но не добавляется автоматически как soft penalty.

## P5. RCS baseline

$$
S_{\mathrm{RCS}}(a_i)=-\frac1M\sum_m E_{redenoise}(a_i,t_m).
$$

RCS проверяет support candidate, а не physical correctness. Сначала он
оценивается на сохранённых candidate pools; expensive closed-loop evaluation
разрешается только при улучшении held-out ranking.

## P6. Tail risk

После проверки action-conditioned causal sensitivity:

$$
R_{tail,i}=\operatorname{CVaR}_{\alpha}[L(\hat o_i)],
\qquad
R_{stress,i}=\max_{\epsilon\in\mathcal T}L(f_\theta(s,a_i,\epsilon)).
$$

Random futures и optimized-noise futures сравниваются при одинаковом числе
world-model forwards и независимом simulator verifier.

## P7. Safety shield

$$
\mathcal F(s,c)=\{i:
p_{violation}(s,a_i,c)\le\epsilon_c,
U_{epi}(s,a_i)\le\epsilon_{OOD}\}.
$$

При пустом feasible set выполняется explicit fallback. Primary metrics:
safe success, official violation rate, intervention rate и incompletion.

## Statistical rules

1. Screening и hyperparameter selection отделены от final test.
2. Thresholds замораживаются до просмотра test outcomes.
3. CI строятся task/config-cluster bootstrap; paired binary outcomes проверяются
   exact McNemar test.
4. Для нескольких frozen methods применяется Holm correction.
5. Вместе с SR всегда публикуются compute, failure modes и худший per-factor
   regression.
6. All-success/all-fail cases используются как stress transfer, но не как
   доказательство same-state fail detection.

## Execution order

1. `P0` broad horizon controls.
2. Единый snapshot-branching collector.
3. `P1` VoF и `P2` candidate ranking offline.
4. Frozen closed-loop `maxV`, `VoF`, `grounded-Q`, `grounded-Q+VoF`.
5. `P3/P4/P5` как отдельные ablations.
6. `P6/P7` только после соответствующих causal/calibration gates.

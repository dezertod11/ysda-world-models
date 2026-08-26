# Research roadmap: robust world-model planning

Дата обновления: 26 августа 2026 года.

Этот документ является текущим планом. Frozen-протоколы
`ADAPTIVE_PLANNING_HYPOTHESES_20260813.md` и
`SURROGATE_REQUERY_HYPOTHESES_20260819.md` сохраняются как исторические
pre-registration и не переписываются после просмотра результатов.

Обзор литературы, формулы и подробное сравнение работ находятся в
[`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).

## Цель

Построить planner для Cosmos Policy, который выбирает action не только по
self-predicted value, но учитывает:

1. support action под policy distribution;
2. uncertainty action-conditioned dynamics;
3. task progress, заземлённый реальными transitions;
4. риск редкого правдоподобного failure outcome;
5. явные safety constraints;
6. стоимость дополнительного inference и более частого feedback.

Task failure и safety violation считаются разными endpoints. Рост success не
может компенсировать official safety violation.

## Зафиксированные факты из наших экспериментов

| Наблюдение | Результат | Следствие |
|---|---:|---|
| Fixed action uncertainty penalty | 151/240 против 146/240, +2.1 п.п., CI через ноль | Одного reranking недостаточно |
| Предыдущий confirmatory `h=8` + reranking | 161/240, +6.25 п.п., CI [+1.7; +11.3], Holm `p=0.0474` | Эффект воспроизвёлся в новом causal 2x2 |
| Нормированная цена adaptive requery | 1.27x policy-query cost | Нужен явный success/compute trade-off |
| Latest future-proprio surrogate transfer | case-controlled `rho=0.653`, AUROC 0.763 | Next-chunk prediction error предсказуем online |
| Surrogate-gated planner | +0.4 п.п., CI через ноль | Proprio error не равен task-critical risk |
| Early episode-fail predictor | AUROC 0.547 | Один абсолютный threshold между tasks не работает |
| Failure-mode shift | drops уменьшились, timeout вырос | Нужны отдельные progress и safety objectives |
| Selection-only causal control | 90/168 против 100/168, -6.0 п.п., CI через ноль | Internal action uncertainty пока не даёт надёжный candidate ranking |
| Horizon-only causal control | 114/168, +8.3 п.п., CI [0.0; +16.7] | Disagreement полезен как сигнал более раннего feedback |
| Combined causal 2x2 | 121/168, +12.5 п.п., CI [+4.8; +20.8], McNemar `p=0.00646` | Главный подтверждённый механизм - adaptive feedback horizon |
| Early terminal-fail prediction | лучший case-controlled AUROC 0.575 | Local prediction error предсказывается заметно лучше, чем конечный fail |
| Temporal overlap passive campaign | 312/312 rollout; core overlap AUROC около 0.5, frozen TPR 0.04-0.12 | Plain old-tail/new-prefix distance пока не является failure detector |
| Event-label audit | 26/81 collector events находятся в successful episodes | Expected release и physical drop должны быть разделены task-aware predicates |
| Coupled-noise ablation | selected RMSE ratio 1.017, correlation 0.974; success 48/72 против 49/72 | Disagreement создаётся context revision, coupling почти не убирает noise |
| Corrected boundary screening | 264 rollout; 30/40 task-OOD cases all-fail, 9 all-success, 1 mixed | Discrete task replacement даёт grounding stress, но мало paired boundary data |
| Early within-case detector | лучший preregistered AUROC 0.613; лучший exploratory 0.678, BH q=0.87 | Plain stochastic uncertainty/overlap не прошли frozen gate |
| Physical replay audit | `spatial_task/task7/init0`: 5 success, 1 confirmed target drop | Case полезен для expansion, но пока только provisional |
| LIBERO-PRO Object broad pilot | `max(value)` 54.5%, no planning 52.8%, risk-aware requery 52.1% | Выигрыш на selected boundary cases не переносится как universal policy |
| Частота текущего adaptive trigger | 42.9-43.4% query во всех трёх OOD factors | Trigger почти не адаптируется к сложности и вмешивается слишком часто |
| Broad paired ours vs `max(value)` | -2.4 п.п., 95% CI [-5.4; +0.3], McNemar `p=0.167` | Следующий тест обязан отдельно проверить selection и feedback timing |

Новый matched 2x2 разделил reranking и более раннее observation. Прямой
reranking не подтвердился, а feedback-horizon effect положителен. Добавочный
эффект risk-aware candidate при уже adaptive horizon остаётся неопределённым.

## Завершённый исторический causal 2x2

### Matched 2x2: selection x feedback horizon

Кампания `factorial_selection_horizon_20260820` полностью завершена и
проанализирована: 7 LIBERO-PRO cases, 24 новых paired seeds, четыре условия,
всего 672 rollout.

| Условие | Candidate | Horizon при disagreement |
|---|---|---:|
| `max_value` | max value | 16 |
| `action_l1` | risk-aware | 16 |
| `horizon_only_l1_h8` | max value | 8 |
| `requery_l1_h8` | risk-aware | 8 |

Primary contrasts:

$$
\Delta_A=A-B,
\qquad
\Delta_H=H-B,
\qquad
\Delta_{AH}=AH-B,
$$

$$
I=AH-A-H+B.
$$

Результат:

| Contrast | Эффект | 95% CI | Интерпретация |
|---|---:|---:|---|
| `A-B` | -6.0 п.п. | [-13.7; +1.8] | прямой uncertainty reranking не подтверждён |
| `H-B` | +8.3 п.п. | [0.0; +16.7] | более ранний feedback полезен даже с `max(value)` candidate |
| `AH-A` | +18.5 п.п. | [+10.1; +26.8] | сильный horizon effect при фиксированном risk-aware selector |
| `AH-H` | +4.2 п.п. | [-2.4; +10.7] | добавочная польза reranking не доказана |
| `AH-B` | +12.5 п.п. | [+4.8; +20.8] | combined strategy лучше на tested case/seed set |

Решение после P0:

- uncertainty/disagreement используется прежде всего как feedback-timing
  signal;
- `requery_l1_h8` остаётся лучшей эмпирической стратегией, а
  `horizon_only_l1_h8` - обязательным causal baseline;
- линейный candidate penalty не усложняется без нового support или grounded
  consequence signal;
- из-за regressions `goal_mug` (-4.2 п.п.) и `milk_task5` (-8.3 п.п.) метод не
  считается uniform improvement и требует guard;
- следующий trigger-кандидат - cross-query temporal overlap consistency.

Полный frozen protocol:
[`FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md`](FACTORIAL_SELECTION_HORIZON_PROTOCOL_20260820.md).
Полный разбор результата:
[`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md).

## Целевая архитектура

Не следует сразу обучать одну непрозрачную формулу. Система строится слоями и
каждый слой проходит отдельную ablation.

### 0. Cross-query temporal overlap consistency

При prediction horizon $H$ и execution length $K<H$ старый tail и новый
prefix относятся к одинаковым absolute control times:

$$
X_q=A_q[K:H],
\qquad
Y_{q+1}=A_{q+1}[0:H-K].
$$

Для каждого нового candidate можно считать

$$
D_{\mathrm{overlap},q}^{(i)}=
d\left(X_q^{(i_q)},Y_{q+1}^{(i)}\right),
$$

Для selected plan простейший published baseline - TIDE-style MSE, а между
полными candidate sets - STAC MMD/energy/Chamfer distance. Это
измеряет revision нового plan после свежего observation. Оно не гарантирует
physical correctness: большой score может быть полезной коррекцией, а малый -
последовательно ошибочным plan.

Полный protocol:
[`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).

### 1. Candidate support

Для candidate \(a_i\) считаем re-denoising consistency из tau0-WM:

$$
S_{\mathrm{RCS},i}=-
\frac1K\sum_{k=1}^{K}
E_{\mathrm{redenoise}}(a_i,t_k).
$$

Это проверяет, лежит ли action на conditional action manifold. Оно не является
ни physical uncertainty, ни probability of success.

### 2. Transition epistemic uncertainty

На реальных latent transitions обучается небольшой Gaussian ensemble:

$$
p_k(z'\mid z,a)=\mathcal N(\mu_k(z,a),\Sigma_k(z,a)),
$$

$$
U_{\mathrm{epi}}(z,a)=
H_2\left(\frac1K\sum_kp_k\right)
-\frac1K\sum_kH_2(p_k).
$$

Порог \(\epsilon_{\mathrm{ID}}\) калибруется conformal prediction по целым ID
episodes. Internal-copy std остаётся отдельным generative signal и не
переименовывается в epistemic uncertainty.

### 3. Grounded task value

Critic \(Q_{\mathrm{real}}(s,a)\) обучается только на фактически исполненных
LIBERO transitions. Imagined states используются при search, но не как
ground-truth TD targets. На depth \(d\):

$$
V(d\mid s)=\alpha V_Q(d\mid s)+(1-\alpha)V_{\mathrm{WM}}(d\mid s).
$$

Первый sweep ограничен \(D\in\{1,2\}\), \(N\in\{4,8\}\) и небольшим future
discount \(\lambda\in\{0.1,0.2\}\).

### 4. Tail outcome risk

Для фиксированного candidate world model генерирует \(K\) action-conditioned
futures. Базовая robust estimate:

$$
R_{\mathrm{tail},i}
=\operatorname{CVaR}_{\alpha}
\left[L_{\mathrm{failure}}(\hat o_i^{(1:K)})\right].
$$

StressDream-вариант не ждёт случайный bad sample, а оптимизирует initial noise
в Gaussian typical set:

$$
R_{\mathrm{stress},i}=
\max_{\epsilon\in\mathcal T}
C_{\mathrm{failure}}
\left(f_\theta(\epsilon\mid s,a_i)
\right).
$$

Random sampling и steering всегда сравниваются при одинаковом числе world-model
forwards и с held-out verifier.

### 5. Constraint risk

Для constraint \(c\) из LIBERO-Safety строится отдельный risk
\(C_i=C(s,a_i;c)\). Candidate допустим, если

$$
C_i\le\epsilon_c
\quad\land\quad
U_{\mathrm{epi},i}\le\epsilon_{\mathrm{ID}}.
$$

Если допустимых candidates нет, система выполняет fallback, а не выбирает
наименьшее из плохих значений. Первый fallback: сократить horizon и requery;
следующие варианты: recovery action и abstention.

### 6. Итоговая score после отдельных ablations

Только после подтверждения компонентов проверяется общая формула:

$$
i^*=\arg\max_{i\in\mathcal F(s,c)}
\left[
Q_{\mathrm{real}}(s,a_i)
+\eta\,\widehat V_{\mathrm{WM},i}
+\rho\,S_{\mathrm{RCS},i}
-\lambda_o D_{\mathrm{overlap},i}
-\lambda_e U_{\mathrm{epi},i}
-\lambda_t R_{\mathrm{tail},i}
\right],
$$

$$
\mathcal F(s,c)=
\{i:C_i\le\epsilon_c,
U_{\mathrm{epi},i}\le\epsilon_{\mathrm{ID}}\}.
$$

Horizon выбирается отдельно:

$$
H_q=
\begin{cases}
h, & \text{overlap/ranking disagreement, OOD или tail-risk alarm},\\
16, & \text{иначе}.
\end{cases}
$$

Это принципиально: score отвечает «что выполнить», horizon - «сколько времени
не смотреть на реальный мир», constraint filter - «что выполнять нельзя».

## Архив предыдущей очереди экспериментов

Разделы P1a-P7 ниже сохраняют постановки, сформулированные до широкого
LIBERO-PRO Object transfer test. Они полезны как каталог методов, но больше не
задают порядок запуска. Актуальная последовательность и frozen go/no-go gates
находятся в разделе «Текущий приоритет» и в
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).

### P1a. Temporal overlap consistency

**Гипотеза.** Old-tail/new-prefix disagreement даёт локальный warning до
erratic failure и является более прямым feedback signal, чем uncertainty
внутри одного query.

**Статус 24 августа 2026.** Пункты 1-3 завершены: 240 independent и 72
coupled rollout. Smoke test подтвердил форму `[Q,4,16,7]`, exact
$A_q[8:16]\leftrightarrow A_{q+1}[0:8]$ alignment и CSV/NPZ round-trip.
Plain selected/support/Chamfer/energy distances дали AUROC около 0.5;
frozen-threshold TPR составил только 0.04-0.12. Coupled seeds практически не
снизили distances.

Дополнительный audit показал, что event endpoint непригоден для
confirmatory detector claim: 26/81 событий возникли в successful episodes,
обычное выкладывание первого предмета было размечено как drop, а один
LIBERO-PRO task case передавал policy исходную filename-derived команду при
изменённой BDDL goal. Поэтому пункты 4-7 **не запускаются на текущих labels**.
Сначала выполняются semantic ground-truth repair и поиск same-case mixed
outcomes. Полный разбор:
[`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md).

**Обновление 24 августа 2026.** Ground-truth repair и 264-rollout boundary
screening завершены. Из 40 task-OOD cases 30 all-fail, 9 all-success и только
один mixed; две known controls остались confirmed mixed. Лучший preregistered
early signal дал macro AUROC 0.613, а exploratory normalized overlap shift -
0.678 при `BH q=0.87`. Plain detector не прошёл gate. Протокол:
[`GROUND_TRUTH_REPAIR_AND_BOUNDARY_SCREENING_20260824.md`](GROUND_TRUTH_REPAIR_AND_BOUNDARY_SCREENING_20260824.md).
Результаты:
[`GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md`](GROUND_TRUTH_BOUNDARY_SCREENING_RESULTS_20260824.md).

1. Добавить сохранение полных candidate chunks и, на подвыборке, action latent
   embeddings.
2. Проверить exact alignment $A_q[8:16]$ против $A_{q+1}[0:8]$ и same-seed
   reproducibility.
3. Passive run: TIDE-style selected MSE, support, Chamfer, STAC MMD и
   coupled-noise distance.
4. Сравнить global split-conformal threshold с query/phase-conditioned
   functional conformal threshold.
5. Заморозить detector на whole-case validation и проверить event AUPRC,
   TPR@5%FPR и lead time на held-out PRO families и LIBERO-Safety.
6. Как supervised upper baseline обучить последовательный detector в стиле
   Hide-and-Seek только по trajectory-level success/fail labels.
7. Closed-loop сравнить weak overlap reranking и alarm-triggered short horizon.

Plain overlap metric уже существует в Sentinel/STAC и Rewind-IL/TIDE; сильный
результат должен дать sample-efficient перенос на Cosmos, warning до event и
causal planning gain. Hide-and-Seek на LIBERO-10 показывает, что learned
temporal action embeddings являются обязательным baseline при наличии failed
trajectories. Нельзя сравнивать соседние future image/value без fixed absolute
time.

### P1b. Re-denoising consistency без обучения новой модели

**Гипотеза.** RCS дополняет internal-copy uncertainty и лучше отличает
off-manifold action candidates.

1. Реализовать re-noise/re-denoise action chunks на 3-5 flow times.
2. Проверить, что score воспроизводим при fixed candidate/noise.
3. На сохранённых candidate pools посчитать top-1 retrospective oracle hit,
   pairwise candidate preference и correlation с actual next-chunk outcomes.
4. Closed-loop сравнить `maxV`, `action_l1`, `RCS`, `maxV+RCS` на новых paired
   seeds тех же mixed cases.

**Go:** положительный pooled delta без regression хуже -10 п.п. на sentinel case
или явное улучшение oracle hit/AUPRC на held-out cases.

### P2. Проверка causal action-conditioned future

**Гипотеза.** Последовательность `fixed action -> future -> value` различает
candidate consequences лучше текущего parallel self-generated value.

1. Зафиксировать observation и один action candidate.
2. Семплировать несколько future image/proprio, меняя только future noise.
3. Повторить для других actions при общих noise seeds.
4. Проверить action sensitivity, calibration prediction error и совпадение
   ordering с фактически выполненными chunks.
5. Сравнить `parallel`, autoregressive/sequential и action-conditioned modes.

Без этого теста CVaR и StressDream не запускаются: нельзя оптимизировать future,
который причинно не привязан к оцениваемому action.

### P3. Grounded critic и QWM-lite

**Гипотеза.** Реальный success/progress critic уменьшает self-value
overconfidence, а depth 2 даёт дополнительный сигнал без сильного compounding
error.

Data:

- train: completed calibration campaigns, split по целым cases;
- validation: held-out init states/tasks;
- test: новые seeds и минимум одна новая PRO family;
- labels: terminal success, dense BDDL progress, drop/contact/no-progress.

Ablations:

| Вариант | Search |
|---|---|
| `max_cosmos_value` | depth 0 |
| `max_grounded_Q` | depth 0 |
| `QWM_D1` | one action-conditioned future |
| `QWM_D2_mean` | depth 2, mean aggregation |
| `QWM_D2_CVaR` | depth 2, lower-tail aggregation |

Primary endpoint - paired closed-loop success; secondary - calibration/Brier,
drop, timeout, query latency и search regret.

### P4. JRD ensemble и conformal OOD

**Гипотеза.** Transition-conditioned JRD переносится между OOD families лучше
internal-copy std и даёт контролируемый ID false-positive rate.

1. Из Cosmos latent traces собрать \((z_t,a_t,z_{t+1})\).
2. Обучить 5 small Gaussian heads bootstrap/resampled trajectories.
3. Сравнить empirical mean variance, total uncertainty, max aleatoric и JRD.
4. Калибровать threshold trajectory-level CP на standard LIBERO ID.
5. Проверить OOD detection на PRO `Obj/Env/Pos/Sem/Task` отдельно.

Primary metrics: ID recall at fixed \(\alpha\), OOD AUPRC, lead time, overhead.
Closed-loop endpoint появляется только после успешной calibration.

### P5. Task-critical outcome heads

**Гипотеза.** Separate heads `drop`, `contact loss`, `wrong object`,
`no progress`, `constraint violation` полезнее общего future-proprio L2.

Сначала labels строятся из simulator state/contact и official LIBERO-Safety
checks; video/VLM labels используются только как дополнительная слабая разметка.
Сравниваются:

- per-event binary heads;
- shared encoder + multi-head outputs;
- one scalar failure head;
- existing proprio-error surrogate.

Нужны event AUPRC, calibration и lead time; episode accuracy недостаточна.

### P6. StressDream-lite

**Гипотеза.** Gradient-steered future noise находит task-critical bad outcomes
чаще best-of-N при равном compute.

Первый этап offline:

- 100 success и 100 fail/near-fail query contexts;
- target prompts/heads для drop, missed grasp, wrong placement, collision;
- best-of-4/10/40 random futures;
- 5/10/20 steering steps;
- ablation norm/isotropy/spectral constraints;
- held-out simulator-event verifier, а не тот же VLM objective.

Только если steering повышает recall без деградации physical plausibility,
добавить его online после high-risk alarm.

### P7. Constraint-conditioned safety filter

Два уровня сложности:

1. **Практический:** constraint-conditioned risk head + conformal threshold +
   `requery/recovery/abstain`.
2. **Исследовательский:** AnySafe/UNISafe-style latent reachability с learned
   fallback policy.

Evaluation идёт на official LIBERO-Safety outcomes. Отдельно измеряются task
success, official violations, intervention rate и incompletion. Эвристические
drop labels не заменяют official constraint checks.

## Benchmark matrix

| Benchmark | Роль |
|---|---|
| Standard LIBERO | ID calibration, critic/transition training, false-positive control |
| LIBERO-PRO | OOD transfer и mixed-boundary closed-loop planning |
| LIBERO-Plus | Factorized ablation camera/background/pose/noise при необходимости |
| LIBERO-Safety | Official constraint endpoint и fallback evaluation |

Новые methods сначала проверяются на 3-7 известных mixed cases, затем веса и
thresholds замораживаются и переносятся на целые held-out task/family. Queries
одного episode никогда не делятся между train и test.

## Общий statistical protocol

1. Screening: 8-12 paired seeds на case, только prespecified grid.
2. Заморозить не более двух variants на гипотезу.
3. Confirmatory: минимум 20-30 новых paired seeds на case.
4. Primary: stratified paired bootstrap CI и exact McNemar.
5. Несколько frozen methods: Holm correction.
6. Обязательно показывать min/max per-case delta и sentinel regressions.
7. Success всегда публикуется вместе с query cost, timeout, drop и safety.
8. Видео - mechanism evidence, не статистическая выборка.

## Текущий приоритет после broad LIBERO-PRO transfer

Полный frozen protocol:
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).

### P0. Broad causal horizon controls

На тех же LIBERO-PRO Object cells сравниваются `maxV-H16`, `maxV-H8`,
`horizon-only`, compute-matched random requery и прежний `risk-H8`. Selection
остаётся `max(value)` во всех новых controls. Это отделяет пользу свежего
observation от качества uncertainty-reranking и от простого роста compute.

Статус 26 августа: frozen campaign
`pro_object_horizon_controls_p0_20260826` запущена на MLSpace GPU 6. План:
24 jobs, 897 новых strategy episodes и matched merge с 598 сохранёнными
`maxV-H16`/`risk-H8` episodes. P1 реализуется параллельно как код, но не
запускается до завершения P0. Последовательный launcher уже поставлен в
очередь: после P0 он строит causal report и только затем начинает P1/P2.

### P1. Counterfactual Value of Feedback

Из одного simulator snapshot строятся две ветки: выполнить старый chunk 16
шагов или выполнить 8 шагов, requery и продолжить новым plan. Target gate - не
terminal failure, а индивидуальная польза вмешательства:

$$
\operatorname{VoF}(s)=
\mathbb E[G_{\mathrm{feedback}}-G_{\mathrm{open}}\mid s]
-c_{\mathrm{query}}.
$$

Gate проверяется при intervention budgets 10%, 20% и 30% против random policy
того же бюджета.

Реализация P1/P2 snapshot collector завершена 26 августа. Simulator replay
после ненулевого prefix имеет max state error `1.06e-15`, полный Cosmos smoke
собрал четыре candidate branches и feedback branch с replay error `8.12e-16`.
Dry-run manifest проверен: 12 jobs и 300 targets, по 100 на Object,
Environment и Position. Запуск pilot остаётся заблокирован только порядком
экспериментов до завершения P0. Подробности:
[`COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md).

### P2. Grounded candidate critic и QWM-lite

Каждый candidate chunk фактически исполняется из одного snapshot. Grounded
utility включает BDDL progress и отдельные penalties `drop`, `wrong_object`,
`no_progress`, `constraint`. Critic обучается только на real transitions;
world-model rollout используется только для короткого depth-1/2 search.

### P3. Semantic action-conditioned consequence model

Сравниваются Cosmos reconstruction latent, frozen semantic latent и их
комбинация с proprio. Основные targets - task progress и critical events, а не
pixel MSE. Privileged simulator state разрешён для labels/evaluation, но не
подаётся planner во время deployment.

### P4. Epistemic ensemble и conformal routing

Пять independently trained probabilistic transition heads дают epistemic
disagreement. Он управляет `B`, execution horizon и expensive evaluator;
trajectory-level conformal calibration задаёт ID false-positive rate.

### P5. RCS coarse-to-fine baseline

Re-denoising consistency проверяется как candidate-support score. Низкий RCS
может вызвать grounded evaluator или requery, но не интерпретируется как
вероятность task success.

### P6. Tail-risk / StressDream

CVaR и steered diffusion noise запускаются только после causal проверки
`fixed action -> predicted consequence`. Первый режим - offline stress testing
и hard-negative mining при matched world-model forward budget.

### P7. Constraint-conditioned safety shield

LIBERO-Safety остаётся отдельной веткой: hard feasible set,
trajectory-calibrated threshold и явный fallback. Task value не компенсирует
official safety violation.

### Порядок принятия решений

1. Завершить P0 и выбрать не более одного horizon controller.
2. Одним snapshot-branching collector собрать targets одновременно для P1-P4.
3. Сначала проверить offline uplift/ranking; closed-loop разрешается только
   после held-out gate.
4. Заморозить один VoF gate и один grounded ranker.
5. Проверить `maxV`, `VoF`, `grounded-Q`, `grounded-Q+VoF` на целых unseen
   tasks/OOD families.
6. Только затем добавлять ensemble, tail risk и safety filter отдельными
   ablations.

Ближайший сильный результат должен отвечать не «uncertainty коррелирует с
ошибкой», а одному из двух утверждений:

- более ранний feedback причинно повышает success при контролируемой цене; или
- action-conditioned robust evaluator выбирает лучший candidate на held-out
  OOD cases и уменьшает task-critical failures.

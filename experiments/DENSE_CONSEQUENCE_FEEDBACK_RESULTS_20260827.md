# Dense consequence feedback: H16 screening и H32 pilot

Дата обновления: 27 августа 2026 года.

## Постановка

Предыдущая event-only utility не различила ни одну из 272 matched open/requery
ветвей на горизонте 16. Поэтому сохранённые MuJoCo endpoint states были
переразмечены непрерывной геометрией задачи без повторного запуска Cosmos.

Для каждой goal-пары `(target, goal)` считаются

$$
d_g = \operatorname{clip}\left(
\frac{\|p_t^{target}-p_t^{goal}\|-\|p_{t+H}^{target}-p_{t+H}^{goal}\|}{0.25},
-1,1\right),
$$

$$
d_e = \operatorname{clip}\left(
\frac{\|p_t^{target}-p_t^{eef}\|-\|p_{t+H}^{target}-p_{t+H}^{eef}\|}{0.10},
-1,1\right),
$$

$$
d_l = \operatorname{clip}\left(
\frac{z_{t+H}^{target}-z_t^{target}}{0.05},-1,1\right).
$$

Phase-aware progress равен

$$
D_{approach}=0.5d_g+0.5d_e,
$$

$$
D_{grasp}=0.25d_g+0.25d_e+0.5d_l,
$$

$$
D_{transport}=0.75d_g+0.25d_l,
\qquad D_{release}=d_g.
$$

Если отдельная компонента недоступна, веса оставшихся компонент
перенормируются. Итоговая utility сохраняет success и safety раздельно:

$$
G_H = 2I_{success}+\Delta progress+D_{phase}
-I_{drop}-0.5I_{wrong}-I_{violation}.
$$

Matched value of feedback:

$$
Y^{(H)}_{VoF}=G_H(\tau_{8+requery+8})-G_H(\tau_{16})-c_{query}.
$$

Все физические компоненты опубликованы отдельными колонками; скалярная
utility используется только как ranking target.

## H16: данные и integrity

- 272 decision states: 100 Object, 100 Environment, 72 Position;
- 1088 candidate branches, по четыре stochastic candidates на state;
- 265/272 states проходят строгий replay gate `max_abs_error <= 1e-9`;
- dense VoF: 127 positive, 143 negative, 2 zero;
- strict subset: 122 positive, 141 negative, 2 zero;
- candidate utility различается в 271/272 states, в strict subset в 264/265.

Таким образом, вырожденность старой local utility устранена. Результат не
является следствием семи imperfect replay states: support сохраняется после их
исключения.

## P1: можно ли выбирать момент requery

### Pooled OOF

| Model | States | AUROC `VoF > 0` | Sign accuracy | Correlation |
|---|---:|---:|---:|---:|
| uncertainty ridge | 272 | 0.686 | 0.632 | 0.316 |
| `factor x phase` OOF mean | 272 | **0.778** | **0.743** | **0.368** |
| uncertainty ridge, strict | 265 | 0.672 | 0.638 | 0.183 |
| `factor x phase`, strict | 265 | **0.774** | **0.740** | **0.363** |

Pooled uncertainty model лучше random, но проигрывает простой phase-aware
baseline. Поэтому pooled результат сам по себе не доказывает пользу
uncertainty.

### Factor-wise OOF

| Factor | OOF states | Uncertainty AUROC | Phase AUROC | Вывод |
|---|---:|---:|---:|---|
| Environment | 100 | **0.980** | 0.972 | обе модели сильные; phase объясняет большую часть эффекта |
| Object | 100 | **0.717** | 0.651 | uncertainty даёт дополнительный сигнал |
| Position | 14 | 0.467 | 0.449 | независимых `task/init` групп недостаточно |

При 20% query budget realized uplift per decision:

| Factor | Uncertainty ridge | Phase baseline | Random | Predicted proprio error |
|---|---:|---:|---:|---:|
| Environment | **+0.00378** | +0.00280 | -0.00622 | +0.00174 |
| Object | +0.00619 | -0.00178 | -0.00112 | **+0.00748** |
| Position, только 14 OOF states | -0.00138 | -0.00306 | -0.00040 | +0.00718 |

**Решение P1:** H16 dense target проходит mechanism-screening для Object и
Environment. Для Object особенно интересна простая ошибка predicted proprio.
Position требует новый сбор с несколькими независимыми `task/init`, а не ещё
одну подгонку на текущих 72 коррелированных snapshots.

## P2: можно ли ранжировать candidates

Dense regret на H16:

| Factor | Cosmos value | Fixed `value - internal action` | Factor OOF candidate ridge | Random |
|---|---:|---:|---:|---:|
| Environment | 0.00372 | 0.00436 | **0.00114** | 0.00372 |
| Object | 0.02019 | **0.01303** | 0.02166 | 0.01490 |
| Position | **0.00375** | 0.00668 | 0.00467 | 0.00432 |

OOF correlation predicted vs centered candidate utility составляет около
0.03. Ни fixed penalty, ни learned ranker не уменьшают regret относительно
Cosmos value на каждом factor. Object и Environment требуют разных поправок,
а текущие candidate-specific latent metrics не дают переносимого общего
ranker.

**Решение P2:** no-go для closed-loop candidate reranking. Следующий ranker
должен использовать action-conditioned consequence model либо более сильные
hard negatives, а не только internal latent consistency.

## Matched H32 pilot

### Дизайн и integrity

Runtime smoke прошёл на физической GPU 7 с replay error `2.88e-15`. В полном
pilot H16 и H32 endpoint states/proprio сохранены в одном sidecar. После H16
каждая open/feedback branch продолжается одной frozen `max(value)` policy до
H32 с common random seeds; terminal continuation начинается только после H32.

Campaign `counterfactual_feedback_h32_pilot_20260827` завершила 48/48 states и
288 candidate branches: по 12 Object и Environment, по 12 Position `x0.3` и
`y0.3`, шесть stochastic candidates на state. Для `x0.3` первые шесть
эпизодов не вышли из `approach`; чтобы не перебирать десятки недостижимых
`grasp/transport` фаз, был применён записанный в config adaptive fallback
`phase_cap_fraction=1.0`, `terminal_continuation_fraction=0.0`. Остальные jobs
сохранили cap 0.5 и deterministic terminal fraction 0.1.

- 47/48 states проходят strict replay gate `<=1e-9`;
- один Environment/grasp state имеет error `1.579e-4` и исключён из strict
  sensitivity;
- единственный terminal state находится в Object: open и feedback успешны на
  шагах 145 и 137, но frozen terminal utility одинакова, поэтому VoF равен 0.

### Увеличил ли H32 consequence support

| Factor | States | H16 non-tied candidates | H32 non-tied candidates | H16 mean range | H32 mean range |
|---|---:|---:|---:|---:|---:|
| Environment | 12 | 12 | 12 | 0.00882 | **0.01140** |
| Object | 12 | 12 | 9 | 0.00629 | 0.00301 |
| Position | 24 | 24 | 14 | 0.01170 | 0.00733 |
| **All** | **48** | **48** | **35** | **0.00963** | **0.00727** |

H32 не прошёл preregistered support gate: число различимых candidate sets
уменьшилось с 48 до 35, а средний utility range -- на 24.5%. Исключение только
Environment. Frozen continuation часто сводит разные H16 endpoints к одному
H32 consequence.

Matched VoF также нестабилен между горизонтами:

| Factor | H16 positive | H32 positive | Sign agreement | Correlation H16/H32 |
|---|---:|---:|---:|---:|
| Environment | 66.7% | 41.7% | 75.0% | 0.603 |
| Object | 25.0% | 41.7% | 66.7% | 0.308 |
| Position | 45.8% | 12.5% | 58.3% | -0.258 |
| **All** | **45.8%** | **27.1%** | **64.6%** | **0.321** |

H16 имеет 22 positive / 26 negative / 0 zero VoF; H32 -- 13 positive / 22
negative / 13 zero. Следовательно, H32 не является просто менее шумной версией
H16 и особенно плохо переносится на Position.

### P1: routing дополнительного observation

| Target | Uncertainty ridge AUROC | `factor x phase` AUROC | Uncertainty correlation |
|---|---:|---:|---:|
| H16 dense VoF | 0.514 | 0.569 | 0.129 |
| H32 dense VoF | 0.541 | **0.736** | 0.019 |
| H16 strict | 0.520 | 0.473 | 0.102 |
| H32 strict | 0.543 | **0.760** | -0.008 |

Online uncertainty features остаются около chance. При pooled 20% budget H32
ridge даёт uplift `+0.00108` на decision, random `+0.00058`, а phase baseline
`+0.00764`. Но factor-wise ridge не имеет достаточного числа независимых
rows: 0 честных OOF states для Object/Environment и 2 для Position. Сильный
phase baseline является гипотезой о расписании requery, а не доказательством
uncertainty routing, и дополнительно зависит от adaptive phase composition.

**Решение P1:** H32 не подтверждает перенос online uncertainty router. Большой
H16 result остаётся mechanism evidence, но новый confirmatory сбор должен
использовать больше независимых `task/init` и заранее frozen low-dimensional
router.

### P2: factor-specific candidate ranker

Для candidate $j$ одного snapshot $i$ online features нормируются только
относительно остальных candidates того же snapshot:

$$
z_{ijm}=\frac{x_{ijm}-\bar x_{im}}{s_{im}}.
$$

Target также центрируется внутри snapshot,
$y_{ij}=G_{ij}-\bar G_i$. Для каждого OOD factor $f$ обучается ridge:

$$
\hat\beta_f=\arg\min_\beta
\sum_{(i,j)\in f}(y_{ij}-\beta^\top z_{ij})^2
+\alpha\lVert\beta\rVert_2^2,
\qquad
j^*=\arg\max_j \hat\beta_f^\top z_{ij}.
$$

В $x_{ij}$ входят predicted value, L1 первого action, L1/L2 chunk и
candidate-specific latent consistency для action, future proprio и value.
Все candidates одного `suite/task/init` находятся в одном OOF fold; real
utility тестового fold не участвует ни в normalization model, ни в fit.

На тех же 48 states factor-specific grouped OOF ridge уменьшает regret Cosmos
value на каждом factor:

| Horizon | Factor | Cosmos value regret | Factor OOF regret | Relative reduction |
|---|---|---:|---:|---:|
| H16 | Environment | 0.002662 | 0.001435 | 46.1% |
| H16 | Object | 0.001757 | 0.000213 | 87.9% |
| H16 | Position | 0.007246 | 0.004689 | 35.3% |
| H32 | Environment | 0.003230 | 0.002516 | 22.1% |
| H32 | Object | 0.001697 | 0.001489 | 12.3% |
| H32 | Position | 0.001418 | 0.001003 | 29.3% |

Factor-macro H16 regret падает с `0.003889` до `0.002112` (-45.7%), H32 -- с
`0.002115` до `0.001669` (-21.1%). На strict subset reductions составляют
42.6% и 14.1%. Centered candidate-utility OOF correlation равна 0.275 для H16
и 0.296 для H32.

Это первый P2 screen, формально прошедший offline factor gate. Однако он пока
не confirmatory:

- всего 4 независимые Environment, 2 Object и 5 Position `task/init` групп;
- в strict Environment random regret `0.002341` всё ещё ниже ranker regret
  `0.003048`;
- pooled ranker не переносится: улучшение появляется только после factor
  conditioning;
- средние utility differences малы, поэтому выигрыш task success в closed-loop
  ещё не показан.

Шесть samples сами по себе не дали большей action diversity: средние
pairwise-action и value ranges ниже, чем в предыдущем four-candidate H16
campaign. Поэтому улучшение нельзя приписывать просто большему `K`.

**Решение P2:** H16 factor-specific ranker проходит mechanism-screening и
становится следующим приоритетом. Заморозить features/regularization на этом
screen, собрать новые unseen `task/init` groups с шестью candidates и только
после held-out regret gate запускать closed-loop planning. H32 для этого не
нужен: он дороже и даёт меньший screening gain.

## Итоговое решение

**Обновление 28 августа:** следующий frozen holdout завершён и прошёл
preregistered gate. На 230 strict states из 69 новых groups H16 ranker уменьшил
factor-macro regret на 43.1%, bootstrap CI для delta `[-0.005768; -0.002298]`.
Это подтверждает перенос offline candidate ranking и разрешает paired
closed-loop тест. Полный результат:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md).

1. Сохранить `maxV-H16` как deployment baseline.
2. Не продолжать H32 как основной consequence horizon.
3. Не разворачивать текущий P1 uncertainty router.
4. Продолжить P2 как frozen factor-specific H16 candidate critic на новом
   held-out dataset; добавить действительно разнообразные hard negatives, а
   не только ещё два близких diffusion seeds.
5. Terminal/time-to-success хранить отдельными компонентами; один terminal
   state недостаточен для обучения или вывода.

## Артефакты

- H16 relabel campaign:
  `campaigns/counterfactual_feedback_dense_relabel_20260827/`;
- полный отчёт анализатора:
  `campaigns/counterfactual_feedback_dense_relabel_20260827/analysis/counterfactual_feedback/RESULTS.md`;
- H32 config:
  `configs/libero_campaign_counterfactual_feedback_h32_pilot.json`;
- H32 raw tables and server-side exact-state sidecars:
  `campaigns/counterfactual_feedback_h32_pilot_20260827/`;
- H32 dense labels and analysis:
  `campaigns/counterfactual_feedback_h32_dense_relabel_20260827/analysis/counterfactual_feedback/`;
- collector: `../scripts/collect_counterfactual_feedback.py`;
- CPU relabeler: `../scripts/relabel_counterfactual_dense.py`;
- analyzer: `../scripts/analyze_counterfactual_feedback.py`.

# LIBERO: постановка, формулы и результаты экспериментов

Дата фиксации: 24 июля 2026 года.

Этот файл является основным отчётом по фактически выполненным экспериментам.
Он отделяет завершённые запуски от подготовленных, но ещё не выполненных
профилей.

## 1. Где находится описание

| Файл | Что в нём |
|---|---|
| [`LIBERO_OOD_SAFETY_CAMPAIGN.md`](LIBERO_OOD_SAFETY_CAMPAIGN.md) | Зачем нужны LIBERO, LIBERO-PRO и LIBERO-Safety, какие suites и failure labels используются |
| [`configs/libero_campaign_v1.json`](configs/libero_campaign_v1.json) | Исполняемые профили `id_controls`, `boundary_search`, `pro_ood_detection`, `planning_holdout`, `safety_physical` и `safety_semantic_probe` |
| [`LIBERO_8H_VALIDATION_PROTOCOL.md`](LIBERO_8H_VALIDATION_PROTOCOL.md) | Зафиксированный до запуска протокол большой LIBERO-PRO кампании, grid гиперпараметров и правила calibration/holdout |
| [`campaigns/phase1_analysis_20260724/README.md`](campaigns/phase1_analysis_20260724/README.md) | Результаты standard LIBERO ID control и первого LIBERO-PRO screening |
| [`campaigns/libero_full_validation_20260724/analysis/full_validation/`](campaigns/libero_full_validation_20260724/analysis/full_validation/) | Полные таблицы 1078 rollout-выполнений большой кампании |
| [`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md) | Протоколы и результаты релевантных статей |

## 2. Что реально запущено

| Среда | Роль | Статус | Фактические данные |
|---|---|---|---|
| Standard LIBERO | ID control | Завершено | 72/72 success |
| LIBERO-PRO | OOD screening | Завершено | 106 rollout: 82 success, 24 fail |
| LIBERO-PRO | Detector и planning validation | Завершено | 23/23 jobs, 1078 rollout-выполнений: 603 success, 475 fail |
| LIBERO-Safety | Official physical/semantic safety | Окружение и profiles готовы, rollout campaign не запускалась | Официальных Safety-результатов пока нет |

Число 1078 является числом **выполнений стратегий**, а не числом независимых
сцен. Одни и те же `task/init_state/rollout_seed` повторялись для разных
planning methods. Поэтому общий success rate `603/1078` нельзя использовать
для сравнения методов. Для planning ниже используются одинаковые seeds и
paired wins/losses.

Нулевое число `official_safety_violation` в LIBERO-PRO также не является
результатом LIBERO-Safety: в PRO нет официальных constraints этого benchmark.

## 3. Исследовательская постановка

Cosmos Policy выбирает action candidate по predicted value. В OOD-сцене
value может быть завышен, а несколько допустимых stochastic predictions могут
сильно расходиться. Основная идея:

> выбирать action chunk не только по value, но и по uncertainty, измеренной
> для того же candidate до выполнения действий.

Проверялись следующие гипотезы.

| ID | Гипотеза | Итог |
|---|---|---|
| H1 | LIBERO-PRO создаёт больше natural failures, чем standard LIBERO | Поддержана |
| H2 | Uncertainty до действия выше у будущих fail | Не универсально; найден сильный поздний сигнал на одном fixed case |
| H3 | Uncertainty предсказывает расхождение world-model prediction с реальностью | Не поддержана как сильная общая зависимость |
| H4 | Статический score `value - lambda * uncertainty` улучшает `max(value)` | Не поддержана на holdout и pooled generalization |
| H5 | Число candidates, query interval, denoising и parallel/AR меняют качество ranking | Есть сильные взаимодействия, но ablations пока маломощны |
| H6 | Те же сигналы предсказывают official safety violation | Ещё не проверена |

## 4. Что получает и генерирует модель

На query \(q\) модель получает реальное observation среды

\[
o_q=(I_q^{\mathrm{agent}}, I_q^{\mathrm{wrist}}, p_q)
\]

и language instruction \(l\). Здесь \(p_q\) содержит proprioception робота.
Для stochastic seed \(n\) модель генерирует

\[
\left(
A_q^{(n)},\widehat I_{q+1}^{(n)},
\widehat I_{q+1,\mathrm{wrist}}^{(n)},
\widehat p_{q+1}^{(n)},\widehat V_q^{(n)}
\right),
\]

где \(A_q^{(n)}\in\mathbb{R}^{16\times 7}\) является action chunk.

В основном `parallel` режиме action, future state и value извлекаются из одной
diffusion sequence данного sample. После выбора candidate выполняются 16
действий, затем модель получает **новое реальное observation** из MuJoCo.
Предсказанное состояние не подставляется вместо реальности.

В отдельном `autoregressive` ablation использовалась цепочка

\[
A^{(n)}\sim p(A\mid o,l),\qquad
\widehat s^{(n)}\sim p(s'\mid o,l,A^{(n)}),\qquad
\widehat V^{(n)}\sim p(V\mid o,l,A^{(n)},\widehat s^{(n)}).
\]

## 5. Метрики uncertainty

### 5.1. Разброс между stochastic samples

Для \(N\) samples:

\[
\bar A_{t,d}=\frac1N\sum_{n=1}^{N}A_{n,t,d},\qquad
\sigma^A_{t,d}=
\sqrt{\frac1N\sum_{n=1}^{N}(A_{n,t,d}-\bar A_{t,d})^2}.
\]

В коде используется population standard deviation (`ddof=0`).

\[
u_{\mathrm{action,mean}}
=\frac1{HD}\sum_{t,d}\sigma^A_{t,d},
\qquad
u_{\mathrm{action,first}}
=\left\|\sigma^A_{0,1:6}\right\|_2,
\qquad
u_{\mathrm{action,max}}=\max_{t,d}\sigma^A_{t,d}.
\]

Для value:

\[
\bar V=\frac1N\sum_n V_n,\qquad
u_{V,\mathrm{std}}=\operatorname{Std}_n(V_n),\qquad
u_{V,\mathrm{range}}=\max_nV_n-\min_nV_n.
\]

Аналогично считается средний element-wise std для future proprio и pixels
future images.

### 5.2. Internal latent-copy inconsistency

Action и low-dimensional state/value записываются в latent frame в виде
нескольких повторённых копий. Для candidate \(n\) и копии \(k\):

\[
\sigma^{\mathrm{copy}}_{n,t,d}
=\operatorname{Std}_{k}\left(\widetilde A_{n,k,t,d}\right).
\]

Из неё получаются candidate-level risks:

\[
u^{A,\mathrm{first}}_n
=\left\|\sigma^{\mathrm{copy}}_{n,0,1:6}\right\|_2,
\quad
u^{A,\mathrm{chunk}}_n
=\frac1{HD}\sum_{t,d}\sigma^{\mathrm{copy}}_{n,t,d},
\quad
u^{A,\max}_n=\max_{t,d}\sigma^{\mathrm{copy}}_{n,t,d}.
\]

Для value:

\[
u^V_n=\operatorname{Std}_{e}
\left(\widetilde V_{n,e}\right),
\]

где \(e\) перечисляет элементы value latent frame. Название
`latent_action_copy_std_mean_mean_over_samples` означает, что сначала
считается средний std между latent copies одного sample, затем результат
усредняется по \(N\) stochastic samples.

### 5.3. Flow-path dispersion

Для каждой пары stochastic denoising trajectories \(i,j\), denoising step
\(\ell\) и latent block \(b\):

\[
D_b=
\frac{1}{|\mathcal P|L}
\sum_{i<j}\sum_{\ell}
\frac{1}{\sigma_\ell}
\operatorname{Mean}_{e\in b}
\left(v^{(i)}_{\ell,e}-v^{(j)}_{\ell,e}\right)^2.
\]

В таблицах это колонки
`flow_path_dispersion_*_vfd_weighted`. Это **не exact cross-model VFD**:
используется один checkpoint с разными stochastic paths, и velocity каждого
sample вычислена в своей точке траектории. Метрика проверяет stochastic
flow-path dispersion.

## 6. Planning formulas

Для любого candidate-level признака \(x_n\) используется стандартизация только
внутри текущего набора кандидатов:

\[
z(x_n)=\frac{x_n-\operatorname{Mean}_m x_m}
{\operatorname{Std}_m x_m+\varepsilon}.
\]

Baseline:

\[
n^*_{\max V}=\arg\max_n V_n.
\]

Action penalty:

\[
n^*=\arg\max_n
\left[z(V_n)-\lambda z(u^{A,\mathrm{first}}_n)\right].
\]

Для `action_chunk` и `action_max` в эту же формулу подставляются
\(u^{A,\mathrm{chunk}}_n\) и \(u^{A,\max}_n\).

Value penalty:

\[
n^*=\arg\max_n
\left[z(V_n)-\lambda z(u^V_n)\right].
\]

Combined:

\[
n^*=\arg\max_n
\left[
z(V_n)-\lambda\left(
w_A z(u^{A,\mathrm{first}}_n)+(1-w_A)z(u^V_n)
\right)
\right].
\]

В основном grid:

\[
N=4,\quad H_{\mathrm{execute}}=16,\quad
\lambda_A\in\{0.5,1,2\},\quad
\lambda_V\in\{1,2\},\quad
\lambda_C\in\{1,2\},\quad
w_A\in\{0.25,0.5,0.75\}.
\]

## 7. Failure и prediction error

Task failure:

\[
F_{\mathrm{task}}=1-S_T,
\]

где \(S_T\) означает выполнение BDDL goal к завершению rollout.

После выполнения chunk сохранялись:

\[
E_I=\operatorname{Mean}
\left(\widehat I_{q+1}-I_{q+1}\right)^2,
\qquad
E_p=\left\|\widehat p_{q+1}-p_{q+1}\right\|_2,
\qquad
E_V=\left|\widehat V_q-y_{q+1}\right|.
\]

Эти ошибки известны только **после** выполнения chunk и не использовались для
выбора action в том же query.

Для online detector односторонний conformal threshold строился только по
successful calibration trajectories. При \(m\) calibration scores:

\[
\tau_\alpha=s_{(k)},\qquad
k=\min\left(m,\left\lceil(m+1)(1-\alpha)\right\rceil\right),
\]

а fail сигнализируется при \(u\ge\tau_\alpha\).

## 8. Результат standard LIBERO

| ID suite | Tasks | Rollout | Success |
|---|---:|---:|---:|
| `libero_spatial` | 0, 5, 8 | 18 | 18 |
| `libero_object` | 1, 7, 9 | 18 | 18 |
| `libero_goal` | 3, 5, 9 | 18 | 18 |
| `libero_10` | 3, 4, 9 | 18 | 18 |
| **Итого** | 12 fixed tasks | **72** | **72 (100%)** |

Wilson 95% CI общего success rate: `[94.9%, 100%]`.

**Вывод.** Standard LIBERO подтверждает корректность model/environment
pipeline, но здесь нет failures для обучения detector или проверки ranking.
Для нашей задачи benchmark практически насыщен.

## 9. Первый LIBERO-PRO screening

| Split | Rollout | Success | Fail | Success rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| Standard LIBERO ID | 72 | 72 | 0 | 100.0% | [94.9%, 100.0%] |
| LIBERO-PRO OOD | 106 | 82 | 24 | 77.4% | [68.5%, 84.3%] |

Fisher exact test ID против выбранных OOD cases: \(p=1.69\cdot10^{-6}\).
Это не unbiased score всего LIBERO-PRO: OOD-конфигурации специально
отбирались как сложные.

### Найденные mixed cases

| Suite/task/init | Success |
|---|---:|
| `libero_spatial_with_milk/task5/init0` | 12/24 |
| `libero_spatial_with_mug/task0/init0` | 8/12 |
| `libero_spatial_with_yellow_book/task8/init0` | 3/6 |
| `libero_spatial_with_yellow_book/task5/init0` | 5/6 |
| `libero_10_with_mug/task4/init0` | 2/4 |
| `libero_10_with_milk/task9/init0` | 3/4 |
| `libero_goal_with_mug/task9/init0` | 3/4 |

Среди 24 fail: 12 `timeout_no_goal`, 11 `target_drop_candidate`,
1 `timeout_partial_goal`.

В leakage-safe окне `query=0..3` лучший exploratory feature был
`latent_action_copy_std_mean_mean_over_samples`, pooled within-group
AUROC `0.671`. Направление `high = failure` совпало в 5/7 групп, было
нейтральным в одной и обратным в одной.

`action_first_step_l2_std`, `value_std`, `value_range` дали соответственно
AUROC `0.512`, `0.537`, `0.522`.

После контроля `suite/task/init_state/query_idx` максимальная содержательная
связь uncertainty с subsequent prediction error была слабой:
\(\rho=0.139\) для future-proprio latent consistency против proprio L2 error.

**Вывод.** H1 поддержана. Internal action-latent consistency стала главным
кандидатом, но universal early detector на Phase 1 не получен.

## 10. Большая LIBERO-PRO validation

Завершены все 23 jobs: 1078 rollout-выполнений, 13351 query rows,
603 success и 475 fail.

### Инвентаризация cases

| Case/split | Выполнения | Success | Fail | Комментарий |
|---|---:|---:|---:|---|
| Direct milk calibration | 36 | 17 | 19 | \(N=5\), denoising traces |
| Direct milk holdout | 36 | 16 | 20 | Независимый seed block |
| Direct mug generalization | 24 | 19 | 5 | Новый OOD object case |
| Direct milk new init states | 30 | 30 | 0 | Слишком лёгкий screen |
| Yellow new init states | 24 | 23 | 1 | Слишком лёгкий screen |
| Milk planning calibration | 232 | 129 | 103 | Повторённые seeds для разных методов |
| Milk planning holdout | 232 | 110 | 122 | Повторённые seeds для разных методов |
| Yellow planning generalization | 194 | 98 | 96 | Повторённые seeds для разных методов |
| Long-mug planning generalization | 124 | 101 | 23 | Повторённые seeds для разных методов |
| Planning ablations | 146 | 60 | 86 | \(N\), query, denoising, AR |

По всем method executions failure labels распределились как
`timeout_no_goal=267`, `target_drop_candidate=196`,
`wrong_object_interaction_candidate=12`.

### 10.1. Direct failure detector

Основной fixed case:
`libero_spatial_with_milk/task5/init0`.
Calibration и holdout содержат по 36 rollout. Все trajectories ещё активны
до `query=5`. Самый ранний физический failure event у fail trajectories
зафиксирован на \(t=169\).

#### Раннее окно

| Exact query | Metric | Calibration AUROC | Holdout AUROC | Вывод |
|---:|---|---:|---:|---|
| 3, \(t=48\) | `action_first_step_l2_std` | 0.514 | 0.616 | Слабый |
| 3, \(t=48\) | `value_std` | 0.495 | 0.653 | Не переносится из calibration |
| 3, \(t=48\) | `value_range` | 0.498 | 0.656 | Не переносится из calibration |
| 3, \(t=48\) | action latent-copy mean | 0.288 | 0.422 | Направление не подтверждено |
| 3, \(t=48\) | flow action dispersion | 0.666 | 0.369 | Направление перевернулось |
| 5, \(t=80\) | flow action dispersion | 0.529 | 0.509 | Случайный уровень |

**Вывод.** В начале эпизода нет стабильного detector, переносимого с
calibration на holdout.

#### Critical-moment сигнал

| Exact query | Alive holdout, fail/success | Metric | Cal AUROC | Holdout AUROC | AUPRC | TPR / FPR при \(\alpha=0.1\) |
|---:|---:|---|---:|---:|---:|---:|
| 8, \(t=128\) | 20/13 | action latent-copy mean | 0.944 | **0.981** | 0.987 | 0.20 / 0.00 |
| 8, \(t=128\) | 20/13 | `value_mean` | 0.996 | **0.923** | 0.868 | 0.85 / 0.077 |
| 9, \(t=144\) | 20/10 | action first-step latent-copy L2 | 0.940 | **0.915** | 0.967 | **0.80 / 0.00** |
| 9, \(t=144\) | 20/10 | action latent-copy mean | 0.801 | **0.840** | 0.908 | 0.30 / 0.00 |

На `query=9` сигнал появляется как минимум за 25 simulator steps до самого
раннего observed failure event. Высокий `value_mean` на `query=8` у будущих
fail является прямым признаком overconfidence, а не uncertainty.

Результат условен на том, что trajectory ещё активна на данном query:
часть successful episodes завершилась раньше. Поэтому это detector
**critical moment among surviving rollouts**, а не prediction из initial
state. Он подтверждён на новом seed block того же task/init, но пока не
подтверждён на другом task.

Exhaustive temporal sweep содержит 205920 combinations. Perfect rows из этого
sweep нельзя считать финальным результатом: перебор большого числа features,
окон и horizons создаёт selection bias, а `all queries` частично кодирует
различную длину success/fail trajectories. Для выводов выше использованы
предварительно выбранные метрики и exact-query comparisons.

### 10.2. Prediction error против реальности

Для `query=0..5` признаки и errors были rank-normalized внутри
`split/query_idx`. Самые большие по модулю correlations:

| Uncertainty | Subsequent error | \(\rho\) |
|---|---|---:|
| action latent-copy mean | wrist image MSE | -0.191 |
| `value_range` | wrist image MSE | -0.185 |
| action latent-copy mean | future proprio L2 | -0.175 |
| action latent-copy mean | value absolute error | +0.175 |
| `action_first_step_l2_std` | agent image MSE | +0.153 |

Все \(|\rho|\le 0.191\), а несколько направлений отрицательны.

**Вывод.** Сильный late failure ranking не означает, что uncertainty является
калиброванной оценкой pixel/proprio prediction error. H3 пока не поддержана.

## 11. Planning: calibration и holdout

### 11.1. Milk, \(N=4\), \(w_A=0.5\)

| Strategy | \(\lambda\) | Calibration | Holdout | Holdout delta vs maxV | Paired W/L/T |
|---|---:|---:|---:|---:|---:|
| `max_value` | 0 | 10/20 | **14/20** | 0 | - |
| action first | 0.5 | 9/20 | 13/20 | -5 pp | 3/4/13 |
| action first | 1 | 12/20 | 11/20 | -15 pp | 3/6/11 |
| action first | 2 | 10/20 | 9/20 | -25 pp | 4/9/7 |
| action chunk mean | 1 | 12/20 | 8/20 | -30 pp | 2/8/10 |
| action chunk max | 1 | 12/20 | 11/20 | -15 pp | 3/6/11 |
| value latent | 1 | 12/20 | 8/20 | -30 pp | 2/8/10 |
| value latent | 2 | 9/20 | 7/20 | -35 pp | 3/10/7 |
| combined | 1 | **13/20** | 5/20 | **-45 pp** | 1/10/9 |
| combined | 2 | **13/20** | 6/20 | -40 pp | 2/10/8 |

Calibration выбрала `combined, lambda=1, w_A=0.5`: 65% против 50% baseline.
После фиксации formula она дала только 25% на holdout против 70% baseline.
Paired exact McNemar/binomial \(p=0.0117\) для 1 win против 10 losses.

Это основной отрицательный результат кампании: подбор статического penalty на
одном seed block сильно переобучился.

### 11.2. Combined weight sweep на milk

| \(w_A\) | \(\lambda\) | Calibration | Holdout |
|---:|---:|---:|---:|
| 0.25 | 1 | 5/8 | 4/8 |
| 0.25 | 2 | 5/8 | 5/8 |
| 0.50 | 1 | 13/20 | 5/20 |
| 0.50 | 2 | 13/20 | 6/20 |
| 0.75 | 1 | 4/8 | 5/8 |
| 0.75 | 2 | 3/8 | 4/8 |

Ни один вес не показывает воспроизводимого улучшения. Крайние веса имеют
только 8 paired rollout и слишком широкую неопределённость.

## 12. Planning: новые OOD cases

### Yellow-book, 18 paired rollout

| Strategy | \(\lambda\) | Success | Delta vs maxV | W/L/T |
|---|---:|---:|---:|---:|
| `max_value` | 0 | 10/18 | 0 | - |
| combined | 1 | **11/18** | +5.6 pp | 3/2/13 |
| action first | 2 | 10/18 | 0 | 5/5/8 |
| action first | 1 | 9/18 | -5.6 pp | 4/5/9 |
| action chunk | 1 | 9/18 | -5.6 pp | 1/2/15 |
| value | 1 | 9/18 | -5.6 pp | 3/4/11 |
| combined | 2 | 9/18 | -5.6 pp | 4/5/9 |
| action first | 0.5 | 7/18 | -16.7 pp | 0/3/15 |
| value | 2 | 7/18 | -16.7 pp | 1/4/13 |

### Long-mug, 12 paired rollout

| Strategy | \(\lambda\) | Success | Delta vs maxV | W/L/T |
|---|---:|---:|---:|---:|
| `max_value` | 0 | 9/12 | 0 | - |
| action first | 0.5 | **11/12** | +16.7 pp | 3/1/8 |
| value | 2 | **11/12** | +16.7 pp | 3/1/8 |
| combined | 1 | 10/12 | +8.3 pp | 2/1/9 |
| action chunk | 1 | 10/12 | +8.3 pp | 2/1/9 |
| value | 1 | 9/12 | 0 | 3/3/6 |
| combined | 2 | 9/12 | 0 | 2/2/8 |
| action first | 1 | 8/12 | -8.3 pp | 2/3/7 |
| action first | 2 | 8/12 | -8.3 pp | 2/3/7 |

Long-mug является наиболее позитивным case, но 3 wins против 1 loss дают
двусторонний exact \(p=0.625\). Это promising pilot, а не доказанное
улучшение.

## 13. Pooled confirmatory planning

Ниже объединены только independent milk holdout, yellow и long-mug:
50 одинаковых rollout seeds на formula, main `parallel N=4` setting.
Calibration milk исключена.

| Strategy | \(\lambda\) | Baseline | Strategy | Delta | W/L/T | Exact \(p\) |
|---|---:|---:|---:|---:|---:|---:|
| action first | 0.5 | 33/50 | **31/50** | -4 pp | 6/8/36 | 0.791 |
| action first | 1 | 33/50 | 28/50 | -10 pp | 9/14/27 | 0.405 |
| action chunk | 1 | 33/50 | 27/50 | -12 pp | 5/11/34 | 0.210 |
| action first | 2 | 33/50 | 27/50 | -12 pp | 11/17/22 | 0.345 |
| value | 1 | 33/50 | 26/50 | -14 pp | 8/15/27 | 0.210 |
| combined | 1 | 33/50 | 26/50 | -14 pp | 6/13/31 | 0.167 |
| value | 2 | 33/50 | 25/50 | -16 pp | 7/15/28 | 0.134 |
| combined | 2 | 33/50 | 24/50 | -18 pp | 8/17/25 | 0.108 |

**Вывод.** Ни одна текущая fixed penalty formula не превосходит
`max(value)` в confirmatory aggregate. Наименее плохой и всё ещё интересный
кандидат - first-action penalty с \(\lambda=0.5\), но его 62% ниже baseline
66%.

## 14. Ablations

| Setting | Baseline | Лучший uncertainty method | Результат | Вывод |
|---|---:|---|---:|---|
| Parallel \(N=2\), execute 16 | 10/16 | combined \(\lambda=1\) | 10/16 | Нет выигрыша |
| Parallel \(N=8\), execute 16 | 3/6 | action/combined \(\lambda=1\) | 3/6 | \(N=8\) не улучшил shared first 6 seeds |
| Parallel \(N=4\), execute 8 | 0/6 | все проверенные | 0/6 | Более частый query не помог на этом seed block |
| Parallel \(N=4\), action denoise 10 | 0/6 | action \(\lambda=1\) | **4/6** | 4 wins, 0 losses, exact \(p=0.125\); требует повторения |
| AR \(N=4\), future/value denoise 3/3 | 3/4 | action \(\lambda=1\) | 3/4 | Выбор совпал по outcome; value penalty 1/4 |
| AR \(N=2\), 2 future x 3 value samples | 0/2 | action \(\lambda=1\) | 0/2 | Слишком мало данных |

По первым шести shared seeds baseline \(N=2\) дал 4/6, а \(N=8\) 3/6.
Следовательно, больше candidates само по себе не гарантирует лучший rollout:
value ranking тоже должен быть надёжным.

Самый интересный ablation - взаимодействие более точного action denoising и
action-risk penalty. Однако выборка \(n=6\) мала, а baseline на ней случайно
получил 0/6, поэтому это отдельная гипотеза для replication, не финальный
метод.

## 15. Safety diagnostics

В большой PRO кампании:

- official violations: 0, поскольку это не LIBERO-Safety;
- `target_drop_candidate`: 300/1078 method executions, из них 196 fail;
- `wrong_object_interaction_candidate`: 15, все 15 завершились fail.

Drop heuristic не универсален. Например, на long-mug он сработал во всех
124 method executions, включая успешные, поэтому его нельзя использовать как
task-independent safety label.

LIBERO-Safety установлен отдельно:

```text
.venv-cosmos-safety
.external/LIBERO-Safety-19ec8df23eedfbb9265bafd3e56495fcebfcfcd0
```

Профили `safety_physical` и `safety_semantic_probe` подготовлены, но manifest
`campaigns/validate_v1/manifest.json` имеет статус `planned`. До их запуска
нельзя делать вывод о collision rate, safe success или safety-aware planning.

## 16. Главные выводы

1. **Нужен OOD benchmark.** Standard LIBERO дал 72/72 и не создаёт полезной
   вариативности outcomes. LIBERO-PRO дал natural success/fail при одинаковых
   task и init state.
2. **Universal early uncertainty detector пока не найден.** В `q=0..5`
   calibration/holdout ranking нестабилен.
3. **Есть воспроизводимый critical-moment сигнал.** На fixed milk case
   action latent-copy inconsistency на \(t=128\) и \(t=144\) переносится на
   holdout; на \(t=144\) conformal detector дал TPR 0.80 при FPR 0.
4. **Обнаружена overconfidence.** На \(t=128\) высокий mean predicted value
   предсказывает fail с holdout AUROC 0.923. Значит, проблема не сводится к
   большому `value_std`: модель может согласованно завышать value.
5. **Uncertainty не равна prediction error.** Связи с subsequent image/proprio
   error малы, поэтому нельзя интерпретировать текущие metrics как
   калиброванную ошибку world model.
6. **Статический penalty не обобщается.** Formula, выигравшая calibration,
   стала существенно хуже на holdout. В pooled 50-rollout comparison все
   fixed penalties не лучше `max(value)`.
7. **Penalty должен быть условным.** Перспективнее не штрафовать каждый query,
   а включать risk-aware re-ranking только при calibrated critical-moment
   trigger, дополнительно увеличивая \(N\), уменьшая execute horizon или
   запрашивая replan.
8. **Нужна task/phase-aware calibration.** Знак и полезность метрик меняются
   по query и task. Один глобальный \(\lambda\) недостаточен.
9. **LIBERO-Safety остаётся обязательной отдельной проверкой.** PRO heuristics
   полезны для диагностики, но не заменяют official constraints.

## 17. Следующий проверяемый метод

Вместо постоянного штрафа:

\[
g_q=\mathbb{1}
\left[
u_q>\tau_{\alpha,\mathrm{task},q}
\right],
\]

\[
n_q^*=
\arg\max_n
\left[
z(V_{q,n})
-g_q\lambda_q z(u^{A,\mathrm{first}}_{q,n})
\right].
\]

То есть `max(value)` остаётся default. Uncertainty penalty включается только
при online risk trigger. Для triggered queries дополнительно проверяется:

\[
N:4\rightarrow 8,\qquad
H_{\mathrm{execute}}:16\rightarrow 4\text{ или }8,
\]

после чего policy быстрее получает новое реальное observation.

Эту формулу следует калибровать только на milk calibration, заморозить и
проверить на:

1. milk holdout;
2. yellow и long-mug без изменения \(\lambda,\tau\);
3. LIBERO-Safety physical suites по task success, safe success и official
   violation rate.

## 18. Таблицы для пересчёта

Основные машинно-читаемые результаты:

- [`planning_strategy_summary.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/planning_strategy_summary.csv);
- [`paired_vs_max_value.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/paired_vs_max_value.csv);
- [`pooled_planning_confirmatory.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/pooled_planning_confirmatory.csv);
- [`prespecified_detector_exact_query.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/prespecified_detector_exact_query.csv);
- [`prediction_error_correlations_q0_5.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/prediction_error_correlations_q0_5.csv);
- [`case_outcome_summary.csv`](campaigns/libero_full_validation_20260724/analysis/full_validation/case_outcome_summary.csv).

Компактные таблицы пересчитываются командой:

```bash
.venv-cosmos/bin/python scripts/summarize_libero_final_results.py \
  --analysis-dir \
  experiments/campaigns/libero_full_validation_20260724/analysis/full_validation
```

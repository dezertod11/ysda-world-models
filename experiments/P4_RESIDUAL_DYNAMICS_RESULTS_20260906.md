# P4: independent residual-dynamics ensemble results

Дата анализа: 6 сентября 2026 года.

## Краткий итог

P4 технически завершён без ошибок, но заранее зафиксированный offline gate дал
**NO-GO**. Собраны 5,668 action-conditioned переходов, обучены пять независимо
инициализированных Gaussian residual heads, рассчитаны OOD-метрики для
LIBERO-PRO Environment, Object и Position и выполнена trajectory-level
conformal calibration.

Primary quadratic Jensen-Renyi score выродился: после предусмотренного
ограничения снизу все 5,668 значений равны нулю. Поэтому его pooled
class-balanced OOD AUPRC равен 0.308, Spearman с realized residual не определён,
а hard filter не изменил ни одного выбора. Closed-loop этап по протоколу не
открывался.

При этом post-hoc ablation дала полезный, но пока не подтверждённый результат:
простая variance of independently trained means,
`ensemble_epistemic_mean`, хорошо связана с фактической ошибкой Cosmos
(`trajectory rho=0.609`) и распознаёт Environment shift (balanced AP 0.795),
но плохо переносится на Object (0.558) и особенно Position (0.387). Значит
ensemble выучил сигнал model error, но не универсальный cross-factor OOD score.

## Проверяемая гипотеза

Для candidate action chunk $a_i$ Cosmos предсказывает endpoint
$(\hat o_{i,t+16},\hat p_{i,t+16})$, а exact MuJoCo replay даёт фактический
endpoint $(o_{i,t+16},p_{i,t+16})$. Frozen CLIP переводит agent/wrist RGB в
признаки. Пять голов моделируют стандартизированный prediction residual:

$$
q_k(r_i\mid x_i)=\mathcal N\!\left(\mu_k(x_i),
\operatorname{diag}(\sigma_k^2(x_i))\right),\qquad k=1,\ldots,5.
$$

Каждая голова имеет отдельную инициализацию и bootstrap по целым trajectories.
Primary uncertainty была зафиксирована как quadratic Jensen-Renyi difference:

$$
U_{\mathrm{JRD}}(x_i)=
H_2\!\left(\frac1K\sum_{k=1}^{K}q_k\right)
-\frac1K\sum_{k=1}^{K}H_2(q_k),
\qquad H_2(q)=-\log\int q(r)^2\,dr.
$$

Для deployment threshold калибруется на максимуме score вдоль ID trajectory:

$$
S_g=\max_{i\in g}U_{\mathrm{JRD}}(x_i),
\qquad
\hat\epsilon=Q^{\mathrm{higher}}_{\lceil(n+1)(1-\alpha)\rceil/n}
(S_1,\ldots,S_n),\quad \alpha=0.1.
$$

Полная постановка, признаки, split contract и gate записаны до вычисления
результатов в
[`P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md`](P4_RESIDUAL_DYNAMICS_PROTOCOL_20260906.md).

## Данные и целостность

| Split / factor | Rows | Trajectory groups | Snapshots |
|---|---:|---:|---:|
| Train, standard LIBERO ID | 1,876 | 148 | 469 |
| Calibration, standard LIBERO ID | 616 | 48 | 154 |
| ID test, standard LIBERO | 708 | 56 | 177 |
| OOD Environment | 1,240 | 148 | 310 |
| OOD Object | 480 | 45 | 120 |
| OOD Position | 748 | 96 | 187 |
| **Всего** | **5,668** | **541** | **1,417** |

- ID collection: 10/10 tasks complete, по 80 NPZ snapshots на task.
- Contract: H16, candidates `K=4`, uncertainty seeds `0,1,2,3`, query indices
  `0,3,6,9`, no feedback branch, no terminal continuation.
- Primary OOD comparison использует тот же query support; 1,564 OOD rows и
  503 total matched-query trajectory groups.
- Split выполняется по целой `suite/task/init/rollout_seed` trajectory; PCA,
  normalization, bootstrap и optimization используют только train.
- Dataset builder не пропустил ни одной строки; deduplication выполняется по
  resolved `(sidecar_path, candidate_idx)`.
- SHA256 manifest, feature archive, frozen heads и metadata проверены локально
  после скачивания и совпадают с сервером.

## Frozen gate

| Условие | Требование | Результат | Решение |
|---|---:|---:|---|
| ID trajectory FPR | $\le 0.15$ | 0.000 | формально PASS, но score константный |
| Pooled OOD balanced AP | $\ge\max(0.65,0.750+0.03)=0.780$ | 0.308 | **FAIL** |
| JRD vs realized residual | Spearman $\ge 0.20$ | NaN | **FAIL** |
| Полный offline gate | все три условия | false | **NO-GO** |

Conformal threshold равен `0.0`; alarm rate равен нулю одновременно на ID,
Environment, Object и Position. Поэтому нулевой ID FPR не является успехом
калибровки: detector просто ни разу не срабатывает.

## Сравнение uncertainty scores

Ниже приведён preregistered query-support-matched trajectory comparison.
Balanced AP использует одинаковую суммарную массу ID и OOD классов.

| Metric | Environment | Object | Position | Pooled OOD | $\rho$ с realized residual |
|---|---:|---:|---:|---:|---:|
| Quadratic JRD, primary | 0.309 | 0.314 | 0.310 | 0.308 | NaN |
| **Independent mean disagreement** | **0.795** | 0.558 | 0.387 | 0.648 | **0.609** |
| Ensemble total variance | 0.597 | 0.393 | 0.659 | 0.594 | 0.528 |
| `value_range` | 0.793 | 0.667 | 0.659 | 0.743 | 0.293 |
| `latent_value_across_seed_std_mean` | 0.790 | **0.713** | 0.666 | **0.750** | 0.285 |
| Future-image pixel std | 0.766 | 0.547 | **0.693** | 0.714 | 0.389 |

Главное различие между задачами:

1. В Environment independent epistemic disagreement почти сравнялся с лучшими
   прежними метриками и имеет terminal-failure AUROC 0.716.
2. В Object он слабее latent-value disagreement; terminal-failure AUROC 0.550.
3. В Position направление частично переворачивается: OOD balanced AP 0.387 и
   terminal-failure AUROC 0.376.
4. Pooled число скрывает эту неоднородность. Один global threshold для трёх
   perturbation families пока не обоснован.

## Почему JRD выродился

Следующая диагностика выполнена после frozen decision и не меняет primary
результат. Аналитическая формула до `max(0, ...)` дала отрицательное значение
для всех 5,668 строк:

| Raw JRD statistic | Значение |
|---|---:|
| min | -94.313 |
| p01 / p10 | -72.509 / -44.615 |
| median | -22.536 |
| p90 / p99 | -8.701 / -3.093 |
| max | -0.304 |

Средние raw значения: ID `-23.04`, Environment `-29.99`, Object `-34.58`,
Position `-18.96`. После frozen nonnegative clamp они все стали нулями.

Это не ошибка Gaussian cross-integral: использованная формула совпадает с
quadratic-Renyi construction в исходном прототипе. Проблема в том, что разность
quadratic Renyi entropies не обязана быть неотрицательной для компонентов с
сильно различающимися covariance. В нашем ensemble median отношения
максимальной к минимальной средней variance голов равна 5.04, p90 13.85,
p99 37.34 и max 126.86. Следовательно, heteroscedastic heads находятся именно
в режиме, где последующее clamping уничтожает ранжирование.

## Качество вероятностной модели

| Диагностика | Результат |
|---|---:|
| Train NLL голов | от -1.34 до -1.25 |
| OOB NLL голов | от 8.34 до 17.12 |
| Mixture NLL median, train | -39.98 |
| Mixture NLL median, calibration / ID test | 130.49 / 121.27 |
| Mixture NLL median, Environment | 12,019.58 |
| Mixture NLL median, Object / Position | 416.95 / 203.32 |

Большой train-to-OOB разрыв показывает переобучение и плохую calibration
предсказанных variance. Поэтому aleatoric/JRD часть текущей модели не должна
использоваться как вероятность риска, даже несмотря на полезный disagreement
между mean predictions.

## Offline hard-filter limitation

Historical OOD atlas оказался вырожденным для within-snapshot action ranking:

| Factor | Candidate rows | Nonzero local utility | Local successes | Snapshots с разными utilities |
|---|---:|---:|---:|---:|
| Environment | 1,240 | 8, все `-0.5` | 0 | 0/310 |
| Object | 480 | 0 | 0 | 0/120 |
| Position | 748 | 0 | 0 | 0/187 |

Поэтому offline hard filter не мог проверить causal reranking даже при хорошем
score: внутри каждого snapshot все candidates имеют одинаковую local utility.
Фактически он изменил 0/391 matched-query selections и получил delta 0.

## Выводы

1. **Исходная P4 архитектура закрывается.** Heteroscedastic quadratic JRD не
   годится как nonconformity score в наблюдаемом режиме; closed-loop rollout
   для неё не запускается.
2. **Независимое обучение голов всё же добавило информацию.** Variance их mean
   predictions связана с realized world-model error заметно сильнее прежних
   stochastic-copy метрик: trajectory $\rho=0.609$ против 0.285 у лучшего
   latent-value baseline.
3. **Model-error detection и fail prediction не эквивалентны.** Хорошая
   residual correlation не дала устойчивой terminal-failure или cross-factor
   ranking. Нужны task-critical targets и causal candidate outcomes.
4. **OOD mechanism factor-specific.** Environment похоже на epistemic feature
   shift, тогда как Object и Position требуют object/contact/geometry signals
   или factor-aware calibration.
5. **Следующая версия должна сначала пройти новый offline gate.** Нельзя
   выбирать новую метрику по этому уже открытому atlas и затем называть её
   confirmatory.

## Следующий проверяемый шаг: P4b

Дешёвый development stage переиспользует frozen features и heads и сравнивает:

1. `ensemble_epistemic_mean` как простой error score;
2. common-covariance/equalized-variance JRD ablation;
3. гарантированно неотрицательную Monte Carlo Jensen-Shannon / predictive
   mutual-information estimate для Gaussian mixture;
4. early stopping, shared aleatoric variance и variance regularization.

Calibration должна быть factor-aware только если это фиксируется до нового
теста. Выбор формулы и threshold выполняется на development/calibration;
подтверждение требует свежего untouched OOD split с реальной вариативностью
candidate outcomes. Closed-loop hard-filter planning разрешается только после
повторного offline gate.

## Артефакты

- `campaigns/p4_residual_dynamics_20260906/sequence_status.json`
- `campaigns/p4_residual_dynamics_20260906/dataset/split_counts.csv`
- `campaigns/p4_residual_dynamics_20260906/analysis/summary.json`
- `campaigns/p4_residual_dynamics_20260906/analysis/ood_detection_metrics.csv`
- `campaigns/p4_residual_dynamics_20260906/analysis/prediction_error_correlations.csv`
- `campaigns/p4_residual_dynamics_20260906/analysis/terminal_failure_detection.csv`
- `campaigns/p4_residual_dynamics_20260906/analysis/offline_hard_filter.csv`
- `campaigns/p4_residual_dynamics_20260906/analysis/ood_detection_average_precision.png`
- `campaigns/p4_residual_dynamics_20260906/analysis/jrd_group_distributions.png`
- `campaigns/p4_residual_dynamics_20260906/analysis/jrd_vs_realized_residual.png`
- `frozen_models/p4_residual_dynamics_20260906/SHA256SUMS`


# Полная восьмичасовая проверка uncertainty-aware planning

Дата фиксации протокола: 24 июля 2026 года.

> **Результат запуска.** Кампания завершена: 23/23 jobs, 1078
> rollout-выполнений, 13351 query rows. Итоговый критический анализ находится
> в [`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md),
> сырые таблицы - в
> [`campaigns/libero_full_validation_20260724/analysis/full_validation/`](campaigns/libero_full_validation_20260724/analysis/full_validation/).

## 1. Цель

Эта кампания проверяет уже реализованные гипотезы до следующего изменения
метода:

1. Предсказывают ли online uncertainty-метрики eventual failure.
2. Переносится ли выбранный сигнал на новый seed block и новые OOD-задачи.
3. Улучшает ли реальный candidate ranking обычный `max(value)`.
4. Как результат зависит от числа candidates, частоты query, denoising steps,
   способа агрегации action uncertainty и режима генерации value.

Основной конфиг:
[`libero_campaign_8h.json`](configs/libero_campaign_8h.json).

## 2. Что перенесено из статей

### UQ for Flow-Based VLA

[Roemer et al., 2026](https://arxiv.org/abs/2606.18043) оценивают flow
velocity dispersion (VFD) на каждом action query и калибруют односторонний
conformal threshold по успешным rollout. Поэтому у нас:

- отдельные `calibration` и `holdout` seed blocks;
- пять stochastic samples в direct detector;
- denoising trace и flow-path metrics;
- пороги `alpha = 0.05, 0.10, 0.20`;
- порог строится только по successful calibration episodes.

Их двухмодельный ensemble здесь не воспроизводится: используется один
checkpoint Cosmos Policy с разными diffusion seeds. Это aleatoric/stochastic
disagreement, а не полноценная epistemic uncertainty.

### Shifting Uncertainty to Critical Moments

[Tang et al., 2026](https://arxiv.org/abs/2603.18342) показывают, что среднее
по эпизоду скрывает короткие всплески uncertainty. Поэтому offline sweep
включает:

\[
u_q,\qquad
\max_{i\le q}u_i,\qquad
\max_{q-W<i\le q}u_i,\qquad
\frac{1}{W}\sum_{q-W<i\le q}u_i,\qquad
\Delta u_q=u_q-u_{q-1},
\]

где \(W\in\{2,3,4,6\}\), а early horizons равны
\(q\in\{0,1,2,3,5,7,10,\text{all}\}\).

### Cosmos Policy

[Agarwal et al., 2026](https://arxiv.org/abs/2601.16163) описывают
best-of-\(N\) planning с цепочкой

\[
a^{(n)} \sim p(a\mid o,l),\qquad
\hat s^{(n)} \sim p(s'\mid o,l,a^{(n)}),\qquad
\hat v^{(n)} \sim p(v\mid o,l,a^{(n)},\hat s^{(n)}).
\]

Кампания явно разделяет:

- `parallel`: action, future state и value извлекаются из одной diffusion
  последовательности;
- `autoregressive`: выполняется отдельная цепочка
  `action -> future state -> value`.

Полный paper-scale вариант \(N=8\), 3 future samples и 5 value samples на
каждый future слишком дорог для статистического LIBERO-теста. Поэтому он
проверяется как reduced AR ablation; основной statistically powered grid
использует быстрый parallel режим.

### SUREFlow

[Islam et al., 2026](https://arxiv.org/abs/2607.10504) мотивируют
dimension-aware uncertainty. У нас отдельно сравниваются:

- uncertainty первого action-вектора;
- средняя uncertainty всего 16-step chunk;
- максимальная uncertainty элемента chunk;
- value uncertainty;
- action/value composite.

## 3. Planning scores

Базовый выбор:

\[
n^*_{\max V}=\arg\max_n z(\hat v_n).
\]

Action penalty:

\[
n^*=\arg\max_n\left[z(\hat v_n)-\lambda z(u^a_n)\right].
\]

Value penalty:

\[
n^*=\arg\max_n\left[z(\hat v_n)-\lambda z(u^v_n)\right].
\]

Composite:

\[
n^*=\arg\max_n\left[
z(\hat v_n)-\lambda\left(
w_a z(u^a_n)+(1-w_a)z(u^v_n)
\right)\right].
\]

Перебираются:

- \(\lambda_a\in\{0.5,1,2\}\);
- \(\lambda_v\in\{1,2\}\);
- \(\lambda_c\in\{1,2\}\);
- \(w_a\in\{0.25,0.5,0.75\}\);
- first-step, chunk-mean и chunk-max action aggregation.

Все scores стандартизируются только внутри текущего candidate set. Это
candidate ranking, а не глобальный classifier failure.

## 4. Задачи и splits

Основная calibration/holdout пара:

- `libero_spatial_with_milk`, task 5, init state 0;
- 20 rollout на method в calibration;
- независимые 20 rollout на method в holdout;
- одинаковые rollout seeds внутри сравниваемых methods.

Generalization:

- `libero_spatial_with_yellow_book`, task 8, init 0;
- новые init states 1 и 2;
- `libero_10_with_mug`, task 4, init 0.

Direct failure detector:

- 36 calibration и 36 holdout rollout;
- \(N=5\) stochastic samples;
- VFD/denoising traces;
- дополнительные milk init states и mug OOD.

Ablations:

- \(N\in\{2,4,8\}\);
- execute 8 против 16 действий до следующего query;
- 5 против 10 action denoising steps;
- parallel против autoregressive prediction;
- AR ensemble: 2 future-state и 3 value samples.

Итого запланировано 1078 rollout-выполнений. Они распределены по GPU 2-7
с учетом длины задачи и стоимости AR, а не поровну по числу rollout.

## 5. Честный выбор метода

1. На `calibration` выбираются metric, temporal aggregation, horizon,
   \(\lambda\) и \(w_a\).
2. Conformal threshold оценивается только по successful calibration
   episodes.
3. После выбора параметры фиксируются.
4. Финальные AUROC, AUPRC, TPR, FPR, balanced accuracy и success rate
   считаются на `holdout`.
5. Для planning дополнительно считаются paired wins/losses на одинаковых
   rollout seeds против `max(value)`.
6. `generalization` не используется для подбора коэффициентов.

## 6. Запуск на сервере

Из корня проекта:

```bash
LIBERO_8H_RUN_PREFIX=libero_full_validation_20260724 \
LIBERO_8H_GPUS=2,3,4,5,6,7 \
nohup ./scripts/run_libero_8h_validation.sh \
  > experiments/campaigns/libero_full_validation_20260724.nohup.log 2>&1 &
```

GPU 0 не используется. В каждой GPU-очереди работает один MuJoCo/model
процесс, поскольку CPU сервера уже загружен другими задачами.

Статус:

```bash
.venv-cosmos/bin/python scripts/status_libero_8h_validation.py \
  --campaign-dir experiments/campaigns/libero_full_validation_20260724
```

При повторном запуске с тем же `RUN_PREFIX` completed jobs пропускаются, а
незавершенный trace продолжается с первого отсутствующего `rollout_id`.

## 7. Артефакты

Для каждого запуска сохраняются:

- query traces в CSV и Parquet;
- metadata и completion marker;
- prediction error после выполнения chunk;
- safety/progress/drop diagnostics;
- per-job analysis и логи.

После завершения автоматически создаются:

- `planning_strategy_summary.csv`;
- `paired_vs_max_value.csv`;
- `temporal_conformal_detector_sweep.csv`;
- `selected_on_calibration_holdout_results.csv`;
- графики и итоговый `README.md`.

Финальный каталог:

```text
experiments/campaigns/<RUN_PREFIX>/analysis/full_validation/
```

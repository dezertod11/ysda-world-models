# Temporal overlap: passive campaign 2026-08-21

Статус: реализация завершена, сначала запускается smoke test, затем основная
кампания. Этот файл фиксирует протокол до просмотра результатов.

## Гипотеза

Cosmos Policy предсказывает chunk длины $H=16$, но исполняет только первые
$K=8$ действий. На следующем query сравниваются два прогноза для одних и тех
же абсолютных моментов времени:

$$
X_q=A_q[8:16],
\qquad
Y_{q+1}=A_{q+1}[0:8].
$$

Рост disagreement до первого физического события может быть ранним сигналом
`drop`, safety violation или wrong-object interaction. В passive campaign
этот score только записывается и не влияет на `max(value)` selection.

## Замороженная конфигурация

| Параметр | Значение |
|---|---:|
| Policy | Cosmos Policy LIBERO Predict2 2B |
| Planning strategy | `max_value` |
| Action horizon $H$ | 16 |
| Executed prefix $K$ | 8 |
| Stochastic candidates $B$ | 4 |
| Action denoising steps | 10 |
| Future/value denoising steps | 1/1 |
| Candidate seed offsets | `0,1,2,3` |
| Main rollouts | 20 per case |
| Coupled ablation | 6 per case |
| Calibration alpha | 0.05 |
| Event horizons | 8, 16, 32 simulator steps |

Полные тензоры сохраняются в compressed sidecars:

$$
\texttt{candidate\_actions\_raw}\in
\mathbb R^{Q\times B\times16\times7}.
$$

CSV/Parquet содержит scalar distances, query timestamps, selected candidate,
prediction errors и причинно корректную разметку относительно первого
физического события. Query после события исключаются из early-warning test.

## Splits и cases

Calibration threshold строится только по successful queries шести известных
cases:

| Case | Suite / task / init | Max steps |
|---|---|---:|
| milk | `libero_spatial_with_milk / 5 / 0` | 220 |
| yellow book | `libero_spatial_with_yellow_book / 8 / 0` | 220 |
| long mug | `libero_10_with_mug / 4 / 0` | 520 |
| spatial mug | `libero_spatial_with_mug / 0 / 0` | 220 |
| long milk | `libero_10_with_milk / 9 / 0` | 520 |
| goal mug | `libero_goal_with_mug / 9 / 0` | 320 |

Frozen threshold переносится на шесть OOD holdout cases:

| Factor | Suite / task / init | Max steps |
|---|---|---:|
| long spatial swap | `libero_10_swap / 4 / 0` | 520 |
| goal perturbation | `libero_goal_task / 6 / 0` | 300 |
| object position | `libero_spatial_object / 0 / 0` | 220 |
| object appearance | `libero_object_object / 7 / 0` | 280 |
| language | `libero_spatial_lan / 6 / 0` | 220 |
| spatial swap | `libero_spatial_swap / 8 / 0` | 220 |

Main режим использует независимые query seeds. Coupled ablation повторяет те
же cases и первые шесть rollout seeds, но sample $i$ получает один и тот же
seed на соседних query. Режимы анализируются раздельно.

## Primary endpoints

Для каждого query до события:

$$
Y_q^{(R)}=
\mathbb 1\{0<t_{event}-t_q\le R\},
\qquad R\in\{8,16,32\}.
$$

Основные показатели:

1. query-level AUPRC, затем AUROC;
2. TPR и FPR при frozen 95% calibration threshold;
3. event detection rate и median lead time;
4. false-alarm rate на уровне no-event episodes;
5. terminal fail separation только как secondary endpoint.

Сравниваются selected TIDE-style RMSE, support, switch gap, Chamfer, energy,
MMD, normalized mean shift и существующие action/value/latent uncertainty
signals. Prediction error прошлого chunk сдвигается на следующий query, чтобы
оставаться online feature.

## Integrity gates

Перед основной кампанией smoke run обязан подтвердить:

- форму action tensor `[Q,4,16,7]`;
- точное совпадение query times и executed steps между Parquet и NPZ;
- пересчёт `overlap_selected_rmse` из sidecar с tolerance `1e-7`;
- $A_q[K:K+L]$ сопоставляется с $A_{q+1}[0:L]$;
- coupled seeds не меняются между query;
- число фактически отправленных actions равно сумме `executed_steps`;
- pre-event labels равны условию $t_q<t_{event}$.

## Артефакты и запуск

- Config: `experiments/configs/libero_campaign_temporal_overlap_passive.json`
- Collector metric code: `cosmos_policy/.../libero/temporal_overlap.py`
- Analyzer: `scripts/analyze_temporal_overlap_campaign.py`
- Integrity validator: `scripts/validate_temporal_overlap_artifacts.py`
- Launcher: `scripts/run_temporal_overlap_passive_campaign.sh`

Smoke:

```bash
TEMPORAL_OVERLAP_PROFILE=temporal_overlap_smoke \
TEMPORAL_OVERLAP_RUN_PREFIX=temporal_overlap_smoke_20260821 \
TEMPORAL_OVERLAP_GPUS=2 \
scripts/run_temporal_overlap_passive_campaign.sh
```

Main:

```bash
TEMPORAL_OVERLAP_PROFILE=temporal_overlap_passive \
TEMPORAL_OVERLAP_RUN_PREFIX=temporal_overlap_passive_20260821 \
TEMPORAL_OVERLAP_GPUS=2,3,4,5,6,7 \
scripts/run_temporal_overlap_passive_campaign.sh
```

Положительный passive результат ещё не доказывает улучшение planning. После
заморозки detector и threshold нужен paired closed-loop test с `h=4` или
candidate reranking только при alarm.

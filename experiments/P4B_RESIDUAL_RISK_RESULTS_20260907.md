# P4b residual-risk candidate selection: results

Дата анализа: 7 сентября 2026 года.

Статус: **completed_no_go**. Closed-loop planner не запускался, как и требовал
frozen protocol.

## Постановка

P4b проверял, можно ли заменить чистый выбор `max(value)` на штраф за
предсказанную ошибку world model. Для каждого candidate residual ensemble
предсказывает standardized residual vector между Cosmos prediction на горизонте
H16 и фактическим MuJoCo endpoint. Замороженной development-формулой стал

$$
R_j=\sqrt{\frac{1}{D}\sum_{d=1}^{D}
\left(\bar\mu_{j,d}^{,2}+\operatorname{Var}_{k}\mu_{k,j,d}\right)},
$$

$$
j^*=\arg\max_j\left[
z_{\mathrm{pool}}(\hat v_j)-2,z_{\mathrm{pool}}\!\left(\log(R_j+10^{-12})\right)
\right].
$$

Здесь $\bar\mu$ -- средний предсказанный residual пяти независимо обученных
heads, а variance по heads -- epistemic disagreement. Нормализация выполняется
только среди четырёх candidates одного snapshot.

Prospective holdout был открыт после SHA256-freeze selector. Он содержит 200
новых query-3 snapshots и 800 terminal branches: 40 Environment, 40 Object и
120 Position states. Все четыре H16 candidates выполнялись из одного captured
MuJoCo state и затем продолжались общей K1 Cosmos policy до success или
`t=280`.

## Целостность

| Проверка | Результат |
|---|---:|
| Campaign jobs | 6/6 completed |
| Candidate rows | 800/800 |
| Complete K4 snapshots | 200/200 |
| Terminal outcomes | 800/800 |
| Heterogeneous success/fail snapshots | 33 |
| Factors с не менее чем 5 heterogeneous states | 3/3 |
| Replay error $\le 10^{-9}$ | 194/200 |
| Maximum replay error | $3.93\cdot10^{-4}$ |

Frozen exact-replay gate формально не пройден из-за шести snapshots. Это не
меняет efficacy-вывод: на strict 194-state subset SR меняется с 57.22% до
55.15%, то есть `-2.06 п.п.`, с теми же 4 rescues и 8 harms.

## Development freeze

На открытом P4 corpus было сравнено четыре ensemble variants, семь scores и
четыре значения $\lambda$. Из 64 combinations development gate прошли 12.
Выбранный `p4_original / mean_plus_epistemic_rms / lambda=2` имел:

- candidate Spearman с realized standardized residual: 0.525;
- selection-change rate: 60.36%;
- mean residual delta: `-0.0163`, или `-1.51%`;
- отрицательный residual delta отдельно на Environment, Object и Position.

Новые heteroscedastic early-stopped heads не улучшили перенос: их mean-risk
correlations на development стали отрицательными. Shared-variance MSE ensemble
дал сильные diagnostic common-covariance JRD и OOD detection, но эти scores не
прошли заранее заданный selector contract.

## Primary terminal result

| Factor | N | max(value) | Frozen P4b | Oracle K4 | Delta | 95% group CI | Rescue / harm |
|---|---:|---:|---:|---:|---:|---:|---:|
| Environment | 40 | 31 (77.5%) | 32 (80.0%) | 37 (92.5%) | +2.5 п.п. | [0.0; +7.5] | 1 / 0 |
| Object | 40 | 20 (50.0%) | 18 (45.0%) | 28 (70.0%) | -5.0 п.п. | [-20.0; +7.5] | 3 / 5 |
| Position | 120 | 66 (55.0%) | 63 (52.5%) | 66 (55.0%) | -2.5 п.п. | [-5.83; 0.0] | 0 / 3 |
| **All** | **200** | **117 (58.5%)** | **113 (56.5%)** | **131 (65.5%)** | **-2.0 п.п.** | **[-5.5; +1.5]** | **4 / 8** |

Exact McNemar $p=0.388$. Drop proxy уменьшился на один случай (`-0.5 п.п.`),
official safety не изменился. Efficacy gate не пройден: delta отрицательна,
нижняя CI отрицательна, а harms вдвое больше rescues.

## Почему хороший risk detector не стал хорошим planner

На всех 800 candidates frozen risk выглядит полезно:

- terminal-failure AUROC: 0.650;
- class-balanced AP: 0.641;
- failure rate по risk quartiles: 22.0%, 46.0%, 53.5%, 51.5%.

Но это в основном **межсценарный** сигнал сложности. Easy Position `x0.1` и
`y0.1` имеют низкий risk и почти всегда success; `x0.3` всегда fail, а `y0.3`
fail в 89.2% branches и имеет высокий risk. Внутри одного heterogeneous
snapshot вероятность поставить failure выше success равна только 0.509 по 114
success/fail candidate pairs. Factor-wise AUROC также нестабилен:

| Factor | Candidate failure AUROC | Within-pool failure ranking |
|---|---:|---:|
| Environment | 0.542 | 0.375 |
| Object | 0.407 | 0.547 |
| Position | 0.813 | 0.538 |
| All | 0.650 | 0.509 |

То есть score распознаёт, что **состояние или cell трудные**, но почти не
отвечает на более важный для planning вопрос: **какое действие из одного и того
же состояния причинно лучше**.

Это подтверждает прямой mechanism check. Frozen selector успешно снизил
realized H16 residual на 2.14% на новом holdout: Environment `-1.46%`, Object
`-1.28%`, Position `-2.66%`. Несмотря на это, terminal SR снизился на 2 п.п.
Минимальная ошибка world model не эквивалентна task success: безопасно
предсказуемое действие может не выполнить grasp/placement, а успешная
манипуляция может иметь большой visual/proprio residual.

## Opportunity и агрессивность переключения

P4b изменил выбор в 121/200 states (60.5%), хотя terminal outcome изменился
только в 12 случаях. В K4 pool было 14 состояний, где max-value fail можно было
спасти, и 19 состояний, где уход от успешного max-value мог навредить. Selector
нашёл 4/14 rescues, но реализовал 8/19 возможных harms.

Особенно важен Position: oracle K4 равен baseline, поэтому в этом наборе нет ни
одного состояния, которое candidate reranking могло спасти. Тем не менее P4b
переключался в 60% Position states и создал три fail. Для `x0.3`, где все
candidates fail, нужен новый proposal/recovery, а не другой ranking score.

## Post-hoc diagnostics

После открытия labels были проверены остальные заранее вычисляемые scores.
Это **не confirmatory result и не основание выбирать новый hyperparameter на
этом holdout**.

Наиболее интересный exploratory вариант использовал expected residual

$$
R_{\mathrm{expected}}=
\sqrt{\frac1D\sum_d\left(
\bar\mu_d^2+\operatorname{Var}_k\mu_{k,d}+\bar\sigma_d^2
\right)}
$$

с $\lambda=0.5$. Он переключался только в 21.5% states и дал 117/200 ->
119/200, `+1.0 п.п.`, CI `[-1.0; +3.0]`, 3 rescues / 1 harm, McNemar
$p=0.625$. Эффект мал, CI пересекает ноль и формула выбрана после просмотра
outcomes, поэтому её можно считать только новой гипотезой для будущего split.

Shared-variance MSE ensemble достиг post-hoc failure balanced AP 0.761 и
residual Spearman 0.474, но его within-pool ranking остался 0.509. Это ещё раз
показывает разницу между global difficulty detection и candidate selection.

Полные exploratory таблицы:

- `terminal_holdout_analysis/posthoc_all_variant_metric_diagnostics.csv`;
- `terminal_holdout_analysis/posthoc_all_variant_selector_diagnostics.csv`.

## Решение

1. **Закрыть** прямое использование predicted residual/epistemic uncertainty
   как additive penalty для выбора action candidate. Frozen P4b gate дал
   однозначный NO-GO.
2. **Сохранить** residual risk как state-level alarm: он подходит для оценки
   сложности, OOD, выделения compute и запуска re-query/recovery, но не для
   безусловного reranking.
3. Следующий candidate-level model должен предсказывать task-critical terminal
   advantage относительно max-value: success, grasp/contact loss, drop,
   wrong-object и no-progress. Обучение должно быть pairwise/listwise и
   group-centered внутри одного exact-state candidate pool.
4. Selector должен быть conservative: оставлять max-value по умолчанию и
   переключаться только при положительной calibrated lower confidence bound
   преимущества. Отдельный opportunity head должен оценивать, есть ли вообще
   heterogeneous outcomes в pool.
5. Новый сбор следует концентрировать на Object и Environment states с oracle
   gap. Для all-fail Position нужна новая action proposal/recovery family.
6. До следующего confirmatory test надо восстановить 200/200 replay integrity;
   текущие шесть отклонений не меняют P4b вывод, но нарушают frozen contract.

## Артефакты

- primary summary: `campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/summary.json`;
- factor/case table: `campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/factor_case_summary.csv`;
- paired choices: `campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/paired_selections.csv`;
- candidate scores: `campaigns/p4b_residual_risk_20260907/terminal_holdout_analysis/candidate_scores.parquet`;
- frozen selector: `campaigns/p4b_residual_risk_20260907/development/frozen_selector.json`;
- plots: `terminal_success_comparison.png` and
  `candidate_risk_by_terminal_outcome.png` in the terminal analysis directory.

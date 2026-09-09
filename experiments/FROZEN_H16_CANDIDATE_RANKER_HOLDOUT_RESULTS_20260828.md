# Frozen H16 candidate ranker: held-out result

Дата результата: 28 августа 2026 года.

Статус: **confirmatory offline gate пройден**. Это подтверждение выбора
candidate по фактически измеренному H16 consequence, но ещё не подтверждение
роста terminal success rate в closed loop.

## Краткий итог

Factor-specific ridge был полностью заморожен до сбора holdout: не менялись
features, коэффициенты, `alpha=1`, H16 target или replay threshold. На 230
strict states из 69 новых `task/init` groups он уменьшил factor-macro regret
относительно Cosmos `argmax(value)`:

$$
0.008998 \rightarrow 0.005124,
\qquad -43.1\%.
$$

Primary contrast равен

$$
\Delta_{macro}=-0.003874,
\qquad 95\%\ CI=[-0.005768,-0.002298].
$$

Point estimate улучшился на каждом factor, train/holdout overlap равен нулю,
и preregistered gate прошёл. Самое сильное отдельное подтверждение получено на
`Position`: regret уменьшился на 66.6%, а individual 95% CI целиком ниже нуля.
Для `Environment` и `Object` знак положительный, но их отдельные интервалы ещё
пересекают ноль.

## Что именно выбиралось

Для одного реального simulator state Cosmos генерировал шесть stochastic
action chunks. Для candidate $j$ и feature $m$ выполнялась нормализация внутри
этой шестёрки:

$$
z_{jm}=\frac{x_{jm}-\operatorname{mean}_k x_{km}}
{\max(\operatorname{std}_k x_{km},10^{-8})}.
$$

Для каждого OOD factor использовалась своя заранее замороженная linear head:

$$
S_f(j)=\hat\beta_f^\top \tilde z_j,
\qquad
j^*_{ranker}=\arg\max_j S_f(j).
$$

Модель использует 11 online-доступных признаков: Cosmos value, нормы первого
action и всего action chunk, latent-copy inconsistency для action,
future-proprio и value. Никакая фактическая H16 consequence не подаётся ranker
при выборе.

После выбора каждый candidate отдельно исполнялся 16 simulator steps из точно
одного runtime snapshot. Ranking target:

$$
G_{16}=2I_{success}+\Delta progress+D_{phase}
-I_{drop}-0.5I_{wrong}-I_{violation},
$$

где $D_{phase}$ объединяет нормированные изменения target-goal distance,
target-EEF distance и lift. Regret метода $m$:

$$
R_i(m)=\max_jG_{16,ij}-G_{16,i,j_m}.
$$

Primary statistic сначала усредняет regret внутри `task/init`, затем между
независимыми groups. Интервалы построены grouped bootstrap из 5000 resamples.

## Данные и integrity

Sampling schedule был outcome-independent: доступные queries
$q\in\{0,3,6,9\}$. Phase сохранялась только для анализа. Source rollout
останавливался после последнего scheduled query, поэтому terminal outcome не
входит в target.

| Factor | All states | Strict states | Groups | Replay failures | Фактически покрытые tasks |
|---|---:|---:|---:|---:|---|
| Environment | 80 | 75 | 23 | 5 | 2-6 |
| Object | 80 | 75 | 26 | 5 | 2-7 |
| Position | 80 | 80 | 20 | 0 | x: 2-3; y: 6-7 |
| **Total** | **240** | **230** | **69** | **10** | |

Strict replay rule был зафиксирован заранее:

$$
\texttt{main\_open\_replay\_state\_max\_abs}\le 10^{-9}.
$$

Максимальные расхождения составили `4.73e-5` для Environment, `1.59e-2` для
Object и `1.89e-14` для Position. Все десять imperfect states исключены только
из primary strict analysis; all-state sensitivity опубликован отдельно.

Config разрешал более широкие task ranges, но collector достиг заданного числа
states до поздних task IDs. Поэтому tasks Environment 7-9, Object 8-9 и
Position x 4-5 / y 8-9 остаются чистым следующим evaluation set.

## Primary strict result

| Factor | Cosmos regret | Frozen regret | Снижение | $\Delta=R_{frozen}-R_{Cosmos}$ | 95% CI | $P(\Delta<0)$ |
|---|---:|---:|---:|---:|---:|---:|
| Environment | 0.011189 | 0.009271 | 17.1% | -0.001918 | [-0.003928, +0.000301] | 0.957 |
| Object | 0.002582 | 0.001683 | 34.8% | -0.000898 | [-0.002249, +0.000443] | 0.906 |
| Position | 0.013223 | 0.004418 | 66.6% | -0.008805 | [-0.014010, -0.004690] | 1.000 |
| **Factor macro** | **0.008998** | **0.005124** | **43.1%** | **-0.003874** | **[-0.005768, -0.002298]** | **1.000** |

Графики:

- [`frozen_ranker_strict/heldout_candidate_regret.png`](campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/analysis/frozen_ranker_strict/heldout_candidate_regret.png);
- [`frozen_ranker_strict/heldout_regret_delta_ci.png`](campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/analysis/frozen_ranker_strict/heldout_regret_delta_ci.png).

Top-1 oracle candidate выбирался чаще на Environment и Position:

| Factor | Cosmos top-1 | Frozen top-1 | Random top-1 |
|---|---:|---:|---:|
| Environment | 18.7% | 37.3% | 16.0% |
| Object | 33.3% | 33.3% | 16.0% |
| Position | 11.3% | 28.8% | 21.3% |

Одинаковая Object top-1 accuracy не означает отсутствие эффекта: frozen
ranker выбирал менее плохой candidate в случаях, где оба метода пропускали
oracle, поэтому mean regret всё равно уменьшился.

## Насколько результат распределён по данным

### State-level выбор

| Factor | Frozen лучше | Одинаковый regret | Frozen хуже | Тот же candidate |
|---|---:|---:|---:|---:|
| Environment | 39 | 18 | 18 | 21.3% |
| Object | 25 | 27 | 23 | 33.3% |
| Position | 55 | 4 | 21 | 5.0% |

### Independent-group signs

| Factor | Лучше | Равенство | Хуже |
|---|---:|---:|---:|
| Environment | 17 | 0 | 6 |
| Object | 13 | 1 | 12 |
| Position | 18 | 0 | 2 |

Object остаётся наиболее неоднородным factor: aggregate regret улучшается, но
число выигравших и проигравших groups почти одинаково. Это аргумент за guard
или дополнительную Object calibration, а не за немедленное универсальное
включение ranker.

## Диагностика механизма

Средняя within-state Spearman correlation с фактическим $G_{16}$:

| Factor | Cosmos value | Frozen score |
|---|---:|---:|
| Environment | 0.122 | 0.332 |
| Object | 0.260 | 0.349 |
| Position | -0.245 | 0.277 |

На Position исходный value в среднем ранжировал candidates в неправильном
направлении, тогда как комбинация action/proprio/value latent signals меняла
знак ordering. Это наиболее ясное объяснение крупного Position gain.

Query-wise Position delta был отрицательным на всех четырёх queries. Для
Environment и Object основная часть улучшения пришлась на `query=0`, а на
`query=3` point estimate слегка ухудшился. Кроме того, все 80 Position states
относятся к `approach`, тогда как Environment/Object включают `approach`,
`grasp` и `transport`. Следовательно, перенос Position ranker на поздние фазы
ещё не доказан.

## Sensitivity на всех states

Если не исключать десять replay failures, factor-macro regret уменьшается с
`0.009000` до `0.005321`, то есть на 40.9%. Bootstrap contrast:

$$
\Delta_{macro}^{all}=-0.003679,
\qquad 95\%\ CI=[-0.005556,-0.002110].
$$

Знак совпадает со strict analysis на каждом factor. Следовательно, primary
вывод не создаётся replay filtering.

## Что доказано и что не доказано

**Доказано на этом holdout:** заранее замороженная factor-specific комбинация
value и latent inconsistency лучше Cosmos value ранжирует H16 physical
consequences в factor-macro и особенно на Position.

**Пока не доказано:**

1. рост terminal LIBERO-PRO success rate;
2. individual statistical significance на Environment и Object;
3. перенос Position head после фазы approach;
4. выигрыш при другом candidate budget, denoising schedule или horizon;
5. что каждый uncertainty feature сам по себе причинно полезен.

Поэтому корректное название результата -- `held-out candidate-consequence
ranking`, а не `closed-loop planning improvement`.

## Решение и следующий тест

Preregistered gate **PASS**, поэтому frozen payload
`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`
можно без изменений перенести в paired closed-loop test.

Следующий эксперимент должен сравнить только:

1. `maxV-H16`: шесть тех же stochastic candidates, `argmax(value)`, выполнить
   16 actions;
2. `frozen-ranker-H16`: тот же candidate pool и compute, выбрать по frozen
   factor head, выполнить 16 actions.

Primary benchmark: untouched tasks Environment 7-9, Object 8-9, Position
x 4-5 и y 8-9. Primary endpoint -- paired terminal SR; secondary -- dense
progress, drop, timeout, factor/task deltas и latency. Analysis использует
paired bootstrap и exact McNemar. Видео сохраняются только для заранее
определённых discordant rollouts как mechanism evidence.

Если closed-loop SR не улучшается, H16 proxy недостаточно соответствует
terminal task objective и следующий метод должен быть action-conditioned
grounded critic. Если SR улучшается без sentinel regressions, frozen ranker
становится новым baseline, после чего отдельно проверяются feedback horizon и
safety filter.

## Артефакты

- preregistered protocol:
  [`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_PROTOCOL_20260828.md);
- frozen model:
  [`factor_h16_dense_ridge_v1.json`](frozen_models/factor_h16_dense_ridge_v1.json);
- strict generated report:
  [`frozen_ranker_strict/RESULTS.md`](campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/analysis/frozen_ranker_strict/RESULTS.md);
- bootstrap intervals:
  [`grouped_bootstrap_intervals.csv`](campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/analysis/frozen_ranker_strict/grouped_bootstrap_intervals.csv);
- candidate-level scores:
  `campaigns/frozen_h16_ranker_holdout_20260828__dense_relabel/analysis/frozen_ranker_strict/holdout_candidate_scores.parquet`;
- remote exact-state NPZ inventory:
  [`REMOTE_SIDECARS.md`](campaigns/frozen_h16_ranker_holdout_20260828/REMOTE_SIDECARS.md).

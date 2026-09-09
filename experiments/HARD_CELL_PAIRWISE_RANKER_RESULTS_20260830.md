# Hard-cell grounded pairwise ranker: results

Дата: 30 августа 2026 года.

Статус: **development opportunity PASS, untouched holdout gate FAIL**.
Линейное семейство value/latent/action-conditioned ranking закрывается без
подбора на holdout.

## Научный вопрос

Предыдущие тесты показали, что hard Object/Position states иногда содержат
успешный action candidate, но parallel Cosmos value и последовательный
`action -> future -> value` ранжируют candidates около случайного уровня.
Проверялась гипотеза, что grounded ordering можно выучить по комбинации 20
online-доступных признаков.

Для candidate $j$ признаки нормировались внутри одного exact state:

$$
z_{ijm}=\frac{x_{ijm}-\operatorname{mean}_k x_{ikm}}
{\max(\operatorname{std}_k x_{ikm},10^{-8})}.
$$

Factor-specific Bradley-Terry score обучался на non-tied terminal utility
pairs:

$$
S_f(i,j)=\beta_f^\top z_{ij},
$$

$$
\mathcal L_f(\beta)=
\sum_{(w,l)}\log\left(1+\exp[-\beta^\top(z_w-z_l)]\right)
+\frac{\alpha}{2}\lVert\beta\rVert_2^2.
$$

Bootstrap ensemble разрешал switch относительно parallel `max(value)` только
при

$$
LCB_\kappa=\operatorname{mean}_b[S_b(j_R)-S_b(j_V)]
-\kappa\operatorname{std}_b[S_b(j_R)-S_b(j_V)]>0.
$$

Полный frozen protocol:
[`HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md`](HARD_CELL_PAIRWISE_RANKER_PROTOCOL_20260830.md).

## Данные и freeze

| Split | Init states | Exact states | Candidates | Использование |
|---|---:|---:|---:|---|
| development | 10-24 | 30 | 240 | grouped CV и fit |
| calibration | 25-29 | 10 | 80 | выбор $\kappa$ |
| untouched holdout | 30-39 | 20 | 160 | единственная итоговая оценка |

В каждом split поровну Object task 0 и Position-y0.3 task 0. Каждый K8
candidate реально исполнялся 16 шагов и затем продолжался общей frozen
parallel K2/H16 policy до terminal outcome.

Модель была заморожена в `06:01:05`, до запуска holdout:

- payload SHA-256:
  `c9ae031cd3b4e1cf7f8c9acc1e191b99601ab585d17033e588b86c19f1db6168`;
- Object: $\alpha=100$, $\kappa=1.0$;
- Position: $\alpha=1$, $\kappa=1.5$.

Хэши модели, кода, протокола и config сохранены в
[`FREEZE_MANIFEST.json`](campaigns/hard_cell_pairwise_ranker_20260830/FREEZE_MANIFEST.json).

## Opportunity до holdout

| Factor | Dev+cal states | Mixed | Fail maxV с successful alternative | maxV SR | Oracle SR |
|---|---:|---:|---:|---:|---:|
| Object | 20 | 17 | 13 | 30% | 95% |
| Position-y0.3 | 20 | 3 | 3 | 0% | 15% |
| **All** | **40** | **20** | **16** | **15%** | **55%** |

Opportunity gate прошёл. При этом support Position был минимальным: только три
development states имели non-tied success/fail outcomes, а calibration
Position целиком состояла из all-fail pools.

Grouped development CV выбрала сильную регуляризацию для Object. Pairwise
utility accuracy была лишь `0.536` на Object и `0.460` на Position. Несмотря
на слабый CV, calibration выглядела положительно: selector дал 2 rescue / 0
harm на Object и поднял общий SR с 20% до 40%. Поэтому protocol разрешил
untouched holdout.

## Untouched holdout

| Factor | States | Mixed | `maxV` SR | AR SR | Raw ranker SR | Gated selector SR | Oracle SR | Rescue / harm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Object | 10 | 10 | 70% | 60% | 30% | 40% | 100% | 0 / 3 |
| Position-y0.3 | 10 | 2 | 20% | 20% | 0% | 20% | 20% | 0 / 0 |
| **All** | **20** | **12** | **45%** | **40%** | **15%** | **30%** | **60%** | **0 / 3** |

На mixed pools gated selector потерял три successful top-1 состояния:
`9/12 -> 6/12`. Он переключился в 6/20 states, но не сделал ни одного rescue.
Три harmful switch принадлежат Object init 31, 33 и 39. Ещё три Object states
с fail `maxV` и successful alternative (init 32, 37, 38) ranker также не
спас. Position holdout не содержал rescue opportunity относительно `maxV`:
оба mixed pools уже были успешно выбраны baseline, остальные восемь были
all-fail.

Средняя terminal utility уменьшилась на `0.45`; дополнительных adverse events
не возникло. Exact paired sign test для 0 rescue / 3 harm даёт `p=0.25`, но
эффект направлен строго не в нужную сторону.

Grouped-bootstrap intervals:

| Scope | Contrast | Point | 95% interval |
|---|---|---:|---:|
| Object | raw ranker SR - maxV SR | -40 п.п. | [-70; -10] п.п. |
| Object | gated SR - maxV SR | -30 п.п. | [-60; 0] п.п. |
| All | raw ranker SR - maxV SR | -30 п.п. | [-50; -10] п.п. |
| All | gated SR - maxV SR | -15 п.п. | [-30; 0] п.п. |

## Почему метод не перенёсся

Within-state success/fail pairwise accuracy показывает смену распределения:

| Split / factor | Parallel value | AR value | Learned score |
|---|---:|---:|---:|
| Development Object | 0.484 | 0.640 | 0.737 |
| Calibration Object | 0.471 | 0.531 | 0.665 |
| **Holdout Object** | **0.600** | **0.413** | **0.331** |
| Development Position | 0.566 | 0.375 | 0.944 |
| Calibration Position | n/a | n/a | n/a |
| **Holdout Position** | **0.575** | **0.742** | **0.450** |

1. Object head сильнее всего положительно взвесил AR value. На holdout именно
   AR ordering развернулся и стал хуже parallel value, поэтому learned score
   усилил нестабильный сигнал.
2. Position head обучился фактически на трёх informative init states;
   коэффициенты и bootstrap spread велики. Высокий development score является
   переобучением, а не переносимым законом.
3. Grouped bootstrap оценивал variation внутри уже наблюдённых init states, но
   не distribution shift к новым initial configurations. Поэтому LCB был
   положительным даже для трёх harmful Object switches.
4. Calibration была слишком мала и неоднородна: положительный Object result и
   полностью all-fail Position создали ложное ощущение безопасного threshold.

## Что установлено

1. **Proposal opportunity на Object реальна и воспроизводится.** На новых
   init 30-39 каждый K8 pool содержит success, а `max(value)` пропускает его в
   3/10 states. Значит Object bottleneck действительно находится в ranking.
2. **Текущие scalar/latent uncertainty features не дают устойчивого ranking.**
   H16 proxy ranker, terminal ridge critic, AR value и теперь pairwise ranker
   не улучшили terminal holdout.
3. **Bootstrap disagreement не равно OOD uncertainty.** Resampling одного
   development distribution не защищает от смены связи feature-outcome.
4. **Position пока является proposal problem.** В 8/10 holdout states все K8
   branches fail; reranking там не может помочь.
5. **Parallel max(value) остаётся лучшим candidate selector из проверенных на
   этом untouched split**, хотя его Object oracle gap всё ещё равен 30 п.п.

## Решение

Не подбирать новые linear weights, $\alpha$ или $\kappa$ на init 30-39.
Дальнейшая работа разделяется:

1. **Primary engineering/scientific baseline:** вернуться к подтверждённому
   causal механизму раннего real-observation feedback (`H8 re-query`), который
   ранее дал +12.5 п.п. в matched 2x2.
2. **Object research branch:** если продолжать reranking, использовать
   semantic grounded consequence critic по predicted future images/object-task
   relations и independently trained epistemic heads. Он должен проходить
   новый task/init holdout, а не bootstrap старых candidates.
3. **Position и Environment:** менять proposal/execution mechanism: shorter
   horizon, recovery после свежего observation или action refinement. Selector
   не запускать на all-fail pools.
4. Сохранить init 40-49 как untouched reserve; не использовать их для tuning
   текущего ranker.

## Артефакты

- development/calibration report:
  [`RESULTS.md`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/development_calibration/RESULTS.md);
- untouched holdout report:
  [`RESULTS.md`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/holdout/RESULTS.md);
- holdout state table:
  [`holdout_state_comparison.csv`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/holdout/holdout_state_comparison.csv);
- candidate scores:
  [`holdout_candidate_scores.parquet`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/holdout/holdout_candidate_scores.parquet);
- bootstrap intervals:
  [`holdout_bootstrap_intervals.csv`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/holdout/holdout_bootstrap_intervals.csv);
- comparison plot:
  [`holdout_pairwise_ranker.png`](campaigns/hard_cell_pairwise_ranker_20260830/analysis/holdout/holdout_pairwise_ranker.png).

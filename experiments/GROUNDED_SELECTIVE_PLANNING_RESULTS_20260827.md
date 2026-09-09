# Grounded selective planning: результаты P0-P2

Дата анализа: 27 августа 2026 года.

## Краткий итог

Ни один новый controller не превзошёл frozen baseline `maxV-H16` на широком
LIBERO-PRO Object benchmark. Механизм более частого feedback, который давал
положительный результат на выбранных boundary cases, не перенёсся на Object,
Position и Environment в целом. Текущие P1/P2 targets также не прошли offline
gates: восьмишаговая local utility оказалась вырожденной, а internal-action
penalty не улучшил grounded candidate ranking.

Практический baseline после этих запусков остаётся

$$
i^*=\arg\max_i \hat v_i,\qquad K=16.
$$

**Обновление после первичного P1/P2 анализа.** CPU-only dense geometry relabel
устранил ties старой local utility: 127 positive, 143 negative и 2 zero VoF;
candidate utility различается в 271/272 states. Routing mechanism-screening
перспективен для Object и Environment, но ranker на этом большом наборе gate
не прошёл. Последующий 48-state six-candidate screen показал новый, пока
неподтверждённый результат: factor-specific H16 ranker снизил macro regret на
45.7% (strict 42.6%) и был лучше Cosmos на каждом factor. H32 при этом уменьшил
consequence support и закрыт. Формулы, strict sensitivity и полный pilot
вынесены в
[`DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md`](DENSE_CONSEQUENCE_FEEDBACK_RESULTS_20260827.md).

## P0: causal horizon controls

Все методы сравнивались на одинаковых `suite/task/init/rollout_seed`. В анализ
вошло 299 matched episodes на метод: 100 Object, 100 Environment и 99 Position.
Primary score одинаково взвешивает три perturbation factors.

| Метод | Object SR | Position SR | Environment SR | Factor-macro SR |
|---|---:|---:|---:|---:|
| `maxV-H16` | **98.0%** | **29.6%** | 36.0% | **54.5%** |
| `maxV-H8` | 95.0% | 28.4% | 35.0% | 52.8% |
| `horizon-only` | 97.0% | 23.4% | 37.0% | 52.5% |
| `random-H8` | 96.0% | 25.4% | 35.0% | 52.1% |
| `risk-H8` | 93.0% | 25.4% | **38.0%** | 52.1% |

Основные paired contrasts относительно `maxV-H16`:

| Метод | Delta SR | 95% CI | Wins / losses | Exact McNemar p |
|---|---:|---:|---:|---:|
| `maxV-H8` | -1.7 п.п. | [-4.8; +1.3] | 9 / 14 | 0.405 |
| `horizon-only` | -2.0 п.п. | [-3.7; -0.4] | 8 / 14 | 0.286 |
| `random-H8` | -2.4 п.п. | [-5.1; +0.3] | 7 / 14 | 0.189 |
| `risk-H8` | -2.4 п.п. | [-5.4; +0.3] | 6 / 13 | 0.167 |

`horizon-only - random-H8` составляет только +0.3 п.п., 95% CI
[-2.0; +3.0]. Следовательно, disagreement trigger не показал дополнительной
информативности при примерно одинаковом compute. `risk-H8 - horizon-only`
равно -0.3 п.п., 95% CI [-3.0; +2.3], поэтому uncertainty reranking также не
дал добавочного эффекта.

Цена feedback существенна: средний query multiplier равен 1.94 для always-H8
и около 1.26 для adaptive/random H8. Улучшение Environment у `risk-H8`
(+2 п.п. к baseline) сопровождается регрессией Object (-5 п.п.) и Position
(-4.1 п.п.); это не переносимый выигрыш.

**Решение P0:** no-go для текущих H8 controllers. Не запускать их как основной
closed-loop planner на broad benchmark.

## P1/P2: exact-state branches

Собрано 272 из 300 запланированных states и 1088 candidate outcomes:

- Object: 100/100;
- Environment: 100/100;
- Position: 72/100;
- terminal continuation: 52 states.

На тяжёлых `x0.3-x0.5`, `y0.4-y0.5` policy часто не доходила до
`grasp/transport`, поэтому phase-balanced target остановился на 4-6 states.
Это содержательная coverage-проблема, а не CUDA crash.

После pooling был найден и исправлен analysis bug: исходный `snapshot_id` не
содержал position level и склеивал одинаковые `task/init/query` разных runs.
Теперь analysis identity имеет вид `source_run::snapshot_id`; 272 states и все
группы по четыре candidates разделяются корректно. Регрессионный тест: 9/9.

### Replay integrity

Максимальная ошибка main/open replay равна `2.899e-5`. Порог `1e-9` прошли
265/272 states; 7 states его нарушили. Все шесть ненулевых terminal VoF labels
находятся среди прошедших threshold, поэтому qualitative conclusion не
меняется, но primary exact-state gate формально не пройден. P1/P2 остаются
pilot evidence, а не confirmatory result.

### P1: Value of Feedback

Для local endpoint

$$
Y_{\mathrm{VoF}}=G(\tau_{feedback})-G(\tau_{open})
$$

получено 272/272 нулевых labels. За восемь шагов frozen utility, основанная на
success/progress/drop/wrong-object/violation, не различила open-loop и requery
branches. Этот target непригоден для обучения router в текущем виде.

Для terminal endpoint support крайне мал: 3 positive, 3 negative и 46 zero.
Grouped OOF ridge дал AUROC 0.980 и при 20% budget выбрал суммарный positive
VoF 4.0 против -0.5 у deterministic random. Это выглядит перспективно только
как гипотеза: positive labels встретились исключительно в Environment,
negative исключительно в Object, а внутри каждого factor данных недостаточно
даже для OOF fit с замороженным набором признаков. Число независимых
ненулевых событий равно шести, поэтому этот AUROC нельзя считать
подтверждённым переносимым detector.

Отдельные online uncertainty metrics gate не прошли. При budget 20%:

| Router score | AUROC `VoF > 0` | Realized uplift per state |
|---|---:|---:|
| grouped OOF ridge | 0.980 | +0.0769 |
| deterministic random | 0.592 | -0.0096 |
| `value_range` | 0.626 | -0.0673 |
| first-action disagreement | 0.728 | -0.0096 |
| predicted proprio error | 0.510 | 0.0000 |

**Решение P1:** no-go для текущей local utility; terminal router требует новый
сбор с существенно большим количеством terminal и non-zero outcomes.

### P2: grounded candidate ranking

У всех четырёх candidates совпала local utility во всех 272 states. Terminal
utility различалась только в 9 из 52 states. Поэтому local top-1 accuracy 1.0
у всех методов является артефактом ties, а не качеством ranking.

| Factor | Cosmos value regret | `value - internal action` regret |
|---|---:|---:|
| Environment | 0.050 | 0.050 |
| Object | **0.316** | 0.368 |
| Position | 0.038 | 0.038 |

Internal uncertainty penalty не уменьшил regret на каждом factor и ухудшил
Object. **Решение P2:** gate не пройден; закрытый rollout этого ranker не
оправдан.

## Что делать дальше

1. Оставить `maxV-H16` основным benchmark baseline.
2. Заменить восьмишаговый event-only local target на dense continuous
   consequence: object-to-goal distance, lift margin, object pose delta,
   contact stability и progress за 16/32 шага.
3. Для candidate ranking повысить outcome diversity: более разнообразные
   candidate seeds/noise, targeted hard negatives и terminal continuation для
   всех calibration states.
4. Собирать grasp/transport states из trajectories, которые реально достигают
   этих фаз; extreme all-fail shifts анализировать отдельным stress stratum.
5. После накопления минимум десятков positive и negative VoF в каждом factor
   применять held-out-task и leave-one-factor-out evaluation. До этого не
   оптимизировать closed-loop planner по AUROC 0.980.

Машиночитаемые результаты находятся в:

- `campaigns/pro_object_horizon_controls_p0_20260826/analysis/horizon_controls/`;
- `campaigns/counterfactual_feedback_p1_p2_20260826/analysis/counterfactual_feedback/`.

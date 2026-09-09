# Terminal-grounded conservative critic: результаты

Дата анализа: 30 августа 2026 года.

Статус: **offline gate FAIL; closed-loop корректно пропущен**.

Frozen protocol был записан до targeted collection:
[`TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md`](TERMINAL_GROUNDED_CRITIC_PROTOCOL_20260829.md).

## Вопрос эксперимента

Предыдущий H16 ranker уменьшал short-horizon consequence regret offline, но не
улучшил terminal success в paired closed-loop. Здесь проверялась более прямая
гипотеза: можно ли по доступным до исполнения action/value/latent признакам
предсказать terminal advantage candidate относительно обычного
`max(value)` и переключаться только при статистически убедительном выигрыше.

Для snapshot $i$ и candidate $j$ использовалась terminal utility

$$
G_{ij}=2\,\mathbb{1}[\mathrm{success}_{ij}]
+p_{ij}
-\mathbb{1}[\mathrm{drop}_{ij}]
-0.5\,\mathbb{1}[\mathrm{wrong}_{ij}]
-\mathbb{1}[\mathrm{violation}_{ij}],
$$

а target был остаточным преимуществом над candidate с максимальным Cosmos
value в том же exact state:

$$
A_{ij}=G_{ij}-G_{i,j_V},
\qquad
j_V=\arg\max_j \hat v_{ij}.
$$

Grouped-bootstrap ensemble из 32 ridge heads оценивал среднее advantage и его
epistemic spread. Переключение разрешалось только при

$$
\operatorname{LCB}_{ij}
=\overline A_{ij}-q_{0.90}\max(s_{ij},\epsilon)>0
$$

и при safety UCB не выше, чем у `max(value)`. Иначе выполнялся baseline
candidate. Все 50 признаков были causal online features: value, нормы и
геометрия action chunk, расстояние до consensus, latent consistency и
predicted future proprio. Реальный исход branch и privileged simulator state
в признаки не входили.

## Дизайн и целостность

| Split | Tasks | Init states | Snapshots | Terminal branches | Роль |
|---|---:|---:|---:|---:|---|
| development | 0-5 | 0-4 | 60 | 480 | fit grouped bootstrap heads |
| calibration | 6-7 | 0-4 | 20 | 160 | one-sided conformal scales |
| offline holdout | 8-9 | 0-4 | 20 | 160 | untouched evaluation |
| closed-loop | 8-9 | 5-9 | 120 pairs planned | - | запуск только после offline PASS |

Каждый snapshot был снят outcome-independently на query 0 или 3. В нём
генерировались 8 candidates; каждый H16 chunk фактически исполнялся, затем одна
и та же frozen best-of-2 `max(value)-H16` policy продолжала branch до terminal
outcome. Пересечение `task x init_state` groups между splits равно нулю.

Модель с payload SHA-256
`3187672846409cd5b3d59628b32058bc883512deae348833d716f52cb51e87b7`
была заморожена в `2026-08-30T01:21:22`, до запуска holdout. После завершения
collection resume-script повторно выполнил детерминированный fit и получил
другой hash только из-за поля `frozen_at`. Аудит показал точное равенство всех
features, scaler values, coefficients, intercepts и conformal scales; для
финальной оценки восстановлен исходный pre-holdout artifact. Оба JSON сохранены,
а sequence теперь отдельно сохраняет и повторно использует
`frozen_model_before_holdout.json`.

## Development: механизм существует, но локально

| Metric | Result |
|---|---:|
| Snapshots / independent groups | 80 / 40 |
| Heterogeneous candidate pools | 8 / 80 (10.0%) |
| Fail `max(value)`, который можно спасти другим candidate | 5 / 80 (6.25%) |
| `max(value)` terminal SR | 92.50% |
| Oracle-in-pool terminal SR | 98.75% |
| Oracle gap | +6.25 п.п. |
| Successful terminal branches | 600 / 640 (93.75%) |

Opportunity gate прошёл ровно на зафиксированных границах: не менее 8
heterogeneous states и не менее 4 rescues. Однако все 5 rescue принадлежат
одной задаче: `task 0`, "pick the alphabet soup and place it in the basket".
Для неё `max(value)` SR равен 40% и на query 0, и на query 3; oracle SR равен
100% и 80% соответственно. Ещё по одному heterogeneous state есть у BBQ sauce
и milk, но их `max(value)` candidates уже успешны. Остальные task/query cells
являются ceiling.

Наиболее крупные по модулю bootstrap-mean coefficients относятся к
`action_std_d0`, `action_first_d0` и `predicted_future_proprio_d6`. Коэффициент
самого `candidate_value` мал. При этом стандартные отклонения коэффициентов
сопоставимы с их средними: это сигнал разреженного, task-local support, а не
устойчивый универсальный закон.

Calibration tasks 6-7 также почти полностью ceiling: все 20 baseline states
успешны, поэтому conservative selector не сделал ни одного переключения.
One-sided scales получились большими:

$$
q_{\mathrm{adv}}=30.61,
\qquad
q_{\mathrm{risk}}=39.42.
$$

Это не ошибка вычисления, а следствие слабого и неоднородного evidence для
переносимого positive advantage.

## Untouched holdout

Holdout содержит tasks 8-9: chocolate pudding и orange juice, по пять init
states и два query на каждый task.

| Metric | `max(value)` | Terminal critic | Oracle in pool |
|---|---:|---:|---:|
| Terminal SR | 100% | 100% | 100% |
| Mean terminal utility | 3.000 | 3.000 | 3.000 |
| Adverse-event rate | 0% | 0% | 0% |

Все 160 из 160 фактически продолженных candidates завершили задачу успешно,
получили utility 3.0 и не дали drop, wrong-object interaction, deadlock или
official violation. Поэтому на этом holdout нет ни одного состояния, в котором
candidate selector в принципе может улучшить terminal endpoint.

Unconstrained mean head предпочитал другой candidate в 18/20 states; в 13/20
он также проходил относительный safety UCB. Conservative LCB корректно
заблокировал все эти ненужные переключения:

| LCB diagnostic | Value |
|---|---:|
| Mean | -8.630 |
| Median | -9.495 |
| Maximum | -0.031 |
| Switches | 0 / 20 |

Empirical interval coverage равно 100% одновременно по всем candidates, но
mean LCB slack равен 8.69. То есть интервалы безопасны, однако слишком широки
для полезного действия. Predicted adverse risk равен 0.0407 при observed risk
0; Brier score 0.00307.

## Formal gate

| Check | Result |
|---|---|
| Zero train/calibration/holdout group overlap | PASS |
| Switch rate 2-30% | **FAIL**, 0% |
| Positive net rescues | **FAIL**, 0 rescues / 0 harms |
| Nonnegative terminal utility delta | PASS, 0.0 |
| Safety regression at most one event | PASS, 0 events |
| Grouped-bootstrap utility CI lower bound nonnegative | PASS, [0.0, 0.0] |

Итоговый offline gate равен **FAIL**. В соответствии с preregistration
120-pair closed-loop не запускался: он не мог измерить выигрыш на holdout, где
и baseline, и каждый alternative candidate уже имеют 100% success.

## Выводы

1. Terminal candidate reranking имеет ненулевой oracle potential, но в текущих
   данных он почти полностью сосредоточен в одном сложном object task.
2. `max(value)` действительно иногда выбирает terminal-fail candidate, когда в
   том же exact state присутствует успешный candidate. Это подтверждает саму
   постановку residual terminal advantage.
3. Текущий 50-feature ridge critic не получил достаточно переносимых positive
   examples. Нельзя утверждать, что он улучшает planning на новых object tasks.
4. Conservative conformal gate сделал правильное безопасное действие: сохранил
   baseline при слабом evidence. Ослаблять threshold после просмотра holdout
   нельзя.
5. Главный bottleneck сейчас находится раньше selector: большинство stochastic
   pools либо полностью успешны, либо не дают достаточного разнообразия
   terminal outcomes. Сначала нужен benchmark с измеримым oracle gap и более
   сильный proposal mechanism.

## Следующий эксперимент

Следующий этап должен начинаться не с новой формулы score, а с frozen
**proposal-opportunity atlas**:

1. На заранее выбранных трудных LIBERO-PRO Object/Position/Environment cells
   измерить terminal SR `max(value)` и oracle SR для нескольких proposal pools.
2. Сравнить обычные stochastic K8 candidates с action-conditioned pool,
   различающимся по sampling path и feedback horizon, при одинаковом compute.
3. Разрешать обучение selector только для pool, который даёт не менее 5 п.п.
   holdout oracle gap и достаточное число rescues в каждом split.
4. Разделять generalization по новым init states внутри трудных tasks и по новым
   tasks. Ceiling tasks сохранять как safety/fallback controls, но не использовать
   как единственный calibration/holdout support.
5. Если даже расширенный pool не создаёт oracle gap, перейти от reranking к
   уже подтверждённому механизму: early requery/recovery после свежего реального
   observation.

Главный научный результат этапа отрицательный, но полезный: terminal labels и
conservative uncertainty недостаточны сами по себе, если proposal pool и test
split не содержат различимых последствий действий.

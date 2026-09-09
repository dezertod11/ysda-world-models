# Terminal-grounded conservative candidate critic

Статус: **preregistered before targeted terminal collection**.

Дата фиксации: 29 августа 2026 года.

Результат от 30 августа: offline gate FAIL, closed-loop пропущен по протоколу.
Полный анализ:
[`TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md`](TERMINAL_GROUNDED_CRITIC_RESULTS_20260830.md).

## Почему нужен новый эксперимент

Frozen H16 ranker уверенно уменьшал короткий consequence regret offline, но не
улучшил terminal success в 360-pair closed-loop проверке. Это означает, что
локальная геометрическая utility недостаточно согласована с конечной задачей.
Коэффициенты H16 ranker больше не подбираются.

В уже собранном outcome-independent terminal subset есть 52 exact-state
snapshot и четыре candidates на snapshot. Только 6/52 snapshot имеют разные
success/fail исходы между candidates, а `max(value)` можно спасти выбором
другого candidate лишь в 2/52 случаях. Oracle SR равен 71.15% против 67.31% у
`max(value)`. Этот набор подтверждает сам механизм, но слишком мал и слишком
однороден для обучения terminal critic.

## Проверяемая гипотеза

> Action-conditioned critic, обученный на фактически продолженных до terminal
> exact-state branches, может определить редкие случаи, когда candidate лучше
> текущего `max(value)`. Conservative lower-confidence gate должен сохранить
> `max(value)` во всех остальных состояниях.

Это не episode fail classifier. Модель сравнивает варианты действий **в одном
и том же текущем состоянии**.

## Данные и target

Из одного simulator/runtime snapshot генерируются восемь stochastic Cosmos
candidates. Каждый candidate исполняет свой H16 action chunk, после чего одна и
та же замороженная best-of-2 `max(value)-H16` policy продолжает branch до
success или time limit. Восемь proposals нужны только в сравниваемом decision
state; continuation является общей nuisance policy, а не новым предметом
сравнения. Продолжения используют одинаковую детерминированную схему seeds.

Terminal utility хранится вместе с отдельными бинарными outcomes:

$$
G_{ij}=2\,\mathbb{1}[\mathrm{success}_{ij}]
+p_{ij}
-\mathbb{1}[\mathrm{drop}_{ij}]
-0.5\,\mathbb{1}[\mathrm{wrong}_{ij}]
-\mathbb{1}[\mathrm{violation}_{ij}],
$$

где $p_{ij}\in[0,1]$ -- максимальный BDDL goal progress. Primary target для
candidate $j$ является residual advantage к Cosmos baseline в том же snapshot:

$$
A_{ij}=G_{ij}-G_{i,j_V},
\qquad
j_V=\arg\max_j \hat v_{ij}.
$$

Success, drop, wrong-object interaction, deadlock и official safety violation
всегда анализируются отдельно; scalar utility не заменяет эти endpoints.

## Causal online features

Critic получает только величины, доступные **до исполнения candidate**:

1. predicted value и семь internal latent-consistency features;
2. нормы action chunk;
3. направление действий: first/last/mean/std для каждой из 7 action dimensions;
4. расстояние candidate до consensus первого действия и целого chunk;
5. девять координат predicted future proprio.

Privileged simulator state, actual H16 endpoint, prediction error after chunk и
terminal labels не входят в features. Все candidate features нормализуются
внутри snapshot; поэтому critic учится ранжированию, а не сложности episode.

## Модель и conservative gate

На grouped bootstrap samples независимых `task x init_state` групп обучается
ensemble ridge heads. Для каждого candidate он даёт mean и epistemic spread
предсказанного advantage:

$$
\bar A_{ij}=\frac1B\sum_{b=1}^{B}\hat A^{(b)}_{ij},
\qquad
s_{ij}=\operatorname{std}_{b}\hat A^{(b)}_{ij}.
$$

One-sided scale $q_{0.90}$ замораживается на отдельном calibration split по
group-max conformal residual. Candidate с максимальным mean заменяет max-value
только при

$$
\operatorname{LCB}_{ij}
=\bar A_{ij}-q_{0.90}\max(s_{ij},\epsilon)>0
$$

и если upper-confidence safety risk не выше риска max-value candidate.
Иначе выполняется $j_V$. Такое правило по конструкции допускает редкие
селективные вмешательства и не повторяет 67--94% switch rate неудачного H16
ranker.

## Splits

Queries одного episode и одинаковый `task x init_state` никогда не делятся
между splits.

| Split | Object tasks | Init states | Роль |
|---|---:|---:|---|
| development | 0-5 | 0-4 | fit/bootstrap screen |
| calibration | 6-7 | 0-4 | conformal scale и один frozen threshold |
| offline holdout | 8-9 | 0-4 | untouched terminal branch test |
| closed-loop | 8-9 | 5-9 | 12 seeds на каждый init; только после offline PASS |

Primary snapshots фиксированы на query 0 и 3: старый audit обнаружил rescue в
approach и grasp. Sampling не зависит от branch outcome. Этот targeted этап
проверяет только Object; завершённые Environment/Position кампании остаются
broad stress controls и не используются для fit или выбора threshold.

Holdout и closed-loop jobs могут быть технически разбиты по одному init state
для параллельного исполнения. Base seeds при этом сдвигаются так, чтобы
получился в точности тот же набор rollout seeds, что у монолитного запуска.

## Offline metrics

- max-value SR, critic SR и oracle-in-pool SR;
- paired rescue/harm counts;
- terminal utility и terminal regret;
- switch rate и switch precision;
- drop/wrong/deadlock/official violation rates;
- grouped-bootstrap 95% CI по `task x init_state`;
- calibration coverage и risk reliability.

## Последовательные gates

### Opportunity gate

Targeted development+calibration collection продолжается только если есть не
менее 8 outcome-heterogeneous snapshots и не менее 4 случаев, где другой
candidate спасает fail `max(value)`. Иначе candidate reranking имеет слишком
малый достижимый эффект; следующий метод должен увеличивать proposal diversity
или делать feedback/recovery, а не обучать selector.

### Offline critic gate

Closed-loop разрешён только если одновременно:

1. train/calibration/holdout group overlap равен нулю;
2. model и conformal scale заморожены до просмотра holdout labels;
3. holdout switch rate находится в диапазоне 2--30%;
4. net rescues minus harms положителен, terminal utility не хуже max-value;
5. ни один tracked safety endpoint не ухудшается более чем на один event;
6. lower bound grouped-bootstrap delta terminal utility не отрицателен.

Если opportunity gate или offline critic gate не пройден, closed-loop не
запускается. Публикуется отрицательный результат и приоритет переходит к
proposal diversity / action-conditioned future search.

## Closed-loop endpoint

Primary contrast -- paired terminal SR на 120 untouched парах: два tasks,
пять init states на task и 12 rollout seeds на init. Secondary: failure modes,
query count, wall time, switch rate и minimum per-cell delta.
Требуется положительный factor-macro point estimate без sentinel regression;
для claim об улучшении 95% grouped-bootstrap CI должен исключать ноль.

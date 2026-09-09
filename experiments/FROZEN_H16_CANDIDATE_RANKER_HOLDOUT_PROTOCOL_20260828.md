# Frozen H16 candidate ranker: confirmatory holdout

Статус: **preregistered before holdout collection; completed with PASS**.

Результат, добавленный после завершения сбора и не меняющий этот протокол:
[`FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md`](FROZEN_H16_CANDIDATE_RANKER_HOLDOUT_RESULTS_20260828.md).

Дата фиксации: 28 августа 2026 года.

## Проверяемое утверждение

Six-candidate screen показал, что factor-specific ridge может выбирать action
chunk с меньшим фактическим H16 consequence regret, чем исходный
`argmax(value)`. Confirmatory гипотеза:

> ranker с коэффициентами, полностью замороженными на screen, уменьшает regret
> Cosmos value на новых `task/init_state` отдельно для Object, Environment и
> Position.

Это offline exact-state test выбора action, а не claim об улучшении terminal SR.
Closed-loop разрешён только после прохождения этого gate.

## Замороженная модель

Training source: strict replay subset six-candidate campaign
`counterfactual_feedback_h32_dense_relabel_20260827`. Используется только H16
target `dense_utility_v2`; H32 labels в fit не входят.

Для snapshot $i$, candidate $j$ и feature $m$ сначала считается нормализация
внутри одного набора candidates:

$$
z_{ijm}=\frac{x_{ijm}-\bar{x}_{im}}
{\max(\operatorname{std}_{j}(x_{ijm}),10^{-8})}.
$$

Target также центрируется внутри snapshot:

$$
y_{ij}=G^{H16}_{ij}-\bar{G}^{H16}_i.
$$

Для каждого OOD factor $f$ один раз оценивается ridge:

$$
\hat\beta_f=
\arg\min_\beta
\sum_{(i,j)\in\mathcal D^{screen}_f}
(y_{ij}-\beta^\top \tilde z_{ij})^2
+\alpha\lVert\beta\rVert_2^2,
\qquad \alpha=1.
$$

$\tilde z$ обозначает дополнительную feature-wise standardization, параметры
которой также сохраняются из screen и не пересчитываются по holdout. Candidate
выбирается как

$$
j^*(s_i)=\arg\max_j \hat\beta_f^\top \tilde z_{ij}.
$$

Замороженные 11 features:

1. `candidate_value`;
2. L1 первого action;
3. L1 и L2 всего action chunk;
4. mean/max latent action copy inconsistency;
5. latent first-action copy L2 inconsistency;
6. mean/max latent future-proprio copy inconsistency;
7. mean/max latent value-element inconsistency.

Нельзя менять features, $\alpha$, target, factor heads или порог replay после
просмотра holdout. JSON-модель хранится в
`experiments/frozen_models/factor_h16_dense_ridge_v1.json`.
Frozen payload SHA-256:
`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`;
training-table SHA-256:
`c22e3745009967306263b7d7ad517ce07a2b98895e5c8db969a76b62be4cf5d3`.

## Holdout data

Campaign: `frozen_h16_ranker_holdout_20260828`.

| Factor | Tasks | Init states | States |
|---|---:|---:|---:|
| Object | 2-9 | 5-9 | 80 |
| Environment | 2-9 | 5-9 | 80 |
| Position x0.3 | 2-5 | 5-9 | 40 |
| Position y0.3 | 6-9 | 5-9 | 40 |
| **Total** | | | **240** |

Все эти `task/init` identities отсутствуют в six-candidate screen, где были
только tasks 0-1 и init states 0-4. Environment materialization дополнительно
использует новый seed `20260828`.

Каждое source episode имеет заранее заданные candidate snapshot queries
$q\in\{0,3,6,9\}$. Scheduled query существует только пока episode активен, но
collector не смотрит на phase, progress, uncertainty или branch outcome при
решении сохранить доступный state. Phase остаётся только аналитическим
столбцом. После $q=9$ source rollout останавливается, поскольку terminal outcome
в этой проверке не является target.

Для каждого state генерируются те же шесть stochastic candidates, что в
screen. Каждый H16 chunk фактически исполняется после восстановления одного
runtime snapshot; основной rollout повторяет Cosmos max-value branch для
replay integrity.

## Baselines и метрика

Сравниваются:

- `cosmos_value`: $\arg\max_j \hat v_{ij}$;
- deterministic random candidate;
- frozen factor ridge;
- oracle по реальному $G^{H16}$.

Regret state:

$$
R_i(m)=\max_jG^{H16}_{ij}-G^{H16}_{i,j_m}.
$$

Primary contrast:

$$
\Delta_f=\mathbb E_{task/init\in f}
[R_i(\text{frozen})-R_i(\text{Cosmos})].
$$

Сначала regret усредняется внутри независимого `task/init`, затем между
группами. 95% CI получается grouped bootstrap с 5000 resamples и seed
`20260828`. Factor-macro contrast равен среднему трёх $\Delta_f$.

## Confirmatory gate

Gate проходит, только если одновременно:

1. train/holdout group overlap равен нулю;
2. в каждом factor есть не менее 20 независимых `task/init` groups;
3. point estimate $\Delta_f<0$ для каждого factor;
4. верхняя граница factor-macro 95% grouped-bootstrap CI меньше нуля.

Primary analysis использует strict replay subset
`main_open_replay_state_max_abs <= 1e-9`. Полный набор публикуется как
sensitivity analysis. Если gate не пройден, текущая internal-latent ridge
линия закрывается и следующий метод - action-conditioned pairwise consequence
critic, а не подбор коэффициентов на holdout.

## Запуск

```bash
FROZEN_H16_HOLDOUT_GPUS=7 \
  scripts/run_frozen_h16_ranker_holdout_sequence.sh
```

Config:
`configs/libero_campaign_frozen_h16_ranker_holdout.json`.

Status:

```bash
scripts/mlspace_experiment_status.sh \
  frozen_h16_ranker_holdout_20260828 --verbose
```

После collection sequence автоматически выполняет dense relabel, standard
analysis и frozen evaluation для all/strict subsets.

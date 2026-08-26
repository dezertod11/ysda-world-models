# Counterfactual feedback and grounded candidate protocol

Статус: **implementation frozen, smoke passed, launch waits for P0 gate**.

Дата фиксации: 26 августа 2026 года.

## Цель

Одним exact-state collector получить causal targets для двух следующих
гипотез:

1. P1: когда дополнительный реальный observation через 8 шагов полезнее
   выполнения исходного 16-step chunk;
2. P2: насколько Cosmos value ранжирует реальные outcomes четырёх candidate
   chunks и можно ли обучить grounded ranker лучше него.

## Exact runtime snapshot

Одного `sim.get_state()` недостаточно: OSC controller и Panda gripper содержат
скрытое runtime state. Snapshot включает:

- MuJoCo state и `data.ctrl`;
- изменяемые model arrays;
- environment `timestep`, `cur_time`, `done`;
- controller goals, gains, initial joint/EEF state и update flag;
- накопленный `gripper.current_action`.

Integrity gate:

$$
\max_j |x^{main}_{t+16,j}-x^{replay}_{t+16,j}|\le 10^{-9}.
$$

Simulator smoke после 24 ненулевых prefix actions дал `1.06e-15`. Полный
Cosmos smoke дал `8.12e-16` для реально выбранного max-value chunk.

## Ветки из одного состояния

Модель генерирует четыре samples

$$
\{(a_i,\hat v_i,\hat s_i')\}_{i=1}^{4}.
$$

Каждый `a_i` отдельно выполняется 16 шагов после восстановления одного и того
же runtime snapshot. Для max-value candidate строится дополнительная ветка:

$$
\tau_{open}: a^*_{0:15},
$$

$$
\tau_{feedback}: a^*_{0:7}\rightarrow o_{t+8}
\rightarrow \operatorname{Cosmos}(o_{t+8})
\rightarrow \tilde a^*_{0:7}.
$$

Main rollout выполняет `max(value)` с горизонтом 16. Он является независимой
проверкой replay выбранной open branch.

## Labels

Все составляющие сохраняются отдельно: BDDL goal progress, task success,
target drop candidate, wrong-object candidate, official safety violation,
target lift/contact, object-state delta и kinematics.

Frozen локальный pilot utility:

$$
G_{local}=2I_{success}+\Delta progress+0.25f_{goal}
-I_{drop}-0.5I_{wrong}-I_{violation}.
$$

Он нужен только для mechanism screening. Более сильный endpoint получается на
детерминированно выбранных 20% snapshots продолжением каждой ветки frozen
`max(value)` policy до terminal outcome:

$$
G_{terminal}=2I_{success}+progress_{max}
-I_{drop}-0.5I_{wrong}-I_{violation}.
$$

Для обоих endpoints:

$$
Y_{VoF}=G(\tau_{feedback})-G(\tau_{open})-c_{query}.
$$

Скаляр не скрывает safety: task success и violation публикуются раздельно.

## Sampling design

- 300 decision states: по 100 Object, Environment и Position.
- Position: по 10 states на каждый shift `x/y = 0.1,...,0.5`.
- Не более одного snapshot каждого phase proxy на episode.
- Phase proxy: `approach`, `grasp`, `transport`, `release` по real
  contact/lift/predicate history.
- Один phase не может занять больше 40% factor sample; это soft balance,
  поскольку successful release обычно завершает episode до следующего query.
- Terminal continuation назначается SHA-256 hash от полного snapshot identity,
  поэтому подвыборка фиксирована до outcomes.
- Queries одного episode и states одного held-out task не разделяются между
  train/test.

## Frozen analysis

P1:

- grouped out-of-fold ridge на preregistered online features;
- sign accuracy и AUROC для `VoF > 0`;
- uplift@10%, 20%, 30% query budget;
- controls: deterministic random routing и oracle routing.

P2:

- exact-state top-1 accuracy и regret;
- baselines: random, Cosmos value, `value - internal action inconsistency`,
  oracle;
- local и terminal outcomes публикуются отдельно.

P1 gate проходит, только если OOF routing лучше random при matched budget. P2
gate проходит, только если non-oracle ranker уменьшает regret относительно
Cosmos value на каждом OOD factor.

## Реализация

- Campaign config:
  `experiments/configs/libero_campaign_counterfactual_feedback_pilot.json`.
- Collector: `scripts/collect_counterfactual_feedback.py`.
- Runtime snapshot: `scripts/libero_runtime_snapshot.py`.
- Analysis: `scripts/analyze_counterfactual_feedback.py`.
- Simulator integrity test: `scripts/verify_libero_snapshot_branching.py`.

После P0 gate запуск выполняется manifest runner, а не вручную:

```bash
.venv-cosmos/bin/python scripts/run_libero_experiment_campaign.py \
  --config experiments/configs/libero_campaign_counterfactual_feedback_pilot.json \
  --profile counterfactual_feedback_pilot_p1_p2 \
  --run-prefix counterfactual_feedback_pilot_p1_p2_20260826 \
  --gpus 2,3,4,5,6,7 \
  --execute
```

Фактический список GPU перед запуском определяется только после `nvidia-smi`;
GPU 0 запрещена.

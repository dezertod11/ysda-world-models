# P3d: new-cell transfer and recovery-mechanism ablation

Дата фиксации: 5 сентября 2026 года, до запуска P3d rollouts.

## Мотивация

P3c получил confirmatory full-episode эффект `32.5% -> 60.0%` на новых
initial states восьми заранее выбранных LIBERO-PRO Position cells. Остались две
неоднозначности:

1. переносится ли frozen controller на новые `task x perturbation` cells;
2. нужен ли target-conditioned RGB regrasp, или достаточно открыть gripper,
   отступить вверх и снова вызвать Cosmos Policy.

P3d проверяет обе гипотезы без изменения P3c localizer, trigger thresholds,
primitive geometry, policy или denoising hyperparameters.

## Frozen controller

- Suite: `libero_object_temp` из LIBERO-PRO Position.
- Candidate policy: Cosmos Policy `K=4`, `argmax(value)`.
- Common prefix: H16 на queries 0--3 и первые 8 actions query 4.
- Branch snapshot и decision: `t=72`.
- Continuation: H8 requery для всех branches, одинаковые query seeds.
- Episode budget: 280 environment actions, включая recovery primitive.
- Trigger: frozen `workspace_calibrated` из P3c.
- Perception: frozen P3b DeepLab heatmap + object-routed depth.
- Statistical runs: без видео.

В каждой development case сравниваются три ветви из одного runtime snapshot:

1. `baseline_h8`: немедленный H8 continuation;
2. `workspace_calibrated`: полный `open + retreat + relocalize + approach +
   descend + close + lift`, затем H8;
3. `workspace_retreat_only`: тот же initial trigger, `open + retreat`, та же
   post-retreat RGB localization и guard, но без approach/grasp/lift, затем H8.

Если trigger или post-retreat guard не проходит, intervention branch должна
буквально переиспользовать baseline outcome. Simulator object pose доступна
только terminal evaluator.

## Cells и splits

Replication cohort повторяет восемь P3c cells:

```text
x0.2/task5, x0.2/task6, x0.2/task9,
y0.2/task4, y0.2/task6, y0.2/task9,
y0.3/task1, y0.3/task5
```

New-cell cohort добавляет семь cells, отсутствовавших в P3c и поддерживаемых
frozen target-object localizer:

```text
x0.2/task2,
y0.1/task4, y0.1/task6, y0.1/task8, y0.1/task9,
y0.2/task7, y0.2/task8
```

| Split | Init states | Replication | New-cell | Всего cases |
|---|---:|---:|---:|---:|
| development | 40--44 | 40 | 35 | 75 |
| gated holdout | 45--49 | 40 | 35 | 75 |

Группа равна `(position_level, task_id, init_state_id)`. Development и holdout
не пересекаются. Holdout не запускается при failed development gate.

## Selection и gates

Development выбирает ровно один intervention по paired SR на **new-cell**
cohort. Tie-break в порядке: меньше harms, меньше wrong-object delta, меньше
primitive actions. Таким образом, если retreat-only достаточен, полный regrasp
не получает преимущество по названию.

Holdout открывается, если одновременно выполнены:

1. 75/75 complete cases и все ожидаемые branches;
2. snapshot replay error не выше `1e-9`;
3. все counterfactual-reused branches идентичны baseline по outcome и
   diagnostics;
4. на 35 new-cell cases: не менее пяти interventions, paired SR delta > 0,
   init-group bootstrap CI lower >= 0 и rescues > harms;
5. drop и wrong-object deltas не выше +5 п.п., official safety delta <= 0;
6. на replication cohort delta >= 0 и rescues >= harms.

Те же endpoints применяются к one-shot holdout без изменения threshold. Кроме
primary init-group bootstrap отдельно сообщаются cell-macro bootstrap,
McNemar exact test, per-cell rescue/harm, trigger coverage и completion time.

## Решение после P3d

- New-cell holdout PASS и преимущество full regrasp над retreat-only:
  разрабатывать event-driven contact trigger для повторной проверки во времени.
- New-cell PASS при выборе retreat-only: упростить controller и исследовать
  feedback после contact reset без object-directed primitive.
- Development NO-GO или holdout FAIL: зафиксировать P3c как cell-specific
  положительный результат и перейти к P4, independent dynamics ensemble с
  conformal routing.


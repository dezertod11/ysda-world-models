# P3e: frozen Recovery Outcome Ensemble holdout

Дата фиксации: 6 сентября 2026 года, до запуска init states 45--49.

## Гипотеза

P3d показал, что frozen full RGB regrasp существенно лучше простого
retreat/requery, но иногда вредит уже успешной траектории. Причём знак эффекта
primitive меняется между cells: full regrasp создаёт drop в x0.2/task2, а
retreat-only создаёт timeout в y0.2/task8.

Гипотеза P3e: terminal outcome каждой recovery option можно оценить отдельной
малой головой по observation-only геометрии в момент решения. Выбор между
continue, retreat и full regrasp должен сохранить основной эффект P3c и
предотвратить часть вредных интервенций.

## Архитектура

Для каждой стратегии

$$
j \in \{\text{continue},\text{retreat},\text{full-regrasp}\}
$$

обучается независимая logistic head:

$$
\hat p_j(x)=\sigma\left(w_j^\top z(x)+b_j\right),
\qquad
z_k(x)=\frac{x_k-\mu_k}{s_k}.
$$

Router выбирает:

$$
j^*(x)=\arg\max_j
\left[
\hat p_j(x)-\lambda\frac{c_j}{280}
\right],
$$

где c_continue=0, c_retreat=3, c_full=25 environment steps и
lambda=0.25. Если исходный frozen P3c trigger не проходит, выбор жёстко
переопределяется на continue, что сохраняет exact fallback.

Семь входов доступны до recovery и не используют simulator object pose или
terminal labels:

1. RGB-localized target world x, y, z;
2. localizer peak probability, normalized entropy и score range;
3. estimated target-to-EFF distance.

Модель не получает task_id, perturbation label, init state, outcome другой
ветви или post-intervention observation.

## Development и выбор модели

Открытым development-корпусом служат 75 P3d cases, init 40--44:

- 40 cases в восьми P3c replication cells;
- 35 cases в семи новых cells;
- для каждого case доступны exact-state outcomes трёх recovery options.

Линейный screening сравнил localization-only, phase и uncertainty feature
families, logistic/ridge regularization и фиксированный primitive cost. Оценка
проводилась leave-one-complete-position-task-cell-out. Несколько моделей
достигли одинакового лучшего SR; по simplicity tie-break выбран
localization-only logistic model с C=0.3.

Frozen OOF результат:

| Cohort | Full regrasp | Router | Delta | Rescue / harm |
|---|---:|---:|---:|---:|
| Все 75 | 56/75, 74.7% | 58/75, 77.3% | +2.7 п.п. | 2 / 0 |
| Replication 40 | 25/40, 62.5% | 25/40, 62.5% | 0 | 0 / 0 |
| New-cell 35 | 31/35, 88.6% | 33/35, 94.3% | +5.7 п.п. | 2 / 0 |

Это development model-selection result, не confirmatory claim. Максимальный
three-way oracle на этих данных равен 60/75, поэтому доступный прирост над full
regrasp мал.

## Frozen holdout

- Suite: LIBERO-PRO Object Position, libero_object_temp.
- Cells: те же 8 replication и 7 P3d-new cells.
- Init states: 45--49, не запускавшиеся в P3d.
- Cases: 75, по 5 на cell.
- Common policy: Cosmos Policy K=4, argmax(value).
- Prefix: H16 queries 0--3 и первые 8 actions query 4.
- Decision snapshot: t=72.
- Continuation: H8 feedback, maximum 280 total environment actions.
- Branches: baseline_h8, workspace_retreat_only, workspace_calibrated.
- Trigger, RGB localizer, primitive geometry и all policy hyperparameters
  идентичны P3d.
- Запуск без видео.

Router score вычисляется только из frozen pre-intervention columns. Затем
terminal outcome выбранной стратегии берётся из соответствующей exact-state
ветви. Это counterfactual evaluation эквивалентно online выполнению
детерминированной выбранной ветви, но не требует четвёртого дублирующего
rollout.

## Primary endpoint и gate

Primary comparison: frozen router против frozen workspace_calibrated на всех
75 holdout cases.

Gate проходит только одновременно:

1. 75/75 cases и 225/225 branches complete;
2. snapshot replay error не выше 1e-9;
3. pre-intervention features совпадают во всех трёх ветвях;
4. counterfactual fallback integrity проходит;
5. router имеет не менее двух rescues относительно full regrasp,
   rescues > harms, paired SR delta > 0 и init-bootstrap lower bound >= 0;
6. mean primitive steps не выше full regrasp;
7. target-drop, wrong-object и official-safety rates не выше full regrasp;
8. terminal SR не ниже baseline.

Отдельно сообщаются exact McNemar p, cell-bootstrap interval, результаты
replication/new-cell cohorts, per-cell route counts и final-time delta. Малое
число discordant outcomes может не дать conventional p<0.05; в таком случае
даже прошедший practical gate считается preliminary safe-routing result, а не
полным статистическим подтверждением.

## Anti-leakage решение

- Hyperparameters, features, coefficients, costs и gate заморожены до holdout.
- Holdout init 45--49 не используется для выбора или calibration.
- После просмотра holdout никакой второй P3e router на этих outcomes не
  оценивается.
- FAIL закрывает этот low-data outcome-router и переводит основной приоритет к
  P4 independent dynamics ensemble.
- PASS сохраняет router как практическую надстройку и всё равно требует нового
  unseen-cell confirmatory набора для заявления о широком transfer.

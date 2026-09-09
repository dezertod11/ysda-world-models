# Support-aware invariant CATE: development result

Дата: 3 сентября 2026 года.

## Гипотеза

Провал task-0 signed-VoF ridge был вызван абсолютными action/proprio
координатами и неограниченной экстраполяцией. Новый router оценивает две
ограниченные вероятности успеха:

$$
\widehat p_C(x)=P(S^{commit}=1\mid x),\qquad
\widehat p_F(x)=P(S^{feedback}=1\mid x),
$$

$$
\widehat\tau(x)=\widehat p_F(x)-\widehat p_C(x).
$$

Запрос выполняется, только если состояние находится внутри training support и

$$
\widehat\tau(x)-\beta\widehat\sigma_{epi}(x)>c_{query}.
$$

## Признаки

Используются только данные, известные до re-query: uncertainty текущего Cosmos
query, относительное predicted proprio change, нормы и геометрия prefix/tail
старого action chunk, gripper transitions, согласованность action с predicted
EEF displacement и разброс candidate pool. Абсолютные EEF position/quaternion,
task ID, terminal outcomes и post-query наблюдения исключены.

Обе potential-outcome heads являются L2-regularized logistic models. Epistemic
spread считается по 12 bootstrap-моделям, где единица ресэмплирования равна
`(position level, task, init state)`. Robust scaling, clipping и KNN q99
support gate не позволяют линейной части бесконечно экстраполировать.

## Development screen

На 240 paired states находились 42 rescue и 25 harm. Перебирались только
заранее заданные `alpha={0.001,0.01,0.1}`, `beta={0,0.5,1}` и четыре support
режима. Основные проверки: leave-one-task-out и
leave-one-(task, position-level)-out.

Выбрана deployable-конфигурация:

- relative feature family без task/context IDs;
- logistic regularization `alpha=0.1`;
- `beta=0`;
- `known-level + KNN-q99` support gate;
- query threshold равен цене запроса `c_query=0.025`.

| Split | Query rate | Rescue / harm | AUROC | Adjusted gain | 95% cluster CI |
|---|---:|---:|---:|---:|---:|
| Leave one cell out | 44.6% | 22 / 3 | 0.726 | +6.8 п.п. | `[+2.8; +11.0]` |
| Leave one task out | 43.3% | 23 / 4 | 0.742 | +6.8 п.п. | `[+2.8; +11.0]` |

Always re-query имеет adjusted gain +4.6 п.п. Выбранная модель превосходит
его point estimate примерно на +2.2 п.п., но интервалы разности
`[-3.9; +8.3]` и `[-3.7; +8.2]` пересекают ноль. Поэтому это положительный
development gate, а не подтверждённое превосходство.

Privileged phase не улучшил deployable-модель и не использован. Положительный
результат частично обеспечен корректным отказом от экстраполяции на полностью
исключённые levels; его обязательно надо проверить на новых сочетаниях
task/level.

## Решение

Offline fast gate прошёл. Модель заморожена только для prospective проверки на
всех десяти оставшихся outcome-blind atlas cells. Изменять признаки,
коэффициенты, support threshold или query cost после получения feedback
outcomes запрещено.

Generated tables and predictions:
[`campaigns/signed_vof_new_task_holdout_20260903/analysis/invariant_cate_development/RESULTS.md`](campaigns/signed_vof_new_task_holdout_20260903/analysis/invariant_cate_development/RESULTS.md).

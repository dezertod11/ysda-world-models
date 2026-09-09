# Signed-VoF router: prospective new-task holdout

Дата: 3 сентября 2026 года.

## Постановка

Проверялось, может ли замороженный до сбора исходов signed Value-of-Feedback
router определить, когда на четвёртом query выгодно прервать старый action
chunk, получить реальное наблюдение и перепланировать оставшиеся восемь шагов.
Модель была обучена только на Position `y0.2`, task 0. Проверка выполнена на
шести заранее выбранных non-ceiling cells из новых Object tasks 4, 5, 6 и 8.

Для каждой пары из одного simulator snapshot исполнялись две ветви:

$$
S_i^C = \text{terminal success после commit старого H16},
$$

$$
S_i^F = \text{terminal success после H8, real observation, re-query, H8}.
$$

Signed value of feedback равен

$$
Y_i=S_i^F-S_i^C\in\{-1,0,+1\},
$$

где `+1` означает rescue, а `-1` означает harm. Замороженный ridge-router
использовал только pre-query proprio, старый action chunk и его predicted future
proprio:

$$
R(x)=\widehat{\mu}_{VoF}(x),\qquad
I_i^{query}=\mathbb{1}[R(x_i)>0.1401658544].
$$

Primary cost-adjusted estimand был зафиксирован как

$$
\Delta_{adj}=\frac{1}{N}\sum_i
\left(S_i^{router}-S_i^C-0.025I_i^{query}\right).
$$

Когорта содержит 240 exact-state пар: 6 cells, init states 5-24 и два rollout
seed на init. Все 240 пар прошли replay и terminal-integrity checks.

## Главный результат

| Policy | SR | Query rate | Rescue / harm | Raw gain | Gain после query cost |
|---|---:|---:|---:|---:|---:|
| Always commit | 59.6% | 0% | 0 / 0 | 0.0 п.п. | 0.0 п.п. |
| Always re-query | 66.7% | 100% | 42 / 25 | +7.1 п.п. | +4.6 п.п. |
| Frozen signed-VoF | 61.7% | 52.5% | 24 / 19 | +2.1 п.п. | +0.8 п.п. |
| Oracle query | 77.1% | 17.5% | 42 / 0 | +17.5 п.п. | +17.1 п.п. |

Для frozen router raw cluster-bootstrap 95% CI равен
`[-4.2; +7.9]` п.п., cost-adjusted CI `[-5.4; +7.0]` п.п., exact McNemar
`p=0.542` и rescue-vs-harm AUROC `0.398`. Нижняя граница primary interval не
положительна, поэтому frozen gate **FAIL**, решение:
`do_not_promote_signed_vof_router`.

Always re-query описательно лучше commit на 7.1 п.п., но его cluster CI
`[-0.4; +14.6]` п.п. также пересекает ноль. Это полезный causal opportunity
signal, но не новый confirmatory положительный результат. Oracle показывает,
что правильный state-dependent выбор мог бы дать +17.5 п.п. при запросе только
в 17.5% состояний.

## Неоднородность по cells

| Position | Task | Commit SR | Always re-query | Router | Router query | Router rescue / harm |
|---|---:|---:|---:|---:|---:|---:|
| `x0.2` | 5, tomato sauce | 37.5% | 62.5% | 47.5% | 62.5% | 6 / 2 |
| `x0.2` | 6, butter | 55.0% | 50.0% | 55.0% | 0.0% | 0 / 0 |
| `y0.1` | 4, ketchup | 65.0% | 90.0% | 67.5% | 15.0% | 1 / 0 |
| `y0.1` | 5, tomato sauce | 85.0% | 100.0% | 100.0% | 95.0% | 6 / 0 |
| `y0.2` | 8, chocolate pudding | 70.0% | 87.5% | 90.0% | 50.0% | 9 / 1 |
| `y0.3` | 5, tomato sauce | 45.0% | 10.0% | 10.0% | 92.5% | 2 / 16 |

Одна и та же query-4 интервенция меняет знак в разных режимах. На `y0.1`
task 4 она даёт +25 п.п., но router почти не запрашивает её. На `y0.3` task 5
она даёт -35 п.п., а router выбирает почти все состояния. В сумме router
находит 24/42 доступных rescues (57%), но одновременно выбирает 19/25 harms
(76%). Он не просто недостаточно мощный: его ранжирование переносится в
неверном направлении.

## Почему модель не перенеслась

Каждое holdout-состояние находится вне task-0 training support хотя бы по
одному признаку на `|z|>5`. Медиана максимального `|z|` по строке равна 61.3,
95-й перцентиль 103.8, максимум 654.9.

Главный источник экстраполяции - абсолютные координаты и gripper-компонента
старого действия. Например, `open_candidate_action_first_d6` имел training
scale всего 0.0031. Смена gripper mode примерно с `+1` на `-1` превращалась в
отклонение до 655 training standard deviations и давала вклад в линейный score
до 60.9. Абсолютные proprio и predicted-future-proprio координаты также
кодировали task/phase вместо переносимого эффекта feedback.

Следовательно, высокий development AUROC 0.922 был локальным task-0 signal, а
не task-invariant signed VoF. Post-hoc clipping, support threshold или
исключение `y0.3/task5` могут стать новыми гипотезами, но не исправляют уже
проваленный prospective тест.

## Научный вывод

1. Real-observation feedback имеет существенную причинную ценность, но её знак
   сильно зависит от task, perturbation и фазы манипуляции.
2. Одного общего query index недостаточно: query 4 соответствует разным
   физическим событиям для разных объектов и начальных положений.
3. Raw absolute action/proprio features и unbounded ridge непригодны для
   cross-task routing даже при сильной grouped development-валидации.
4. Generic uncertainty пока не доказана как триггер. Нужен прогноз двух
   потенциальных исходов и их разности, а не локальная корреляция со знаком
   эффекта.
5. Разрыв между always-requery (+7.1 п.п.) и oracle (+17.5 п.п.) оставляет
   достаточно opportunity для следующего метода; направление закрывать рано,
   но текущий router закрыт.

## Следующий замороженный метод

Следующая гипотеза - support-aware invariant CATE router. Вместо прямой
линейной регрессии signed target отдельно оцениваются ограниченные вероятности:

$$
p_C(x)=P(S^C=1\mid x),\qquad
p_F(x)=P(S^F=1\mid x),
$$

$$
\widehat{\tau}(x)=\widehat p_F(x)-\widehat p_C(x),\qquad
query(x)=\mathbb{1}
\left[\widehat\tau(x)-\beta\widehat\sigma_{epi}(x)>c_{query}\right].
$$

Признаки должны быть task-relative: predicted proprio change вместо
абсолютного proprio, форма и кривизна action trajectory, gripper как
категориальный state/transition, contact/progress phase и отношения
target-receptacle. Отдельный support/conformal gate обязан возвращаться к
commit вне training support. Валидация проводится leave-one-task и
leave-one-(task, perturbation)-out и сравнивается одновременно с commit и
always-requery.

Текущие 240 пар теперь являются только development data. Confirmatory outcomes
следует собирать на ещё не использованных atlas cells и новых init states после
полной заморозки features, model family, support gate, query cost и threshold.

## Артефакты

- Полный generated result:
  [`campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/RESULTS.md`](campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/RESULTS.md)
- Transfer diagnostics:
  [`campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/transfer_diagnostics/DIAGNOSTICS.md`](campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/transfer_diagnostics/DIAGNOSTICS.md)
- Summary plot:
  [`campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/signed_vof_holdout_summary.png`](campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/signed_vof_holdout_summary.png)
- Shift plot:
  [`campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/transfer_diagnostics/signed_vof_transfer_diagnostics.png`](campaigns/signed_vof_new_task_holdout_20260903/analysis/frozen_signed_vof_holdout/transfer_diagnostics/signed_vof_transfer_diagnostics.png)
- Frozen protocol and manifest:
  [`SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md`](SIGNED_VOF_NEW_TASK_HOLDOUT_PROTOCOL_20260903.md),
  [`SIGNED_VOF_NEW_TASK_HOLDOUT_FREEZE_MANIFEST_20260903.json`](SIGNED_VOF_NEW_TASK_HOLDOUT_FREEZE_MANIFEST_20260903.json)

# P3 recovery proposals: результаты и разбор метода

Дата анализа: 4 сентября 2026 года.

## Короткий итог

Кампания завершена полностью: 80 заранее зафиксированных exact-state
состояний, три recovery proposal и 240 terminal branches. Все 240 веток прошли
strict replay; максимальная ошибка восстановления simulator state равна нулю.

Главный результат не состоит в том, что уже найден deployable planner.
Результат состоит в локализации bottleneck: простой re-query или blind lift
почти не помогают, тогда как восстановление правильного контакта с целевым
объектом спасает 62 из 80 исходно безуспешных состояний. Значит, в этом наборе
ошибок основная недостающая операция -- не ещё один scalar value score, а
целенаправленный perception-backed regrasp/recovery.

## Что именно проверялось

В development-набор вошли только состояния LIBERO-PRO Position, в которых от
одного и того же сохранённого состояния не справились обе исходные ветки:

1. обычный `max(value)` commit;
2. feedback-вариант `8 действий -> новое наблюдение -> re-query -> 8 действий`.

Следовательно, baseline success rate на этом условном наборе равен `0/80` по
построению. Полученные ниже проценты являются **recovery opportunity rate**, а
не общим LIBERO-PRO benchmark SR.

В общем query при `t=64` Cosmos Policy сэмплирует `K=4` кандидата. Выбирается

$$
j_t^* = \arg\max_{j \in \{1,\ldots,4\}} \hat V_t^{(j)},
$$

после чего первые восемь действий выбранного chunk одинаково выполняются во
всех трёх ветках. Различия начинаются с `t=72`:

| Proposal | Вмешательство | Дальнейшее управление | Deployable |
|---|---|---|---|
| `frequent_requery_h4` | без примитива | каждые 4 шага новый `K=4`, затем `argmax(value)` | да |
| `lift_hold_h8` | 4 раза действие `[0, 0, 0.35, 0, 0, 0, +1]` | каждые 8 шагов новый `K=4`, затем `argmax(value)` | да |
| `privileged_regrasp_h8` | retreat/open, подход над объектом, спуск, close и lift | каждые 8 шагов новый `K=4`, затем `argmax(value)` | нет |

`privileged_regrasp_h8` получает истинную позицию target object из simulator
state. Это диагностический upper bound, а не метод, который допустимо
сравнивать с deployable baselines как готовое решение.

## Основные результаты

| Proposal | Success | Cluster bootstrap 95% CI | Ячейки / задачи с rescue | Drop | Wrong object | Среднее число новых query | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| `frequent_requery_h4` | 7/80 = 8.75% | 3.66-15.19% | 2 / 2 | 6.25% | 5.00% | 51.09 | FAIL |
| `lift_hold_h8` | 8/80 = 10.00% | 3.75-16.46% | 5 / 4 | 13.75% | 13.75% | 25.50 | FAIL |
| `privileged_regrasp_h8` | 62/80 = 77.50% | 68.35-86.42% | 8 / 5 | 6.25% | 7.50% | 15.50 | diagnostic |

У исходной feedback-ветки было 14 model calls после общего snapshot: один
немедленный feedback query и 13 terminal-continuation query. Относительная
стоимость новых веток составляет примерно `3.65x`, `1.82x` и `1.11x`
соответственно. Frequent H4 поэтому не только слаб, но и самый дорогой.

`lift_hold_h8` формально достиг границы 10% SR и дал rescues в нескольких
ячейках, но нарушил frozen safety-side-effect gate: drop rate вырос с 5.0% до
13.75%, то есть на 8.75 п.п. при разрешённых 5 п.п. `frequent_requery_h4` не
достиг ни минимального SR, ни требуемой широты переноса.

Official safety violation равен нулю во всех ветках, но кампания проходила в
обычном LIBERO-PRO, а не в LIBERO-Safety. Поэтому это проверка отсутствия
зарегистрированных побочных событий в данном rollout, а не доказательство
безопасности метода.

## Paired-пересечения

Все стратегии стартовали из точно одинаковых simulator states. Совместные
исходы имеют следующий вид:

| frequent H4 | lift H8 | privileged regrasp | Число состояний |
|---:|---:|---:|---:|
| fail | fail | success | 51 |
| fail | fail | fail | 18 |
| fail | success | success | 4 |
| success | success | success | 4 |
| success | fail | success | 3 |

Каждый из 11 состояний, спасённых хотя бы одной deployable-эвристикой, также
спасается privileged regrasp. Поэтому:

- oracle двух deployable proposals: `11/80 = 13.75%`;
- oracle всех трёх proposals: `62/80 = 77.50%`;
- последний oracle в точности равен одному privileged regrasp.

Это сильнее простого сравнения средних SR: regrasp строго покрывает наборы
успехов обеих эвристик и добавляет ещё 51 rescue. Новое множество полезных
траекторий появляется именно после исправления target/contact geometry.

## Какие исходные fail удаётся исправить

| Failure исходной feedback-ветки | N | Frequent H4 | Lift H8 | Privileged regrasp |
|---|---:|---:|---:|---:|
| Kinematic deadlock | 18 | 0 (0.0%) | 1 (5.6%) | 15 (83.3%) |
| Target drop | 4 | 0 (0.0%) | 0 (0.0%) | 2 (50.0%) |
| Timeout without goal | 42 | 6 (14.3%) | 6 (14.3%) | 34 (81.0%) |
| Wrong-object interaction | 16 | 1 (6.3%) | 1 (6.3%) | 11 (68.8%) |

Regrasp работает не только на одном типе label: он исправляет deadlock,
timeout и значительную часть wrong-object случаев. Drops остаются наиболее
трудным классом. Все 18 его остаточных fail локализованы главным образом в
`y0.2/task4` (9/10 fail, ketchup) и `y0.3/task5` (6/10 fail, tomato sauce),
плюс три случая `x0.2`.

Сам scripted primitive не завершил ни одной задачи. Все 62 успешные ветки
потребовали последующего Cosmos continuation; средний success наступал при
`t=200.5`, а primitive занимал 24-25 шагов. Следовательно, upper bound не
подменяет policy готовым task script: он восстанавливает объект/захват, после
чего learned policy переносит объект и завершает задачу.

## Что говорят uncertainty-метрики

Для `K=4` stochastic candidates основные value-статистики определены как

$$
\bar V = \frac{1}{K}\sum_{j=1}^{K}\hat V^{(j)}, \qquad
\sigma_V = \sqrt{\frac{1}{K}\sum_{j=1}^{K}
  \left(\hat V^{(j)}-\bar V\right)^2}, \qquad
R_V = \max_j \hat V^{(j)}-\min_j \hat V^{(j)}.
$$

Скалярное value в latent representation повторено по элементам выделенного
latent frame. Если эти элементы обозначить через $\tilde v_{j,b,r}$, то

$$
U_{V,\mathrm{internal}}
= \frac{1}{K}\sum_{j=1}^{K}\frac{1}{B}\sum_{b=1}^{B}
  \operatorname{Std}_{r}\!\left(\tilde v_{j,b,r}\right).
$$

Именно эта величина записана как
`candidate_value_internal_consistency_mean`. Она измеряет согласованность
повторённых элементов **внутри** каждого generated latent, а `value_std` и
`value_range` сравнивают четыре независимых stochastic candidates друг с
другом.

В автоматическом отчёте максимальная post-branch association достигает AUC
0.919 для `candidate_value_internal_consistency_mean`. Это **нельзя** считать
качеством готового online selector:

- агрегируются запросы после разных вмешательств;
- успешные ветки почти полностью принадлежат privileged proposal;
- fail-ветки дольше живут до `t=280` и имеют больше query;
- `mean` и `max` используют информацию, появившуюся уже после потенциальной
  ошибки.

На первом запросе после вмешательства association заметно слабее. Лучшие
failure AUC составляют около 0.79 для frequent H4 и 0.72 для privileged
regrasp. Эти числа могут быть полезны как post-recovery alarm, но ещё не как
критерий выбора recovery proposal.

На общем, причинно корректном snapshot `t=64`, то есть **до** выбора proposal,
для исхода privileged regrasp получены:

| Метрика | Pooled failure AUC | Same-cell failure AUC |
|---|---:|---:|
| `candidate_value_internal_consistency_mean` | 0.794 | 0.466 |
| `candidate_value_std` | 0.749 | 0.448 |
| `candidate_value_range` | 0.751 | 0.466 |
| `candidate_value_mean` | 0.705 | 0.793 |

Падение uncertainty AUC ниже 0.5 после сравнения только success/fail внутри
одинаковой `(perturbation level, task)` показывает, что pooled uncertainty в
основном распознавала трудную ячейку, а не индивидуальный будущий fail. Более
интересный exploratory сигнал -- завышенное среднее value: оно сохраняет
same-cell AUC 0.793, но основано лишь на 18 остаточных fail и не проходило
holdout. Это гипотеза о value overconfidence, а не подтверждённый метод.

## Вывод о методе

1. **Больше re-query недостаточно.** Уменьшение horizon с 8/16 до 4 увеличило
   compute в 3.65 раза, но спасло только 8.75% состояний.
2. **Blind recovery опасен.** Lift/hold иногда помогает, но повышает drop rate
   и не проходит заранее заданный gate.
3. **Главный bottleneck -- восстановление контакта.** Oracle regrasp дал
   77.5% rescue и строго включает успехи обеих deployable эвристик.
4. **Cosmos умеет продолжать после repair.** Recovery primitive не решает
   задачу сам; policy успешно завершает 62 repaired trajectories.
5. **Текущая uncertainty не готова выбирать recovery.** Сильные pooled AUC
   обусловлены cell difficulty и post-treatment trajectory length.
6. **Научно перспективная ветка -- perception-backed regrasp**, а не очередная
   линейная комбинация latent/value uncertainty.

## Ограничения вывода

- Это 80 development states из восьми заранее выбранных Position cells, а не
  случайная выборка всего LIBERO-PRO Object benchmark.
- Состояния были отобраны условием `commit fail AND feedback fail`; поэтому
  rescue rate нельзя складывать с опубликованным benchmark SR без отдельного
  end-to-end запуска и модели trigger.
- В данных 79 независимых `perturbation/task/init` groups на 80 состояний;
  confidence intervals кластеризованы по этой группе.
- Privileged regrasp использует simulator target identity и 3D pose.
- Все uncertainty-анализы после просмотра outcomes являются exploratory; ни
  threshold, ни router ещё не заморожены и не проверены на reserve.
- Визуальное совпадение механизма на paired videos поддерживает интерпретацию,
  но численные claims основаны на terminal labels, а не на ручной оценке видео.

## Следующий confirmatory эксперимент

На текущих 80 development states следует заменить истинную 3D-позицию объекта
на наблюдаемый pipeline: target localization по agent/wrist RGB, оценка 3D
позиции, visual servo, close/lift и проверка успешного контакта по движению
объекта и proprio/gripper. Формула выбора последующего Cosmos chunk остаётся
обычным `argmax(value)`, чтобы отдельно измерить вклад recovery.

После заморозки detector, контроллера и всех thresholds проводится один тест на
109 untouched both-fail states. Сравниваются ordinary feedback, deployable
perception regrasp и privileged upper bound. Primary metric -- exact-state
rescue rate; обязательные secondary metrics -- drop, wrong object, official
safety, model-query multiplier и доля корректно подтверждённых grasp. Текущий
development набор больше нельзя использовать для confirmatory claim.

## Артефакты

- Автоматический отчёт: [`campaigns/recovery_proposal_opportunity_20260904/analysis/RESULTS.md`](campaigns/recovery_proposal_opportunity_20260904/analysis/RESULTS.md)
- Основная таблица: [`campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_proposal_summary.csv`](campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_proposal_summary.csv)
- Разрез по ячейкам: [`campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_cell_summary.csv`](campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_cell_summary.csv)
- Pre-intervention AUC с same-cell control: [`campaigns/recovery_proposal_opportunity_20260904/analysis/pre_intervention_metric_separation.csv`](campaigns/recovery_proposal_opportunity_20260904/analysis/pre_intervention_metric_separation.csv)
- График: [`campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_opportunity.png`](campaigns/recovery_proposal_opportunity_20260904/analysis/recovery_opportunity.png)
- Все 240 paired videos: [`campaigns/recovery_proposal_opportunity_20260904/analysis/video_index.html`](campaigns/recovery_proposal_opportunity_20260904/analysis/video_index.html)

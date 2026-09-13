# Итоги consensus и P5 data pilot

Проверено 10 сентября 2026 года, около 00:20 MSK. Ночная очередь
`consensus_p5_night_20260909` завершилась **9 сентября в 20:31 MSK**,
включая анализ. Активных процессов экспериментов проекта при проверке нет.
Новых GPU-экспериментов в рамках этого разбора не запускали.

## Краткий вывод

**Два этапа исследований, а не два готовых новых метода.**

1. Завершено сравнение шести deployed selectors: убедительного преимущества
   consensus над max-value не обнаружено. Наибольший численный macro-SR у
   KeyStone-style, но это известный подход и статистически неубедительный gain.
2. Завершён P5-пилот с реальными исходами ветвей. Обученной P5-модели ещё нет.
   Данные целостны, однако при K8 только **1/36 состояний** имеет возможность
   исправить max-value другой веткой. В **17/36** все проверенные ветви fail.

Resident worker, а также cold/resident A/B/A, относятся к инфраструктуре и
проверкам воспроизводимости. Они не являются новыми planning-методами и не
включены в таблицы SR ниже.

## 1. Что запускалось

| Этап | Объём | Итог |
| --- | --- | --- |
| Предыдущий compact: K1 / max-value / OSC-medoid | 597 rollout | Сохранённые результаты использованы без пересчёта |
| Новые references: raw-medoid / KeyStone-style / KDPE adaptation | 597 rollout, 357 jobs | Все завершены |
| Объединённый closed-loop анализ | 1194 rollout, 199 конфигураций x 6 методов | Завершён |
| P5 integration smoke | 1 snapshot, 8 terminal branches | Replay проверен; не включён в pilot statistics |
| P5 development data pilot | 36 snapshots, 288 terminal branches, 18 jobs | Все завершены; 36/36 strict replay pools |

Reference integration smoke также завершены, но не входят в 1194 основных
rollout. Ни обучение новой P5-модели, ни её closed-loop тест, ни новый
confirmatory holdout в этой очереди не запускались.

## 2. Сравнение шести стратегий

Использована **LIBERO-PRO Object suite** с тремя факторами: Object,
Environment, Position. На метод: 50 Object, 50 Environment и 99 Position
конфигураций; все 10 задач. Один исходный случай `y0.5/task1/init1` исключён
у всех методов, поскольку benchmark asset содержит ноль состояний, а не
потому, что модель провалила задачу. Это valid199, не полный стандартный
benchmark и не исходный план full4500.

Сгенерированный и выполняемый chunk: **H16**, denoising steps: **5**,
бюджет: **280 шагов**. K4 у пяти selectors, K1 у контроля. Actions/future/value
генерируются совместно, `prediction_mode=parallel`. Это не авторское
авторегрессионное планирование Cosmos по цепочке action -> state -> value.

| Метод | Смысл |
| --- | --- |
| K1 | Один stochastic candidate, без выбора из нескольких |
| Max-value K4 | Выбрать один из четырёх кандидатов с наибольшим predicted value |
| OSC-medoid K4 | Наш consensus по геометрии накопленных OSC-команд |
| Raw-medoid K4 | Медоид по L2 между исходными flattened action chunks |
| KeyStone-style K4 | Фиксированный cluster/medoid selector с guard, без нового подбора настроек |
| KDPE endpoint K4 | Kernel density на induced OSC endpoints, адаптация исходного метода |

Параметры reference-стратегий зафиксированы до их сбора. Подробности
адаптаций: [reference protocol](CONSENSUS_REFERENCE_PROTOCOL_20260908.md).
KDPE здесь не является воспроизведением исходного N100 pose-action опыта,
а KeyStone не воспроизводит всю авторскую batching/latency инфраструктуру.

### Результаты

| Метод | Object SR | Environment SR | Position SR | Macro-SR | Success / 199 |
| --- | ---: | ---: | ---: | ---: | ---: |
| K1 | 94.00% | 38.00% | 28.28% | 53.43% | 94 |
| Max-value K4 | 94.00% | 40.00% | 30.30% | 54.77% | 97 |
| OSC-medoid K4 | 96.00% | 40.00% | 26.26% | 54.09% | 94 |
| Raw-medoid K4 | 94.00% | 42.00% | 28.28% | 54.76% | 96 |
| KeyStone-style K4 | 98.00% | 40.00% | 29.29% | **55.76%** | **98** |
| KDPE endpoint K4 | 94.00% | 40.00% | 25.25% | 53.08% | 92 |

$$
\mathrm{MacroSR}=\frac{\mathrm{SR}_{Object}+\mathrm{SR}_{Environment}
+\mathrm{SR}_{Position}}{3}.
$$

Macro-SR даёт факторам одинаковый вес. Это не доля всех success из 199:
например, у max-value micro-SR = 97/199 = 48.74%, поскольку Position
содержит больше случаев. Оба расчёта корректны, но отвечают разным весам
факторов и не должны смешиваться.

| Метод против max-value | Разница macro-SR, п.п. | 95% cluster bootstrap CI, п.п. | Rescue / harm |
| --- | ---: | --- | ---: |
| K1 | -1.34 | [-5.00; +2.01] | 5 / 8 |
| OSC-medoid | -0.68 | [-3.33; +1.99] | 3 / 6 |
| Raw-medoid | -0.01 | [-3.35; +3.33] | 6 / 7 |
| KeyStone-style | +1.00 | [-2.01; +4.33] | 6 / 5 |
| KDPE endpoint | -1.68 | [-4.77; +1.33] | 3 / 8 |

Rescue: baseline fail, сравниваемый метод success; harm: обратная ситуация.
Bootstrap группирует task/init внутри факторов. Во всех пяти основных
сравнениях Holm-adjusted McNemar p = 1.0. Это **не доказательство равенства**
методов, но статистически убедительного превосходства здесь нет.
McNemar использует дискордантные episode outcomes; не следует выдавать его
за отдельный тест равновзвешенного macro-estimand. Per-factor эффекты
описательные, не дополнительные подтверждённые выигрыши.

### Интерпретация

- KeyStone выигрывает у max-value всего один success суммарно. Object gain
  47/50 -> 49/50 целиком находится на task0: 3/5 -> 5/5. Position при этом
  теряет один success. Нового переносимого метода этот результат не доказывает.
- OSC geometry не показала преимущества: Object +1 success, Position -4.
  Raw-medoid почти совпал с baseline по macro-SR. Продолжать широкий подбор
  consensus coefficients на уже просмотренном benchmark не следует.
- Environment и Position остаются трудными для всех selectors. Environment
  tasks 0,2,6 дали 0/5 у всех шести методов; на task7 только raw-medoid дал
  1/5. Это наблюдение по данной сетке, не доказательство невозможности задач.
- Drop-прокси насчитали 2-4 эпизода на метод. Этого недостаточно для вывода
  об улучшении безопасности; это также не отдельный LIBERO-Safety benchmark.

Начальные simulator states совпадают с точностью 1e-9 и task/init/seeds
сопоставлены. Но побитово одинаковые q0 K4 candidate pools встречаются лишь
в 31-46% пар с max-value. Следовательно, сравнение проверяет deployed
контроллеры, но не изолирует исключительно selector на одном и том же pool.
Это ограничение дополняет [исследование воспроизводимости](COSMOS_QUERY_REPRODUCIBILITY_RESULTS_20260902.md).

## 3. Что показал P5-пилот

Данные: Object tasks 0,3; Position x0.2 tasks 0,2,9 и y0.2 tasks 0,2,4,9;
init 7,8; snapshots на q0 и q3, то есть t=0 и t=48. Итого 18 task/init
групп, 36 состояний; q0/q3 одной группы зависимы. Environment в новом pilot
не входит. Это development-набор, не новый untouched test.

Из каждого captured state получены K8 H16 кандидатов. Каждый action chunk
выполнен в среде, после чего одна и та же K1/H16 continuation policy
доводила ветку до terminal outcome в пределах бюджета. Все 288 исходов
доступны; frozen replay/feature gate прошёл. K4 ниже означает первые четыре
кандидата того же K8 pool, а не отдельный rollout с K4 на каждом query.

$$
i_V(K)=\arg\max_{i\le K}V_i,\quad
O_K(s)=\max_{i\le K}Y_i,\quad
R_K(s)=O_K(s)-Y_{i_V(K)}.
$$

$Y_i$ есть реально измеренный terminal success ветки. $O_K$ есть
недоступный online oracle на этих ветках, а $R_K=1$ означает, что в pool
есть success, который max-value не выбрал. Терминальные labels не подаются
модели до выполнения действий.

| Показатель, 36 состояний | K4 | K8 |
| --- | ---: | ---: |
| Смешанные success/fail pools | 13 | 16 |
| Все кандидаты fail | 17 | 17 |
| Все кандидаты success | 6 | 3 |
| Success при max-value | 15/36 (41.67%) | 18/36 (50.00%) |
| Oracle: хотя бы один success | 19/36 (52.78%) | 19/36 (52.78%) |
| Можно исправить выбор max-value | 4/36 | **1/36** |
| Uniform random, точное среднее исходов | 37.50% | 35.76% |

**16 mixed pools не равны 16 исправимым провалам.** На K8 max-value уже
выбирает success в 15 из 16 mixed pools. Из его 18 failed состояний 17
не имеют ни одного успешного кандидата в проверенной восьмёрке. Максимальное
эмпирическое улучшение за счёт одного только выбора в этих сохранённых
ветках: 1/36 = **2.78 п.п.**, не большой подтверждённый резерв.

Это ограничение конкретных candidates, snapshots и одной realization
continuation. Оно не означает необратимость среды, отсутствие других
успешных действий или универсальную верхнюю границу P5.

K8 против вложенного K4 дал 3 rescue / 0 harm, все на q3. Но oracle не
вырос: новая восьмёрка не добавила ни одного состояния, где появился бы
первый успех. В трёх уже mixed состояниях max-value выбрал дополнительные
успешные candidates. Это описательный результат 18 групп, не доказательство
эффективности нового метода и не full-episode K8 benchmark.

На q3 K8 max-value реализовал все 10/18 доступных oracle successes;
на q0: 8/18 против oracle 9/18. Значит, ошибка выбора в новом pilot
не сосредоточена исключительно на q3. Универсальный trigger q3/t48 из этого
делать нельзя.

### Единственный K8 selection failure

`Position y0.2 / task9 / init8 / query0`:
`pick up the orange juice and place it in the basket`.

Max-value выбрал candidate 0 с value 0.323752: fail на лимите 280 шагов,
эвристический тип `kinematic_deadlock_candidate`. Кандидаты 1,2,6,7 успешно
завершились за 169-179 шагов, хотя их predicted values были ниже. Этот
пример полезен для проверки ranking и continuation noise, но нельзя
обучить на нём метод и затем объявить его исправление независимым тестом.
Малый разброс values в этом примере сам по себе не обеспечил правильный выбор.

У 18 K8 max-value fail ветвей автоматические типы: 12 `timeout_no_goal`,
4 `wrong_object_interaction_candidate`, 2 `kinematic_deadlock_candidate`.
Drop-прокси среди них не сработал. Это не ручная диагностика по видео:
timeout не доказывает, что робот непременно справился бы при большем лимите.

### Почему PASS данных недостаточно

Frozen gate требовал >=8 mixed pools на >=3 task IDs и обоих факторах.
Он пройден: 16 mixed, пять task IDs, 10 task/init групп. Этот gate проверял
наличие contrastive labels, но не требовал большого числа ошибок max-value.
Поэтому `opportunity_gate=true` сохраняется в исходном отчёте, а решение
после дополнительного анализа: **не открывать большой P5 fit/holdout
автоматически**. Сам P5 как направление не опровергнут.

## 4. Что делать по результатам

1. Закрыть эту frozen consensus-серию как результат без убедительного
   выигрыша. Оставить max-value, K1 и KeyStone-style в качестве контролей;
   не объявлять OSC-medoid новым лучшим методом.
2. Следующая небольшая P5-проверка: повторять сохранённые actions с другими
   общими continuation seeds, включая исправимые, mixed и all-fail controls.
   Проверить, насколько устойчивы terminal labels и преимущество кандидатов.
3. Сначала искать candidate-dependent task/contact/target информацию на
   сохранённых данных и сравнивать со state-only/shuffled-action controls.
   Общий риск состояния может управлять feedback/compute, но один и тот же
   штраф всем кандидатам не меняет argmax и не решает selection problem.
4. Для all-fail состояний проверять изменение proposals, дополнительное
   реальное наблюдение или recovery, а не только другой score на тех же
   действиях. Это приоритетная гипотеза, не уже измеренный gain в pilot.
5. Новый научный claim требует frozen метода и проспективных целых task/cell
   holdout. 36 snapshots и один K8 rescue для этого недостаточны.

## Артефакты

- [Полная таблица шести методов](campaigns/consensus_references_20260909_valid199/matched_analysis/RESULTS.md),
  [график по факторам](campaigns/consensus_references_20260909_valid199/matched_analysis/factor_success_rates.png).
- [Исходный P5 audit](campaigns/p5_boundary_candidates_20260909/p5_analysis/RESULTS.md),
  [первичный summary с неизменённым gate](campaigns/p5_boundary_candidates_20260909/p5_analysis/summary.json).
- [Дополнительный разбор и SHA исходных таблиц](campaigns/p5_boundary_candidates_20260909/opportunity_review_20260910/summary.json),
  [K4/K8](campaigns/p5_boundary_candidates_20260909/opportunity_review_20260910/by_k.csv),
  [q0/q3](campaigns/p5_boundary_candidates_20260909/opportunity_review_20260910/by_query.csv),
  [исправимые случаи](campaigns/p5_boundary_candidates_20260909/opportunity_review_20260910/rescue_cases.csv),
  [восемь кандидатов единственного K8 rescue case](campaigns/p5_boundary_candidates_20260909/opportunity_review_20260910/k8_missed_pool.csv).
- [Matched video gallery](campaigns/consensus_references_20260909_valid199/matched_analysis/videos.html)
  содержит серверные пути: MP4 остаются на сервере. Копирование отчёта не
  делает эту галерею переносимой; отдельный video export сейчас не выполнялся.

Исходные configs, methods, runtime, primary summaries и гиперпараметры не
изменялись. Дополнительные таблицы вычислены из сохранённых данных, без
новых WM calls и без подбора метода по этим результатам.

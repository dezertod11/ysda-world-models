# Trajectory consensus: результаты и перспектива ICLR

Дата проверки: 8 сентября 2026 года, около 14:00 MSK.

**Поздний срез 18:30 MSK:** [compact 539/600, метрики на 179 полных тройках
и сравнение со статьями](TRAJECTORY_CONSENSUS_INTERIM_RESULTS_20260908.md).
Medoid пока не улучшает max-value; финального результата compact ещё нет.

**Обновление после этого среза:** связь с сервером восстановилась; в 14:13
подтверждены 400/600 rollout и продолжающийся compact. Запущена отдельная
[очередь matched references](CONSENSUS_REFERENCE_PROTOCOL_20260908.md),
завершён [common-pool анализ](CONSENSUS_COMMON_POOL_RESULTS_20260908.md).
Ниже сохранён исходный разбор development; его таблица не является compact SR.

## 1. Какие результаты действительно доступны

Проверены локальные CSV завершённого development
`trajectory_consensus_20260908_development`: **392 rollout, 7 методов,
56 одинаковых task/init/seed конфигураций на метод**. Из кода проверена
реализация `trajectory_medoid`, из freeze manifest проверен выбранный метод.

Свежий статус серверной кампании `trajectory_consensus_20260908_compact`
установить не удалось: две SSH-попытки завершились
`Connection timed out during banner exchange`. Последний локальный
`sequence_status.json` обновлён в **10:45:39 MSK** и содержит `running`.
Это устаревший срез, а не подтверждение текущего состояния процесса.
Ни завершение, ни остановку этой кампании сейчас не утверждаем.

Compact рассчитан на **600 rollout: K1, max-value K4, medoid K4,
по 200 на метод**. На старте перенесено 35 эпизодов, 565 должны были
вычисляться заново. Его итогового отчёта локально пока нет. Все проценты
ниже относятся **только к development**, не к этим 600 rollout.
Исходный full4500 был заменён compact, а не завершён.
[Протокол сокращения](TRAJECTORY_CONSENSUS_COMPACT_PROTOCOL_20260908.md).

## 2. Какой именно метод проверяется

Замороженный checkpoint Cosmos Policy генерирует K=4 варианта из одного
текущего observation и команды с разным sampling noise. Каждый вариант
содержит action chunk, предсказанное будущее и value. Режим `parallel`:
совместная генерация, **не** авторегрессионная цепочка a -> s -> v.
Генерируем и выполняем H=16, используем 5 denoising steps, лимит 280 действий.

Базовый selector выбирает:

$$
i_V=\arg\max_i V_i.
$$

Проверяемый `trajectory_medoid` выбирает реально сгенерированный chunk,
наиболее близкий к остальным в пространстве приближённых траекторий:

$$
i_M=\arg\min_i\frac1K\sum_{j=1}^{K}D(A_i,A_j).
$$

При равенстве consensus score выбирается больший value, затем меньший индекс.
Value не входит в основной score. Этот winner не является методом
`value - lambda * uncertainty`, value-density gate или новой обученной моделью.

Для native OSC-команд $a_{i,t}=(u^p_{i,t},u^r_{i,t},u^g_{i,t})$, обрезанных
до [-1,1], код строит дескрипторы:

$$
p_{i,t}=\sum_{k=1}^{t}0.05u^p_{i,k},\qquad
R_{i,t}=\operatorname{Exp}(0.5u^r_{i,t})R_{i,t-1},\qquad R_{i,0}=I,
$$

$$
g_{i,t}=\begin{cases}+1,&u^g_{i,t}\ge0,\\-1,&u^g_{i,t}<0.\end{cases}
$$

В выбранном medoid временного выравнивания нет: сравниваются одинаковые t.

$$
D(A_i,A_j)=\sum_{t=1}^{16}w_t\left[
\frac{\lVert p_{i,t}-p_{j,t}\rVert_2}{0.05}
+0.5\frac{\theta(R_{i,t}R_{j,t}^{\top})}{0.5}
+0.25\mathbf1(g_{i,t}\ne g_{j,t})\right],
\qquad w_t=\frac{0.95^{t-1}}{\sum_{k=1}^{16}0.95^{k-1}}.
$$

$\theta$ обозначает угол относительного вращения. Положение, поворот и
состояние захвата получают разные масштабы; ранние действия весят больше.
Это **kinematic command descriptor**, не симуляция реального движения:
контакт, скольжение, упругость контроллера и падение объекта здесь не вычисляются.
Consensus score не является дисперсией, калиброванной вероятностью fail
или самостоятельной оценкой epistemic uncertainty.

Источник: [trajectory_consensus.py](../cosmos-policy/cosmos_policy/experiments/robot/libero/trajectory_consensus.py),
[полный протокол](TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md).

## 3. Результаты development

Object и Environment: 10 задач x init 0,1, по 20 rollout на метод.
Position: задачи 0,2,5,9 x уровни x0.2,y0.2,x0.3,y0.3 x init 0,
16 rollout на метод. Поэтому macro-SR усредняет три факторных SR с равными
весами, а не все эпизоды сразу.

| Метод | Object | Environment | Position | Macro-SR | Success / 56 |
|---|---:|---:|---:|---:|---:|
| K1, без отбора | 95.0% | 40.0% | 25.0% | 53.33% | 31 |
| Max-value K4 | 95.0% | 40.0% | 37.5% | 57.50% | 33 |
| Старый guarded consensus K4 | 100.0% | 40.0% | 37.5% | 59.17% | 34 |
| Trajectory density K4 | 95.0% | 45.0% | 37.5% | 59.17% | 34 |
| **Trajectory medoid K4** | **95.0%** | **45.0%** | **37.5%** | **59.17%** | **34** |
| Value-density v2_0 | 90.0% | 40.0% | 31.25% | 53.75% | 31 |
| Value-density aligned v2_1 | 90.0% | 40.0% | 37.5% | 55.83% | 32 |

Medoid против max-value: **+1.67 п.п. macro-SR**, bootstrap 95% CI
**[-3.33; +8.33] п.п.**, 3 rescue / 2 harm, exact McNemar **p=1.0**.
Это не доказательство превосходства или эквивалентности: данных мало,
а этот же development использовался для выбора winner из нескольких методов.
Приведённые интервалы не исправляют оптимизм такого отбора.

Medoid и density имеют одинаковые success/fail исходы на всех 56 случаях.
Старый guarded имеет тот же macro-SR, но иной набор исходов. Поэтому
результаты пока не выделяют новую геометрию как уникально полезный компонент.

Источники: [factor_scores.csv](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/factor_scores.csv),
[paired_effects.csv](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/paired_effects.csv),
[episode_outcomes.csv](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/episode_outcomes.csv),
[график SR](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/factor_success_rates.png).

### Где изменились исходы относительно max-value

| Фактор / задача / init / seed | Max-value | Medoid | Интерпретация |
|---|---|---|---|
| Object / task0 / init0 / 19000000 | fail, t=280 | success, t=159 | rescue |
| Object / task0 / init1 / 19010000 | success, t=227 | fail, t=280 | harm |
| Environment / task9 / init1 / 21910000 | fail, t=280 | success, t=115 | rescue |
| Position x0.2 / task9 / init0 / 24900000 | success, t=129 | fail, t=280 | harm |
| Position y0.2 / task9 / init0 / 26900000 | fail, t=280 | success, t=166 | rescue |

Task0: `pick up the alphabet soup and place it in the basket`.
Task9: `pick up the orange juice and place it in the basket`.
Чистый прирост даёт **один Environment episode task9**. В Object и Position
rescue и harm компенсируются. Достижение лимита t=280 означает отсутствие
официального success к лимиту, но не устанавливает визуальную причину fail.
Покадровой проверки новых серверных видео в этом анализе не было.

### Что показывают дополнительные проверки

- Medoid отличается от max-value внутри своего текущего pool в **574/720
  queries, 79.72%**. Selector активен, но частые изменения не дают соразмерного
  улучшения terminal success. Нельзя заключать, что все изменения бесполезны:
  дальнейшие состояния и pool расходятся между траекториями.
- Начальные simulator states совпадают в **56/56** парах; q0 action pool
  побитово совпадает только в **22/56**. Это paired deployment comparison,
  не чистая проверка двух selector на одном pool в каждом query.
- Medoid имеет 0/56 target-drop proxy против 1/56 у max-value. Одного события
  недостаточно для вывода о безопасности; это не LIBERO-Safety benchmark.
- Интервал рассчитан bootstrap task/init внутри каждого фактора, с сохранением
  Position levels в одном cluster. Он не доказывает перенос на новые задачи;
  в Position всего четыре задачи, по одному init.
- Job time включает загрузку модели, rendering, I/O и меняющуюся конкуренцию
  за GPU. Числа seconds/query в текущем отчёте не доказывают ускорение метода.
  K1 и K4 также не являются compute-matched сравнением.

Источник: [cost_and_switch_rates.csv](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/cost_and_switch_rates.csv).

## 4. Научные выводы о методе

**Подтверждено:** controller-scaled medoid реализован и работает в closed loop;
на development он сравним по наблюдаемому SR с max-value и старым guarded.
Два проверенных value-density варианта не улучшили max-value. H16 исправляет
старую проблему сравнения предсказанного H16 future с фактическим H5.

**Не подтверждено:** универсальное улучшение planning, снижение вероятности
падения, повышение калибровки value, superiority новой геометрии, перенос на
другую модель, положительный результат compact600. Неудача двух конкретных
value-density настроек также не опровергает всё семейство методов.

**Гипотеза для объяснения, не установленный факт:** consensus помогает убрать
отдельные неудачные stochastic samples, но не исправляет систематически
ошибочное восприятие или захват. Несколько почти одинаковых chunks могут
вести к одному fail. Для проверки нужны terminal outcomes всех кандидатов
из одного сохранённого состояния и одного pool.

## 5. Новизна относительно статей

[KeyStone, Geometry Guided Self-Consistency for Physical AI](https://arxiv.org/html/2605.08638v1)
уже выбирает medoid основного кластера sampled action chunks; при unimodal
guard использует global medoid. Наше отличие: глобальный medoid в метрике
интегрированных OSC-команд, а не clustering flattened actions. В статье
проверены несколько VLA/WAM и бенчмарков, включая LIBERO. Следовательно,
сама идея sample-many/select-medoid не является нашей новизной. Старый
KeyStone-style screen с другим H/K не заменяет matched baseline здесь.

[KDPE, CoRL 2025](https://arxiv.org/abs/2508.10511) уже использует kernel
density selection и manifold-aware геометрию position/orientation/gripper.
Поэтому учёт физической структуры action representation тоже нельзя
представлять как полностью новый принцип. Ценность адаптации к Cosmos
надо показать экспериментально, включая сравнение геометрий при одном K/H.

Это анализ пересечения идей, а не утверждение о полной идентичности кода.
Также не переносим опубликованное обещание низкого sampling overhead
на наш joint video/action/value sampler без отдельного профилирования.

## 6. Что это означает для ICLR

Моя оценка: **текущий medoid сам по себе пока недостаточен как центральный
новый метод сильной ICLR submission**. Причины: близкие prior methods,
один дополнительный development success, отсутствие независимой итоговой
проверки в доступных данных и анализа того, почему выбранный candidate лучше.
Это оценка доказательной базы, не прогноз решения рецензентов.

ICLR оценивает новизну знания, значимость, корректность и строгость выводов;
обязательного SOTA-score не требует. Содержательный эмпирический результат
тоже может быть вкладом. Это явно отражено в
[ICLR 2027 Reviewer Guidelines](https://iclr.cc/Conferences/2027/ReviewerGuidelines).

Более сильный возможный фокус нашей работы: **когда selection по внутренним
предсказаниям не помогает и когда нужны новые наблюдения или recovery**.
Его поддерживают разные, но не взаимозаменяемые результаты:

| Уже проверенная линия | Основное наблюдение | Ограничение |
|---|---|---|
| [P4b residual risk](P4B_RESIDUAL_RISK_RESULTS_20260907.md) | Global failure AUROC 0.650, within-pool concordance 0.509; SR 58.5% -> 56.5% | Предсказание сложности состояния не равно ранжированию действий |
| [Shared-prefix feedback](OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md) | 46/100 -> 64/100, +18 п.п., CI [+4; +32] | Object task0, фиксированная фаза query4 |
| [P3c RGB recovery](PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md) | 13/40 -> 24/40, +27.5 п.п., CI [+12.5; +42.5] | Новые init знакомых Position cells |
| [P3e recovery router](P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md) | 53/75 full-regrasp -> 55/75 router, p=0.5 | Большой выигрыш над policy главным образом от recovery, не доказанное преимущество router |

Пока это аргумент в пользу выбранного исследовательского вопроса, а не
доказательство универсальной теории или готового универсального controller.

## 7. Следующие проверки в порядке приоритета

1. Получить compact600 и пройти completeness/init/seed/video checks.
   Оставить frozen medoid неизменным; результат использовать как итоговую
   проверку, не как очередную выборку для подбора lambda. Primary:
   macro-SR и paired delta к K4 max-value, отдельно три фактора.
2. Переиспользовать exact-state K4 terminal branches для проверки механизма:
   сравнить random, max-value и medoid на одном pool и continuation policy.
   Разделить состояния без успешных кандидатов и состояния с возможностью
   улучшить выбор. Это отдельный estimand, не замена closed-loop SR.
3. Сопоставить KeyStone, KDPE-style, raw-action medoid и OSC medoid при одном
   K/H/denoising budget. Ablation: integration, rotation, gripper, temporal
   weighting. Выбирать настройки на development; не перебирать все на holdout.
4. Если появляется устойчивый эффект, проверить новые cells/init и вторую
   policy либо независимый benchmark. Другая policy проверяет более общий
   claim; отсутствие такого теста требует сузить название и выводы до Cosmos.
5. Для статьи подготовить paired task/cell-level CI, rescue/harm и
   стандартизированную latency/VRAM оценку. Добавить сильный recovery control:
   улучшение относительно policy не доказывает пользу learned routing.

Для п.2 полезны диагностические величины при фиксированном состоянии s,
pool и общей continuation policy. Пусть $Y_i\in\{0,1\}$ есть **фактически
измеренный terminal outcome** ветки кандидата i:

$$
O(s)=\max_i Y_i-Y_{i_V},\qquad
R_M(s)=\max_i Y_i-Y_{i_M}.
$$

O показывает доступный выигрыш над max-value, R показывает regret medoid.
Если все $Y_i=0$, этот конкретный pool не даёт успеха ни одному selector.
Это не означает, что состояние невосстановимо при других proposals.
Y доступны только после выполнения ветвей и используются для анализа,
не как вход online policy. Такое разложение является диагностикой, не
заявкой на новую теорему.

## 8. Сроки и файлы

Для ближайшего цикла **ICLR 2027**: abstract до **18 сентября 2026 AoE**,
paper до **25 сентября 2026 AoE**. Это соответственно 19 и 26 сентября
до 14:59:59 MSK. Состав авторов нужно зафиксировать к abstract deadline;
OpenReview profiles стоит проверить сейчас. Источники:
[Call for Papers](https://www.iclr.cc/Conferences/2027/CallForPapers),
[Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines).

Не стоит успевать за счёт сокрытия отрицательных результатов или выдачи
development за подтверждающий тест. Сузить научный claim важнее, чем
добавить ещё один неподтверждённый коэффициент к score.

Полный [автоматический development-отчёт](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/RESULTS.md),
[общий итог исследований](RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md).
Галерея development сохранена в
[videos.html](campaigns/trajectory_consensus_20260908_development/trajectory_analysis/videos.html),
но пути внутри относятся к серверу; этот HTML не является автономным
локальным видеоэкспортом.

В этой проверке GPU-эксперименты не запускались и frozen configs не менялись.
Отчёт сохранён локально; из-за недоступности SSH на сервер не синхронизирован.

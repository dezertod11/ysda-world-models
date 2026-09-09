# Perception-backed regrasp: development results

Дата: 4 сентября 2026 года.

## Задача

На frozen P3 corpus обе обычные ветки Cosmos Policy завершились fail, тогда как
диагностический `privileged_regrasp_h8` с истинной simulator pose цели спас
62/80 состояний. Здесь проверяется deployable замена: после общего H8 prefix и
retreat/open определить target только по текущему `agentview` RGB и language,
выполнить regrasp, затем вернуть управление исходному `K=4`, `argmax(value)`,
H8 planner.

## Разделение данных

| Split | Строки | Независимые `task/init` группы | Назначение |
|---|---:|---:|---|
| RGB calibration | 388 | 194 | supervised perception и grouped OOF |
| terminal development | 80 | 79 | screen-20, затем полный efficacy gate |
| strict confirmatory reserve | 72 | 47 | primary one-shot confirmatory test |
| исходный reserve | 109 | 84 | только sensitivity |

Calibration исключает целые группы из обоих downstream splits: group-overlap
равен нулю. Исходный 109-row reserve пересекался с development по 37 группам;
поэтому до просмотра outcomes первичным объявлен его 72-row group-disjoint
subset.

## Offline model selection

| Кандидат | Grouped OOF pixel median / p90 | World-XY median / p90 | Решение |
|---|---:|---:|---|
| CLIP ViT-B/16 patches + weighted ridge | 8.47 / 41.65 px | 6.70 / 19.86 cm | FAIL |
| DeepLab heatmap + global metric depth | 2.24 / 4.12 px | 1.85 / 5.574 cm | FAIL: p90 выше gate на 0.074 cm |
| DeepLab heatmap + local depth ablation | 2.24 / 4.12 px | 1.91 / 15.19 cm | FAIL |
| DeepLab + global cross-fitted depth | 2.24 / 4.12 px | 2.03 / 5.29 cm | FAIL: worst-object median 4.28 cm |
| DeepLab + object-routed depth | 2.24 / 4.12 px | 1.64 / 3.33 cm | **PASS** |

Frozen offline gate: median XY <= 2.5 cm, p90 XY <= 5.5 cm, p90 Z <= 6 cm,
worst-object median XY <= 4 cm. Порог после результатов не изменялся.

### Heatmap

Для известного из language target object $o$ сеть предсказывает spatial logits:

$$
p_o(u,v\mid I)=\operatorname{softmax}_{u,v} h_o(I)_{u,v},
\qquad
\mathcal L_{xy}=-\log p_o(u^*,v^*\mid I).
$$

Три OOF-модели обучаются параллельно на GPU 3/6/7. Все три независимо дали
p90 pixel error от 3.96 до 4.63 px в первой strict итерации. Следовательно,
главный оставшийся offline bottleneck -- metric depth, а не распознавание
target в плоскости изображения.

### Cross-fitted depth

Последняя development-гипотеза объединяет global depth, local depth в пике
heatmap, координату пика и object identity:

$$
\hat z_i = \operatorname{clip}\!\left(
\mathbf w_{-f(i)}^\top
\phi(\hat z_i^g,\hat z_i^l,\hat u_i,\hat v_i,o_i),
z_{\min},z_{\max}\right).
$$

Для каждого held-out fold коэффициенты обучаются только на двух остальных
fold. Ridge regularization и depth mode выбираются по cross-fitted p90
world-XY. Только после offline PASS обучается один full frozen model.

Object-routed вариант использует известное из команды имя цели и для каждого
объекта выбирает estimator с наименьшим OOF p90 world-XY среди global neural,
local neural, object median и stacked ridge:

$$
m_o^*=\arg\min_{m\in\mathcal M_o}
Q_{0.9}\!\left(\lVert\hat{\mathbf p}^{(m)}_{xy}-
\mathbf p_{xy}\rVert_2\mid o\right),
\qquad
\hat z=\hat z^{(m_o^*)}.
$$

Если хотя бы один estimator для объекта проходит p90-Z gate, множество
$\mathcal M_o$ содержит только прошедшие варианты; иначе используется
tail-minimizing fallback. Полученный route: global neural для butter и salad
dressing, stacked ridge для orange juice, object median для остальных пяти
объектов. Итоговые p90-Z и worst-object median XY равны 1.62 и 2.55 cm.

## Terminal screen

Первый screen обнаружил ошибку интеграции: calibration использовала raw
`agentview_image`, а rollout передавал localizer вертикально перевёрнутый кадр,
предназначенный для Cosmos. При неизменной raw camera matrix heatmap стала
почти равномерной; этот запуск (`1/20`, 5%) не является оценкой метода.

После восстановления единого raw-camera contract выполнена clean replication
на тех же frozen состояниях и artifact:

| Метрика | Результат | Gate |
|---|---:|---:|
| Success rate | **11/20 = 55%**, bootstrap CI [35%; 75%] | >=20% |
| Rescued cells / tasks | **6 / 4** | >=3 / >=3 |
| Strict replay | **20/20 = 100%** | >=95% |
| Drop-rate delta | **-5 п.п.** | <=+5 п.п. |
| Safety-rate delta | **0 п.п.** | <=0 п.п. |

Screen gate прошёл полностью.

## Full development

На всех 80 frozen состояниях получено:

| Метрика | Результат |
|---|---:|
| Success rate | **49/80 = 61.25%** |
| Init-cluster bootstrap CI | **[50.62%; 71.43%]** |
| Rescued cells / tasks | **6 / 4** |
| Strict replay | **80/80 = 100%** |
| Drop-rate delta | **0 п.п.** |
| Wrong-object-rate delta | **-2.5 п.п.** |
| Safety-rate delta | **0 п.п.** |

Все development gates пройдены, включая положительную нижнюю границу CI.
После этого автоматически и впервые открыт strict 72-state confirmatory
reserve из 47 не встречавшихся в development `task/init` групп.

### Связь с privileged upper bound

Paired comparison на тех же 80 состояниях даёт строгую эмпирическую
вложенность:

$$
\mathcal S_{H4}\cup\mathcal S_{lift}
\subseteq \mathcal S_{RGB}
\subseteq \mathcal S_{privileged}.
$$

RGB regrasp покрыл все 11 уникальных успехов прежних deployable эвристик и
49/62 = **79.03%** privileged-pose successes. Learned-only successes
отсутствуют; остаётся 13 privileged-only случаев. SR gap к upper bound равен
-16.25 п.п., init-cluster CI `[-25.32; -8.86]`, exact McNemar
`p=0.000244`. Среднее число Cosmos queries: 16.31 у RGB regrasp, 15.50 у
privileged regrasp и 51.09 у frequent H4.

## Confirmatory reserve

One-shot запуск на 72 строках / 47 новых `task/init` группах завершён без
изменения frozen artifact или controller:

| Метрика | Confirmatory результат |
|---|---:|
| Success rate | **43/72 = 59.72%** |
| Init-cluster bootstrap CI | **[45.20%; 73.91%]** |
| Rescued cells / tasks | **11 / 8** |
| Strict replay | **72/72 = 100%** |
| Drop-rate delta | **-1.39 п.п.** |
| Safety-rate delta | **0 п.п.** |
| Mean Cosmos queries | **16.39** |

Все заранее реализованные confirmatory checks прошли. Point estimate почти
совпал с development (59.72% против 61.25%), несмотря на полное разделение
`task/init` групп.

Авторитетный verdict для этого split находится в `confirmatory_gate.json`.
Общий `recovery_proposal_summary.csv` показывает `gate_passed=False` только
потому, что его legacy complete-check жёстко ожидает 80 development states;
это не результат confirmatory gate для заранее зафиксированного reserve72.

Результат неоднороден. `y0.2/task6` дал 15/15, а `x0.2/task9` и
`y0.2/task4` -- 0/4 и 0/14. Wrong-object flag вырос с 8.33% у исходных
failure trajectories до 29.17% после intervention (`+20.83 п.п.`); этот
диагностический endpoint не входил в frozen confirmatory gate и потому не
меняет формальный PASS, но является главным ограничением метода.

Post-hoc `perception_score_range` различал success/fail на reserve с AUROC
0.841 (macro AUROC 0.882 по четырём mixed cells), однако на development общий
AUROC был 0.658. Поскольку метрика выбрана после просмотра reserve, она лишь
формирует гипотезу для нового holdout, а не подтверждённый selector.

## Mechanism replays

После завершения статистического анализа отдельно пересняты пять заранее
назначенных иллюстративных ролей. Все learned outcomes точно воспроизвели
исходный frozen run:

| Роль | State | RGB regrasp | Privileged pose | Что показывает |
|---|---|---:|---:|---|
| development both success | `x0.2/task5/init15/r0` | success | success | обычное успешное восстановление tomato sauce |
| development privileged only | `x0.2/task9/init12/r0` | wrong-object fail | success | perception/contact gap для orange juice |
| development both fail | `y0.2/task4/init11/r1` | wrong-object fail | fail | одной точной pose цели недостаточно |
| reserve success | `y0.1/task8/init20/r0` | success | не измерялся | перенос на chocolate pudding |
| reserve fail | `x0.2/task9/init5/r0` | wrong-object fail | не измерялся | воспроизводимая граница на orange juice |

Ролики начинаются с frozen intervention state при `t=64`, то есть показывают
общий H8 prefix, recovery primitive и всю последующую траекторию до success или
`t=280`. Это mechanism evidence, а не дополнительная статистическая выборка.

## Промежуточные выводы

1. Привилегированный upper bound не превращается в deployable recovery без
   отдельной object localization; blind recovery закономерно не покрывает его.
2. Низкоразрешающий linear CLIP head недостаточен из-за редких крупных
   подмен похожих упаковок.
3. Object-conditioned dense heatmap практически решил 2D часть на unseen
   init-группах; улучшение p90 относительно CLIP примерно десятикратное.
4. Ошибка world-XY чувствительна к Z из-за наклонной камеры: при true Z p90 XY
   был 2.53 cm, а с первым neural Z -- 5.57 cm.
5. Clean terminal screen дал 55% rescue против 5% в диагностическом запуске с
   ошибочной ориентацией. Это также показывает, что preprocessing contract
   должен проверяться вместе с camera geometry, а не только unit-тестом модели.
6. Полный development подтвердил screen: 61.25% rescue с нижней границей
   cluster CI 50.62%, без роста drop и safety rate.
7. One-shot reserve подтвердил перенос: 59.72% rescue, CI полностью выше нуля,
   11 cells / 8 tasks, без роста drop или official safety rate.
8. P3b решает задачу recovery **при известном моменте intervention**, но ещё не
   задачу online detection. Для полного planner нужны observable trigger и
   shield от wrong-object interactions, замороженные до нового full-episode
   holdout.

Полный frozen protocol:
[`PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md`](PERCEPTION_REGRASP_ACCELERATED_PROTOCOL_20260904.md).

Пять выбранных exact-state mechanism replays, включая learned/privileged
контрасты и independent reserve success/fail, собраны в
[`campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html`](campaigns/perception_regrasp_heatmap_orientationfix_20260904__mechanism_videos/video_index.html).

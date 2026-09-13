# Задержка и повторный допуск к recovery: результаты

11 сентября 2026. Campaign `timing_eligibility_20260911_v2`.
[Замороженный протокол](TIMING_ELIGIBILITY_PROTOCOL_20260911.md).

## Главный вывод

**Новый delayed/latched controller не превзошёл немедленный RGB regrasp.**
Сильный прежний контроль и diagnostic-latched получили по 76/96 успехов;
fresh-delayed и checked-latched по 74/96, продолжение без recovery 63/96.
Основной кандидат не прошёл frozen gate. Holdout 38–45 не открывался.

Полезный результат здесь механистический: повторный отказ при ненадёжной
локализации иногда отменяет ещё полезное восстановление. Но безусловно
сохранять допуск тоже нельзя: короткое движение до внутренней проверки
способно ухудшить последующую траекторию, даже если полный regrasp отменён.

## Завершение и проверка

V2 стартовала в 13:54:59 MSK и завершилась **в 15:09:03 MSK**, за 74 минуты.
**10/10 технических + 480/480 основных ветвей**, штатное завершение до deadline.
У dispatcher нет активных workers; новые GPU-эксперименты этим анализом не запускались.
Исходные JSON/NPZ/MP4, логи и отчёты скачаны локально, около 175 MB campaign.

Повторный аудит: все 490 ветвей прошли проверки identity, хешей, query seeds,
физических шагов и кадров. Все 490 видео декодированы, **59 174 кадра**.
Шесть старых controls воспроизведены точно. В screen 98 common-delay и
170 equal-decision проверок; дополнительно 223 ветви без recovery точно совпали
с continue, включая 188 сравнений без исходного trigger. **79 CPU-тестов прошли.**
Серверная проверка замороженных исходников, runtime и артефактов: PASS.
Первая техническая v1 с девятью ветвями сохранена отдельно и не включена в SR.

## Постановка

Это **LIBERO-PRO Position perturbations семейства Object tasks**, а не полный
LIBERO-PRO benchmark и не LIBERO-Safety. Tasks 2/5/9: salad dressing,
tomato sauce, orange juice; смещения x/y 0.1/0.2, всего 12 известных cells.
На cell: init 46–49, по 2 rollout seeds; **96 paired states, 48 init clusters**.
Cells известны прошлым исследованиям; новые запуски не доказывают перенос на
неизвестные задачи. Init не пересекаются с calibration 5–24 и прошлой серией 34–37.

Общий K4/H16 prefix до t=72; suffix: K4/max-value, generate 16 / execute 8,
5 denoising steps, joint/parallel action/future/value, не AR a→s→v.
Лимит 280 физических действий включает recovery. Видеозапись начинается с t=72;
соответствие кадров физическому времени хранится в `frame_t` NPZ.
Все 96 prefix ещё не успешны. Сравнение проводится из точных сохранённых
состояний, но t=72 остаётся фиксированной исследовательской точкой, не общим
детектором события. Не смешиваем эти SR с full benchmark и обычным H16 rollout.

Обозначения: $G_t=F_tC_tW_tR_tM_t$, $S_t=F_tC_tW_tR_t$.
$F,C,W,R,M$: конечность данных, confidence локализатора, workspace,
reach, расстояние target–EEF как proxy miss. Проверки заморожены.
Запросы: immediate $G_{72}$; delayed-fresh $G_{72}G_{80}$;
checked-latched $G_{72}S_{80}$; diagnostic-latched $G_{72}$ после 8 действий.
При success вмешательство подавляется; в этой серии success во время delay не было.
Все запросившие recovery используют тот же primitive с новой проверкой
**после retreat с открытием gripper**. Checked не является гарантированно
безопасным controller; raw-latched остаётся только диагностикой в симуляторе.

## Результаты

| Стратегия | Success / 96 | SR | Запрос recovery | Полный primitive | Drop proxy |
|---|---:|---:|---:|---:|---:|
| Continue K4/H8 | 63 | 65.63% | 0 | 0 | 2 |
| Немедленный RGB regrasp | **76** | **79.17%** | 49 | 35 | 3 |
| Delay8 + fresh gate | 74 | 77.08% | 30 | 28 | 0 |
| Delay8 + latched checked | 74 | 77.08% | 33 | 31 | 0 |
| Delay8 + latched diagnostic | **76** | **79.17%** | 49 | 35 | 1 |

Drop proxy является post-hoc эвристикой, не official safety violation.
Малые числа не подтверждают улучшение безопасности. Запрос recovery не
равен полному primitive: до отклоняющей проверки уже выполнен физический retreat.

![Сводные результаты и вмешательства](campaigns/timing_eligibility_20260911_v2/review_20260911/overview.png)

| Заранее заданное сравнение | Разность SR, п.п. | 95% init-cluster bootstrap CI | Rescue / harm | Holm p |
|---|---:|---:|---:|---:|
| Checked − fresh | 0 | [0, 0] | 0 /0 | 1 |
| Checked − immediate | −2.08 | [−7.29, +3.13] | 3 /5 | 1 |
| Fresh − immediate | −2.08 | [−7.29, +3.13] | 3 /5 | 1 |
| Diagnostic − fresh | +2.08 | [−2.08, +6.25] | 3 /1 | 1 |
| Diagnostic − checked | +2.08 | [−2.08, +6.25] | 3 /1 | 1 |
| Immediate − continue | **+13.54** | **[+8.33, +18.75]** | **16 /3** | **0.17046** |

У immediate vs continue исходный cluster-sign p=0.02841, после Holm по
шести comparisons p=0.17046. Поэтому положительный point estimate не
объявляем новым family-wise значимым результатом. Bootstrap внутри фиксированных
cells и cluster-sign test различаются; CI не подменяет заранее заданный тест.
На cell всего четыре init clusters. CI[0,0] у checked/fresh отражает совпадение
96 наблюдавшихся labels, не доказывает эквивалентность в популяции.

Diagnostic vs immediate: описательное сравнение **3 rescue / 3 harm**, нулевая
разность итогового SR. Равный средний результат не означает одинаковые эпизоды.
Frozen criterion для checked (лучше обоих controls поCI и Holm, без роста
drop proxy) не выполнен: `candidate_confirmation_worthwhile=false`.

## Где помогло и где навредило

Все значения ниже из 8 эпизодов на cell; это описательная детализация, не
независимо подтверждённые улучшения каждой строки.

| Cell | Continue | Immediate | Fresh | Checked | Diagnostic |
|---|---:|---:|---:|---:|---:|
| x0.1/task2 | 8 | 8 | 8 | 8 | 8 |
| x0.1/task5 | 8 | 8 | 7 | 7 | 7 |
| x0.1/task9 | 8 | 8 | 8 | 8 | 8 |
| x0.2/task2 | 7 | 5 | 7 | 7 | 7 |
| x0.2/task5 | 3 | 8 | 8 | 8 | 8 |
| x0.2/task9 | 0 | 0 | 0 | 0 | 0 |
| y0.1/task2 | 8 | 8 | 8 | 8 | 8 |
| y0.1/task5 | 8 | 7 | 8 | 8 | 8 |
| y0.1/task9 | 4 | 8 | 5 | 5 | 8 |
| y0.2/task2 | 0 | 0 | 0 | 0 | 0 |
| y0.2/task5 | 8 | 8 | 8 | 8 | 7 |
| y0.2/task9 | 1 | 8 | 7 | 7 | 7 |

### 1. Проверка miss-distance не объясняет потери

Исходно допущены 49/96 states. После 8 общих действий fresh допускает 30,
checked 33, diagnostic 49. **19 отмен**: 9 confidence+workspace,
4 confidence+miss-distance, 3 workspace, 3 только miss-distance.
Удаление только miss-distance вернуло три полных recovery на
`x0.2_t2_i46_r1`, `x0.2_t2_i49_r0`, `x0.2_t2_i49_r1`, но не изменило исходов.
Checked и fresh совпали по 96/96 labels и 93/96 полных траекторий.

### 2. Ненадёжная локализация иногда восстанавливается после движения

На `y0.1/task9` immediate/diagnostic 8/8 против fresh/checked 5/8.
Три парных rescue diagnostic против fresh:

| Case | Score перед retreat | Порог | Score после retreat | Fresh / diagnostic |
|---|---:|---:|---:|---|
| y0.1_t9_i46_r1 | 19.06 | 25.13 | 32.03 | fail /success |
| y0.1_t9_i47_r0 | 17.54 | 25.13 | 33.84 | fail /success |
| y0.1_t9_i47_r1 | 18.34 | 25.13 | 32.66 | fail /success |

Команда: `pick up the orange juice and place it in the basket`.
Fresh блокирует по confidence и miss-distance; checked оставляет confidence
и тоже блокирует. Diagnostic выполняет retreat, повторно локализует цель,
проходит внутренний guard и завершает задачу. На этих точно парных ветвях
отмена recovery, а не неизбежная потеря возможности за 8 шагов, объясняет
разницу fresh/diagnostic. Это три эпизода на двух init одной cell, не широкое
доказательство полезности снятия confidence guard.

Score здесь **диапазон score map RGB-localizer**, не predicted value Cosmos,
не калиброванная вероятность и не доказанная epistemic uncertainty.
Изменение видимости предмета является объясняющей гипотезой; сами данные
устанавливают рост score и восстановление допуска после физического движения.

![Пример полезного сохранения допуска](campaigns/timing_eligibility_20260911_v2/review_20260911/y0.1_t9_i46_r1_storyboard.png)

### 3. Отмена полного primitive не отменяет вреда retreat

`y0.2_t5_i46_r1`: `pick up the tomato sauce and place it in the basket`.
Fresh и checked не вмешиваются и успешны. Diagnostic делает **только 3 шага
retreat**, затем отклоняется по confidence/workspace; полного regrasp нет.
Его продолжение fail, тогда как остальные четыре стратегии success.
После retreat score 9.76 остаётся ниже порога 14.16. Drop proxy отмечен
значительно позже, t=196, а не в момент первого движения t=80–83.

Поэтому нельзя писать «полный regrasp уронил предмет на t=80» или считать
failed guard отсутствием вмешательства. Мы наблюдаем вред ветви с коротким
retreat и последующим изменённым rollout; микрофизический момент ошибки
требует покадровой проверки. Raw diagnostic не следует использовать как
готовый безопасный controller.

![Пример вреда диагностического retreat](campaigns/timing_eligibility_20260911_v2/review_20260911/y0.2_t5_i46_r1_storyboard.png)

### 4. Оставшиеся общие провалы находятся вне допуска

Есть **17 paired cases**, где проиграли все пять методов. **Ни один из 17
не прошёл исходный trigger**: ветви точно совпадают с continue.
16 из них приходятся на x0.2/task9 и y0.2/task2 (по 0/8); ещё один
на x0.2/task2. Блокировки включают confidence/workspace, иногда reach.

Это показывает ограниченную область применения нынешнего trigger.
Это **не** доказательство, что recovery не может помочь в этих сценах:
его там не проверяли. Также нельзя просто убрать геометрические проверки:
нужно отделить ошибочную локализацию от реального выхода за область
достижимости/калибровки. В этой серии расширять пороги задним числом нельзя.

Из 33 провалов continue 17 не попадают под trigger. Остальные 16 немедленный
regrasp исправляет, одновременно создавая 3 новых провала среди успешных
continue. Это post-hoc описание данной выборки, не заявка на 100% rescue
в будущих сценах и не доказанная точность trigger как fail-detector.

Если задним числом выбирать любой успешный arm, получается 79/96 (82.29%).
Та же наблюдаемая объединённая успешность есть уже у двух controls
immediate+continue. В данном конечном наборе реализованных траекторий
новые delayed arms не расширили набор решённых cases. Выбор между ними
имеет лишь 3 дополнительных успеха над immediate; это не верхняя граница
для других seeds, новых действий или новых recovery primitives.

## Решение и следующий шаг

1. Сохранить immediate RGB regrasp сильным baseline. Не расширять текущий
   checked-latched sweep и не открывать holdout 38–45: gate NO-GO.
2. На development отдельно проверить observation/retreat **без открытия
   gripper**, с теми же post-motion guards. Нужны continue, старый retreat,
   новый retreat и full-recovery controls, чтобы не приписать физический
   эффект качеству нового verifier. Это гипотеза, пока не реализованный выигрыш.
3. Приоритет для нового controller: passive/two-view verification и память
   последних надёжных наблюдений, с явной обработкой `unknown`. Решение должно
   различать ненадёжную локализацию и отсутствие необходимости recovery.
   Проверять полезность информации относительно immediate, а не только continue.
4. Отдельный offline аудит 17 недопущенных failures: видимость, GT-ошибка
   локализации, workspace/reach и выбранный момент вмешательства. GT только
   для диагностики, не online-input. После этого заморозить новую гипотезу
   и провести независимую проверку, не обучаться и тестироваться на этих же labels.

Не запускаем большой новый value/uncertainty/ranking sweep по этому результату.
Научный вклад серии: разделение момента вмешательства, perception gate и
реального движения до проверки; не новый SOTA planner.

## Где смотреть

- [Полная таблица заранее заданных эффектов](campaigns/timing_eligibility_20260911_v2/analysis/screen/paired_effects.csv).
- [Аудит и машинный summary](campaigns/timing_eligibility_20260911_v2/review_20260911/summary.json).
- [Выбранные видео помощи и вреда, все пять стратегий рядом](campaigns/timing_eligibility_20260911_v2/review_20260911/selected_videos.html).
- [Все 480 видео](campaigns/timing_eligibility_20260911_v2/analysis/screen/videos.html).
- [Все случаи отмены recovery](campaigns/timing_eligibility_20260911_v2/review_20260911/cancelled_case_comparisons.csv)
  и [общие failures](campaigns/timing_eligibility_20260911_v2/review_20260911/all_method_failures.csv).
- Воспроизведение CPU-аудита: `python scripts/review_timing_eligibility.py`.

Примеры выбраны post-hoc как первые по сортировке rescue/harm; это не
представительная случайная выборка и не основание для оценки общего SR.
Последний столбец storyboard показывает индивидуальное terminal время;
для синхронного сравнения используйте подписанные одинаковые физические t.

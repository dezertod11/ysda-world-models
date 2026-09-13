# Probe → Verify → Repair: результаты и диагностика

Дата анализа: 11 сентября 2026. Campaign: `probe_verify_repair_20260910_v2`.
[Замороженный протокол](PROBE_VERIFY_REPAIR_PROTOCOL_20260910.md),
[машинная сводка](campaigns/probe_verify_repair_20260910_v2/analysis/screen/summary.json),
[дополнительный аудит](campaigns/probe_verify_repair_20260910_v2/review_20260911/summary.json).

## Главный результат

**Серия завершена штатно 10 сентября в 23:50 MSK: 24 smoke и 192/192 screen-ветви.**
Это 48 общих начальных состояний × 4 метода, не 192 независимых состояния.
V2 заняла около 69 минут от запуска, основной screen около 59 минут.
12 часов были максимальным бюджетом, а не обязательной длительностью.
Статус диспетчера: `completed_screen_gate_failed`; holdout не запускался.
При проверке сервера активных `collect_probe_repair.py` не было.

**Новый verifier не улучшил сильный recovery-контроль:** 30/48 против 35/48,
разница −10.42 п.п.; 4 rescue / 9 harm. Положительный эффект относительно
простого продолжения 26/48 недостаточен для принятия нового метода.
Главное диагностическое наблюдение: в семи случаях движение захвата
ошибочно интерпретировалось как движение целевого предмета.

## Что проверяли

Гипотеза: короткой физической пробой можно отличить состоявшийся захват от
промаха и не выполнять вредный повторный захват уже удерживаемого предмета.

LIBERO-PRO, **Object suite / Position perturbation**, внутреннее имя
`libero_object_temp`. Шесть сочетаний perturbation/task, init25–28,
по два rollout seed: 48 состояний, 24 кластера `(cell, init)`.
Это механизм-screen на выбранных условиях, не полный benchmark Object /
Environment / Position и не LIBERO-Safety.

Frozen Cosmos: K4 `max(value)`, joint/parallel action/future/value,
5 denoising steps. Общий prefix H16 до **t=72**, затем однократное
вмешательство и K4/H8 у всех методов: предсказываем 16 действий, выполняем 8.
Общий лимит 280 физических действий включает probe/regrasp; 10 settling steps
учитываются отдельно. Suffix seeds согласованы по номеру query, не по
абсолютному времени после вмешательств разной длительности.
**t72 здесь фиксированный контроль, не универсальный момент ошибки.**

| Метод | Действие после общего prefix |
|---|---|
| `continue_h8` | Продолжить policy без вмешательства |
| `physical_regrasp` | При frozen RGB-trigger выполнить полный regrasp |
| `probe_only` | При том же trigger до 3 шагов подъёма с закрытым захватом, затем policy |
| `probe_verify_repair` | Та же проба; regrasp только при `miss`, продолжение при `held` / `unknown` |

RGB-verifier сравнивает медианный optical flow треков в crop радиуса 16px
вокруг предсказанного центра предмета с проекцией движения EEF:

$$
d_o=\operatorname{median}_j(p_j^{after}-p_j^{before}),\qquad
d_e=\Pi(eef^{after})-\Pi(eef^{before}),
$$
$$
\rho=\frac{\|d_o\|_2}{\|d_e\|_2},\qquad
c=\frac{d_o^\top d_e}{\max(\|d_o\|_2\|d_e\|_2,10^{-8})}.
$$

При валидной confidence, ≥4 треках и движении EEF ≥2px: `held`, если
$c\ge0.7$ и $0.3\le\rho\le2.5$; иначе `miss`, если
$\|d_o\|_2\le0.75$px; остальные случаи `unknown`.
Онлайн доступны RGB, task text, EEF proprio и калибровка камеры.
Истинные object poses / contacts использованы **только после сбора** для
диагностики, не для выбора действия.

## Итоговые метрики

| Метод | Success / 48 | SR | Drop proxy, эпизоды | Средний final t | Среднее число suffix queries |
|---|---:|---:|---:|---:|---:|
| Continue H8 | 26 | 54.17% | 2 | 209.71 | 17.54 |
| Physical regrasp | **35** | **72.92%** | 4 | 188.27 | 13.42 |
| Probe only | 26 | 54.17% | 1 | 208.40 | 17.25 |
| Probe + verify + repair | 30 | 62.50% | 1 | 199.38 | 15.31 |

Drop proxy не является официальной safety violation. Один из четырёх
drop-proxy эпизодов full regrasp в итоге успешен. Сигналы этого аудита
покрывают продолжение после t72, а не историю до общего snapshot.
Среднее число запросов включает эффект более раннего success: это не
сравнение методов при одинаковой длительности успешного эпизода.

Среднее время branch: continue 47.75с, full 38.34с, probe 47.46с,
verified 43.21с. Это локальный счётчик ветви без общего prefix и кодирования
видео, с replay/интервенцией; shared-server условия. Не полноценный latency benchmark.

### Парные эффекты

Положительная разница означает выигрыш первого метода. Rescue: первый
успешен, второй нет; harm наоборот. Равные веса cells, bootstrap по init
внутри cell, повторные seeds остаются одним кластером.

| Сравнение | Разница SR, п.п. | 95% cluster bootstrap CI | Rescue / harm | Cluster p | Holm p |
|---|---:|---|---:|---:|---:|
| Verified − full | **−10.42** | [−20.83; 0.00] | 4 / 9 | 0.27989 | 0.83967 |
| Verified − probe | +8.33 | [0.00; 16.67] | 6 / 2 | 0.31272 | 0.83967 |
| Verified − continue | +8.33 | [−2.08; 16.67] | 7 / 3 | 0.46905 | 0.83967 |

Ни по одному из трёх контрастов превосходство не подтверждено.
Нельзя заменять это утверждением о статистически доказанном ухудшении:
оценка primary отрицательная, но малый screen даёт широкий интервал.
В supplementary-аудите точный перебор ненулевых init-cluster sign flips даёт
p=0.28125 / 0.3125 / 0.46875, согласуясь с исходным Monte Carlo тестом.
Исходная методика и Holm-коррекция не заменены этим post-hoc расчётом.

Дополнительные, **post-hoc**, контрольные контрасты:
full − continue +18.75 п.п., 13 rescue / 4 harm, CI [8.33; 29.17], exact
cluster p=0.109375; probe − continue 0 п.п., 3 / 3, CI [−10.42; 8.33], p=1.
Положительный percentile CI при таком малом числе init не эквивалентен
прохождению cluster sign-test. Не заявляем нового confirmatory результата
для full − continue только по этому screen.

Frozen holdout gate требовал verified − full ≥5 п.п. Получено −10.42;
остальные practical условия (положительные вторичные разницы, drop count
не выше full, ≥8 пропусков regrasp) выполнены. **NO-GO; init29–32 не открыты.**

## Где возникли различия

Число success из восьми на каждом методе:

| Position / task | Cell в calibration | Continue | Full | Probe | Verified | Trigger / 8 |
|---|---|---:|---:|---:|---:|---:|
| x0.1 / task5 | Нет | 8 | 8 | 8 | 8 | 4 |
| x0.1 / task9 | Нет | 8 | 8 | 8 | 8 | 0 |
| x0.2 / task2 | Да | 6 | 4 | 6 | 5 | 8 |
| x0.2 / task5 | Да | 4 | **8** | 2 | **3** | 8 |
| y0.2 / task2 | Нет | 0 | 0 | 0 | 0 | 0 |
| y0.2 / task9 | Да | 0 | **7** | 2 | **6** | 8 |

На трёх новых для calibration сочетаниях все методы имеют 16/24: два
потолочных результата и одна all-fail cell без срабатывания trigger.
Это **не подтверждение переноса** verifier. Новые cells не означают новые
task/object identities или отсутствие этих cells во всех прошлых исследованиях.

### Почему verifier ошибается

Из 28 проб: 14 `miss`, 9 `held`, 5 `unknown`. В 20 состояниях trigger не
сработал. Verified запросил 14 regrasp, из них 13 исполнили полный primitive,
один остановился по post-retreat guard после трёх физических шагов.
Full запросил 28, полностью исполнил 24. Реальное состояние после guard
сохранено: rollback уже выполненного движения нет.

**Семь из девяти `held` не соответствуют удержанию цели во время пробы:**

- Все семь в `x0.2 / task5`; цель `tomato_sauce_1` почти неподвижна
  (<0.001мм по сохранённому simulator trace), контактов robot–target 0/3.
- EEF при этом перемещается на 25.36–26.31мм. Медианный flow равен
  6.71–7.02px, проекция EEF 6.47–6.86px: критерий совместного движения проходит.
- В иллюстративном crop большую часть окна занимает движущийся захват.
  Проверка геометрической согласованности треков не проверяет их принадлежность
  предмету. Это ошибка object correspondence, не прежняя ошибка OpenGL/CV.
- Пять из этих семи ветвей заканчиваются fail; full regrasp успешен во всех
  семи соответствующих состояниях. Остальные две ветви позднее восстанавливаются
  самой policy: ложный `held` не означает неизбежный terminal fail.
- Другие два `held` действительно сопровождаются движением цели на
  29.10/29.88мм и контактами 3/3; обе ветви успешны.

Эти семь ошибок объясняют важную часть картины, но **не все девять harms**.
Ещё четыре harm имеют verdict `miss` и запрошенный regrasp. Чтобы отделить
последствия самой пробы от неправильного решения пропустить восстановление,
нужен контроль **probe → always-regrasp из того же post-probe состояния**.
Нынешний full control начинается до пробы. Нельзя утверждать, что одно
исправление verdict гарантированно спасёт все пять false-held failures.

![GT-аудит движения и входы RGB-verifier](campaigns/probe_verify_repair_20260910_v2/review_20260911/probe_motion_audit.png)

Слева истинное перемещение цели и EEF за те же три шага: семь красных точек
на нуле сливаются из-за близких значений. Справа verifier видит согласованное
движение пикселей и руки. GT слева недоступен онлайн и не использован для
подбора новых порогов в этой серии.

![Ошибочный held: crop отслеживает захват](campaigns/probe_verify_repair_20260910_v2/review_20260911/false_held_crop.png)

## Видео и раскадровка

[Все 48 групп × 4 метода: HTML-видеогалерея](campaigns/probe_verify_repair_20260910_v2/analysis/screen/videos.html).
Видео локально скачаны; обе камеры, от общего snapshot t72 до terminal,
не весь prefix от t0. Количество кадров: `terminal_t − 72 + 1`.

Пример `x0.2_t5_i26_r0`: continue и full успешны, probe и verified нет.
[Full regrasp: success](campaigns/probe_verify_repair_20260910_v2/screen/x0.2_t5_i26_r0/physical_regrasp.mp4),
[Verified: fail](campaigns/probe_verify_repair_20260910_v2/screen/x0.2_t5_i26_r0/probe_verify_repair.mp4).
На t75 неверно определяется захват; это **не момент падения**. В этой
verified-ветви первый зарегистрированный подъём цели t168, drop-proxy t229,
эпизод заканчивается без goal на t280.

![Четыре продолжения из одного prefix](campaigns/probe_verify_repair_20260910_v2/review_20260911/false_held_storyboard.png)

Внутренние столбцы сравнивают одинаковые физические t. Если эпизод уже
завершился, показан последний кадр с фактическим временем; последний столбец
всегда terminal. H264 используется для иллюстрации, числа движения считаются
по lossless NPZ/JSON, а не по сжатому видео.

## Проверки и воспроизводимость

- Повторный строгий анализ: SHA-256 prefix/branch/video, job identities,
  фактические действия и frame accounting всех 192 ветвей прошли проверку.
- В двух probe arms повторная проба даёт одинаковые sim state и observation
  hashes. Нет подмены технических ошибок policy failures.
- В 20 состояниях без trigger все четыре arms побитово совпали по действиям,
  final state и per-step signals. В 14 `held`/`unknown` продолжение verified
  так же совпало с probe-only: лишнего пересемплирования не возникло.
- Все четыре видео разобранного случая декодированы, frame counts совпали.
- 26 CPU-тестов controller/review прошли. Замороженный controller не менялся.
- Первые 16 технических smoke-ветвей v1 с несовпадением координат отдельно
  архивированы. Они не входят в 24 smoke v2 и в 192 screen.

Config SHA-256:
`68d7c42f4c3fc98090e5ad263432e57e1213b53a70828e690583d53580ad2736`.

Из корня проекта:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/review_probe_repair_results.py
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q tests/test_probe_repair_review.py tests/test_probe_repair.py
```

[Raw diagnostic table](campaigns/probe_verify_repair_20260910_v2/review_20260911/probe_motion_audit.csv),
[парные случаи](campaigns/probe_verify_repair_20260910_v2/review_20260911/paired_cases.csv),
[дополнительные контрасты](campaigns/probe_verify_repair_20260910_v2/review_20260911/additional_diagnostic_effects.csv).

## Вывод и следующий разумный шаг

1. Сохраняем P3c/physical regrasp как сильный recovery-control. Новый
   active verifier v2 не продвигаем и не тратим на него conditional holdout.
2. Ближайший дешёвый тест: object-specific tracking / исключение robot mask /
   wrist-view на уже собранном development. Раздельно измерять false-held,
   unknown/coverage, локальный grasp и будущий terminal outcome. Mask/GT из
   симулятора допустимы как явно привилегированная offline верхняя граница,
   но не как скрытый вход deployable verifier.
3. Перед новой массовой серией отделить эффект пробы от gate: добавить
   `probe → always-regrasp` к прежним четырём controls. Сначала диагностические
   exact-state branches на development; подтверждение только на новых init.
4. Рассмотреть passive/two-view verification перед активным вмешательством.
   Сам по себе короткий подъём дал 3 rescue / 3 harm против continue: он не
   бесплатен и не гарантированно безвреден.
5. После исправления correspondence отдельно проверить event timing и
   trigger coverage, включая all-fail `y0.2/task2`. Не подбирать одновременно
   десятки thresholds/timing и не оценивать затем на тех же прочитанных labels.

Научный результат этой серии: **внешняя RGB-проверка полезна только при
надёжной привязке наблюдения к целевому объекту; совместное движение
пикселей с рукой само по себе не подтверждает захват**. Это конкретный
отрицательный результат и диагностированный механизм ошибки, не новый SOTA
planner, не доказательство бесполезности active perception вообще и не
достаточная самостоятельная заявка о готовности к ICLR.

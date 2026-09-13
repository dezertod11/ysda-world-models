# Проверка по маске предмета и отложенный regrasp: результаты

11 сентября 2026. Campaign `grounded_probe_20260911_v2`.
[Замороженный протокол](GROUNDED_PROBE_PROTOCOL_20260911.md).

## Краткий вывод

**Маска устранила наблюдавшиеся ложные подтверждения захвата, но улучшение
планировщика относительно сильного recovery-контроля не доказано.**
Консервативный вариант получил 35/48, ровно как «проба → всегда regrasp»;
47/48 полных траекторий у них побитово одинаковы. Самостоятельный вклад
verification в SR здесь не установлен. Отложенный regrasp не подтвердил
перенос: 33/48 против 36/48 у немедленного восстановления.

Сохраняем полный RGB regrasp как сильный контроль. Не продвигаем mask-gate
или фиксированную задержку как подтверждённый новый метод. Следующий вопрос:
как выбирать восстановление при ненадёжном наблюдении, не теряя возможность
исправить ошибку и не повреждая сцену самой диагностической пробой.

## Завершение и постановка

- Старт 01:59:04 MSK, завершение **03:56:57 MSK**, примерно 1 ч 58 мин.
- Завершены **48 smoke + 384 screen + 144 transfer = 576 ветвей**.
- Нет незавершённых cases. Conditional confirmation не запускалась: ни один
  candidate не прошёл заранее заданный screen gate. Это штатное завершение,
  не обрыв по времени; неиспользованный бюджет не заполняли лишними опытами.
- Данные, NPZ, checkpoint маски и все видео скачаны локально. Повторный
  анализ проверил хеши, общие prefix/probe states, действия, query seeds и
  индексы кадров. Контроллер, веса и научные параметры не менялись.
- Все576видео декодированы: 74572кадра, число кадров каждого файла совпало
  с метаданными. Серверная проверка frozen sources/runtime/weights: PASS.
  Локальные тесты collector/verifier/audit: **56 passed**.

Используем **LIBERO-PRO Position perturbations семейства Object tasks**, а не
весь LIBERO-PRO Object benchmark и не LIBERO-Safety. Tasks 2/5/9 относятся
к salad dressing / tomato sauce / orange juice. Каждая cell задаётся
сочетанием задачи и position level. Screen: шесть cells, init34–37,
два rollout seeds на init: **48 paired states, 24 init clusters**. Transfer:
ещё шесть cells, та же структура выборки, без пересечения cells со screen.
Эти задачи/предметы нельзя называть полностью неизвестными прошлым исследованиям.

Общий K4/H16 prefix до t=72; дальше генерируются 16 действий, исполняются
первые 8, K4/max-value, пять denoising steps, joint/parallel generation,
не AR a→s→v. Каждая ветвь продолжается из одного сохранённого состояния.
Лимит 280 реальных действий включает probe и recovery. Видеозапись начинается
с t=72, не с reset. Это механизм-эксперимент в фиксированной точке, не
доказательство универсальности t=72 или полный benchmark planner.

## Основная серия

| Стратегия | Success / 48 | SR | Изменение к full regrasp |
|---|---:|---:|---:|
| Продолжение без recovery (`continue_h8`) | 27 | 56.25% | −12.50 п.п. |
| Полный RGB regrasp (`physical_regrasp`) | 33 | 68.75% | Контроль |
| Только физическая проба (`probe_only`) | 23 | 47.92% | −20.83 п.п. |
| Прежний crop-flow verifier | 29 | 60.42% | −8.33 п.п. |
| Проба → всегда regrasp | **35** | **72.92%** | +4.17 п.п. |
| Маска: regrasp только при `miss` | 29 | 60.42% | −8.33 п.п. |
| Маска: regrasp при `miss` или `unknown` | **35** | **72.92%** | +4.17 п.п. |
| Восемь policy actions → новый trigger → regrasp | 34 | 70.83% | +2.08 п.п. |

Слово «всегда» относится к запросу recovery после разрешённой пробы.
Внутренние safety/workspace/confidence guards самого primitive сохраняются;
это не безусловное выполнение полного движения на всех 48 сценах.

![Сводные SR](campaigns/grounded_probe_20260911_v2/review_20260911/aggregate_success.png)

| Парное сравнение | Разность SR | 95% init-cluster bootstrap CI | Rescue / harm | Holm p |
|---|---:|---:|---:|---:|
| Conservative mask − full | +4.17 п.п. | [−4.17, +10.42] | 3 / 1 | 1.0 |
| Miss-only mask − full | −8.33 п.п. | [−16.67, 0] | 3 / 7 | 1.0 |
| Delayed − full | +2.08 п.п. | [−10.42, +12.50] | 4 / 3 | 1.0 |
| Conservative mask − probe-always | 0 | [0, 0] | 0 / 0 | 1.0 |

Все primary improvements статистически не подтверждены. Нулевой CI в
последней строке описывает совпавшие labels в этой выборке, а не доказывает
эквивалентность методов на любой сцене. Интервалы условны на шести фиксированных
cells; всего четыре init clusters на cell. Bootstrap CI и дискретный
cluster-sign test не взаимозаменяемы; критерий promotion учитывает заранее
заданный тест, а не только красивую границу CI. Все post-hoc дополнительные
сравнения вынесены в отдельный CSV и не используются для изменения gate.

Причины NO-GO: conservative не набрал +5 п.п., не обошёл probe-always и
сделал только один eligible skip вместо требуемых четырёх. Miss-only уступил
full и probe-always. Delayed дал лишь +2.08 п.п. к full. Пороги после анализа
не снижались, закрытый init38–45 holdout не открывался.

## Что именно изменила маска

DeepLabv3 обучался только на 388 прежних calibration samples, без новых
terminal labels. Validation: IoU 0.8167, precision 0.8682. Это качество
сегментации на своей calibration, не SR и не точность online grasp detector.

Из 48 состояний 27 прошли исходный trigger и получили физическую пробу.
На **тех же самых 27 post-probe states**:

| Ответ | Прежний crop-flow | Object mask |
|---|---:|---:|
| held | 11 | 1 |
| miss | 12 | 14 |
| unknown | 4 | 12 |
| held при неподвижной цели без контакта | **10** | **0** |

Последняя строка: post-hoc simulator audit, перемещение цели <0.1 мм и
отсутствие контакта с целевым предметом на всех шагах пробы. Это локальная
проверка явных false positives, не полная разметка всех возможных grasp states.
Simulator poses/contacts не поступали в online verifier.

Из десяти ложных `held` два стали `miss`, восемь стали `unknown`.
На последних восьми маска не дала достаточно согласованных object tracks:
три `insufficient_object_tracks`, пять `inconsistent_object_motion`.
Визуальная проверка стала осторожнее, но отсутствие достоверного `held`
ещё не означает, что получен достоверный `miss`.

![Ответы verifier и реальное движение](campaigns/grounded_probe_20260911_v2/review_20260911/verifier_audit.png)

У miss-only policy `unknown` означает «не восстанавливаться». Поэтому
перевод `held → unknown` сам по себе не меняет её поведение. На screen
новая miss-only и прежняя verification совпали по всем 48 terminal labels.
На `x0.2/task5`: continue 7/8, probe-only 2/8, legacy/miss-only 2/8,
full/conservative/probe-always 8/8. Здесь conservative выигрывает шесть
эпизодов относительно miss-only, но не относительно probe-always.

**Ключевое разложение:** classifier, правило обработки `unknown` и физическое
восстановление нельзя считать одним улучшением. По этим данным положительный
terminal результат conservative обеспечивается практически тем же действием,
что и у контроля без нового verifier.

У conservative и probe-always совпадают все outcomes и 47/48 полных
action/state/signal traces. Единственный `held` в `x0.2_t2_i35_r1` действительно
сопровождался движением предмета. Skip сэкономил три шага: control после
retreat сам отклонил полное движение своим guard. Обе ветви успешны
(t=132 против t=135), число реально выполненных полных primitives одинаково: 20.
Пока это экономия одной короткой попытки, а не значимое новое управление.

## Физическая проба не бесплатна

Probe-only: 23/48 против continue 27/48, **2 rescue / 6 harm**.
Это post-hoc сравнение, не доказанный универсальный вред пробы. Но оно
показывает, почему нельзя считать диагностическое движение нейтральным
получением информации. На `x0.2/task5` сама проба без recovery дала 2/8
против 7/8 у continue. Probe-always устранил эти провалы в текущей выборке.

При этом probe-always против full: +4.17 п.п., CI [−4.17, +10.42].
Добавлять пробу ко всем восстановлениям как доказанное улучшение тоже рано.
Drop proxies screen: continue2, full3, probe4, probe-always1,
miss-only2, conservative1, delayed2. Малые числа и неофициальные proxies
не дают основания заявлять улучшение LIBERO-Safety.

## Проверка переноса и timing

| Стратегия | Success / 48 | SR |
|---|---:|---:|
| Continue | 33 | 68.75% |
| Full regrasp | **36** | **75.00%** |
| Delayed regrasp | 33 | 68.75% |

Full − continue: +6.25 п.п., CI [−4.17, +16.67], 6 rescue /3 harm,
Holm p=1. Delayed − full: −6.25 п.п., CI [−16.67, +4.17], 3 rescue /6 harm.
Delayed и continue имеют одинаковый terminal label на каждом из48cases,
но не все их траектории одинаковы.

После восьми действий исходный допуск **21/48** сократился до **7/48**.
В 14 ветвях свежая оценка перестала разрешать recovery. На `y0.1/task9`
получилось: continue3/8, full8/8, delayed3/8; все семь исходно разрешённых
recovery были отменены свежим trigger. При отсутствии recovery delayed
побитово совпадает с continue: это проверено, не только предположено по SR.

Следовательно, результат нельзя объяснять только «позже физически хуже»:
в arm одновременно меняются момент вмешательства **и повторный допуск**.
Здесь есть наблюдаемый механизм потери полезных вмешательств. Причина
конкретного отказа свежего trigger по его отдельным thresholds не сохранена
в branch JSON; для такого разбора нужен отдельный replay/новый диагностический
лог, а не догадка по картинке.

| Cell, по 8 states | Continue | Full | Delayed |
|---|---:|---:|---:|
| x0.1/task2 | 8 | 7 | 8 |
| x0.2/task9 | 0 | 0 | 0 |
| y0.1/task2 | 8 | 8 | 8 |
| y0.1/task5 | 8 | 8 | 8 |
| y0.1/task9 | 3 | 8 | 3 |
| y0.2/task5 | 6 | 5 | 6 |

Полезность recovery неоднородна: есть пять rescue на одной cell и harms
на других. У полностью провальных `screen y0.2/task2` и `transfer x0.2/task9`
исходный trigger ни разу не сработал. Нельзя заключать, что на этих states
проверенный recovery primitive физически бесполезен: он там не был выполнен.

## Видео и контроль реализации

[Все 48 screen-групп, восемь стратегий](campaigns/grounded_probe_20260911_v2/analysis/screen/videos.html).
[Все 48 transfer-групп, три стратегии](campaigns/grounded_probe_20260911_v2/analysis/transfer/videos.html).
Файлы MP4 доступны локально по относительным ссылкам галерей.

![Пример различия fallback](campaigns/grounded_probe_20260911_v2/review_20260911/screen_diagnostic_storyboard.png)

![Пример отменённого recovery](campaigns/grounded_probe_20260911_v2/review_20260911/transfer_diagnostic_storyboard.png)

Примеры выбраны как первые по job_id среди пар с rescue; это иллюстрации,
не дополнительная независимая выборка. Последний столбец показывает terminal
каждой ветви, остальные позиции сопоставлены по физическому t и обрезаны
по завершению эпизода. Неисполненные действия после success не дорисовываются.

`Fail` здесь означает, что predicate успеха LIBERO не достигнут до280.
Это не обязательно падение предмета или необратимая ошибка: например,
в screen-раскадровке fail поздно подводит предмет к корзине. Продление
горизонта могло бы изменить label, но в этой серии не проверялось.
Для анализа раннего предсказания ошибки нужны отдельные event labels,
а не подмена terminal fail моментом наблюдаемого падения.

Проверены 201 сравнение no-trigger ветвей, 144 сравнения одинаковых probe/
repair путей и 19 delayed ветвей без recovery: actions, final sim states и
signals совпали побитово, включая допустимые NaN. Это проверки конкретных
инвариантов; не гарантия отсутствия любых ошибок в системе.

## Решение и следующий шаг

1. Не расширять текущий mask-miss/conservative sweep и не открывать
   условный holdout задним числом. Сохранить протокол и отрицательный gate.
2. Приоритетный диагностический опыт: разнести delay и свежий trigger.
   Сравнить immediate, delayed+fresh-gate и delayed+сохранённая eligibility,
   сохраняя актуальные guards безопасности самого движения. Не исполнять
   blindly regrasp после опасного изменения состояния. Логировать причины
   отказа до и после delay; затем фиксировать новую версию и новые init.
3. Для verifier сначала offline/shadow проверка passive/two-view target
   motion и явной политики `unknown`, до вмешательства в сцену. Требуется
   не только уменьшить false-held, но и показать случаи полезного skip,
   в которых strong recovery сам не справился бы столь же хорошо.
4. Отдельно разметить task progress, wrong-object grasp, отпускание и
   достижение корзины. Не учить «раннюю ошибку» только по timeout labels.
5. Broad P5/RL fit и очередной scalar uncertainty sweep не следуют из этого
   результата автоматически. Новые GPU-эксперименты данным анализом не запускались.

**Научный итог:** object correspondence улучшает достоверность отдельных
perceptual решений, но closed-loop benefit определяется fallback, ценой
измерения и timing/eligibility. Эти факторы теперь разделены сильными controls.
Общего нового SOTA planner или подтверждённого выигрыша нового verifier нет.

## Источники чисел

- [Frozen screen summary и gate](campaigns/grounded_probe_20260911_v2/analysis/screen/summary.json)
- [Transfer summary](campaigns/grounded_probe_20260911_v2/analysis/transfer/summary.json)
- [Аудит и агрегаты](campaigns/grounded_probe_20260911_v2/review_20260911/summary.json)
- [Branch diagnostics](campaigns/grounded_probe_20260911_v2/review_20260911/branch_diagnostics.csv)
- [Движение цели и контакты](campaigns/grounded_probe_20260911_v2/review_20260911/probe_motion_audit.csv)
- [Timing/trigger по cell](campaigns/grounded_probe_20260911_v2/review_20260911/delay_trigger_audit.csv)
- [Воспроизводимый CPU-аудит](../scripts/review_grounded_probe_results.py)

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/review_grounded_probe_results.py
```

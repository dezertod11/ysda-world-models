# P4c2: результаты подготовки и smoke

8 сентября 2026, 02:11 MSK. **7/7 smoke завершены и проверены.**
Полный benchmark ещё не завершён: автоматически начался development на GPU6,7.

## Что уже проверено

- Offline screen: 194 exact P4b pools, 32 настройки; 1 rescue / 1 harm у лучших guarded finalists.
- На сервере прошли 33 geometry/planning tests и 10 config/analysis tests.
- Реальная среда приняла новую controller-scaled geometry.
- Все 7 эпизодов имеют полные MP4 и непрерывные query traces.
- q0 simulator state всех семи методов совпадает с точностью 1e-9.
- Предсказания H16 не сравниваются с концом укороченного chunk.
- Автоматический отчёт и HTML-видеосравнение сформированы.
- Конфигурация полного теста прошла input validation для всех 360 jobs.

## Одна диагностическая сцена

LIBERO-PRO `libero_object_object`, task0, init0, seed18000000.
Команда: pick up the alphabet soup and place it in the basket.
Генерация/исполнение H16, 5 denoising steps, лимит 280 действий.

| Метод | Success | Выполнено шагов | Query | Switch от max-value | Drop proxy |
|---|---|---:|---:|---:|---:|
| K1 first | да | 181 | 12 | 0 | 0 |
| max-value K4 | да | 163 | 11 | 0 | 0 |
| старый guarded K4 | да | 221 | 14 | 7 | 0 |
| trajectory-medoid | нет | 280 | 18 | 13 | 1 |
| trajectory-density | нет | 280 | 18 | 17 | 0 |
| value-density, lambda0.25 | да | 129 | 9 | 0 | 0 |
| value-density aligned, lambda0.25 | да | 163 | 11 | 0 | 0 |

Это проверка исполнения, **не оценка SR на benchmark**. Оба pure consensus
могут выбирать согласованные, но неуспешные действия. У одного сработал
drop-proxy, второй закончился без success predicate и без этого drop-признака.

Guarded методы ни разу не отклонились от max-value. Поэтому 129 против 163
шагов нельзя считать улучшением selector: action pools отдельных процессов
не всегда побитово совпадают даже при одинаковых task/init/seed. У unaligned
варианта q0 max absolute action difference относительно baseline = 0.00651006;
у aligned q0 разница = 0. Само происхождение расхождения этим тестом не
локализовано. Для обоснования улучшения нужны полный paired deployment SR,
switch statistics и последующая exact-state branch проверка, а не только эти видео.

Независимое воспроизведение trajectory-medoid по сохранённым candidate chunks
повторило все 18/18 выбранных индексов.

## Где смотреть

- [Smoke отчёт и таблицы](campaigns/trajectory_consensus_20260908_smoke/trajectory_analysis/RESULTS.md).
- [Все семь видео рядом](campaigns/trajectory_consensus_20260908_smoke/trajectory_analysis/videos.html).
- [Формулы, гипотезы и полный протокол](TRAJECTORY_CONSENSUS_PROTOCOL_20260908.md).
- [Команды статуса и продолжения](TRAJECTORY_CONSENSUS_RUN_20260908.md).

Далее без ручного запуска: 392 development rollout -> freeze одного метода
-> 4500 новых rollout (K1, max-value K4, выбранный K4 метод). Полные outcomes
не используются для подбора коэффициентов. Улучшение на полном тесте пока
не установлено и не гарантируется результатами smoke.

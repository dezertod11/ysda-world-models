# P3: досчёт и репликации до 09:00 МСК

Запущено 15 сентября 2026 в 01:04 МСК по запросу пользователя.
Это протокол запуска, **не объявление новых научных результатов**.

## Очередь и время

| Приоритет | Серия | Объём | Оценка при восьми свободных GPU |
|---|---|---:|---|
| 1 | Досчёт исходной P3 valid199 | 688 недостающих из 995 main rollout | 1-2 часа, консервативно до 3 |
| 2 | Полная seed-репликация S1 | 995 main + 12 smoke | Около 1.5-2.5 часов |
| 3 | Полная seed-репликация S2 | 995 main + 12 smoke | Около 1.5-2.5 часов |
| CPU | Coverage trigger, таблицы по seeds, rescue/harm, видеоиндекс | По committed данным всех серий | Параллельно, без GPU |

Начальная оценка общего времени: 4-6 часов; рабочий резерв после загрузки
моделей: **5-7 часов**, ориентир завершения 06:00-08:00 МСК при сохранении
ресурсов. Это прогноз, не гарантия. Две репликации поставлены в очередь,
но при нехватке времени последняя останется partial, без final inference.
Генерация ограничена **08:30 МСК**, остановка собственных workers имеет
grace до 120 секунд; оставшееся время отведено на аудит и выгрузки.
CPU-агрегатор ограничен 08:50. Пользовательский крайний срок: 09:00.

Оценка по 61 завершённому парному случаю: среднее время всех пяти arm
на один worker составляет Object 133 с, Environment 221 с, Position 227 с.
Для оставшихся 44/44/50 случаев это около 7.5 worker-hours, в идеале
около 56 минут на восьми GPU. Реальная оценка выше из-за загрузки моделей,
рендера/видеозаписи, аудита, хвостовых batch и возможного ожидания GPU.
Elapsed-times используют межметодный cache; это оценка времени кампании,
а **не честное сравнение латентности отдельных стратегий**.

Старый ETA в `sequence_status.json` включает десятичасовой простой и
сейчас завышен. Новый `operations/night_status.json` считает ETA от
момента возобновления после появления как минимум 20 новых outcomes.
Он тоже приблизителен и отражает время загрузки/ожидания после рестарта.

## Научный смысл

1. Закрыть отсутствующую таблицу Object/Environment/Position/Macro-SR/Success199
   для P3 и одновременных контролей. Не заменять её scoped recovery-SR.
2. Проверить, воспроизводится ли эффект на новых stochastic rollout seeds,
   сохранив все задачи, init IDs, методы и гиперпараметры. Это важнее нового
   coefficient sweep на уже просмотренных исходах.
3. Измерить ограничение событийного подхода: насколько часто есть валидная
   локализация, close-near, память попытки, mask-miss, persistent miss и
   разрешённая геометрия. Отсутствие вмешательств не доказывает эффективность
   recovery; этап, блокирующий действие, надо показать явно.

Не утверждаем новый SOTA или новую архитектуру. Репликация на том же
историческом task/init support проверяет устойчивость к seeds, **не перенос
на невиданные задачи или init**. Сильный локальный recovery-результат и
широкий benchmark остаются разными утверждениями. Негативные результаты,
harms и все клетки сохраняются независимо от знака эффекта.

## Фиксированные сравнения

Во всех трёх сериях: 199 случаев = Object50 + Environment50 + Position99;
в каждом случае пять методов:

- `first_k1`: один candidate, generate16/execute16;
- `max_value_h16`: K4, max-value, execute16;
- `h8_at72`: исторический контроль смены горизонта после t72;
- `p3_at72`: исторический RGB-gated physical regrasp, затем H8;
- `p3_event`: тот же recovery с наблюдаемым persistent-miss trigger.

Joint/parallel action-state-value generation, 5 denoising steps, frozen Cosmos,
общий бюджет 280 физических действий. Старые t72 arms нужны как controls,
не выдаются за универсальный момент ошибки. Пороги event-controller не меняются.

S1: `rollout_seed_original + 10_000_000`.
S2: `rollout_seed_original + 20_000_000`.
Seed каждого candidate: `rollout_seed + query_index * 1000 + candidate_index`.
Внутри каждого случая все arms получают одинаковое сохранённое initial state.
Между seed-группами идентичность начальных изображений проверяется отдельно;
её не предполагаем без сравнения hashes.

Следующая серия стартует только после полного завершения и аудита предыдущей,
**независимо от SR**. Техническая ошибка останавливает продвижение; недостающие
эпизоды не считаются fail. По дедлайну неполная репликация остаётся partial и
не входит в среднее по полностью завершённым seeds.

## Метрики и выводы

Для каждой полной серии отдельно: факторные SR, равновзвешенный Macro-SR,
Success/199; предзаданные четыре paired contrasts, task/init-cluster bootstrap,
sign-flip и Holm из исходного протокола. Дополнительно: rescue/harm, logical
model calls/candidates, частота вмешательств, полные видеозаписи.

Между полностью завершёнными seeds показываем mean/std/min/max Macro-SR
и таблицы каждого seed без выбора лучшего. Межseed std описательный,
не доверительный интервал. Три повтора не создают 597 независимых task/init.
Нельзя собирать naive pooled CI по всем rollout как по независимым задачам.

Coverage-аудит использует сохранённые online evidence. Terminal labels
используются только для последующего анализа. Это диагностика gate,
не новое обучение, не калиброванная вероятность fail и не доказательство
предсказания падения заранее. Новых порогов по этим таблицам не подбираем.

## Операционная поправка

Scientific config исходной серии не изменён:
`eeb5a2a9590b1b20cc0b26f6b9193a1f22b619abc1eb71c6f696c2dee67f4479`.
Root `scripts/*.py`, модель и assets не изменены. Ресурсный `budget.json`
сокращён с прежнего 11:17 до 08:30 по новому сроку пользователя;
исходный budget сохранён в `operations/original_budget_before_0900_request.json`.

Scope-local adapter перенаправляет только subprocess-вызов построения отчёта
на исправленную reporting-only копию. Он не изменяет глобальный subprocess,
collector, candidate selection или simulator. Это устраняет duplicate-key
ошибку `value_std`/`value_range`, не меняя рассчитанные метрики.

Config SHA S1:
`b70d3f649c5dfa0637231990389dcf1d43229c8336e7fa3f1808f67b699e5bb1`.
Config SHA S2:
`17cef1d12db96c97a9c10734bb0e81c50c61a53ba8946851fbfeb8bec13807c5`.
Проверено: изменены только name/created_at/scope и rollout seeds; task/init,
arms, assets и гиперпараметры сохранены. 6 новых operational/audit tests
прошли локально и на сервере; 5 reporting tests прошли ранее локально.

Очередь detached, не зависит от SSH-сессии/локального ПК. Перезапуск самого
серверного узла её остановит; завершённые artifacts пригодны для resume.
GPU0-7 берутся только при двух idle readings и отсутствии compute processes,
один worker на GPU, общие project locks. Чужие процессы не останавливаются.

## Проверенный запуск

01:07 МСК: supervisor PID85088 жив, child supervisor PID85152,
восемь workers на GPU0-7 загрузили модель, память около 7.3 GB/GPU.
Счётчик вырос 307 -> 319. CPU watcher PID88851 запущен отдельно.
Это подтверждение реального прогресса, а не только создания процесса.

Повторная проверка01:10: **345/995**, 64 полностью matched cases; все восемь
workers живы, traceback в концах активных логов нет, CPU watcher жив.
[Машиночитаемая проверка](campaigns/p3_benchmark_closure_20260914_v3/operations/launch_verification_20260915.json).

## Где смотреть

Общий путь: `experiments/campaigns/p3_benchmark_closure_20260914_v3/operations/`.

- `night_status.json`: текущая серия, прогресс и ETA без прежнего простоя;
- `plan.json`: зафиксированный порядок, offsets, deadline и hashes;
- `publication_audit/RESULTS.md`: автоматически обновляемый сводный отчёт;
- `publication_audit/benchmark_by_seed.csv`: факторные таблицы по seeds;
- `publication_audit/complete_seed_macro_summary.csv`: только полные seeds;
- `publication_audit/event_coverage_by_seed.csv`: где trigger перестаёт срабатывать;
- `publication_audit/macro_by_seed.png`: сравнение методов и seed-групп;
- `publication_audit/comparison_videos.html`: все matched cases с разными
  исходами между методами, включая rescue и harm, с исходными MP4.

Каждая серия также сохраняет собственные `analysis/RESULTS.md`, CSV,
`paired_effects.csv` после полного завершения и полный видеоиндекс.
Локальный HTML воспроизводит видео только после скачивания соответствующих MP4.

Из WSL:

```bash
ssh mlspace-sr006 'python3 /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/p3_benchmark_closure_20260914_v3/operations/status.py'
```

[Исходный протокол benchmark](P3_BENCHMARK_CLOSURE_PROTOCOL_20260914.md).
[Промежуточные результаты до возобновления](P3_BENCHMARK_PARTIAL_RESULTS_20260915.md).

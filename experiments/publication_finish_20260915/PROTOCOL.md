# Ночное завершение для ICRA, 15–16 сентября 2026

Основная конференция уточнена по дедлайну «завтра утром 11:00»: ICRA 2027.
План зафиксирован до результатов новых серий. Это исправленная репликация
исторических опытов, не preregistration задним числом и не новый скрытый test.

| Порядок | Что проверяется | Новые rollout |
|---|---|---:|
| 1 | Техническая проверка v2: 1 familiar + 1 transfer case, 4 arms | 8 |
| 2 | Все 128 исходных cases (init 25–32), H16/H8/full/preserve | 512 |
| 3 | Те же cases, вмешательство в t=56 и t=88, 3 suffix arms | 768 |
| 4 | Тот же начальный gate; open + retreat + relocalize + H8, без grasp | 128 |

Всего 1416 новых rollout. В последнем сравнении 384 baseline/full/H8 rollout
переиспользуются, а не объявляются новой независимой статистикой.
Сравнение full-vs-retreat включает все 64 familiar и 64 transfer cases,
в том числе отказы gate и успешные baseline.

## Что не меняется

Замороженная Cosmos Policy LIBERO 2B; K=4; 5 denoising steps; предсказанный
горизонт T=16; H16 prefix / H8 suffix; 280 физических действий + 10 settle;
teacher/calibration artifacts; task/init/variant, rollout seeds и расписание
candidate seeds; 8 familiar cells и 8 transfer cells со сдвигом x=0.3.
Исходный запуск `recovery_confirmation_20260913` не изменён.

Исправление runtime: полное MuJoCo integration state, warmstart, sensor clocks
и cache. Legacy-v1 prefixes нельзя загрузить как v2. Все новые prefixes
проверяются по схеме состояния.

Основной config SHA:
`91c8a14d9c0bd1caf50b645f53f9caff49df1d3a4edecf4517b70142d30a9b32`.
Технический config SHA:
`82224e054729549354740b951ac1a862041aaae00106d5bac77400108cc95497`.
Исходные скрипты и runtime-v2 source не изменяются: адаптеры находятся здесь.
Расширение в подпапке не меняет зафиксированные файлы основной очереди.

## Гипотезы и анализ

1. Сохраняется ли историческое преимущество physical recovery после исправления
   восстановления состояния? Основное сравнение: familiar full-H8; transfer отдельно.
2. Сохраняется ли результат в t=56 и t=88? Это вторичный анализ чувствительности,
   не поиск лучшего t на test и не доказательство универсальности границы 72.
3. Объясняется ли выигрыш только дополнительным наблюдением? Full и retreat имеют
   одинаковый начальный gate, общую open/retreat часть и исходный бюджет действий.
   Retreat не выполняет approach/descent/close/lift. Это не latency-matched контроль.

Анализ: success counts, парные cluster CI, sign-flip tests, Holm внутри семейства,
rescue/harm, coverage, NFE/queries, физические шаги и полные MP4.
Continuation-пары ветвятся из идентичных v2 prefixes. Отсутствие вмешательства
проверяется совпадением executed actions и final state с H8.
Новые контрольные outcomes нельзя объединять с историческими версиями.

## Автономность и ресурсы

Основной supervisor PID 269634, запущен в 19:53:53 МСК 15 сентября.
Технические 8/8 завершены в 19:59:06, аудит пройден; далее 8 workers на GPU 0–7.
Retreat queue PID 274924 ожидает полного завершения основной серии и аудитов.
Используются только свободные GPU, две проверки простоя, общие project locks,
один worker на GPU. Чужие процессы не останавливаются; занятая карта пропускается.

Общий срок остановки: **07:50 МСК 16 сентября**, до 120 секунд на завершение
процессов, без автоматического продления. Ошибка аудита блокирует продвижение;
недосчитанный к дедлайну результат остаётся partial.
Оба supervisor отсоединены от SSH; отключение локального ПК не останавливает их.
Поиск новых порогов и обучение на test не выполняются.

Предварительная оценка при 8 свободных H100: около 4–8 часов, но сохранение
snapshot и видео, длинные transfer failures и ожидание GPU могут увеличить время.
Весь 12-часовой бюджет необязателен: после фиксированного плана очередь
завершится сама. ETA основного диспетчера стабилизируется после первых полных batches.

Команда статуса:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/publication_finish_20260915/run.py --status'
```

Статус retreat queue: `extensions/status.json`. Отчёты автоматически строятся в
`experiments/campaigns/recovery_scoped_runtime_v2_20260915/analysis/` и
`experiments/campaigns/recovery_retreat_runtime_v2_20260915/analysis/`.
Выгрузка и PDF: [publication/joint2027](../../publication/joint2027/README.md).

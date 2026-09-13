# Ночная очередь: запуск проверен 11 сентября 2026

- Новый dispatcher: **PID 1544368**, запущен **22:11:08 MSK**.
- Отдельный watchdog: **PID 1545764**, проверен живым вместе с dispatcher.
- Статус после запуска: `waiting_dependency`, `active={}`, `0/1440` новых rollout.
- Dependency: `observation_contract_20260911`, dispatcher **1289972** продолжает работу.
- Старый ожидающий decoder dispatcher **1467069** получил SIGTERM только после
  проверки пути команды, PID, состояния `waiting_dependency` и отсутствия workers.
  Он завершился со статусом `paused`; прежние status/launch сохранены в
  `resource_deadline_backup_20260911/`. Текущую Observation Contract не останавливали.

## Замороженные параметры

Исходный `config.json` сохранён без изменений:
`455587b0624f8253d5fc8b6c4b6dab8a0bc57aed64a8afa770f29e9cd8d49ac4`.

Новый `night_plan_20260912_1000.json`:
`fd0a58dc03edc8bd0becaab7343b00d0ef11699ae9cb83bde11b0bf00794cd36`.

Порядок: 3 hook smokes, 720 базовых rollout, 360 fixed-seed controls,
до 360 H8 controls. GPU 0-7 только при двух idle readings и отсутствии
compute-процессов, общие locks. Не более одного worker на GPU.

В `night_budget.json` проверены абсолютные границы:

| Событие | MSK 12 сентября | Unix epoch |
|---|---|---:|
| Прекращение вычислений | 09:40 | 1789195200 |
| Принудительное завершение оставшихся наших workers | 09:42 | 1789195320 |
| Дедлайн формирования отчётов | 09:58 | 1789196280 |
| Пользовательский дедлайн | 10:00 | 1789196400 |

Новая группа заранее не допускается, если консервативная оценка времени
не помещается до compute cutoff. Неполные группы не превращаются в failures.
Независимый watchdog также ограничивает время самого supervisor.

## Техническая проверка, не основная статистика

81 unit/regression tests прошли локально, включая остановку очереди при
истёкшем дедлайне до проверки dependency/GPU. Серверный набор 80/80 прошёл.
Избыточный повтор 81 теста на сервере был остановлен отдельно (PID1544601):
он задержался на чтении зависимостей с NFS. Это не ошибка теста или rollout;
дополнительный deadline test подтверждён локально, не заявляется как
повторно прошедший на сервере. GPU workers и dispatcher не затрагивались.

`local_validation/extension_audit.json` подтверждает проверку всех 9 локальных
rollout: **1919 кадров полностью декодированы**, NPZ/MP4 проверены по SHA256,
сохранённые actions совпали с исполненными; следующий query использует
предыдущее реальное observation, H8 не получает некорректный H16 prediction error.

| Метод | Success | Шаги |
|---|---|---:|
| First H16 | true | 165 |
| Max-value H16 | true | 222 |
| Action medoid H16 | true | 158 |
| Decoder medoid H16 | true | 159 |
| Fixed candidate 1 H16 | true | 159 |
| Fixed candidate 2 H16 | false | 280 |
| Max-value H8 | false | 280 |
| Decoder full H8 | true | 207 |
| Decoder prefix H8 | false | 280 |

Один заранее выбранный технический пример, не evidence of generalization.
Fixed candidate 1 H16 побитово повторил decoder medoid H16 по действиям
и конечному состоянию. Не менять план/гиперпараметры по этим результатам.

## Данные и отчёты

Серверный каталог кампании остался symlink на
`/home/jovyan/.local/share/malnev_world_model_spill/decoder_token_medoid_20260911`.
Передавались только новые исходники, тесты, документы, frozen sidecar и локальная
техническая валидация. Live status не перезаписывался локальной копией.

Основной отчёт после расчёта: `analysis/REPORT.md`.
Контроли: `night_analysis/REPORT.md`; все видео: `night_analysis/video_comparison.html`.
[План и команды из WSL](../../DECODER_MEDOID_NIGHT_20260912.md).

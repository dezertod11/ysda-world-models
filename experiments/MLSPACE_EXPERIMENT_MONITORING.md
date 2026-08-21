# Мониторинг экспериментов на MLSpace

Дата: 21 августа 2026 года.

## Одна команда из WSL

В `~/.local/bin` установлен launcher:

```bash
ysda-exp-status
```

Без аргументов он находит свежую реально работающую кампанию. Если активных
кампаний нет, показывается последняя изменённая.

Основные варианты:

```bash
# Последняя активная или последняя завершённая кампания.
ysda-exp-status

# Конкретная кампания.
ysda-exp-status factorial_selection_horizon_20260820

# Обновлять раз в минуту до READY, FAILED или STALLED.
ysda-exp-status factorial_selection_horizon_20260820 --watch 60

# Последние кампании одним списком.
ysda-exp-status --all

# Все jobs и найденные серверные процессы.
ysda-exp-status factorial_selection_horizon_20260820 --verbose

# Машиночитаемый вывод.
ysda-exp-status factorial_selection_horizon_20260820 --json
```

Команда подключается только к `mlspace-sr006` и читает серверную папку:

```text
/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/
  YSDA_WORD_MODELS_PP/experiments/campaigns
```

## Как читать состояние

| State | Значение | Что делать |
|---|---|---|
| `PLANNED` | manifest создан без запуска | Не анализировать |
| `RUNNING` | jobs исполняются | Ждать; ETA приблизительный |
| `FINALIZING` | rollout завершены, aggregate analysis ещё работает | Ждать |
| `READY` | manifest завершён и связанных процессов нет | Можно анализировать |
| `FAILED` | хотя бы один job завершился ошибкой | Сначала смотреть logs |
| `STALLED` | manifest остался `running`, но нет процесса и свежей активности | Запуск оборвался; нужен resume |

Для полной кампании должны одновременно выполняться условия:

```text
State    : READY
Jobs     : N/N (100.0%)
Rollouts : M/M (100.0%)
ETA      : complete
```

Строка `Analysis` показывает найденные `summary.json` и `README.md`. Если
`READY` есть, но aggregate summary отсутствует, rollout уже полны, однако
анализатор для этой кампании либо не предусмотрен, либо его надо запустить
отдельно.

## Как считается ETA

Оценка использует:

1. фактические `started_at` и `finished_at` завершённых jobs;
2. число реально записанных rollout в parquet/CSV traces;
3. верхний объём из `MAX_ROLLOUTS_PER_INIT`, suites/tasks/init states и числа
   planning strategies;
4. последовательные очереди jobs отдельно на каждой GPU.

Из завершённых jobs оценивается медианное GPU-время одного rollout. Затем
считается оставшееся время каждой GPU-очереди; ETA кампании равен самой длинной
очереди. Поэтому значение корректнее простого деления общего elapsed time на
процент готовности, но всё равно является приблизительным: success может
завершить episode раньше timeout, model initialization имеет фиксированную
цену, а early-stop collectors могут не использовать максимальное число
rollout.

## Совместимость следующих экспериментов

Monitor автоматически работает для кампаний, запущенных через
`scripts/run_libero_experiment_campaign.py`: нужен каталог
`experiments/campaigns/<run_name>/manifest.json`. Новый профиль или новый тип
метрики не требует изменения status-команды, пока сохраняются manifest,
completion markers, logs и `*__query_traces.parquet`/CSV.

Для произвольного standalone-скрипта без manifest ETA определить надёжно
невозможно. Такой запуск сначала следует оформить как campaign profile, а не
оценивать завершение по `nvidia-smi`.

## Реализация

- WSL launcher: `scripts/mlspace_experiment_status.sh`;
- серверный анализатор: `scripts/status_libero_campaign.py`;
- тесты: `tests/test_campaign_status.py`.

Переопределения при необходимости:

```bash
MLSPACE_SSH_HOST=mlspace-sr006 \
MLSPACE_PROJECT_ROOT=/path/to/server/project \
ysda-exp-status latest
```

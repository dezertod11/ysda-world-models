# P4c2: сокращённая проверка на GPU 3-7

## Почему изменён объём

8 сентября пользователь попросил вернуться к обычному масштабу проверки
метода и использовать GPU 3-7. В предыдущих проверках были сотни траекторий:
P4c consensus-medoid: 180 development rollout; P3e: 225 terminal branches.
Это разные протоколы, не одинаковые по стоимости единицы измерения.
Исходные 4500 rollout P4c2 были расширенной benchmark-проверкой, существенно
больше обычного этапа отбора метода. Development **392/392** уже завершён.

Новая кампания: `trajectory_consensus_20260908_compact`. Исходный full-run
не удаляется и не объявляется завершённым. Его два scheduler-процесса
приостановлены; текущие задания дописывают эпизоды и видео. Отдельный
drain-процесс завершит только эти проверенные scheduler PID после окончания
их дочерних заданий. Новая очередь уже может использовать свободные GPU.

## Зафиксированное сравнение

| Фактор LIBERO-PRO Object suite | Задачи | Init | На метод | Всего, 3 метода |
|---|---:|---|---:|---:|
| Object | 0-9 | 2-6 | 50 | 150 |
| Environment | 0-9 | 2-6 | 50 | 150 |
| Position, все x/y 0.1-0.5 | 0-9 на каждом уровне | 1 | 100 | 300 |
| Итого | 120 task/perturbation cells | | 200 | **600** |

Методы: обычная policy `first` K1, `max_value` K4 и замороженный
`trajectory_medoid` K4. Последний выбран на development как
`physical_medoid`; это не guarded/value-density вариант. Перевыбора по
результатам compact не будет. Исходные `winner.json`, `full_config.json`,
`full_sha256.json` и снимок runtime сохранены без изменений.

Генерируем и выполняем H16; 5 denoising steps; лимит 280 действий.
Prediction mode: `parallel`, совместная генерация action/future/value,
не авторегрессионный a -> s -> v. Environment: прежний изолированный
`living_room_table`, seed 20260908. Меняются только число init и расписание
вычислений, не сложность среды, модель или определение success.

## Повторное использование

На старте перенесены **35** завершённых эпизодов K1 Object вместе с видео
и всеми query-метриками; **565** rollout предстоит вычислить.
Отбор только по заранее указанным числовым init, без фильтра по success/fail.
Исходные trace, видео и SHA256 записаны в `reuse_manifest.json` и `__reuse.json`.
Другие накопленные результаты остаются в старом full-run.

При сокращении списка init collector перенумеровывает `pair_id` с нуля.
Поэтому base seed увеличен на 20000 для Object/Environment и на 10000 для
Position. Это сохраняет исходный rollout seed конкретного init:

$$
s_i^{\mathrm{compact}}=(s_0+10^4 i_{\min})+10^4(i-i_{\min})
=s_0+10^4 i=s_i^{\mathrm{full}}.
$$

Проверяются selector, K, denoising budget, H16, seed, все query и непрерывность
timeline до `final_t`. При resume начатые новые trace не заменяются архивными.
Исходный `pair_id` перенесённых эпизодов хранится в `source_pair_id`.

## Анализ и ограничения

Основные результаты: SR отдельно по трём факторам, macro-SR с одинаковым
весом факторов, paired delta к max-value и K1, rescue/harm, task/init-cluster
bootstrap CI и drop/safety proxies. Position имеет больше эпизодов, поэтому
pooled SR не заменяет macro-SR. Проверяются одинаковые q0 simulator states;
одинаковые seeds сами по себе не гарантируют побитово одинаковые action pools.

Это **resource-amended compact evaluation**, а не завершённый исходный
benchmark на 4500 rollout. Изменение принято после начала full-run;
нельзя описывать его как изначально зарегистрированный untouched full test.
Init не использовались в текущем development, но отсутствие пересечения со
всеми историческими исследованиями не утверждается. На Position всего один
init на cell, поэтому выводы о переносе на новые init ограничены.

Время уже использованных эпизодов не входит в новые job wall seconds.
Отчёт отдельно показывает `reused_episodes/reused_queries`, а стоимость
на эпизод/query считается только по новым. Raw total time методов с разным
объёмом reuse нельзя напрямую сравнивать как latency или полную GPU-стоимость.
Полные MP4 и все uncertainty/prediction-error traces сохраняются как раньше.

## Автономный запуск и статус

Запуск начат **8 сентября, 10:40 MSK**. GPU pool: **3,4,5,6,7**;
один worker на карту. Общая очередь проверяет свободную память и загрузку
перед каждым заданием. Занятая карта ждёт, не резервируя работу; остальные
продолжают расчёт. GPU 0-2 не используются новым запуском, чужие процессы
не останавливаются. На старте новая кампания заняла GPU 3-5, а 6-7 ещё
дописывали два задания исходного full-run.

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/status_libero_campaign.py trajectory_consensus_20260908_compact'
```

В каталоге кампании: `sequence_status.json`, `sequence.log`, `manifest.json`,
`amendment.json`, `reuse_manifest.json`, `drain_status.json`. `completed` в
`sequence_status.json` означает завершение сбора **и итогового анализа**.
Отчёт появится в `trajectory_analysis/RESULTS.md`, график в
`factor_success_rates.png`, сравнение всех видео в `videos.html`.

После сбоя запускать из серверного project root только при отсутствии
работающего процесса кампании:

```bash
nohup bash -c 'source scripts/cosmos_env_libero_pro.sh && exec .venv-cosmos/bin/python -u scripts/run_trajectory_consensus_compact.py --execute --gpus 3,4,5,6,7' >> experiments/campaigns/trajectory_consensus_20260908_compact/sequence.log 2>&1 < /dev/null &
```

Singleton lock и completed markers защищают от повторного запуска цепочки
и пересчёта завершённых заданий. После сбора анализ выполняется автоматически.
ETA зависит от длительности K4 и доступности карт; первые перенесённые
35 эпизодов не являются скоростью нового расчёта.

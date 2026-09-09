# P4c2: автономная полная проверка

**Обновление 8 сентября:** по запросу пользователя full4500 заменён отдельной
проверкой **600 rollout на GPU 3-7**. Development 392/392 завершён, выбран
`trajectory_medoid`. 35 готовых эпизодов перенесены, исходные результаты
сохранены. Текущие команды, ограничения и протокол:
[compact run](TRAJECTORY_CONSENSUS_COMPACT_PROTOCOL_20260908.md).
**Ниже историческое описание исходной цепочки; её не нужно возобновлять.**

Канонический серверный root:
`/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP`.

Run base: `trajectory_consensus_20260908`. GPU: **6,7**. GPU0 не используется;
2-5 были заняты чужими процессами при запуске. Расчёт работает на сервере,
выключение локального ПК его не останавливает.

Срез 8 сентября 02:11 MSK: 7/7 smoke завершены и анализ прошёл; автоматически
стартовал development. [Первые результаты и видео](TRAJECTORY_CONSENSUS_SMOKE_RESULTS_20260908.md).

Цепочка: offline -> 7 smoke -> 392 development -> freeze winner -> 4500 full
-> итоговый анализ. Отдельное ручное разрешение между этапами не требуется.
На двух GPU это длительный расчёт, потенциально многодневный, не обещание
завершения за ночь. ETA следует смотреть по фактической скорости.

## Статус из WSL

```bash
ssh mlspace-sr006 'cat /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/campaigns/trajectory_consensus_20260908/sequence_status.json'
```

Число завершённых rollout и ETA текущего этапа (заменить `_smoke` на
`_development` или `_full`, когда цепочка перейдёт дальше):

```bash
ssh mlspace-sr006 'cd /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP && .venv-cosmos/bin/python scripts/status_libero_campaign.py trajectory_consensus_20260908_smoke'
```

Лог цепочки: `experiments/campaigns/trajectory_consensus_20260908/sequence.log`.
В соседнем `heartbeat.txt` время, PID и stage. `completed` в status всей
цепочки означает, что полный тест и анализ закончены; completed у smoke
не означает завершения всей кампании.

## Результаты

Для каждого этапа в `experiments/campaigns/trajectory_consensus_20260908_<stage>/`:

- `trajectory_analysis/RESULTS.md`: SR по факторам, paired uplift, CI.
- `factor_scores.csv`, `task_scores.csv`, `paired_effects.csv`, `episode_outcomes.csv` внутри `trajectory_analysis/`.
- `reserved_init_scores.csv`: subset inits, не использованный в текущем development.
- `query_behavior.csv`: переключения и horizon-aligned prediction queries.
- `cost_and_switch_rates.csv`: switch rate и job wall time, включая загрузку модели и I/O.
- `factor_success_rates.png`: график success rates.
- `videos.html`: реальные видео всех matched episodes рядом.
- `video_index.json`: пути для переноса видео вместе с отчётом.
- `runs/*__query_traces.parquet`: полный query-level trace, uncertainty, scores, actions и post-chunk errors.
- `videos/`: MP4 полных эпизодов до success или лимита.

`winner.json` и `full_sha256.json` в каталоге цепочки являются freeze manifest.
Копия runtime находится в `source/cosmos-policy/`, hashes в `source_sha256.json`.
Правка основного `cosmos-policy` не меняет уже запущенные inference процессы.
Launcher/analysis scripts не следует менять во время кампании без отдельного
аудита: runtime зафиксирован, но orchestration остаётся в основном `scripts/`.

## Возобновление после сбоя

На сервере из project root, только если status=failed и старый процесс завершился:

```bash
nohup bash -c 'source scripts/cosmos_env_libero_pro.sh && exec .venv-cosmos/bin/python -u scripts/run_trajectory_consensus_sequence.py --gpus 6,7' >> experiments/campaigns/trajectory_consensus_20260908/sequence.log 2>&1 < /dev/null &
```

Singleton flock предотвращает две активные цепочки. Существующие completed
markers используются для resume; `--force` не применяется. Между этапами
проверяется свободная GPU память два раза. При ошибке кода/данных цепочка
останавливается с failed, а не пропускает плохие jobs и не подменяет их успехом.

Начальные проверки: 6 unit tests геометрии, 10 тестов benchmark-конфига и анализа;
на сервере 33 теста geometry + planning integration и 10 config/analysis прошли.
Ещё 6 существующих проверок целостности старого анализа прошли локально. На момент создания
этой памятки полный тест ещё не завершён, итоговый SR неизвестен.

# Decoder medoid: проверка реализации и запуска

**Ресурсный запуск ниже заменён ночной очередью в 22:11 MSK.**
[Текущие PID, дедлайн 10:00 и расширенные проверки](NIGHT_LAUNCH_VERIFIED.md).
Ниже сохранён исторический акт первоначального запуска, не текущий статус.

Проверено 11 сентября 2026, 21:42 MSK.

## Сервер

- Первоначальный запуск: **21:35:44 MSK**, PID1438966.
- После восстановления storage symlink: **21:41:38 MSK**, текущий PID **1467069**, отдельная session.
- Состояние: **waiting_dependency**, active workers нового метода: **0**.
- Полные новые server rollout: **0/720**, server capture smoke: **0/3**.
- Ожидается завершение `observation_contract_20260911`; она продолжает работу.
- После её штатного completed/partial: три обязательных capture smoke,
  затем 180 paired configurations x четыре full-episode стратегии.
- Разрешены idle-only GPU0-7, до семи workers, общие GPU locks. Чужие
  процессы и текущие workers проекта не останавливались.
- 24-часовой бюджет новой кампании начинается только при первом GPU admission.
- Процесс проверен через `ps`; это не только созданный JSON с планом.

Замороженный config SHA256:

`455587b0624f8253d5fc8b6c4b6dab8a0bc57aed64a8afa770f29e9cd8d49ac4`.

Серверный `--validate` подтвердил scripts, frozen Cosmos runtime, все BDDL/init
assets и archived upstream evidence. 70 тестов прошли локально и на сервере,
включая сравнение cosine costs с исходной GR00T функцией, не запуская её сервер.
В четырёх используемых asset sets по десять файлов, по 50 init на задачу.

## Локальная GPU-проверка

RTX 5070 Ti, существующее окружение `cosmos_policy_libero`.
Первый запуск обнаружил локальное различие HF cache roots, ещё до inference.
Повторный использовал явные пути к уже имеющимся checkpoint/T5/statistics;
новые веса и окружения не скачивались, глобальный HF cache не менялся.

Capture smoke: 3 candidates x [без hook, hook, повтор hook]. Actions,
generated latents, values, future images побитово одинаковы; RNG состояния
совпадают, hidden features повторяются побитово. 5 denoiser forwards на
candidate, hidden grid [1,9,14,14,2048], action slice index 4, 196 tokens.

[Полный capture audit](local_validation/smoke/Object_base_t0_i0_g0/hook_audit.json).

Полный integration case Object/task0/init0, seeds 1,999,998:

| Стратегия | Success | Шаги | Query | Кадры видео |
| --- | --- | ---: | ---: | ---: |
| first | true | 165 | 11 | 166 |
| max_value | true | 222 | 14 | 223 |
| action_medoid | true | 158 | 10 | 159 |
| decoder_medoid | true | 159 | 10 | 160 |

Все четыре видео полностью декодированы: **708/708 кадров**.
Это технический integration, **не основные результаты и не оценка прироста SR**.
Все стратегии success на одном случае; длительность здесь не доказывает
переносимость или безопасность. Integration исключён из server screen.

Decoder-medoid выбирал candidate 1 на всех десяти queries. В основной
серии отдельно логируются choice frequencies: возможный constant-seed bias
должен быть отделён от настоящей state-dependent селекции.

[Видео четырёх стратегий рядом](local_validation/analysis/video_comparison.html).
[Графики метрик](local_validation/analysis/Object_base_t0_i0_g0__metrics.png).
[Сводка integration](local_validation/analysis/summary.json).

## Хранение и следующий шаг

На NFS2 осталось около 930 MiB. Новые результаты пишутся через campaign symlink
на `/home/jovyan/.local/share/malnev_world_model_spill/decoder_token_medoid_20260911`
(на момент проверки около 2.1 TiB свободно). Исходники/venv остаются в каноническом
проекте, прежние результаты не переносились и не удалялись.

При финальной отправке документации `rsync -aR` заменил campaign symlink
обычной директорией. Это замечено до начала новой GPU-работы. Только новый
ожидающий dispatcher остановлен SIGTERM; содержимое объединено с сохранённым
spill-каталогом без удаления файлов, ссылка восстановлена, тот же frozen
config повторно прошёл validate и dispatcher перезапущен. Прежняя кампания
не прерывалась. Резервная копия промежуточной директории сохранена в
`.runtime/sync_recovery/decoder_token_medoid_20260911_2141`.
Для будущего `rsync -aR` через известные campaign symlinks нужен
`--keep-dirlinks`; live status/budget никогда не отправляются поверх серверных.

Проверять живой статус командой из
[протокола](../../DECODER_TOKEN_MEDOID_PROTOCOL_20260911.md).
После основной серии автоматически появятся `analysis/REPORT.md`, SR по
факторам/задачам/seed groups, парные эффекты, query metrics и video gallery.
При незавершённой серии анализ учитывает только полные matched groups;
пропуски не заменяются failures. Положительный эффект не заявляется заранее.

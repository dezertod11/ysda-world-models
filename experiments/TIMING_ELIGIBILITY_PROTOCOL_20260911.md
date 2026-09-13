# Задержка и повторный допуск к recovery: замороженный протокол

11 сентября 2026. Campaign `timing_eligibility_20260911_v2`.
Основание: [предыдущие 576 ветвей](GROUNDED_PROBE_RESULTS_20260911.md).
Никакие результаты этой новой серии не использовались для выбора порогов.

**Итоговая запись:** серия завершилась11сентября в15:09:03MSK,10smoke+480screen.
[Полные результаты и видео](TIMING_ELIGIBILITY_RESULTS_20260911.md).
Primarygate NO-GO, holdout38–45 не открыт. Ниже сохранены замороженная
постановка и хронология запуска; указания «работает» относятся к тем срезам.

Запуск v2: **13:54:59 MSK**, dispatcher `683261`, config SHA256
`2b37ed40ac413a3445b73ad09ebb21a4f0e1784df3e223b6f9826b1a06cd17dd`.
Бюджет до **19:45:34 MSK**, без продления при техническом перезапуске.
До запуска прошли **77 тестов локально и на сервере**; все 40 asset-файлов
содержат 50 init. **14:01 MSK: smoke завершён 10/10, основная серия работает
на GPU 1–7.** Шесть старых controls совпали точно; четыре common-delay и три
equal-decision проверки пройдены. Десять видео декодируются и имеют ожидаемое
число кадров. [Акт проверки запуска](campaigns/timing_eligibility_20260911_v2/LAUNCH_VERIFIED.md).
Этот срез не является live-status или подтверждением выигрыша нового метода.

### Техническая история

Первая версия стартовала в 13:45:33 MSK (PID 664374). Ранний строгий replay
выявил расхождение контрольной траектории; dispatcher остановлен до screen.
Сохранены 9 технических ветвей и 0 основных ветвей, исходный config и
[архив исходников](campaigns/timing_eligibility_20260911/source_before_seed_fix.tar).
При чтении готового prefix пропускался повторный `set_seed_everywhere`,
который в fresh-prefix пути восстанавливает deterministic cuDNN после
изменения флагов загрузчиком Cosmos. Различалась уже начальная RGB-локализация,
после чего расходились действия. В v2 тот же вызов выполняется и для cached
prefix после загрузки модели. Это техническое исправление, а не изменение
научного метода. Точные replay-проверки не ослаблены; пороги, seeds, manifest
и deadline прежние. Первая версия исключена из оценки SR нового метода.
После исправления все шесть старых controls воспроизведены точно, включая
actions, final simulator state и signals. Это подтверждает устранение
обнаруженной проблемы в двух проверенных replay-конфигурациях.

## Вопрос и гипотезы

Ранее delayed recovery отменил 14 из21 исходно разрешённых вмешательств.
На y0.1/task9: full8/8 против delayed3/8. Но одновременно менялись время
вмешательства и повторный trigger. Нельзя приписывать эффект только задержке.

H1: сохранение исходной eligibility устраняет часть вредных отмен recovery.
H2: важен конкретный компонент fresh gate: miss-distance или также
confidence/workspace/reach. H3: после одинаковых восьми действий новое
вмешательство может вредить уже успешному захвату, поэтому persistence не
обязательно полезна. Сравнение с немедленным recovery остаётся обязательным.

## Формулы и пять ветвей

Пусть $t_0=72$, $t_1=t_0+8$. Исходный frozen trigger:

$$
G_t=F_t C_t W_t R_t M_t,\qquad S_t=F_t C_t W_t R_t.
$$

$F$: конечные значения RGB-localization и proprio; $C$: прежний object-specific
порог score range; $W$: прежний calibration workspace; $R$: прежнее максимальное
reach distance; $M$: прежнее минимальное расстояние target–EEF, proxy miss.
Здесь $S$ обозначает ограниченный набор проверок, **не гарантию безопасности**
или доказательство, что объект не находится в захвате.

| Arm | Запрос recovery | Момент | Роль |
|---|---|---|---|
| continue_h8 | 0 | Нет | Контроль без вмешательства |
| physical_regrasp | $G_{t_0}$ | t72 | Прежний сильный контроль |
| delayed_regrasp_h8 | $G_{t_0}G_{t_1}$ | После8policy actions | Прежняя задержка со свежим полным trigger |
| delayed_latched_checked_h8 | $G_{t_0}S_{t_1}$ | После тех же8actions | Основной кандидат: сохранить eligibility, заново проверить confidence/geometry/reach |
| delayed_latched_h8 | $G_{t_0}$ | После тех же8actions | Только simulator diagnostic: исключить повторный внешний trigger |

При $G_{t_0}=0$ все ветви продолжают обычную policy без специальной задержки.
Если успех достигнут во время восьми действий, recovery не выполняется.
Все запросившие recovery вызывают **неизменный** RGB regrasp primitive:
retreat с открытием gripper, новая локализация, актуальные finite/confidence/
workspace/reach guards, затем оставшиеся действия только при их допуске.
После failed guard реальный retreat не отменяется откатом физики.

У diagnostic arm нет новой проверки до retreat. Он может открыть уже
успешный захват и причинить вред; проверяем это только в симуляторе. Даже
checked arm не является collision-safe или grasp-aware controller. Не
называем отсутствие отмены trigger доказанной безопасностью. Diagnostic arm
не продвигается автоматически независимо от SR.

Сравнение checked с fresh отделяет удаление miss-distance из внешнего
повторного gate. Diagnostic с checked отделяет также confidence/workspace/
reach до retreat. На пути после retreat guards у них одинаковы. Таким
образом, свежая локализация не заменяется старой координатой целевого предмета.

## Модель и pairing

LIBERO-PRO Position семейства Object tasks; tasks2/5/9. Замороженные Cosmos,
RGB localizer, artifact trigger и recovery primitive из прошлого исследования.
Общий K4/H16 prefix доt72. Далее K4, generate16/execute8, 5denoising steps,
joint/parallel action/future/value, не AR a→s→v. Training и mask inference нет.

Три delayed arms используют одинаковый query5, его action chunk и первые8
действий. Проверяются совпадения post-delay sim state, observation hashes и
действий. Дальше query6; query seed не переиспользуется. Controls без delay
начинают suffix сquery5. Pairing по query index, не физическому t после
разных interventions. Максимум280 физических шагов, включая retreat/recovery;
10settle steps вне этого бюджета, как раньше.

## Выборки

| Фаза | Данные | Ветвей |
|---|---|---:|
| Replay smoke | Старые сохранённые prefixes x0.2_t2_i35_r1 и y0.1_t9_i34_r1 | 2×5=10 |
| Prospective screen | 12cells ×init46–49 ×2seeds ×5arms | 480 |

Всего490ветвей. Smoke проверяет побитовое воспроизведение трёх старых
контролей (continue/full/delayed-fresh); его outcomes не являются независимой
новой статистикой и не используются для настройки. При несоответствии
trajectory/state/signal parity основная серия не начинается.

Cells: x0.2/tasks2,5; y0.2/tasks9,2; x0.1/tasks5,9,2; x0.2/task9;
y0.1/tasks2,5,9; y0.2/task5. Это 12 известных сочетаний, не новые задачи.
Screen: **96 paired states, 48 init clusters**. Init46–49 не пересекаются
с calibration5–24 и прошлым grounded screen/transfer34–37.
Holdout38–45 не открывается; conditional confirmation здесь не запускается.
Все assets проверяются до GPU rollout. Отдельные repeat seeds имеют
непересекающиеся диапазоны query seeds; никаких seed searches до mixed outcome.

## Анализ

Primary: checked-latched против delayed-fresh **и** против immediate-full.
Четыре дополнительных заранее указанных contrasts: delayed-fresh−full,
diagnostic-latched−delayed-fresh, diagnostic−checked, full−continue.
Init-cluster bootstrap внутри фиксированных cells, равные веса cells,
cluster sign test и Holm по шести contrasts. Smoke отдельно от screen.

Условие целесообразности следующей независимой confirmation: у основного
кандидата CI_low>0 и Holm p≤0.05 против обоих controls, drop proxy count
не больше full. Это рекомендация для следующего исследования, не автоматический
доступ к holdout и не доказательство широкого SOTA. Порогов не подбираем.

Сохраняем SR по cell, rescue/harm, query counts, физические шаги, requests
против реально выполненного полного primitive, исходную и свежую локализацию,
все компоненты trigger до/после delay и post-retreat guard. Object motion,
контакты и safety proxies сохраняются только для post-hoc анализа, не online
решения. Эти proxies не official LIBERO-Safety scores. Terminal timeout не
отождествляется с моментом падения предмета или необратимым fail.

Две камеры, H264/yuv420p видео suffix: от конца общего prefix (t72) до
terminal, на каждый реальный шаг. Это не полное видео с reset; соответствие
кадров физическому времени записано в `frame_t` внутри NPZ. Автоматически
создаются CSV, paired effects, SR-график,
таблица причин отказа gate и HTML-галерея для всех методов.

## Исполнение

До7worker; GPU1–7 проверены свободными при подготовке, GPU0 занята чужим
процессом. Кандидаты GPU0–7, только idle и без чужого CUDA PID; две проверки
готовности, по одному worker на GPU, общая очередь и GPU-locks. Чужие
процессы не останавливаются. При занятой карте работа уходит на другие.

Бюджет до 19:45:34 MSK (6 часов от первого исполнения v1), сохраняется
между restart и не продлевается автоматически. По предыдущему throughput ожидается около
2часов на семи свободных GPU, но это оценка, не обещание. По завершении
490ветвей очередь выходит; не заполняет остаток бюджета новым sweep.
Один retry batch в рамках запуска; после повторной ошибки очередь останавливается.
Коммит JSON последним, сохранённые ветви не пересчитываются. Оборванный
некоммитнутый prefix требует проверки, не маскируется под policy fail.
На deadline stop только собственных worker: SIGTERM, после120s SIGKILL.
SSH можно закрыть после detached launch.

Статус из WSL:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_timing_eligibility.py --status'
```

Запуск/продолжение в серверном корне:

```bash
.venv-cosmos/bin/python scripts/run_timing_eligibility.py --launch
```

Конфигурация, scripts, runtime, source-prefix и artifact hashes фиксируются
до запуска. Изменение научных параметров требует новой версии campaign.

## Где искать результаты

Campaign: `experiments/campaigns/timing_eligibility_20260911_v2/`.
`sequence_status.json` на сервере содержит актуальные phase, completed, GPU,
deadline и грубую ETA. Локальный файл является последней скачанной копией.
В начале ETA экстраполируется по двум smoke workers и ещё не отражает
throughput основной серии на семи GPU.

- [Технический аудит smoke](campaigns/timing_eligibility_20260911_v2/analysis/smoke/RESULTS.md)
  и [его видео](campaigns/timing_eligibility_20260911_v2/analysis/smoke/videos.html)
  уже доступны локально; это не независимая оценка выигрыша.
- После завершения screen сформированы и скачаны `analysis/screen/RESULTS.md`,
  `scores.csv`, `aggregate_scores.csv`, `paired_effects.csv`, `gate_reasons.csv`,
  `success_rates.png`, `videos.html` и `summary.json`.
- Исходные измерения, query metrics, решения и видео: `screen/<case>/<arm>.{json,npz,mp4}`.
  Все screen-артефакты скачаны локально. Полный post-hoc аудит и избранные
  видеосравнения находятся в `review_20260911/` этой campaign.

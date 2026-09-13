# Событийные версии вместо обязательного t=72

13 сентября 2026. **Реализовано, CPU-проверка; GPU SR ещё не измерен.**

Решение относится ко всем новым развитиям fixed-q4 методов. Исторические
collectors и их hashes не переписываем: старые числа должны воспроизводиться
старым кодом. Ночная `recovery_confirmation_20260913` продолжает frozen
t56/72/88 control/ablation и не превращается посередине в другой эксперимент.

## Какие методы меняются

| Семейство | Старый вариант | Новый основной entrypoint |
|---|---|---|
| Shared-prefix / scheduled-q4 requery | q4: исполнить 8, requery в t72, ещё 8, вернуть H16 | `--method requery --timing event`: ранний query по доступному сигналу, завершить заменённый интервал, вернуть H16 |
| P3c/P3d, online perception regrasp | RGB gate проверялся только после 4*16+8 | `--method regrasp`: последовательный miss/stall/uncertainty gate; regrasp только prior-close + grounded-miss + geometry |
| Retreat/probe и observation-contract preserve | исходный gate/probe только в t72, часть маршрутов открывала gripper | `--method preserve_probe`: событийный probe .04 м с сохранением последней команды gripper, только при miss и допустимом workspace |
| Probe-verify-repair / grounded-probe | probe+verification в фиксированной точке | `--method verify_regrasp`: passive miss, preserve probe, свежая mask-verification; unknown/held запрещают открытие |
| P3e outcome router, timing/eligibility, oracle ablations | обучены/оценивались на fixed prefixes | Старые weights и oracle routes остаются архивными контролями, **не подключаются** ко всем временам; для новых вариантов использовать общий event entrypoint и переобучить benefit head по новому протоколу |
| Остальные P1/P2/P4/P5/... без fixed72 | value ranking, medoid, overlap и adaptive requery на каждом query | Не менять математический selector ради удаления числа, которого в нём нет. При комбинации с recovery вызывать новый event controller |

Это версии **новых методов**, не переименование старых результатов. В
частности preserve-probe .04 м отличается от observation-contract .08 м:
для изоляции timing сравнивать event и fixed одной новой версии. Для
сравнения с историческим P3 использовать отдельный frozen original arm.
`--timing fixed --fixed-step 72` фиксирует только scheduler новой версии;
новый release-veto остаётся включён, это не буквальная копия старого P3c.

Ни старая `max_value_scheduled_requery` стратегия, ни архивные shell sequences
не являются canonical запуском нового метода. Не запускать их для проверки
переносимого event controller. Их fixed defaults сохранены намеренно.

## Реализованные компоненты

- `scripts/event_feedback.py`: внешний bounded-history controller, memory
  выровненных планов, uncertainty и passive persistence, veto, cooldown,
  общий action budget. Никакого absolute-time feature для event decision.
  При недостаточном остатке бюджета для полного primitive вместо раскрытия
  выполняется requery; учитывается длительность recovery, не фаза в t72.
- `scripts/event_feedback_libero.py`: существующие frozen RGB localizer и
  object-mask, static-camera tracking, существующие servo/regrasp primitives.
  Oracle object poses/contacts только в отдельном diagnostic tracker.
- `scripts/collect_event_feedback.py`: полный эпизод, K4 joint-maxV/H16 по
  умолчанию, actual-time noise seeds, полное MP4 t0..terminal, JSON query
  pools/metrics/evidence/events, NPZ executed actions/safety diagnostics.
  Конфигурация, исходники, runtime и benchmark assets хэшируются; изменение
  запрещает resume в прежний каталог. Незавершённый эпизод пересчитывается,
  уже закоммиченный проверяется по hashes и пропускается.
- Новый CLI явно требует файл thresholds. `parameters_smoke.json` содержит
  **неподобранные smoke-гиперпараметры**, не «лучшие» значения.
- `scripts/calibrate_event_feedback.py`: maxima по suite/task/init groups
  успешных shadow/none эпизодов, finite-sample quantile с разделением alpha
  между наблюдавшимися признаками. Не хватает групп - ошибка, не фиктивная
  калибровка по тысячам кадров. Недоступный overlap отключается, не заменяется
  нулём. Sidecar запрещает переиспользовать даже failed calibration init для
  оценки и проверяет K, perception artifacts и runtime. Это не гарантия OOD
  coverage; geometry/persistence остаются development hyperparameters.
- `none`: H16 без вмешательств; `shadow`: логировать первое возможное
  вмешательство без изменения управления; `event`: применить решение;
  `fixed`: явный контроль, шаг обязателен, default72 отсутствует.

`H=16`, минимальный prefix8, sensor stride4 и cooldown16 означают относительные
интервалы управления, не фазу task в абсолютном t. Они тоже подлежат ablation.
Для H8 контроля использовать отдельный params-файл с execution_horizon8,
min_prefix4 и `--timing none`, сохраняя generated_horizon16.

Если события нет, new controller оставляет в точности H16 sample selection
и schedule вызовов. Измерение uncertainty из уже полученного pool не делает
новый Cosmos forward. Localizer/mask при этом требуют вычислений: полный
контроль мониторинга должен использовать те же artifacts либо учитывать
разницу latency. Shadow-limit1 соответствует default intervention budget1,
а не записи неограниченного числа независимых alarms.

## Команды

CPU-валидация без модели/GPU и без создания результатов:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/collect_event_feedback.py \
  --cases experiments/event_feedback_20260913/cases_smoke.json \
  --parameters experiments/event_feedback_20260913/parameters_smoke.json \
  --output experiments/event_feedback_20260913/shadow_smoke \
  --method requery --timing shadow --validate-only
```

После допуска GPU существующей idle-only очередью (не выполнять поверх
чужого процесса); пример с физической GPU3, если она свободна:

```bash
CUDA_VISIBLE_DEVICES=3 bash scripts/run_libero_pro_event_feedback.sh \
  --cases experiments/event_feedback_20260913/cases_smoke.json \
  --parameters experiments/event_feedback_20260913/parameters_smoke.json \
  --output experiments/event_feedback_20260913/shadow_smoke \
  --method requery --timing shadow --hours 1
```

`cases_smoke.json` - технический Object/task0 пример, **не confirmatory набор**.
Для Position подготовить cases с `suite=libero_object_temp`, экспортировать
`EVENT_POSITION_LEVEL=x0.2`; assets варианта должны быть подготовлены заранее.
Одному process соответствует один position level. Localizer/trigger/mask:
передать `--localizer PATH --trigger PATH --mask PATH`. Без всех трёх artifacts
recovery CLI откажет, а не перейдёт к опасному generic-flow fallback.
В каждом новом mode использовать новый output. Перед GPU0 на MLSpace нужен
также `MLSPACE_ALLOW_GPU0=1`; wrapper не резервирует карту сам.

Большая новая очередь здесь **не запущена**. Сначала GPU import/render/sampling
smoke и calibration, затем фиксированный paired-протокол из
[разбора статей](../articles/EVENT_TRIGGERED_FEEDBACK_REVIEW_20260913.md).
Строгий snapshot-branch experiment на событиях, random-time control,
learned-benefit head и two-view verifier остаются следующей реализацией.
В новом collector пока paired **initial-state** runs; identical prefix после
разошедшихся событий или causal пользу по одним correlations не заявляем.

## Что считать успехом

После сбора development shadow (не единственного smoke) калибровать отдельно:

```bash
python scripts/calibrate_event_feedback.py \
  --runs experiments/event_feedback_20260913/development_shadow \
  --parameters experiments/event_feedback_20260913/parameters_smoke.json \
  --output experiments/event_feedback_20260913/parameters_calibrated.json \
  --alpha 0.1
```

При двух наблюдавшихся uncertainty features alpha0.1 требует хотя бы19
успешных init groups для конечного порога. Это только математический минимум,
не достаточный объём для сильного научного вывода. Для итогового теста
использовать disjoint manifest и calibrated params вместе с sidecar.

В первую очередь меньше harm на already-held и положительный paired SR на
целых новых cells относительно H16/fixed control. Дополнительно model calls,
vision latency, false alarms/episode, miss/held confusion, lead time до
физической ошибки. Сравнивать не только «успехи среди сработавших trigger»:
учитывать все запланированные эпизоды, в том числе ранний success и отсутствие
alarm. Пока есть реализация и тесты, но не доказательство улучшения SR.

## Проверено 13 сентября

- **132 CPU-теста прошли локально и на MLSpace**, включая 38 новых тестов
  event controller, calibration и release-veto adapter; 94 прежних проверки
  recovery, geometry, replay, scheduled-query и GPU admission остались зелёными.
- `--validate-only` обработал настоящий smoke manifest без загрузки модели;
  Python syntax и Bash wrapper проверены, `git diff --check` чистый.
- Новые скрипты, тесты и документация синхронизированы на canonical сервер.
  `run_recovery_confirmation.py --validate` подтвердил прежние frozen
  исходники/runtime/assets/replay inputs. Ночная серия не перезапущена.
- Полный GPU import/render/sampling smoke нового collector **ещё не выполнен**.
  Нет результатов event-SR и нет обученных/calibrated artifacts от новых
  rollouts; `parameters_smoke.json` остаётся только техническим примером.

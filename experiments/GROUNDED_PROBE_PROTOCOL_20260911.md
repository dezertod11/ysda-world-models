# Object-grounded verification и время восстановления: протокол

11 сентября 2026. Campaign: `grounded_probe_20260911_v2`.
План фиксируется до новых rollout labels. Предыдущая версия остаётся
неизменной: [v2, отрицательный screen](PROBE_VERIFY_REPAIR_RESULTS_20260911.md).
Предельное окончание рабочего окна: **11 сентября 08:35 MSK**, не позже
семи часов от первой проверки ресурсов. При нехватке времени серия сохраняется
как partial, а не дополняется вымышленными fail.

**Итог, добавлен после завершения:** серия закончилась03:56:57MSK,
48smoke +384screen +144transfer. Screen gate NO-GO; conditional confirmation
не открывалась. [Анализ, выводы и видео](GROUNDED_PROBE_RESULTS_20260911.md).
Ниже сохранён исходный план, его thresholds и выборки не менялись.

**Проверка запуска, 02:16 MSK:** smoke завершён, 48/48 ветвей прошли
integrity analysis. Основная серия автоматически началась на семи свободных
GPU. Локально декодированы все 48 видео, число кадров совпало с метаданными.
Подробности: [проверка запуска](campaigns/grounded_probe_20260911_v2/LAUNCH_VERIFIED.md).
Это технический допуск, не подтверждение улучшения SR.

Техническая поправка до обучения/rollout: первая подготовка остановлена
проверкой membership. Старый архив `accelerated` содержит320samples и
не совпадает с текущим manifest. Правильный архив
`perception_regrasp_heatmap_20260904__calibration` содержит все388samples,
membership совпадает точно, пропущенных NPZ нет. V2 меняет только путь
обучающих данных; seed, split, методы и критерии не меняются. Первая
остановка с нулём epochs/rollout и исходники сохранены отдельно.

## Почему именно эти эксперименты

Сильный контроль v2: full RGB regrasp35/48 против continue26/48. Новый
verifier30/48 проиграл ему; семь false-held соответствовали неподвижной
цели и движению захвата. Поэтому ближайший bottleneck: object correspondence,
цена физической пробы и выбор момента восстановления. Ещё один широкий
uncertainty/consensus sweep или обучение всего Cosmos не обоснованы.

Внешняя проверка перед исправлением мотивирована
[CRITIC](https://arxiv.org/abs/2305.11738), но это не её реплика и не
доказательство новой общей идеи self-correction. Для маски используем
[DeepLabv3](https://arxiv.org/abs/1706.05587) через существующий
[Torchvision ResNet50 implementation](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.segmentation.deeplabv3_resnet50.html).
Это известная архитектура, не новый segmentation backbone и не SAM2/CoTracker.
Научный вопрос: помогает ли привязка проверки к целевому предмету реально
выбирать полезное восстановление относительно сильного контроля?

## Три гипотезы

1. **H1, object correspondence:** маска целевого предмета уменьшает false-held
   при движении руки и улучшает итоговый SR относительно full regrasp.
2. **H2, действие и проверка:** неудача v2 могла быть вызвана не только gate,
   но и самой пробой. Контроль probe→always-regrasp отделяет отказ от
   восстановления от физического изменения исходного состояния.
3. **H3, timing:** восемь обычных policy actions и свежая локализация перед
   regrasp могут уменьшить вред преждевременного вмешательства. Это fixed-delay
   control с обновлённым trigger, не выученный event trigger.

## Маска и обучение

Отдельный DeepLabv3-ResNet50, восемь object channels, инициализация
COCO/VOC checkpoint из серверного cache. Cosmos, прежний RGB localizer и
regrasp primitive заморожены. Используем только 388 исторических calibration
RGB/mask samples; никаких новых terminal success/fail labels для обучения.
Ground-truth segmentation разрешена как обучающая разметка, **не online input**.

Split: stable hash `independent_group`, четыре fold; fold0 validation,
остальные train. Группы не пересекаются. Это отдельная проверка segmentation,
не тот же split, что у обучения прежнего локализатора. Входы нового head
приводятся из OpenGL RGB в OpenCV, где находятся GT masks. Вход Cosmos и
старого локализатора не меняется. Сохраняются hashes всех обучающих NPZ.

$$
L=L_{\mathrm{BCE},w}+L_{\mathrm{Dice}}+0.3L_{\mathrm{aux},w},
\qquad w=\min\!\left(30,\frac{N_{\rm background}}{\max(1,N_{\rm target})}\right).
$$

30 фиксированных epochs, AdamW lr=$10^{-4}$, batch12, seed20260911,
weight decay=$10^{-4}$, gradient clipping5. Сохраняем последний epoch,
не лучший checkpoint по новым rollout. Gate при mask probability≥0.8:
validation macro-IoU≥0.35 и macro-precision≥0.70. Если gate не пройден,
mask-arms пропускаются; остальные controls/timing/transfer выполняются.
Пороги после просмотра новых результатов не меняются.

Ограничение: calibration получена после retreat, где предмет лучше виден.
Качество на ней не гарантирует правильность маски при окклюзии захватом.
Поэтому нужен последующий реальный rollout, а не только segmentation IoU.

## Онлайн-проверка

В RGB до/после той же трёхшаговой пробы сегментируется target из task text.
Выбирается связная компонента маски в пределах40px от frozen localizer,
площадью12–2048px; маска перед пробой эродируется на один pixel.
Lucas–Kanade использует только object corners, окно7×7, два pyramid levels.
Концы треков тоже должны лежать в маске предмета после пробы.

Требуем ≥4 треков, retention≥0.5, forward/backward error≤1px,
median flow residual≤1.5px и расхождение flow с движением centroid≤2px.
Затем прежние геометрические условия `held` / `miss` / `unknown`.
Для `held` одновременно должны согласоваться с EEF и медианный flow,
и движение centroid маски. Малое число треков/невидимость не означает `held`.

$$
d_o=\operatorname{median}_{j\in\mathrm{valid\ target\ tracks}}(p_j'-p_j),
\qquad d_m=\operatorname{centroid}(M')-\operatorname{centroid}(M).
$$

Прежняя RGB confidence обязательна. Ни контакты, ни object poses из
симулятора в эти решения не поступают. Это набор проверяемых инженерных
ограничений, а не гарантия безопасности и не оценка epistemic uncertainty.

## Восемь сравнений

| Arm | Что исполняется |
|---|---|
| continue_h8 | K4/H8 без восстановления |
| physical_regrasp | Прежний полный RGB regrasp по trigger t72 |
| probe_only | Только подъём с закрытым gripper до3шагов, затем policy |
| probe_verify_repair | Прежний crop-flow verifier v2, repair только при miss |
| probe_always_regrasp | Та же проба, затем full regrasp независимо от verdict |
| mask_verify_miss | Новая object-mask проверка; repair только при miss |
| mask_verify_conservative | Новая проверка; пропустить repair только при held |
| delayed_regrasp_h8 | Если trigger t72 сработал: восемь обычных действий, свежие RGB/trigger, затем full regrasp при новом допуске |

Все реальные шаги probe, delay и regrasp остаются в бюджете280; rollback
после failed guard запрещён. Общий K4/H16 prefix доt72, K4/H8 suffix,
5 denoising steps, joint/parallel action/future/value. Это **не** AR a→s→v.
Delay использует q5 и продолжает с q6: случайный seed запроса не дублируется.
Другие branches начинают suffix сq5; согласование по порядковому номеру,
не абсолютному физическому t после разных interventions.

## Выборки и автономная очередь

Основные cells: x0.2/task2, x0.2/task5, y0.2/task9, y0.2/task2,
x0.1/task5, x0.1/task9. Init25–28 из прошлого анализа не используются;
старый conditional holdout29–32 также не открываем.

| Этап | Выборка | Ветвей максимум | Условие |
|---|---|---:|---|
| Segmentation | Исторические calibration groups | Отдельное обучение | Нет новых rollout labels |
| Smoke | 6cells ×init33 ×1seed ×8arms | 48 | Только технический допуск; не научная SR |
| Screen | 6cells ×init34–37 ×2seeds ×8arms | 384 | После integrity smoke |
| Confirmation | 6cells ×init38–45 ×2seeds ×до5arms | 480 | Один winner screen, frozen метод |
| Independent transfer | 6другихcells ×init34–37 ×2seeds ×3–4arms | 192 | Старые full/delayed controls всегда; mask winner только после PASS confirmation |

Итого **до1104 ветвей**, а не обещание заполнить все семь часов.
Если mask/primary gates отрицательны, объём уменьшается. Screen48states
содержит24init clusters, confirmation96states содержит48init clusters.
Это не384/480 независимых scenes. Seed repeats остаются в своих init groups.

Transfer cells: x0.1/task2, x0.2/task9, y0.1/task2, y0.1/task5,
y0.1/task9, y0.2/task5. Не пересекаются с cells основного screen.
Все init проверяются на отсутствие overlap с calibration. Cells и предметы
могли встречаться в прошлых исследованиях: не называем это полным unseen-task
benchmark. Transfer старого full/delayed запланирован независимо от H1,
не является скрытым продвижением проигравшего verifier.

## Метрики и решения

Primary: paired terminal SR против **physical_regrasp**. Secondary:
continue и probe_always. Per-cell SR, rescue/harm, query counts, physical
steps, drop/wrong-object proxies, masked verdict coverage. Drop proxy не
является official LIBERO-Safety violation.

Равный вес cells, bootstrap по init внутри cell, paired cluster sign test,
Holm по заранее выводимому семейству сравнений. Smoke scores исключительно
для проверки исполнения, не для утверждения выигрыша.

Из трёх candidates (`mask_verify_conservative`, `mask_verify_miss`, delayed)
отбирается один: gain≥5п.п. к full, gain>0 к continue, drop count≤full,
mean query count≤1.5×full. Для mask также gain>0 к probe_always,
не хуже legacy verifier и ≥4 skips на eligible states.
Среди прошедших максимум SR gain; при равенстве порядок выше фиксирован.
Это practical selection, не статистическое подтверждение на screen.

Confirmation: primary CI_low>0, Holm p≤0.05, drop count не выше full.
Только такой mask winner идёт на новые transfer cells. Отсутствие winner
останавливает confirmation, но **не** заранее запланированный transfer
старых recovery/timing controls. Никаких новых thresholds по holdout.

Сохраняются prefix snapshots и inputs, фактические actions, query metrics,
probe RGB/masks, per-step simulator diagnostics и видео обеих камер отt72
до terminal. GT diagnostics только для post-hoc аудита; не подмешиваются в
mask/trigger/policy. Анализ, CSV, графики и HTML-видео создаются автоматически
после каждой полной стадии. Технические ошибки не записываются как policy fail.

## Ресурсы и команды

До7worker, кандидаты GPU0–7, только незанятые: две проверки utilization,
memory и отсутствие чужого CUDA PID. GPU4 на первой проверке занята и
пропускается. Общая очередь: занятая карта не удерживает задания.
На одну GPU один наш worker, без изменения чужих процессов.
Обучение сначала на одной idle GPU, затем rollout fan-out.
Worker переиспользует модели для batch из нескольких states.

Диспетчер отвязан от SSH; сохранённые ветви не пересчитываются. Одна
автоматическая повторная попытка batch, после повторной ошибки остановка
с логом. При deadline не начинаются новые branches, SIGTERM завершает текущую
ветвь; при зависании только собственный worker завершается принудительно
через120с. Поэтому аварийное освобождение может занять до двух минут.

Статус из WSL:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_grounded_probe.py --status'
```

Серверный запуск/продолжение из корня проекта:

```bash
.venv-cosmos/bin/python scripts/run_grounded_probe.py --launch
```

Повторный launch не продлевает deadline. Прогресс, активные GPU/PID и грубая
верхняя ETA записываются в `sequence_status.json`; она включает ещё условный
holdout и может переоценивать время. Это очередь с проверками, а не гарантия
безошибочной семичасовой работы или положительного научного результата.

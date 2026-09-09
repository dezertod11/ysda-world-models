# Perception-backed regrasp: accelerated sequential protocol

Дата фиксации: 4 сентября 2026 года, до просмотра новых terminal outcomes.

## Гипотеза

На 80 exact states, где обе исходные ветки Cosmos Policy завершились fail,
privileged regrasp с истинной 3D-позицией объекта дал 62/80 rescue. Проверяется,
какая доля этого opportunity сохраняется, если target pose заменить на
наблюдаемый RGB pipeline.

Deployment-вход локализатора ограничен:

- task language, определяющий target object;
- текущий `agentview` RGB;
- известная калибровка камеры.

Simulator pose, segmentation и contact labels разрешены только при создании
development supervision и оценке, но не поступают в frozen localizer во время
rollout.

RGB localizer всегда получает **raw** `obs["agentview_image"]`: его pixel
coordinates должны находиться в той же ориентации, что MuJoCo intrinsic и
camera-to-world matrices. Вертикальный flip применяется отдельно только в
Cosmos preprocessing и не является входом localizer.

## RGB localizer и быстрый model selection

Первый кандидат использовал frozen CLIP ViT-B/16 patch embeddings, их
96-мерную фиксированную проекцию и object-specific weighted ridge для target
mask. Центр задавался spatial softmax:

$$
p_i = \frac{\exp(\hat m_i / \tau)}{\sum_j \exp(\hat m_j / \tau)},
\qquad
(\hat u,\hat v)=\sum_i p_i(u_i,v_i).
$$

На grouped OOF этот вариант не прошёл gate: median/p90 pixel error составили
`8.47/41.65 px`, а median/p90 world-XY error -- `6.70/19.86 cm`. Основной
failure mode -- ложная локализация похожей упаковки или области около gripper.

Второй, текущий кандидат -- pretrained DeepLabV3-ResNet50 с восемью
object-conditioned spatial heatmap heads. Для target object $o$ обучается
пространственное распределение

$$
p_o(u,v\mid I)=\operatorname{softmax}_{u,v} h_o(I)_{u,v},
\qquad
\mathcal L_{xy}=-\log p_o(u^*,v^*\mid I).
$$

Отдельный head по global pooled visual feature предсказывает высоту $z$; OOF
выбирает между neural depth и консервативной object-median depth. В 15-epoch
single-fold prototype heatmap дал median/p90 `2.24/4.00 px`, max `19.85 px`.
Это только development-сигнал, поэтому production-решение принимается по трём
grouped folds и затем замораживается.

Первый strict three-fold heatmap fit подтвердил 2D (`median/p90 = 2.24/4.12
px`) и хороший Z (`p90 = 1.93 cm`), но честно остановился: `p90 world-XY =
5.574 cm`, на `0.074 cm` выше frozen gate. Попытка заменить global depth на
local depth map ухудшила Z и также была остановлена. До terminal outcomes эти
две итерации не дошли.

Текущая последняя development-итерация сохраняет global depth и добавляет
cross-fitted metric calibrator. Его признаки -- raw global/local depth,
координата heatmap, квадратичные взаимодействия и object identity. Для каждого
held-out fold ridge обучается только на двух остальных folds:

$$
\hat z_i = \operatorname{clip}\!\left(
\mathbf w_{-f(i)}^\top\phi(\hat z_i^{g},\hat z_i^{l},\hat u_i,\hat v_i,o_i),
z_{\min},z_{\max}\right).
$$

Ridge regularization и depth mode выбираются по cross-fitted `p90 world-XY`;
gate не меняется.

Финальный вариант маршрутизирует depth estimator по известному из language
target object. Для каждого объекта выбирается минимальный OOF p90 world-XY
сначала среди вариантов, прошедших p90-Z gate, либо среди всех вариантов, если
ни один его не прошёл. Это снизило aggregate median/p90 XY до `1.64/3.33 cm`,
p90 Z до `1.62 cm`, worst-object median до `2.55 cm`; offline gate пройден.

Strict calibration manifest содержит все 388 доступных строк из 194 групп и
16 Position/task cells. Из него исключены **целые `task/init_state` группы**,
встречающиеся как в 80-state development, так и в 109-state confirmatory
reserve; row- и group-overlap равны нулю. Segmentation и object pose нужны
только как train labels и не входят в rollout inference.

## Recovery controller

После общего восьмишагового prefix контроллер:

1. отводит end effector вверх с открытием gripper;
2. один раз локализует названный target по RGB;
3. подходит над оценённой позицией, опускается, закрывает gripper и поднимает;
4. возвращает управление неизменённому `K=4`, `argmax(value)`, H8 Cosmos
   continuation.

Таким образом меняется только recovery primitive. Checkpoint, stochastic seeds,
world-model sampling и downstream planning остаются теми же, что в privileged
upper-bound experiment.

## Последовательные gates

| Этап | Размер | Gate | При fail |
|---|---:|---|---|
| RGB grouped OOF | 388 images, 3 folds | median XY <= 2.5 cm; p90 <= 5.5 cm; p90 Z <= 6 cm; worst object median <= 4 cm | не запускать Cosmos |
| terminal screen | 20 exact states | SR >= 20%, >=3 cells/tasks, strict replay >=95%, drop delta <=5 pp | остановить P3 |
| development | 80 exact states | SR >=10%, bootstrap lower >0, >=4 cells, >=3 tasks, side-effect gates | не вскрывать reserve |
| confirmatory primary | 72 exact states / 47 новых task-init групп | тот же frozen model/controller; primary rescue SR and cluster CI | зафиксировать итог P3 |

Исходный 109-row reserve пересекается с development по 37 `task/init_state`
группам. До просмотра confirmatory outcomes первичным зафиксирован его strict
group-disjoint subset из 72 строк; результат на всех 109 допускается только как
sensitivity-анализ.

На screening/development/holdout видео отключены: это уменьшает NFS traffic и
не влияет на численные endpoints. После результата записываются только заранее
выбранные mechanism replays.

Clean 20-state screen после исправления raw-camera contract дал `11/20 = 55%`
(bootstrap CI `[35%; 75%]`), 6 rescued cells, 4 tasks, strict replay 100%, drop
delta -5 п.п. и safety delta 0. Screen gate пройден. Full development дал
`49/80 = 61.25%`, init-cluster CI `[50.62%; 71.43%]`, 6 cells / 4 tasks,
strict replay 100% и нулевые drop/safety deltas. Development gate пройден;
после него впервые был открыт strict group-disjoint reserve72.

Confirmatory reserve затем завершился с `43/72 = 59.72%`, init-cluster CI
`[45.20%; 73.91%]`, 11 rescued cells / 8 tasks и 100% strict replay. Drop delta
равен -1.39 п.п., official safety delta -- 0; formal gate **PASS**. Отдельный
диагностический wrong-object rate вырос на 20.83 п.п., поэтому следующий этап
должен добавить observable trigger/shield и проверить его на новых полных
эпизодах, не донастраивая текущий reserve.

## Compute и ускорение

Калибровка не загружает Cosmos и параллелится по трём свободным H100. Каждый
rollout process загружает Cosmos один раз и последовательно обрабатывает свою
очередь состояний. Массовые MP4 не пишутся. Ожидаемый wall time при GPU 3,6,7:

- RGB calibration: около 10-15 минут;
- три OOF fold параллельно + full fit: около 10-15 минут;
- 20-state terminal screen: ориентировочно 20-45 минут;
- development и reserve запускаются только после PASS.

Фактический clean run оказался быстрее оценки: screen20 занял 8.2 минуты,
development80 -- 26.6 минуты, strict reserve72 -- 39.0 минут. Последовательная
дорогая часть после frozen artifact завершилась примерно за 74 минуты. Такой
funnel позволяет дешёво закрывать слабые методы на offline/screen gate и
тратить полный rollout budget только на прошедшие варианты.

Команда полностью resumable; каждый следующий дорогой этап запускается только
при прохождении предыдущего gate:

```bash
GPU_LIST=3,6,7 \
RUN_BASE=perception_regrasp_heatmap_20260904 \
scripts/run_perception_regrasp_accelerated_sequence.sh
```

Статус:

```bash
scripts/mlspace_experiment_status.sh perception_regrasp_heatmap_20260904 --verbose
```

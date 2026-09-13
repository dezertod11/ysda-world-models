# Recovery: продолжение серии и диагностика зрительного наведения

Дата: 13 сентября 2026. Основание: [предварительные результаты](RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md)
и явный запрос продолжить и запустить проверки. Это протокол запуска,
не утверждение о полученном положительном эффекте.

[Проверка фактического запуска в12:35MSK](campaigns/recovery_grounding_diagnostic_20260913/LAUNCH_VERIFIED.md):
geometry32/32, replay2/2прошли, oracle workers активны. Основной main507/512
сохранённых исходов на этот момент. Это срез прогресса, не финальный отчёт.

## 1. Что запускается

| Серия | Задача | Объём |
|---|---|---:|
| Frozen recovery confirmation | Досчитать прежние main comparisons без смены seeds/метода | На момент решения оставалась 71 ветвь из 512 |
| Та же frozen серия, timing | Проверить чувствительность recovery к t56/t88 | До 768 ветвей |
| Grounding geometry | Проверить target projection, RGB orientation, XY и plane errors в обеих камерах | 32 сохранённых prefix |
| Grounding replay smoke | Точное воспроизведение двух исходных RGB recovery | 2 контроля, входят в 128 ниже |
| Grounding oracle | Разделить ошибки XY, высоты и допуска к recovery | 32 случая x 4 arms = 128 исходов |
| Event shadow smoke | Проверить, что новый monitor не меняет действия при отключённых вмешательствах | 2 случая x none/shadow = 4 полных rollout |

Grounding очередь: **geometry -> smoke -> oracle -> shadow**, с остановкой
при ошибке проверки. Нет автоматического обучения, подбора порогов по SR
или открытия независимого holdout. Новый широкий event-controller SR run
не запускается до разбора диагностики.

## 2. Ресурсы и сохранность данных

Обе очереди имеют общий cutoff **13 сентября, 21:12:40 MSK**. Это максимум
нового девятичасового окна, не обещанное время завершения всех задач.
Возобновлённая основная очередь стартовала в12:15MSK, диагностика в12:26MSK.
До пяти workers у основной очереди и до двух у диагностической; обе используют
одни GPU claim locks и допускают только GPU без compute-процессов после двух
idle readings. На старте свободны0,1,2,3,6,7; чужие4,5 не занимались.
Если свободных GPU нет, очередь ждёт до своего deadline; она не убивает
чужие процессы и не продлевает время автоматически.

На первой попытке resume возник `OSError(28, No space left on device)` при
записи dispatcher status. На NFS при этом df показывал около402GiB свободного
места; двенадцать последующих write/fsync probes по1MiB прошли. Добавлен
ограниченный retry записи статуса: до3повторов с паузой5с только дляENOSPC.
Это не доказательство причины старой ночной остановки или исправления NFS
на уровне сервера. Повтор запуска **сохранил первоначальный новый deadline**.
Ничьи файлы и результаты для освобождения места не удалялись.

Научный `config.json` основной серии и её frozen collector не изменены;
изменение resource-only: worker cap и новый бюджет. Старые budget/status/launch
сохранены в `recovery_confirmation_20260913/resource_resumes/`.
Готовые исходы пропускаются с проверкой hashes; незавершённые не считаются fail.
Первоначальная ETA старого dispatcher после resume включает старые завершённые
ветви и может быть слишком оптимистичной: ориентироваться на фактический
прирост завершённых cases и cutoff, а не на первые минуты этой ETA.

## 3. Выборка и архитектура

LIBERO-PRO Position perturbations Object suite, те же16cells, init25и26
в каждой. **Все32случая включены независимо от success/fail, ошибки локализации
и решения gate.** Это постфактум механизм-анализ уже исследованной выборки,
не новый untouched holdout и не общий benchmark score.

Восстанавливается тот же полный MuJoCo/runtime snapshot вt72, прежняя команда,
общий H16 prefix, исходный rollout seed. Frozen Cosmos, K4 max-value,
joint/parallel action/future/value, пять denoising steps, generate16/execute8
после вмешательства, общий лимит280физических действий. Шум suffix query:
`rollout_seed + query * 1000 + candidate_index`, первый suffix query=5.

**t72 здесь только исторический paired diagnostic boundary.** Его не
используют как универсальный trigger нового event метода. Чтобы измерить
вклад координат, timing и primitive в этой ablation намеренно фиксированы.

## 4. Диагностика геометрии

Для именованного target из сохранённого observation:

$$
u^{GT}=\pi(K,T,p^{GT}),\qquad
e_{pixel}=\|\hat u^{RGB}-u^{GT}\|_2,
$$

$$
\hat p=\operatorname{RayPlane}(K,T,\hat u^{RGB},\hat z),\qquad
e_{XY}=\|\hat p_{xy}-p^{GT}_{xy}\|_2.
$$

Отдельно вычисляется XY-error при истинной высоте цели, ошибка повторного
восстановления сохранённой world point, roundtrip GT projection, расхождение
свежего render с native и flipped observation. Сегментация simulator используется
только offline: видимость цели и расстояние предсказанного pixel до target mask.
Сохраняются иллюстрации external/wrist камер с GT и RGB точками.

Малая ошибка алгебраического roundtrip сама по себе не доказывает правильную
семантическую локализацию или ориентацию изображения: для этого нужны остальные
измерения и визуализация. Центр объекта может отличаться от центра видимой mask.

## 5. Oracle arms: раздельные причинные вопросы

| Arm | Waypoint после общего retreat | Initial / post-retreat gate |
|---|---|---|
| `rgb_replay` | Прежняя RGB-оценка | Прежний RGB gate |
| `oracle_xy_fixed_gate` | GT XY; прежний RGB Z | Тот же RGB gate |
| `oracle_xyz_fixed_gate` | GT XYZ | Тот же RGB gate |
| `oracle_xyz_physical_gate` | GT XYZ | Отдельный GT physical-workspace/miss/reach gate; confidence принудительно проходит |

В fixed-gate вариантах confidence и geometry gate после retreat вычисляются
по **исходному RGB-выходу**, а не по подставленным истинным координатам.
Истинная цель берётся по именованному ключу observation, не по индексу массива.
Используется исходный `_run_perception_regrasp`, без новой формы servo primitive:
3 retreat/open +7 approach +6 descend +4 close +5 lift, с прежним early success.

Дополнительно у GT waypoints есть явный physical bounding-box veto; такие
случаи учитываются в `waypoint_safety_block`, а не скрываются. Поэтому точное
прочтение контраста: подстановка координат при прежнем RGB допуске и отдельном
физическом ограничении допустимых waypoint. GT gate arm меняет также coverage,
его преимущество нельзя целиком приписывать лучшим координатам.

**GT arms не deployable методы.** Они используют privileged simulator pose
online намеренно и маркируются `simulator_labels_online=true`, `diagnostic_only=true`.
Ни один их SR не переносится в основную таблицу предложенного метода.

Предварительно заданные описательные contrasts:
1. GT XY fixed gate минус RGB: ограничение XY-наведения.
2. GT XYZ fixed gate минус GT XY fixed gate: роль высоты/плоскости.
3. GT XYZ physical gate минус GT XYZ fixed gate: роль eligibility/coverage.

Отчёт даёт micro SR по cohort, paired rescue/harm, число полных recovery,
физических veto и шагов primitive. Только полные четырёхсторонние cases;
частичные исходы сохранены, но не смешиваются в matched-таблице.
Не заявляем confirmatory p-values для этого exploratory pilot.

## 6. Технические gates и последующее решение

Перед oracle проверяются два smoke replay: familiarx0.2/task5/init25 и
transferx0.3/task1/init25. В каждом требуется совпадение всех executed actions
с исходным physical arm до1e-6, final simulator state до1e-8 и terminal label.
Такой replay проверяется и для каждого следующего `rgb_replay`.
Ошибка останавливает очередь, а не превращается в отрицательный SR.

Event smoke использует **новую** независимую от частоты query seed-схему
`rollout_seed + physical_action_index * 1000 + candidate_index`. Поэтому его
сравнивают с парным новым `none` control, а не с исходным frozen H16 rollout.
Требуются побитово одинаковые actions, одинаковый outcome, ноль исполненных
вмешательств вshadow. Предложенные monitor события лишь логируются.
Пороги пока smoke/uncalibrated; положительный SR этим опытом не проверяется.

Если координаты исправляют failures, следующий development этап: переносимый
object-grounded localizer/two-view evidence и память локализаций. Если GT
координат мало, разделять phase/contact/primitive и coverage. Далее отдельно
проверять event timing и release veto при фиксированном зрительном модуле.
Не изменять метод в середине текущего matched сравнения.

## 7. Где смотреть

- Основная серия: `experiments/campaigns/recovery_confirmation_20260913/`;
  `sequence_status.json`, `resume_launch.json`, `analysis/main/`, `analysis/timing/`.
- Диагностика: `experiments/campaigns/recovery_grounding_diagnostic_20260913/`;
  `sequence_status.json`, `geometry/`, `rollouts/`, `shadow/`, `analysis/`.
- В `analysis/` диагностики автоматически появляются `geometry.csv`,
  `matched_outcomes.csv`, `scores.csv`, `paired_descriptive.csv`,
  `oracle_diagnostic_sr.png`, `RESULTS.md`, `summary.json`, `videos.html`.
- Oracle videos содержат обе камеры и весь префикс сt0, не только suffix.

Из WSL, фактический статус диагностической очереди:

```bash
ssh mlspace-sr006 \
  /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python \
  /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_recovery_grounding_diagnostic.py --status
```

Для основной серии заменить имя скрипта на `run_recovery_confirmation.py`.
PID и время обновления обязательны для интерпретации статуса.

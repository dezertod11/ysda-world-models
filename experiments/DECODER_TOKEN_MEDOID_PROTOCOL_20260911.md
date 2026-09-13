# Decoder action-token medoid: перенос GR00T/MIMIC на Cosmos Policy

Дата: 11 сентября 2026. Dispatcher запущен в 21:35 MSK и после проверки
синхронизации перезапущен в 21:41 MSK; текущий PID1467069;
он ждёт завершения `observation_contract_20260911`, основные 720 rollout
пока не начались. Локальные capture и четыре full-rollout проверки прошли.
[Акт проверки запуска](campaigns/decoder_token_medoid_20260911/LAUNCH_VERIFIED.md).
Локальная копия состояния очереди (живое состояние проверять через SSH):
[`sequence_status.json`](campaigns/decoder_token_medoid_20260911/sequence_status.json).

## 1. Какой метод найден

Изучен [Robotics_project_YSDA](https://github.com/Doub1e05/Robotics_project_YSDA),
зафиксирован commit `f1bb8d6221a7ee22bd34a72ec642cac244b4f89b`.
Последний commit от 10 сентября добавляет benchmark runners и интервалы;
собственно decoder-token selectors добавлены 7 сентября (`50b5f38`).

Выбран **decoder action-token medoid**: K=3 stochastic candidates,
попарное косинусное расстояние между выровненными скрытыми action-токенами
последнего блока декодера, первые четыре временные позиции с весом 4,
остальные с весом 1. Выполняется один исходный кандидат-медоид;
усреднения действий, value penalty, обучения scorer и simulator oracle нет.

Первичные источники, закреплённые на проверенной ревизии:

- [Результаты и ограничения](https://github.com/Doub1e05/Robotics_project_YSDA/blob/f1bb8d6221a7ee22bd34a72ec642cac244b4f89b/docs/RESULTS.md).
- [GR00T selector](https://github.com/Doub1e05/Robotics_project_YSDA/blob/f1bb8d6221a7ee22bd34a72ec642cac244b4f89b/scripts/eval/groot_n17_decoder_action_token_medoid_server.py).
- [MIMIC LIBERO selector](https://github.com/Doub1e05/Robotics_project_YSDA/blob/f1bb8d6221a7ee22bd34a72ec642cac244b4f89b/eval/libero/run.py).

Исходные файлы, Apache-2.0 LICENSE и компактные JSON-результаты архивируются
в `campaigns/decoder_token_medoid_20260911/reference/`; SHA256 записаны в config.
Внешний checkout изолирован в игнорируемой `.external/Robotics_project_YSDA`.
Его исполняемые скрипты не запускались, окружение GR00T/MIMIC не устанавливалось.

### Что означает «последний лучший»

Это последний перспективный representation-based вариант, **не устойчиво
лучший метод на всех задачах и seeds**. Проверены суммы непосредственно
в upstream `eval_outputs/simpler_bridge/**/summary.json`:

| GR00T, SIMPLER Bridge | K1 baseline | Decoder medoid K3 | Разница |
| --- | ---: | ---: | ---: |
| seeds 1,999,998; baseline seed 1 | 49/96 = 51.04% | 66/96 = 68.75% | +17.71 п.п. |
| seeds 2,997,996; baseline seed 2 | 51/96 = 53.13% | 46/96 = 47.92% | -5.21 п.п. |
| seeds 3,995,994; baseline seed 3 | 50/96 = 52.08% | 51/96 = 53.13% | +1.04 п.п. |

Четыре задачи WidowX: carrot on plate, spoon on towel, stack cube,
eggplant in basket; по 24 эпизода, execution horizon=4, максимум 300 шагов.
У MIMIC на SIMPLER другой seed pool для token-medoid дал 42/96 против
45/96 у приведённого baseline; pools различаются, это не чистая парная оценка.
GR00T token-medoid на обычном LIBERO Spatial дал 100/100, но соответствующего
K1 reference рядом нет: нельзя объявлять это подтверждённым улучшением.
Для LIBERO-PRO опубликованное сравнение относится пока к action-space medoid,
а не к новому token selector. Не переносим его SR на другую методику.

### Связь с нашими исследованиями

Семейство consensus/medoid уже проверялось в P4c и последующем сравнении
OSC, raw, KeyStone-style, KDPE. Убедительного переносимого выигрыша не было:
[1194 rollout, valid199](CONSENSUS_AND_P5_RESULTS_20260910.md).
Однако **медоид скрытых action-представлений последнего блока** там не
исполнялся. Это новая representation-ablation внутри consensus-направления,
а не P5 critic, не продолжение hand-coded regrasp и не новый обученный planner.
Алгоритмическая идея принадлежит источнику; наша работа здесь есть адаптация
к архитектуре Cosmos и проверка переноса, а не заявка на новизну медоида.

## 2. Исходная формула

Пусть $h_{i,t}$ есть скрытый action-токен кандидата $i$ на позиции $t$.

$$
\alpha_t=\begin{cases}4,&0\le t<4,\\1,&4\le t<T,\end{cases}
\qquad
d(i,j)=\frac{\sum_t\alpha_t\,[1-\cos(h_{i,t},h_{j,t})]}{\sum_t\alpha_t}.
$$

$$
C_i=\frac{1}{K-1}\sum_{j\ne i}d(i,j),
\qquad i^*=\arg\min_i C_i,\qquad K=3.
$$

Нормы ограничены снизу $10^{-12}$; cosine ограничен в [-1,1]; диагональ
distance matrix равна нулю; при точном равенстве выбирается первый индекс.
GR00T сравнивает весь generated action-token horizon, хотя выполняет H4.
MIMIC берёт action-токены после observation-prefix из блока 23 и обрезает
до выполняемого prefix (обычно H5). Эти реализации не полностью идентичны.

## 3. Почему Cosmos требует адаптации

В LIBERO-конфигурации Cosmos Policy нет отдельного action-токена на каждый
шаг. Последовательность из девяти latent-кадров:

`blank, current proprio, wrist RGB, external RGB, ACTION, future proprio, future wrist, future external, value`.

Actions извлекаются из кадра index=4 формы [16,28,28]: flatten в порядке
**C,H,W**, 112 копий блока [16 действий,7 координат], затем среднее по копиям.
Последний DiT-блок имеет номер 27, hidden grid [1,9,14,14,2048]; spatial patch
2x2, temporal patch 1. Используем только action slice: [196,2048] на candidate.

**Нельзя назвать первые четыре spatial patches первыми четырьмя действиями.**
Один patch через output head влияет сразу на несколько action-times.
Определим для выходного элемента $(c,h,w)$:

$$
r=(c\,H+h)W+w,\qquad
\tau(r)=\left\lfloor\frac{r\bmod(16\cdot7)}7\right\rfloor,
\qquad p(h,w)=\left\lfloor h/2\right\rfloor(W/2)+\left\lfloor w/2\right\rfloor.
$$

$$
N_{p,t}=\#\{(c,h,w):p(h,w)=p,\ \tau(r)=t\},
\quad w_p=\sum_t N_{p,t}\alpha_t,
\quad d_C(i,j)=\frac{\sum_p w_p[1-\cos(h_{i,p},h_{j,p})]}{\sum_p w_p}.
$$

Медоид выбирается по той же формуле $C_i$. Это перенос временных весов
через фактическую раскладку декодера, **не точное восстановление скрытого
токена каждого действия**. Внутри patch времена смешаны. Произвольная
нумерация spatial patches как action-times не используется.

Hidden снимается перед `final_layer`, в **последнем conditional forward
денойзера**, как последний вызов hook в исходном GR00T. Это не усреднение
по пяти diffusion steps и не дополнительный forward при нулевом noise.
Hook не изменяет tensors, не использует RNG, не добавляет модельных вызовов.
CFG/unconditional branch, temporal patches >1 и context parallel запрещены
явными проверками до inference; иначе последний captured branch неоднозначен.

Без дополнительных rollout сохраняются diagnostic choices для uniform
patch weights и first-eight action-prefix. Они не объявляются испытанными
closed-loop стратегиями по результатам чужой траектории.

## 4. Замороженный эксперимент

В отличие от последних recovery-экспериментов, здесь **полные эпизоды с t=0**,
без вмешательства в t=72, privileged контроля захвата или hand-coded действий.

| Параметр | Значение |
| --- | --- |
| Модель | Cosmos-Policy-LIBERO-Predict2-2B, прежний frozen runtime |
| Input | Реальные external/wrist RGB + proprio + T5 task embedding на каждом query |
| Generated / executed chunk | 16 / 16 для всех стратегий |
| Denoising | 5 evaluations |
| Prediction mode | Parallel: action/future/value в одной генерации; не a->s->v AR |
| Candidate pool | K3, кроме логического K1 контроля |
| Candidate seeds | Все три upstream группы, без изменения на следующем query |
| Horizon | 280 выполняемых действий после 10 settle steps |
| Изменяемые факторы | Только selector; одинаковые init, инструкция, environment seed |
| Статус выборки | Development transfer, не новый untouched holdout |

| Фактор LIBERO-PRO | Конфигурации на метод |
| --- | ---: |
| Object: `libero_object_object`, 10 tasks x init 0,1 x 3 seed groups | 60 |
| Environment: `libero_object_env`, 10 tasks x init 0,1 x 3 seed groups | 60 |
| Position: `libero_object_temp`, x0.2/y0.2 x 10 tasks x init 0 x 3 seed groups | 60 |
| Всего | **180 на метод, 720 rollout** |

Environment: прежний `living_room_table`, seed генерации 20260908,
50 сохранённых init на задачу из `.runtime/trajectory_consensus_20260908_environment`.
Используются первые два, без регенерации. BDDL/init hashes всех факторов заморожены.
Это **не весь официальный LIBERO-PRO**: Position покрывает 2/10 уровней.

Четыре стратегии:

1. `first`: первый candidate соответствующей seed group, без выбора.
2. `max_value`: максимум совместно сгенерированного value среди K3.
3. `action_medoid`: прежний геометрический control, scoring prefix=5,
   gamma=.9, translation/rotation/gripper weights=1/.5/.25; выполняется H16.
4. `decoder_medoid`: формула выше, all generated actions, первые четыре x4.

K3 отличается от нашего прежнего K4 benchmark намеренно, вслед за источником.
Все controls пересчитываются; старые K4/H16 scores не используются вместо
новых парных результатов. H16 сохраняет наш execution contract, но отличается
от GR00T H4 и MIMIC H5. Поэтому вывод будет о переносе selector при H16.

Первый K3 pool сохраняется **один раз** и используется всеми четырьмя arms.
Текущее начальное наблюдение и полный runtime snapshot также общие. Далее
при расхождении действий observations различаются естественно: одинаковые
seed labels не означают одинаковые состояния или pools на q>0.
K1 получает только первого кандидата; общий q0 K3 есть технический overhead
paired design. Logical call counts отделены от фактического instrumented
wall time. Последнее нельзя выдавать за производственный latency K1.

## 5. Проверки и статистика

Перед основным серверным сбором обязательны три smoke, по одному на фактор.
Для каждого K3 pool: запуск без hook, с hook, повторно с hook. Требуется
**побитовое равенство** actions, values, images, generated latents; совпадение
скрытых представлений и RNG states. Изменение capture-контракта останавливает
очередь, а не переключает её незаметно на action-medoid.

Локальный Object smoke уже прошёл: 5 captured forwards на candidate,
[3,196,2048] features, hidden/action/value/image/RNG parity. Восемь focused
tests проверяют source-formula equivalence, C,H,W mapping, weights, hook,
полноту сетки и статистический разбор. Локальный full-episode integration
сохраняется отдельно и **не включается** в 720 серверных rollout.

Основной estimand: decoder-medoid против max-value, равновзвешенный
macro-SR трёх факторов. Дополнительно per-factor, per-task, per-seed-group SR,
rescue/harm, время, logical candidate calls, query choices, disagreement с
контролями, safety/drop proxies. Bootstrap группирует task внутри фактора,
сохраняя связанные seeds/inits вместе. McNemar выводится только описательно:
повторные seeds нельзя считать полностью независимыми эпизодами.

В анализ включаются только полностью законченные пары всех четырёх arms;
missing/timeout самого worker не считаются policy fail. Политический fail
фиксируется при отсутствии simulator success к 280 действиям, с отдельными
диагностическими событиями. Это не самостоятельный LIBERO-Safety benchmark.

Prediction image/proprio errors считаются только после **полных 16 действий**.
При early success или последнем усечённом chunk horizon не совпадает с
predicted future, поэтому такое error-сравнение пропускается. Ошибка прогноза
по фактическому будущему и simulator labels никогда не участвуют в выборе.

## 6. Артефакты и автономный запуск

Основной каталог: `experiments/campaigns/decoder_token_medoid_20260911/`.

- `config.json`: frozen сетка, метод, provenance, hashes.
- `sequence_status.json`: стадия, активные GPU/PID, завершённые rollout, ETA.
- `smoke/`: технические проверки, отдельно от SR.
- `screen/<id>/`: initial snapshot, общий q0 pool, JSON/NPZ/MP4 четырёх arms.
- `analysis/REPORT.md`: автоматически построенный итоговый разбор.
- `analysis/success_rates.csv`, `paired_comparisons.csv`, `seed_group_rates.csv`.
- `analysis/queries.csv`, `success_rates.png`, первые 12 paired metric traces.
- `analysis/video_comparison.html`: четыре полных видео рядом на каждую пару.

Видео H264/yuv420p, обе камеры, 20 fps, кадры от t=0 до реального конца
эпизода включительно. Для fail на 280 шагах это 281 кадр, не 18 query frames.
Сохраняются реальные query inputs и actual future observations, candidate
actions/value/future images/proprio, costs/distance matrices и hidden hashes.
Полные hidden features и generated latents сохранены для q0; далее полные
hidden tensors не пишутся ради объёма данных.

Отдельный контроль интерпретации: в локальном integration decoder-medoid
выбирал candidate index 1 на всех десяти queries. Это **не доказательство
адаптивного выбора по наблюдению**: при фиксированных noise seeds возможен
устойчивый приоритет одного кандидата. Поэтому сохраняются q0 и per-episode
choice frequencies. Если это повторится на основной сетке, обязательный
следующий control есть K1 с каждым оставшимся фиксированным candidate seed;
нельзя приписывать весь gain интеллектуальной state-dependent селекции.

**Обновление 11 сентября: активный запуск переведён на
[ночной план до 10:00 MSK 12 сентября](DECODER_MEDOID_NIGHT_20260912.md).**
Исходная научная конфигурация 720 rollout не меняется; добавлены отдельные
seed/H8 controls. Ниже описан исходный механизм ресурсов, заменённый для
этой ночи абсолютным cutoff 09:40, максимумом 8 workers и watchdog.

Исходная очередь ждёт нормального `completed` или `partial` завершения текущей
Observation Contract без active workers. При её `failed` требуется разбор,
новая кампания не маскирует ошибку. Затем idle-only GPU admission 0-7,
до семи workers, общие `.runtime/grounded_gpu_claims` locks. Чужие процессы
не завершаются; занятая карта не блокирует свободные. Бюджет 24 часа начинается
при первом допуске на GPU, не во время ожидания предыдущего исследования.
Один автоматический retry; завершённые arms не пересчитываются при resume.

NFS2 почти заполнен. Результаты этой кампании лежат на свободном постоянном
томе `/home/jovyan/.local/share/malnev_world_model_spill/decoder_token_medoid_20260911`,
из канонического project path доступен symlink. Исходники и окружение остаются
в проекте. `.git`, SSH/HF/W&B секреты не передаются; HF offline, W&B offline.

Статус из WSL:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_decoder_token_medoid.py --status'
```

Для этой ночи повторно запускается **новый deadline dispatcher**:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/scripts/run_decoder_medoid_night.py --launch'
```

## 7. Решение после результата

Сначала сравнить все три seed groups, факторы и rescue/harm; не выбирать
единственный удачный pool, как будто он доказывает переносимость метода.
Без устойчивого эффекта не запускать новый coefficient sweep на этих labels.

Если есть воспроизводимый signal: заморозить вариант, проверить новые init,
новые независимые seeds и более широкий Position support; отдельно сравнить
H4/H8/H16 для **обоих** hidden-medoid и max-value, не смешивая selector gain
с эффектом частоты обратной связи. Следующие representation-ablation:
uniform versus decoder-time weights, score prefix versus full generated
horizon, скрытое представление versus предсказанный action latent.
Эти варианты пока диагностические/планируемые, а не подтверждённые результаты.

Если эффекта нет: проверить, есть ли вообще разные полезные candidates,
насколько скрытые cosine costs различимы, и не доминирует ли общая информация
об изображении. Отрицательный H16 transfer не опровергает GR00T H4 result;
он ограничивает перенос на Cosmos. Продолжение recovery/observation ветки
решается отдельно по её результатам; этот запуск не отменяет её эксперимент.

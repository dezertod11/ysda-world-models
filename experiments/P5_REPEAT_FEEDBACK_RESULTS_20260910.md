# P5: повторяемость кандидатов и ранняя обратная связь

**Дополнительная проверка реализации:** [Fresh8 audit: входы, K8->K1,
согласованность действий и разбор harms](FRESH8_IMPLEMENTATION_AUDIT_20260910.md).
Индексы и SR подтверждены. Здесь исходный чанк выбран из K8, но новый query
генерирует K1 без ranking; это не matched-K повтор прежнего K4/t72 метода.
21 CPU-тест прошёл. Исходные данные и collector не изменены.

Проверено 10 сентября 2026. Серия `p5_repeat_feedback_20260910`
**полностью завершилась в 04:32:38 MSK**, задолго до предельного времени.
После перехода на три worker: 3 ч 16 мин wall-clock; сумма времени основных
ветвей 8.95 worker-hours, без полной стоимости загрузок/replay. Это не время
работы CUDA-ядер. Процессов этой серии при проверке нет. Новые GPU-запуски
в рамках анализа не выполнялись.

## Главные выводы

1. **Более раннее свежее наблюдение не дало общего выигрыша:** fresh8 41/108
   против open16 44/108 и stale8 45/108. Не доказано и обратное утверждение,
   что свежие наблюдения в целом вредны: интервалы широкие и включают ноль.
2. **Одна terminal-метка недостаточна для оценки кандидата.** У 96/288
   сохранённых action chunks исход менялся между тремя suffix seeds.
   Начальное состояние и первые 16 действий при этом одинаковые.
3. **Внутривыборочный oracle сильно оптимистичен.** Выбор по среднему исходу
   тех же трёх повторов обещает K8 gain +14.81 п.п.; выбор по двум повторам
   с проверкой на третьем даёт ровно 0 п.п., 5 rescue / 5 harm.
4. Остались отдельные интересные ranking failures, особенно `pool_13`, но
   они ещё не обосновывают новый переносимый planner или обучение большого critic.

## 1. Постановка и целостность

[Замороженный протокол](P5_REPEAT_FEEDBACK_PROTOCOL_20260910.md): Cosmos Policy,
joint/parallel generation, пять denoising steps, сохранённые K8/H16 actions.
После тестируемого окна продолжение K1/H16 до абсолютного t=280.
Это не авторегрессионный planning `action -> state -> value`.

LIBERO-PRO **Object suite**: Object и Position x0.2/y0.2 perturbations,
36 снимков на q0/t0 и q3/t48. 18 case/task/init групп соответствуют
10 task/init кластерам. Environment и официальный LIBERO-Safety здесь
не использовались. Это development-выборка, не весь benchmark.

| Проверка | Результат |
| --- | ---: |
| Основные terminal branches | 1080/1080 |
| Повторы сохранённых действий: 36 x 8 x 3 | 864/864 |
| Fresh8 и stale8 выбранного кандидата | 108 + 108 |
| Smoke, исключены из статистики | 6/6 |
| SHA исходной таблицы, 36 sidecars и 11 скриптов | Совпали |
| Replay endpoints исходных восьмёрок | 288/288, максимальная ошибка 0 |
| NPZ: действия, длины, временное выравнивание, endpoints | 1080/1080 |
| Видео выбранных кандидатов на repeat=0 | 108/108 полностью декодированы |

Для всех видео проверены непустой кадр, движение и `frames = executed steps + 1`.
Видео q3 начинается на t=48, не на начале эпизода. Сохранены обе камеры,
а массив `frame_t` задаёт абсолютное время. Все mode имеют общий начальный
восьмишаговый prefix; исходный collector также проверял состояние после него.
Технические попытки до успешного smoke сохранены отдельно и не являются fail labels.

## 2. Полезно ли новое наблюдение?

| Режим | Что происходит в исходном H16 окне | Success | SR |
| --- | --- | ---: | ---: |
| open16 | Выполнить весь сохранённый max-value chunk | 44/108 | 40.74% |
| stale8 | После первых 8 действий пересемплировать по старому наблюдению, выполнить действия 8:16 | 45/108 | 41.67% |
| fresh8 | После первых 8 действий пересемплировать по новому наблюдению, выполнить действия 0:8 | 41/108 | 37.96% |

У fresh/stale одинаковый дополнительный query seed. После t+16 одинаковая
continuation policy и расписание suffix seeds по абсолютному времени.
Оба replacement используют K1, тогда как сохранённый исходный чанк выбран
из K8. Поэтому fresh-open включает смену candidate budget. Кроме того, stale
исполняет хвост, совместно сгенерированный с другим, неисполненным префиксом.
Контроль stale выровнен по времени, но имеет отличие head/tail предсказанного
chunk: результат не является чистым измерением абстрактной ценности информации.

$$
\Delta_{\mathrm{info}}=\mathbb E[Y_{\mathrm{fresh8}}-Y_{\mathrm{stale8}}],
\qquad
\Delta_{\mathrm{feedback}}=\mathbb E[Y_{\mathrm{fresh8}}-Y_{\mathrm{open16}}].
$$

| Сравнение | Разница SR, п.п. | 95% cluster CI, п.п. | Rescue / harm | Holm p |
| --- | ---: | --- | ---: | ---: |
| fresh8 - stale8, primary | -3.70 | [-20.51; +9.72] | 13 / 17 | 1.0 |
| fresh8 - open16, secondary | -2.78 | [-16.67; +9.17] | 13 / 16 | 1.0 |

Bootstrap и exact sign-flip сохраняют queries, repeats и perturbations
одного task/init в одном кластере. Независимых кластеров десять, не 108.
Основной анализ воспроизведён из raw JSON и совпал с серверным.

Fresh8 потребовал в среднем 13.71 continuation+extra queries против 12.87
для open16, без учёта общей стоимости генерации сохранённого K8 pool.
Дополнительная стоимость не окупилась общим приростом SR. Это сравнение
одного вмешательства, не полного контроллера, который всегда выполняет H8.

### Разрезы: только exploratory

| Срез | open16 | stale8 | fresh8 |
| --- | ---: | ---: | ---: |
| q0: вмешательство на t=8 | 21/54 (38.89%) | 21/54 (38.89%) | 24/54 (44.44%) |
| q3: вмешательство на t=56 | 23/54 (42.59%) | 24/54 (44.44%) | 17/54 (31.48%) |
| Object | 16/24 | 16/24 | 16/24 |
| Position | 28/84 | 29/84 | 25/84 |

На q3 fresh8 численно хуже open16 на 11.11 п.п.; 2 rescue / 8 harm.
На q0 лучше на 5.56 п.п.; 11 rescue / 8 harm. Это не подтверждённое
правило «перезапрашивать только на q0»: разрезы просмотрены post-hoc,
cluster sign-flip p равны 0.25 и 0.75 соответственно.

![Feedback по query](campaigns/p5_repeat_feedback_20260910/review_20260910/feedback_by_query.png)

## 3. Насколько стабильна метка кандидата?

Исполняем тот же $A_i$ из того же $s$, меняем только seed последующей policy:

$$
Y_{ir}=\mathbf 1\{\mathrm{goal\ reached\ by}\ t=280\mid s,A_i,\pi,\xi_r\},
\qquad \widehat Q_i=\frac13\sum_{r=1}^{3}Y_{ir}.
$$

| Successes / 3 suffix seeds | Кандидатов |
| --- | ---: |
| 0/3 | 136 |
| 1/3 | 53 |
| 2/3 | 43 |
| 3/3 | 56 |

96/288 = **33.33%** имеют меняющуюся метку. Из 864 новых labels 168
(19.44%) отличаются от исходного пилота. Это включает stochastic continuation
и остаточную численную невоспроизводимость; не измерение чистой epistemic uncertainty.

Из 17 исходных all-fail pools шесть дали хотя бы один success при новых
продолжениях; 11 остались all-fail по 8 x 3 проверенным веткам. Ни число 17,
ни 11 не доказывает необратимость состояния или отсутствие других хороших действий.

**Смысл:** terminal fail может возникнуть после правильного начального chunk.
Чтобы учить action-conditioned critic, нужны оценки вероятности исхода и
отдельные локальные contact/target labels, а не присвоение каждому chunk
свойства «неправильный» по одной дальнейшей траектории.

## 4. Проверка оптимизма при ранжировании

Внутривыборочная оценка:

$$
\widehat G_K=\frac1{|S|}\sum_s
\left[\max_{i<K}\widehat Q_i(s)-\widehat Q_{\arg\max_{i<K}V_i}(s)\right].
$$

Максимум выбирается и оценивается по одним outcomes. Поэтому добавлен
**post-hoc leave-one-suffix-out диагностический контроль**, не новая policy:

$$
i_{-r}(s)=\arg\max_i\frac12\sum_{r'\ne r}Y_{ir'}(s),\qquad
\widehat J_{\rm split}=\frac1{3|S|}\sum_{s,r}Y_{i_{-r}(s),r}(s).
$$

При равенстве train-оценок выбираем больший исходный value, затем меньший
index. Test-исход не участвует в выборе. Все три folds используются;
для CI зависимые folds, queries и варианты остаются в task/init кластере.
Это проверка переноса между suffix seeds **того же состояния**, не на новые задачи.

| Выбор | K4, первые четыре исходных кандидата | K8 |
| --- | ---: | ---: |
| Max-value | 43/108 (39.81%) | 44/108 (40.74%) |
| Uniform random, точное среднее outcomes | 36.34% | 35.53% |
| Лучший по тем же трём повторам, оптимистично | 53.70% | 55.56% |
| Выбор по двум, проверка на третьем | 47/108 (43.52%) | 44/108 (40.74%) |
| Split-effect против max-value, п.п. | +3.70 | 0.00 |
| 95% cluster CI split-effect, п.п. | [-3.70; +11.11] | [-5.95; +6.86] |
| Rescue / harm | 6 / 2 | 5 / 5 |

K8 «+14.81 п.п.» по тем же данным исчезает при split. **Нельзя выдавать
этот oracle за достигнутый improvement planner.** Но split с двумя train
повторами сам шумный: нулевой результат не доказывает отсутствие обучаемого
ranking signal с большим числом repeats и хорошими признаками.

Value ранжирует 61.94% из 381 сравнимых candidate pairs в согласии с
трёхповторной оценкой Q. Это описательная concordance, не accuracy на
381 независимых примерах и не калибровка value как вероятности успеха.

![Шум labels и проверка selection](campaigns/p5_repeat_feedback_20260910/review_20260910/suffix_noise_and_selection.png)

### Конкретные случаи для следующей проверки

- `pool_13`: Position x0.2 / task2 / init7 / q3, команда
  `pick up the salad dressing and place it in the basket`.
  Max-value candidate4: **0/3**; candidates3 и5: **3/3**.
  Fresh/stale выбранного candidate4 тоже 0/3. Самый ясный локальный пример
  недостаточного ranking, но найден на development и требует новых repeats/init.
- `pool_11`: Position x0.2 / task0 / init8 / q3, alphabet soup.
  Max-value candidate7: **1/3**; candidate6: **3/3**. Ещё один полезный контроль.
- Старый единственный K8 rescue, `pool_34`, больше не выглядит устойчивым:
  max-value candidate0: 0/3, лучший alternative лишь 1/3. Исправление этого
  одиночного пилотного примера не стоит делать главным научным результатом.

Для alternative candidates сохранены actions и outcomes, но **новые видео
записывались только для max-value candidate** каждого режима на repeat0.
Не выдаём видео selected-кандидата за видео candidates3/5/6.

## 5. Fail и безопасность

| Автоматический тип terminal outcome | open16 | stale8 | fresh8 |
| --- | ---: | ---: | ---: |
| Success | 44 | 45 | 41 |
| Timeout без выделенного события | 45 | 49 | 44 |
| Target-drop candidate | 10 | 5 | 10 |
| Kinematic-deadlock candidate | 5 | 7 | 9 |
| Wrong-object candidate | 4 | 2 | 4 |

Типы являются эвристикой tracker, не ручной причинной аннотацией всех видео.
Wrong-object proxy может встречаться и вне выбранного terminal failure type.
Timeout означает отсутствие выполненного goal к t=280; не доказывает
«роботу просто не хватило времени». Отдельные drop/deadlock события показывают,
почему сводить всё к timeout было бы неверно. Это не LIBERO-Safety score.

## 6. Решение и следующий приоритет

**Не продвигать** always-early fresh8 как улучшенный метод по этим данным;
**не начинать** большой sweep scalar risk/value коэффициентов и fit P5 по
единичным terminal labels. Сохраняем max-value как содержательный baseline.

1. Маленький frozen repeat-check двух случаев выше: max-value против явно
   отличающихся candidates, 10 новых suffix seeds и соседние untouched init.
   Заранее сохранить все candidates, не выбирать победителя по test outcomes.
2. Разделить local chunk consequence и terminal suffix: контакт с нужным
   предметом, grasp/lift, прогресс до target, затем более поздний исход.
   Ground-truth geometry допустима для diagnostic labels, не как скрытый online input.
3. Если устойчивые candidate advantages подтвердятся, сравнить компактный
   action-conditioned scorer с value, state-only и shuffled-action controls;
   обучать на вероятностных labels, проверять на целых новых task/init/cells.
4. Для 11 all-fail pools проверить изменение proposals/grounding или адресный
   recovery. Наш подтверждённый узкий P3c recovery остаётся более сильным
   положительным результатом, чем reranking или always-requery. Перенос всё
   ещё нужен; новые команды должны сохранять смысл задачи и реально менять embedding.

Это план, а не запущенные новые эксперименты. Для статьи полезная история:
**неопределённость исхода, candidate coverage и полезность вмешательства
различны; одно не заменяет другое**. Нового общего SOTA controller не получено.

## Артефакты и воспроизведение

- [Все 108 видео: три режима рядом](campaigns/p5_repeat_feedback_20260910/videos.html).
  Например `pool_08` показывает repeat0 rescue от fresh8, `pool_22` harm;
  выбор этих примеров иллюстративный, статистика включает все pools.
- [Primary scores](campaigns/p5_repeat_feedback_20260910/analysis/selected_candidate_scores.csv),
  [paired effects](campaigns/p5_repeat_feedback_20260910/analysis/paired_effects.csv).
- [Аудит, числа и ограничения](campaigns/p5_repeat_feedback_20260910/review_20260910/summary.json),
  [split-предсказания](campaigns/p5_repeat_feedback_20260910/review_20260910/leave_one_suffix_out_predictions.csv),
  [pool-level таблица](campaigns/p5_repeat_feedback_20260910/review_20260910/pool_opportunities.csv).
- Исходный автоматический [RESULTS](campaigns/p5_repeat_feedback_20260910/analysis/RESULTS.md)
  не переписан; новый разбор хранится отдельно. Raw, NPZ и видео скачаны локально.

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/review_p5_repeat_feedback.py --decode-videos
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q tests/test_p5_repeat_feedback.py tests/test_p5_repeat_feedback_review.py
```

Для другого компьютера нужны оба каталога campaigns: `p5_repeat_feedback_20260910`
и исходные sidecars/таблица `p5_boundary_candidates_20260909`. Скрипт сопоставляет
серверные пути с локальной копией, не изменяя frozen config.

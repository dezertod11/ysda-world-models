# Главные результаты исследования

**Дополнение 13 сентября, пока не финальный результат:**
[Прерванная recovery confirmation](../../experiments/RECOVERY_CONFIRMATION_INTERIM_RESULTS_20260913.md):
108/128 полных matched cases; знакомые cells16/61 ->40/61 (+39.3п.п.),
x0.3 0/47 ->1/47. Preserve-only не улучшил старый recovery.
Обнаружен сильный переносной сбой локализации: медианная XY-ошибка23.5см
наx0.3 против2.5см на знакомых cells. Приоритет: закончить frozen main,
разделить geometry/localizer/primitive, затем проверять событийный controller.
Ниже приведены прежние завершённые результаты, не смешанные с этим срезом.

**Срез: 12 сентября 2026.** Frozen Cosmos Policy, преимущественно LIBERO-PRO.
[Полный отчёт](FULL_RESEARCH_REPORT.md) · [ICLR PDF](build/iclr2027.pdf) ·
[Источники](RESULTS_INDEX.md).

## Что исследовали

Можно ли улучшить управление world-action model без её дообучения:
выбирать действия по uncertainty/consensus вместо max-value, раньше получать
свежие наблюдения и восстанавливать неудачный захват по RGB?

Разделили четыре вопроса: **обнаружить риск состояния; выбрать лучшее действие;
решить, когда наблюдать; решить, когда и как вмешаться**. Выяснилось, что хороший
score для одного вопроса не обязательно решает остальные.

## Самые важные числа

Строки относятся к **разным выборкам и controls**, их SR нельзя ранжировать
как результаты единого benchmark.

| Эксперимент | Control → method | Что установлено |
|---|---|---|
| P3c: RGB regrasp, новые init восьми hard Position cells | 13/40 →24/40; **+27.5 п.п.**, CI[12.5; 42.5] | Сильнейший локальный положительный результат; 12 rescue/1 harm |
| P3d: повтор на знакомых cells | 6/40 →25/40; **+47.5 п.п.**, CI[30; 65] | Локальное recovery воспроизводится |
| P3d: новые cells | 26/35 →31/35; +14.3 п.п., CI[-2.9; 31.4] | Общий transfer **не подтверждён** |
| Shared-prefix requery, Object/task 0 | 46/100 →64/100; **+18 п.п.**, init-CI[4; 32] | Полезно конкретное feedback-вмешательство; не универсальное $t=72$ |
| valid 199: max-value vs OSC-medoid | Macro 54.77% →54.09%; -0.68 п.п., CI[-3.33; 1.99] | Широкого преимущества нашего selector нет |
| valid 199: max-value vs KeyStone-style | Macro 54.77% →55.76%; +1 п.п., CI[-2.01; 4.33] | Лучший point estimate, но superiority не установлено |
| P4b residual risk | 117/200 →113/200; -2 п.п., CI[-5.5; 1.5] | Prediction error улучшился, terminal SR нет |
| Decoder-medoid, H16 | 112/180 →112/180; **0 п.п.**, CI[-3.33; 3.33] | Равен max-value по SR; 7 rescue/7 harm |
| Observation Contract, primary extra regrasp | 151/192 →145/192 | Новый primary не лучше старого recovery |

## Что дали последние эксперименты

**Decoder-medoid:** выполнены 1440 rollout с H16/H8 и fixed-index controls.
H8 не улучшил средний SR; candidate calls почти удвоились. Hidden medoid
выбирает один seed своей группы в 81-84%queries. Это повод проверить seed
affinity representation, а не считать latent distance готовым value verifier.

**Observation Contract:**1536 основных ветвей. Preserve-only 161/192 против
preserve+regrasp 145/192: **16 success потеряны после дополнительного вмешательства**.
Аудит показывает: до regrasp предмет уже двигался вместе с захватом; после
открытия пальцев он падал. Это 8 prefixes/6 initclusters, не 16 независимых задач.
Ни один из шести заранее заданных pooled contrasts не прошёл Holm.05.

Preserve-only лучше старого physical 151/192 на 10 net successes, но это
**post-hoc gain одной cell**; cluster p=.09587. Нужен новый holdout.

## Какие научные выводы действительно есть

1. **State-risk detection ≠ action ranking.** P4b: global failure AUROC.650,
   within-pool ranking.509. Модель различает трудные состояния, но почти
   не различает хорошие и плохие действия одного состояния.
2. **Agreement ≠ correctness.** Consensus и маленький latent disagreement
   не гарантируют правильный захват или достижимый target.
3. **Candidate outcome зависит от продолжения.** У 96/288 fixed candidates
   success/fail менялся при смене suffix seed. Single-rollout oracle нестабилен.
4. **Локальная value misranking существует.** На одном fixed pool alternatives
   дали 10/10 против 1/10 max-value на новых repeats. Переносимый verifier ещё не найден.
5. **Свежие данные и recovery имеют цену.** Requery обрывает chunk;
   probe/regrasp физически меняют контакт и могут испортить уже хороший захват.
6. **Лучший положительный механизм сейчас: RGB recovery на конкретных hard cells.**
   Нового подтверждённого SOTA planner на широком PRO benchmark пока нет.

## Формулы для обсуждения

Действия $A_i\in\mathbb R^{16\times7}$ семплируются из одного checkpoint
при одинаковом текущем наблюдении. Межсемпловое std считается с делителем K:

$$
\sigma_{h,d}=\sqrt{\frac1K\sum_i(a_{i,h,d}-\bar a_{h,d})^2},\qquad
U_{first}=\sqrt{\sum_{d=1}^{6}\sigma_{1,d}^2},\qquad
U_{value}=\operatorname{Std}_i(V_i).
$$

Классический risk score: $S_i=V_i-\lambda U_i$.
**Если U одно на весь pool, штраф не изменяет argmax.** Для reranking нужен
candidate-specific uncertainty; для выбора requery подходит state/pool risk.
Latent-copy std измеряет disagreement повторных записей внутри одного
generated tensor, а не независимые samples.

В наших основных сериях actions/futures/value генерировались **joint/parallel**,
не по полной авторской AR planning-системе $a\to s'\to v$.
Prediction error по реальному будущему доступен **после** исполнения chunk,
поэтому не годится как предупреждение ошибки в том же chunk без surrogate.

## Что делать первым

Заморозить preserve-only/contact-preserving intervention и проверить новые
task/init/cells против continue, старого recovery и matched probe. Оценивать
SR, harm/drop, calibration и compute отдельно. Учить **advantage вмешательства**,
а не только uncertainty состояния. Decoder масштабировать лишь после
seed-bank/permutation controls. Это план, не результат уже выполненной серии.

## Как представлять работу

Корректный тезис: «Мы исследовали границы inference-time улучшения frozen
world-action model и показали, почему uncertainty, consensus, feedback и
recovery требуют разных контролируемых проверок. Получили локальный recovery
gain и выявили механизм вредных вмешательств».

Некорректно: «Наш planning уже превосходит SOTA на LIBERO-PRO».
Текущая рукопись является **эмпирическим диагностическим исследованием**.
Для сильной submission нужны авторская проверка и чётко ограниченный claim;
желательны независимый transfer и подтверждение нового controller.

Подробные источники: [P3c](../../experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md),
[P3d](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md),
[q4](../../experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md),
[P4b](../../experiments/P4B_RESIDUAL_RISK_RESULTS_20260907.md),
[consensus/P5](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md),
[fixed pool](../../experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md),
[Observation Contract](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md),
[decoder](../../experiments/DECODER_MEDOID_RESULTS_20260912.md).

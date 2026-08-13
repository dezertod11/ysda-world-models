# Adaptive uncertainty-aware planning: гипотезы и протокол

Дата фиксации протокола: 13 августа 2026 года. Этот документ создан до новых
online rollout и отделяет гипотезы от последующего анализа результатов.

## Исходное наблюдение

В denoise-10 replication фиксированный action penalty дал 56/100 success против
52/100 у `max(value)`, но эффект был неоднородным: `+7.5` п.п. на milk,
`+16.7` п.п. на yellow-book и `-13.3` п.п. на long-mug. Oracle, который для
каждого seed выбирает успешную из этих двух стратегий, получил бы 66/100.

Следовательно, основной резерв находится не в увеличении одного глобального
коэффициента, а в контекстном решении: когда доверять value, когда учитывать
uncertainty и когда раньше запросить новое реальное наблюдение.

## Проверяемые гипотезы

### H1. Episode-level regime/difficulty gate

На первом query вычисляется среднее value кандидатов

\[
d_0=\frac{1}{N}\sum_{i=1}^{N}V_{i,0}.
\]

Затем на весь эпизод фиксируется

\[
g=\mathbb{1}[d_0\ge \tau_d],\qquad
S_i=z(V_i)-g\lambda z(U_i^{\mathrm{internal}}).
\]

Порог `tau_d=0.088588` выбран на старой denoise-5 кампании. При ретроспективной
проверке на новых denoise-10 данных это правило дало 61/100, но выбор самого
признака остаётся exploratory и требует новых seeds. Высокое `d0` здесь надо
интерпретировать как идентификатор режима value-overconfidence, а не как
калиброванную вероятность лёгкой задачи.

**Protocol amendment до выполнения H1 rollout.** На уже существующей denoise-10
calibration среднее `d0` равно примерно `0.089` для long-mug, `0.331` для milk и
`0.311` для yellow. Поэтому дополнительно проверяются `tau_d=0.1` и `0.2`:
оба должны реализовывать один и тот же устойчивый task-regime split. Если их
результаты различаются существенно, q0-value gate нельзя считать стабильным.
Эти варианты остаются calibration sweep и проходят тот же независимый
confirmatory-протокол; они не оцениваются на старых outcomes как test set.

### H2. Conservative value-margin gate

Сначала находится risk-aware кандидат `r`, затем он заменяет max-value кандидат
`m` только при малой цене по value и достаточном выигрыше по uncertainty:

\[
r=\arg\max_i[z(V_i)-\lambda z(U_i)],
\]

\[
i^*=\begin{cases}
r,&V_m-V_r\le\tau_V\ \land\ z(U_m)-z(U_r)\ge\tau_U,\\
m,&\text{иначе}.
\end{cases}
\]

Проверяются `tau_V` в `{0.0005, 0.002, 0.01}` и `tau_U` в `{0, 0.5}`.

### H3. Cross-sample action consensus

Internal-copy uncertainty может быть низкой при общей систематической ошибке.
Поэтому вводится независимый межсемпловый score:

\[
C_i=\frac{1}{N-1}\sum_{j\ne i}\lVert a_{i,0}-a_{j,0}\rVert_2,
\qquad S_i=z(V_i)-\lambda z(C_i).
\]

Он штрафует action-кандидаты, являющиеся выбросами относительно остальных.
Проверяются `lambda` в `{0.5, 1, 2}`.

### H4. Phase-aware penalty

Ошибка grasp/drop необратима главным образом в manipulation phase, тогда как
постоянный penalty может мешать длинным стабильным эпизодам:

\[
S_{i,q}=z(V_{i,q})-
\mathbb{1}\!\left[\frac{t_q}{T_{max}}\le\rho\right]
\lambda z(U_{i,q}).
\]

Проверяются `rho` в `{0.3, 0.5, 0.7}`.

### H5. Disagreement-triggered receding horizon

Если `max(value)` и risk-aware ranking выбирают разные candidates, состояние
считается неоднозначным. В таком query исполняется только `h<16` действий,
после чего policy получает новое реальное наблюдение:

\[
H_q=\begin{cases}
h,&\arg\max V_i\ne\arg\max[z(V_i)-\lambda z(U_i)],\\
16,&\text{иначе}.
\end{cases}
\]

Проверяются `h` в `{4, 8, 12}`. Это отличается от неудачного fixed `H=8`:
короткий horizon используется только в неоднозначных query.

### H6. Difficulty gate + adaptive horizon

Комбинация H1 и H5 применяет uncertainty только в выбранном на `q=0` режиме и
сокращает horizon только при фактическом конфликте rankings. Это основной
кандидат на итоговый метод, если обе отдельные компоненты подтвердятся.

### H7. Robust world/value prediction

Следующая линия после текущей кампании: autoregressive `a -> future state -> v`,
несколько value/future-state samples и LCB/CVaR вместо среднего value. Она
существенно дороже и не смешивается с текущей проверкой selection logic.

### H8. Calibrated abstention для Safety

LIBERO-Safety показал 0/144 success при сильно завышенном value. Поэтому для
Safety нужен отдельный OOD/calibration score и действие `replan/abstain`, а не
только disagreement между samples. Эту гипотезу нельзя валидировать на четырёх
имеющихся violations; сначала требуется больше positive safety events.

### H9. Разложение uncertainty и noise floor

Наблюдаемая вариативность состоит как минимум из stochastic-sample
disagreement, CUDA/process nondeterminism и истинной чувствительности closed-loop
траектории. Exact replay одной стратегии с теми же seeds оценивает второй и
третий компоненты. Candidate penalty должен давать эффект больше replay
disagreement rate, иначе улучшение нельзя отделить от вычислительного шума.

### H10. Temporal change score вместо абсолютного порога

Fail может предсказывать не высокий уровень uncertainty, а быстрый рост перед
grasp/drop. Для каждого online-признака можно использовать EWMA/CUSUM:

\[
R_q=\max\{0,\ \beta R_{q-1}+z(U_q)-\kappa\}.
\]

При `R_q > tau_R` policy уменьшает horizon или усиливает penalty. Параметры
следует обучать только на calibration trajectories и проверять на новых tasks.

### H11. Hierarchical learned gate

Вместо одного порога обучается малый интерпретируемый gate

\[
p_{risk}=\sigma(w^T x_q+b_{suite}+b_{phase}),
\]

где `x_q` содержит value margin, internal uncertainty, cross-sample consensus,
progress и gripper phase. Leave-one-task/suite-out оценка проверяет, переносится
ли gate, а partial pooling не позволяет малым tasks переобучить коэффициенты.

### H12. Adaptive compute budget

Число candidates можно увеличивать с `N=2/4` до `N=8` только при конфликте
rankings или temporal alarm. Это должно дать лучшую coverage сложных состояний
без постоянного удвоения стоимости inference.

### H13. Learned prediction-error surrogate

Настоящий image/proprio prediction error известен только после chunk. Его можно
использовать как target для небольшого online surrogate, предсказывающего
будущее расхождение по latent/action/value признакам текущего query. В planning
используется `value - lambda * predicted_error`, а не недоступная future error.

### H14. Constrained safety planning

Для LIBERO-Safety goal value и constraint risk должны быть раздельными heads:

\[
i^*=\arg\max_i V_i\quad\text{при}\quad \widehat C_i\le\epsilon,
\]

с fallback `replan/abstain`, если допустимых candidates нет. Обычный scalar
penalty не различает task failure и нарушение ограничения.

## Экспериментальный протокол

1. `adaptive_screening`: три известных mixed OOD case, 12 одинаковых seeds для
   каждой стратегии; перебор только заранее перечисленных параметров.
   Отдельный `adaptive_regime_threshold_screening` добавляет два зафиксированных
   выше порога H1/H6 на тех же calibration seeds.
2. По screening выбираются максимум две adaptive стратегии без просмотра
   confirmatory outcomes.
3. `adaptive_confirmatory`: новые непересекающиеся seeds на шести case: три
   известных boundary и три дополнительных OOD case.
4. Primary endpoint: pooled paired success delta против `max(value)` со
   stratified paired bootstrap CI и exact McNemar test.
5. Secondary endpoints: per-case delta, wins/losses/ties, rerank rate, число
   model queries, final time, drop/wrong-object rates и compute overhead.
6. Результаты обязательно показываются отдельно по case; pooled score без
   task control не считается доказательством универсальности.
7. Для `max(value)` и fixed action penalty запускаются точные replay-копии.
   Их paired disagreement задаёт эмпирический noise floor межпроцессной CUDA
   недетерминированности; эффект нового метода должен сравниваться и с ним.

### Правило выбора после screening

До просмотра итогов screening фиксируются две отдельные категории кандидатов:

1. **Без дополнительного inference:** `difficulty`, `margin`, `consensus` и
   `phase` с теми гиперпараметрами, которые присутствуют во всех трёх core case.
2. **Adaptive horizon:** `requery` и `difficulty_requery`, также только варианты,
   присутствующие во всех трёх core case.

В каждой категории конфигурации ранжируются по заранее заданному utility

\[
J=\Delta_{pool}+0.5\min_c\Delta_c
  -0.02\max(0, Q_{ratio}-1),
\]

где `Delta_pool` -- paired success delta на всех calibration seeds,
`min_c Delta_c` -- худший delta по case, а `Q_ratio` -- нормированная стоимость
model queries относительно `max(value)`. Для каждого эпизода она считается как
`num_queries / ceil(final_t / 16)`, поэтому timeout и ранний success не смешиваются
с дополнительным inference adaptive horizon. В confirmatory проходит по одному победителю категории.
При равном `J` выбирается меньший query overhead, затем меньшая сложность правила.
Replay-варианты и fixed penalty являются контролями и в отборе не участвуют.

Если лучший adaptive-horizon вариант имеет `Delta_pool <= 0`, он всё равно
проверяется как заранее выделенная отдельная гипотеза, но не называется улучшением.
Так мы не подменяем отрицательный результат новым post-hoc перебором.

### Независимая confirmatory-выборка

После заморозки двух победителей запускаются 30 новых paired rollout на каждом из
шести case (seed ranges не пересекаются со screening):

| Роль | Suite / task / init | Max steps |
| --- | --- | ---: |
| известный boundary | `libero_spatial_with_milk / 5 / 0` | 220 |
| известный boundary | `libero_spatial_with_yellow_book / 8 / 0` | 220 |
| известный boundary | `libero_10_with_mug / 4 / 0` | 520 |
| новый OOD holdout | `libero_spatial_with_mug / 0 / 0` | 220 |
| новый OOD holdout | `libero_10_with_milk / 9 / 0` | 520 |
| новый OOD holdout | `libero_goal_with_mug / 9 / 0` | 320 |

На каждом case сравниваются `max(value)`, его exact replay, fixed action penalty
`lambda=1`, его exact replay и два замороженных adaptive-метода. Primary result
считается одновременно на всех 180 paired seeds; известные и новые case также
показываются отдельными strata. Видео сохраняются не для всех 1080 траекторий,
а отдельным deterministic replay для discordant outcomes после статистики.

Все новые traces сохраняют candidate values, internal uncertainty, consensus
distance и planning scores как JSON-массивы. Это позволит обучать следующий
ranker только на calibration split и воспроизводимо применять его online.

## Frozen confirmatory result

Результат зафиксирован после завершения всех `1080/1080` strategy executions:
6 cases, 30 новых paired rollout seeds на case и 6 стратегий. Два adaptive
метода были выбраны только по calibration и не менялись после просмотра этих
outcomes.

| Метод | Success | Delta к `max(value)` | 95% paired bootstrap CI | Exact McNemar | Holm p | Нормированный query cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `max(value)` | 115/180 = 63.9% | -- | -- | -- | -- | 1.00x |
| fixed `action_l1` control | 131/180 = 72.8% | +8.9 п.п. | [+0.6; +17.2] | 0.0559 | -- | 1.00x |
| `phase_l1_r0.3` | 130/180 = 72.2% | +8.3 п.п. | [+0.6; +16.1] | 0.0489 | 0.0489 | 1.00x |
| `requery_l1_h8` | 143/180 = 79.4% | +15.6 п.п. | [+7.2; +23.3] | 0.00062 | 0.00123 | 1.27x |

### Что подтвердилось

- Оба эффекта уменьшились относительно calibration (`requery`: `+30.6` до
  `+15.6` п.п.; `phase`: `+19.4` до `+8.3` п.п.), что показывает заметный
  screening optimism. При этом направление эффекта сохранилось на новых seeds.
- **H4 получила погранично значимое подтверждение.** Phase-aware penalty дал
  положительный delta на всех шести cases (`+3.3...+16.7` п.п.) без
  дополнительного inference. При этом он статистически не лучше fixed
  `action_l1` (`-0.6` п.п., McNemar `p=1.0`): преимущество H4 состоит прежде
  всего в отсутствии наблюдаемого отрицательного per-case delta.
- **H5 получила наиболее сильное подтверждение.** Disagreement-triggered
  receding horizon дал `+15.6` п.п. pooled и сохранил положительный эффект как
  на известных boundary cases (`+18.9` п.п.), так и на новых OOD holdout
  (`+12.2` п.п.). После поправки на две frozen гипотезы результат остаётся
  значимым.
- Эффект H5 неоднороден: четыре cases улучшились на `+20...+46.7` п.п., но
  `milk_task5` ухудшился на `-10` п.п., а `goal_mug_task9` на `-3.3` п.п.
  Поэтому adaptive requery нельзя без дополнительного gate применять как
  универсальную замену baseline.
- Нормированный inference cost H5 равен `1.27x`; фактическое среднее число
  queries выросло только в `1.067x`, потому что успешные requery-эпизоды чаще
  завершались раньше. Для сравнения алгоритмов следует использовать первое
  число, которое не награждает метод за раннее завершение.

### Диагностика механизма и ограничения

- Exact `max(value)` replay изменил outcome в `8/180 = 4.4%` seed, а replay
  fixed action penalty -- в `17/180 = 9.4%`. Улучшение H5 существенно больше
  baseline noise floor, но отдельные discordant видео нельзя трактовать как
  детерминированное доказательство причинности. Среди восьми post-hoc выбранных
  discordant seed оба исходных outcome полностью воспроизвелись в пяти exact
  replays; эта галерея является качественной диагностикой, а не новой оценкой
  success rate.
- Internal latent-action disagreement связан с ошибкой future proprio после
  chunk: case-controlled Spearman `rho=0.548`. Для latent value uncertainty
  связь слабее (`rho=0.385`). Это поддерживает использование uncertainty как
  online planning-сигнала.
- Лучший ранний бинарный fail predictor на query `0...3` имеет только
  case-controlled AUROC `0.588`. Следовательно, текущие метрики полезнее для
  относительного ранжирования кандидатов в одном состоянии, чем для единого
  абсолютного порога «эпизод завершится fail» между разными tasks.
- Q0 difficulty gate сработал в `90.6%` confirmatory эпизодов и практически не
  разделил режимы. H1 в текущей пороговой форме следует заменить
  task-normalized/learned gate, обученным только на calibration cases.
- Prediction error измеряется уже после исполнения chunk. Его корреляция с
  текущей uncertainty является mechanism evidence, но использовать сам error
  для выбора того же действия нельзя без causal online surrogate (H13).

Полные таблицы, графики и paired outcomes находятся в
[`campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md`](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md).

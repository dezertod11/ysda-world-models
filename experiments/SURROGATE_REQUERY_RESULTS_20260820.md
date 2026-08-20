# Adaptive requery и prediction-error surrogate: итог эксперимента

Дата фиксации результата: 20 августа 2026 года. Кампания
`surrogate_confirmatory_20260819` завершена полностью: 960/960 rollout,
ошибок jobs нет.

## Краткий итог

Главный положительный результат: стратегия `requery_l1_h8` повысила success
rate с 146/240 (60.8%) до 161/240 (67.1%). Парная разница равна +6.25 п.п.,
95% bootstrap CI `[+1.7; +11.3]` п.п., exact McNemar `p=0.0237`, после
Holm-коррекции по двум заранее выбранным adaptive-стратегиям `p=0.0474`.

Это улучшение не бесплатно: нормализованная стоимость model queries выросла
до 1.27x, а фактическое число policy-query rounds - до 1.22x. Кроме того, эффект
неоднороден: разброс по задачам составляет от -15 до +30 п.п.

Frozen learned surrogate хорошо предсказывает физическую ошибку следующего
proprio-состояния, но не улучшает task success. Для выбранного
`phase_surrogate...` получено 147/240 (61.3%), то есть всего +0.4 п.п. к
baseline, CI `[-4.2; +5.0]` п.п., Holm `p=1.0`.

## Постановка

В каждом состоянии Cosmos Policy генерирует четыре stochastic candidates.
Для candidate `i` доступны value `V_i`, action chunk
`A_i in R^(16 x 7)`, future proprio/image и latent-представления. Стандартный
planner выбирает

\[
i_V=\arg\max_i V_i
\]

и исполняет 16 действий до следующего наблюдения.

Action uncertainty вычисляется внутри latent одного candidate. В latent action
vector повторён несколько раз. Для первого действия берётся стандартное
отклонение по копиям, затем L2-агрегация по семи координатам:

\[
u_i^a=\left\|\operatorname{Std}_{c}
\left[A^{(c)}_{i,0,:}\right]\right\|_2.
\]

Value и uncertainty стандартизируются внутри текущих четырёх candidates:

\[
S_i=z(V_i)-\lambda z(u_i^a),\qquad \lambda=1,
\quad i_R=\arg\max_i S_i.
\]

Проверены четыре стратегии:

| Стратегия | Выбор candidate | Число исполняемых действий |
|---|---|---:|
| `max_value` | `i_V` | 16 |
| `action_l1` | `i_R` | 16 |
| `requery_l1_h8` | `i_R` | 8, если `i_R != i_V`, иначе 16 |
| `phase_surrogate...` | risk-aware в первой половине эпизода или при alarm | 8 при alarm, иначе 16 |

Таким образом, `requery_l1_h8` одновременно меняет ranking и adaptive horizon:
если uncertainty меняет выбор относительно `max(value)`, среда наблюдается
снова после восьми действий.

## Протокол

- Модель: `nvidia/Cosmos-Policy-LIBERO-Predict2-2B`.
- Benchmark: 12 LIBERO-PRO cases, один фиксированный `init_state` на case.
- Шесть ранее найденных boundary cases и шесть заранее выбранных новых OOD
  axes/families.
- 20 новых matched rollout seeds на каждый case.
- Четыре стратегии на одинаковых `suite/task/init_state/rollout_seed`.
- Четыре stochastic candidates, denoise-10, action chunk 16.
- Итого: 12 x 20 x 4 = 960 rollout.
- Primary test: paired success delta, stratified bootstrap CI, exact McNemar;
  Holm correction для двух frozen adaptive-стратегий.

Screening использовал другие seeds и только выбирал две стратегии для
confirmatory проверки. Его числа являются exploratory и не смешиваются с
финальным тестом.

В screening `requery_l1_h8` показал +14.6 п.п. (39/48 против 32/48), а
`phase_surrogate...` +8.3 п.п. (36/48 против 32/48). На frozen confirmatory
split эффекты закономерно уменьшились до +6.25 и +0.4 п.п. соответственно.
Первый сохранился, второй исчез. Это и есть причина, почему screening нельзя
использовать как финальное доказательство.

## Confirmatory результаты

| Стратегия | Success | Delta к `max_value` | 95% CI, п.п. | McNemar p | Holm p | Query cost | Calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| `max_value` | 146/240 (60.8%) | - | - | - | - | 1.00x | 1.00x |
| `action_l1` | 151/240 (62.9%) | +2.1 п.п. | [-2.9; +7.1] | 0.522 | - | 1.00x | 0.99x |
| `requery_l1_h8` | **161/240 (67.1%)** | **+6.25 п.п.** | **[+1.7; +11.3]** | **0.0237** | **0.0474** | 1.27x | 1.22x |
| `phase_surrogate...` | 147/240 (61.3%) | +0.4 п.п. | [-4.2; +5.0] | 1.000 | 1.000 | 1.11x | 1.13x |

У `requery_l1_h8` risk-aware ranking отличался от `max(value)` примерно на
41.1% queries. Сравнение с `action_l1` даёт +4.2 п.п., но CI
`[-0.4; +8.8]` и `p=0.154`. Поэтому данные согласуются с тем, что важен именно
более ранний feedback из среды, однако текущий эксперимент ещё не отделяет его
эффект от reranking статистически надёжно.

В абсолютных числах baseline использовал 3332 policy-query rounds, а requery -
4057. Получено 15 дополнительных successes за 725 дополнительных rounds, то
есть около 48 дополнительных re-planning points на один net success. Это не
финальная latency-метрика, но полезная оценка цены улучшения.

### Перенос и неоднородность

На шести известных boundary cases: +7.5 п.п., CI `[-1.7; +16.7]`. На шести
новых OOD cases: +5.0 п.п., CI `[+1.7; +8.3]`, unadjusted McNemar `p=0.031`.
Но среди новых OOD только `libero_spatial_swap/task8` был действительно mixed:
там success вырос с 5% до 35%. Остальные пять cases имели 0% или 100% baseline,
поэтому stratum-результат нельзя трактовать как широкий перенос на все OOD.

Наиболее заметные deltas для `requery_l1_h8`:

| Case | Delta |
|---|---:|
| new OOD spatial swap | +30 п.п. |
| spatial mug | +25 п.п. |
| long mug | +15 п.п. |
| yellow book | +15 п.п. |
| long milk | +5 п.п. |
| goal mug | -15 п.п. |

На остальных шести cases delta равна нулю. Это подтверждает наличие полезного
механизма, но также показывает необходимость context-aware gate.

## Что показал surrogate

Frozen ridge surrogate предсказывает ошибку после исполнения chunk:

\[
e_q=\lVert \hat p_{q+1}-p_{q+1}\rVert_2,
\]

\[
\log \hat e_q=-2.89194
+0.12337z(\log U_q^a)
+0.13764z(\log U_q^p)
+0.40796z(\log \bar V_q)
+0.30282z(\log D_q^p).
\]

На 3332 новых baseline queries:

- case-controlled Spearman `rho=0.579`;
- AUROC для case-relative top-quartile proprio error `0.731`;
- median actual error при alarm в 3.03 раза выше, чем без alarm;
- median predicted/actual calibration ratio `1.12`.

То есть surrogate действительно находит chunks с большим рассогласованием
world-model и реальности. Однако лучший ранний predictor итогового fail на
queries 0..3 имеет AUROC только `0.547`, почти случайный. Ошибка future proprio
и task failure - разные targets: большая динамическая ошибка не обязательно
мешает задаче, а небольшой промах в контакте может полностью разрушить успех.

## Диагностика типов ошибок

Эвристический `target_drop_candidate` встречался в 73/240 baseline episodes и
51/240 episodes `requery_l1_h8`: -9.2 п.п., paired McNemar `p=0.00020`.
Среди только failed episodes основной тип `target_drop` уменьшился с 54 до 30.
Одновременно `timeout_no_goal` вырос с 14 до 24 episodes.

Surrogate hybrid тоже уменьшил `target_drop_candidate` с 73 до 57, но увеличил
`timeout_no_goal` с 14 до 37. Поэтому он скорее меняет тип ошибки с падения
объекта на незавершение задачи, чем повышает success.

Эти метки являются post-hoc эвристиками, а не официальными LIBERO-Safety
violations; приведённые p-values диагностические и не корректировались за
множественную проверку.

## Выводы

1. Лучший текущий planner - `requery_l1_h8`: uncertainty полезна как сигнал
   того, когда сократить open-loop horizon и получить реальное наблюдение.
2. Постоянный uncertainty penalty без adaptive feedback даёт лишь +2.1 п.п. и
   не подтверждён статистически. Простое изменение ranking недостаточно.
3. Future-proprio surrogate переносится как estimator физической ошибки, но не
   как gate для task success. Нельзя оптимизировать удобный proxy вместо
   task-critical риска.
4. Улучшение сопровождается меньшим числом падений объекта, но большим числом
   таймаутов. Следующий score должен учитывать и safety, и progress.
5. Эффект сильно зависит от задачи. Средний pooled gain не отменяет регрессию
   -15 п.п. на goal-mug case.
6. Ранние агрегированные uncertainty metrics не дают универсального fail
   detector: лучший AUROC 0.547.

## Следующие проверки

1. На новых mixed-success cases отдельно сравнить: fixed `action_l1`,
   `requery_l1_h8` и horizon-only стратегию, которая сохраняет `i_V`, но
   исполняет восемь действий при ranking disagreement. Это разделит эффекты
   reranking и feedback.
2. Заморозить и проверить horizons 4/8/12 вместе с value-margin и
   uncertainty-gain gates; оценивать success вместе со стоимостью queries.
3. Обучать surrogate на task-critical targets: drop/contact, object-pose
   divergence и отсутствие progress, а не только proprio L2.
4. Делать cross-case calibration и оставлять целый suite/task вне обучения;
   не подбирать gate на тех же cases, где измеряется итоговый success.
5. Добавить официальный LIBERO-Safety outcome как отдельную цель, чтобы
   сокращение падений не обменивалось незаметно на таймауты.

## Артефакты

- Notebook с таблицами и графиками:
  [`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb)
- Автоматический отчёт:
  [`campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/README.md`](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/README.md)
- Frozen primary table:
  [`frozen_confirmatory_results.csv`](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/frozen_confirmatory_results.csv)
- Paired per-case table:
  [`paired_by_case.csv`](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/paired_by_case.csv)
- Failure-mode diagnostics:
  [`paired_failure_modes.csv`](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/paired_failure_modes.csv)
- Surrogate transfer:
  [`surrogate_transfer_diagnostics.csv`](campaigns/surrogate_confirmatory_20260819/analysis/adaptive_summary/surrogate_transfer_diagnostics.csv)
- Frozen protocol:
  [`SURROGATE_REQUERY_HYPOTHESES_20260819.md`](SURROGATE_REQUERY_HYPOTHESES_20260819.md)

Matched-seed video replays поставлены в очередь и будут собраны автоматически,
когда на сервере освободится GPU 2-7. Confirmatory success statistics от них не
зависят.

# Phase 1: ID и LIBERO-PRO OOD результаты

Анализ включает только завершённые non-smoke runs, для которых одновременно
есть `query_traces`, `metadata` и `pair_summary`. Незавершённые и оборванные
asset-запуски перечислены в `run_inventory.csv` и не участвуют в числах ниже.

## Итоговые outcomes

| Split | Эпизоды | Success | Fail | Success rate | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| ID | 72 | 72 | 0 | 100.0% | [94.9%, 100.0%] |
| LIBERO-PRO OOD | 106 | 82 | 24 | 77.4% | [68.5%, 84.3%] |

Разница ID/OOD статистически заметна уже в screening
(`Fisher exact p=1.69e-06`), но это не оценка общего benchmark:
мы намеренно выбирали сложные OOD-конфигурации.

## Найденные mixed-outcome конфигурации

| Suite | Task | Success | Success rate |
|---|---:|---:|---:|
| `libero_10_with_milk` | 9 | 3/4 | 75.0% |
| `libero_10_with_mug` | 4 | 2/4 | 50.0% |
| `libero_goal_with_mug` | 9 | 3/4 | 75.0% |
| `libero_spatial_with_milk` | 5 | 12/24 | 50.0% |
| `libero_spatial_with_mug` | 0 | 8/12 | 66.7% |
| `libero_spatial_with_yellow_book` | 5 | 5/6 | 83.3% |
| `libero_spatial_with_yellow_book` | 8 | 3/6 | 50.0% |

Всего найдено 7 фиксированных `suite/task/init_state`
со смесью success и fail. Лучшие boundary cases для следующих planning
экспериментов: `libero_spatial_with_milk/task5/init0` и
`libero_spatial_with_yellow_book/task8/init0`, оба с success rate 50%.

## Failure modes и safety

- OOD outcomes: `success`=82, `timeout_no_goal`=12, `target_drop_candidate`=11, `timeout_partial_goal`=1.
- Official safety violations: **0**. Это
  ожидаемо для LIBERO-PRO без официальных LIBERO-Safety constraints.
- Drop heuristic отметил 19 OOD эпизодов, из них
  11 закончились fail. Его precision относительно финального
  fail равен 57.9%, recall всех fail 45.8%.
  Ещё 8 отмеченных эпизодов затем успешно завершились,
  поэтому `*_candidate`
  нельзя использовать как официальный safety label.

## Early online failure signal

Для каждого mixed group online-метрики усреднены по `query=0..3`,
затем стандартизованы **внутри того же suite/task/init_state**. Самое раннее
физическое событие в данных произошло на `t=55`, поэтому окно до `t=48`
не содержит post-failure leakage.

Лучший exploratory признак:
`latent_action_copy_std_mean_mean_over_samples` с pooled
group-standardized AUROC
**0.671**
и направлением `high=failure`.
Согласованность направления: 5/7 групп с `high=failure`, 1 tie и 1 с обратным направлением. Это оставляет
внутреннюю согласованность action latent главным кандидатом, но уже не
поддерживает тезис об универсальности сигнала.

При этом обычные `action_first_step_l2_std`, `value_std` и `value_range` не
показали устойчивого направления между задачами. Ranking является exploratory:
признак выбран и оценён на тех же
60 эпизодах,
внешнего holdout здесь ещё нет.

## Prediction error

После контроля `suite/task/init_state/query_idx` связи uncertainty с
последующей image/proprio prediction error оказались слабыми. Самая сильная
не-value пара: `latent_future_proprio_copy_std_mean_mean_over_samples` vs `prediction_error_future_proprio_l2`: Spearman $\rho=0.139$. Ранее наблюдавшиеся корреляции
около 0.8 в pooled trajectories в основном объяснялись фазой эпизода.

Следовательно, Phase 1 поддерживает ранний latent-action risk signal, но пока не
доказывает, что output dispersion является хорошо откалиброванной оценкой
ошибки world model.

## Что запускать дальше

1. Довести до минимум 40 rollout каждую основную boundary-конфигурацию:
   `milk/task5/init0`, `yellow_book/task8/init0` и
   `libero_10_with_mug/task4/init0`.
2. Зафиксировать feature и normalization на calibration split.
3. Проверить `latent_action_copy_std...` на новых seed blocks и новых init states.
4. Отдельно оценить transient-drop detector на LIBERO-Safety.
5. Только после holdout перейти к paired candidate planning против `max(value)`.

Графики находятся в `plots/`, подробные таблицы в CSV рядом с этим файлом.

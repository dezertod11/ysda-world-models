# Frozen H16 ranker: paired closed-loop result

Дата: 29 августа 2026 года.

Статус: **основная кампания завершена, 720/720 episodes; formal gate FAIL**.

## Главный результат

Factor-specific H16 ranker ранее устойчиво уменьшал offline regret на новых
exact-state branches, но это улучшение **не перенеслось в terminal task
success**. На 360 парных rollout:

$$
\Delta SR_{macro}=SR_{ranker}-SR_{maxV}=-0.28\ \text{п.п.},
$$

$$
95\%\ CI=[-2.22; +1.39]\ \text{п.п.}
$$

У max-value получилось 165/360 success (45.83%), у frozen ranker 164/360
(45.56%). Это не доказывает, что ranker в среднем вреден, но уверенно не
подтверждает заявленное улучшение. Согласно preregistered правилу ranker не
становится новым planning baseline и не должен дообучаться на этих outcomes.

## Что проверялось

В каждом query Cosmos Policy строила один и тот же для обеих стратегий набор
из шести joint candidates:

$$
\mathcal C_q=\{(a_i^{1:16},\hat s_i^+,\hat v_i,z_i)\}_{i=1}^{6}.
$$

Baseline выбирал

$$
i_{maxV}=\arg\max_i\hat v_i.
$$

Frozen ranker использовал одиннадцать заранее зафиксированных признаков:

$$
x_i=[\hat v_i,\|a_i^1\|_1,\|a_i^{1:16}\|_1,
\|a_i^{1:16}\|_2,u^a_{mean},u^a_{max},u^{a_1}_{copy},
u^p_{mean},u^p_{max},u^v_{mean},u^v_{max}].
$$

После стандартизации внутри текущего candidate pool применялась отдельная
ridge-head для OOD factor:

$$
r_{f,i}=\theta_f^\top
\frac{\operatorname{impute}(z_{\mathcal C_q}(x_i))-\mu_f}{\sigma_f},
\qquad i_{ranker}=\arg\max_i r_{f,i}.
$$

Этот critic был обучен предсказывать не terminal success, а короткую H16
dense consequence utility:

$$
G_{16}=2I_{success}+\Delta progress+D_{phase}
-I_{drop}-0.5I_{wrong}-I_{violation}.
$$

Именно перенос от локальной H16 utility к длинному closed-loop исходу являлся
предметом проверки.

Frozen model:
`experiments/frozen_models/factor_h16_dense_ridge_v1.json`.

Payload SHA-256:
`086dfebd71040c3b8512d9e9cc25151dd95fdc19d68b60a3a990f563924cfbbb`.

## Дизайн

Обе стратегии имели одинаковые `task/init_state/rollout_seed`, шесть diffusion
samples, H16, пять action denoising steps и максимум 280 environment steps.
Query-zero candidate pools совпадают; после первого различающегося действия
траектории закономерно расходятся.

| Factor | LIBERO-PRO cells | Pairs |
|---|---|---:|
| Environment | `libero_object_env`, tasks 7-9, init 5-9 | 120 |
| Object | `libero_object_object`, tasks 8-9, init 5-9 | 120 |
| Position | `x=0.3` tasks 4-5 и `y=0.3` tasks 8-9, init 5-9 | 120 |
| **Всего** | 45 independent `task/init` groups | **360** |

Primary endpoint был зафиксирован до просмотра outcomes. Доверительные
интервалы получены 5000-кратным bootstrap по `task/init` groups внутри factor,
seed 20260829. Smoke outcomes исключены.

Полный preregistration:
[`FROZEN_H16_CLOSED_LOOP_PROTOCOL_20260829.md`](FROZEN_H16_CLOSED_LOOP_PROTOCOL_20260829.md).

## Terminal success

| Factor | maxV | Frozen ranker | Delta | Gains / losses | 95% grouped CI | Exact McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| Environment | 45/120 = 37.50% | 41/120 = 34.17% | -3.33 п.п. | 1 / 5 | [-9.17; 0.00] | 0.2188 |
| Object | 120/120 = 100% | 120/120 = 100% | 0.00 п.п. | 0 / 0 | [0.00; 0.00] | 1.0000 |
| Position | 0/120 = 0% | 3/120 = 2.50% | +2.50 п.п. | 3 / 0 | [0.00; 5.00] | 0.2500 |
| **Factor macro** | **45.83%** | **45.56%** | **-0.28 п.п.** | **4 / 5** | **[-2.22; +1.39]** | exploratory overall p = 1.0 |

Ни один factor-specific exact paired test не отделился от нуля. Position дал
три редких rescue, но Environment потерял четыре net successes. Object не
содержит информации о ranking quality из-за полного ceiling effect.

## Integrity

Все технические условия прошли:

- 360/360 complete pairs и ровно 120 pairs на factor;
- шесть candidates на каждом query;
- правильный frozen hash во всех 720 episodes;
- query-zero values, ranker scores и first actions совпали между процессами
  точно, максимальная разница равна 0;
- baseline всегда выбирал argmax value, ranker всегда выбирал argmax score;
- query-zero selectors расходились в 73.06% пар, поэтому treatment был активен;
- ошибок Python, OOM и незавершённых jobs нет.

Gate провален только по содержательному primary condition: нижняя граница
macro CI не выше нуля.

## Что делал ranker на практике

Ranker оказался агрессивной заменой selector, а не небольшой risk correction.

| Factor | Disagreement на query 0 | Не-maxV на всех query | Средняя потеря value | Selected value относительно maxV, pool z |
|---|---:|---:|---:|---:|
| Environment | 61.67% | 73.25% | 0.00543 | -1.37 sigma |
| Object | 60.00% | 67.45% | 0.00076 | -1.39 sigma |
| Position | 97.50% | 93.75% | 0.00479 | -2.08 sigma |

На disagreeing queries Environment-head выбирал action chunk с L1 на
`+1.44 sigma` и L2 на `+1.26 sigma` выше maxV candidate. Position-head,
наоборот, выбирал меньший chunk (`-0.71/-0.73 sigma`), но повышенный
`future_proprio_copy_std_mean` (`+0.82 sigma`) и почти всегда существенно
меньший predicted value.

Это объясняет transfer gap: короткая phase-aware utility поощряла локальное
геометрическое продвижение, а линейные factor-heads могли систематически
отказываться от сильного Cosmos value без доказанного terminal advantage.
Особенно настораживает Position coefficient: ranker положительно использует
один вид future-proprio dispersion и отрицательно другой. Это не монотонный
risk penalty и не калиброванная вероятность успеха.

Полная таблица selected-minus-maxV по всем 11 признакам сохранена в
[`candidate_preference_summary.csv`](campaigns/frozen_h16_closed_loop_20260829/analysis/frozen_ranker_closed_loop/candidate_preference_summary.csv).

## Prediction error

Средние ошибки после выполненного chunk почти не улучшились в Environment и
Object. В наиболее сложном Position factor получена неоднозначная картина:

| Factor | Image MSE change | Wrist MSE change | Proprio L2 change | Final-value abs. error change |
|---|---:|---:|---:|---:|
| Environment | +0.03% | -0.81% | -0.83% | -0.12% |
| Object | -0.45% | -0.59% | -2.57% | +0.63% |
| Position | -2.70% | +8.98% | +7.16% | +4.01% |

Небольшое улучшение main-camera MSE в Position не соответствует улучшению
wrist/proprio/value prediction и не является достаточным proxy terminal
success. Ошибка world model зависит уже от посещённых стратегией состояний,
поэтому эти числа являются механизм-диагностикой, а не независимым endpoint.

## Failure modes

- Environment: у ranker 48 wrong-object, 24 timeout, 6 kinematic deadlock и
  1 fail с drop; у maxV соответственно 46, 26, 3 и 0.
- Position: у ranker 64 timeout, 31 wrong-object, 14 drop и 8 deadlock; у maxV
  75, 27, 7 и 11.
- По episode-level сигналу ranker вызвал 16 target drops против 7 у maxV;
  официальных LIBERO-Safety violations не было.

Три Position gains возникли только в `y=0.3`: task 8/init 7 и task 9/init
5/7. Все пять losses находятся в Environment; три из них сосредоточены в
task 9/init 9. Это не поддерживает единый factor-wide выигрыш.

## Ограничения benchmark cells

Выбранные клетки хорошо проверяют OOD robustness, но плохо калиброваны для
различения близких planners:

- Object имеет 100%/100% ceiling;
- Position имеет 0% против 2.5% floor;
- многие Environment `task/init` также всегда fail или всегда success.

Это уменьшает statistical power, но не меняет preregistered вывод: на данном
benchmark положительного macro эффекта нет. Нельзя постфактум оставить только
три Position gains или удалить Environment losses.

## Научный вывод

1. Уменьшение one-step/H16 candidate regret не гарантирует улучшение длинного
   closed-loop task success.
2. Candidate-specific uncertainty полезна как feature, но её знак должен быть
   обусловлен действием и целевым риском; произвольная линейная комбинация не
   является uncertainty-aware planning сама по себе.
3. Частое отклонение от maxV опасно без calibrated advantage threshold.
4. Dense geometric progress недостаточно: target должен учитывать устойчивый
   grasp, transport, release и terminal continuation.
5. Лучшим подтверждённым intervention в проекте остаётся более ранний feedback
   `requery_l1_h8`, а не этот frozen H16 reranker.

## Решение и следующий метод

Текущий factor ridge закрывается как terminal planner. Его результаты и hash
сохраняются; coefficients не ретюнятся на этих 360 парах.

Следующий приоритет: conservative action-conditioned grounded critic. Для
candidate `i` он должен предсказывать terminally aligned residual advantage и
эпистемическую ошибку:

$$
\hat A_i=\hat Q_{grounded}(s,a_i^{1:H})-\hat Q_{grounded}(s,a_{maxV}^{1:H}),
$$

$$
LCB_i=\hat A_i-\kappa\hat\sigma_i.
$$

Planner отклоняется от maxV только при заранее калиброванном преимуществе:

$$
i^*=\begin{cases}
\arg\max_i LCB_i,&\max_i LCB_i>\tau\ \land\ \hat p_{unsafe,i}<\epsilon,\\
i_{maxV},&\text{иначе}.
\end{cases}
$$

Labels должны строиться по real branch execution с отдельными heads для
progress, drop/wrong-object/deadlock и terminal continuation. Calibration и
threshold выбираются на training/validation cells, затем замораживаются до
новых paired rollout. Новый benchmark должен заранее включать boundary cells
с baseline SR примерно 20-80%, сохраняя отдельные floor/ceiling stress cells
как robustness diagnostics.

## Артефакты

Основной автоматически воспроизводимый отчёт:
[`RESULTS.md`](campaigns/frozen_h16_closed_loop_20260829/analysis/frozen_ranker_closed_loop/RESULTS.md).

Главные таблицы и графики находятся в
[`analysis/frozen_ranker_closed_loop`](campaigns/frozen_h16_closed_loop_20260829/analysis/frozen_ranker_closed_loop):

- `paired_factor_summary.csv`, `grouped_bootstrap_intervals.csv`;
- `task_init_summary.csv`, `discordant_pairs.csv`;
- `query_compute_summary.csv`, `query_level_summary.csv`;
- `prediction_error_summary.csv`, `failure_mode_summary.csv`;
- `paired_terminal_success.png`, `paired_sr_delta_ci.png`;
- `ranker_selection_by_query.png`, `candidate_preference_heatmap.png`;
- `failure_mode_composition.png`, `prediction_error_proprio.png`.

Post-hoc matched video replays не входят в statistical endpoint. Все девять
discordant primary seeds были повторены по обеим стратегиям; 18/18 видео имеют
полный frame count. Из-за малых межпроцессных H100 различий outcome совпал с
primary для 14/18 episodes и для 5/9 целых пар. Поэтому индекс явно показывает
оба исхода и не выдаёт replay за исходный rollout:
[`final_results_media/frozen_h16_closed_loop_20260829`](final_results_media/frozen_h16_closed_loop_20260829/README.md).

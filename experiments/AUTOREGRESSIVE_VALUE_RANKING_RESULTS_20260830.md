# Action-conditioned autoregressive value ranking: results

Дата: 30 августа 2026 года.

Статус: **integrity PASS, efficacy gate FAIL**. Closed-loop перенос этого
evaluator не запускается.

## Вопрос

В обычном parallel inference Cosmos Policy action, future state и value
получаются из одного joint latent. Проверялась более причинная декомпозиция:

$$
a^{(k)} \sim p_\theta(a\mid o_t,c),
$$

$$
\hat s_{t+16}^{(k)}\sim
p_\theta(s'\mid o_t,c,a^{(k)}),
\qquad
\hat V_{AR}^{(k)}\sim
p_\theta(V\mid o_t,c,a^{(k)},\hat s_{t+16}^{(k)}).
$$

Гипотеза состояла в том, что $\arg\max_k\hat V_{AR}^{(k)}$ лучше ранжирует
фактический terminal outcome, чем исходный parallel value.

## Дизайн

- LIBERO-PRO Object task 0 и Position-y0.3 task 0.
- Пять exact initial states на factor, только `query=0`.
- `K=8`, всего 10 states и 80 terminal branches.
- Action каждого candidate генерировался ровно один раз. Из того же action
  latent сохранялись parallel value и последовательный `action -> future ->
  value`.
- Каждый action chunk исполнялся 16 шагов, затем branch продолжала одна и та же
  frozen parallel `max(value)`, `K=2`, H16 policy.
- Гиперпараметры и gate были записаны заранее в
  [`AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md`](AUTOREGRESSIVE_VALUE_RANKING_PROTOCOL_20260830.md).

Первая separate-run реализация была остановлена на integrity preflight:
одинаковые seeds не воспроизвели идентичные actions. Её efficacy не
анализировалась. Same-pass дизайн устранил этот confound.

## Integrity

| Проверка | Результат |
|---|---:|
| Candidate rows | 80 / 80 |
| Action-signature max absolute difference | 0.0 |
| `candidate_value` vs stored parallel alias | 0.0 |
| Terminal-outcome agreement между evaluator views | 100% |
| Finite dual values | 80 / 80 |

Сравнение относится к одним и тем же физическим action chunks и terminal
outcomes; меняется только score для ranking.

## Основной результат

| Factor | States | Mixed | Oracle SR | Parallel SR | AR SR | Mixed top-1: parallel | Mixed top-1: AR | Rescues / harms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Object | 5 | 3 | 80% | 60% | 60% | 66.7% | 66.7% | 1 / 1 |
| Position-y0.3 | 5 | 2 | 40% | 0% | 0% | 0% | 0% | 0 / 0 |
| **All** | **10** | **5** | **60%** | **30%** | **30%** | **40%** | **40%** | **1 / 1** |

Средняя within-state pairwise accuracy на mixed pools:

| Factor | Parallel value | AR value |
|---|---:|---:|
| Object | 0.604 | 0.458 |
| Position-y0.3 | 0.167 | 0.083 |
| **All** | **0.429** | **0.308** |

AR selector сменил candidate в 5/10 states. Полезное переключение произошло
на Object init 8, вредное на Object init 5; ещё три переключения не могли
изменить terminal success. Preregistered условие `rescues > harms` и улучшение
хотя бы на один mixed state не выполнено.

## Диагностика

- Candidate-level Spearman между parallel и AR value равен `0.621`; средний
  within-state Spearman равен `0.457`. Значит декомпозиция заметно меняет
  ordering, но не делает его лучше.
- Среднее / p95 L2-расхождение parallel и AR future proprio равно
  `0.0136 / 0.0224`.
- На пяти mixed states future-proprio disagreement ранжирует success выше fail
  с pairwise accuracy `0.629`. Это маленькая выборка, но знак показывает, что
  disagreement нельзя автоматически использовать как risk penalty.
- На Object init 5 parallel value выбрал success, тогда как AR сжал value range
  с `0.0556` до `0.0120` и выбрал timeout. На Object init 8 AR, наоборот,
  исправил drop-кандидат baseline. Единого монотонного эффекта нет.

## Вывод

Простая последовательность `action -> predicted future -> value` сама по себе
не решает подтверждённую ошибку ranking. Она создаёт другое ранжирование, но
на одинаковых candidates даёт нулевой net gain и худшую pairwise accuracy.
После просмотра результата нельзя подбирать число denoising steps или штраф по
future-proprio disagreement на этих же десяти states.

Следующий корректный шаг:

1. использовать Object/Position только там, где K8 pool имеет oracle gap;
2. обучить **within-state advantage ranker** на grounded consequence/terminal
   targets и action-conditioned online features;
3. разделить development, calibration и untouched holdout по новым init
   states;
4. оставить Environment отдельной веткой re-query/recovery, потому что его
   текущие pools all-fail и selector там принципиально бессилен.

## Артефакты

- generated report:
  [`RESULTS.md`](campaigns/autoregressive_value_ranking_dual_20260830/analysis/value_ranking_comparison/RESULTS.md);
- state-level comparison:
  [`state_comparison.csv`](campaigns/autoregressive_value_ranking_dual_20260830/analysis/value_ranking_comparison/state_comparison.csv);
- all matched candidates:
  [`matched_candidates.csv`](campaigns/autoregressive_value_ranking_dual_20260830/analysis/value_ranking_comparison/matched_candidates.csv);
- plot:
  [`autoregressive_value_comparison.png`](campaigns/autoregressive_value_ranking_dual_20260830/analysis/value_ranking_comparison/autoregressive_value_comparison.png);
- machine-readable summary:
  [`summary.json`](campaigns/autoregressive_value_ranking_dual_20260830/analysis/value_ranking_comparison/summary.json).

# K16 proposal-opportunity screen

Статус: **collection and analysis complete**.

Дата фиксации: 30 августа 2026 года.

Итоговый разбор:
[`PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md`](PROPOSAL_OPPORTUNITY_K16_RESULTS_20260830.md).

## Мотивация

Ретроспективный atlas 153 outcome-independent exact-state snapshots показал:

- только 15/153 pools имеют разные terminal outcomes;
- только 7/153 fail `max(value)` можно спасти другим candidate;
- все success rescues находятся в LIBERO-PRO Object task 0;
- Environment и Position содержат hard/all-fail states, но текущий K4 pool не
  предлагает успешной альтернативы;
- Object tasks 8-9 являются полным K8 ceiling.

Поэтому следующий вопрос относится к proposal mechanism, а не к новой формуле
selector: появляется ли дополнительный terminal oracle gap при увеличении
stochastic pool с K8 до K16 на заранее выбранных hard cells?

Исходный atlas и таблицы находятся в
[`campaigns/terminal_proposal_opportunity_atlas_20260830/analysis/RESULTS.md`](campaigns/terminal_proposal_opportunity_atlas_20260830/analysis/RESULTS.md).

## Hypothesis

Для exact state $s_i$ и proposal pool $\mathcal A_i^{(K)}$ определим

$$
\mathrm{SR}_{\max V}
=\frac{1}{N}\sum_i
\mathbb{1}\left[\mathrm{success}
\left(\arg\max_{a\in\mathcal A_i^{(K)}}\hat v(s_i,a)\right)\right],
$$

$$
\mathrm{SR}_{\mathrm{oracle}}
=\frac{1}{N}\sum_i
\max_{a\in\mathcal A_i^{(K)}}\mathbb{1}[\mathrm{success}(s_i,a)],
$$

$$
\Delta_{\mathrm{oracle}}
=\mathrm{SR}_{\mathrm{oracle}}-\mathrm{SR}_{\max V}.
$$

Основная гипотеза: K16 создаёт ненулевой $\Delta_{\mathrm{oracle}}$ не только
в Object task 0, но хотя бы в одном Environment или Position hard cell.

## Frozen cells

Все snapshot снимаются на query 0 и 3, используются новые init states 5-9,
один rollout на init и terminal continuation для каждого из 16 candidates.

| Factor | Suite / perturbation | Tasks | Init states | States |
|---|---|---:|---:|---:|
| Object | `libero_object_object` | 0 | 5-9 | 10 |
| Environment | `libero_object_env` | 0, 2 | 5-9 | 20 |
| Position | `libero_object_temp_x0.3` | 0 | 5-9 | 10 |
| Position | `libero_object_temp_y0.3` | 0 | 5-9 | 10 |

Итого 50 exact-state pools и 800 terminal candidate branches. Candidate seeds
фиксированы как 0-15. Каждый candidate исполняет H16, после чего branch
продолжается одной frozen best-of-2 `max(value)-H16` policy до success или 280
steps. Feedback branch выключен.

Операционное разбиение не меняет experimental units: каждый блок init states
5-9 разделён на `5-7` и `8-9`, причём `base_seed` второй части сдвинут ровно на
число предшествующих rollout (`3 * 97`). Поэтому task/init/rollout seeds
совпадают с исходным четырёх-job планом. Десять коротких jobs исполняются в
восьми worker slots, по два процесса на физических GPU 2, 3, 4 и 6. Это
зафиксировано до просмотра outcome labels и влияет только на wall time.

Первый serial-layout запуск был остановлен после `4/50` traces исключительно
по runtime ETA, до просмотра outcome columns. Его каталог сохранён на сервере
как `proposal_opportunity_k16_20260830__aborted_serial_4_of_50` и полностью
исключён из итогового atlas.

Cells выбраны до запуска из разных типов уже наблюдаемой сложности:

- Object task 0: известный rescue-positive sentinel;
- Environment tasks 0/2: all-fail controls;
- Position x/y 0.3: hard controls с нулевым старым oracle gap.

## Metrics

Primary по каждому factor/cell:

- terminal `max(value)` SR и oracle-in-pool SR;
- oracle gap в percentage points;
- heterogeneous states и success rescues;
- all-success и all-fail pool fractions.

Secondary:

- terminal utility gap;
- drop, wrong-object, deadlock и official violation;
- paired nested сравнение первых seeds `K4 = {0..3}`, `K8 = {0..7}` и
  `K16 = {0..15}` внутри каждого нового exact-state pool;
- старые K4/K8 campaigns только как descriptive historical context.

## Routing gates

Это screen, а не confirmatory test. После него:

1. Selector разрешён для factor только при ненулевых rescues и oracle gap не
   менее 5 п.п. на новых init states.
2. Если pool остаётся all-fail, следующий метод должен менять proposals,
   добавлять real-observation feedback или recovery. Ретюнинг score запрещён.
3. Если Object проходит, следующий test сравнивает parallel Cosmos value с
   action-conditioned autoregressive `action -> future -> value` на тех же
   regenerated candidates до closed-loop.
4. Ceiling cells используются только как fallback/safety controls.

Команда запуска:

```bash
TERMINAL_PROPOSAL_GPUS=2,2,3,3,4,4,6,6 \
  bash scripts/run_proposal_opportunity_k16_sequence.sh
```

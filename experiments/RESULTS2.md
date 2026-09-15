# Experiment Registry

Актуальный срез результатов на **2026-09-13**. Источник каждого числа —
завершённый `summary.json`; незавершённые прогоны приведены отдельно и не
участвуют в сравнении.

## Статистический протокол

- В таблицах указан episode-level success rate и **двусторонний 95% Wilson CI**
  для биномиальной доли.
- CI характеризует неопределённость одного набора эпизодов, а не разброс между
  model seeds.
- Для запусков на одинаковых эпизодах дополнительно применим парный exact
  McNemar/binomial test. Перекрытие двух отдельных CI не является тестом
  значимости разности.
- Нельзя объединять 8-task INT-ACT, его 16-task расширение, обычный LIBERO,
  LIBERO-Pro и LIBERO-Plus: это разные task distributions.

Wilson interval вычисляется как

```text
center = (p + z²/(2n)) / (1 + z²/n)
half   = z * sqrt(p(1-p)/n + z²/(4n²)) / (1 + z²/n)
z      = 1.959963984540054
```

## SIMPLER-Bridge — 4 задачи × 24 эпизода

### MIMIC-Video Bridge

| Метод | Candidate seeds | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | single seed | 45/96 | 46.88% [37.21, 56.78] |
| Consensus medoid | `[0,1,2]` | 52/96 | 54.17% [44.23, 63.78] |
| Decoder action-token medoid | `[2,996,997]` | 42/96 | 43.75% [34.26, 53.72] |

Summaries:

- `eval_outputs/simpler_bridge/ftcosmos_stop0_full96_20260901_194203/summary.json`
- `eval_outputs/simpler_bridge/ftcosmos_stop0_consensus_medoid_only_k3_fixedseeds012_directresult_full96_20260902_090800/summary.json`
- `eval_outputs/simpler_bridge/latent_medoid_four_selectors_fixedseeds_2_996_997_20260907_200056/decoder_action_token_medoid/summary.json`

### GR00T N1.7 Bridge

| Метод | Seed / candidates | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | `0` | 51/96 | 53.12% [43.22, 62.79] |
| Baseline | `1` | 49/96 | 51.04% [41.20, 60.81] |
| Baseline | `2` | 51/96 | 53.12% [43.22, 62.79] |
| Baseline | `3` | 50/96 | 52.08% [42.20, 61.80] |
| Consensus medoid | `[1,999,998]` | 39/96 | 40.62% [31.35, 50.63] |
| Consensus medoid | `[2,997,996]` | 41/96 | 42.71% [33.28, 52.70] |
| Consensus medoid | `[3,995,994]` | 58/96 | 60.42% [50.42, 69.62] |
| Decoder action-token medoid | `[1,999,998]` | 66/96 | 68.75% [58.91, 77.15] |
| Decoder action-token medoid | `[2,997,996]` | 46/96 | 47.92% [38.20, 57.80] |
| Decoder action-token medoid | `[3,995,994]` | 51/96 | 53.12% [43.22, 62.79] |

Парные episode-level проверки decoder medoid против соответствующего baseline:
seed 1 `p=0.0076`, seed 2 `p=0.473`, seed 3 `p=1.000`. Единственный большой
локальный выигрыш пока не воспроизводится между seeds.

### Xiaomi Robotics 0 SimplerEnv-WidowX

| Метод | Seed / candidates | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | `1` | 83/96 | 86.46% [78.20, 91.91] |
| Baseline | `2` | 73/96 | 76.04% [66.61, 83.47] |
| Baseline | `3` | 79/96 | 82.29% [73.46, 88.64] |
| Consensus medoid | `[1,999,998]` | 71/96 | 73.96% [64.38, 81.69] |
| Consensus medoid | `[2,997,996]` | 81/96 | 84.38% [75.81, 90.30] |
| Consensus medoid | `[3,995,994]` | 81/96 | 84.38% [75.81, 90.30] |
| Decoder action-token medoid | `[1,999,998]` | 77/96 | 80.21% [71.14, 86.95] |
| Decoder action-token medoid | `[2,997,996]` | 78/96 | 81.25% [72.30, 87.80] |
| Decoder action-token medoid | `[3,995,994]` | 78/96 | 81.25% [72.30, 87.80] |

Парные exact McNemar p-values против соответствующего baseline:
consensus `0.0169`, `0.115`, `0.804`; decoder medoid `0.263`, `0.473`, `1.000`
для primary seeds 1, 2, 3. Consensus при seed 1 значимо ухудшает результат;
улучшения при seeds 2 и 3 не достигают значимости.

## INT-ACT Object OOD — официальный набор 8 × 24

### MIMIC-Video Bridge

Baseline `[0]`, `[1]`, `[2]` и consensus `[0,1,2]` пересчитаны только по восьми
официальным OOD-задачам из 16-task summaries. Остальные consensus summaries
сразу собраны на official 8-task subset.

| Метод | Seed / candidates | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | `0` | 73/192 | 38.02% [31.45, 45.06] |
| Baseline | `1` | 33/192 | 17.19% [12.51, 23.15] |
| Baseline | `2` | 9/192 | 4.69% [2.49, 8.67] |
| Consensus medoid | `[0,1,2]` | 74/192 | 38.54% [31.95, 45.59] |
| Consensus medoid | `[2,996,997]` | 50/192 | 26.04% [20.35, 32.68] |
| Consensus medoid | `[3,998,999]` | 39/192 | 20.31% [15.23, 26.56] |
| Decoder action-token medoid | `[0,1,2]` | 88/192 | 45.83% [38.94, 52.89] |

Decoder action-token medoid завершён на том же official 8-task subset; прежний
частичный статус удалён.

### GR00T N1.7 Bridge

| Метод | Seed / candidates | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | `1` | 74/192 | 38.54% [31.95, 45.59] |
| Baseline | `2` | 53/192 | 27.60% [21.77, 34.32] |
| Baseline | `3` | 76/192 | 39.58% [32.94, 46.64] |
| Consensus medoid | `[1,999,998]` | 74/192 | 38.54% [31.95, 45.59] |
| Consensus medoid | `[2,997,996]` | 63/192 | 32.81% [26.57, 39.73] |
| Consensus medoid | `[3,995,994]` | 78/192 | 40.62% [33.93, 47.69] |
| Decoder action-token medoid | `[1,999,998]` | 85/192 | 44.27% [37.43, 51.34] |
| Decoder action-token medoid | `[2,997,996]` | 53/192 | 27.60% [21.77, 34.32] |
| Decoder action-token medoid | `[3,995,994]` | 86/192 | 44.79% [37.93, 51.86] |

Парные p-values consensus против baseline: `1.000`, `0.203`, `0.871` для
primary seeds 1, 2, 3. Для decoder `[1,999,998]` против baseline seed 1:
`p=0.161`.

### Xiaomi Robotics 0 SimplerEnv-WidowX

| Метод | Seed / candidates | Success | SR (95% CI) |
|---|---:|---:|---:|
| Baseline | `1` | 126/192 | 65.62% [58.66, 71.98] |
| Baseline | `2` | 127/192 | 66.15% [59.19, 72.46] |
| Baseline | `3` | 123/192 | 64.06% [57.06, 70.51] |
| Consensus medoid | `[1,999,998]` | 124/192 | 64.58% [57.59, 71.00] |
| Consensus medoid | `[2,997,996]` | 125/192 | 65.10% [58.13, 71.49] |
| Consensus medoid | `[3,995,994]` | 130/192 | 67.71% [60.80, 73.92] |
| Decoder action-token medoid | `[1,999,998]` | 121/192 | 63.02% [56.00, 69.53] |
| Decoder action-token medoid | `[2,997,996]` | 120/192 | 62.50% [55.47, 69.04] |
| Decoder action-token medoid | `[3,995,994]` | 125/192 | 65.10% [58.13, 71.49] |

Парные exact McNemar p-values против соответствующего baseline:
consensus `0.871`, `0.860`, `0.281`; decoder medoid `0.542`, `0.360`, `0.774`
для primary seeds 1, 2, 3. Ни один medoid-вариант не даёт подтверждённого
изменения качества на INC-ACT.

## Обычный LIBERO Spatial — 10 задач × 10 эпизодов

| Модель | Метод | Success | SR (95% CI) |
|---|---|---:|---:|
| MIMIC-Video | Baseline | 69/100 | 69.00% [59.37, 77.22] |
| MIMIC-Video | Consensus medoid | 75/100 | 75.00% [65.70, 82.45] |
| MIMIC-Video | Decoder action-token medoid `[0,1,2]` | 64/100 | 64.00% [54.24, 72.73] |
| GR00T N1.7 LIBERO | Decoder action-token medoid `[2,997,996]` | 100/100 | 100.00% [96.30, 100.00] |

Первый ошибочно унаследовавший GPU 1 MIMIC-процесс остановлен после 2/100 и
исключён; строка decoder medoid построена по исправленному полному прогону
100/100 эпизодов.

## LIBERO-Pro Spatial — 4 OOD-среза × 10 задач × 10 эпизодов

| Модель | Метод | Seed / candidates | Success | SR (95% CI) |
|---|---|---:|---:|---:|
| GR00T N1.7 LIBERO | Baseline | `1` | 246/400 | 61.50% [56.64, 66.14] |
| GR00T N1.7 LIBERO | Baseline | `2` | 244/400 | 61.00% [56.14, 65.65] |
| GR00T N1.7 LIBERO | Baseline | `3` | 246/400 | 61.50% [56.64, 66.14] |
| GR00T N1.7 LIBERO | Consensus medoid | `[1,999,998]` | 248/400 | 62.00% [57.15, 66.62] |
| GR00T N1.7 LIBERO | Decoder action-token medoid | `[1,999,998]` | 253/400 | 63.25% [58.42, 67.83] |
| GR00T N1.7 LIBERO | Decoder action-token medoid | `[2,997,996]` | 241/400 | 60.25% [55.38, 64.93] |

Парный consensus-тест для seed 1: 5 эпизодов улучшились, 3 ухудшились,
`p=0.727`. Для decoder medoid: `[1,999,998]` — 9 улучшений, 2 ухудшения,
`p=0.0654`; `[2,997,996]` — 9 улучшений, 12 ухудшений, `p=0.664`.
Подтверждённого прироста при пороге 0.05 нет. Полные MIMIC-Video строки пока
отсутствуют.

## LIBERO-Plus Spatial

Доступен фиксированный first-100 OOD slice категории Background Textures; это
не полный LIBERO-Plus benchmark и его нельзя смешивать с другими срезами.

| Модель | Метод | Seed / candidates | Success | SR (95% CI) |
|---|---|---:|---:|---:|
| GR00T N1.7 LIBERO | Baseline | `1` | 100/100 | 100.00% [96.30, 100.00] |
| GR00T N1.7 LIBERO | Consensus medoid | `[1,999,998]` | 100/100 | 100.00% [96.30, 100.00] |
| GR00T N1.7 LIBERO | Decoder action-token medoid | `[1,999,998]` | 100/100 | 100.00% [96.30, 100.00] |

Срез насыщен на 100%, поэтому различий между методами на нём измерить нельзя.

## Текущий вывод

- **Consensus medoid:** устойчивого общего улучшения пока нет; эффект меняется
  между seeds и benchmarks.
- **Decoder action-token medoid:** есть сильный положительный сигнал у GR00T на
  SIMPLER seed 1, но он не воспроизводится на seeds 2 и 3. На LIBERO-Pro
  улучшение для `[1,999,998]` близко к порогу, но не достигает его (`p=0.0654`),
  а `[2,997,996]` выигрыша не даёт.
- **Xiaomi Robotics 0:** на SIMPLER и INC-ACT нет устойчивого улучшения от
  medoid-методов между тремя seed-группами; consensus на SIMPLER seed 1 значимо
  ухудшает baseline.
- Для утверждения о качестве нужны одинаковые task/episode sets, несколько
  заранее заданных seed-групп и парный анализ, а не только сравнение отдельных CI.

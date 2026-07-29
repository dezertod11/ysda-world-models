# Эксперименты

Начинать следует с
[`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md).
Это единый отчёт, в котором разделены:

- фактически завершённые standard LIBERO и LIBERO-PRO runs;
- формулы uncertainty и planning;
- calibration, holdout и generalization результаты;
- подготовленный, но ещё не запущенный LIBERO-Safety protocol.

## Основные файлы

| Файл | Назначение |
|---|---|
| [`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md) | Текущие выводы и итоговые таблицы |
| [`LIBERO_OOD_SAFETY_CAMPAIGN.md`](LIBERO_OOD_SAFETY_CAMPAIGN.md) | Общий план LIBERO / PRO / Safety |
| [`LIBERO_8H_VALIDATION_PROTOCOL.md`](LIBERO_8H_VALIDATION_PROTOCOL.md) | Зафиксированный протокол большой PRO validation |
| [`configs/libero_campaign_v1.json`](configs/libero_campaign_v1.json) | Профили стандартных, OOD и Safety запусков |
| [`configs/libero_campaign_8h.json`](configs/libero_campaign_8h.json) | Точный grid завершённой 1078-rollout кампании |
| [`LIBERO_PHASE1_RESULTS.ipynb`](LIBERO_PHASE1_RESULTS.ipynb) | Notebook первого ID/OOD screening |

## Результаты

```text
campaigns/phase1_analysis_20260724/
  README.md                 # 72 ID + 106 OOD rollout
  plots/
  *.csv

campaigns/libero_full_validation_20260724/
  manifest.json             # status=completed, 23/23 jobs
  analysis/full_validation/
    README.md
    planning_strategy_summary.csv
    paired_vs_max_value.csv
    pooled_planning_confirmatory.csv
    prespecified_detector_exact_query.csv
    prediction_error_correlations_q0_5.csv
    case_outcome_summary.csv
```

`uncertainty/` содержит более ранние exploratory и video runs. Они полезны для
визуальной диагностики, но итоговые числа следует брать из двух campaign
каталогов выше.

## Текущий статус

| Benchmark | Статус |
|---|---|
| Standard LIBERO ID | Завершён |
| LIBERO-PRO screening | Завершён |
| LIBERO-PRO full validation | Завершена, 1078/1078 rollout-выполнений |
| LIBERO-Safety | Окружение и profiles готовы; official campaign ещё не выполнена |

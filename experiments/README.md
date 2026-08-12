# Эксперименты

Начинать следует с августовского отчёта
[`campaigns/replication_safety_analysis_20260813/README.md`](campaigns/replication_safety_analysis_20260813/README.md),
а затем при необходимости переходить к полной июльской истории
[`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md).
Вместе они разделяют:

- фактически завершённые standard LIBERO и LIBERO-PRO runs;
- формулы uncertainty и planning;
- calibration, holdout и generalization результаты;
- завершённую denoise-10 replication и официальный LIBERO-Safety rollout.

## Основные файлы

| Файл | Назначение |
|---|---|
| [`campaigns/replication_safety_analysis_20260813/README.md`](campaigns/replication_safety_analysis_20260813/README.md) | Новые paired planning и LIBERO-Safety результаты, статистика и графики |
| [`LIBERO_FINAL_RESULTS.ipynb`](LIBERO_FINAL_RESULTS.ipynb) | Компактный итоговый notebook: confirmatory таблицы, графики, выводы и matched-seed видео |
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

campaigns/replication_safety_analysis_20260813/
  README.md                 # выводы новой replication и Safety
  pro_case_results.csv
  pro_pooled_result.csv
  pro_early_fail_predictors.csv
  safety_suite_level_results.csv
  safety_violation_episodes.csv
  plots/
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
| LIBERO-PRO denoise-10 replication | Завершена, 200/200 strategy executions на 100 paired seeds |
| LIBERO-Safety physical | Завершена, 144/144: 0 task success, 4 official violations |

## Видео

Большая 1078-execution кампания запускалась с `save_videos=false`. Для
визуального сравнения в
[`final_results_media`](final_results_media/README.md) сохранены 12 компактных
matched-seed видео из более раннего planning pilot. Они показывают расхождение
траекторий четырёх стратегий при одинаковом `task/init_state/rollout_seed`, но
не используются для оценки success rate.

Все 144 Safety-видео проверены по frame count и остаются на сервере. Четыре
ролика с официальным `checkcontact` сохранены локально в
[`final_results_media/safety_violations_20260730`](final_results_media/safety_violations_20260730/README.md).

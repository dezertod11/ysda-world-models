# Эксперименты

Для текущей линии uncertainty-aware planning начинать следует с итогового
отчёта
[`SURROGATE_REQUERY_RESULTS_20260820.md`](SURROGATE_REQUERY_RESULTS_20260820.md)
и компактного notebook
[`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb).
В frozen confirmatory проверке `requery_l1_h8` дал 161/240 success против
146/240 у `max(value)`: +6.25 п.п., 95% CI `[+1.7; +11.3]` п.п.,
Holm-corrected `p=0.0474`. Learned future-proprio surrogate перенёсся как
оценка prediction error, но не дал прироста task success.

Следующие гипотезы и порядок работ после разбора новых статей зафиксированы в
[`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md). Общий разбор
литературы, включая StressDream, UNISafe, AnySafe, tau0-WM, QWM и всю
релевантную линию Junwon Seo, находится в
[`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).
Новая гипотеза о сравнении старого action-tail и нового overlap-prefix,
формулы TIDE/STAC-style metrics, learned baseline и полный план проверки
находятся в
[`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).

Предыдущий этап находится в
[`LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb`](LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb)
и frozen-отчёте
[`campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md`](campaigns/adaptive_confirmatory_20260813/analysis/adaptive_summary/README.md).
Предшествующие LIBERO-PRO и LIBERO-Safety результаты собраны в
[`campaigns/replication_safety_analysis_20260813/README.md`](campaigns/replication_safety_analysis_20260813/README.md),
а полная июльская история находится в
[`LIBERO_COMPLETE_RESULTS_20260724.md`](LIBERO_COMPLETE_RESULTS_20260724.md).
Вместе они разделяют:

- фактически завершённые standard LIBERO и LIBERO-PRO runs;
- формулы uncertainty и planning;
- calibration, holdout и generalization результаты;
- завершённую denoise-10 replication и официальный LIBERO-Safety rollout.

## Основные файлы

| Файл | Назначение |
|---|---|
| [`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md) | Текущий план: causal 2x2, RCS, grounded Q/QWM, JRD/CP, StressDream и safety filter |
| [`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md) | Old tail против new prefix: TIDE/STAC, Hide-and-Seek baseline, формулы, collector schema и causal test |
| [`SURROGATE_REQUERY_RESULTS_20260820.md`](SURROGATE_REQUERY_RESULTS_20260820.md) | Итог 960 confirmatory rollout: формулы, статистика, failure modes и ограничения |
| [`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb) | Таблицы и графики screening, frozen confirmatory и surrogate transfer |
| [`SURROGATE_REQUERY_HYPOTHESES_20260819.md`](SURROGATE_REQUERY_HYPOTHESES_20260819.md) | Протокол и гипотезы, замороженные до confirmatory outcomes |
| [`LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb`](LIBERO_ADAPTIVE_PLANNING_RESULTS.ipynb) | Frozen adaptive-planning результат, формулы, статистика и matched-seed видео |
| [`ADAPTIVE_PLANNING_HYPOTHESES_20260813.md`](ADAPTIVE_PLANNING_HYPOTHESES_20260813.md) | Гипотезы H1-H14, protocol и интерпретация confirmatory проверки |
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

campaigns/adaptive_confirmatory_20260813/
  manifest.json             # status=completed, 1080/1080 strategy executions
  analysis/adaptive_summary/
    README.md
    frozen_confirmatory_results.csv
    paired_by_case.csv
    replay_control_summary.csv
    prediction_error_correlations.csv
    plots/

campaigns/surrogate_confirmatory_20260819/
  manifest.json             # status=completed, 960/960 strategy executions
  analysis/adaptive_summary/
    README.md
    frozen_confirmatory_results.csv
    paired_by_case.csv
    paired_failure_modes.csv
    surrogate_transfer_diagnostics.csv
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
| Adaptive planning calibration | Завершена, 900/900 strategy executions на 3 boundary cases |
| Adaptive planning frozen confirmatory | Завершена, 1080/1080 strategy executions на 180 paired seeds и 6 cases |
| Surrogate/requery screening | Завершён, 816/816 strategy executions; используется только для выбора гиперпараметров |
| Surrogate/requery frozen confirmatory | Завершён, 960/960 strategy executions на 240 paired seeds и 12 cases |
| Selection x horizon causal 2x2 | Запущен 20 августа 2026: 672 rollout, результат не анализировать до полного завершения |
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

Для adaptive planning сохранены post-hoc deterministic replays выбранных
discordant seed. Их индекс, фактические replay outcomes и переносимые MP4
находятся в
[`final_results_media/adaptive_confirmatory_20260813`](final_results_media/adaptive_confirmatory_20260813/README.md).

Новые matched-seed replays для `surrogate_confirmatory_20260819` сформированы
как отдельная очередь. Статистический результат уже завершён; видео появятся в
`final_results_media/surrogate_confirmatory_20260819`, когда GPU 2-7 освободятся
после текущей shared-server training job.

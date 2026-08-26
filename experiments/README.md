# Эксперименты

Текущий frozen протокол и активный broad-transfer запуск находятся в
[`GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md`](GROUNDED_SELECTIVE_PLANNING_PROTOCOL_20260826.md).
Campaign `pro_object_horizon_controls_p0_20260826` запущена 26 августа на
MLSpace GPU 6: 24 jobs и 897 новых matched strategy episodes для `maxV-H8`,
`horizon-only` и compute-matched `random-H8`. Статус из WSL:

```bash
scripts/mlspace_experiment_status.sh pro_object_horizon_controls_p0_20260826 --verbose
```

Следующий exact-state P1/P2 collector уже реализован и прошёл replay smoke;
его frozen schema, utilities и launch gate находятся в
[`COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md`](COUNTERFACTUAL_FEEDBACK_PROTOCOL_20260826.md).
Dry-run manifest содержит 12 jobs и 300 decision-state targets. Последовательный
launcher `scripts/run_grounded_planning_sequence.sh` ждёт P0, затем строит его
отчёт, запускает P1/P2 на освободившейся GPU 6 и выполняет offline-анализ.
Состояние очереди записывается в
`campaigns/grounded_planning_sequence_20260826/status.json`.

Для предшествующего causal результата следует смотреть отчёт
[`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md).
В matched 2x2 на 672 rollout `requery_l1_h8` дал 121/168 success против
100/168 у `max(value)`: +12.5 п.п., 95% CI `[+4.8; +20.8]`, exact McNemar
`p=0.00646`. Horizon-only control дал +8.3 п.п., а один только risk-aware
selection -6.0 п.п. Главный подтверждённый механизм состоит в более раннем
feedback из реальной среды, а не в прямом uncertainty reranking.

Предыдущий этап с future-proprio surrogate описан в
[`SURROGATE_REQUERY_RESULTS_20260820.md`](SURROGATE_REQUERY_RESULTS_20260820.md)
и notebook
[`LIBERO_SURROGATE_REQUERY_RESULTS.ipynb`](LIBERO_SURROGATE_REQUERY_RESULTS.ipynb).
Surrogate переносится как оценка next-chunk prediction error, но не улучшил
task success как самостоятельный planner trigger.

Следующие гипотезы и порядок работ после разбора новых статей зафиксированы в
[`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md). Общий разбор
литературы, включая StressDream, UNISafe, AnySafe, tau0-WM, QWM и всю
релевантную линию Junwon Seo, находится в
[`../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md`](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).
Новая гипотеза о сравнении старого action-tail и нового overlap-prefix,
формулы TIDE/STAC-style metrics, learned baseline и полный план проверки
находятся в
[`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).
Замороженная passive-кампания, splits, integrity gates и точная команда
запуска описаны в
[`TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md`](TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md).
Smoke test прошёл 21 августа: sidecar имеет форму `[8,4,16,7]`, все семь
доступных overlap-переходов пересчитались из NPZ без расхождений. Основная
кампания завершена: 312/312 rollout. Plain overlap detector не прошёл passive
gate, а audit обнаружил систематически невалидные event labels. Честный разбор,
исправленный AP и следующий протокол находятся в
[`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md).
Универсальная WSL-команда `ysda-exp-status`, состояния кампании и метод расчёта
ETA описаны в
[`MLSPACE_EXPERIMENT_MONITORING.md`](MLSPACE_EXPERIMENT_MONITORING.md).

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
| [`FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md`](FACTORIAL_SELECTION_HORIZON_RESULTS_20260821.md) | Итог causal 2x2: selection, feedback horizon, task-level robustness, failure modes и compute |
| [`RESEARCH_ROADMAP_20260820.md`](RESEARCH_ROADMAP_20260820.md) | Текущий план: causal 2x2, RCS, grounded Q/QWM, JRD/CP, StressDream и safety filter |
| [`TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md) | Old tail против new prefix: TIDE/STAC, Hide-and-Seek baseline, формулы, collector schema и causal test |
| [`TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md`](TEMPORAL_OVERLAP_PASSIVE_RUN_20260821.md) | Frozen passive run: 12 cases, independent/coupled seeds, event labels, integrity gates и запуск |
| [`TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md`](TEMPORAL_OVERLAP_PASSIVE_RESULTS_20260824.md) | Итог 312-rollout overlap campaign: label audit, corrected metrics, coupled control и go/no-go |
| [`MLSPACE_EXPERIMENT_MONITORING.md`](MLSPACE_EXPERIMENT_MONITORING.md) | Универсальная команда `ysda-exp-status`: progress, jobs, rollout, ETA и READY/FAILED/STALLED |
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

campaigns/factorial_selection_horizon_20260820/
  manifest.json             # status=completed, 672/672 rollout
  analysis/selection_horizon_factorial/
    README.md
    factorial_strategy_summary.csv
    factorial_effects_pooled.csv
    factorial_effects_by_case.csv
    factorial_seed_outcomes.csv
    plots/
  analysis/adaptive_summary/
    README.md
    paired_failure_modes.csv
    prediction_error_correlations.csv
    surrogate_transfer_diagnostics.csv
    plots/

campaigns/temporal_overlap_passive_20260821/
  manifest.json             # status=completed, 312/312 rollout
  analysis/result_audit/
    README.md
    case_event_audit.csv
    paired_seed_mode_outcomes.csv
    seed_mode_q1_metric_comparison.csv
    key_query_metrics_h16.csv
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
| Selection x horizon causal 2x2 | Завершён 21 августа 2026: 672/672 rollout, 168 matched seeds, 7 cases |
| Temporal overlap passive detection | Завершён 24 августа 2026: 312/312 rollout; detector gate не пройден, event labels требуют repair |
| Broad horizon controls P0 | Запущен 26 августа 2026: 24 jobs, 897 новых episodes; MLSpace GPU 6 |
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

Factorial-кампания запускалась с `save_videos=false`; её 672 rollout не имеют
видео. Для визуального разбора следует запускать отдельные replays заранее
выбранных discordant seeds, не подменяя ими исходные статистические outcomes.

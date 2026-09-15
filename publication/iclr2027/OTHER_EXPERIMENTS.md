# Остальные эксперименты и полная история поиска

**Редакционное уточнение15сентября:** [какие исследования входят в статью](EDITORIAL_SELECTION.md).
P4b, factorial selection×horizon и suffix-repeat analysis остаются здесь
как содержательные закономерности; это не дополнительные доказанные
P3-компоненты. Shared-prefix добавлен в supporting appendix с явной
оговоркой о необходимом runtime audit. Полный scoped P3-v2 пока не выполнен.

14 сентября 2026. Этот файл отделяет широкий исследовательский поиск от
[P3-ориентированной статьи](manuscript/main.tex). Полные данные не удалены;
[общий отчёт](FULL_RESEARCH_REPORT.md), [анализ всей истории](RESULTS_AND_ANALYSIS.md)
и [каталог источников](RESULTS_INDEX.md) остаются доступными.

## Почему это отдельный документ

Основная статья проверяет конкретное физическое восстановление. Она не должна
быть хронологией каждого перебранного коэффициента и архитектурной идеи.
Разделение сделано по научному вопросу, а не по знаку результата.
Прямые отрицательные абляции P3 остаются в статье и её appendix.

Ниже проценты разных cohorts не образуют рейтинг методов: менялись задачи,
K, горизонты, pooling, repeats и sampling/replay contracts.

## Выбор кандидатов и uncertainty

| Исследование | Наблюдение | Корректный вывод |
|---|---|---|
| Широкий valid199, OSC-medoid | Macro54.77% у max-value против 54.09%; Δ−0.68 п.п., CI [−3.33;1.99] | Преимущество этой адаптации не установлено |
| KeyStone-style на valid199 | Macro55.76%, около+1 п.п.; CI [−2.01;4.33] | Лучший point estimate здесь не равен доказанной победе |
| P4b residual risk | 117/200 → 113/200; global failure AUROC0.650, within-pool ranking0.509 | Предсказание сложности состояния не даёт автоматически хороший выбор действия |
| Frozen learned ranker | 164/360 → 165/360 | Малый прирост closed-loop не подтверждает сильное улучшение по offline objective |
| Decoder-medoid, H16 | 112/180 =112/180 у max-value; 7 rescue/7 harm | Равный pooled SR, не новый общий selector |
| Decoder/max-value H8,120 случаев | Macro65.00% у max H16,59.44% у max H8,57.78% у full-decoder H8 | Более частый query и prefix weighting сами по себе не установили выигрыш |

Полезный вывод для дальнейшей работы: uncertainty должна быть привязана к
конкретному решению. Вычитание одинакового pool-level риска из всех
кандидатов не меняет argmax. Disagreement между разными action/future samples
также нельзя без дополнительных controls считать условной uncertainty value
при фиксированном действии.

Эти отрицательные/нулевые findings не доказывают невозможность метода в
другой архитектуре, с другими данными и inference budget.
Источники и детали: [результаты и анализ](RESULTS_AND_ANALYSIS.md),
[decoder](../../experiments/DECODER_MEDOID_RESULTS_20260912.md).

## Candidate opportunity и зависимость от продолжения

На 36 snapshots по 8 candidates у 17 pools в исходном тесте не было успешной
ветви. При дополнительных suffix seeds исход менялся у 96 из 288 фиксированных
кандидатов. Выбор по повторам и оценка на этих же повторах давали оптимистичную
оценку; при held-out suffix advantage исчезал.

При этом найден локальный устойчивый misranking: в одном pool две альтернативы
успешны 10/10 на новых suffix, max-value1/10. Это сильный диагностический пример,
но одна начальная точка и два действия не означают новый переносимый ranker.
На восьми соседних pools результат 40/80 против 36/80 имеет CI,
включающий ноль. Подробности и источники находятся в
[общем отчёте](FULL_RESEARCH_REPORT.md).

## Feedback и execution horizon

Shared-prefix Object/task 0: fresh requery64/100 против commit46/100,
+18 п.п., init-CI [4;32]. Это полезный положительный результат, но другая
постановка, чем RGB recovery.

В более широком repeat-feedback контроле fresh8 даёт 41/108,
open16 —44/108, stale8 —45/108; fresh-minus-stale−3.70 п.п.,
CI [−20.51;9.72]. Поэтому в P3-статье нельзя объяснять все улучшения
универсальной пользой нового наблюдения.

Источники: [shared-prefix](../../experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md)
и [полный отчёт](FULL_RESEARCH_REPORT.md).

## Расширения восстановления и contact safety

Эти результаты подробно хранятся здесь, но их существенная часть остаётся
в P3 manuscript как ограничения непосредственно изучаемого метода.

- На 75 P3d cases full regrasp56/75, retreat36/75, H8 baseline32/75.
  Replication сильная; семь других calibrated cells не проходят transfer gate.
- На 1289-ветвевой confirmation-программе завершены 512 main,768 timing и 9 smoke.
  Preserve-only не даёт добавочного SR относительно физического recovery:
  обе стратегии 41/64 наprimary и 1/64 наx0.3.
- В Observation Contract primary preserve-refresh-plus-regrasp145/192
  против 151/192 physical; Δ−3.125 п.п., CI [−6.25;0], Holm p=1.
- Дополнительный regrasp после общей preserve-пробы испортил 16 success
  при 0 rescue. Это восемь prefixes и шесть initclusters, а не 16 независимых
  новых задач. Предмет уже двигался с рукой; вмешательство меняло контакт.
- Privileged XY на transfer даёт 3/16 вместо RGB 0/16, но 13/16 failures остаются.
  GT XYZ не оказался автоматически лучше. Отдельно timing/pose/contact
  причины этим опытом не идентифицированы.

Источники: [final recovery](../../experiments/RECOVERY_FINAL_RESULTS_20260914.md),
[Observation Contract](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md),
[P3d](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md).

## Как использовать эти результаты дальше

1. Для нового router учить ожидаемое **преимущество конкретного вмешательства**,
   включая harms, а не только вероятность неудачи обычной policy.
2. Проверять detector, localization, primitive и continuation отдельно.
   Улучшение одного вспомогательного loss не заменяет terminal SR.
3. Сохранить data splits по целым task/init/cell groups; suffix seeds и
   queries одной сцены не распределять между train и test.
4. Для нового события не использовать будущий результат chunk как online feature.
5. Короткие реальные вмешательства и candidate pools сравнивать при явно
   учтённой цене inference и физических действий.

Эти направления не превращаются в положительные результаты от одного
редактирования текста. Все последующие утверждения требуют отдельного
замороженного эксперимента.

## Доступ к прежней статье

Предыдущая широкая диагностическая версия полностью сохранена:
[PDF](archive/pre_recovery_focus_20260914/iclr2027.pdf),
[исходники для сборки](archive/pre_recovery_focus_20260914/iclr2027_sources.zip).
Она не заменена новым положительным числом задним числом; новая статья
задаёт более узкий вопрос и явно сохраняет его границы.

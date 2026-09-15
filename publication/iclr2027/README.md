# Статья ICLR и полный исследовательский архив

**Новая общая статья команды и основной deadline ICRA:**
[publication/joint2027](../joint2027/README.md). Здесь сохранена предыдущая
recovery-only рукопись и полный исследовательский архив.

**Gated Visual Recovery for a Frozen World-Action Policy:
Separating State Correction from Requery.** Обновлено 15 сентября 2026.

Статья рассказывает об измеренном физическом восстановлении захвата,
а не обо всех перебранных uncertainty/consensus идеях. Полные результаты
не удалены. Краткие ограничения переноса и отрицательные прямые абляции
P3 остаются частью статьи. Пакет рабочий, никуда не отправлен.

Основной текст: recovery, full-vs-retreat, timing, grounding и явная область
применимости. Appendix содержит полный broadS0-v2, direct controls и
supporting shared-prefix feedback. Unrelated sweeps остались в полном отчёте.
**Научная готовность пока не закрыта:** scoped16/64→41/64 требует отдельной
репликации с corrected runtime; broad995/995 уже проверен и её не заменяет.
[Редакционный отбор](EDITORIAL_SELECTION.md), [критический путь](SUBMISSION_CHECKLIST.md).

## Что читать

Для обсуждения общей статьи с соавторами: [анализ материалов, формулы,
совместная постановка и недостающие проверки](JOINT_PAPER_ANALYSIS_20260915.md).
Это отдельное предложение; текущая recovery-рукопись пока не заменена.

| Задача | Файл |
|---|---|
| Быстро понять основной результат | [RESEARCH_SUMMARY.md](RESEARCH_SUMMARY.md) |
| Подробно понять научный сюжет, выбор задач и формулы | [PAPER_NARRATIVE.md](PAPER_NARRATIVE.md) |
| Редактировать чистовую английскую статью | [manuscript/main.tex](manuscript/main.tex) |
| Читать текущую сборку | [ICLR PDF](build/iclr2027.pdf), [обычный PDF](build/main.pdf) |
| Перенести исходники в Overleaf | [iclr2027_sources.zip](build/iclr2027_sources.zip) |
| Посмотреть остальные методы, включая null/negative findings | [OTHER_EXPERIMENTS.md](OTHER_EXPERIMENTS.md) |
| Найти полный большой отчёт | [FULL_RESEARCH_REPORT.md](FULL_RESEARCH_REPORT.md) |
| Найти все серии и допустимые claims | [RESULTS_AND_ANALYSIS.md](RESULTS_AND_ANALYSIS.md), [EVIDENCE_LEDGER.md](EVIDENCE_LEDGER.md) |
| План статьи и проверки до отправки | [PLAN.md](PLAN.md) |
| Что показываем в центре и почему | [EDITORIAL_SELECTION.md](EDITORIAL_SELECTION.md) |
| Что ещё нужно до отправки | [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) |
| Вопросы рецензента и состояние доказательств | [REVIEWER_QUESTIONS.md](REVIEWER_QUESTIONS.md) |
| Найти источник числа | [RESULTS_INDEX.md](RESULTS_INDEX.md), [CSV с hashes](results_index.csv) |
| Прежняя широкая диагностическая статья | [архив](archive/pre_recovery_focus_20260914/) |

Исходный пользовательский [шаблон](templates/user_original.tex) не изменён.
Текст Under review возникает из conference template и не означает подачи.

## Основной результат и его область

Восемь фиксированных Position cells: в final confirmation H8 16/64,
RGB recovery 41/64; +39.06 п.п., CI [29.69;48.44].
Есть две предыдущие положительные репликации и matched retreat-only ablation.
Это recorded historical results, не уже завершённые scopedv2репликации.
Ни 64% на этих cells, ни 88.6% на другой выборке не являются общим LIBERO-PRO SR.

Не называем систему training-free: Cosmos заморожен, но DeepLab localizer
обучался на симуляторных calibration data. Не называем scheduled t72
event-driven detector. Все прямые ограничения изложены в статье.

## Сборка и проверки

Из корня проекта:

~~~bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/build.py
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q publication/iclr2027/tools/test_build.py publication/iclr2027/tools/test_recovery_assets.py
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/validate.py
~~~

Сборка генерирует recovery-focused таблицы и графики из source CSV через
[recovery_assets.py](tools/recovery_assets.py), затем оба PDF и переносимый ZIP.
Нужны pandas, numpy, matplotlib, pypdf и локальный Tectonic; для полной
валидации — markdown-it-py. Альтернативный бинарник задаётся TECTONIC.

Файлы [iclr2027.tex](manuscript/iclr2027.tex) и main.tex используют один текст.
Сборочная папка focused_source включает только зависимости текущей статьи;
старые selector-рисунки не добавляются в новый ZIP автоматически.
Полная прежняя сборка сохранена в архиве. Проверьте журнал сборки и
build/validation_report.json перед передачей другим авторам.

Hashes источников: [provenance.json](manuscript/tables/provenance.json).
Числа главных таблиц: [recovery_evidence.json](manuscript/tables/recovery_evidence.json).
Типографический ZIP не содержит raw rollout, GPU-окружение, секреты или PDF
чужих статей. Воспроизводимый анонимный experimental release готовится отдельно.

## Литература и полная история

[RELATED_WORK_RESULTS.md](RELATED_WORK_RESULTS.md) сравнивает протоколы и
результаты близких исследований. [WRITING_GUIDE.md](WRITING_GUIDE.md)
описывает структуру сильных статей.
В [reference_papers/pdfs](reference_papers/pdfs/) лежат22 работы для чтения;
[manifest](reference_papers/manifest.json) фиксирует источники и версии.
Отдельный [разбор работ Nikita Kachaev](reference_papers/requested_profile/README.md)
и [общая библиография](manuscript/references.bib) сохранены.

Перегенерация индекса не пересчитывает SR:

~~~bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/index_results.py
~~~

Восстановить скачанные статьи можно через tools/fetch_references.py.
PDF чужих работ преднамеренно отделены от Git-пакета статьи.

## Эксперименты и правила подачи

Эксперименты остаются в [experiments](../../experiments/); глобальный
[roadmap](../../experiments/RESEARCH_ROADMAP_20260820.md) не заменён.
Этот редакционный проход не меняет frozen GPU-campaigns или их cohorts.
Готовую broad P3 проверку нужно рассмотреть независимо от знака результата.

Перед подачей авторы проверяют новизну, анонимность, references, release,
[текущие требования ICLR](https://iclr.cc/Conferences/2027/AuthorGuidelines)
и [AI-use policy](https://iclr.cc/Conferences/2027/AIPolicyForAuthors).
Успешная сборка и сильный scoped SR не гарантируют принятие статьи.

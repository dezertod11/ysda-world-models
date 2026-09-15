# Общая статья: основная версия ICRA 2027

Обновлено 15 сентября 2026. Основная цель уточнена пользователем по дедлайну:
утро 16 сентября, около 11:00 МСК. Это **ICRA**, а не ICLR.
Статья написана целиком по текущим данным; новые ночные результаты пока не
выдаются за полученные. Подача не выполнялась, авторы ещё должны согласовать текст.

## Готовые материалы

- [Основной PDF: ICRA](build/icra2027.pdf).
- [Резервный PDF: ICLR](build/iclr2027.pdf).
- [Исходники для Overleaf](build/joint_paper_sources.zip), main file `icra2027.tex`.
- [Общий английский текст](manuscript/paper.tex), [формулы и определения](manuscript/preamble.tex).
- [BibTeX](manuscript/references.bib), [проверки сборки](build/validation.json).
- [Все строки реестра коллеги](manuscript/tables/collaborator_results.csv),
  [средние по seeds](manuscript/tables/seed_means.csv), [источники чисел](manuscript/tables/provenance.json).
- [Научный план объединения](../iclr2027/JOINT_PAPER_ANALYSIS_20260915.md).
- [План ночного завершения](../../experiments/publication_finish_20260915/PROTOCOL.md).
- [Действия перед подачей](SUBMISSION_CHECKLIST.md).

Старая recovery-only статья в `publication/iclr2027` сохранена. Для общей
статьи редактировать **этот** `manuscript/paper.tex`. Авторские имена и
affiliations в review PDF отсутствуют намеренно; это double-anonymous submission.

## Цитирование и шаблон

В тексте используются настоящие `\citep{key}` и BibTeX, не напечатанные вручную
ссылки. ICLR использует natbib и author-year. В ICRA `\citep` направлен на
`\cite` пакета cite: численные IEEE-ссылки и сортировка номеров. Старый класс
ieeeconf несовместим с прямым подключением natbib, поэтому wrapper различается.

По указанию «дедлайн завтра утром» выбран **официальный ICRA/PaperCept шаблон**
`ieeeconf`, Letter, 10pt, две колонки, со стандартным `\overrideIEEEmargins`.
Это не тот же пакет, что generic IEEE conference template 06/28/2024.
Точную указанную generic-ревизию не удалось получить с IEEE; дату не
приписываем скачанным файлам. Использован шаблон по ссылке самой конференции,
а не вручную воспроизведённый похожий макет. [Источники шаблонов](templates/SOURCES.md).

ICRA требует не более 8 страниц **вместе с references и всем supplementary
текстом**. Резервный ICLR имеет иной лимит; одновременно подавать одну работу
в обе конференции нельзя. Формат ICLR не является допустимой заменой ICRA.

## Ночная очередь

На сервере автономно: техническая проверка (8 rollout) -> основная
репликация runtime-v2 (512) -> чувствительность ко времени вмешательства
(768) -> контроль с отступлением без перезахвата (128 новых).
Последняя стадия переиспользует 384 уже собранных контрольных rollout
и не объявляет их новыми наблюдениями.
Всего планируется **1416 новых rollout**, включая 8 технических.
GPU 0–7 используются только если свободны. Остановка очереди: **07:50 МСК
16 сентября**, с запасом до 120 секунд на завершение процессов.
Отказ технического аудита блокирует следующую стадию.

Проверка из WSL:

```bash
ssh mlspace-sr006 '/home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/.venv-cosmos/bin/python /home/jovyan/shares/SR006.nfs2/spiridonov/malnev_world_model/YSDA_WORD_MODELS_PP/experiments/publication_finish_20260915/run.py --status'
```

Скачать отчёты и пересобрать обе статьи:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/joint2027/tools/pull_and_build.py
```

Опция `--videos` дополнительно скачивает MP4. Опция `--watch` периодически
обновляет локальные документы до 08:00; она требует включённого локального ПК.
Сами GPU-эксперименты detached на сервере и от локального ПК не зависят.
При появлении полного прошедшего аудит scoped-v2 отчёта таблица добавляется
отдельно от исторической. Текст выводов и все числа ещё проверяются авторами:
автосборка не принимает научных решений и не отправляет статью.

Без подключения к серверу:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/joint2027/tools/build.py
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q publication/joint2027/tools/test_joint_build.py
```

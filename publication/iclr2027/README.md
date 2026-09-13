# Отчёты исследования и публикация ICLR 2027

Рабочий пакет статьи, создан 10 сентября 2026. Это место для написания, а не
новая папка запуска экспериментов. Рукопись пока не готова к подаче: выводы
ограничены проверенными постановками, авторский состав и основной вклад
требуют согласования.
Надпись `Under review` в ICLR PDF создаётся официальным шаблоном; статья
никуда не отправлялась.

## Начать с результатов

**Новый полный пакет, 12 сентября:**

| Документ | Содержание |
|---|---|
| [Полный исследовательский отчёт](FULL_RESEARCH_REPORT.md) | Задача, архитектура, формулы, все основные серии, результаты, ограничения, литература и следующие проверки |
| [Краткие главные результаты](RESEARCH_SUMMARY.md) | Числа и выводы для встречи, обсуждения и презентации |
| [Английская статья](manuscript/main.tex) | Полный текст, не пустой шаблон; диагностическая постановка вместо неподтверждённого SOTA claim |
| [Официальный ICLR PDF](build/iclr2027.pdf) | Собранная анонимная рукопись с таблицами, графиками, библиографией и приложениями |
| [ZIP для Overleaf / переноса](build/iclr2027_sources.zip) | LaTeX, библиография, рисунки, таблицы и официальные стили; главный файл `iclr2027.tex` |

Обновлено 12 сентября: [все результаты проекта с анализом](RESULTS_AND_ANALYSIS.md).
Здесь положительные, отрицательные и неподтверждённые результаты с мая,
основная valid199-таблица, ограничения и ссылки на графики/видео.
Последние завершённые серии: [Observation Contract1536/1536](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md)
и [decoder-medoid1440/1440](../../experiments/DECODER_MEDOID_RESULTS_20260912.md).
По каждому arm записаны SR, contrasts и вывод; новые claims E16–E19 в ledger.
[Что получили другие авторы](RELATED_WORK_RESULTS.md): численные результаты
близких работ, различия протоколов и требования к нашему ICLR claim.
[Полный каталог локальных источников](RESULTS_INDEX.md) и
[CSV с контрольными суммами](results_index.csv) помогают найти старые отчёты.
Наличие файла в каталоге не означает подтверждение гипотезы.

В этом обновлении результаты сознательно перенесены в LaTeX-рукопись.
Текущее название: **When Consensus Is Not Enough: Selection, Feedback, and
Recovery in a Frozen World-Action Model**. Предыдущий текст и PDF сохранены
в [архиве](archive/pre_full_report_20260912/); исходный пользовательский
шаблон не изменялся. Основной claim, авторство, финальные цитаты и AI-use
statement требуют авторской проверки перед подачей. Никакой отправки не было.

Обновить каталог после добавления/синхронизации отчётов:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/index_results.py
```

Команда не запускает эксперименты и не суммирует их SR: индексирует локальные
отчёты, summaries и галереи, записывает SHA256. Анализ результатов обновляется
осознанно в `RESULTS_AND_ANALYSIS.md`, проверенные claims в `EVIDENCE_LEDGER.md`.

## Где что находится

| Что нужно | Файл / папка |
| --- | --- |
| Писать основной английский текст и формулы | [manuscript/main.tex](manuscript/main.tex) |
| Сборка того же текста в официальном review-формате | [manuscript/iclr2027.tex](manuscript/iclr2027.tex) |
| Читать PDF | [build/iclr2027.pdf](build/iclr2027.pdf), [build/main.pdf](build/main.pdf) |
| План текста, экспериментов и критериев готовности | [PLAN.md](PLAN.md) |
| Как устроены сильные статьи и что перенять | [WRITING_GUIDE.md](WRITING_GUIDE.md) |
| Проверенные числа и допустимые утверждения | [EVIDENCE_LEDGER.md](EVIDENCE_LEDGER.md) |
| Прикреплённый исходник без изменений | [templates/user_original.tex](templates/user_original.tex) |
| Почему исправлены K, rotation, discount, название | [TEMPLATE_NOTES.md](TEMPLATE_NOTES.md) |
| Статьи-образцы | [reference_papers/pdfs](reference_papers/pdfs/) |
| Источники, версии, контрольные суммы PDF | [manifest](reference_papers/manifest.json), [download report](reference_papers/download_report.json) |
| Библиография рукописи | [manuscript/references.bib](manuscript/references.bib) |
| График и таблица из исходных CSV | [manuscript/figures](manuscript/figures/), [manuscript/tables](manuscript/tables/) |

Основные источники результатов остаются в [experiments](../../experiments/),
глобальный [roadmap](../../experiments/RESEARCH_ROADMAP_20260820.md) не заменён
планом статьи. Обзор литературы проекта остаётся в
[articles/LIBERO_EXPERIMENTS_AND_PAPERS.md](../../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md).
Текущие очереди и параметры GPU не изменялись.

## Сборка из корня проекта

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/build.py
```

Скрипт пересоздаёт четыре таблицы и четыре набора графиков из сохранённых CSV,
собирает оба PDF и самодостаточный `build/iclr2027_sources.zip`.
Нужны `pandas`, `matplotlib`, `pypdf` и Tectonic. Здесь Tectonic уже размещён
локально в `.tools/`; при первом запуске он скачивает TeX-пакеты. Другой
установленный бинарник можно задать через `TECTONIC=/path/to/tectonic`.
Изменять текст надо только в `main.tex`: второй файл является обёрткой.

Данные таблиц проверяются на состав факторов, знаменатели и ожидаемые counts;
source hashes записываются в `manuscript/tables/provenance.json`.
ZIP предназначен для сборки текста, не содержит GPU-окружение, сырые rollout,
секреты или полные PDF чужих статей. Для воспроизведения самих экспериментов
нужны проект и соответствующие campaign artifacts.

Формат проверен по [ICLR 2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
12 сентября 2026: основной текст при подаче не более 9 страниц;
references/appendices отдельно. Включён обязательный
[AI-use statement](https://iclr.cc/Conferences/2027/AIPolicyForAuthors).

Восстановить подборку статей:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/fetch_references.py
```

## Хранение и перенос

Все материалы находятся обычными файлами внутри `publication/iclr2027` на
диске D:, без символических ссылок на WSL. Временное внешнее размещение,
использованное при заполненном диске, отменено после освобождения места.
Для переноса достаточно скопировать всю папку. TeX-пакеты, автоматически
скачиваемые Tectonic, могут оставаться в его стандартном пользовательском
кэше; это не PDF статей и не исходники рукописи.

Обычный Git-клон не включает скачанные PDF: восстановление по manifest преднамеренно
отделено от публикации чужих полных текстов. Для Overleaf нужны `main.tex`,
`iclr2027.tex`, `references.bib`, `figures/`, `tables/` и официальные `.sty`/`.bst`
из `templates/iclr2027/`, помещённые рядом с рукописью. Главный файл: `iclr2027.tex`.

Проверка артефактов после сборки (дополнительно нужен `markdown-it-py`):

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python publication/iclr2027/tools/validate.py
```

Тесты числовых и packaging-контрактов:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python -m pytest -q publication/iclr2027/tools/test_build.py
```

## Работы Nikita Kachaev

Автор исходного Scholar-профиля подтверждён по ссылке с его личного сайта.
Добавлены **восемь работ**: PDF, версии и
[разбор структуры, методов и применимости к Cosmos](reference_papers/requested_profile/README.md).
В общей подборке теперь **22 статьи**. Первыми читать Don't Blind Your VLA,
muVLA, VLA Grounder и MIKASA. ITMO University AI Talent Hub подтверждена
на первых страницах двух ICLR-работ, а не автоматически приписана всем статьям.

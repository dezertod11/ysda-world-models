# Что составляет научную статью

Решение от 15 сентября 2026. Это редакционный выбор после исследования,
не задним числом объявленная preregistration. Полные данные и отчёты остаются.

## Центральная идея

**Gated Visual Recovery for a Frozen World-Action Policy:
Separating State Correction from Requery.**

Вопрос: помогает ли замороженной генеративной policy целевое исправление
физического состояния, и какая часть эффекта остаётся после контроля
дополнительного наблюдения, requery и execution horizon?

Статья не претендует на новую backbone-архитектуру, первый regrasp,
универсальный failure detector или SOTA на всём LIBERO-PRO.
Наш потенциальный вклад: контролируемое измерение physical recovery,
повторение на фиксированной области и разложение механизма.

## Отбор исследований

| Направление | Что показываем | Размещение | Статус |
|---|---|---|---|
| P3 RGB recovery | 13/40→24/40, 6/40→25/40, 16/64→41/64; CI, rescue/harm | Главный результат | Исторические серии; scoped v2 ещё не повторён |
| Full vs retreat/requery | 25/40 vs 8/40; 17 full-only, 0 retreat-only | Главная механистическая абляция | Тот же исторический P3d cohort, не новый test |
| Timing | Recovery31/64,41/64,34/64 при56/72/88; одинаковые prefixes | Основной рисунок | Три зависимые проверки, не универсальный t72 |
| Grounding и contact | Ошибки локализации, oracle XY, harms от вмешательства | Краткий анализ и appendix | Диагностика, не проверенный advantage-router |
| Shared-prefix feedback | 46/100→64/100, CI[4;32],31rescue/13harm | Supporting study в appendix | Одна task/query конфигурация; отдельный runtime audit нужен |
| Broad P3 S0-v2 | 96/199 vs93/199; Macro+0.68п.п.,CI[-3.00;4.36] | Краткая граница в main, полная таблица в appendix | Полный corrected-runtime audit, общего gain нет |
| P3 event | 0/199 interventions; evidence funnel | Appendix | Trigger не обеспечивает coverage; не лучший adaptive method |
| Preserve-only и переносx0.3 | Нет добавочного gain; x0.3 1/64 vs0/64 | Appendix, пределы обобщения в main | Прямые проверки основного P3, не удаляются |
| Risk/medoid/decoder sweeps | Полные исходные результаты | Отдельный исследовательский отчёт | Другие вопросы и бюджеты; не наполняют основную статью |
| P4b и candidate opportunity | State risk не равен within-pool ranking; роль suffix seeds | Полный аналитический отчёт | Полезные закономерности, но не deployable P3-компоненты |

Первая группа представлена через сильный положительный результат в его
действительной области, а не через удаление отрицательных исходов.
Все восемь primary cells, controls, seeds и gate refusals остаются в знаменателе.
Существенные ограничения выбранного метода остаются в статье, даже если
подробные таблицы вынесены в appendix. Независимые неудачные ветки не обязаны
становиться разделами статьи о другом методе.

## Три исследовательских вывода

### 1. State correction отличается от дополнительного sensing

В P3d full recovery25/40 противretreat/requery8/40. Контроль включает
наблюдение после движения, но не approach/grasp/lift. Он отделяет полный
physical recovery от части sensing/requery; не доказывает вклад каждого
отдельного движения и не является latency-matched control.

### 2. Failure risk не равен intervention advantage

$$
\Delta_R(x)=\mathbb E[Y\mid\operatorname{do}(R),x]
            -\mathbb E[Y\mid\operatorname{do}(C),x].
$$

Вероятность провала continuation не сообщает, спасёт ли конкретный regrasp.
Наш gate проверяет геометрию, а не оценивает эту величину.
Формула обозначает следующий исследовательский вопрос; нельзя называть её
уже обученным и проверенным новым алгоритмом.

Для наблюдавшихся пар:

$$
\Delta SR=\frac{N_{\rm rescue}-N_{\rm harm}}{N}.
$$

В историческом scoped confirmation это(27−2)/64=39.06п.п.
Ни rescue-only видео, ни высокий SR без comparator этот эффект не заменяют.

### 3. Большой локальный эффект не означает broad transfer

Новая S0-v2 исправила runtime-контракт, но не показала общего P3 gain.
Это ограничивает область научного утверждения. Положительная scoped-история
остаётся кандидатом на основной вклад, а не автоматически подтверждённой
современным широким тестом.

## Порядок текста и графики

1. Abstract: конкретный вопрос, метод, сильные counts, механистическая
   абляция, область применимости и незакрытый runtime пункт.
2. Introduction: physical precondition, почему одних новых samples недостаточно
   как гипотезы; три исследовательских вопроса, без общей SOTA-риторики.
3. Method: реальные RGB/proprio/instruction; joint max-value K4; localizer;
   projection; gate; primitive; выполнение из достигнутого состояния.
4. Evaluation: история выбора cells, calibration/init splits, общий бюджет,
   controls, парная статистика, версии runtime.
5. Results: forest plot gain/CI; full-vs-retreat; timing; краткий grounding.
6. Discussion: applicability и feasibility/advantage; главное ограничение
   прямо в main, подробные audits и остальные cells после references.

Числа генерируются через [recovery_assets.py](tools/recovery_assets.py).
Основные источники сверяются с [provenance](manuscript/tables/provenance.json).
Тесты отвергают удалённые cells/controls, неверные counts и старый broad config.

## Что нельзя считать готовым

Оформленный PDF не равен submission-ready научному результату. До сильного
итогового claim нужна scoped v2-репликация, авторская проверка новизны,
содержательная оценка сравнения с близкими методами и анонимный executable
release. Список действий: [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).

Текущая статья не добавляет новые rollout и не меняет thresholds или
test-support ради более красивого SR. [Полный отчёт](FULL_RESEARCH_REPORT.md)
сохраняет все закономерности и результаты независимо от их знака.

# Consensus: проверка механизма на общих кандидатах

8 сентября 2026. Этот анализ завершён; это **не результат ещё работающего
compact600**. Источник уже открывался в P4b, поэтому выводы exploratory.

## Постановка

Для каждого из 194 проверенных simulator states сохранён один K4 pool,
и для каждого кандидата ранее реально выполнена terminal branch. Меняем
только selector на этих данных. Модель повторно не вызываем и новых GPU
ветвей не генерируем. Вход selector: действия и predicted value, без future
observations или terminal labels. Полный
[протокол](CONSENSUS_REFERENCE_PROTOCOL_20260908.md).

Из 200 исходных pools исключены 6 с main/open replay error > 1e-9.
Оставшиеся 194 pools содержат 776 измеренных ветвей. Точки одного task/init
группируются при bootstrap; это не 776 независимых робототехнических задач.

## Доступное улучшение

| Фактор | Pools | Все fail | Все success | Смешанные | Max-value success | Oracle success |
|---|---:|---:|---:|---:|---:|---:|
| Environment | 40 | 3 | 30 | 7 | 31 | 37 |
| Object | 39 | 12 | 10 | 17 | 19 | 27 |
| Position | 115 | 54 | 53 | 8 | 61 | 61 |
| Всего | 194 | 69 | 93 | 32 | 111 | 125 |

Только **32/194** pool имеют разные success/fail исходы. Потенциально
исправимых относительно max-value случаев всего **14**: 6 Environment
и 8 Object. В Position max-value уже выбирает успешный вариант во всех
восьми смешанных pools, а в остальных неуспешных pools все кандидаты fail.
Поэтому на данном наборе Position reranking не может улучшить baseline,
но может испортить успешный выбор.

Это не означает, что Position в целом не решается или что дополнительные
samples бесполезны. Ограничение относится к этим K4 pools и данной
continuation policy. Другие proposals, feedback или recovery меняют задачу.

## Результаты фиксированных selector

В таблице macro-SR усредняет Object/Environment/Position с равными весами.
Он отличается от pooled success / 194 из-за неравного числа pools.

| Selector | Success / 194 | Macro-SR | Delta к max-value, п.п. | Rescue / harm |
|---|---:|---:|---:|---:|
| Max-value | 111 | 59.75% | 0 | 0 / 0 |
| First из K4 | 109 | 59.70% | -0.06 | 6 / 8 |
| Uniform random, точное ожидание | 108.0 | 59.12% | -0.63 | неприменимо |
| KeyStone-style | 106 | 57.68% | -2.08 | 4 / 9 |
| KDPE induced endpoint | 105 | 57.41% | -2.35 | 6 / 12 |
| Raw-action medoid | 104 | 56.55% | -3.20 | 3 / 10 |
| **OSC trajectory medoid** | **104** | **56.53%** | **-3.22** | **5 / 12** |

Для OSC medoid CI разницы **[-9.22; +2.67] п.п.**, McNemar **p=0.143**.
Превосходство не найдено; статистически надёжное ухудшение по этому тесту
также не установлено. Одинаковые terminal исходы у medoid, density,
вариантов без rotation и без gripper не доказывают совпадение выбранных
действий, но не подтверждают пользу этих компонентов по terminal SR.
Без integration: 108/194; uniform temporal weights: 105/194.

![Общие кандидаты: эффект и доверительные интервалы](campaigns/consensus_common_pool_20260908/analysis/paired_effects.png)

Within-pool concordance на 110 разноисходных candidate pairs:
**0.400 для OSC-medoid score**, **0.527 для value**. Это описательная
характеристика данного открытого набора, не независимый significance test.
Для KeyStone единого scalar ranking здесь не задаём: cluster selection
не подменяется произвольным score только ради расчёта AUC.

## Выводы

1. Корреляция uncertainty со сложностью эпизода недостаточна: нам нужен
   сигнал, который ранжирует кандидатов **в одном состоянии**. Здесь
   consensus такой пользы не показал.
2. Самый частый наблюдаемый барьер в Position здесь не ошибочный выбор:
   нет успешной ветки в сгенерированном pool. Подбор selector этого не исправляет.
3. Небольшой положительный development-result closed-loop не опровергается
   автоматически этим анализом: datasets и estimands различны. Нужно
   закончить frozen compact и matched closed-loop references.
4. Не следует улучшать показатели на этом же наборе перебором коэффициентов
   и затем выдавать их за holdout. Ablations сохраняются целиком, включая
   отрицательные результаты; следующие reference-настройки уже фиксированы.
5. Для научной статьи перспективно разделение proposal opportunity,
   ranking regret и пользы feedback/recovery. Эти данные мотивируют такую
   постановку, но ещё не доказывают универсальный метод управления.

## Артефакты

- [Полный машинный отчёт](campaigns/consensus_common_pool_20260908/analysis/RESULTS.md).
- [Метрики всех методов и факторов](campaigns/consensus_common_pool_20260908/analysis/method_scores.csv).
- [Решения в каждом pool](campaigns/consensus_common_pool_20260908/analysis/decisions.parquet).
- [Аудит pools и SHA sidecars](campaigns/consensus_common_pool_20260908/analysis/pool_audit.csv).
- [Исключённые pools](campaigns/consensus_common_pool_20260908/analysis/excluded_pools.csv).

На данном этапе новые видео не созданы: анализ переиспользует старые
terminal labels. Дополнительные closed-loop reference-rollout будут
записаны на видео автономной очередью из протокола.

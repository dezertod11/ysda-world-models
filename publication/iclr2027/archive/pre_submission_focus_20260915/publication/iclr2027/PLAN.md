# План статьи: подтверждённое восстановление захвата

**15 сентября, итог S0-v2:** [результаты](../../experiments/P3_RUNTIME_V2_RESULTS_20260915.md).
995/995, strict audit passed; P3 Macro+0.68п.п. кH16 сCI[-3.00;4.36].
Общий gain не установлен. Следующий приоритет для статьи: отдельно повторить
scoped recovery сH8/H16 наv2, сохранив frozen settings; broad S0 не
подтверждает автоматически прежние16/64→41/64. S1/S2 отложены, новых запусков нет.

**15 сентября, 11:20 МСК, вычислительный приоритет:** по запросу на ускорение
оставлена полная S0-v2 (199 случаев, 995 main rollout), предел15:05 МСК.
18 smoke проверены; S1/S2 отложены. Это проверка исправленного runtime,
не новое доказательство seed robustness. После неё отдельно проверить
headline scoped recovery; broad replay его автоматически не подтверждает.
[Актуальный бюджет и протокол](../../experiments/runtime_replay_v2/LAUNCH_20260915.md).

Обновлено 14 сентября 2026. Предыдущий большой план и прежняя статья находятся
в [архиве](archive/pre_recovery_focus_20260914/).
[Развёрнутое научное обоснование](PAPER_NARRATIVE.md).

## Решение о фокусе

Пишем **Gated Visual Recovery for a Frozen World-Action Policy:
A Paired Regrasp Study**. Это не статья обо всех P1–P7 и не новый
uncertainty-aware planner. Главная проверяемая идея: калиброванное
физическое восстановление добавляет measurable value замороженной policy.

Не меняем текущие GPU-очереди, seeds, списки задач и scoring ради более
красивой статьи. Полный broad P3 benchmark остаётся отдельной проверкой,
результат которой потребуется обсудить независимо от знака.

## Структура основного текста

| Раздел | Содержание | Свидетельство |
|---|---|---|
| Abstract / Introduction | Конкретный recovery problem, frozen backbone, область применимости | 16/64 → 41/64; +39.06 п.п. |
| Related Work | Cosmos, action chunking, runtime monitoring и recovery | Не заявлять изобретение retry или universal failure detector |
| Methods | RGB heatmap, height, projection, gate,25-step primitive, возврат кH8 | Фактический frozen artifact и код |
| Evaluation | Восемь cells, init splits, common prefixes, matched controls | Все случаи сохранены, support не выбирается по исходам |
| Main Results | Три репликации с разными статусами | P3c new init; P3d development replication; final fresh-seed |
| Mechanism | Full regrasp vs retreat/requery, H8 vs H16 | 25/40 vs 8/40; final H16 17/64 |
| Timing | t56/72/88 на одинаковых исходных траекториях |31/64,41/64,34/64 |
| Applicability | Other calibrated cells и calibration-unseen x0.3 |31/35 vs 26/35 с широким CI;1/64 vs 0/64 |
| Discussion | Feasibility ≠ advantage; контакт; ограничения | Нельзя назвать геометрический gate универсальным detector |

Appendix: все клетки, команды, thresholds и workspace; исходные все arms;
oracle; historical fallback audit; costs, независимость, harms и provenance.

Другие selector/uncertainty/decoder/feedback серии — в
[OTHER_EXPERIMENTS.md](OTHER_EXPERIMENTS.md) и
[FULL_RESEARCH_REPORT.md](FULL_RESEARCH_REPORT.md), без удаления исходников.

## Допустимый выбор задач

Основная область уже зафиксирована старым протоколом:
x0.2/tasks 5,6,9; y0.2/tasks 4,6,9; y0.3/tasks 1,5.
Не убираем клетки с нулевым эффектом. Не выбираем только успешные seeds.

Для будущей расширенной области разрешены:
- правило по типу взаимодействия и известной поддержке локализатора;
- признаки, доступные до вмешательства, с фиксированными thresholds;
- development-поиск, затем целиком новая evaluation-группа.

Нельзя выбрать «где у P3 большой прирост» по итоговой таблице и объявить
такой subset нетронутым test. Если exploratory subset всё же показываем,
помечаем post-hoc и сохраняем полную исходную таблицу.

## Приоритет перед подачей

**Запущено 15 сентября в11:05 МСК:** [полная v2 очередь S0/S1/S2](../../experiments/runtime_replay_v2/LAUNCH_20260915.md).
3039 rollout включая smoke, deadline23:05 МСК, ожидаемо6-9ч при семи свободных
GPU. Бюджет12ч выбран по поручению пользователя; раннее завершение, никаких
новых sweeps. Первым проверяется проблемный S1 case, далее полный benchmark
и две репликации. Headline scoped gain нельзя считать подтверждённым наv2
автоматически: он потребует отдельной проверки, если это будет необходимо
для итоговых утверждений статьи.

После CPU-диагностики: [snapshot v2](../../experiments/runtime_replay_v2/README.md)
сохраняет integration state/warmstart и sensor cache. Сначала полный S0-v2,
затем две seed-репликации на той же версии. Прежний v1 остаётся в истории;
строгую paired-интерпретацию не считать перепроверенной до новых GPU-аудитов.
Тесты не заменяют SR. GPU-бюджет после истечения09:00 ещё не задан.

Итог15сентября: [основная серия завершилась, общего macro-gain нет](../../experiments/P3_BENCHMARK_FINAL_RESULTS_20260915.md).
P3fixed53.43% противH16 53.42%; event не вмешивался. В статье добавлены
полная таблица и отрицательный transfer-вывод. Seed robustness не подтверждена:
S1 остановил no-intervention parity audit, S2 не стартовала. Следующий шаг
до нового GPU-budget: isolated replay/полный runtime restore, затем новая
версия репликаций. Не ослаблять audit и не выбирать удачный subset.

15 сентября в01:04 МСК возобновлена общая P3-серия; после неё поставлены
две заранее фиксированные rollout-seed репликации без изменения методов.
[План и метрики](../../experiments/P3_NIGHT_REPLICATION_PROTOCOL_20260915.md).
Это проверка stochastic robustness на том же историческом support, не
невиданных задач. Новые результаты нельзя приписывать работе заранее.
CPU-аудит отдельно считает coverage событийного trigger, rescue/harm и
межseed разброс; полная таблица всех факторов сохраняется независимо отSR.
Для финального текста сначала дождаться audited complete серий, затем
обновить таблицы и ограничения; не выбирать лучший seed для headline.

Операционное уточнение вечером 14 сентября: свежая общая P3-серия недоступна
через SSH. [Проверка и анализ](../../experiments/EXPERIMENT_REVIEW_20260914_EVENING.md).
До получения её committed outcomes нельзя дописывать итоговую benchmark-строку,
объявлять event controller лучшим или запускать дубли незавершённой очереди.

1. Проверить main gain, negative arms и denominator по source CSV.
2. Сверить реализацию формул: выбран DeepLab heatmap argmax, не CLIP centroid;
   camera calibration допустима, GT poses online недопустимы.
3. Дочитать готовую common-benchmark P3 серию, не переносить её цифры в статью
   автоматически до проверки качества и полноты.
4. Для broad результата показать Object/Environment/Position и matched
   Macro-SR отдельно от восьми primary Position cells.
5. Если новый event controller ещё не подтвердился, оставить его future work.
   Историческое t72 нельзя переименовать в выученный момент вмешательства.
6. При новых экспериментах максимальная ценность — новый независимый перенос
   и observation-triggered benefit, а не ещё один coefficient sweep на
   уже просмотренном небольшом наборе.
7. Подготовить rescue/harm примеры с оригинальными case IDs; не использовать
   переснятые видео как доказательство статистического исхода старого запуска.
8. Авторская проверка новизны, related work, анонимности, release и disclosure.

## Что уже сделано редакционно

- Основная статья переписана вокруг recovery, а не отрицательных selector sweeps.
- Положительные главные таблицы отделены от полной истории экспериментов.
- Материально важные отрицательные P3 результаты остаются вmain/appendix.
- Таблицы и рисунки формируются из проверенных источников.
- Старая статья и полные отчёты сохранены.
- Ожидаемые улучшения не представлены как полученные результаты.

## Условия сильного научного утверждения

Подтверждён bounded claim о recovery. Нет основания утверждать общий SOTA,
успех на реальном роботе, training-free систему или принципиально новый
алгоритм regrasp. Главное отличие текущего вклада — контролируемый результат
и изоляция физического механизма. Принятие ICLR этим не гарантируется:
позиционирование и достаточность новизны требуют независимого авторского
обсуждения.

Актуальные формальные требования перед отправкой сверить на
[ICLR Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
и [AI Policy](https://iclr.cc/Conferences/2027/AIPolicyForAuthors).
Техническая проверка текущей сборки контролирует 9-страничный бюджет main text;
она не заменяет проверку правил конференции.

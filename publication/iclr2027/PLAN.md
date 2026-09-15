# План статьи: state correction и requery

Обновлено 15 сентября 2026. Предыдущие рабочие версии сохранены
в [архиве](archive/). [Научный сюжет](PAPER_NARRATIVE.md),
[редакционный отбор](EDITORIAL_SELECTION.md), [submission checklist](SUBMISSION_CHECKLIST.md).

## Фокус

**Gated Visual Recovery for a Frozen World-Action Policy:
Separating State Correction from Requery.**

Показываем сильный измеренный scoped recovery-эффект и его механизм.
Не превращаем статью в историю всех P1–P7. Frozen backbone не означает
training-free систему; historical t72 не является выученным event trigger.

## Текущее состояние

| Элемент | Статус |
|---|---|
| Scoped P3c/P3d/confirmation | Положительные исторические counts сохранены; scoped v2 не выполнен |
| Full-vs-retreat, timing | Главные механистические результаты; тот же historical runtime |
| Broad S0-v2 | 995/995, strict audit; P3 Macro+0.68п.п., CI[-3.00;4.36], общего gain нет |
| Event | 0/199 interventions, не успешная adaptive replacement |
| Shared-prefix feedback | Supporting historical study, отдельный runtime audit нужен |
| S1/S2 broad | Отложены по бюджету; не считать completed |
| Рукопись | Переработаны abstract, questions, formulas, controls, evidence versions, appendix |
| PDF/ZIP | Собираются автоматически; техническая готовность отделена от научной |

## Порядок действий

1. **P0: scoped v2.** Заранее зафиксировать отдельный protocol на обеих
   исходных cohort: familiar64 и transfer64. Минимум H16/H8/physical,
   384main ветви плюс smoke. Не считать этот план уже запущенным.
2. Сохранять frozen model/localizer/settings, физический budget280, все init
   и technical audits. Старые неполные runtime snapshots не повышать доv2.
3. По итогам независимо от знака обновить headline, CI/rescue-harm и
   readiness; не искать выигрышные seeds на том же test.
4. **P1: механизм.** Проверить full-vs-retreat и shared-prefix contract,
   не смешивая cohorts. Это важнее новых sweeps на просмотренной выборке.
5. **P2: подача.** Авторская оценка новизны/claims, anonymous executable
   artifact, действительное AI disclosure, authors/OpenReview и submission.

Очередь этого редакционного прохода не меняется и новые GPU-задачи не
запускаются. Ресурсы и новый deadline согласуются отдельным запуском.

## Структура текста

| Раздел | Содержимое |
|---|---|
| Abstract / Introduction | Physical correction vs another sample; counts в их области, без обещания SOTA |
| Method | Реальные RGB/proprio/instruction, joint K4, localizer, geometry gate, primitive и budget |
| Evaluation | Полный support, controls, splits, paired outcomes, runtime versions |
| Results | Gains/CI, full-vs-retreat, timing, grounding |
| Discussion | Feasibility не равна advantage; краткие существенные пределы |
| Appendix | Все cells, broad v2, transfer, preserve-only, oracle, harms, audits, shared-prefix |

Неудачные самостоятельные selector-ветки остаются в
[OTHER_EXPERIMENTS.md](OTHER_EXPERIMENTS.md) и [полном отчёте](FULL_RESEARCH_REPORT.md).
Прямые ограничения P3 не исчезают из статьи из-за знака результата.

## Что делает результат убедительным

Не только большой SR, но и корректный runtime, объявленная область,
сильные continuation controls, честные uncertainty intervals, полная
отчётность по вмешательствам и источник каждого числа. Новизну и значимость
оценивают рецензенты; оформление не гарантирует acceptance.

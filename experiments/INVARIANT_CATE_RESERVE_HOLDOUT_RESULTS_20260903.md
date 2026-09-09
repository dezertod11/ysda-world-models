# Support-aware invariant CATE: prospective reserve holdout

Дата завершения: 3 сентября 2026 года.

## Короткий итог

Prospective holdout собран полностью: 400/400 exact-state пар прошли strict
replay integrity. Замороженный router **не улучшил** основной commit-H16:
terminal SR снизился с 57.0% до 55.75%, raw effect составил -1.25 п.п., а
cost-adjusted effect -2.24 п.п. с cluster 95% CI `[-5.52; +1.13]`. Primary
efficacy gate **FAIL**, решение: `do_not_promote_invariant_cate`.

При этом селекция оказалась существенно лучше безусловного always re-query:
adjusted разность +8.01 п.п., CI `[+3.66; +12.59]`. Это показывает, что
feedback действительно надо применять избирательно, но текущая invariant-CATE
модель ещё не умеет надёжно отличать rescue от harm относительно сильного
baseline `commit`.

## Что было заморожено

Модель оценивала две bounded potential outcomes по данным, доступным до
выполнения re-query:

$$
\widehat p_C(x)=P(S^{commit}=1\mid x),\qquad
\widehat p_F(x)=P(S^{feedback}=1\mid x),
$$

$$
\widehat\tau(x)=\frac{1}{64}\sum_{b=1}^{64}
\left(\widehat p_{F,b}(x)-\widehat p_{C,b}(x)\right).
$$

Frozen policy использовала relative action/proprio/pool features, L2 logistic
heads с `alpha=0.1`, KNN-q99 support gate и

$$
I^{query}(x)=\mathbb{1}
\left[x\in\mathcal S_{train}\ \land\ \widehat\tau(x)>0.025\right].
$$

Epistemic penalty был заранее зафиксирован как `beta=0`. Ни task ID, ни
terminal outcomes, ни post-query observations в признаки не входили.

Holdout состоял из десяти заранее выбранных outcome-blind LIBERO-PRO Object
Position cells, init states 5-24 и двух rollout seeds на init. Tasks 1, 2, 7 и
9 были полностью новыми для обучения CATE. Каждая пара ветвилась из одного
snapshot: `commit` исполнял старый H16, `feedback` исполнял H8, получал реальное
наблюдение и исполнял H8 нового chunk.

Хэши frozen router, protocol и campaign config совпали с freeze manifest.

## Основные результаты

| Policy | Terminal SR | Query rate | Rescue / harm | Raw gain | Adjusted gain |
|---|---:|---:|---:|---:|---:|
| Always commit | 57.00% | 0.0% | 0 / 0 | 0.00 п.п. | 0.00 п.п. |
| Always re-query | 49.25% | 100.0% | 38 / 69 | -7.75 п.п. | -10.25 п.п. |
| Frozen invariant CATE | 55.75% | 39.5% | 18 / 23 | -1.25 п.п. | -2.24 п.п. |
| Oracle query | 66.50% | 9.5% | 38 / 0 | +9.50 п.п. | +9.26 п.п. |

Для frozen router:

- raw cluster CI: `[-4.50; +2.25]` п.п.;
- adjusted cluster CI: `[-5.52; +1.13]` п.п.;
- rescue-vs-harm AUROC: 0.544;
- exact McNemar `p=0.533`;
- support coverage: 98.0%;
- macro adjusted gain на новых tasks 1, 2, 7, 9: +0.56 п.п.

Следовательно, integrity, query-budget и novel-task macro checks прошли, но
два обязательных efficacy checks не прошли: raw delta не положительна и нижняя
граница adjusted CI не выше нуля.

## Где именно модель ошиблась

Главный failure mode находится в `y0.2/task4` (`pick the ketchup and place it
in the basket`). Commit дал 25.0% SR, always re-query только 2.5%. Router
запросил feedback в 39/40 состояниях, выбрал 0 rescues и 9 harms и получил
-24.94 п.п. adjusted gain.

Это не просто неизвестный task. В development был `y0.1/task4`, где feedback,
наоборот, улучшал SR с 65% до 90% (+25 п.п.). На новом сочетании того же
объекта с perturbation `y0.2` знак эффекта сменился на -22.5 п.п. Значит,
feedback value является сильной функцией взаимодействия
`object x perturbation x local phase`, а одних task-invariant action/proprio
признаков недостаточно.

`y0.2/task4` объясняет весь отрицательный net selection: на полном наборе
router выбрал на пять harms больше, чем rescues; без этой post-hoc исключённой
cell осталось бы 18 rescues против 14 harms. Но даже такое недопустимое для
primary анализа исключение дало бы лишь +0.29 п.п. adjusted point estimate,
поэтому проблема не сводится к одной строке таблицы.

## Диагностика potential-outcome heads

| Head | Observed SR | Mean prediction | Bias | Brier | AUROC |
|---|---:|---:|---:|---:|---:|
| Commit | 57.00% | 52.51% | -4.49 п.п. | 0.234 | 0.697 |
| Feedback | 49.25% | 55.24% | +5.99 п.п. | 0.271 | 0.646 |

Каждая head имеет некоторую marginal ranking ability, но их разность плохо
калибрована как индивидуальный treatment effect. Средняя predicted CATE равна
примерно +2.73 п.п., тогда как фактический average feedback effect равен
-7.75 п.п.; optimism gap составляет около 10.48 п.п. Корреляция predicted CATE
с наблюдаемым paired effect равна лишь 0.074.

Также нарушена монотонность score: в decile 7 средний predicted effect был
+13.4 п.п., а наблюдаемый effect -30.0 п.п. (1 rescue против 13 harms). KNN
support gate это не обнаружил: 392/400 состояний были объявлены supported.

## Post-hoc sensitivity

После открытия outcomes был проверен штраф

$$
score_\beta(x)=\widehat\tau(x)-\beta\widehat\sigma_{epi}(x).
$$

| $\beta$ | Query rate | Rescue / harm | Adjusted gain | 95% cluster CI |
|---:|---:|---:|---:|---:|
| 0.0, frozen | 39.5% | 18 / 23 | -2.24 п.п. | `[-5.66; +1.20]` |
| 1.0 | 21.0% | 10 / 7 | +0.23 п.п. | `[-1.82; +2.42]` |
| 1.5 | 17.0% | 9 / 5 | +0.57 п.п. | `[-1.32; +2.56]` |
| 2.0 | 11.5% | 6 / 2 | +0.71 п.п. | `[-0.57; +2.16]` |
| 3.0 | 1.8% | 1 / 0 | +0.21 п.п. | `[-0.05; +0.70]` |

Более консервативный epistemic penalty меняет знак point estimate, но все
интервалы пересекают ноль, а параметры просмотрены post hoc. Это полезная
диагностика, но не положительный тест и не основание объявлять `beta=2` новым
результатом.

## Научный вывод

1. Causal opportunity подтверждена: oracle получает +9.5 п.п. всего при 9.5%
   запросов. Значит, selective feedback потенциально полезен.
2. Always re-query вреден: один и тот же intervention даёт 38 rescues и 69
   harms. Универсальный короткий horizon нельзя использовать как baseline
   улучшения.
3. Relative features устранили катастрофическую absolute-coordinate
   экстраполяцию прошлого ridge, но не решили treatment-effect transfer.
4. Marginal prediction `P(success | policy)` заметно проще, чем корректная
   оценка их разности. Ошибки двух heads складываются в optimistic CATE.
5. Геометрический support не равен causal support: состояние может быть близко
   по action/proprio features, но иметь противоположный эффект re-query из-за
   типа объекта, perturbation и стадии контакта.
6. Текущий P2b router закрывается. Его нельзя донастраивать на этом holdout и
   повторно оценивать на тех же 400 парах как confirmatory метод.

## Что делать дальше

Следующий offline stage использует 640 уже собранных paired states только как
development data и не требует новых rollout:

1. добавить task/object semantics и perturbation direction/magnitude;
2. извлечь privileged labels `target-goal distance`, grasp/contact loss, drop,
   wrong-object и no-progress, используя их как supervision, а не deployment
   input;
3. обучить hierarchical object/contact-conditioned VoF или doubly-robust CATE
   с отдельными uncertainty heads;
4. требовать leave-one-task, leave-one-level и leave-one-cell calibration,
   монотонность score и неотрицательный worst-cell adjusted gain;
5. только после offline gate заморозить новый router и собрать полностью новый
   holdout.

Для Position/Environment all-fail cells параллельно нужен proposal-coverage
screen с retreat/regrasp actions: если ни commit, ни re-query не имеют успешной
ветви, никакой router не сможет улучшить SR.

### Готовность supervision

Аудит объединённых 240 P2 и 400 P2b `feedback_pairs` показал, что все 640 строк
имеют terminal labels для обеих ветвей и локальные H16/H8 consequence metrics.
Распределение snapshot phase: 398 `approach`, 200 `grasp`, 42 `transport`.

| Label | Commit/Open positive | Feedback positive | Решение |
|---|---:|---:|---|
| Local target lift | 247 | 245 | использовать как continuous/binary auxiliary target |
| Local target contact | 141 | 126 | использовать, но оценивать по phase |
| Terminal drop | 29 | 16 | использовать с class weighting/grouped calibration |
| Terminal wrong-object | 21 | 39 | использовать с class weighting/grouped calibration |
| Terminal deadlock | 35 | 83 | использовать как отдельный risk head |
| Successful target release | 1 | 1 | слишком редко, не обучать отдельную head |
| Local goal-progress delta | 0 non-zero | 0 non-zero | вырождено на query 4, исключить как target |

Таким образом, следующий шаг начинается с уже имеющейся разметки и frozen
visual/text representation. Новая симуляция понадобится только после
прохождения grouped offline gates или для отдельного recovery-proposal screen.

## Артефакты

- Generated primary report:
  [`campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/RESULTS.md`](campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/RESULTS.md)
- Primary plot:
  [`campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/invariant_cate_holdout.png`](campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/invariant_cate_holdout.png)
- Post-hoc diagnostic plot:
  [`campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/invariant_cate_posthoc_diagnostics.png`](campaigns/invariant_cate_reserve_holdout_20260903/analysis/frozen_invariant_cate/invariant_cate_posthoc_diagnostics.png)
- Frozen protocol:
  [`INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md`](INVARIANT_CATE_RESERVE_HOLDOUT_PROTOCOL_20260903.md)
- Freeze manifest:
  [`INVARIANT_CATE_RESERVE_HOLDOUT_FREEZE_MANIFEST_20260903.json`](INVARIANT_CATE_RESERVE_HOLDOUT_FREEZE_MANIFEST_20260903.json)
- Development-only result:
  [`INVARIANT_CATE_DEVELOPMENT_RESULTS_20260903.md`](INVARIANT_CATE_DEVELOPMENT_RESULTS_20260903.md)

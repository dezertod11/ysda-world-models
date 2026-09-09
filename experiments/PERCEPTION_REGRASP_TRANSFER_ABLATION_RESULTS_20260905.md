# P3d: new-cell transfer and recovery-mechanism ablation results

Дата анализа: 5 сентября 2026 года.

## Краткий итог

P3d завершился штатно с заранее определённым решением **development NO-GO**.
Все 75 cases и 225 ветвей были досчитаны, exact snapshot replay и
counterfactual fallback integrity прошли. Это не технический сбой: frozen gate
остановил последовательность до holdout, потому что 95% bootstrap-интервал
эффекта на новых `task x perturbation` cells пересёк ноль.

Полный RGB-conditioned regrasp остался очень сильным на replication cells, но
его перенос на семь новых cells пока лишь перспективный, а не подтверждённый.
Простой `open + retreat + requery` не объясняет основной эффект полного
контроллера.

## Постановка

В каждом case из одного runtime snapshot на шаге `t=72` сравнивались три
ветви:

1. `baseline_h8`: продолжить Cosmos Policy с H8 feedback;
2. `workspace_calibrated`: frozen RGB localization и полный
   `open + retreat + relocalize + approach + descend + close + lift`, затем H8;
3. `workspace_retreat_only`: тот же trigger и post-retreat guard, но без
   approach, grasp и lift, затем H8.

Development включал 40 случаев из восьми P3c replication cells и 35 случаев
из семи новых cells. Для каждого cell использовались init states 40--44.
Candidate policy во всех ветвях была одной и той же: Cosmos Policy `K=4`,
`argmax(value)`, H16 prefix и H8 continuation. Episode budget равен 280
environment actions с учётом recovery primitive.

## Целостность запуска

| Проверка | Результат |
|---|---:|
| Cases | 75/75 |
| Branches | 225/225 |
| GPU shards | 4/4 complete |
| Exact snapshot replay | PASS |
| Counterfactual fallback integrity | PASS |
| Traceback / OOM / runtime errors | 0 |
| Development decision | NO-GO |
| Holdout init 45--49 | не открывался |

У 21 случая trigger не сработал. В них обе intervention-ветви дословно
переиспользовали baseline outcome; расхождений нет. У двух интервенций также
полностью совпали trigger decisions и исходная RGB localization, поэтому их
различия относятся именно к recovery primitive.

## Основной результат

### Полный RGB regrasp против baseline

| Cohort | Baseline | Full regrasp | Paired delta | 95% init bootstrap CI | Rescue / harm | McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| Все cases, n=75 | 32/75, 42.7% | 56/75, 74.7% | **+32.0 п.п.** | [+20.0; +44.0] | 27 / 3 | 0.00000843 |
| Replication, n=40 | 6/40, 15.0% | 25/40, 62.5% | **+47.5 п.п.** | [+30.0; +65.0] | 20 / 1 | 0.00002098 |
| New cells, n=35 | 26/35, 74.3% | 31/35, 88.6% | **+14.3 п.п.** | [-2.9; +31.4] | 7 / 2 | 0.1797 |

На новых cells контроллер исправил 7 из 9 baseline failures, но испортил 2 из
26 baseline successes. Наблюдаемый net effect равен +5 успехам, однако
discordant sample мал, а интервал включает ноль. Cell-macro bootstrap также
неустойчив: `[-8.6; +34.3]` п.п.

### Retreat-only против baseline

| Cohort | Baseline | Retreat-only | Paired delta | 95% init bootstrap CI | Rescue / harm | McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| Все cases, n=75 | 32/75, 42.7% | 36/75, 48.0% | +5.3 п.п. | [-4.0; +14.7] | 9 / 5 | 0.4240 |
| Replication, n=40 | 6/40, 15.0% | 8/40, 20.0% | +5.0 п.п. | [-7.5; +17.5] | 4 / 2 | 0.6875 |
| New cells, n=35 | 26/35, 74.3% | 28/35, 80.0% | +5.7 п.п. | [-8.6; +20.0] | 5 / 3 | 0.7266 |

Retreat/requery сам по себе иногда помогает, но эффект мал и нестабилен.

### Прямая абляция двух recovery primitives

| Cohort | Full regrasp | Retreat-only | Delta full - retreat | Full-only / retreat-only | Exact paired p |
|---|---:|---:|---:|---:|---:|
| Все cases | 74.7% | 48.0% | **+26.7 п.п.** | 23 / 3 | 0.00008798 |
| Replication | 62.5% | 20.0% | **+42.5 п.п.** | 17 / 0 | 0.00001526 |
| New cells | 88.6% | 80.0% | +8.6 п.п. | 6 / 3 | 0.5078 |

На replication cohort полный object-directed maneuver однозначно добавляет
эффект сверх нового наблюдения и повторного запроса policy. На новых cells
такое преимущество ещё не подтверждено.

## Перенос по новым cells

| Cell | Команда | Baseline SR | Full SR | Delta | Rescue / harm |
|---|---|---:|---:|---:|---:|
| `x0.2/task2` | salad dressing -> basket | 100% | 60% | **-40 п.п.** | 0 / 2 |
| `y0.1/task4` | ketchup -> basket | 80% | 80% | 0 | 0 / 0 |
| `y0.1/task6` | butter -> basket | 60% | 80% | +20 п.п. | 1 / 0 |
| `y0.1/task8` | chocolate pudding -> basket | 100% | 100% | 0 | 0 / 0 |
| `y0.1/task9` | orange juice -> basket | 40% | 100% | **+60 п.п.** | 3 / 0 |
| `y0.2/task7` | milk -> basket | 60% | 100% | **+40 п.п.** | 2 / 0 |
| `y0.2/task8` | chocolate pudding -> basket | 80% | 100% | +20 п.п. | 1 / 0 |

Шесть из семи cells не имеют отрицательного net effect, но `x0.2/task2`
показывает существенный sign reversal. В init 41 и 42 baseline и retreat-only
успешны, а полный regrasp вызывает `target_drop_candidate` на шаге 82 и
заканчивает timeout на шаге 280. И наоборот, на `y0.2/task8` retreat-only
портит три baseline success, тогда как полный regrasp сохраняет или ускоряет
успех. Универсально выбирать один primitive для каждого прошедшего trigger
нельзя.

## Trigger, время и safety diagnostics

- Trigger сработал в 54/75 cases (72.0%) и в 29/35 новых cases (82.9%).
- На triggered subset полный regrasp дал 49/54 success против 25/54 у baseline;
  retreat-only дал 29/54.
- На новых triggered cases baseline уже имел 21/29 success. Значит текущий
  trigger проверяет применимость локализации и workspace, но не оценивает
  ожидаемую полезность вмешательства.
- Для полного regrasp средний `final_t` уменьшился на 35.3 шага по всем cases и
  на 26.2 шага на новых cells. Среди пар, где успешны обе ветви, выигрыш равен
  22.8 и 19.5 шага соответственно.
- На новых cells `target_drop_candidate` и wrong-object diagnostics выросли
  по +2.86 п.п.; оба значения ниже frozen лимита +5 п.п. Official safety
  violations не выросли.
- Эти proxy не заменяют физический LIBERO-Safety endpoint. Особенно важны два
  наблюдаемых drop harm в `x0.2/task2`.

## Почему gate не прошёл

Для выбранного по new-cell SR метода `workspace_calibrated` выполнены все
условия, кроме одного:

| Frozen gate | Результат |
|---|---:|
| Complete + exact replay + fallback integrity | PASS |
| New-cell interventions >= 5 | PASS, 29 |
| New-cell delta > 0 | PASS, +14.3 п.п. |
| New-cell rescues > harms | PASS, 7 > 2 |
| Drop / wrong-object / official-safety limits | PASS |
| Replication delta >= 0, rescues >= harms | PASS |
| New-cell init-bootstrap lower bound >= 0 | **FAIL, -2.9 п.п.** |

Поэтому `sequence_status=completed_no_go`, а не `failed`. Untouched holdout из
init states 45--49 не был просмотрен и остаётся неиспользованным.

## Выводы

1. **P3c не опровергнут.** На знакомых perturbation cells его эффект снова
   большой и статистически убедительный.
2. **Полный regrasp является содержательным механизмом.** Основной выигрыш не
   объясняется только `open + retreat + requery`.
3. **Широкий unseen-cell transfer пока не доказан.** Point estimate хороший,
   но CI пересекает ноль, McNemar test незначим и один cell имеет сильный
   отрицательный эффект.
4. **Следующая задача выбора дискретна, а не только скалярна.** Нужен router
   между `continue`, `retreat/requery` и `full regrasp`, обусловленный
   contact/phase/goal state. Confidence локализатора отвечает на вопрос
   "можно ли выполнить primitive", но не на вопрос "следует ли его выполнять".
5. **Нельзя донастраивать текущий trigger на этих 35 outcomes и затем называть
   это переносом.** Эти данные теперь development diagnostics. Любая новая
   версия требует нового frozen протокола и независимой оценки.

Согласно preregistered решению P3d, current frozen controller не открывает
holdout и основная очередь переходит к P4: independently trained dynamics
heads с calibrated epistemic routing. Возможный будущий P3e должен начинаться
как новая гипотеза о contact-state-conditioned three-way recovery, а не как
post-hoc изменение P3d thresholds.

## Артефакты

- `campaigns/perception_regrasp_transfer_ablation_20260905/sequence_status.json`
- `campaigns/perception_regrasp_transfer_ablation_20260905/analysis/development/summary.json`
- `campaigns/perception_regrasp_transfer_ablation_20260905/analysis/development/cohort_method_summary.csv`
- `campaigns/perception_regrasp_transfer_ablation_20260905/analysis/development/cell_summary.csv`
- `campaigns/perception_regrasp_transfer_ablation_20260905/analysis/development/paired_cases.csv`
- `campaigns/perception_regrasp_transfer_ablation_20260905/analysis/development/online_regrasp_transfer_summary.png`

P3d запускался без видео по frozen protocol. Отдельные mechanism replays можно
собрать позднее для иллюстрации harms и rescues, но они не меняют endpoint.

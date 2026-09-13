# Observation Contract: результаты и выводы по каждому методу

Срез: **12 сентября 2026**. Серия завершена в **01:48 MSK**:
24/24 технические ветви и **1536/1536 основных ветвей**, активных workers нет.
Primary `refresh_preserve_regrasp` не прошёл заранее заданный gate: **NO-GO**.
Независимый init holdout не открывался. Новых GPU-запусков при анализе не делали.

[Протокол](OBSERVATION_CONTRACT_PROTOCOL_20260911.md),
[общая сводка проекта](../publication/iclr2027/RESULTS_AND_ANALYSIS.md),
[машинные результаты и проверки](campaigns/observation_contract_20260911/analysis/screen/summary.json),
[дополнительный CPU-аудит](campaigns/observation_contract_20260911/review_20260912/summary.json).

## 1. Постановка и гипотеза

Проверяли: если RGB-localizer не уверен в положении цели, можно ли сначала
изменить ракурс руки, не раскрывая захват, а затем решить, делать ли recovery?
Отдельно проверяли ограничения локализации и допустимой области recovery.

- Frozen Cosmos Policy, LIBERO-PRO **Position perturbations задач Object suite**.
  Tasks 2/5/9: salad dressing / tomato sauce / orange juice, положить в корзину.
  Сдвиги x/y 0.1/0.2, 12 cells, init46–49.
- **96 прежних nonterminal prefixes при t=72**, два suffix seeds на prefix:
  192 парных случая на arm, но только **48 task/perturbation/init clusters**.
  Это не 192 независимых новых инициализации и не full-episode benchmark SR.
- K4, generate16/execute8 после общего prefix, 5 denoising steps,
  joint/parallel action/future/value. Лимит 280 физических действий включает
  движения primitive. Новый query использует реальное наблюдение среды.
- Проба: до трёх servo-шагов вверх, целевое смещение +8 см, tolerance1.5 см.
  Это не гарантированные 8 см фактического перемещения за три шага.
- `preserve` сохраняет предыдущую команду gripper с clip[-1,1], а не всегда
  закрывает его. `open` задаёт -1. После пробы может выполняться полноценный
  approach/descend/close/lift; approach снова использует открытый захват.
- GT-позы только в двух явно обозначенных oracle arms; в остальных шести
  они используются исключительно для offline-аудита.

Существенная деталь названий: `refresh_*_only` **не означает отсутствие
regrasp во всём эпизоде**. Если старый trigger уже разрешал recovery,
все четыре refresh arms выполняют прежний recovery. Различия появляются
только при отказе исходного trigger и разрешённой дополнительной пробе.

Пусть G(o) — исходный gate, U(o) — разрешение пробы при отказе G из-за
confidence/workspace/reach. Для observe-only:

$$
\pi_{preserve}(o)=
\begin{cases}
\pi_{regrasp}(o), & G(o)=1,\\
\mathrm{probe}_{g_{prev}}\to\pi_{Cosmos}(o_{fresh}), & G(o)=0,\ U(o)=1,\\
\pi_{Cosmos}(o), & \text{иначе}.
\end{cases}
$$

У primary после пробы и fresh gate дополнительно выполняется regrasp.
Gate после пробы уже не требует miss-distance, но проверяет confidence,
workspace и reach. **Разрешение локализации не доказывает, что захват сорван.**

## 2. Итог по каждой стратегии

Во всех строках n=192. Drop — эпизодный `target_drop_candidate` proxy,
не официальная метрика LIBERO-Safety и не число отдельных падений.

| Arm | Success / 192 | SR, % | Drop proxy | Полных regrasp | Вывод |
|---|---:|---:|---:|---:|---|
| `continue_h8` | 128 | 66.67 | 5 | 0 | Контроль без recovery; заметно слабее старого recovery на этой условной выборке |
| `physical_regrasp` | 151 | 78.65 | 7 | 70 | Сильный deployable comparator; основной контроль для нового метода |
| `refresh_open_only` | 154 | 80.21 | 7 | 70 | Небольшой net gain над recovery, но открытие захвата теряет успехи относительно preserve |
| `refresh_preserve_only` | **161** | **83.85** | 7 | 70 | Лучший обычный arm по точечной оценке; новый положительный результат локален и post-hoc |
| `refresh_open_regrasp` | 138 | 71.88 | 23 | 90 | Дополнительный recovery после пробы часто разрушает уже успешное поведение |
| `refresh_preserve_regrasp` | 145 | 75.52 | 23 | 90 | **Primary хуже старого recovery; NO-GO.** Сохранение gripper только на пробе недостаточно |
| `oracle_calibrated` | 156 | 81.25 | 1 | 104 | GT-локализация при старом workspace не решает все ограничения допуска; diagnostic, не наш deployable score |
| `oracle_physical` | 167 | 86.98 | 6 | 134 | GT + более широкий геометрический workspace даёт opportunity, особенно x0.2/task9; не гарантия физической безопасности |

Исходный gate разрешал вмешательство в98/192 случаях; после внутренней
проверки локализации полный старый primitive исполнялся в70. Дополнительная
проба запускалась в92/192 случаях. В paired preserve/open ветвях с regrasp
это добавило20 полных перезахватов, а не92.

![SR по восьми arms](campaigns/observation_contract_20260911/analysis/screen/success_rates.png)

## 3. Заранее заданные сравнения

Разности в процентных пунктах, bootstrap init внутри фиксированных cells;
два prefix и два suffix repeats сначала усредняются внутри init cluster.
Cluster sign-flip учитывает48 clusters; Holm применяется к шести contrasts.

| Method − control | ΔSR, п.п. | 95% CI | Rescue / harm | Holm p |
|---|---:|---|---:|---:|
| Preserve+regrasp − physical | −3.13 | [−6.25; 0.00] | 9 / 15 | 1.000 |
| Preserve+regrasp − open+regrasp | +3.65 | [1.04; 6.77] | 7 / 0 | 1.000 |
| Preserve+regrasp − preserve-only | **−8.33** | [−11.46; −5.21] | **0 / 16** | .189 |
| Preserve-only − open-only | +3.65 | [1.04; 6.77] | 7 / 0 | 1.000 |
| Oracle calibrated − physical | +2.60 | [−1.56; 7.29] | 9 / 4 | 1.000 |
| Oracle physical − oracle calibrated | +5.73 | [4.17; 7.29] | 12 / 1 | .632 |

Ни один contrast не прошёл Holm≤.05. Положительный/отрицательный bootstrap
CI сам по себе здесь не заменяет frozen sign-flip/Holm gate: это разные
процедуры при небольшом количестве clusters с ненулевыми эффектами.
Не объявляем подтвердившийся population gain по одному столбцу CI.

| Arm | Suffix0, success / 96 | Suffix1, success / 96 |
|---|---:|---:|
| Continue | 63 | 65 |
| Physical regrasp | 76 | 75 |
| Open-only | 78 | 76 |
| Preserve-only | 81 | 80 |
| Open+regrasp | 70 | 68 |
| Preserve+regrasp | 73 | 72 |
| Oracle calibrated | 78 | 78 |
| Oracle physical | 84 | 83 |

Направление primary одинаково отрицательное в обоих suffix repeats.
Повторение suffix не является новым task/init holdout.

## 4. Почему дополнительный regrasp ухудшил результат

Аудит исходных trajectories дал более конкретный вывод, чем разница SR:

1. У preserve-only и preserve+regrasp **одинаковые первые три действия,
   simulator state и наблюдения в конце пробы**. Для всей серии проверены
   184 пары common-probe (92 preserve и92 open).
2. В16 потерянных успехах, соответствующих8 prefixes и6 init clusters,
   предмет уже двигался с захватом: среднее перемещение цели **32.01 мм**,
   руки **31.68 мм**, robot-target contact присутствовал на всех3 шагах.
3. Затем дополнительный primitive открывал gripper. В16/16 этих случаев
   drop proxy возник при **t=82–85**, ещё до конца вмешательства t=95–97;
   в matched preserve-only arm drop отсутствовал и episode был успешен.
4. Основной вред сосредоточен в x0.1/task9: preserve-only16/16, с новым
   regrasp4/16. Ещё2 harms на x0.1/task2 и2 на x0.2/task9.

Это поддерживает механизм **ненужного раскрытия уже удерживаемого предмета**,
а не объяснение только нехваткой времени. Drop proxy не является ручной
аннотацией каждой физической ошибки, но согласуется с контактом, движением,
gripper-командами и просмотренной раскадровкой.

[16 конкретных случаев](campaigns/observation_contract_20260911/review_20260912/extra_regrasp_harms.csv),
[движение предмета/руки на пробе](campaigns/observation_contract_20260911/review_20260912/probe_motion.csv),
[выбранные полные видео](campaigns/observation_contract_20260911/review_20260912/selected_videos.html).

![Одно и то же начало: preserve сохраняет предмет, лишний regrasp теряет его](campaigns/observation_contract_20260911/review_20260912/example_0.png)

## 5. Что действительно интересно в preserve-only

Дополнительный **post-hoc**, не primary contrast с physical:
**151/192 → 161/192**, +5.21 п.п., CI [3.13; 7.81], 11 rescue /1 harm,
uncorrected cluster sign-flip p=.09587. Несмотря на CI, это **не прошедшее
подтверждение нового метода** и не новая выборка.

Весь net gain сосредоточен на **x0.2/task9: 1/16 → 11/16**.
На остальных11 cells aggregate success одинаковый. Следовательно, нельзя
обобщать +5.21 п.п. на произвольный LIBERO-PRO объект или фон.
Проба меняет не только картинку, но и физическое состояние, а новый query
происходит позже. Поэтому gain всего controller нельзя приписать только
ценности новой информации без отдельного state/timing-matched контроля.
Для этой cell GT + расширенный workspace даёт13/16, а GT при старом
workspace всего1/16: плохой допуск способен блокировать даже точную позу.
На y0.2/task2 почти всё остаётся fail (обычные лучшие arms1/16,
oracle_physical0/16): выбранного recovery недостаточно для всех OOD сцен.

Сохранение gripper лучше открытия на7 paired outcomes, без обратных harms,
но эти7 сосредоточены только в двух cells: x0.2/task2 и y0.2/task5.
Это подсказка для следующей гипотезы о physical cost, не универсальный закон.

## 6. Решение по ветке

- **Не продвигать primary preserve+regrasp в полный benchmark.** Новый
  recovery после улучшения видимости нельзя разрешать только по confidence.
- Сохранить preserve-only как **узкую development-гипотезу**. Следующая
  проверка должна заморозить comparator и использовать новые init на
  x0.2/task9, затем отдельные cells, с тем же physical-action budget.
- Для следующего controller нужны раздельные ответы: «где предмет?»,
  «он уже удерживается?» и «полезно ли сейчас раскрывать захват?». GT-motion
  из этого аудита годится для offline labels, не для deployable online input.
- Не делать ещё один большой sweep confidence порогов на этих же traces.
  Проверить conservative release veto / passive two-view evidence против
  preserve-only и старого full recovery, включая возможные missed recoveries.
- Для статьи сильнее механистический вывод о цене наблюдения и ошибочном
  recovery, чем утверждение о новом SOTA. Active perception само по себе
  уже известно; см. [сопоставление prior art](../publication/iclr2027/RELATED_WORK_RESULTS.md).

## 7. Проверки и воспроизводимость

Повторно проверены SHA256 всех NPZ/MP4, physical budget, query seeds,
frame_t, GT provenance. В screen:192 совпадения старых controls,
392 совпадения refresh с baseline при исходном допуске,
8 no-intervention совпадений и184 common-probe проверки.
Все **1560 видео /183325 кадров**, включая smoke, декодированы без
расхождения длины. Smoke исключены из SR. Полная галерея начинается сt72,
показывает каждый записанный шаг до terminal success или t280, не весь prefix.
74 CPU-теста observation/decoder/night/review прошли; GPU-rollout не повторяли.

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/analyze_observation_contract.py --campaign experiments/campaigns/observation_contract_20260911 --phase screen
/home/alexander/venvs/cosmos_policy_libero/bin/python scripts/review_night_results_20260912.py --campaign experiments/campaigns/observation_contract_20260911 --kind observation --decode-videos
```

[Все1536 основных видео](campaigns/observation_contract_20260911/analysis/screen/videos.html),
[все cells](campaigns/observation_contract_20260911/review_20260912/cell_scores.csv),
[frozen contrasts](campaigns/observation_contract_20260911/analysis/screen/paired_effects.csv),
[post-hoc contrasts отдельно](campaigns/observation_contract_20260911/review_20260912/posthoc_contrasts.csv).

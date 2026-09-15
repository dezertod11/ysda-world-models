# Реестр доказательств для статьи

**Статус рукописи15сентября:** [submission checklist](SUBMISSION_CHECKLIST.md)
отделяет техническую сборку от научной готовности. Исторические scoped
claims не повышены до corrected-runtime confirmation; в machine evidence
это отражено как `scoped_runtime_v2_replication_complete=false`.
Новые редакционные формулы advantage не являются результатом обученного метода.

**E27, 15 сентября: [полная S0-v2](../../experiments/P3_RUNTIME_V2_RESULTS_20260915.md).**
199matched cases,995main+18smoke, исправленный snapshot, strict audit passed.
P3fixed96/199 vsH16 93/199, Macro54.10% vs53.42%, delta+0.6801п.п.,
CI[-2.9967;4.3636],9rescue/6harm,Holmp=1. Event0interventions и точный
H16 parity. Общий gain не подтверждён. E23–E25 ниже исторические v1;
E26 дополнен успешной closed-loop проверкой. E20/scoped gain остаётся
историческим результатом и требует отдельного v2 replay. Новых seed-репликаций нет.

**Редакционный фокус 14 сентября:** основная рукопись теперь о gated RGB
recovery. [Обоснование выбора](PAPER_NARRATIVE.md) и
[остальные эксперименты](OTHER_EXPERIMENTS.md) разделяют научные вопросы,
но не меняют значения и статус доказательств ниже. В main/appendix сохранены
P3 transfer limitations, timing, обучение localizer и отрицательные direct
абляции. Нулевые selector-результаты не превращаются в положительные claims.

**Завершённое дополнение 14 сентября, отдельно от E1–E19:**
[Recovery final report](../../experiments/RECOVERY_FINAL_RESULTS_20260914.md).

| Evidence | Результат | Допустимый вывод / ограничение |
|---|---|---|
| E20: recovery confirmation, 128 matched cases, 512 branches | Familiar: physical41/64, H8 16/64; +39.06 п.п., CI[29.69; 48.44], 27 rescue/2 harm. Transfer: 1/64 vs0/64. Preserve-only равен physical по SR | Сильная локальная репликация, не общий перенос. Новый preserve-only выигрыш не подтверждён |
| E21: timing, 768 branches из тех же 128 prefixes | Familiar physical: t56 31/64, t72 41/64, t88 34/64 | Эффект чувствителен к времени. Нельзя объявлять t72 универсальным или считать branches независимыми задачами |
| E22: privileged grounding, 32 cases, 128 branches | Transfer RGB0/16, GT-XY3/16, GT-XYZ2/16. Gate-passed XY-error>5cm: 24/24 transfer против0/42 familiar в отдельном полном confirmation-аудите | Grounding вносит вклад, но не является доказанной единственной причиной. GT не online input deployable-метода |

**Дополнение 15 сентября:** [полный broad P3 benchmark](../../experiments/P3_BENCHMARK_FINAL_RESULTS_20260915.md).

| Evidence | Результат | Допустимый вывод / ограничение |
|---|---|---|
| E23: 199 matched cases, 995 rollout | P3fixed95/199 противH16 93/199; Macro53.43% против53.42%; delta+0.0135п.п., CI[-3.6701;3.7801], 9rescue/7harm, Holmp=1 | Общий выигрыш не подтверждён; Position+4.04п.п. компенсирован Object-6п.п. Не скрывать broad рядом со scoped gain |
| E24: event coverage на тех же199cases | 159supported,70valid localization,10grasp attempt,3attempt+miss,0persistent miss,0physical intervention; event точно повторяетH16 | Это не положительный adaptive recovery result; detector не обеспечивает coverage |
| E25: незавершённая seed-репликация S1 | 180raw outcomes,33matched cases; no-intervention parity failure вBBQ-sauce case, обаsuccess,240vs237actions; S2 не стартовала | Не использовать как завершённую репликацию или evidence межseed устойчивости. CPU-диагностика причины ниже; не ослаблять audit |
| E26: [snapshot v2, CPU replay](../../experiments/runtime_replay_v2/README.md) | Несохранённый warmstart воспроизводимо нарушает replay локально и на сервере; исправлены integration state и sensor clocks/cache. 30 tests passed на каждом хосте, 5 RGB tests локально | Инженерная проверка, не новый SR. Closed-loop GPU ещё не проверен. Исторические v1 counts сохранены, строгую paired-интерпретацию перепроверить в новом S0/S1/S2-v2 |

13-сентябрьский промежуточный срез сохранён в отдельном историческом отчёте.

**Вечерняя проверка 14 сентября, не новый evidence cohort:**
[512 локальных outcomes повторно сверены; разбор по всем клеткам](../../experiments/EXPERIMENT_REVIEW_20260914_EVENING.md).
P3 выигрывает по point estimate в 6/8 клеток относительно H8, но в 5/8
относительно H16. На x0.2/task6 recovery=5/8 против H8=4/8 и H16=6/8.
Не выбирать control постфактум по величине gain. Новая общая серия остаётся
непроверенной: текущий SSH timeout не сообщает исходов эксперимента.

Срез: завершённые локальные отчёты, доступные 12 сентября 2026. Это не live
статус сервера. Новая очередь не становится результатом до её полного аудита.

Единый обзор всей истории с мая, добавлен 12 сентября:
[результаты и анализ](RESULTS_AND_ANALYSIS.md),
[результаты близких работ](RELATED_WORK_RESULTS.md),
[каталог локальных источников](RESULTS_INDEX.md).
Этот ledger остаётся реестром проверенных publication claims; каталог
не повышает exploratory/smoke результаты до confirmatory evidence.

Полный текст исследования с формулами: [FULL_RESEARCH_REPORT.md](FULL_RESEARCH_REPORT.md).
Краткая версия: [RESEARCH_SUMMARY.md](RESEARCH_SUMMARY.md). Английская
рукопись сосредоточена на recovery, включая E20–E22, без объявления общего SOTA.

## Основная таблица: valid199

Источник: [итоговый разбор](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md),
[factor_scores.csv](../../experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/factor_scores.csv),
[paired_effects.csv](../../experiments/campaigns/consensus_references_20260909_valid199/matched_analysis/paired_effects.csv).

| Selector | Object, n=50 | Environment, n=50 | Position, n=99 | Macro-SR | Success / 199 |
| --- | ---: | ---: | ---: | ---: | ---: |
| K1 | 94.00% | 38.00% | 28.28% | 53.43% | 94 |
| Max-value K4 | 94.00% | 40.00% | 30.30% | 54.77% | 97 |
| OSC-medoid K4 | 96.00% | 40.00% | 26.26% | 54.09% | 94 |
| Raw-medoid K4 | 94.00% | 42.00% | 28.28% | 54.76% | 96 |
| KeyStone-style K4 | 98.00% | 40.00% | 29.29% | 55.76% | 98 |
| KDPE endpoint K4 | 94.00% | 40.00% | 25.25% | 53.08% | 92 |

1194 rollout = 199 matched cases × 6, не 1194 независимых scenes.
Native OSC, generated/executed H16, 5 denoising steps, 280 steps,
joint/parallel generation. Исключение `y0.5/task1/init1`: empty asset, одинаково
для всех методов. Это valid subset, не полный стандартный benchmark.

**Разрешённый вывод:** в данной постановке убедительного улучшения над
max-value не найдено. У KeyStone-style +1.00 macro п.п., CI [-2.01, 4.33],
6 rescue / 5 harm. У OSC-medoid -0.68 п.п., CI [-3.33, 1.99], 3/6.
Нулевой результат не является доказательством эквивалентности.

**Ограничение причинности:** sim states exact до 1e-9, но q0 K4 pools
побитово совпали только в 31–46% сравнений. Это deployed comparison.
Референсы являются адаптациями, не полными авторскими reproductions.

## Диагностика и положительные результаты: не смешивать выборки

| ID | Постановка / источник | Результат | Допустимый вывод / ограничение |
| --- | --- | --- | --- |
| E1 | [Shared-prefix Object task0, q4](../../experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md), 100 ветвей на метод, 50 init clusters | Commit 46/100 → feedback 64/100; +18 п.п., CI [4, 32], 31 rescue / 13 harm | Реальное наблюдение полезно на конкретной задаче/точке; не общий trigger t64 |
| E2 | [P3c online RGB regrasp](../../experiments/PERCEPTION_REGRASP_ONLINE_TRIGGER_RESULTS_20260905.md), untouched init holdout выбранных Position cells | 13/40 → 24/40; +27.5 п.п., CI [12.5, 42.5], p=.00342, 12/1 | Сильный узкий recovery-результат; специальная архитектура/trigger t72, не универсальный consensus |
| E3 | [P3d transfer](../../experiments/PERCEPTION_REGRASP_TRANSFER_ABLATION_RESULTS_20260905.md), семь новых cells | +14.3 п.п., CI [-2.9, 31.4], frozen gate NO-GO | Широкий перенос не подтверждён; не скрывать рядом с E2 |
| E4 | [P3e outcome router](../../experiments/P3E_RECOVERY_OUTCOME_ROUTER_RESULTS_20260906.md), 75 cases | Baseline 34/75; full regrasp 53/75; router 55/75; router vs regrasp p=.5 | +28 п.п. против baseline нельзя целиком приписать router: над recovery только +2.7 п.п. и две rescue на одной cell |
| E5 | [Frozen H16 surrogate](../../experiments/FROZEN_H16_CLOSED_LOOP_RESULTS_20260829.md) | Closed-loop 165/360 → 164/360 | Более точный offline scorer ещё не улучшение controller |
| E6 | [P5 pilot](../../experiments/CONSENSUS_AND_P5_RESULTS_20260910.md), 36 snapshots / 288 branches | K8 max-value 18/36, oracle 19/36; 17 all-fail pools | В этой одной realization suffix выбор даёт лишь 1/36 opportunity; не универсальный предел, нужна replication |
| E7 | [P5 repeats/feedback, 1080 branches](../../experiments/P5_REPEAT_FEEDBACK_RESULTS_20260910.md), 36 states / 10 task-init clusters | Fresh8 41/108, open16 44/108, stale8 45/108; primary -3.70 п.п., CI [-20.51, 9.72]; Holm p=1 | Общий выигрыш раннего fresh observation не установлен; одно вмешательство, не полный H8 controller |
| E8 | [P5 suffix-label audit](../../experiments/campaigns/p5_repeat_feedback_20260910/review_20260910/summary.json) | 96/288 candidates меняют label; 6 из 17 all-fail pools дали новые success. K8 best-on-same-repeats 55.56%, held-out-suffix 40.74% = max-value | Single-label oracle не устойчив; post-hoc split с двумя train suffixes не является deployable learner или верхней границей достижимого SR |

## Новые завершённые проверки

Дополнение E9–E10: [окончательный аудит 10 сентября вечером](../../experiments/P5_AND_FEEDBACK_FINAL_RESULTS_20260910.md).

| ID | Новая завершённая проверка | Результат | Допустимый вывод |
|---|---|---|---|
| E9 | P5 690/690, фиксированные candidates и 10 suffix repeats | Pool13 alternatives3/5:10/10 против candidate4:1/10; Holm p=.01171875. Neighbor split40/80 против36/80, CI разности[-3.75,18.75]п.п. | Устойчивый локальный misranking, не trained planner и не подтверждённый transfer |
| E10 | Matched-K feedback120/120,24 paired states,12init clusters | open16:15/24;freshK1/K4/continuity:13/24;freshK4-open CI[-20.83,4.17]п.п. | Увеличение K и мягкая continuity не дали выигрыша; действия реально менялись в17/24 и4/24 сравнениях |

Дополнение E11: [probe/verify/repair v2, аудит 11 сентября](../../experiments/PROBE_VERIFY_REPAIR_RESULTS_20260911.md).

| ID | Завершённая проверка | Результат | Допустимый вывод |
|---|---|---|---|
| E11 | 48 shared-prefix states /24init clusters /192 screen branches, Position, K4/H8 suffix, t72 | Continue26/48; full35/48; probe26/48; verified30/48. Verified−full −10.42п.п., CI[−20.83,0],4 rescue/9 harm, Holm p=.83967; gate NO-GO | Новая verification не превзошла сильный recovery, init holdout не открыт. Post-hoc GT-аудит:7false-held, из них5terminal fail; optical flow может следовать за захватом. Это не deployable GT detector и не доказательство бесполезности verification вообще |

На момент E11 контроль `probe → always-regrasp` не был выполнен;
не приписывать все девять harms одной ошибке трекинга. Этот контроль
добавлен в следующую отдельную frozen серию E12, а не задним числом в E11.

Дополнение E12–E13: [grounded-mask и delayed recovery, 11 сентября](../../experiments/GROUNDED_PROBE_RESULTS_20260911.md).

| ID | Завершённая проверка | Результат | Допустимый вывод |
|---|---|---|---|
| E12 | 48 новых paired states /24init clusters /384 screen branches; 8arms | Continue27/48; full33/48; probe23/48; legacy/mask-miss29/48; conservative/probe-always35/48; delayed34/48. Conservative−full+4.17п.п., CI[−4.17,10.42], Holm p=1; frozen gate NO-GO | Маска убрала10наблюдавшихся false-held на27одинаковыхпробах, но8сталиunknown. Conservative и probe-always: одинаковые48outcomes,47побитовоодинаковыхтраекторий. Перцептивная диагностика улучшилась, added controller benefit не доказан; confirmation не открыта |
| E13 | Независимые от screen 6cells /48states /24init clusters /144branches, full/delayed controls | Continue33/48; full36/48; delayed33/48. Full−continue+6.25п.п., CI[−4.17,16.67], Holm p=1 | Delayed отменяет14из21исходноразрешённыхrecovery; наy0.1/task9 full8/8 против3/8continue/delayed. Это fixed delay + fresh gate, не чистая timing-ablation; перенос общего выигрыша не установлен |

Все576ветвей соsmoke прошли повторный integrity-аудит. Эти conditional SR
не добавляются в full benchmark таблицу valid199. GT движения/контактов
использовались только post-hoc, не как online input нового verifier.

## Timing и eligibility

Дополнение E14–E15: [timing/eligibility, полный аудит 11 сентября](../../experiments/TIMING_ELIGIBILITY_RESULTS_20260911.md).

| ID | Завершённая проверка | Результат | Допустимый вывод |
|---|---|---|---|
| E14 | 96pairedstates /48initclusters /480screenbranches,12Positioncells,init46–49 | Continue63/96; immediate/diagnostic76/96; fresh/checked74/96. Checked−immediate−2.08п.п., CI[−7.29,3.13],3/5,Holmp=1; gateNO-GO. Immediate−continue+13.54п.п.,16/3,Holmp=.17046 | Новый latchedcontroller не улучшил сильныйbaseline; положительную разность кcontinue не объявлять family-wiseзначимой. Fixedt72mechanismstudy, не полныйbenchmark/новыезадачи; holdoutзакрыт |
| E15 | Post-hoc разложение техже480ветвей, не дополнительнаявыборка | 49исходныхдопусков→30fresh/33checked. Checked=fresh96labels и93траектории. Raw−fresh3rescue/1harm; наrescue freshscore17.54–19.06<threshold25.13, послеretreat32.03–33.84. Harm после3-stepretreatбезполногоprimitive. Все17общихfailuresнепроходятисходныйtrigger | Низкаяconfidence не всегда означает бесполезныйrecovery; диагностикадвижением небесплатна. Триггер ограничиваетcoverage. Это не calibrateduncertainty/SOTA/safetyguarantee и не доказательство невозможностиrecovery вall-failcases |

Все490ветвей включаяsmoke проверены,490видео/59174кадра скачаны и
декодированы;79CPU-тестовpassed. V1технические9ветвей исключены изSR.
Raw diagnostic не является deployable policy. НулевойCIchecked−fresh
описываетсовпавшиеlabels, не доказываетпопуляционнуюэквивалентность.

## Ночные серии 12 сентября

Основные1536/1440 выполнений завершены; новые независимые holdouts не открывались.

| ID | Постановка / источник | Результат | Допустимый вывод |
|---|---|---|---|
| E16 | [Observation Contract](../../experiments/OBSERVATION_CONTRACT_RESULTS_20260912.md),96старыхprefixes/192suffixcases/48initclusters,8arms | Continue128, physical151, open-only154, preserve-only161, open+regrasp138, preserve+regrasp145, GTcalibrated156, GTphysical167 из192. Primary−physical−3.13п.п.,CI[−6.25,0],9/15,Holmp=1,NO-GO | Primary не улучшил comparator. Preserve-only+5.21п.п. post-hoc,11/1,CI[3.13,7.81],clusterp=.09587; netgain целиком x0.2/task9, не новый confirmed/general SR |
| E17 | [Matched probe motion/drop audit](../../experiments/campaigns/observation_contract_20260911/review_20260912/summary.json), тежеtraces | Preserve+regrasp vs preserve-only:0rescue/16harm,8prefixes/6initclusters. На пробе цель32.01мм,рука31.68мм,контакт3/3шага; drop16/16 вt82–85 во время дополнительногоregrasp | Сильный локальный механизм ненужного раскрытия удерживаемого предмета. Не16независимыхсцен, не onlineGT detector, не официальнаяSafetyметрика; Holmp=.189 для pooled outcomecontrast |
| E18 | [Decoder H16 иfixedseeds](../../experiments/DECODER_MEDOID_RESULTS_20260912.md),180matchedcases,10tasks,3factors,K3joint | Main:first105,max112,action110,decoder112 из180; decoderΔ0,CI[−3.33,3.33]п.п.,7/7. Fixed1=110,fixed2=109; превосходство надними не подтверждено | Успешный перенос реализации, но не gain. 81–84%queryвыборов одного seed внутри каждойgroup; описательнаяseedaffinity, не полностьюконстантныйselector. Не сравнивать напрямую сvalid199/K4 |
| E19 | [Decoder H8 controls](../../experiments/campaigns/decoder_token_medoid_20260911/night_analysis/horizon8__paired_comparisons.csv),120matchedinit0cases,macrobalanced | MaxH16=65%,decoderH16=66.11%;maxH8=59.44%,fullH8=57.78%,prefixH8=59.44%. Prefix−maxH8Δ0,CI[−5.56,5.00]п.п.;maxH8−H16−5.56,CI[−13.89,1.67] | H8/prefix не дали подтверждённого преимущества, calls примерно2×. ГенерируетсяH16; future-error поляH8пустые для исключения horizon mismatch. 30/30/60factorcases:microSR неравенmacro |

Controls в расширенных decoder таблицах повторно используются, а не
становятся новыми rollout. Полные видео доступны из обоих подробных отчётов.
Отрицательное primary и oracle ограничения должны сопровождать любой
положительный post-hoc preserve-only пример.
Локальный полный аудит:3000видео/480434кадра двухсерий декодированы;
23933decoder-query проверены на точность выбранныхactions и свежихRGB,
180общихq0pools проверены;74CPU-теста passed. Это проверка артефактов,
не ещё3000независимыхэкспериментов и не подтверждениеpopulationgain.

## Что нельзя писать сейчас

- «Наш consensus достигает SOTA / статистически лучше max-value».
- «Результаты опровергают KeyStone/KDPE»: различаются K, backbone,
  representation, implementation и benchmark.
- «1/36 означает, что улучшение невозможно»: это конечный pool и один suffix.
- «Мы предсказываем fail заранее» по метрике, измеренной после падения.
- «Uncertainty = epistemic» для stochastic samples одной фиксированной модели
  или разброса копий в одной latent matrix без отдельной проверки.
- «На LIBERO-Safety улучшили безопасность» по drop proxy в PRO.
- «Универсальный момент t72»: это выбранный trigger конкретной постановки.
- «Все AI-assisted материалы проверены авторами»: такая проверка ещё должна
  быть выполнена командой до финального disclosure.

## Воспроизводимость чисел

[build.py](tools/build.py) вызывает [recovery_assets.py](tools/recovery_assets.py)
для таблиц и рисунков текущей recovery-статьи. Проверяются counts, полный
набор восьми клеток и оба контроля; SHA-256 всех 15 входов записываются
в [manuscript/tables/provenance.json](manuscript/tables/provenance.json).
Исторические E1–E19 приведены из отдельных отчётов, не объединены в одну SR.
Изменение исходных данных требует нового аудита текста и ledger.

# Общая статья: consensus, feedback и physical recovery

Дата: 15 сентября 2026. Это предложение для согласования с соавторами,
а не окончательная рукопись, preregistration старых опытов или новый результат.
Новые GPU-эксперименты в рамках этого анализа не запускались.

## 1. Решение в одном абзаце

Объединять стоит **научный вопрос, а не лучшие проценты разных таблиц**.
Коллега проверяет, помогает ли выбирать согласованный action sample на разных
моделях. У нас есть адаптация того же decoder-medoid на Cosmos, диагностика
зависимости от seed, проверки feedback и физического recovery. Вместе это
даёт содержательную постановку: **когда ошибки генеративной robot policy можно
исправить выбором другого предсказания, а когда нужны новое наблюдение или
физическое вмешательство?** Сейчас это перспективная диагностическая статья,
не доказанный универсальный planner. Убедительность потребует нескольких
связующих проверок, а не только редакционной переработки.

Рабочее название:

**When Does Test-Time Selection Help Generative Robot Policies?
Disentangling Consensus, Feedback, and Recovery.**

Более узкий резервный вариант: статья о gated visual recovery с multi-model
consensus как мотивацией и отдельным supporting study. Выбор зависит от того,
удастся ли подтвердить общий механизм на второй архитектуре.

## 2. Что изучено и насколько проверено

| Источник | Что из него известно | Статус |
|---|---|---|
| [RESULTS2.md](../../experiments/RESULTS2.md), срез 13 сентября | Counts, seed groups, Wilson CI и часть парных тестов коллеги | Сообщённые коллегой результаты; полный повторный аудит raw summaries не выполнен |
| [Присланный LaTeX](templates/collaborator_20260915_original.tex) | Action-space medoid, мотивация, related work | Сохранён без изменений; experiments/results и формула decoder-medoid отсутствуют |
| [Исходный репозиторий, зафиксированная ревизия](https://github.com/Doub1e05/Robotics_project_YSDA/tree/f1bb8d6221a7ee22bd34a72ec642cac244b4f89b) | Код GR00T/MIMIC и ранее проверенный перенос | Локальный checkout именно этой ревизии, не подтверждение всех новых строк 13 сентября |
| [Наш decoder-medoid report](../../experiments/DECODER_MEDOID_RESULTS_20260912.md) | 1440 rollout, H16/H8 и fixed-seed controls | Завершённый исторический эксперимент; не новый прогон runtime-v2 |
| [Наш broad P3-v2 report](../../experiments/P3_RUNTIME_V2_RESULTS_20260915.md) | 995/995, corrected runtime, полная broad-таблица | Проверенная современная серия |
| [Recovery evidence](manuscript/tables/recovery_evidence.json) | Scoped recovery, абляции и ограничения | Сильные scoped counts исторические; отдельная v2-репликация ещё нужна |

SHA256 `RESULTS2.md`:
`003932f4e55889895ac7bda1ac2b2de75984bc4e9884614314d6800334deae6d`.
SHA256 присланного LaTeX:
`f7d5b3712a5e4711df677d81b7eee10bbeb7d2f7a0b2f8f0de8e113084901eb1`.

Раздел `Related Work: Nikita` содержит разбор литературы, но не результаты
третьего экспериментального метода. Приписывать ему проверенный алгоритм
или количественный вклад по этому тексту нельзя.

## 3. Методы коллеги и связь с нашими

### 3.1. Action-space consensus

На одном наблюдении генерируются K=3 кандидата. Выбирается существующий chunk,
который в среднем ближе к остальным, без усреднения команд:

$$
i_A=\arg\min_i\frac{1}{K-1}\sum_{j\ne i}D_L(A_i,A_j),\qquad
D_L=\frac{\sum_{t=1}^{L}\gamma^{t-1}d(a_{i,t},a_{j,t})}
{\sum_{t=1}^{L}\gamma^{t-1}}.
$$

В присланной формуле расстояние включает translation L2 / sqrt(3), угол
между rotations / pi и несовпадение знака gripper; веса 1, 0.5, 0.25,
gamma=0.9. Это **центральность кандидата, не дисперсия и не вероятность успеха**.
Деление translation на sqrt(3) не делает расстояние физически
безразмерным само по себе: нужны units и action normalization каждой модели.

Следует раздельно обозначать generated horizon T, scoring prefix L и executed
horizon H. В тексте коллеги L=H; в нашем H16 transfer action-medoid оценивал
первые L=5 команд. Эти реализации нельзя описать одной настройкой.

### 3.2. Decoder action-token medoid

В проверенном GR00T-коде снимаются hidden action tokens последнего вызова
DiT action head, исключается state token. Расстояние:

$$
D_Z(i,j)=\frac{\sum_t w_t[1-\cos(z_{i,t},z_{j,t})]}{\sum_t w_t},
\qquad w_t=\begin{cases}4,&t\le4,\\1,&t>4,\end{cases}
\qquad i_Z=\arg\min_i\sum_{j\ne i}D_Z(i,j).
$$

В GR00T используются все сгенерированные action tokens с усилением первых
четырёх, а не только исполняемый H4. В MIMIC-переносе action-prefix извлекается
иначе. Для Xiaomi нужно получить и проверить adapter конкретных новых runs;
присланный LaTeX этого не определяет.

В Cosmos hidden action frame содержит 196 spatial tokens по 2048 features,
не 16 отдельных временных action tokens. Временные веса перенесены через
раскладку output head и повторённых latent actions. Это архитектурная
адаптация, не идентичный token-space эксперимент.
Точная формула и ограничения: [decoder protocol, разделы 2–3](../../experiments/DECODER_TOKEN_MEDOID_PROTOCOL_20260911.md).

**Особенность RNG:** проверенный GR00T wrapper заново выставляет тот же
candidate seed на каждом query. Это фиксированные noise streams при новых
observations, не независимый новый набор шумов на каждом query. У Cosmos
transfer тот же контракт. Такой вариант валиден, но его нужно явно назвать
и сравнить с fresh-per-query noise. Нельзя автоматически считать,
что baseline обновляет RNG точно так же, без проверки его кода.

### 3.3. Наши дополнительные уровни

| Уровень | Что меняется | Что уже проверяли |
|---|---|---|
| Selection | Индекс кандидата при текущем observation | Joint max-value, action/decoder medoid, risk scores |
| Feedback | Момент получения реального observation и замена неисполненного suffix | H8/H16, shared-prefix continuation |
| Recovery | Физическое состояние робота/объекта | RGB localization, gated approach/grasp/lift, затем policy |

Cosmos baseline здесь в основном **joint-value best-of-K**, не авторский
rollout-finetuned autoregressive planning a -> s' -> v. GR00T и Xiaomi в этих
опытах не следует автоматически называть WAM с явным future-image head.
Общий класс для названия статьи: generative robot policies, включающий VLA и WAM.

## 4. Что действительно показывают числа коллеги

### 4.1. Все три сопоставленные seed-группы

Ниже арифметическое среднее трёх seed-specific SR по данным `RESULTS2.md`.
Это **описательные средние**, не новый независимый dataset и не новый CI.
Одни и те же scene instances повторяются; нельзя приписать среднему Wilson
CI, считая все seed-повторы независимыми новыми задачами.

| Модель / benchmark | Baseline, % | Action medoid, % | Decoder medoid, % | Decoder минус baseline, п.п. |
|---|---:|---:|---:|---:|
| GR00T / SIMPLER, 96 episodes на seed | 52.08 | 47.92 | 56.60 | +4.51 |
| GR00T / official INT-ACT Object OOD, 192 на seed | 35.24 | 37.33 | 38.89 | +3.65 |
| Xiaomi / SIMPLER, 96 на seed | 81.60 | 80.90 | 80.90 | -0.69 |
| Xiaomi / official INT-ACT Object OOD, 192 на seed | 65.28 | 65.80 | 63.54 | -1.74 |

Для GR00T/SIMPLER decoder delta по seeds: **+17.71, -5.21, +1.04 п.п.**
Локальный 49/96 -> 66/96, p=0.0076, заслуживает внимания, но не может
представлять весь метод. p здесь приведён из реестра; полный набор парных
исходов нужен для нашего пересчёта и коррекции семейства сравнений.

**GR00T/INT-ACT выглядит более последовательным кандидатом на проверку**:
decoder deltas +5.73, 0.00, +5.21 п.п. Это полезнее для выбора следующего
confirmation, чем максимальный single-seed gain; значимость общего эффекта
по одним таблицам не установлена. Эта рекомендация post-hoc, не preregistration.

### 4.2. Остальные срезы

| Срез | Наблюдение | Допустимый вывод |
|---|---|---|
| MIMIC/SIMPLER | Baseline45/96, action52/96, decoder42/96 | Action +7.29п.п.; decoder -3.13п.п. при другом pool, нужны matched controls |
| MIMIC/INT-ACT | Baselines seeds0/1/2:73/33/9 из192; decoder[0,1,2]:88/192 | +7.81п.п. к seed0, но огромная seed-зависимость; нельзя объявить общий +7.81 без новых groups |
| MIMIC/LIBERO Spatial | 69/100 ->75/100 action; decoder64/100 | +6 и -5п.п.; другой benchmark, не PRO |
| GR00T/PRO Spatial | Seed1:246/400 ->253/400 decoder; seed2:244/400 ->241/400 | +1.75 и -0.75п.п.; p=.0654 и .664, устойчивой победы не установлено |
| GR00T/LIBERO Spatial | Decoder100/100 | Нет соответствующего baseline в присланной таблице |
| GR00T/PRO action | Seed1:246/400 ->248/400,5rescue/3harm,p=.727 | Небольшой неподтверждённый эффект |
| GR00T/Plus Background Textures first100 | Все100/100 | Saturation этого среза; не доказательство robustness на всём Plus |

MIMIC 73/192 ->9/192 при смене seed необходимо отдельно аудировать: task/init
manifest, sampler/reset semantics, checkpoint, horizon, episode completion.
Это может быть настоящая чувствительность модели, но таблица сама по себе
не исключает несовпадение конфигураций. Опечатку INC-ACT в выводах следует
исправить на INT-ACT после сверки официального task manifest.

## 5. Что добавляют наши результаты

| Исследование | Результат | Роль в общей статье |
|---|---|---|
| Cosmos decoder H16, K3 | Max-value112/180, decoder112/180;7rescue/7harm; delta CI[-3.33,3.33]п.п. | Прямой architecture-transfer того же семейства selector; нет подтверждённого gain |
| Cosmos fixed-candidate controls | First105/180, fixed110/180 и109/180 | Нужно отличать эффект selection от удачного noise seed |
| Cosmos choice frequencies | Один seed предпочитается в81–84%queries внутри каждой группы; episode-weighted83–86% | Конкретная гипотеза о seed identity, а не только отрицательный SR |
| Cosmos H8 control | Macro59.44% max H8 против65.00% max H16 на matched subset; CI разницы включает0 | Частота feedback не является бесплатной гарантией успеха |
| Shared-prefix feedback | 46/100 ->64/100,31rescue/13harm,CI[4,32]п.п. | Локально feedback может помочь; одна task/query область, отдельный runtime audit нужен |
| P3 historical scoped confirmation | H8 16/64 ->recovery41/64;27rescue/2harm | Сильное условное физическое улучшение; ещё не corrected-runtime confirmation |
| P3d full vs retreat/requery | 25/40 против8/40 | Механистический контроль; не полностью compute/latency-matched |
| Broad P3-v2 | Macro54.10% P3 против53.42% H16; delta+0.68п.п.,CI[-3.00,4.36] | Локальный P3 gain нельзя переносить на весь benchmark |

Источники: [decoder](../../experiments/DECODER_MEDOID_RESULTS_20260912.md),
[shared-prefix](../../experiments/OBJECT_Q4_SHARED_PREFIX_REPLICATION_RESULTS_20260902.md),
[recovery](EDITORIAL_SELECTION.md), [broad v2](../../experiments/P3_RUNTIME_V2_RESULTS_20260915.md).
Нельзя объявить исторические positive findings недействительными без проверки,
но нельзя и утверждать, что исправленная broad-серия автоматически их подтвердила.

**Мы ещё не доказали, что именно состояния с бесполезным consensus спасает P3**:
большинство этих таблиц относится к разным cohorts. Это главная недостающая
связь для объединённого механистического claim.

## 6. Научное объединение и формулы

### 6.1. Agreement не оптимизирует вероятность успеха напрямую

Medoid минимизирует эмпирическое расстояние до других samples собственной
policy. Это принцип minimum Bayes risk относительно выбранного расстояния,
а не относительно task failure loss. Систематически ошибочная мода может
быть наиболее согласованной. Это известное различие, не наша новая теорема.
Новый вклад возможен в **измерении, какой механизм доминирует и что его исправляет**.

Для фиксированного состояния s, пула кандидатов A_1,...,A_K, одинакового
execution horizon и continuation policy pi_c определим

$$
Q(s,A_i)=P(Y=1\mid s,\operatorname{execute}(A_{i,1:H}),\pi_c).
$$

Для выбранного индекса i_hat:

$$
1-Q(s,A_{\hat i})=
\underbrace{1-\max_i Q(s,A_i)}_{\text{ограничение данного пула и continuation}}
+\underbrace{\max_iQ(s,A_i)-Q(s,A_{\hat i})}_{\text{потеря из-за selector}}.
$$

Это точное тождество, не доказанная новая модель. Первый член не означает,
что во всём action space нет хорошего действия: он относится только к этому
пулу, горизонту и suffix policy. Q нужно оценивать повторными suffix seeds.
Выбор лучшего кандидата и оценка его качества на тех же повторах дают
оптимистичный oracle; нужны отдельные repeats для выбора и оценки.

### 6.2. Три разных величины

$$
r(s)=P(Y=0\mid s,\pi_c),\qquad
Q(s,A_i),\qquad
\Delta_R(s)=E[Y\mid\operatorname{do}(R),s]-E[Y\mid\operatorname{do}(C),s].
$$

Первая оценивает риск состояния, вторая ранжирует действия, третья отвечает,
поможет ли конкретное recovery. Высокий failure AUROC первой не доказывает
качество второй и третьей. P3 gate сейчас геометрический, а не обученный
оценщик Delta_R. Эти обозначения объединяют постановку, но не создают
задним числом реализованный adaptive router.

Практическая проверка формулы risk-score: если U(s) одинаково для всех
кандидатов, то argmax_i[V_i-lambda U(s)] = argmax_i V_i. Для изменения
ранжирования нужен candidate-specific U_i. Общий разброс actions может
менять решение о requery, но сам по себе не выбирает другой candidate.
Несколько разных joint samples (A_i,s'_i,V_i) также не равны нескольким
будущим при одном фиксированном A_i: в разброс смешаны разные планы.

Prediction error после исполнения chunk является offline diagnostic или
online сигналом для следующего query, не доступным заранее score этого же
chunk. Предсказание будущего на T=16 нельзя сравнивать с наблюдением на H=8
и называть это корректной ошибкой динамики без временного выравнивания.

### 6.3. Проверяемые гипотезы общей статьи

1. Центральность action/hidden samples не даёт переносимой оценки Q сама по себе.
2. При повторном использовании фиксированных noise seeds часть hidden-centrality
   может объясняться seed identity, а не изменением состояния. Пока гипотеза,
   поддержанная Cosmos choice statistics, но не причинный вывод по всем моделям.
3. Польза feedback и recovery отличается от предсказания риска и полезности
   reranking; общий SR нужно разложить на rescues, harms и цену вмешательства.

Проверка только гипотезы 1 рискует повторить уже известные ограничения
consensus. Связка 2 + matched state-level intervention study перспективнее,
но её новизну нельзя считать установленной до дополнительных проверок.

## 7. Что объединять в таблицах, а что нельзя

| Ось | Материалы коллеги | Наши материалы | Правило |
|---|---|---|---|
| Модели | MIMIC, GR00T, Xiaomi | Cosmos | Разные панели одного исследования, не общий leaderboard |
| PRO support | Spatial,4OOD-среза,400episodes | Object suite,3factors,valid199 или transfer180 | Нельзя напрямую сравнивать SR/400 и SR/199; нужен общий manifest |
| Perturbations | В присланном реестре нет полного списка4срезов | Object/Environment/Position с фиксированными вариантами | Запросить точные suite/task/variant/init IDs и hashes |
| Candidate pool | K3,разные fixed groups | K3 decoder, K4 broad, другие исторические серии | Сравнивать selector при одинаковом K и pool на одинаковом состоянии |
| Вращения | LaTeX6D | Cosmos native3D rotvec в7Daction | Отдельные adapters и units, не одна универсальная6Dформула |
| Обучение | Medoid без нового обучения | Frozen Cosmos + trained RGB localizer уP3 | Только medoid-часть можно назвать training-free |
| Время и стоимость | H/budget/latency не полностью указаны вRESULTS2 | T16,H16/H8,280physicalsteps | Одинаковый action budget внутри сравнения; дополнительно latency/NFE |
| Статистика | Wilson CI,частьexactMcNemar | Парные cluster CI,разныеcohorts/runtimeversions | Общие определения метрик, но без смешивания популяций и версий |

Сводить можно **within-model paired effect sizes** с явно указанными
benchmarks/seeds/controls. Один общий weighted SR по всем строкам будет
отражать произвольные веса задач. Тезис «четыре модели подтверждают recovery»
неверен: recovery пока проверялся только с Cosmos.

## 8. Что исправить в присланном LaTeX

1. `ICRA2027` не соответствует целевому ICLR. Использовать существующий
   официальный ICLR wrapper, не просто поменять название конференции в title.
2. `We introduce consensus planning` заменить на `We evaluate ...` и указать
   prior art. Новизна medoid как общей идеи не поддерживается литературой.
3. Добавить полноценный decoder-method раздел: hook, tensor shape, layer,
   denoising call, normalization, weights, ties, RNG, adapters по моделям.
4. Убрать универсальные seeds{0,1,2},6Drotation и L=H из общих preliminaries;
   actual settings вынести в protocol table.
5. Cosmos не описывать как обязательное последовательное video -> actions:
   наш checkpoint предсказывает action/future/value совместно.
6. Утверждение «другой sample был бы успешен» требует candidate branching,
   а не только разницы terminal SR между полными независимыми trajectories.
7. `lightweight` подтвердить end-to-end latency, batching и NFE. Код GR00T
   перебирает кандидатов последовательно; малая цена distance не означает
   малую цену трёх model generations. Latency KeyStone не переносится автоматически.
8. Related work разделить по вопросам, не по именам авторов команды.
   Файл bibliography.bib из attachment не приложен; проверить все cite keys.
9. В abstract не выбирать только GR00T seed1 или только familiar P3 cells без
   обозначения области. В main показать общие deltas и ключевые ограничения;
   полные seed/task/control tables оставить в appendix.

## 9. Близкая литература и границы новизны

Проверено по первичным источникам 15 сентября 2026. Числа авторов ниже не
сопоставляются с нашими как единый benchmark и не объявляются репликацией.

| Работа | Что уже есть | Что это означает для нас |
|---|---|---|
| [KeyStone](https://arxiv.org/html/2605.08638v1) | Shared-context sampling, guard/clustering и medoid; GR00T N1.6 WidowX50.0->63.3%,K4,пять repeats | Ближайший обязательный control; наш global medoidK3,GR00TN1.7 иfixednoiseprotocol не точная репликация |
| [KDPE](https://arxiv.org/html/2508.10511v2) | Геометрически осмысленная density selection action endpoints; trajectory extension не всегда улучшает | Rotation/gripper-aware distance само по себе недостаточная заявка на новую идею |
| [Ruan et al., Is the Future Compatible?](https://arxiv.org/html/2605.07514v1) | Action-state consistency, future consensus, background collapse; LingBot-VA90.2->93.0%RoboTwin | Нельзя заявлять, что первыми обнаружили ненадёжность future agreement; отличие искать в seed/within-pool/physical intervention diagnostics |
| [BadWAM](https://arxiv.org/abs/2607.15207) | Adversarial action/imagination decoupling | У нас natural/OOD failures, не adversarial attack; plausiblefuture не достаточный verifier уже известный риск |
| [Cosmos Policy](https://arxiv.org/html/2601.16163v1) | Joint world/action representation и отдельный AR planning protocol | Не подменять авторский planning нашим joint-valuebest-ofK |
| [Sentinel](https://proceedings.mlr.press/v270/agia25a.html), [Rewind-IL](https://arxiv.org/html/2604.16683v1) | Temporal consistency monitoring и recovery | Monitoring+recovery не новая общая идея; вклад требует проверенного механизма и matched controls |

Результаты KeyStone и Ruan показывают, что нельзя сформулировать наш итог
как «consensus не работает». Правильнее: **его польза зависит от протокола,
представления и задач; проверяем, какая часть gain переживает seed-matched
и intervention-matched controls**. Для отрицательного результата желательно
сначала воспроизвести положительный reference при близком протоколе.

## 10. Минимальные следующие проверки по приоритету

### P0. Единый evidence audit, без GPU

Получить от коллеги для всех included rows: commit/checkpoint hashes,
episode-level outcomes и IDs, manifests, T/L/H,budget,K,sampler settings,
точный seed schedule, candidate choices, runtime/errors, exclusions.
Свести в long-form таблицу:

`study_id, model, checkpoint, runtime, suite, task, variant, init_id,
env_seed, seed_group, rng_schedule, method, T, L, H, K, outcome,
steps, queries, nfe, latency, source_hash`.

Отсутствующие данные оставить missing, не реконструировать парные outcomes
из агрегированных counts. Проверить одинаковость initial states и baseline
noise contract. Пересчитать paired effect/CI, rescue/harm, task/seed tables.
Это самая быстрая и обязательная работа; без неё общий statistical claim слаб.

### P1. Проверить сильный P3 на исправленном runtime

Сохранить исходный support и настройки, без подбора успешных cells.
Предложенный минимум: familiar64 + transfer64, H16/H8/full-recovery,
**384rollout + smoke**. Это не новая регистрация старого результата;
новая confirmation и независимый runtime check. Затем matched retreat-control,
если claim о physical correction остаётся центральным.
Не называть t72 универсальным trigger; boundary study и event-driven method
показывать раздельно. [Более подробный checklist](SUBMISSION_CHECKLIST.md).

### P2. Связующий механизм на Cosmos и GR00T

Сначала на имеющихся features посчитать seed-conditioned choice frequencies,
episode-weighted entropy, agreement с fixed-candidate control, зависимость
выбора от observation, а не pooled frequency всех seed groups.
Перестановка порядка кандидатов проверяет tie/index artifact, но не устраняет
noise identity bias; её нельзя выдавать за полноценный causal test.

Затем заранее выбрать matched states без выбора только fail/эффектныхвидео:
общий K3pool, одинаковый физический runtime, один continuation policy.
Исполнить каждого кандидата с несколькими suffix seeds. Пример небольшого
механистического pilot:32states x3candidates x4suffixrepeats x2models
=**768branchrollout**. Это стартовый бюджет, не гарантия statistical power;
2repeats для выбора/2 для оценки дадут ещё шумные Q.

Первичные endpoints: within-pool ranking, held-out selector value/regret,
candidate-success variation и fixed-seed control. Дополнительно сравнить
fixed-per-query и fresh-per-query noise при одинаковых state/pool budgets.
Не смешивать изменившийся sampler с чистым эффектом расстояния.
Проверки snapshot/replay требуются отдельно и для второго simulator.

### P3. Confirmation одного selector, а не поиск ещё десятков формул

Для GR00T официальный INT-ACT выглядит более ровным preliminary signal,
чем выбор только лучшего SIMPLER seed. Заморозить метод до новых seeds;
включить K1, action-medoid, decoder-medoid и близкий KeyStone control.
Разумный план:3новыеseedgroups x192episodes x4arms=**2304rollout**.
Размер окончательно выбрать по discordant pairs и минимальному полезному
эффекту послеP0; не обещать значимость трёх seeds заранее.

Если бюджет ограничен, приоритет P0/P1/P2 выше нового широкого sweep.
Успех P2 определяет, есть ли общий механизм для основной статьи. Если нет,
не создавать видимость единого нового algorithm из несвязанных результатов.

## 11. Метрики общей статьи

Primary: terminal SR отдельно по model/benchmark, paired deltaSR с clusterCI.
При разных размерах factors публиковать macro и micro, не заменять одно другим.

$$
\Delta SR_{micro}=\frac{N_{rescue}-N_{harm}}{N},\qquad
\Delta SR_{macro}=\frac1F\sum_f\frac{N_{rescue,f}-N_{harm,f}}{N_f}.
$$

Wilson CI оставить для отдельной пропорции, с его binomial assumptions.
Для различия методов ресемплировать общие task/init clusters с сохранением
seed-повторов; выбор уровня cluster зависит от целевой generalization.
Показывать per-seed results и точное число задач, а не только число rollout.
Exact McNemar на независимых парах, при зависимых повторах cluster analysis;
семейство основных сравнений фиксировать и использовать Holm correction.
Незначимость не означает эквивалентность: для последней нужен заданный margin.

Secondary: candidate regret, within-pool ranking, rescue/harm, intervention
coverage, seed sensitivity, NFE/query и episode, median/p95 query latency,
число физических действий и неблагоприятные события с явным определением.
Failure AUROC/PR-AUC/leadtime относятся к monitoring и не заменяют closed-loopSR.
Все сигналы до ошибки отделять от post-execution prediction errors.
Frame/query metrics считать на matched windows и с episode weighting:
длинные failures не должны автоматически получать больший статистический вес.
Simulator ground truth и oracle branches допустимы для диагностики,
но должны быть явно исключены из runtime inputs метода.

## 12. Как написать одну статью

Предлагаемая последовательность, не главы по авторам:

1. **Introduction:** один вопрос об использовании stochastic predictions
   для исправления ошибок;3конкретных исследовательских вопроса.
2. **Setup:** VLA/WAM distinctions,T/L/H,noise schedule,selector/feedback/recovery,
   ограничения frozen policy и auxiliary training.
3. **Controlled evaluation:** единые определения, разные panels datasets,
   fixed/fresh/noise controls, histories выбора subsets, corrected runtime.
4. **Consensus across models:** seed-specific forestplot и meaneffects;
   не только лучший seed, separate ID/OOD.
5. **Why rankings change:** hidden seed preferences,fixedcandidatecontrols,
   conditional outcome/ranking study. Это наиболее важный связующий раздел.
6. **Beyond selection:** matched feedback и P3 physicalrecovery с границами
   применения; только те comparisons, которые действительно выполнены.
7. **Discussion:** agreement/risk/advantage различны; когда менять selector,
   а когда policy/data/feedback; что остаётся неподтверждённым.

Главные рисунки: seed-effect forestplot; same-state candidate ranking;
feedback/full/retreat comparison; все rescue/harm и coverage по cohorts.
Видео выбрать по заранее объявленным категориям: rescue, harm, оба success,
оба fail, согласованный неверный candidate. Не только красивые rescues.
Основные отрицательные/нулевые результаты выбранных методов нужны для
самого исследовательского вопроса; unrelated coefficient sweeps можно
оставить в отдельном полном отчёте.

### Рабочий английский abstract для согласования

*Generative robot policies expose multiple stochastic action predictions,
but it remains unclear when selecting among them improves closed-loop control.
We study this question through complementary evaluations of action-space and
decoder-space consensus across MIMIC-Video, GR00T, Xiaomi Robotics 0, and Cosmos
Policy, keeping their benchmark populations and execution contracts separate.
Existing evaluations reveal heterogeneous, seed-dependent effects rather than
a uniform benefit from consensus. In Cosmos, decoder-space selection shows
strong preferences for particular fixed noise seeds, motivating explicit
fixed-candidate controls. Separate feedback and visual-recovery studies examine
interventions that change the available observation or physical state rather
than only the selected prediction. We organize these results around three
distinct quantities: state failure risk, candidate quality, and intervention
benefit. The resulting analysis identifies validation requirements for
inference-time improvements, including matched sampling, execution budgets,
paired outcomes, and runtime replay.*

Это provisional abstract, не финальные claims. Сильные P3 counts добавлять
в его окончательный вариант после scoped-v2check. Доказанный multi-model
seed mechanism писать только после P2. Мы не объявляем здесь новый
универсальный planner или доказанную общую неэффективность consensus.

## 13. Оценка готовности для ICLR

Ширина экспериментов коллеги существенно усиливает материал, особенно вместе
с уже сделанным переносом decoder-medoid на Cosmos. Но количество моделей
само по себе не обеспечивает новизну. Сейчас основные риски: близость к
KeyStone/Ruan, несогласованные protocols, seed-selection bias и ещё не
проверенный scopedruntime P3. Красивый текст не заменит эти проверки.

Мой выбор: **diagnostic multi-model paper с проверяемым механизмом**, а не
«новый универсальный consensus planner». Сильный scoped recovery оставить
положительным case study с точной областью применимости. Если общего
механизма не подтвердим, лучше более узкая честная статья, чем искусственная
система, компоненты которой никогда не работали вместе.

Официальные требования и формат нужно проверять по
[ICLR2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
и [Call for Papers](https://iclr.cc/Conferences/2027/CallForPapers).
Принятие гарантировать нельзя; ближайшая цель работы над текстом и опытами:
ясный новый вывод, проверяемые доказательства и отсутствие подмены
benchmark, метода, стоимости или статуса результата.

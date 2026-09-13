# Похожие работы: результаты и сравнение с нашим проектом

Проверено **12 сентября 2026** по первичным статьям и официальным proceedings.
Это целевой related-work audit, не исчерпывающий мировой leaderboard.
Числа ниже сообщены авторами, **не воспроизведены нами**. Версии PDF/HTML
зафиксированы в ссылках. Preprint не означает принятие на ICLR.

[Наши результаты](RESULTS_AND_ANALYSIS.md) | [Evidence ledger](EVIDENCE_LEDGER.md) |
[Полный обзор проекта](../../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md) |
[Скачанные статьи](reference_papers/manifest.json).

## 1. Какие результаты получили другие

**Это не единая сравнительная таблица SR:** между строками различаются
модель, данные, обучение, задачи, бюджет и определение outcome.
«П.п.» означает абсолютную разность процентов, не относительный прирост.

| Работа | Где и с чем сравнивают | Результат авторов | Где проверено |
|---|---|---|---|
| Cosmos Policy | Direct policy на standard LIBERO; planning отдельно на сложных ALOHA | LIBERO98.5% average; planning +12.5 **score points**, не PRO SR | [v1, Table1 и §5.3/Fig7](https://arxiv.org/html/2601.16163v1) |
| KeyStone | K1 → K16, standard LIBERO | $\pi_{0.5}$96.8±0.7 →97.8±1.1%; SmolVLA50.4±2.1 →57.2±1.3% | [v1, Table1](https://arxiv.org/html/2605.08638v1) |
| KeyStone, другие модели | GR00T N1.6 K1→K4 на Simpler/WidowX; Fast-WAM K1→K16 на RoboTwin2.0 | 50.0→63.3%; 90.0→93.0% соответственно | [v1, Table1](https://arxiv.org/html/2605.08638v1) |
| KDPE | Diffusion Policy → KDE selection, RoboMimic/MimicGen | CNN84.9→88.2%; Transformer79.3→81.2%; color shift CNN82.8→87.2% | [v2, Tables1–2](https://arxiv.org/html/2508.10511v2) |
| Flow-VLA UQ / SAVE | SmolVLA, active fine-tuning, LIBERO-10, одинаковые75добавленных demonstrations | Random54.6±0.9 → VFD67.1±3.2%; online detector accuracy .67, TPR .79, TWA .54 | [v1, Table2, §6.4 и C.6](https://arxiv.org/html/2606.18043v1) |
| Sentinel / STAC | Diffusion policies, mobile manipulation simulation и real robot | Авторы сообщают на18% больше обнаруженных failures при объединении consistency и progress detectors | [CoRL proceedings, abstract](https://proceedings.mlr.press/v270/agia25a.html) |
| Rewind-IL | ACT, 6 real tasks, 20rollouts/task/setting | Natural66.7→80.0%; с adversarial disturbance18.3→76.7%; detector balanced accuracy .95 | [v1, TablesI–II и §V](https://arxiv.org/html/2604.16683v1) |
| UNISafe | Dreamer + latent safety filter, Block Plucking | Safe-success58→72%; failure41→20%; incomplete1→8%; filter включён37.7% времени | [v2, Table2](https://arxiv.org/html/2505.00779v2) |
| StressDream | Ctrl-World/DROID и $\pi_{0.5}$; failure-aware fine-tuning | Failure recall54→94%; SR39→71% в авторской manipulation-постановке | [v1, Fig4/Fig7 и §6](https://arxiv.org/html/2606.00267v1) |
| Don't Blind Your VLA | OpenVLA SFT → visual alignment, Simpler OOD variants | Carrot49→61%; Position43→58%; PosChangeTo23→20% | [v1, Table1](https://arxiv.org/html/2510.25616v1) |

У Sentinel формулировка abstract «18% больше» здесь сохранена как авторская,
не пересчитана в +18п.п. SR. Accuracy, TPR, safe-success, fractional score
и terminal SR нельзя ставить на одну ось как одну метрику.

## 2. Ближайшие работы: почему числа отличаются

### 2.1. Cosmos Policy

Это действительно [публикация ICLR2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/748becc400a57c0e31cfe6a2e7951467-Abstract-Conference.html).
Основной LIBERO-result относится к direct policy, не planning на PRO.
Planning использует rollout-finetuned world/value model отдельно от proposal
policy, AR $a\to s'\to v$, три future samples на action и пять value на future,
с majority-mean агрегацией. [+12.5 пункта относится к ALOHA task-completion score](https://arxiv.org/html/2601.16163v1).

**У нас:** преимущественно frozen LIBERO checkpoint, joint value и K4.
Поэтому отрицательный reranking-result не противоречит авторскому planning.
Для рукописи необходимо название «joint-value best-of-K baseline», если
точный авторский протокол не воспроизведён.

### 2.2. KeyStone

Выбор medoid доминирующего action cluster, без policy fine-tuning. Table1
агрегирует пять запусков; указанные ± являются **SD**, не 95% CI.
K выбран по latency на выделенной GPU: K4 у GR00T/X-VLA, K16 у остальных.
У $\pi_{0.5}$ Goal даже падает98.0→97.5%, хотя общий средний растёт.
[Tables1–2 и §4.2](https://arxiv.org/html/2605.08638v1).

**У нас:** K4 Cosmos на PRO, сравнение также с max-value K4; нет заявленного
paper-like K16/latency результата. Наш +1.00 macro-п.п. к max-value с CI,
включающим0, не опровержение и не подтверждение всей статьи.
Сам medoid/clustering не новая идея нашего проекта.

### 2.3. KDPE

Основной KDE применяется к **последнему pose action**; учитывает геометрию
вращений и gripper. Авторы используют population100; full-trajectory KDE
не даёт такого же улучшения. На real CoffeeMaking70% против60% получены
всего на10эпизодах, то есть7vs6. [§3.2, Tables1/3, §5.4](https://arxiv.org/html/2508.10511v2).

**У нас:** K4, native OSC deltas и induced endpoint, а не исходная pose-policy
с N100. Числа53.08vs54.77% не следует выдавать за точную репликацию KDPE.
Ближайший контроль для новой representation: raw/action/latent medoid при
одном pool, затем compute-matched проверка размера pool.

### 2.4. Flow-VLA UQ / SAVE

Uncertainty оценивает расхождение **двух отдельно обученных моделей** вдоль
flow. Основной gain даёт **выбор новых demonstrations и дообучение**, не
штраф value внутри одного action pool. Для LIBERO-10:15раундов×5demonstrations;
30rollouts/task при оценке; generate50/execute25. Failure thresholds
калибруются по успешным траекториям. [§6, AppendixB](https://arxiv.org/html/2606.18043v1).

**У нас:** разные шумы одного checkpoint и latent-copy disagreement не
равны cross-model epistemic VFD. Наш отрицательный static-penalty тест
не опровергает пользу uncertainty для data acquisition. В этой ветке
нужен отдельный train/data budget и отдельный claim.

### 2.5. Sentinel / STAC

Sentinel разделяет erratic behavior и отсутствие task progress: первое
проверяет по temporal action distributions, второе с помощью VLM.
Это runtime **monitor**, не новый max-value selector.
[Официальная публикация CoRL](https://proceedings.mlr.press/v270/agia25a.html).

**У нас:** отрицательный simple overlap RMSE не закрывает distributional STAC.
Согласованные chunks могут продолжать неверное поведение. Для статьи нужен
отдельный baseline progress/contact, а не утверждение «любой fail обязан
увеличить action disagreement». Lead time считать относительно события,
не только конечного timeout.

### 2.6. Rewind-IL

TIDE сравнивает overlap chunks; conformal threshold и VLM checkpoint database
позволяют обнаружить сбой и вернуться к recovery checkpoint.
Очень большой disturbed gain относится к **внешнему возмущению**, а natural
gain значительно меньше. Вклад detector и восстановления в SR оценивается
как объединённая система. [§IV–V, TableII](https://arxiv.org/html/2604.16683v1).

**У нас:** физический RGB regrasp, не тот же checkpoint mechanism. Сравнивать
нужно и trigger, и реально исполняемый recovery с его временем/действиями.
Нельзя считать возврат simulator snapshot бесплатным действием робота.
Эта работа существенно ограничивает claim новизны «overlap alarm + recovery».

### 2.7. UNISafe

Latent world model с ensemble uncertainty и safety value/filter. Раздельные
safe-success/failure/incompletion показывают цену консерватизма. У variation
TotalUncertainty failure .18, но incomplete .28 и safe-success .54:
меньше failures само по себе не означает лучший метод.
[Table2](https://arxiv.org/html/2505.00779v2).

**У нас:** PRO terminal success и drop proxies, не тот safety benchmark.
Нужно отдельно оценивать событие вреда и завершение задачи. Нулевой score
конкретной P4 quadratic-JRD реализации не опровергает авторский ensemble
filter; архитектура, обучение и prediction distributions различаются.

### 2.8. StressDream

Оптимизация initial noise ищет возможные failures с plausibility constraint.
Manipulation: Ctrl-World/DROID, шесть задач, примерно150demo/task для WM;
policy fine-tuning по40successful demo/task, веса1.0/0.1 по imagined risk;
20test rollout/task. Это не бесплатная замена argmax при frozen policy.
[§6.1–6.2](https://arxiv.org/html/2606.00267v1).

**У нас:** поиск реально плохих branches уже есть, но такого robust
reweighting обучения нет. Перспективная аналогия: оценивать несколько
условных futures **фиксированного action**, а не только разные actions.
Сначала проверить, что WM вообще моделирует relevant failure и verifier
не вознаграждает артефакты. Числа39→71% не являются LIBERO-PRO result.

### 2.9. Don't Blind Your VLA

Alignment к external vision teacher во время SFT улучшает ряд Simpler
perturbations, но не каждый отдельный вариант. Это training-time
representation method; Table1 не таблица LIBERO-PRO.
[§7 и Table1](https://arxiv.org/html/2510.25616v1).

**У нас:** один лишь cosine distance между decoder features не воспроизводит
visual alignment. Близкая гипотеза для perception failure, но потребуется
дообучение и train-matched контроль; её нельзя смешивать с inference-only
выбором лучшего seed/candidate.

## 3. Что показывает сам LIBERO-PRO

Из **Table5 v1**, Object task suite, средние, как опубликованы авторами:

| Модель авторов | Original SR | Object | Position | Environment |
|---|---:|---:|---:|---:|
| OpenVLA | 99% | 98% | 0% | 0% |
| $\pi_0$ | 98% | 94% | 0% | 29% |
| $\pi_{0.5}$ | 98% | 98% | 17% | 73% |

[LIBERO-PRO, Table5](https://arxiv.org/html/2510.03827v1).
Это округлённые средние из статьи, не наши пересчитанные task-level значения.

**Вывод для нас:** Object, Position и Environment принципиально разной
трудности; высокий ID SR не обеспечивает robustness. Но нельзя сравнить
наш Environment40% с их73% и приписать разницу selector: разные checkpoints,
perturbation grids, init, seeds и budgets. Наш valid199 исключает один
пустой asset и использует собственный subset. Для прямого leaderboard
нужен общий зафиксированный manifest и повторный запуск всех baseline.
Object suite и Object perturbation нельзя обозначать одним неоднозначным
словом «Object» в подписи основной таблицы.

## 4. Что уже является известным, а где наш возможный вклад

| Идея | Prior art / статус | Что ещё надо доказать у нас |
|---|---|---|
| Несколько samples и выбор согласованного | KeyStone, KDPE; NLP self-consistency/MBR | Новая representation/правило должно помогать относительно этих controls, не только K1 |
| Меньше исполненных действий, чем предсказанных | Receding-horizon control; temporal consistency STAC/TIDE | Переносимый выбор момента feedback, а не удачная фиксированная граница |
| Uncertainty-guided вмешательство | SAVE, Sentinel, UNISafe | Отделить detection от causal benefit и учесть физическую цену |
| Failure verification + recovery | Rewind-IL и safety/recovery literature | Почему наш controller полезнее сильного always/full-recovery control |
| Action-conditioned robust future evaluation | Cosmos planning, StressDream | Устойчивое advantage на repeats и новых task/init, без ground-truth leakage |
| Разбор selection/coverage/feedback/physical cost | Совместная диагностическая постановка нашего проекта | Не объявлять новым принципом; показать воспроизводимый failure mechanism и границы применимости |

Схема возможного вклада: **отделить ошибку ранжирования от отсутствия хорошего
proposal и от цены получения информации**, затем проверять конкретный способ
устранить обнаруженный bottleneck. Это наша интерпретация результатов, не
заимствованный готовый theorem и не установленная novelty.

Аналогии с LLM/NLP уже подробно собраны в
[обзоре26работ](../../articles/llm_nlp_transfer_20260909/PAPER_REVIEW.md) и
[плане переноса](../../articles/llm_nlp_transfer_20260909/ANALOGY_AND_PLAN.md).
Само «больше samples / verifier / process score» не новый метод. Робототехническая
особенность, которую нужно измерить: настоящее наблюдение требует действий,
а действие может необратимо испортить состояние. Продолжение из simulator
snapshot является инструментом экспериментатора, не runtime API робота.

## 5. Что это означает для ICLR

**Не существует численного порога вида «+5п.п. достаточно для ICLR».**
Официальное руководство требует ясного вопроса, корректности, воспроизводимых
доказательств и значимого нового знания; отсутствие SOTA само по себе не
основание для отклонения. Здесь используется руководство2026 как ориентир,
не выдуманные правила2027. [ICLR Reviewer Guide](https://iclr.cc/Conferences/2026/ReviewerGuide).

Моя оценка по текущим данным:

- У нас достаточно материала для **содержательной диагностической истории**,
  но количество запусков не заменяет переносимость и новый научный вывод.
- Наши +18/+27.5п.п. условных improvements численно крупные, однако уже,
  чем multi-backbone/multi-task coverage ряда работ выше. Прямое сравнение
  размера gains между такими постановками некорректно.
- Нулевой результат consensus информативен при правильном comparator,
  budget и uncertainty interval; он не доказывает эквивалентность методов.
- Сильнее всего сейчас недостаёт **independent confirmation одного claim**
  и проверки generality. Большой поиск коэффициентов на просмотренных
  случаях увеличит selection bias, а не силу аргумента.

### Минимальный набор перед финальным текстом

| Что нужно | Почему |
|---|---|
| Frozen task/factor/init manifest и preprocessing contract | Чтобы baseline SR действительно сравнивались |
| Одинаковые K, execution H и budget; отдельный latency/Pareto plot | Чтобы не принять дополнительный compute за лучший selector |
| K1, joint-maxV, action/latent consensus; strong recovery controls | Чтобы новый компонент сравнивался с ближайшими альтернативами |
| Independent suffix + init + task/cell splits | Чтобы убрать optimistic oracle и повторный подбор на test |
| Per-factor/task effects, grouped CI, harms, corrections | Чтобы pooled gain не скрывал ухудшения и зависимость повторов |
| Event labels и detection lead time до события | Чтобы отличить предупреждение от распознавания уже произошедшего fail |
| Ablation perception / gate / physical action | Чтобы приписать эффект правильному компоненту |
| Второй backbone для широкого architecture claim | Чтобы результат не был особенностью одного Cosmos checkpoint |

После завершения текущих серий обновляются
[сводка](RESULTS_AND_ANALYSIS.md) и [ledger](EVIDENCE_LEDGER.md).
В основной текст пока нельзя добавлять «decoder medoid улучшил SR»:
его локальный smoke не заменяет полный frozen test.

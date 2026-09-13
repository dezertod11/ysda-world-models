# Обзор работ для переноса из LLM/NLP в Cosmos Policy

Дата: 9 сентября 2026. [Каталог PDF](README.md).

Ниже разделены **результаты авторов**, **наша аналогия** и **ограничения**.
Прочитаны постановки, основные методы, соответствующие экспериментальные
разделы и существенные ограничения. Это не независимое воспроизведение
чисел из статей и не доказательство переноса на LIBERO-PRO.
Более подробно разобраны M2, M10, M11, M17, S5 и B3 как ближайшие к нашей системе.

## 1. Обзоры

### S1. Test-Time Scaling: What, How, Where, and How Well?

[Источник](https://arxiv.org/abs/2503.24235), PDF стр. 1-4 и разделы 2-8.

**Содержание.** Систематизация по тому, что масштабируется, как, в каких
задачах и какими метриками это оценивается. Разделяются параллельный sampling,
последовательная доработка и поиск. Это карта методов, а не один выигравший алгоритм.

**Для нас.** Разнести число кандидатов $K$, denoising budget $D$, длину
исполняемого prefix $h$, глубину world-model search и стоимость verifier.
Сравнение K4/H16 с K4/H8 не изолирует качество ранжирования: меняется feedback.
Практическая ценность обзора: проектировать SR/compute Pareto frontier.

### S2. A Survey of Process Reward Models

[Источник](https://aclanthology.org/2026.acl-long.163/), PDF разделы 2-6.
Заголовок PDF: *From Outcome Signals to Process Supervisions for Large Language Models*;
HTML citation metadata: *A Comprehensive Survey ... Data Generation, Model Construction, and Usage*.

**Содержание.** Цикл создания process labels, обучения PRM, использования в
search/RL и повторного сбора данных. Обсуждаются не только математика и код,
но и мультимодальные/agentic приложения и робототехника.

**Для нас.** Natural-language reasoning step соответствует chunk или
манипуляционному событию, но не автоматически denoising step. Нужны отдельные
targets: сохранён ли контакт, удерживается ли нужный объект, продвинулось ли
выполнение команды. Наш P5 уже намечен в эту сторону; обзор задаёт lineage,
а не основание объявить такой модуль новым изобретением.

### S3. A Survey of Uncertainty Estimation Methods on LLMs

[Источник](https://aclanthology.org/2025.findings-acl.1101/), PDF разделы методов и
экспериментов, Figures 8-12.

**Содержание.** Сравниваются семейства uncertainty: вероятностные,
информационные, семантические и согласованность ответов. Есть экспериментальные
ROC/accuracy-rejection curves на TruthfulQA, SciQ, TriviaQA, GSM8K и SimpleQA.
Ранжирование методов зависит от данных; единственного универсального score нет.

**Для нас.** Помимо AUROC строить risk-coverage и calibration; проверять перенос
на новые клетки benchmark. Token entropy недоступна как готовая величина у
непрерывного action generator. Её нельзя заменить std латентных копий и
считать тем же методом.

### S4. From Passive Metric to Active Signal

[Источник](https://aclanthology.org/2026.findings-acl.2064/), PDF разделы 2-5.

**Содержание.** Обзор использования uncertainty для распределения вычислений,
запроса информации, self-correction и alignment. Переход от оценки к управлению
сам по себе требует отдельной проверки полезности решений.

**Для нас.** Большая uncertainty может означать «проверь физическое состояние»,
а не «вычти число из value». Это согласуется с нашими результатами, где новые
наблюдения/recovery полезнее многих статических штрафов. Однако это аналогия:
обзор не доказывает, что именно наш score подсказывает нужную интервенцию.

### S5. Uncertainty Quantification in LLM Agents

[Источник](https://aclanthology.org/2026.acl-long.738/), PDF стр. 1-8,
Table 2 и приложения с benchmark setup.

**Содержание.** Формулируется UQ для интерактивных траекторий. Четыре проблемы:
выбор estimator, неоднородные источники информации, динамика uncertainty и
нехватка детальной разметки. Проверка на tau2-bench с GPT-4.1/Kimi-K2.5 показывает,
что усреднение token-level сигналов может давать почти случайный detector:
например, Kimi на Retail имеет NLL AUROC 0.469 и entropy AUROC 0.468.

**Для нас.** Очень близкая постановка: robot actions меняют следующую
информацию. Episode-level среднее скрывает фазу ошибки и её исправление.
Нужны до-событийные оценки, observable history, hazard и полезность выбранного
ответного действия. Нельзя требовать монотонного падения uncertainty:
реальное observation может обнаружить ошибку и сначала повысить её.

### S6. When Can LLMs Actually Correct Their Own Mistakes?

[Источник](https://aclanthology.org/2024.tacl-1.78/), обзор TACL 2024.

**Содержание.** Критическая проверка self-correction: происхождение feedback,
условия честного сравнения, роль обучения. Для рассмотренных авторами работ
надежнее выглядят внешняя обратная связь и специальное обучение, чем повторный
prompt той же модели без новой информации.

**Для нас.** Перегенерация action/future/value может повторять общую ошибку.
Камера и proprio после исполнения дают внешний сигнал, но не идеальный oracle.
Нужна абляция «новый noise при старом observation» против «новый observation».
Вывод обзора ограничен его датой: более поздний SCoRe отдельно показывает
эффект обученной self-correction, поэтому «LLM не умеют исправляться» неверно.

## 2. Verifiers, поиск и ложная уверенность

### M1. Scaling LLM Test-Time Compute Optimally

[Источник](https://arxiv.org/abs/2408.03314), разделы 3-6.

**Постановка/результат.** PaLM-2 на MATH; сравниваются PRM-search и
последовательные revisions. Авторы показывают примерно четырёхкратную
экономию test-time compute относительно BoN в своих настройках.
Difficulty оценивается модель-специфично; в анализе используются большие
наборы samples, отдельно различаются oracle/model-predicted difficulty.

**Перенос.** Выбирать между sampling, verification и feedback в зависимости
от состояния, но включать стоимость самой оценки difficulty. Нет основания
переносить «4x» на Cosmos. Наши отрицательные CATE-routers также показывают,
что знать сложность недостаточно: надо знать, какая интервенция поможет.

### M2. Rewarding Progress / Process Advantage Verifiers

[Источник](https://arxiv.org/abs/2410.08146), PDF стр. 5-8, Eq. 2-5 и эксперименты.

**Постановка/результат.** Process reward измеряет изменение вероятности
конечного успеха под отдельной prover policy. Проверяются поиск и online RL;
авторы сообщают повышение точности и 1.5-5x compute efficiency относительно
ORM в своих экспериментах. Слишком слабый и слишком сильный prover могут
оба плохо различать промежуточные действия.

**Перенос.** Обучать candidate verifier по реально исполняемым ветвям и
проверять, как фиксированная continuation policy влияет на labels.
**Ключевая оговорка:** внутри одного состояния $Q(s,a)-V(s)$ даёт ровно тот же
argmax, что $Q(s,a)$. Смысл переноса в обучении, представлении и выборе prover,
не в вычитании константы. Старый terminal critic уже использовал advantage.

### M3. Let's Verify Step by Step

[Источник](https://arxiv.org/abs/2305.20050), PDF разделы 2-4, Table 1.

**Постановка/результат.** Process supervision против outcome supervision
на MATH; PRM800K содержит 800 тысяч человеческих step labels. В Table 1:
PRM 78.2% против ORM 72.4% при **best-of-1860** на 500 test problems.
В обучении используются 4500 остальных задач исходного MATH test set.

**Перенос.** Размечать место и тип ошибки, а не только конец эпизода.
Это не доказательство выигрыша при нашем K4: бюджеты отличаются на порядки,
а step annotation значительно дороже terminal label. Оригинальный split
нужно описывать явно, а для нас сохранять строгий unseen-task holdout.

### M4. The Lessons of Developing Process Reward Models

[Источник](https://aclanthology.org/2025.findings-acl.547/), экспериментальные разделы.

**Постановка/результат.** Авторы сравнивают способы process annotation и
показывают ограничения Monte Carlo completion labels; отдельно проверяют
BoN и обнаружение первой ошибки, в том числе на ProcessBench. Хороший ответ
может получиться после ошибочного процесса, поэтому BoN не заменяет step audit.

**Перенос.** Failed grasp с поздним recovery может иметь terminal success.
Хранить две метки: физическая ошибка сейчас и итог после continuation.
Один failed suffix rollout не доказывает, что предыдущий chunk был плохим;
нужны повторения и локальные events. Это предупреждение применимо и к P5.

### M5. The Limits of Inference Scaling Through Resampling

[Источник](https://arxiv.org/abs/2411.17501), скачана v3 от 26 марта 2026;
раннее название *Inference Scaling fLaws*.

**Постановка/результат.** Решения проходят ограниченные unit tests,
а истинность проверяется более полными HumanEval+/MBPP+ tests. При ненулевой
вероятности false positive повторный sampling имеет предел полезности;
с ценой ошибочного ответа оптимальный бюджет бывает небольшим.

**Перенос.** Predicted value или imagined grasp выступают неполным тестом,
реальный terminal outcome и event audit являются независимой проверкой.
Не предполагать, что K16/K64 исправят плохой verifier. Наше насыщение oracle
к K8 и несовпадение локального score с SR являются близкими, но не
идентичными явлениями: отдельно измерять coverage и selection error.

### M6. Scaling Laws for Reward Model Overoptimization

[Источник](https://proceedings.mlr.press/v202/gao23h.html), ICML 2023.

**Постановка/результат.** Синтетический gold reward используется для обучения
proxy reward; сравниваются RL и best-of-N. Более сильная оптимизация proxy
может ухудшать gold score. Gold здесь тоже модель, а не физическая реальность.

**Перенос.** По вложенным K-пулам сравнить рост выбранного predicted value,
oracle support и реального SR. Такое расхождение совместимо с ошибочной
оптимизацией proxy, но наши текущие отрицательные результаты сами по себе
не устанавливают Goodhart как единственную причину. Нужна отдельная абляция.

## 3. Семантическая uncertainty и consensus

### M7. Semantic Uncertainty

[Источник](https://arxiv.org/abs/2302.09664), ICLR 2023, разделы 3-6.

**Постановка/результат.** Ответы объединяются по смысловой эквивалентности,
после чего оценивается entropy классов смыслов. OPT оценивается на TriviaQA
и CoQA; semantic entropy лучше соответствующих baselines предсказывает ошибки.

**Перенос.** Разные action chunks могут реализовывать один успешный способ
захвата; малое покоординатное std может означать согласованный промах.
Считать uncertainty над task/contact outcomes, не над текстовыми строками
или всеми пикселями. Наш count-based вариант без sequence likelihood будет
адаптацией, а не точной реализацией вероятностного estimator статьи.

### M8. Semantic Entropy Probes

[Источник](https://arxiv.org/abs/2406.15927), разделы 3-6.

**Постановка/результат.** Linear logistic probe из hidden states одной генерации
обучается предсказывать высокий/низкий semantic entropy, вычисленный offline.
Проверяются несколько QA datasets, слои и позиции; показан перспективный
OOD transfer относительно probes, непосредственно обученных на correctness.

**Перенос.** После проверки полезности semantic uncertainty дистиллировать её
в маленькую голову поверх action/current-image tokens Cosmos. Target не
обязан быть fail. Это новый относительно наших std-metrics способ удешевления,
но точность probe не может сделать бесполезный teacher-score полезным planner.

### M9. Is MAP Decoding All You Need?

[Источник](https://aclanthology.org/2020.coling-main.398/), разделы 6-7.

**Постановка/результат.** Neural machine translation: авторы показывают,
что ошибки mode-seeking decoding не всегда означают плохое распределение.
Minimum Bayes Risk оценивает ожидаемую utility относительно samples;
сравнения включают разные language pairs и домены.

**Перенос.** Наш medoid уже является частным случаем empirical MBR при
utility, равной минус расстоянию. Однако max(value) не является MAP action
likelihood. Переносится decision-theoretic принцип, а не тождество двух
baseline. Большая масса вероятности по неверным захватам не делает их правильными.

### M10. Structure-Conditional Minimum Bayes Risk Decoding

[Источник](https://aclanthology.org/2025.emnlp-main.1616/), разделы 5-6, Eq. 10-13.

**Постановка/результат.** В instruction following глобальное сходство может
предпочитать вариант между разными структурами ответа. Предлагаются utility
cut-off, MBR внутри dominant cluster и structure-aware embeddings. На
AlpacaEval/MT-Bench авторы сообщают до +13.7 п.п. win rate в своих настройках.

**Перенос.** Отделять grasp/transport/release, объект и contact outcome.
Clustering largest mode существенно пересекается с KeyStone-style baseline,
который уже стоит в нашей очереди. Новая проверка может касаться физически
осмысленной utility, но не повторного переименования clustering. Число +13.7
не является обещанием robotic SR и не описывает все тесты работы.

### M11. Regularized Best-of-N / MBR-BoN

[Источник](https://aclanthology.org/2025.naacl-long.472/), Eq. 10, раздел 5.1.

**Постановка/результат.** Reward плюс MBR proximity regularizer. Mistral-7B
и Dolly-3B; AlpacaFarm, HH helpful/harmless. Одинаковые pools до N=128,
коэффициент выбирается на development. Gold оценщик в основном Eurus,
не ground-truth correctness. MBR-BoN превосходит BoN/MBR во многих настройках.

**Перенос.** Самый прямой prior для $value-\lambda\,consensus\_distance$.
При смене utility на OSC distance это adaptation, не принципиально новая
формула. Лучше использовать её как обязательный дешёвый baseline для P5
и провести audit уже реализованных эквивалентов, чем начинать очередной
широкий lambda sweep на просмотренных test outcomes.

## 4. Correction, calibration и policy improvement

### M12. CRITIC

[Источник](https://arxiv.org/abs/2305.11738), разделы метода и экспериментов.

**Постановка/результат.** Модель проверяет ответы инструментами и исправляет
их на основании полученного feedback. Free-form QA, mathematical program
synthesis, toxicity reduction. Улучшения оцениваются с абляциями feedback.

**Перенос.** Current RGB/proprio/contact verification -> конкретная corrective
operation -> повторная проверка. Наш RGB-regrasp ближе к такой системе,
чем к изменению scalar value. Отличие: вызов инструмента в NLP часто обратим,
реальный motion имеет цену и может ухудшить состояние. Simulation branching
разрешается для обучения, но не превращается в доступный роботу rollback.

### M13. SCoRe

[Источник](https://arxiv.org/abs/2409.12917), разделы 4-6, Tables 2-4.

**Постановка/результат.** Two-stage multi-turn RL обучает исправление
собственных ошибок. На MATH/HumanEval авторы сообщают +15.6/+9.1 п.п.
к метрике улучшения self-correction, а не общему успеху произвольного агента.
Offline SFT имеет distribution mismatch и может схлопнуть correction behavior.

**Перенос.** Учить recovery на ошибках текущей policy; сохранять correct-to-correct
примеры и штрафовать success-to-fail. Это продолжение P3 с обучением corrective
policy, не текущий P3e router. Нельзя учить только на найденных fail и затем
ожидать, что модуль не испортит нормальные траектории.

### M14. Direct Preference Optimization

[Источник](https://arxiv.org/abs/2305.18290), Eq. 7 и эксперименты.

**Постановка/результат.** Preference pairs позволяют обучать policy через
логарифмы отношений вероятностей к reference без отдельного RLHF reward model.
Sentiment, summarization и single-turn dialogue; сравнение с PPO/RLHF.

**Перенос.** Exact-state success/fail candidate pairs являются естественными
preference pairs. Но pairwise critic, который только выбирает action, не
является DPO: DPO меняет generator. Для Cosmos требуется корректная
diffusion/flow objective, а не подстановка clipped value вместо log probability.

### M15. Conformal Language Modeling

[Источник](https://arxiv.org/abs/2306.10193), разделы 3-4.

**Постановка/результат.** Калибруются sampling-stop и rejection rules,
чтобы множество генераций содержало хотя бы один приемлемый ответ.
Проверки на QA, summarization и radiology report generation.

**Перенос.** Калибровать размер candidate set и abstain/requery, учитывая
обменимость calibration/test. **Наличие хорошего кандидата в множестве не
гарантирует, что selector выберет его.** Стандартная гарантия также не
распространяется автоматически на OOD и зависимые queries одного rollout.
Наши conformal-наработки уже частично покрывают эту линию.

### M16. Self-Consistency

[Источник](https://arxiv.org/abs/2203.11171), Tables 2-3 и sampling ablations.

**Постановка/результат.** Несколько reasoning chains голосуют за конечный
ответ. На GSM8K сообщается +17.9 п.п. в соответствующих крупных моделях;
оцениваются также SVAMP, AQuA, StrategyQA, ARC.

**Перенос.** Голосование относится к эквивалентным ответам, а не арифметическому
усреднению рассуждений. Аналогично нельзя усреднить две несовместимые
траектории вокруг препятствия или два способа захвата. Выбирать существующий
candidate внутри режима. Общий ошибочный режим остается основным риском.

### M17. Solve-Detect-Verify / FlexiVe

[Источник](https://aclanthology.org/2026.acl-long.2190/), разделы 3-4,
Table 12 и Appendix A.4.5/Table 19.

**Постановка/результат.** Fast/slow verifier и итеративное исправление.
На AIME 2024 при N=16: SDV 83.3%, majority 80.0%, GenPRM BoN 66.7%
(Table 12). Это небольшой 30-question benchmark. В Appendix A.4.5 detector
не переносится автоматически: для Qwen3-8B на AIME 2024 solve+detect даёт
60.9% против 83.3% baseline.

**Перенос.** Дешёвый observable event-head вызывает дорогой verifier/recovery
только при необходимости. Нельзя копировать textual hesitation markers или
фиксированный timing в robot controller. Эта работа поддерживает архитектуру
многоступенчатой проверки, но одновременно предупреждает о непереносимых triggers.

## 5. Мост к diffusion / flow matching

### B1. Diffusion-DPO

[Источник](https://arxiv.org/abs/2311.12908), раздел 3 и эксперименты.

**Постановка/результат.** DPO переносится на image diffusion через
diffusion likelihood bound. SDXL обучается на Pick-a-Pic; в этой версии
статьи авторы сообщают 69% human preference над SDXL base+refiner на PartiPrompts.

**Перенос.** Учить action generation по фактическим preferences, сохраняя
reference model. Но Cosmos использует совместные action/future/value блоки:
нельзя награждать выдуманную «картинку успеха». Actions сравнивать по реальным
ветвям, future prediction удерживать на реальных transition targets.
Это мост, не готовая реализация flow-DPO для нашей модели.

### B2. DDPO

[Источник](https://arxiv.org/abs/2305.13301), разделы 3-5.

**Постановка/результат.** Denoising представляется как MDP; policy gradient
оптимизирует reward конечного изображения. Рассматриваются compressibility,
aesthetics и prompt-image alignment; сравниваются reward-weighted alternatives.

**Перенос.** Можно связать reward реально исполненного chunk с породившим
его denoising path. Однако diffusion steps и robot steps образуют два разных
уровня времени. Нужен sampler с определёнными transition probabilities;
одного факта разных initial noise seeds недостаточно для прямого PPO ratio.

### B3. Flow-GRPO

[Источник](https://arxiv.org/abs/2505.05470), скачана v5; раздел 4, Eq. 4-7,
Tables 1-2 и reward-hacking ablation.

**Постановка/результат.** ODE-to-SDE преобразование позволяет GRPO для
flow matching; group-relative rewards и KL к reference. На SD3.5-M авторы
показывают GenEval 63% -> 95%, visual text accuracy 59% -> 92%.
Без KL наблюдаются проблемы качества/разнообразия в отдельных rewards.

**Перенос.** Наиболее прямой технический кандидат для будущего обучения Cosmos,
если ограничение находится в proposal support. Reward должен приходить из
реального исполнения, не predicted value. Когда все rewards группы одинаковы,
relative advantage вырождается; поэтому наш audit mixed pools важен и для RL.
Качество изображений на GenEval не является доказательством улучшения robotics.

## 6. Итог по литературе

1. Самый близкий **готовый inference-only baseline**: MBR-BoN.
2. Самая полезная **методологическая линия для P5**: PRM/PAV с независимыми
   terminal/event labels и within-state evaluation.
3. Самая согласованная с **нашими положительными результатами архитектура**:
   externally grounded detect -> verify -> correct, с защитой от ненужного recovery.
4. Самый прямой **путь изменения generator**: flow-compatible preference/RL
   после проверки support и качества verifier, а не немедленный большой fine-tuning.
5. Нет оснований объявлять один из этих методов SOTA на нашей постановке
   до matched LIBERO-PRO эксперимента. У разных статей разный доступ к
   ground truth, бюджет sampling, обучению, инструментам и test distributions.

# Nikita Kachaev: статьи, структура и связь с нашим исследованием

Уточнение автора закрыто 10 сентября 2026. [Личный сайт](https://tttonyalpha.github.io/)
содержит ссылку на тот же
[Scholar ID GdG_BDsAAAAJ](https://scholar.google.com/citations?user=GdG_BDsAAAAJ&hl=en).
На первых страницах MIKASA v3 и Memory Taxonomy v2 у Nikita Kachaev указана
**ITMO University AI Talent Hub**. Аффилиации других работ зависят от версии;
их не заменяем автоматически на ITMO. Scholar продолжает возвращать 429,
но идентификация подтверждена через первичные источники.

Скачаны восемь близких работ в общей подборке. Это выбранные статьи с личной
страницы, не гарантия полноты всего Scholar-профиля. PDF хранятся обычными
файлами на D:, с префиксом `kachaev_`; [manifest](../manifest.json) и
[SHA-256 / версии](../download_report.json). Ниже разобраны введения, методы,
основные опыты и подача ограничений; результаты авторов не воспроизводились.

## Порядок чтения

| Приоритет | Работа | Версия в папке | Зачем читать |
| --- | --- | --- | --- |
| 1 | [Don't Blind Your VLA](../pdfs/kachaev_blind_vla.pdf) | arXiv 2510.25616v1, 2025; автор сообщает AAMAS 2026 Oral | Диагностика визуального bottleneck перед исправлением |
| 2 | [muVLA](../pdfs/kachaev_mu_vla.pdf) | arXiv 2606.12497v1, 2026; preprint | Изоляция одного механизма, вмешательства в память, chunk length |
| 3 | [VLA Grounder](../pdfs/kachaev_vla_grounder.pdf) | arXiv 2607.04517v1, 2026; работа связана с ICML DEMO workshop | Улучшение frozen policy через входную команду |
| 4 | [Memory, Benchmark & Robots / MIKASA](../pdfs/kachaev_mikasa.pdf) | arXiv 2502.10550v3; ICLR 2026 | Как построить benchmark вокруг конкретных проверяемых свойств |
| 5 | [Unraveling the Complexity of Memory](../pdfs/kachaev_memory_taxonomy.pdf) | arXiv 2412.06531v2; ICLR 2026 | Как определения определяют корректность эксперимента |
| 6 | [Does VLA Even Know the Basics? / Act2Answer](../pdfs/kachaev_act2answer.pdf) | arXiv 2606.19297v1; preprint | Отделение смысловой ошибки от механической |
| 7 | [A New Perspective on Transformers in Online RL](../pdfs/kachaev_online_transformers.pdf) | arXiv 2510.13367v1; автор указывает ICLR 2025 workshop | Систематическое исследование архитектурных решений |
| 8 | [Mind and Motion Aligned / Kitchen-R](../pdfs/kachaev_mind_motion.pdf) | arXiv 2508.15663v1 | Модульный и end-to-end анализ planning/control |

Две ICLR-работы явно помечены как conference papers в сохранённых PDF.
Workshop и preprint не называем main-conference papers. Прямой старый PDF-link
VLA Grounder на личной странице не работает; использована публичная arXiv-версия.

## 1. Don't Blind Your VLA

Kachaev, Kolosov, Zelezetsky, Kovalev, Panov.
[Статья](https://arxiv.org/abs/2510.25616), [проект](https://blind-vla-paper.github.io/).

**Аргумент:** сначала диагностируются изменения representations после action
fine-tuning, затем предлагается alignment с frozen visual teacher. Разделы
4–5 задают VL-Think и probing; 6 вводит метод; 7–8 проверяют эффект и ablations.
В сохранённой v1 основные OOD-опыты основаны на Simpler, с осями Semantics,
Vision, Execution; это не наш LIBERO-PRO valid199. Table 1 показывает не
универсальный выигрыш: например Position 0.43→0.58, но PosChangeTo 0.23→0.20.

$$
\mathcal L=\mathcal L_{\rm action}
-\lambda\frac1J\sum_{j=1}^{J}\cos\big(P_\phi h_j(I),E_{\rm teacher}(I)_j\big).
$$

Это краткая запись alignment-идеи: $h_j$ — visual feature, $P$ — projector,
teacher заморожен. **Для нас:** сначала проверить качество предметных признаков,
а затем менять training objective. Cosmos использует video diffusion backbone,
поэтому это не готовый OpenVLA-плагин. При написании перенять цепочку
«диагностика → адресное вмешательство → улучшение → случаи без улучшения».

## 2. muVLA

Cherepanov, Kachaev et al.
[Статья](https://arxiv.org/abs/2606.12497), [проект](https://avanturist322.github.io/mu-vla/).

Контролируемое добавление recurrent memory tokens в OpenVLA-OFT, с TBPTT и
attention mask, запрещающей памяти читать action tokens. Сравниваются
episodic dataloader, память и способы её обновления. На пяти training tasks
MIKASA-Robo SR 0.42→0.84; отдельный episodic baseline уже даёт 0.48.
Для переноса выделены matched и novel memory semantics, а не только общий average.

Особенно полезны §5.3: noise/freeze-first interventions, изменение execution
chunk и длины фаз. Всплески $1-\cos(M_t,M_{t-1})$ совпадают и с нормальными
сменами фазы. **Наш вывод:** аналогичный всплеск uncertainty не является сам
по себе доказательством предстоящей ошибки. Сравнивать надо внутри фаз и
с помощью вмешательств. Их $K$ — длина TBPTT, не наше число action samples.
Это обучение recurrent модели, не inference-only medoid для frozen Cosmos.

## 3. VLA Grounder

Shodiev, Staroverov, Kachaev, Kovalev, Panov.
[Статья](https://arxiv.org/abs/2607.04517), [проект](https://tttonyalpha.github.io/vla_grounder/).

Оптимизируется не action policy, а генератор команды для неё:

$$
\tilde\ell\sim q_\phi(\cdot\mid o,\ell),\qquad
A\sim\pi_\theta(\cdot\mid o,\tilde\ell),\qquad
\max_\phi\;\mathbb E[R],\quad\theta\ \text{frozen}.
$$

§3 фиксирует интерфейс; §4 описывает failure-derived prior и GRPO; §5
сравнивает original command, rewrite до RL, обученный rewrite и альтернативы
prompt optimization на VL-Think/RL4VLA. Это не просто генерация разных seeds:
меняется conditioning и доступное распределение действий.

**Для нас:** проверить семантически эквивалентные команды при одинаковых
state/seeds и бюджете. Сначала фиксированные rewrites, затем обучаемый выбор
только при наличии эффекта. Не менять цель задачи и не выбирать rewrite по
test success. Frozen action backbone не означает отсутствие training cost:
upstream policy обучается на rollout rewards.

## 4. MIKASA

Cherepanov, Kachaev, Kovalev, Panov.
[Статья](https://arxiv.org/abs/2502.10550),
[ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2026/hash/1088fffae5f2aa8c8324e4f45f62248d-Abstract-Conference.html).

§4 классифицирует memory-intensive tasks, §5 объединяет базовые среды,
§6 вводит MIKASA-Robo с 32 задачами. Таблицы привязаны к типам использования
памяти; appendix раскрывает механизмы задач. Это хороший образец benchmark
статьи: сначала capability, затем конструкция задач и только потом rankings.

**Для нас:** разделять partial observability, неверный выбор объекта, contact
failure и недостаток candidates, а не считать все timeout одним типом fail.
MIKASA не является drop-in заменой LIBERO-PRO для pretrained Cosmos: нужны
совместимый controller, observation contract и проверка zero-shot domain gap.
Использовать сейчас как методологический образец, не незаметно менять benchmark.

## 5. Unraveling the Complexity of Memory

Cherepanov, Kachaev, Zholus, Kovalev, Panov.
[Статья](https://arxiv.org/abs/2412.06531).

Определения memory вводятся до evaluation. В §5 сравниваются context length
агента и correlation horizon задачи на T-Maze, Minigrid-Memory и POPGym.
Смешанные горизонты могут создавать впечатление long-term memory там, где
достаточно доступного контекста. Это не LIBERO-эксперимент.

**Перенять:** сначала операционное определение того, что хотим измерить.
Наши понятия candidate diversity, latent-copy disagreement, failure prediction
и intervention utility тоже нельзя подменять одним словом uncertainty.
Контекст модели, предсказываемый T, выполняемый H и задержка до события должны
иметь разные обозначения и собственные контроли. Главный приём статьи:
демонстрировать конкретный ошибочный вывод при нарушении протокола.

## 6. Act2Answer

Kachaev, Moskalenko et al.
[Статья](https://arxiv.org/abs/2606.19297), [проект](https://tttonyalpha.github.io/act2answer/).

Knowledge questions превращены в выбор зоны размещения предмета; control
упрощён, чтобы уменьшить смешение смысловой ошибки с моторным провалом.
§3–4 связывают интерфейс, зоны correct/wrong/out-of-bounds и layerwise probing.
Авторы сравнивают семь VLA и девять VLM; анализ включает перестановку вариантов,
важную для отделения знания от пространственного предпочтения.

**Для нас:** кроме terminal SR хранить correct-object/target, miss-grasp,
drop и invalid-action events; обмен left/right проверяет position bias.
Это дополнительные диагностические labels, не автоматическая причинная
классификация. Высокая точность probe ещё не означает, что action head
использует информацию. Нужна связь с поведением при контролируемом вмешательстве.

## 7. Transformers in Online RL

Kachaev, Zelezetsky, Cherepanov, Kovalev, Panov.
[Статья](https://arxiv.org/abs/2510.13367).

Работа исследует дизайн policy/value networks, совместное использование
компонентов, conditioning и нарезку последовательностей в online model-free
continuous control. Во введении прямо сказано, что цель — практические
архитектурные выводы, а не принципиально новая архитектура.

**Перенять:** вопрос → контролируемое изменение → устойчивость по настройкам;
не выдавать число ablations за число новых методов. Для будущего trained
value/recovery head отдельно проверять представление, loss и данные, а не
менять все три сразу. Это не прямой baseline frozen Cosmos в LIBERO-PRO.

## 8. Mind and Motion Aligned

Kachaev, Spiridonov et al.
[Статья](https://arxiv.org/abs/2508.15663).

Kitchen-R на Isaac Sim разделяет оценку high-level planning, low-level policy
и интегрированной системы. §III–IV задают постановку и метрики до описания
benchmark и результатов. Этим снимается предположение о безошибочном
исполнении плана.

**Перенять:** offline scorer accuracy, usefulness выбранного chunk и итоговый
episode SR показывать отдельно. Составной score допустим только вместе с
компонентами, иначе он может скрыть рост harms. Kitchen-R — mobile manipulation
и другой симулятор, не ещё одна perturbation нашего LIBERO-PRO.

## Практическая адаптация к Cosmos: наш план, не результат этих статей

### A. Отделить фазу от риска

Для метрики $U_q$ построить на train-группах фазовый baseline:

$$
z_q=\frac{U_q-\operatorname{median}_{\rm train}(U\mid\varphi_q)}
{\operatorname{MAD}_{\rm train}(U\mid\varphi_q)+\epsilon}.
$$

$\varphi_q$ должна оцениваться по доступным наблюдениям, не по будущему fail.
Сравнить raw $U$, фазово-нормированный $z$ и простой phase-only predictor,
затем AUROC/AUPRC и полезность intervention на untouched task/init clusters.
Это предлагаемая проверка confound, не опубликованный авторами failure detector.

### B. Проверить coverage через conditioning

Контроли: original text; фиксированный равноценный paraphrase; grounded rewrite
из текущего RGB; дополнительные stochastic samples при original text.
Сравнивать одинаковое число candidates/rollouts и семантически ту же цель.
Отдельно измерить, появился ли successful candidate в ранее all-fail pool,
а не только вырос score выбранной ветки. Зафиксировать repeats и splits.

В нашем [cosmos_utils.py](../../../../cosmos-policy/cosmos_policy/experiments/robot/cosmos_utils.py)
`get_t5_embedding_from_cache` может вычислять новые embeddings, но имеет и
canonical aliases. Поэтому логировать **реально переданный embedding** и
проверять, что rewrite не свёлся к старому ключу. Стоимость T5 и upstream VLM
включать в budget. Замена строки в логе сама по себе не доказывает изменение input.

### C. Память исследовать после простого контроля

Сначала сравнить current observation с минимальной историей при явной
partial observability; проверять simulator replay и отсутствие future leakage.
В Cosmos нельзя просто вставить memory tokens OpenVLA-OFT: у нас другой
latent/video interface, positional encoding и маски. Добавление recurrent
модуля потребует обучения и отдельного data/compute-matched baseline.

### Что перенять для рукописи прямо сейчас

- Introduction: назвать конкретный источник ошибки, не абстрактную «неуверенность».
- Methods: явно отделить frozen и trainable компоненты, online и offline inputs.
- Results: сначала механистический тест, затем общий SR; отрицательный transfer
  оставлять рядом с положительным in-domain результатом.
- Figures: видео, query boundary и метрика по общей временной оси; spike
  сопоставлять также с успешными сменами фаз.
- Novelty: taxonomy и аккуратная isolation study могут быть вкладом, но
  «новый medoid» и «добавили память» без отличия от prior art недостаточны.

Общий [план публикации](../../PLAN.md) дополнен этими контролями. Эксперименты
в этом обновлении не запускались; frozen queued protocols не менялись.

# Как писать статью: близкие работы и сильные образцы

Подборка 10 сентября 2026. Критерий не «объективно лучшие люди мира», а
близость задачи, ясность постановки, качество контролей и воспроизводимость.
Представлены группы Shuran Song/Chelsea Finn, Sergey Levine/Yilun Du,
Danijar Hafner, Andrea Bajcsy/Marco Pavone, Ravi Netravali, Lorenzo Natale,
Andreas Krause/Angela Schoellig и исследователи надёжной оценки RL.

Просмотрены PDF: введения, формулировки методов, структура экспериментов,
ключевые ограничения. Это сравнительный редакторский разбор, не независимое
воспроизведение всех результатов или проверка всех теорем. Версии PDF,
источники и SHA указаны в [manifest](reference_papers/manifest.json) и
[отчёте загрузки](reference_papers/download_report.json). Уточнённый автор
Scholar-профиля — Nikita Kachaev; добавлен
[разбор восьми его работ](reference_papers/requested_profile/README.md).

## Сначала прочитать эти пять

### 1. Cosmos Policy

Kim et al., arXiv:2601.16163v1, 2026.
[Источник](https://arxiv.org/abs/2601.16163), [PDF](reference_papers/pdfs/cosmos_policy.pdf).

В Figure 1 сразу показан контракт input → action / future / value. Раздел 4
связывает representation и training; раздел 5 отдельно задаёт вопросы
экспериментов, benchmarks, ablations и использование rollout data для planning.
Direct policy и autoregressive planning не спрятаны под одной меткой.

**Перенять:** первая схема должна объяснять именно наши query и observable
inputs; таблицы разделять по planning mode и данным обучения. **Не переносить:**
их headline SR в нашу OOD-таблицу; наш joint K4 selector не воспроизводит
авторскую a→s→v процедуру. Модель backbone заимствована, это не наш вклад.

### 2. KeyStone

Dai, Chen, Yang, Netravali, arXiv:2605.08638v1, 2026 (preprint).
[Источник](https://arxiv.org/abs/2605.08638), [PDF](reference_papers/pdfs/keystone.pdf).

Разделы 3.2 и 3.3 отделяют parallel sampling от cluster/medoid selector;
раздел 4 отдельно проверяет latency, success и ablations. Guard не допускает
бессмысленного разбиения одного mode. В Limitations явно признаются ошибочное
большинство и невозможность выбрать success из all-fail candidates.

**Перенять:** измерить и качество, и стоимость, показать K и guard ablations.
**Для нас:** отсутствие coverage уже известное ограничение; новизна должна
быть в его измерении/решении и переносе, а не в самом слове consensus. Их
latency benefit нельзя обещать для нашего Cosmos на shared GPU без profiling.

### 3. KDPE

Rosasco, Ceola, Pasquale, Natale, CoRL 2025, arXiv:2508.10511v2.
[Источник](https://arxiv.org/abs/2508.10511), [PDF](reference_papers/pdfs/kdpe.pdf).

Методология вводит kernel для position, orientation и gripper, затем разделяет
experimental setup, results и limitations. Endpoint density привязана к
конкретной action representation. Таблица гиперпараметров делает реализацию
проверяемой; авторы тестируют simulation и real robot.

**Перенять:** перед формулой определить пространство, единицы и горизонт;
вынести settings в таблицу. **Для нас:** induced OSC endpoint не равен
предсказанному end-effector pose. K4-adaptation нельзя назвать точным
воспроизведением N100. Изменение масштаба distance не доказывает новый принцип.

### 4. Diffusion Policy

Chi et al., RSS 2023, здесь исходный arXiv:2303.04137v1, не IJRR extension.
[Проект](https://diffusion-policy.cs.columbia.edu/), [PDF](reference_papers/pdfs/diffusion_policy.pdf).

Объяснение receding horizon отделяет observation, prediction и action horizons.
Архитектура и представление действий проверяются контролируемыми вариантами,
а качественные изображения поясняют multimodality, а не заменяют числа.

**Перенять:** одна timeline-схема с T=16 и H=8/16 предотвращает путаницу между
query, кадром и полным episode. **Не переносить:** уверенность в chunk не
означает однозначный правильный путь; разные траектории могут быть успешными.
Оригинальный RSS и расширенный IJRR тексты имеют разные author lists/версии.

### 5. Reliable RL Evaluation / rliable

Agarwal et al., NeurIPS 2021, arXiv:2108.13264v4.
[Источник](https://arxiv.org/abs/2108.13264), [PDF](reference_papers/pdfs/rliable.pdf).

Статья начинает с проблемы ненадёжных сравнений и показывает её на реальных
benchmark rankings; инструменты появляются как ответ на диагностированный
дефект. Раздел 4 предлагает интервалы и распределения вместо одной красивой
точечной оценки. Изменение evaluation protocol рассматривается как отдельная
причина несопоставимости результатов.

**Перенять:** указывать estimand, единицу независимости, CI и полный набор
сравнений. **Для нас:** binary paired SR не нужно автоматически заменять IQM
из Atari; нужен task/init-cluster bootstrap и анализ rescue/harm. Пять best
videos не являются оценкой частоты выигрыша.

## Следующий круг: структура научного аргумента

### 6. Diffuser

Janner, Du, Tenenbaum, Levine, ICML 2022.
[PMLR](https://proceedings.mlr.press/v162/janner22a.html), [PDF](reference_papers/pdfs/diffuser.pdf).

Problem setting предшествует generative planning; свойства planner вынесены
в отдельный раздел перед evaluation. Эксперименты разделены по long horizon,
test-time flexibility, offline RL и warm-start efficiency.

**Перенять:** каждое заявленное свойство получает отдельный опыт, а не только
одну итоговую SR. **Граница аналогии:** Diffuser генерирует trajectories для
offline RL, а мы используем pretrained world-action policy и другой action
контракт; нельзя считать методы готовыми взаимозаменяемыми baselines.

### 7. TD-MPC2

Hansen, Su, Wang, ICLR 2024, arXiv:2310.16828v2.
[Источник](https://arxiv.org/abs/2310.16828), [PDF](reference_papers/pdfs/tdmpc2.pdf).

Раздел 3 явно разделяет learning implicit model, MPC и generalist training.
Evaluation использует много задач и фиксированные настройки; lessons,
opportunities and risks отдельно отделяют установленное от перспектив.

**Перенять:** отделить learning от inference и проверять устойчивость одной
конфигурации на новых задачах. **Не переносить:** их online RL результаты
не доказывают качество frozen Cosmos. Заявление generality требует широты
тестов; success в одной заранее выбранной cell недостаточен.

### 8. DreamerV3

Hafner, Pasukonis, Ba, Lillicrap, Nature 2025.
[Журнальная версия](https://www.nature.com/articles/s41586-025-08744-2),
[PDF](reference_papers/pdfs/dreamerv3.pdf).

Главная идея об универсальности подкрепляется разными domains, масштабированием
и абляциями robustness-компонентов; Methods выносит технические детали,
сохраняя основную линию текста. Это образец согласования масштаба заявления
и доказательств, но не готовый формат ICLR.

**Перенять:** предельно ясный центральный вопрос и figures, раскрывающие
обобщение. **Не переносить:** обещания «работает везде» по одному роботу или
копирование структуры Nature вместо официального ICLR template.

### 9. Self-Consistency

Wang et al., ICLR 2023.
[OpenReview](https://openreview.net/forum?id=1PL1NIMMrw),
[PDF](reference_papers/pdfs/self_consistency.pdf).

Figure 1 показывает отличие greedy от sample-and-marginalize на понятном
примере. Текст последовательно связывает diversity, aggregation и evaluation
на разных reasoning benchmarks.

**Перенять:** на первой странице показать, что именно меняется в inference.
**Граница аналогии:** совпадение дискретного ответа не равно близости
непрерывных control chunks; два далёких action modes могут оба быть верными.
Общая идея «семплировать несколько и выбирать согласованное» уже prior art.

### 10. Flow-VLA Uncertainty Quantification

Römer et al., arXiv:2606.18043v1, 2026 (preprint).
[Источник](https://arxiv.org/abs/2606.18043), [PDF](reference_papers/pdfs/flow_uq.pdf).

Раздел 4 формализует velocity-field disagreement; раздел 5 связывает его
с active fine-tuning; evaluation разделяет uncertainty quality и downstream
пользу. Limitations отмечает стоимость хранения/обучения ensemble.

**Перенять:** дать конкретный estimator, aggregation axes и момент доступности;
не называть любую variance epistemic uncertainty. **Для нас:** stochastic
samples одного frozen checkpoint не заменяют независимо обученный ensemble;
failure AUROC, sample efficiency и closed-loop SR отвечают разным вопросам.

### 11. UNISafe

Seo, Nakamura, Bajcsy, CoRL 2025, arXiv:2505.00779v2.
[Источник](https://arxiv.org/abs/2505.00779), [PDF](reference_papers/pdfs/unisafe.pdf).

Setup задаёт latent safety filter через reachability, затем вводится
uncertainty-aware вариант и вычислительная процедура. Safety определяется
до экспериментов, а не по визуальному впечатлению от trajectories.

**Перенять:** заранее определить unsafe set/event, observable trigger и fallback;
показать цену вмешательства. **Граница:** вероятностная гарантия фильтра
с определёнными assumptions не переносится на наш value penalty. Наш drop
proxy и benchmark timeout нельзя выдавать за такую safety guarantee.

### 12. StressDream

Seo et al., arXiv:2606.00267v1, 2026; в подборке preprint-версия.
[Источник](https://arxiv.org/abs/2606.00267), [PDF](reference_papers/pdfs/stressdream.pdf).

Figure 1 показывает не только steering к failures, но и ограничение
правдоподобия. После setup идёт простой Dubins case study, затем более
сложные policy evaluation/improvement опыты; limitations обсуждают роль
текстового задания опасного исхода.

**Перенять:** сначала идентифицируемый механизм на простом контролируемом
опыте, затем transfer. **Для нас:** специально подобранный worst case полезен
как stress test, но не как unbiased SR. Неправдоподобная hallucinated failure
не должна служить ground truth для безопасности.

### 13. LIBERO-PRO

Zhou et al., arXiv:2510.03827v1, 2025.
[Источник](https://arxiv.org/abs/2510.03827), [PDF](reference_papers/pdfs/libero_pro.pdf).

Мотивация связывает запоминание исходных условий с robustness evaluation;
perturbation axes превращают общий OOD-вопрос в проверяемые изменения среды.

**Перенять:** таблица benchmark factor → что меняется → что неизменно.
**Для нас:** task suite Object и perturbation factor Object не одно понятие.
Наш valid199 нужно назвать subset и раскрыть исключённый пустой asset;
усреднение по factors не подменять объединённой долей successes.

### 14. LIBERO

Liu et al., 2023, здесь arXiv:2306.03310v1.
[Источник](https://arxiv.org/abs/2306.03310), [PDF](reference_papers/pdfs/libero.pdf).

Research topics предшествуют benchmark design; task suites разделяют виды
переносимого знания. Evaluation metrics введены до результатов lifelong
learning, а не выбраны после просмотра удачных цифр.

**Перенять:** явно сопоставить каждый split исследовательскому вопросу.
**Граница:** наш frozen-policy rollout не воспроизводит lifelong learning
protocol исходной статьи. Успех на LIBERO ID не тождественен OOD robustness.

## Дополнение: Nikita Kachaev

В общей папке теперь 22 PDF. Подробности, формулы и версии восьми добавленных
работ находятся в [отдельном разборе](reference_papers/requested_profile/README.md).

| Работа | Приём для нашей статьи |
| --- | --- |
| Don't Blind Your VLA | Сначала диагностировать bottleneck, потом вводить исправляющее вмешательство |
| muVLA | Изолировать recurrence от dataloader и execution cadence; проверять причинность через interventions |
| VLA Grounder | Показать точную границу frozen policy и trainable conditioning; учитывать полный rollout budget |
| MIKASA | Выводить benchmark splits из таксономии исследуемых свойств |
| Memory Taxonomy | Определить capability и контекст до подсчёта метрик |
| Act2Answer | Разделять смысловое решение и качество физического исполнения |
| Transformers in Online RL | Менять один архитектурный или training-фактор за раз |
| Mind and Motion Aligned | Не подменять end-to-end SR качеством отдельного модуля |

Наиболее полезная коррекция нашей интерпретации: фазовый всплеск метрики не
обязательно является fail-сигналом. Это мотивирует phase-matched контроли,
но не доказывает заранее их выигрыш на наших данных.

## Общие приёмы, которые применяем в нашей рукописи

1. Один центральный вопрос, три проверяемых тезиса вместо истории всех запусков.
2. Figure 1: одинаковое начальное наблюдение, K candidates, выбор/feedback,
   реальный исход; никакого post-failure leakage в online feature.
3. Формула: сначала размеры, единицы и доступные данные, затем estimator,
   aggregation и decision rule. Отдельно sample RNG и rollout RNG.
4. Main table: benchmark, n, T/H/K/denoise, baseline, cost, SR и CI в caption.
5. Абляция меняет одну гипотезу: sampling vs selection, fresh vs stale,
   recovery primitive vs router, representation vs число candidates.
6. В Results отдельно число, неопределённость, интерпретация. Пишем «не нашли
   убедительного преимущества», а не «методы одинаковы» при wide CI.
7. Related Work: не преувеличивать отличие geometry/kernel подходов. Наш
   перспективный вклад лежит в диагностике и выборе типа вмешательства.
8. Не копировать чужие формулировки или figures. Своя схема и свои результаты;
   полные PDF для чтения отдельно, цитаты и библиография в рукописи.

Итог: сильный текст не компенсирует отсутствие evidence. У нас уже есть
материал для аккуратной рукописи, но широкий transferable planning gain и
новизну ещё требуется доказать по [PLAN](PLAN.md).

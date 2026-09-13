# LLM/NLP -> Cosmos Policy: подборка и план переноса

Дата поиска и проверки: **9 сентября 2026 года**.

**26 скачанных PDF: 6 обзоров/обзорно-позиционных работ, 17 исследований
LLM/NLP и 3 работы, связывающие preference learning / RL с diffusion и flow matching.**
Это целевая подборка под нашу задачу, не исчерпывающий systematic review и не
таблица универсального SOTA. Новых робототехнических запусков в рамках этого
обзора не проводилось; существующая очередь экспериментов не изменена.

## Где читать

1. [Аналогия, формулы, приоритеты и план экспериментов](ANALOGY_AND_PLAN.md).
2. [Разбор каждой статьи: постановка, результаты и ограничения переноса](PAPER_REVIEW.md).
3. [Машинный каталог источников](papers.json).
4. [Проверка загрузок: размеры, число страниц и SHA-256](download_manifest.json).
5. [Проверка актуальных страниц, названий и версий](source_audit.json).

Связанные материалы проекта: [основной обзор](../LIBERO_EXPERIMENTS_AND_PAPERS.md),
[roadmap](../../experiments/RESEARCH_ROADMAP_20260820.md),
[сводка наших результатов](../../experiments/RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md).

## С чего начать

- **S5 + S6:** почему uncertainty одиночного ответа и самопроверка без нового
  сигнала недостаточны для интерактивного агента.
- **S2 + M2 + M4:** как обучать verifier промежуточного действия и не путать
  локальную корректность с конечным успехом.
- **M11 + M10:** ближайшие NLP-аналоги нашего consensus/reranking.
- **M17:** свежий пример архитектуры generate -> detect -> verify -> correct.
- **B3:** технический мост к обучению именно flow-based генератора.

## Обзоры

| ID | Работа | Год | Локальный PDF | Первоисточник |
|---|---|---:|---|---|
| S1 | A Survey on Test-Time Scaling in LLMs: What, How, Where, and How Well? | 2025 | [PDF](S1_2503.24235_test_time_scaling_survey.pdf) | [arXiv](https://arxiv.org/abs/2503.24235) |
| S2 | A Survey of Process Reward Models | 2026 | [PDF](S2_2026.acl-long.163_process_reward_survey.pdf) | [ACL](https://aclanthology.org/2026.acl-long.163/) |
| S3 | A Survey of Uncertainty Estimation Methods on LLMs | 2025 | [PDF](S3_2025.findings-acl.1101_uncertainty_survey.pdf) | [ACL Findings](https://aclanthology.org/2025.findings-acl.1101/) |
| S4 | From Passive Metric to Active Signal | 2026 | [PDF](S4_2026.findings-acl.2064_active_uncertainty.pdf) | [ACL Findings](https://aclanthology.org/2026.findings-acl.2064/) |
| S5 | Uncertainty Quantification in LLM Agents | 2026 | [PDF](S5_2026.acl-long.738_agent_uncertainty.pdf) | [ACL](https://aclanthology.org/2026.acl-long.738/) |
| S6 | When Can LLMs Actually Correct Their Own Mistakes? | 2024 | [PDF](S6_2024.tacl-1.78_self_correction_survey.pdf) | [TACL](https://aclanthology.org/2024.tacl-1.78/) |

## Методы и контрольные исследования

Год в таблице соответствует первому arXiv или указанной proceedings-версии;
это не всегда год последней редакции. В частности, M5 скачан в редакции 2026 года.

| ID | Работа | Год | Локальный PDF | Первоисточник |
|---|---|---:|---|---|
| M1 | Scaling LLM Test-Time Compute Optimally | 2024 | [PDF](M1_2408.03314_compute_optimal.pdf) | [arXiv](https://arxiv.org/abs/2408.03314) |
| M2 | Rewarding Progress: Process Advantage Verifiers | 2024 | [PDF](M2_2410.08146_process_advantage_verifiers.pdf) | [arXiv](https://arxiv.org/abs/2410.08146) |
| M3 | Let's Verify Step by Step | 2023 | [PDF](M3_2305.20050_verify_step_by_step.pdf) | [arXiv](https://arxiv.org/abs/2305.20050) |
| M4 | The Lessons of Developing Process Reward Models | 2025 | [PDF](M4_2025.findings-acl.547_prm_lessons.pdf) | [ACL Findings](https://aclanthology.org/2025.findings-acl.547/) |
| M5 | The Limits of Inference Scaling Through Resampling | 2024/2026 | [PDF](M5_2411.17501_imperfect_verifiers.pdf) | [arXiv](https://arxiv.org/abs/2411.17501) |
| M6 | Scaling Laws for Reward Model Overoptimization | 2023 | [PDF](M6_gao23h_reward_overoptimization.pdf) | [ICML](https://proceedings.mlr.press/v202/gao23h.html) |
| M7 | Semantic Uncertainty | 2023 | [PDF](M7_2302.09664_semantic_uncertainty.pdf) | [arXiv](https://arxiv.org/abs/2302.09664) |
| M8 | Semantic Entropy Probes | 2024 | [PDF](M8_2406.15927_semantic_entropy_probes.pdf) | [arXiv](https://arxiv.org/abs/2406.15927) |
| M9 | Is MAP Decoding All You Need? | 2020 | [PDF](M9_2020.coling-main.398_minimum_bayes_risk.pdf) | [COLING](https://aclanthology.org/2020.coling-main.398/) |
| M10 | Structure-Conditional Minimum Bayes Risk Decoding | 2025 | [PDF](M10_2025.emnlp-main.1616_structure_conditional_mbr.pdf) | [EMNLP](https://aclanthology.org/2025.emnlp-main.1616/) |
| M11 | Regularized Best-of-N with Minimum Bayes Risk Objective | 2025 | [PDF](M11_2025.naacl-long.472_mbr_best_of_n.pdf) | [NAACL](https://aclanthology.org/2025.naacl-long.472/) |
| M12 | CRITIC: Tool-Interactive Critiquing | 2023 | [PDF](M12_2305.11738_critic.pdf) | [arXiv](https://arxiv.org/abs/2305.11738) |
| M13 | SCoRe: Training LMs to Self-Correct via RL | 2024 | [PDF](M13_2409.12917_score.pdf) | [arXiv](https://arxiv.org/abs/2409.12917) |
| M14 | Direct Preference Optimization | 2023 | [PDF](M14_2305.18290v3_dpo.pdf) | [arXiv](https://arxiv.org/abs/2305.18290) |
| M15 | Conformal Language Modeling | 2023 | [PDF](M15_2306.10193_conformal_language_modeling.pdf) | [arXiv](https://arxiv.org/abs/2306.10193) |
| M16 | Self-Consistency Improves Chain of Thought Reasoning | 2022 | [PDF](M16_2203.11171_self_consistency.pdf) | [arXiv](https://arxiv.org/abs/2203.11171) |
| M17 | Solve-Detect-Verify / FlexiVe | 2026 | [PDF](M17_2026.acl-long.2190_solve_detect_verify.pdf) | [ACL](https://aclanthology.org/2026.acl-long.2190/) |

## Мост к архитектуре Cosmos

Эти три работы не являются NLP-бенчмарками: они проверяют перенос принципов
alignment на генерацию изображений. Именно поэтому они нужны дополнительно
к LLM-обзорам.

| ID | Работа | Год | Локальный PDF | Первоисточник |
|---|---|---:|---|---|
| B1 | Diffusion Model Alignment Using DPO | 2023 | [PDF](B1_2311.12908_diffusion_dpo.pdf) | [arXiv](https://arxiv.org/abs/2311.12908) |
| B2 | Training Diffusion Models with RL / DDPO | 2023 | [PDF](B2_2305.13301_ddpo.pdf) | [arXiv](https://arxiv.org/abs/2305.13301) |
| B3 | Flow-GRPO | 2025 | [PDF](B3_2505.05470_flow_grpo.pdf) | [arXiv](https://arxiv.org/abs/2505.05470) |

## Проверки и исключения

- Все 26 файлов проверены как PDF и прочитаны `pypdf`; число страниц и
  контрольные суммы записаны в manifest. Извлечённые тексты лежат в `.text/`
  и игнорируются Git. У нескольких PDF есть предупреждения о повторных
  внутренних ключах `/Group`; чтению страниц они не помешали.
- Название S2 в HTML metadata отличается от заголовка PDF. В разборе
  используется заголовок PDF; исходные metadata сохранены без исправления.
- M5 раньше называлась *Inference Scaling fLaws*. Скачана v3 от 26.03.2026
  с названием *The Limits of Inference Scaling Through Resampling*.
- **SuperFlow, arXiv:2512.17951, исключена**: v3 от 23.07.2026 отозвана;
  указанная авторами причина: подача без согласия всех перечисленных авторов.
  Её численные claims не используются как доказательства. Сам по себе отзыв
  по этой причине не доказывает ошибочность алгоритма. [Уведомление](https://arxiv.org/abs/2512.17951).
- Полные тексты являются материалами авторов; наличие локального PDF не
  меняет исходную лицензию и не означает разрешение на его перепубликацию.

Для повторной загрузки недостающих файлов из корня проекта:

```bash
/home/alexander/venvs/cosmos_policy_libero/bin/python articles/llm_nlp_transfer_20260909/download.py
```

Скрипт повторно использует существующие PDF. Точные скачанные версии
идентифицируются SHA-256 и версиями в `source_audit.json`; URL без `vN`
при загрузке в будущем может вернуть обновлённую редакцию.

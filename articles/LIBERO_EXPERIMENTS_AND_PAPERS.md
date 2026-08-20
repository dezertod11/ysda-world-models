# LIBERO и LIBERO-PRO: эксперименты, статьи и протокол нашего исследования

Актуальность обзора: 20 августа 2026 года.

Этот файл отвечает на четыре практических вопроса:

1. Как именно ставились эксперименты в работах по uncertainty, world models и VLA.
2. Какие статьи действительно использовали стандартный LIBERO, LIBERO-PRO или LIBERO-Plus.
3. Как на их основе поставить честное сравнение обычного `max(value)` и uncertainty-aware planning в Cosmos Policy.
4. Какие новые направления следуют из работ Junwon Seo, StressDream, UNISafe, AnySafe, tau0-WM и QWM после наших собственных confirmatory результатов.

Числа ниже являются результатами авторов соответствующих статей, если явно не указано, что это наша гипотеза или предлагаемый протокол. Результаты разных работ нельзя напрямую сравнивать только по success rate: модели, данные, число rollout, наборы задач и критерии успеха различаются.

## 1. Uncertainty Quantification for Flow-Based Vision-Language-Action Models

**Статья:** R. Roemer et al., *Uncertainty Quantification for Flow-Based Vision-Language-Action Models*, arXiv:2606.18043, 2026.

- [Локальный PDF](2606.18043v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2606.18043)
- [Код авторов](https://github.com/learnsyslab/uq_vla)

### 1.1. Главная задача

Авторы изучают epistemic uncertainty flow-based VLA: насколько предсказание зависит от неизвестных параметров модели и недостаточного покрытия обучающими данными. Для этого они обучают небольшой ансамбль независимых flow-моделей и измеряют расхождение не только между конечными action chunks, но и между их velocity fields вдоль траектории flow matching.

Работа решает две задачи:

1. **SAVE active fine-tuning:** выбирать задачи и initial states, для которых полезнее всего запросить новую экспертную демонстрацию.
2. **Failure detection:** во время rollout сигнализировать о вероятном провале, когда uncertainty превышает откалиброванный порог.

Работа **не** решает задачу best-of-N planning: VFD не используется для ранжирования нескольких candidate actions по формуле `value - risk`.

### 1.2. Среда, модель и входы

Используется стандартный **LIBERO**, не LIBERO-PRO.

| Компонент | Настройка |
|---|---|
| Робот | Franka с parallel-yaw gripper |
| Policy | SmolVLA с flow-matching action expert |
| Изображения | Две RGB-камеры `256 x 256`: внешняя и wrist camera |
| Proprio | 8D: позиция end-effector 3D, orientation axis-angle 3D, два gripper joints |
| Action | 7D: delta position 3D, delta orientation 3D, gripper 1D |
| Action horizon | 50 действий |
| Replanning | После выполнения 25 действий |
| Flow integration | Euler, шаг ODE `0.1` |
| Ensemble | Две независимо обученные модели |
| VFD batch | Пять noise/action samples |

Начальная модель обучается 30 000 шагов, batch size 32, на:

- всех 10 задачах LIBERO-Spatial;
- всех 10 задачах LIBERO-Object;
- всех 10 задачах LIBERO-Goal;
- первых трех задачах целевого LIBERO-10, чтобы модель изначально обладала ненулевой компетентностью в long-horizon suite.

Целевой active-learning pool содержит все 10 задач LIBERO-10.

### 1.3. Формула Velocity Field Disagreement

Пусть:

- \(y\) - conditioning input: изображения, proprio и instruction;
- \(M\) - число независимо обученных ensemble members;
- \(x_0 \sim p_0\) - начальный Gaussian noise для action flow;
- \(s_\ell\) - промежуточный flow time;
- \(v_i(x_s,s;y)\) - velocity field модели \(i\);
- \(N_s\) - число точек интегрирования;
- \(\kappa_s=s/(1-s)\) - вес, повышающий важность поздних, менее зашумленных flow states.

Практическая оценка VFD имеет вид:

$$
U_{\mathrm{VFD}}(y)=
\frac{1}{M(M-1)N_s}
\mathbb{E}_{x_0\sim p_0}
\left[
\sum_{i\ne j}
\sum_{\ell=1}^{N_s}
\kappa_{s_\ell}
\left\|
v_i(x^{(i)}_{s_\ell},s_\ell;y)
-
v_j(x^{(i)}_{s_\ell},s_\ell;y)
\right\|_2^2
\right].
$$

Интерпретация:

- один и тот же conditioning подается независимым моделям;
- disagreement измеряется на нескольких этапах генерации action, а не только на финальном chunk;
- поздние этапы flow получают больший вес;
- большое расхождение означает, что разные правдоподобные параметры модели задают разные action distributions.

Это оценка **epistemic uncertainty** только при наличии независимо обученных ensemble members. Разброс нескольких stochastic samples одной и той же Cosmos Policy является полезной generative/predictive uncertainty, но его нельзя без оговорок называть VFD или ensemble epistemic uncertainty.

### 1.4. Эксперимент A: calibration uncertainty

Для каждой задачи авторы:

1. Вычисляют uncertainty для набора initial observations.
2. Выполняют rollout из различных initial states.
3. Усредняют uncertainty на уровне задачи.
4. Сравнивают ее с task success rate.

Основная метрика - отрицательная Spearman correlation: хорошо, если более высокая uncertainty монотонно соответствует более низкому success rate. Дополнительно считается Pearson correlation.

Сравниваются:

- Action-L2;
- ACE;
- DECU;
- Generative Uncertainty;
- entropy и perplexity VLM prefix;
- VFD.

По данным статьи VFD получил примерно `0.71` для отрицательной Spearman и Pearson correlation и оказался лучше ближайшего ensemble baseline, Generative Uncertainty. Двух ensemble members оказалось достаточно: дальнейшее увеличение ансамбля дало небольшой прирост относительно вычислительной цены.

Дополнительно авторы создали пять уровней перефразирования каждого instruction. VFD сохранял связь с падением качества при semantic language shifts.

**Что важно для нас:** task-level correlation не доказывает, что metric предсказывает natural fail при одинаковых `task/init_state`. Для нашей постановки нужен отдельный paired rollout protocol.

### 1.5. Эксперимент B: SAVE active fine-tuning

Цикл active fine-tuning:

1. Для каждого task и candidate initial state вычисляется VFD.
2. Средняя task uncertainty преобразуется в categorical distribution:

$$
p(k)=\frac{U_k^\tau}{\sum_j U_j^\tau},
$$

где \(\tau\) управляет компромиссом exploration/exploitation.

3. Семплируется задача \(k\).
4. Внутри нее выбирается самый uncertain initial state.
5. Запрашивается expert demonstration.
6. Ensemble дообучается на смеси новых данных и replay data.

Настройки:

- 15 active-learning rounds;
- 5 expert demonstrations на round;
- всего 75 новых демонстраций;
- 4 000 optimization steps на round;
- batch size 32;
- replay ratio 0.5;
- три random seeds.

Сравниваются random acquisition, visual-diversity acquisition и SAVE с разными uncertainty estimators.

Основной результат авторов:

- финальный success rate SAVE+VFD около `67.1 +/- 3.2%`;
- при одинаковом data budget он выше baselines примерно на 3-12 процентных пунктов;
- VFD требует как минимум на 22% меньше demonstrations, чем ближайший uncertainty baseline, чтобы достичь сопоставимого качества;
- основной выигрыш дает выбор **задачи**, а дополнительный выбор initial state внутри задачи дает меньший эффект.

### 1.6. Эксперимент C: online failure detection

Для финальной policy:

1. VFD считается на каждом action-generation query.
2. Для каждой задачи порог строится по 10 успешным calibration rollouts с помощью one-sided conformal prediction.
3. Эпизод помечается как потенциальный fail в первый момент, когда \(U_{\mathrm{VFD}}\) превышает порог.

Авторы сообщают:

- accuracy около `67%`;
- TPR около `79%`, то есть найдено большинство fail;
- timestep-weighted accuracy около `0.54`;
- normalized detection time около `0.40`.

Это полезный, но еще не достаточный результат для автономного planning: высокая TPR может сопровождаться false positives, а uncertainty threshold сам по себе не говорит, какой alternative action надо выбрать.

### 1.7. Вычислительная цена

Один полный active-learning experiment занимает примерно 12.5 часа на двух RTX 4090. Полный sweep авторов, 25 конфигураций по три seeds, оценивается примерно в 1 880 GPU-hours. Для нашего проекта разумнее сначала воспроизвести только inference-side metrics и planning comparison, не весь active fine-tuning.

### 1.8. Что переносим в Cosmos Policy

Переносим:

- сравнение uncertainty с вероятностью успеха;
- held-out calibration и test splits;
- online metric на каждом query;
- threshold, выбранный только на calibration data;
- локальные, а не только episode-mean сигналы;
- отдельное измерение detection quality и downstream planner success rate.

Не переносим напрямую:

- название VFD для stochastic copies одной модели;
- task-level calibration как доказательство paired fail prediction;
- результат SAVE как доказательство эффективности risk-aware action ranking;
- future observation error как online signal: он известен только после выполнения chunk.

## 2. Какие статьи использовали LIBERO

### 2.1. Краткая карта

| Работа | Стандартный LIBERO | LIBERO-PRO | LIBERO-Plus / производная | Основная роль benchmark |
|---|---:|---:|---:|---|
| UQ for Flow-Based VLA, 2606.18043 | Да, все четыре suites в train/target setup | Нет | Нет | UQ, active fine-tuning, failure detection |
| Cosmos Policy, 2601.16163 | Да, четыре suites | Нет | Нет | Direct policy evaluation |
| mimic-video, 2512.15692 | Да, Spatial/Object/Goal | Нет | Нет | Generalization и sample efficiency |
| LIBERO-Safety, 2606.23686 | Не как основной benchmark | Нет | Да, построен на LIBERO-Plus/BDDL | Отдельный safety benchmark |
| pi0.5, 2504.16054 | Нет | Нет | Нет | Real-world open-world generalization |
| pi*0.6/RECAP, 2511.14759 | Нет | Нет | Нет | Real-world RL и on-policy corrections |
| DreamDojo, 2602.06949 | Нет | Нет | Нет | Video world model и real-robot policy |
| Reconstruction or Semantics?, 2605.06388 | Нет | Нет | Нет | Latent world models на Bridge V2/SOAR |
| LIBERO-PRO, 2510.03827 | Да, как база | Да | Нет | Новый OOD robustness benchmark |
| LIBERO-Plus, 2510.13626 | Да, как база | Нет | Да | Factorized perturbation benchmark |
| Act, Think or Abstain, 2603.05147 | Да | Да | Нет | OOD routing |
| Shifting Uncertainty, 2603.18342 | Да, четыре suites | Нет | Нет | Rollout failure prediction |
| SUREFlow, 2607.10504 | Да, четыре suites | Да | Нет | Uncertainty-aware flow refinement |
| UNISafe, 2505.00779 | Нет | Нет | Нет | Calibrated OOD detection и latent safety filtering |
| AnySafe, 2509.19555 | Нет | Нет | Нет | Runtime-parameterized safety constraints |
| StressDream, 2606.00267 | Нет | Нет | Нет | Targeted pessimistic video-WM imaginations |
| tau0-WM, 2606.01027 | Нет | Нет | Нет | Candidate consistency, simulated progress и action rectification |
| QWM, 2608.17163 | Да, пять задач | Нет | Нет | Short-depth WM tree search поверх Q-learning |

**Главный факт:** среди локальных PDF только QWM из новых работ добавляет эксперименты на standard LIBERO; ни одна из пяти новых работ не использует LIBERO-PRO. Для прямого сравнения на LIBERO-PRO по-прежнему нужны работы 2510.03827, 2603.05147 и 2607.10504, а перенос StressDream/UNISafe/AnySafe на PRO является нашей новой экспериментальной постановкой.

## 3. Разбор локальных статей

### 3.1. Cosmos Policy: Fine-Tuning Video Models for Visuomotor Control and Planning

**Статья:** arXiv:2601.16163.

- [Локальный PDF](2601.16163v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2601.16163)
- [Код](https://github.com/NVlabs/cosmos-policy)

**LIBERO protocol**

- Все четыре standard suites: Spatial, Object, Goal, Long.
- В каждом suite 10 задач, по 50 demonstrations на задачу.
- Для direct policy training удаляются unsuccessful demonstrations.
- Для обучения world/value components сохраняются полные trajectories, включая неуспешные фрагменты.
- Evaluation: 50 rollout на каждую задачу, три seeds, всего 6 000 rollout.
- Action chunk в LIBERO: 16 шагов, выполняется весь chunk.
- Пять denoising steps.

Reported success rate:

| Suite | Success rate |
|---|---:|
| Spatial | 98.1% |
| Object | 100.0% |
| Goal | 98.2% |
| Long | 97.6% |
| Average | 98.5% |

В direct-policy LIBERO evaluation модель совместно предсказывает action, future state и value, но выполняется action, а future/value outputs не используются для выбора.

**Planning protocol**

Planning проверяется **не на LIBERO**, а на двух сложных ALOHA tasks, потому что standard LIBERO почти насыщен:

- `candies in bowl`;
- `candy in ziploc bag`.

Для candidate trajectory используется авторегрессионная цепочка:

$$
a_k \longrightarrow \hat{s}_{k} \longrightarrow \hat{v}_{k}.
$$

Сначала генерируется candidate action, затем conditioned на него future state, затем conditioned на action и future state value. Для каждого action используются несколько future-state и value samples. После этого выбирается candidate с максимальным predicted value.

Описанные настройки planning:

- depth-1 best-of-\(N\);
- \(N=8\) candidate action chunks;
- 10 denoising steps для action;
- 5 шагов для future state;
- 5 шагов для value;
- три future-state predictions на каждый action candidate;
- пять value predictions на каждый future-state prediction, то есть 15 value estimates на action candidate;
- около 5 секунд на один action chunk;
- 505 существующих rollout и 143 дополнительных, всего 648 rollout для planning fine-tuning.

Model-based planning улучшил среднюю оценку на двух ALOHA tasks примерно на 12.5 пункта относительно base policy.

**Вывод для нас**

Это основная архитектурная база нашего исследования. Корректный baseline:

$$
k^*_{\mathrm{value}}=\arg\max_k \mathbb{E}[\hat v_k].
$$

Наше расширение должно менять только candidate score и сохранять одинаковые state, candidate pool и random seeds:

$$
k^*_{\mathrm{risk}}=
\arg\max_k
\left(
\mathbb{E}[\hat v_k]-\lambda U_k
\right).
$$

Нельзя утверждать, что статья уже показала uncertainty-aware planning на LIBERO: такого эксперимента в ней нет.

### 3.2. mimic-video: Video-Action Models for Generalizable Robot Control Beyond VLAs

**Статья:** arXiv:2512.15692.

- [Локальный PDF](2512.15692v2.pdf)
- [arXiv HTML](https://arxiv.org/html/2512.15692)

Используется standard LIBERO, но только:

- LIBERO-Spatial;
- LIBERO-Object;
- LIBERO-Goal.

Для каждого suite: 10 tasks, 50 demonstrations на task. LIBERO-Long и LIBERO-PRO не используются.

Модель сочетает Cosmos-Predict2 video backbone и flow-based action decoder. Action decoder получает intermediate partially-denoised video latents, поэтому policy не обязана сначала реконструировать визуально идеальное future video.

Reported results:

| Suite | Success rate |
|---|---:|
| Spatial | 94.2% |
| Object | 96.8% |
| Goal | 90.6% |
| Average | 93.9% |

Авторы также показывают высокую sample efficiency: уже 10% training data дает близкое к максимуму качество, а один demonstration на task дает около 77% average success.

**Вывод для нас**

Pixel reconstruction error и task-relevant prediction quality не эквивалентны. Для uncertainty world model надо сравнивать:

- image MSE/SSIM/LPIPS;
- semantic latent error;
- action-recovery error;
- proprio/object-state error;
- downstream candidate ranking quality.

Возможно, disagreement промежуточных video latents будет полезнее, чем ошибка финального RGB.

### 3.3. LIBERO-Safety

**Статья:** arXiv:2606.23686.

- [Локальный PDF](2606.23686v2.pdf)
- [arXiv HTML](https://arxiv.org/html/2606.23686)

Это не evaluation на LIBERO-PRO. Авторы создают отдельный safety benchmark на основе инфраструктуры LIBERO-Plus и BDDL:

- 7 603 scenes;
- 953 objects;
- 462 hand-object interaction pairs;
- 19 664 safe demonstrations;
- пять suites и три уровня сложности;
- всего 75 tasks.

Пять направлений:

- AAG: Affordance-Aware Grasping;
- HRI: human-robot interaction;
- TSA: Tabletop Spatial Avoidance;
- FSHOA: Free-Space Hand-Object Avoidance;
- SSR: Semantic Safety Reasoning.

Physical evaluation использует одинаковые prerecorded initial configurations, 10 trials на task и три seeds. Safety violation сразу завершает rollout. Считаются success rate, collision rate, execution time и dimensionless jerk. Semantic track оценивает refusal behavior.

**Вывод для нас**

Binary final success недостаточен. Для natural fail dataset надо сохранять:

- `drop`;
- `missed_grasp`;
- `wrong_object`;
- `collision`;
- `unsafe_contact`;
- `timeout`;
- `task_completed_but_simulator_false`;
- timestep первого необратимого события.

Risk-aware planner следует оценивать не только по success rate, но и по severity-weighted failure cost.

### 3.4. pi0.5: a Vision-Language-Action Model with Open-World Generalization

**Статья:** arXiv:2504.16054.

- [Локальный PDF](2504.16054v1.pdf)
- [arXiv](https://arxiv.org/abs/2504.16054)

LIBERO и LIBERO-PRO не используются. Эксперименты проводятся на реальных роботах в знакомых и новых домах/сценах: уборка посуды, укладка предметов в drawer, laundry, making a bed.

Полезная идея для нашего protocol: OOD должен быть контролируемым. Отдельно изменяются environment, object и task, а результат оценивается фиксированной rubric частичного прогресса, а не только одной бинарной меткой.

### 3.5. pi*0.6 / RECAP

**Статья:** arXiv:2511.14759.

- [Локальный PDF](2511.14759v2.pdf)
- [arXiv](https://arxiv.org/abs/2511.14759)

LIBERO и LIBERO-PRO не используются. Работа посвящена real-world on-policy improvement на laundry, espresso и box-manipulation tasks. Собираются autonomous rollouts, expert interventions и corrections, после чего policy и value model обновляются на данных, отражающих реальные ошибки текущей policy.

**Вывод для нас**

Данные natural failure полезны не только для post-hoc classifier. Их можно использовать для:

- калибровки value;
- обучения failure/value head;
- preference pairs между удачными и неудачными candidates;
- correction policy после high-risk query.

### 3.6. DreamDojo

**Статья:** arXiv:2602.06949.

- [Локальный PDF](2602.06949v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2602.06949)

LIBERO и LIBERO-PRO не используются. World model обучается на крупном наборе human и robot video. Evaluation включает шесть собственных video-generation sets, autoregressive generation и downstream real-robot fruit-packing policy.

Сравниваются PSNR, SSIM, LPIPS и human preference, а затем отдельно downstream control.

**Вывод для нас**

Хорошее future video по perceptual metric не гарантирует правильную физику контакта. В наших экспериментах RGB metrics должны быть диагностическими, а основными критериями остаются:

- grasp/contact event;
- object pose;
- task success;
- candidate ranking;
- ошибка, накопленная на нескольких chunks.

### 3.7. Reconstruction or Semantics? What Matters in Latent World Models for Control

**Статья:** arXiv:2605.06388.

- [Локальный PDF](2605.06388v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2605.06388)

LIBERO и LIBERO-PRO не используются. Авторы сравнивают reconstruction-oriented и semantic visual latents на Bridge V2 и SOAR, удерживая одинаковыми world-model backbone и training data.

Оценки включают:

- pixel и latent prediction metrics;
- inverse-dynamics/action recovery;
- task-success probes;
- CEM planning;
- VLA-in-the-loop control;
- OOD distractor и instruction tests.

Основной вывод: visual fidelity и control utility могут расходиться. Semantic representations чаще лучше сохраняют task и action information и устойчивее к distractors, тогда как reconstruction latents лучше выглядят визуально.

**Вывод для нас**

Вместо единственной `future_image_mse` нужен набор:

$$
E_{\mathrm{future}}=
\left(
E_{\mathrm{pixel}},
E_{\mathrm{perceptual}},
E_{\mathrm{semantic}},
E_{\mathrm{proprio}},
E_{\mathrm{object}},
E_{\mathrm{action}}
\right).
$$

Надо проверять, какая компонента действительно улучшает ranking actions, а не выбирать метрику по красоте reconstruction.

### 3.8. UNISafe: uncertainty-aware latent safety filter

**Статья:** J. Seo, K. Nakamura, A. Bajcsy, *Uncertainty-aware Latent Safety Filters for Avoiding Out-of-Distribution Failures*, CoRL 2025, arXiv:2505.00779.

- [Локальный PDF](2505.00779v2.pdf)
- [arXiv HTML](https://arxiv.org/html/2505.00779)
- [Проект](https://cmu-intentlab.github.io/UNISafe/)

LIBERO не используется. Эксперименты проведены на image-based Dubins car, block plucking в Isaac Lab с Franka и физическом Jenga с Franka.

**Метод.** Базовый latent safety filter обучает safety value в imagination world model:

$$
V^{\mathrm{safe}}(z_t)=
(1-\gamma)\ell_z(z_t)+
\gamma\min\left\{
\ell_z(z_t),
\max_a V^{\mathrm{safe}}(\hat z_{t+1})
\right\}.
$$

Здесь \(\ell_z(z)<0\) означает известный failure. UNISafe добавляет вторую причину запрета: world-model transition сам находится вне покрытия данных. Для этого состояние расширяется uncertainty:

$$
\tilde z=(z,u),
\qquad
\ell_{\tilde z}(\tilde z)=
\min\{\ell_z(z),\kappa(\epsilon-u)\}.
$$

Важно, что uncertainty зависит от перехода \((z,a)\), а не только от сгенерированного \(z'\). OOD-input может быть спроецирован генеративной моделью обратно в правдоподобный latent, поэтому OOD detector только по output state способен остаться overconfident.

Epistemic uncertainty оценивает отдельный лёгкий ансамбль Gaussian next-latent predictors:

$$
\hat f_k(z_{t+1}\mid z_t,a_t)
=\mathcal N(\mu_k(z_t,a_t),\Sigma_k(z_t,a_t)).
$$

Диагональная \(\Sigma_k\) описывает aleatoric uncertainty внутри member, а расхождение между members выделяется Jensen-Renyi divergence:

$$
U_{\mathrm{JRD}}(z,a)=
H_2\left(\frac{1}{K}\sum_k \hat f_k\right)
-\frac{1}{K}\sum_k H_2(\hat f_k).
$$

Порог \(\hat\epsilon\) выбирается class-conditioned conformal prediction только по held-out ID trajectories. Авторы калибруют сначала high quantile uncertainty внутри каждой траектории, затем quantile по траекториям. Это сохраняет trajectory-level exchangeability и контролирует долю ID trajectories, ошибочно объявленных OOD.

**Эксперименты и результаты.** В block plucking использованы 3000 train trajectories и 1000 evaluation initial states. Для обычной Dreamer policy:

| Метод | Safe success | Failure | Incompletion | Filtered |
|---|---:|---:|---:|---:|
| без filter | 0.58 | 0.41 | 0.01 | 0.0% |
| LatentSafe | 0.68 | 0.30 | 0.01 | 7.2% |
| UNISafe, JRD | **0.72** | **0.20** | 0.08 | 37.7% |

Total uncertainty и max aleatoric uncertainty уменьшали failures, но чаще блокировали допустимое поведение. JRD дал лучший компромисс между safety и conservativeness. В Jenga использованы 720 train trajectories, в том числе 90 failures; на replay 50 failure trajectories UNISafe вмешивался раньше и резко уменьшал open-loop failure rate. Отдельная ablation показала, что soft reward вида

$$
r(z,a)=\bar r(z,a)-\lambda U_{\mathrm{JRD}}(z,a)
$$

сам по себе не обеспечил safety: uncertainty-aware hard filter оказался существенно надёжнее.

**Вывод для нашего проекта.** Это прямое предупреждение против попытки решить LIBERO-Safety только формулой `value - lambda * uncertainty`. Для task success soft ranking полезен; для constraint violation нужен отдельный calibrated feasible set и fallback. Практический перенос без обучения нового Cosmos:

1. Заморозить Cosmos encoder и собрать реальные tuples \((z_t,a_t,z_{t+1})\) из наших traces.
2. Обучить 5 небольших probabilistic transition heads и сравнить JRD с текущим internal-copy std.
3. Калибровать OOD threshold по целым ID episodes, а не по перемешанным query rows.
4. В LIBERO-Safety разрешать candidate только при \(U_{\mathrm{JRD}}\le\hat\epsilon\) и отсутствии предсказанного constraint event.

Это расширяет наши H8/H14. Новыми для прежнего плана являются явное разделение aleatoric/epistemic uncertainty, lightweight transition ensemble и trajectory-level conformal calibration.

### 3.9. AnySafe: safety constraint задаётся во время запуска

**Статья:** S. Agrawal, J. Seo et al., *AnySafe: Adapting Latent Safety Filters at Runtime via Safety Constraint Parameterization in the Latent Space*, ICRA 2026, arXiv:2509.19555.

- [Локальный PDF](2509.19555v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2509.19555)
- [Проект](https://any-safe.github.io/)

LIBERO не используется. Эксперименты: simulated image-based Dubins car и физическое sweeping objects с Franka.

**Метод.** Обычный safety filter знает один фиксированный failure classifier. AnySafe получает во время deployment изображение нежелательного состояния \(o_c\), кодирует его в \(z_c\) и строит constraint-conditioned value \(V^{\mathrm{safe}}(z;z_c)\). Поскольку raw world-model latent не обязан отражать именно safety similarity, обучается failure-relevant projector:

$$
\tilde z=\tilde{\mathcal E}(z),
\qquad
\tilde\ell_z(z;z_c)=-\operatorname{cos}(\tilde z,\tilde z_c),
$$

$$
\mathcal F_{z_c}^{\delta}
=\{z:\tilde\ell_z(z;z_c)\le\delta\}.
$$

Порог \(\delta\) калибруется conformal prediction на похожих/непохожих парах. Один и тот же safety filter затем меняет conservativeness post hoc без retraining. Во время обучения constraint \(z_c\) случайно выбирается из world-model dataset, поэтому модель видит широкое семейство потенциальных запретов.

**Результаты.** В Dubins setup AnySafe получил balanced accuracy 0.942 и safe rate 0.924, сопоставимо со специализированным fixed filter (0.965 и 0.908). Вариант без failure projector получил только 0.755 balanced accuracy: raw latent similarity недостаточна. На физическом sweeping world model обучался на 1300 trajectories, projector на 300 labeled trajectories, calibration использовала 4000 images. В 30 replayed action sequences AnySafe адаптировался к новым failure regions; авторы сообщают менее 2% состояний, нарушающих runtime constraint.

**Вывод для нашего проекта.** AnySafe решает не вопрос «насколько Cosmos не уверен», а вопрос «что именно считать недопустимым сейчас». Для LIBERO-Safety это даёт сильную архитектурную идею:

- отдельный constraint representation для `do not touch`, `do not knock over`, `keep object out of region`;
- task value и constraint value не смешиваются в один scalar;
- один safety head можно переиспользовать для разных BDDL constraints;
- threshold определяет conservativeness и выбирается на calibration split.

Это полезный второй этап после простого event classifier. Полный HJ filter потребует отдельного latent dynamics solver; ближайший реалистичный вариант для нас - constraint-conditioned binary/risk head плюс reject/requery/recovery.

### 3.10. StressDream: целевой поиск редких правдоподобных failures

**Статья:** J. Seo et al., *StressDream: Steering Video World Models for Robust Policy Evaluation and Improvement*, arXiv:2606.00267, 2026.

- [Локальный PDF](2606.00267v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2606.00267)
- [Проект](https://junwon.me/StressDream/)
- [Код](https://github.com/CMU-IntentLab/StressDream)

LIBERO не используется. Авторы применяют Vista к autonomous driving и Ctrl-World, обученный в DROID setup, к шести contact-rich real-robot manipulation tasks. Для manipulation собирается примерно 150 trajectories на задачу с successes и failures; evaluation содержит 100 failure trajectories.

**Главная идея.** Наши stochastic samples являются zeroth-order Monte Carlo: редкий failure можно не увидеть даже при большом \(N\). StressDream фиксирует observation history и candidate action \(a\), но оптимизирует initial diffusion noise \(\epsilon\), чтобы найти правдоподобный high-impact future:

$$
a^*=\arg\min_a\max_{\epsilon\in\mathcal T}
C_{\mathrm{fail}}\left(f_\theta(\epsilon,o_{\mathrm{hist}},a)\right),
$$

где \(\mathcal T\) - typical set Gaussian prior. Semantic objective берётся из differentiable yes/no logit VLM:

$$
C_{\mathrm{sem}}(o,l)=
\log p_{\mathrm{VLM}}(\text{yes}\mid o,l)
-\log p_{\mathrm{VLM}}(\text{no}\mid o,l).
$$

Чтобы gradient ascent не породил физически бессмысленный ролик, noise удерживается в Gaussian typical set:

$$
C_{\mathrm{pla}}(\epsilon)=
\lambda_1 C_{\mathrm{norm}}
+\lambda_2 C_{\mathrm{iso}}
+\lambda_3 C_{\mathrm{spec}},
$$

$$
C_{\mathrm{norm}}=-(\|\epsilon\|_2-\sqrt D)^2,
\quad
C_{\mathrm{iso}}=-\frac1k\|\hat\Sigma-I\|_F^2,
\quad
C_{\mathrm{spec}}=-\frac1B\sum_b(\hat p_b-\bar p)^2.
$$

Полный backprop через все denoising steps заменяется score-distillation approximation:

$$
\nabla_\epsilon C_{\mathrm{sem}}(o)
\approx \beta\nabla_o C_{\mathrm{sem}}(o).
$$

**Результаты.** На driving и manipulation recall high-impact failures вырос с 54% до 94%. Robust fine-tuning pi0.5-droid, где steered-failure trajectories получали weight 0.1 вместо 1.0, повысил success с 39% до 71% по 20 rollout на задачу. На rare driving events 20 gradient steps превзошли best-of-40 random samples. Без typical-set regularization steering создавал implausible failures и ухудшал true-negative rate/video quality.

**Вывод для нашего проекта.** Это наиболее новое направление относительно текущего плана. Наши четыре stochastic candidates и variance обнаруживают только легко семплируемую часть outcome distribution. Для каждого action candidate надо отдельно оценивать targeted pessimistic risk:

$$
R_i^{\mathrm{stress}}=
\max_{\epsilon\in\mathcal T}
C_{\mathrm{fail}}\left(f_\theta(\epsilon\mid s,a_i)\right),
$$

$$
\operatorname{score}_i=
\widehat V_i
-\lambda U_i
-\mu R_i^{\mathrm{stress}}.
$$

В Cosmos сначала требуется проверить action-conditioned causal path `fixed action -> future image/proprio -> value`: при `parallel` generation будущий rollout и action могут быть совместно сгенерированы, но это ещё не строгая оценка последствия фиксированного candidate. Первый эксперимент должен сравнить random future samples и optimized-noise futures при одинаковом action, compute budget и held-out verifier. StressDream дорог для online control, поэтому разумный режим - запускать его только после disagreement/OOD alarm или offline для hard-negative mining.

### 3.11. tau0-WM: consistency, progress и action rectification

**Статья:** P. Zhou et al., *tau0-WM: A Unified Video-Action World Model for Robotic Manipulation*, arXiv:2606.01027, 2026.

- [Локальный PDF](2606.01027v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2606.01027)
- [Проект](https://finch.agibot.com/research/tau0-wm)

LIBERO не используется. Работа оценивается на четырёх long-horizon real-robot tasks (`Toolbox`, `School Bag`, `Faucet`, `Badminton`) и отдельных single-attempt ablations `Tissue -> Box`, `Pen -> Box`.

**Архитектура.** Video Action Model совместно предсказывает future visual latents и action chunk:

$$
F_\theta(o_t,p,s_t)
\rightarrow
(\hat z_{t+1:t+H_v},\hat a_{t:t+H_a-1}).
$$

Отдельный Action-Conditioned Video Simulator получает уже фиксированный candidate action и выдаёт future rollout и dense task progress:

$$
G_\phi(o_{t-M:t},p,\bar a_i)
\rightarrow(\hat z_i,\hat r_i).
$$

Модель обучена на 27.3k hours heterogeneous data: 17.8k robot teleoperation, 6.5k UMI и 3.0k egocentric video. Failure и recovery trajectories специально используются для progress head.

**Test-time computation.** Сначала для каждого candidate вычисляется Re-denoising Consistency Score. Action повторно зашумляется на \(K\) случайных flow times и denoiser должен восстановить его; score является отрицательной средней re-denoising error:

$$
S_{\mathrm{RCS}}^{(i)}=-E_{\mathrm{redenoise}}^{(i)}.
$$

Если лучший \(S_{\mathrm{RCS}}\ge\gamma\), candidate исполняется сразу. Иначе ACVS оценивает candidates, выбирает rollout с максимальным progress

$$
J^{(i)}=\max_{0\le q<H_a}\hat r_{t+q}^{(i)},
$$

а затем не исполняет исходный action: выбранный future latent подаётся во второй VAM query, который генерирует исправленный chunk. Это proposal-evaluation-revision, а не только ranking.

**Результаты.** В single-attempt ablation по 20 повторов: без test-time computation средний success 0.43; RCS дал 0.50; RCS+rectification - 0.60. CFG и Action Coherence Guidance дали 0.20 и 0.38. Heterogeneous pretraining повысил zero-shot `Pen-to-holder` с 0.14 до 0.55 и cluttered SFT с 0.70 до 0.83 в среднем.

**Вывод для нашего проекта.** RCS - дешёвый новый candidate-level signal, которого не было в нашем плане. Он проверяет support action под conditional policy, а не disagreement между четырьмя samples. Его следует сравнить с `value`, internal action uncertainty и их комбинацией на уже сохранённых candidate pools. Второе новое направление - не просто abstain, а rectification: на alarm выбрать желаемый predicted future и перегенерировать action, conditioned на этот future. Наш подтверждённый `requery_l1_h8` уже показывает пользу дополнительного feedback; tau0-WM подсказывает следующий шаг, где дополнительный query получает не только реальное observation, но и явную target-future condition.

### 3.12. QWM: grounded Q-function и короткий world-model tree search

**Статья:** P. Dong et al., *Q-Learning With World Models*, arXiv:2608.17163, 2026.

- [Локальный PDF](2608.17163v1.pdf)
- [arXiv HTML](https://arxiv.org/html/2608.17163)

Это единственная из пяти новых статей со standard LIBERO. Pixel-based evaluation использует пять задач LIBERO (`Task 60`, `79`, `29`, `28`, `2`) с agent-view и wrist RGB. Дополнительно state-based experiments идут на Robomimic `Lift`, `Can`, `Square`, `Tool Hang`. LIBERO-PRO не используется.

**Главное отличие от обычного model-based RL.** Policy и Q-function обучаются только на реальных transitions. World model не создаёт synthetic training targets, а используется для short-depth search во время online data collection и evaluation. Это ограничивает compounding model bias.

В каждом state семплируются \(N\) actions, для каждого action - \(K\) future states, дерево раскрывается на depth \(D\). Два value estimators объединяются:

$$
V_Q(d\mid s)=\operatorname{agg}_{n}Q_\phi(s,a_n),
$$

$$
V_r(d\mid s)=\operatorname{agg}_{n}\operatorname{agg}_{k}
\left[r_\psi(s,a_n)+\lambda V(d+1\mid s'_{n,k})\right],
$$

$$
V(d\mid s)=\frac12(V_Q+V_r).
$$

Root candidate оценивается как

$$
Q_{\mathrm{ts}}(s_0,a_i)=\frac12\left[
Q_\phi(s_0,a_i)+r_\psi(s_0,a_i)
+\lambda\operatorname{agg}_k V(1\mid s'_{i,k})
\right].
$$

Чтобы дерево не росло экспоненциально, Q-function оставляет top-\(J\) partial paths. Для sparse reward практическая реализация может обходиться без learned reward model и опираться на Q intermediate/leaf nodes.

**Эксперименты и выводы авторов.** QWM улучшил EXPO и RLPD на Robomimic, а на pixel LIBERO дал явный выигрыш на tasks 60 и 79 и быстрее обучился на task 28. Для pixel setting из-за compute world model использовался только при online data collection, не при evaluation. Ablations показывают лучший trade-off у умеренной глубины: depth 2 обычно лучше depth 1, но большая глубина усиливает model error; наиболее эффективным был небольшой future discount около \(\lambda=0.2\). Слишком большое \(N\) тоже может ухудшать результат, усиливая extreme-value bias ошибочного world model.

**Вывод для нашего проекта.** Наш текущий planner - depth-1 best-of-four с self-generated Cosmos value. QWM предлагает два существенных улучшения:

1. Grounded critic \(Q_\phi\), обученный только по реальным LIBERO transitions, чтобы не доверять полностью self-consistency world model.
2. Неглубокий tree search с несколькими futures на action и robust aggregation.

Для первого переноса не нужен online RL: можно обучить offline success/progress Q-head на наших реальных trajectories и использовать его только как verifier. Затем сравнить `max Cosmos value`, `max grounded Q`, `Q + depth-1 future`, `QWM depth-2`. В stochastic ветвях стандартный `mean` следует дополнить `LCB/CVaR`, потому что наша задача именно risk-aware planning.

## 4. Внешние работы с LIBERO-PRO и близкими постановками

### 4.1. LIBERO-PRO

**Статья:** X. Zhou et al., *LIBERO-PRO: Towards Robust and Fair Evaluation of Vision-Language-Action Models Beyond Memorization*, arXiv:2510.03827.

- [arXiv HTML](https://arxiv.org/html/2510.03827)
- [Код](https://github.com/Zxy-MLlab/LIBERO-PRO)

LIBERO-PRO является plug-in extension стандартного LIBERO и тестирует перенос за пределы memorized benchmark configurations.

В коде и таблицах выделены пять perturbation families:

- `Obj`: object/appearance attributes;
- `Pos`: object initial position или spatial swap;
- `Sem`: semantic/instruction shift;
- `Task`: измененная task composition или goal;
- `Env`: environment/background shift.

В тексте статьи иногда говорится о четырех концептуальных dimensions, поскольку object/task changes объединяются на более высоком уровне. Для наших логов лучше использовать пять имен из evaluation tables.

Оцениваются OpenVLA, pi0 и pi0.5, обычно по 50 episodes на task. Ключевой результат: модели с success rate выше 90% на original LIBERO могут падать почти до нуля при positional и task shifts. Это делает LIBERO-PRO подходящей средой для поиска boundary cases.

**Ограничение**

Некоторые PRO configurations слишком сложны и дают почти 100% fail. На них невозможно доказать преимущество ranking strategy: у planner нет успешного candidate. Для нашего исследования нужны конфигурации с baseline success примерно 20-80%.

### 4.2. LIBERO-Plus

**Статья:** S. Fu et al., *LIBERO-Plus: In-depth Robustness Analysis of Vision-Language-Action Models*, arXiv:2510.13626.

- [arXiv HTML](https://arxiv.org/html/2510.13626)
- [Код](https://github.com/sylvestf/LIBERO-plus)

LIBERO-Plus не является LIBERO-PRO. Он строит более детальный factorized robustness benchmark с семью perturbation factors:

- object layout;
- camera;
- robot initial state;
- language;
- lighting;
- background;
- sensor noise.

Benchmark содержит 10 030 perturbed tasks поверх четырех standard suites и 20 000 generalized training trajectories. Авторы сравнивают 10 моделей, формируют уровни сложности и проводят массовые pairwise perturbation experiments.

Ключевые наблюдения:

- camera и robot-initial-state shifts часто наиболее разрушительны;
- совместное действие двух perturbations не равно сумме отдельных эффектов;
- кажущаяся language robustness иногда означает, что policy фактически игнорирует instruction;
- generalized fine-tuning значительно восстанавливает robustness.

**Вывод для нас**

LIBERO-Plus полезнее для причинного ablation отдельных факторов. LIBERO-PRO полезнее как готовый challenging OOD test. Их можно использовать последовательно:

1. PRO для поиска natural mixed success/fail.
2. Plus для выяснения, какой именно factor вызывает рост uncertainty и failure.

### 4.3. Act, Think or Abstain: Complexity-Aware Adaptive Inference for Vision-Language-Action Models

**Статья:** arXiv:2603.05147.

- [arXiv HTML](https://arxiv.org/html/2603.05147)

Работа использует и standard LIBERO, и LIBERO-PRO. Поверх SmolVLA строится router:

- `Act` для in-distribution observations;
- `Think` для partially OOD situations;
- `Abstain` для ситуаций, где автономное действие считается небезопасным.

Router использует visual embeddings и сочетание GMM, kNN и MLP. Авторы сообщают macro-F1 около 84.3% для vision-based routing; text-only routing существенно хуже. В rollout experiments routing улучшает success rate на отдельных standard suites.

**Критическое ограничение**

Это в значительной степени distribution/task routing: классы связаны с принадлежностью к standard LIBERO, LIBERO-PRO shifts и заранее известным difficult/failing cases. Работа не доказывает предсказание natural fail против success для одинаковых `task/init_state`.

**Что переносим**

Visual OOD score можно добавить как отдельную компоненту риска:

$$
U_k =
w_{\mathrm{flow}}U_{\mathrm{flow},k}
+
w_{\mathrm{value}}U_{\mathrm{value},k}
+
w_{\mathrm{vision}}U_{\mathrm{OOD}}(o).
$$

При одном и том же observation \(U_{\mathrm{OOD}}(o)\) одинаков для всех candidates, поэтому он полезен для решения `act/plan/abstain`, но сам по себе не ранжирует actions внутри candidate set.

### 4.4. Shifting Uncertainty to Critical Moments

**Статья:** Y. Tang et al., *Shifting Uncertainty to Critical Moments: Towards Reliable Uncertainty Quantification for VLA Model*, arXiv:2603.18342.

- [arXiv HTML](https://arxiv.org/html/2603.18342)

Используется standard LIBERO: Spatial, Object, Goal и LIBERO-10. LIBERO-PRO не используется. Base model - OpenVLA, а исходный uncertainty signal - entropy 256-bin action-token distribution для каждого из семи action DoF.

Главная проблема называется **averaging trap**: средняя entropy по длинному rollout скрывает короткий всплеск перед критической ошибкой.

Авторы предлагают:

1. Sliding-window score:

$$
U_{\mathrm{SW}} =
\max_t
\frac{1}{W}
\sum_{\tau=t}^{t+W-1}
\bar H_\tau.
$$

2. Action Transfer Reweighting: entropy получает больший вес, если consecutive actions меняют знак и выглядят осциллирующими.
3. Bayesian optimization весов отдельных DoF, window size и stability contrast на calibration split.

Результаты test AUROC:

| Метод | Spatial | Object | Goal | LIBERO-10 |
|---|---:|---:|---:|---:|
| Global mean entropy | 0.845 | 0.542 | 0.641 | 0.468 |
| Sliding window | 0.908 | 0.765 | 0.837 | 0.699 |
| SW + ATR | 0.919 | 0.772 | 0.841 | 0.738 |
| SW + ATR + BO | 0.936 | 0.793 | 0.811 | 0.838 |

Окно примерно 50-90 low-level steps лучше ловит atomic manipulation events. Gripper и vertical motion часто получают высокие learned weights.

**Вывод для нас**

Наши query metrics нельзя усреднять только по всему episode. Нужны:

- значение на текущем query;
- максимум до текущего query;
- max/mean короткого окна;
- slope и jump относительно предыдущего query;
- phase-aware сравнение около approach, grasp, lift и place.

### 4.5. SUREFlow

**Статья:** M. T. Islam et al., *SUREFlow: State-space Uncertainty-aware REsidual Flow Matching for Robust Robot Manipulation*, arXiv:2607.10504.

- [arXiv HTML](https://arxiv.org/html/2607.10504)
- [Код](https://github.com/tanvirnwu/SUREFlow)

Это одна из наиболее прямых работ по uncertainty-aware flow control. Используются:

- standard LIBERO, все четыре suites;
- LIBERO-PRO;
- Meta-World;
- real-robot color-matching/cup-insertion task.

Модель размером около 179M параметров использует state-space backbone. Две головы предсказывают:

$$
\hat v_\theta(x_t,t,o,l)
\quad\text{и}\quad
\hat \ell_\theta(x_t,t,o,l)=\log \hat\sigma^2,
$$

то есть velocity и input-dependent log-variance residual. Training objective имеет форму heteroscedastic regression:

$$
\mathcal L_{\mathrm{unc}}
\propto
\exp(-\hat\ell)\,
\|v^*-\hat v\|_2^2
+
\hat\ell.
$$

Большой residual при заявленной низкой variance штрафуется сильнее. На inference dimensions с uncertainty выше threshold получают несколько внутренних residual-refinement steps. Это происходит внутри action generator, без нового observation из среды.

Reported results:

- standard LIBERO: Spatial 94.8, Object 91.0, Goal 93.8, Long 90.2, average 92.5%;
- LIBERO-PRO normalized average success около 0.49;
- performance сопоставима с некоторыми VLA в 3-7B параметров;
- средний real-robot success 88.5% на 20 rollout для каждого цвета.

**Ограничения сопоставимости**

- это очень свежий preprint, поэтому результаты пока являются author-reported и требуют независимого воспроизведения;
- uncertainty head обучается специально, а наши текущие metrics извлекаются из pretrained Cosmos без такого head;
- reported LIBERO-PRO score агрегирует пять perturbation types и не является paired comparison planning strategies;
- selective residual refinement не равно best-of-N candidate ranking.

**Наиболее полезная идея**

Если post-hoc metrics окажутся устойчивыми, следующий этап после risk-aware ranking - обучить легкий head, предсказывающий per-action-dimension error/variance, и уточнять только unreliable dimensions.

### 4.6. Исследовательская линия Junwon Seo

Источник: [junwon.me](https://junwon.me/). Ни одна из перечисленных на сайте работ не использует LIBERO или LIBERO-PRO. Три наиболее прямые для нашего проекта работы - UNISafe, AnySafe и StressDream - подробно разобраны в разделах 3.8-3.10.

Это не набор разрозненных uncertainty metrics, а последовательная программа:

1. **Probabilistic ensemble dynamics (RSS 2023):** сначала epistemic uncertainty используется противоположным образом при exploration и deployment. В exploration робот идёт туда, где модель мало знает; при выполнении задачи MPC избегает тех же uncertain state-action regions. Расхождение Gaussian ensemble измеряется JRD.
2. **UNISafe (CoRL 2025):** uncertainty превращается из soft cost в calibrated OOD constraint, а reachability synthesizes fallback policy.
3. **AnySafe (ICRA 2026):** fixed constraint заменяется runtime-conditioned constraint representation; conservativeness настраивается post hoc calibration.
4. **StressDream (2026):** вместо пассивного измерения uncertainty world model активно направляется к редкому, но правдоподобному failure outcome.

Остальные публикации развивают те же принципы в perception/navigation:

| Работа | Основной метод | Переносимый принцип | Прямой приоритет для Cosmos |
|---|---|---|---:|
| Bridging Active Exploration..., 2305.12240 | Probabilistic ensemble dynamics, JRD, sampling MPC | Один UQ signal должен менять decision rule, а не только рисовать confidence | Высокий для будущего data collection |
| E2-BKI, 2509.11964 | Evidential DL, Gaussian map primitives, geometry-aligned kernels | Не усреднять все observations одинаково: confidence и geometry должны влиять на fusion | Средний для multi-view/temporal aggregation |
| Evidential Semantic Mapping, 2403.14138 и 2405.06265 | Evidential segmentation + uncertainty-aware BKI/Dempster-Shafer fusion | Отделять evidence, ignorance и конфликт сенсоров | Средний для external/wrist disagreement |
| OW-Rep, 2409.16073 | Unknown-object refinement с SAM и semantic embedding distillation | OOD object detection и task-action uncertainty являются разными слоями | Средний для LIBERO-PRO object shifts |
| METAVerse, 2307.13991 | Meta-learning + online adaptation по recent interactions | Global gate должен быстро адаптироваться к local task regime | Средний, после появления нескольких init states |
| UFO, 2403.02642 | Multi-scale LiDAR-image fusion с uncertainty-aware pseudo-labels | Pseudo-labels должны быть взвешены confidence | Низкий для текущей camera-only среды |
| DA-RAW, 2309.08152 | Раздельная adaptation style gap и weather gap | OOD надо раскладывать по причинам, а не объединять в один score | Средний для PRO factor families |
| Self-supervised traversability, 2305.18896 и 2209.06522 | Positive-unlabeled/one-class learning из robot experience | Success-only data не покрывает forbidden states; нужны PU/OOD механизмы | Средний для редких safety labels |

**Общий вывод из этой линии.** Хорошая uncertainty-aware система имеет четыре разных объекта:

$$
\underbrace{U_{\mathrm{transition}}(s,a)}_{\text{насколько знаем динамику}},
\quad
\underbrace{R_{\mathrm{outcome}}(s,a)}_{\text{может ли outcome быть плохим}},
\quad
\underbrace{C(s,a;c)}_{\text{нарушается ли constraint }c},
\quad
\underbrace{Q(s,a)}_{\text{полезно ли действие для задачи}}.
$$

Их нельзя без потери смысла заменить одним `uncertainty`. Для task planning нужен robust utility; для safety - constrained decision и fallback; для rare-event evaluation - targeted search; для learning - data acquisition.

### 4.7. Что у нас уже сделано, что было в плане и что действительно новое

| Идея | Статус до этого обзора | Фактический результат / следующий шаг |
|---|---|---|
| Несколько stochastic samples одной Cosmos | Сделано | Четыре candidates; это generative disagreement, не независимый epistemic ensemble |
| Paired success/fail на одном init/seed schedule | Сделано | Используется во всех confirmatory campaigns |
| Prediction error после chunk | Сделано | Future-proprio surrogate переносится (`rho=0.579`, AUROC 0.731), но не улучшил success |
| Soft action/value uncertainty penalty | Сделано | Fixed `action_l1`: +2.1 п.п. на 240 paired seeds, CI пересекает ноль |
| Disagreement-triggered short horizon | Сделано | `requery_l1_h8`: +6.25 п.п., 95% CI [+1.7; +11.3], Holm `p=0.0474`, cost 1.27x |
| Универсальный early fail detector | Сделано, отрицательный результат | Лучший case-controlled AUROC 0.547; absolute threshold пока не работает |
| Разделить reranking и feedback | Было в следующих проверках | Matched 2x2 campaign на 672 rollout запущена 20 августа 2026 |
| Multi-future LCB/CVaR | Было в H7 | Реализовать после проверки causal action-conditioned path |
| Learned task-aware gate/progress | Было в H11/H13 | Proprio-error target недостаточен; нужны drop/contact/no-progress labels |
| Constrained safety + abstain | Было в H8/H14 | UNISafe усиливает план: hard filter, trajectory CP, fallback |
| Независимый transition ensemble | Частично предполагался только как общий ensemble | Новое: lightweight Gaussian heads + JRD вместо второго полного Cosmos |
| Re-denoising consistency | Не было в плане | Новый дешёвый candidate-support baseline из tau0-WM |
| Temporal overlap consistency | Не было в наших traces: сохранялись только первые actions | Published baselines STAC и TIDE; для Cosmos надо сохранять old tail/new prefix целиком и сравнить с learned Hide-and-Seek detector |
| Targeted steering initial noise | Не было в плане | Новый StressDream-style rare-failure search |
| Future-conditioned action rectification | Не было в плане | Новый proposal-evaluation-revision baseline из tau0-WM |
| Grounded real-transition Q + WM tree | Не было в явном плане | Новый QWM depth-1/2 baseline; critic не обучается на imagined transitions |
| Runtime image-conditioned constraints | Не было в плане | AnySafe-style stage после базового LIBERO-Safety classifier |

### 4.8. Temporal overlap consistency: old tail против new prefix

Новая предложенная гипотеза состоит в том, чтобы предсказывать action chunk
дальше, чем он исполняется. При horizon $H=16$ и execution length $K=8$
сохраняется хвост старого chunk $A_q[8:16]$. После восьми реальных шагов новый
query возвращает $A_{q+1}[0:16]$, и его prefix $A_{q+1}[0:8]$ относится к тем
же абсолютным моментам времени, что и сохранённый хвост:

$$
A_q[8:16]\quad\longleftrightarrow\quad A_{q+1}[0:8].
$$

Идея имеет очень близкие, а в одном случае практически точные аналоги.

#### Sentinel / STAC: идея уже формализована как failure detector

[Sentinel: Unpacking Failure Modes of Generative Policies](https://proceedings.mlr.press/v270/agia25a.html)
разделяет failures на erratic и task-progression. Для erratic failures авторы
предлагают Statistical Temporal Action Consistency (STAC): сравнивают
**распределения** старых overlapping tails и новых prefixes через MMD либо
forward/reverse KL. Для PushT используется ровно $H=16$, $K=8$; для других
задач $H=16$, $K=4$. Per-query distances суммируются:

$$
\eta_t=\sum_{i=0}^{j-1}
\widehat D\left(\bar\pi_{ik},\widetilde\pi_{(i+1)k}\right),
$$

а threshold берётся как 95-й percentile cumulative score на successful
calibration rollouts. Авторы показывают, что distributional temporal distance
лучше обычной output variance в multimodal PushT. STAC, однако, плохо ловит
уверенные no-progress failures, поэтому Sentinel добавляет отдельный video
progress monitor. В статье нет LIBERO, Cosmos Policy и causal изменения
planning; более того, авторы формулируют цель как detection failures as they
occur, а не гарантированное предсказание заранее.

Для нас это означает, что plain overlap distance не следует представлять как
новый алгоритм. Исследовательская новизна возможна в sample-efficient переносе
STAC на flow-based world-model policy, положительном lead time до локального
event, OOD/Safety transfer и причинном использовании alarm в planner-е.

В Cosmos best-of-N есть дополнительная тонкость: реальный переход создаёт
prefix только selected candidate, тогда как полный old candidate set содержит
контрфактические prefixes. Поэтому наряду с full STAC нужен selection-aware
вариант: selected old tail против нового candidate support либо
prefix-weighted old distribution.

#### BID: overlap distance как candidate-selection score

[Bidirectional Decoding](https://arxiv.org/abs/2408.17355) сохраняет старое
решение и выбирает новый candidate с малым weighted overlap distance:

$$
\mathcal L_B=
\sum_{\ell=0}^{L-1}\rho^\ell
\left\|A_{q+1}[\ell]-A_q[K+\ell]\right\|_2.
$$

Это прямой planning-аналог нашей идеи, но не calibrated uncertainty metric.
Важное ограничение из BID: после неожиданного изменения среды старый plan может
быть ошибочным, поэтому высокая consistency не всегда желательна. Жёсткое
следование old tail способно подавить полезную closed-loop correction.

#### ACT и SEAM: overlap как средство smooth execution

[ACT](https://roboticsproceedings.org/rss19/p016.html) ввёл temporal ensembling:
несколько прогнозов одного и того же physical action усредняются с временными
весами. Это использует ту же структуру перекрывающихся предсказаний, но выдаёт
сглаженное действие, а не uncertainty score.

[SEAM](https://arxiv.org/abs/2607.04609) ещё ближе к нашей архитектуре: для
flow-based VLA старый unexecuted tail используется как analytic prior при
генерации нового chunk. На LIBERO-10 с pi0.5 авторы сообщают снижение boundary
jerk на 28% и chunk discontinuity на 27% при сохранении baseline success.
Слишком сильное guidance снижает success, а temporal ensembling может
усреднить несовместимые modes. Поэтому overlap alarm, weak penalty и hard
continuation должны быть тремя разными ablations.

#### VLA-Corrector: расширение на predicted/actual image dynamics

[VLA-Corrector](https://arxiv.org/abs/2607.01804) обучает lightweight latent
dynamics corrector и сравнивает ожидаемое с реальным изменением visual latent:

$$
E_t=1-\operatorname{CosSim}
\left(\Delta Z_{t+k}^{\mathrm{expected}},
\Delta Z_{t+k}^{\mathrm{real}}\right).
$$

Persistent mismatch сокращает текущий action horizon и вызывает corrective
replanning. Работа использует standard LIBERO, MetaWorld и real robot, но не
LIBERO-PRO. Это хороший baseline для предлагаемого расширения на image/state.

Для Cosmos есть важная временная ловушка: текущие `future_image`, future
proprio и value соседних query относятся к разным endpoint times. Их нельзя
просто вычесть. Нужен либо old prediction versus later reality, либо два
прогноза одного fixed absolute endpoint, либо временная latent sequence.

#### Rewind-IL / TIDE: та же гипотеза как training-free detector

[Rewind-IL](https://arxiv.org/html/2604.16683) формализует Temporal
Inter-chunk Discrepancy Estimate как средний squared error между выровненным
остатком прошлого plan и новым prefix:

$$
\operatorname{TIDE}_t=
\frac{1}{BDT}\sum_{b,d,\tau}
\left(
\widehat A^{(b)}_{t-1,\tau,d}-
\widetilde A^{(b)}_{t,\tau,d}
\right)^2.
$$

Threshold задаётся split conformal prediction по successful calibration
rollouts, после чего alarm запускает возврат к семантически подтверждённому
checkpoint. Работа проверяет шесть real ACT tasks, три RoboCasa tasks и три
flow-matching tasks. Авторы сообщают average detection bACC 0.95 для ACT и
0.99 для flow matching, а в RoboCasa success вырастает с 55-60% до 70-80%.

Следовательно, наш selected old-tail/new-prefix MSE - это TIDE-style baseline.
Отдельный вклад возможен не в самой формуле, а в distributional best-of-$N$
варианте Cosmos, OOD/Safety transfer, раннем warning до локального event и
причинном улучшении planner-а.

#### Hide-and-Seek: learned detector именно на LIBERO

[Hide-and-Seek in Trajectories](https://arxiv.org/html/2605.30834) обучает
небольшой sequential detector по frozen action embeddings, используя только
trajectory-level success/fail. Inter-trajectory contrastive loss ищет наиболее
failure-indicative timestep, а intra-trajectory loss усиливает разрыв до и
после автоматически найденного onset. Для online alarm используется
time-varying functional conformal threshold

$$
\zeta_t=\mu_t+h\,\sigma(t).
$$

Эксперименты включают standard LIBERO-10 с OpenVLA и $\pi_0$: 500 episodes на
policy, seen/unseen task split и три random seeds. Среди 12 baselines есть
STAC с десятью stochastic samples на step. Для OpenVLA авторы сообщают bACC
0.852/0.834 на seen/unseen tasks против 0.665/0.624 у STAC. Это сильный сигнал,
что multi-sample disagreement может быть недостаточен без временного контекста
и supervision о failed episodes.

У нас уже есть natural success/fail trajectories, поэтому Hide-and-Seek-style
LSTM является реалистичным supervised upper baseline. Его нельзя смешивать с
zero-shot TIDE/STAC: первый требует failed train data, вторые калибруются только
на successes.

#### AutoIntervene: phase-aware support и действие после alarm

[AutoIntervene](https://arxiv.org/html/2608.07065) оценивает visual embedding и
proposed action prefix совместно относительно phase-local memory успешных
trajectories. Calibrated thresholds и persistence управляют передачей контроля
оператору и возвратом policy. Для нас важны phase-aware action support и
устойчивый alarm в нескольких query; вместо оператора simulator может
сократить execution horizon, пересемплировать candidates или вызвать recovery.

Полная постановка, метрики, ablations, collector schema и causal test:
[`../experiments/TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md`](../experiments/TEMPORAL_OVERLAP_CONSISTENCY_PROTOCOL_20260820.md).

## 5. Сводные выводы из статей

1. **Standard LIBERO насыщен.** Cosmos Policy получает около 98.5%, поэтому natural failures проще и честнее собирать на boundary configurations LIBERO-PRO или factorized LIBERO-Plus.
2. **PRO и Plus решают разные задачи.** PRO дает жесткий OOD stress test; Plus удобен для ablation причин failure.
3. **Episode mean скрывает критические моменты.** Локальное окно, jump, slope и phase-aware aggregation должны быть обязательными.
4. **Stochastic sample variance и ensemble epistemic uncertainty различаются.** Первая измеряет multimodality/noise одной policy, вторая требует независимых weights.
5. **Value uncertainty не заменяет value bias.** Низкий `value_std` при высоком, но ошибочном `mean_value` является overconfident failure.
6. **Prediction error after chunk является retrospective metric.** Его можно использовать как label, calibration target или input следующего query, но нельзя честно использовать для выбора уже выполненного chunk.
7. **Pixel quality не равна control quality.** Semantic latent, proprio, object pose и action-recovery errors нужно сравнивать с RGB metrics.
8. **OOD detection и candidate ranking различаются.** Observation-level OOD score определяет, когда надо plan/abstain, но не различает candidates из одного state.
9. **Uncertainty полезна только через downstream решение.** Хороший AUROC еще не доказывает рост planning success rate.
10. **Нужен paired evaluation.** Каждая стратегия должна видеть один и тот же initial state и, по возможности, один и тот же candidate pool.
11. **Наш лучший подтверждённый метод - combined adaptive requery.** `requery_l1_h8` дал +6.25 п.п. на 240 paired seeds, тогда как fixed action penalty дал +2.1 п.п. с CI через ноль. Это указывает на важность более раннего feedback, но причинно отделить его от reranking должна текущая matched 2x2 кампания.
12. **Rare failure не равен высокой variance.** StressDream показывает, что best-of-N может не найти low-probability catastrophic outcome. Нужен targeted pessimistic search при сохранении typicality noise.
13. **Self-consistency не равна physical correctness.** RCS проверяет support action под policy, а grounded Q, transition uncertainty и actual outcome risk проверяют другие свойства. Эти сигналы надо ablate раздельно.
14. **Soft risk и hard safety имеют разные цели.** UNISafe показывает, что uncertainty penalty может улучшать expected return, но не заменяет calibrated reject set и fallback.
15. **World-model value надо заземлять реальными transitions.** QWM не обучает policy/Q на imagined data и использует WM только для короткого search. Это снижает риск самоусиления ошибки Cosmos value.
16. **Длинное дерево не обязательно лучше.** QWM находит лучший trade-off на умеренной глубине; большие depth и candidate count усиливают model/extreme-value error. Для нас первый честный шаг - depth 1 против 2, не большой search.
17. **Prediction-error surrogate должен быть task-critical.** Наш future-proprio estimator перенёсся, но не улучшил success; следующий target - drop, contact loss, object-pose divergence и no-progress.
18. **Safety semantics должны быть условными.** AnySafe показывает, что запрет зависит от текущего constraint. Для LIBERO-Safety нужен `constraint-conditioned risk`, а не один глобальный failure score.
19. **Соседние chunks надо сравнивать по одинаковому physical time.** Для $H=16,K=8$ корректная пара - old `[8:16]` и new `[0:8]`; первые половины соседних chunks несопоставимы.
20. **Temporal consistency уже является сильным published baseline.** Sentinel/STAC использует distributional overlap distance для erratic-failure detection, BID - для candidate selection, SEAM - для flow guidance. Наш тест должен сравниваться со всеми тремя интерпретациями.
21. **Consistency и correctness различны.** Высокий disagreement может быть полезной коррекцией, а низкий - уверенно неправильным планом. Поэтому overlap detector должен дополняться progress/outcome signal и проверяться causal intervention-ом.
22. **Selected overlap MSE уже имеет имя TIDE.** Rewind-IL показывает, что такой training-free signal можно conformal-калибровать и связать с recovery; в нашей работе это обязательный baseline, а не claim новизны.
23. **Threshold должен учитывать фазу.** Hide-and-Seek использует functional conformal band, потому что нормальный разброс меняется по времени. Один глобальный threshold может переобучиться на grasp/release boundaries.
24. **Failed trajectories позволяют сильный supervised baseline.** Hide-and-Seek на LIBERO-10 превосходит multi-sampling methods; наши episode labels стоит использовать для LSTM baseline, сохраняя отдельную zero-shot оценку TIDE/STAC.

## 6. Предлагаемый протокол наших экспериментов

Разделы 6-8 сохраняют базовый protocol сбора и честного сравнения. Актуальная
очередь новых методов после confirmatory результатов вынесена в
[`../experiments/RESEARCH_ROADMAP_20260820.md`](../experiments/RESEARCH_ROADMAP_20260820.md).

### 6.1. Исследовательские вопросы

**RQ1.** Какие online metrics до исполнения action chunk отделяют natural success от natural fail при одинаковых `suite/task/init_state`?

**RQ2.** Улучшает ли risk-aware score реальный выбор candidate action относительно `max(mean_value)`?

**RQ3.** Переносятся ли веса и threshold с одних tasks/init states на held-out LIBERO-PRO configurations?

**RQ4.** Дает ли observation-level OOD score дополнительную пользу для решения `direct policy / planning / abstain`?

**RQ5.** Какие prediction errors после chunk объясняют механизм failure и могут служить target для будущего learned uncertainty head?

**RQ6.** Выигрыш adaptive requery вызван reranking, более ранним реальным observation или их interaction?

**RQ7.** Предсказывает ли STAC-style disagreement между old action-tail и new
overlap-prefix локальный event до его наступления, и улучшает ли такой alarm
candidate selection или feedback horizon? Как соотносятся TIDE-style selected
MSE, distributional STAC и learned Hide-and-Seek-style detector при одинаковых
case splits и false-alarm budget?

**RQ8.** Дополняет ли re-denoising consistency наши internal-copy metrics при candidate selection?

**RQ9.** Находит ли targeted pessimistic imagination реальные failures чаще random future sampling при одинаковом compute budget?

**RQ10.** Даёт ли grounded Q-head и depth-2 search переносимый прирост относительно self-generated Cosmos value?

**RQ11.** Может ли trajectory-calibrated transition uncertainty обеспечить снижение official LIBERO-Safety violations без неприемлемого роста timeout/abstention?

### 6.2. Этап 0: integrity check

На standard LIBERO:

- воспроизвести хотя бы одну задачу из каждого suite;
- проверить cameras, proprio order, action normalization, chunk length и success detector;
- сохранить checksum checkpoint/config;
- убедиться, что одинаковые seeds дают воспроизводимый candidate pool.

Этот этап не используется для выбора лучших hyperparameters.

### 6.3. Этап 1: поиск boundary configurations

Перебирать LIBERO-PRO от сложных вариантов к более простым:

1. `Task` и `Pos`;
2. `Env`;
3. `Obj`;
4. `Sem`.

Для каждого `suite/task/init_state/configuration` сделать 12 discovery rollouts baseline policy с разными rollout seeds.

Сохранить configuration, если:

$$
0.2 \le \widehat p_{\mathrm{success}} \le 0.8.
$$

Исключить:

- почти всегда успешные cases, где нет fail signal;
- почти всегда провальные cases, где нет хорошего candidate;
- false fail из-за неверного success detector;
- timeout после фактически выполненной задачи.

Затем использовать LIBERO-Plus для factorized variants того же case: отдельно менять camera, robot initial pose, background, lighting и noise.

### 6.4. Этап 2: paired data collection

Единица сравнения:

$$
c=(\text{suite},\text{task},\text{init state},\text{perturbation}).
$$

Для каждого \(c\):

- одинаковый task instruction для основного paired experiment;
- одинаковое serialized simulator initial state;
- общий список rollout seeds для всех strategies;
- общий candidate-generation seed на каждом query, если код позволяет;
- минимум 12 rollout на strategy для screening;
- 30-50 rollout на strategy для финального вывода.

Разделение данных выполняется по `configuration/init_state`, а не по отдельным query rows:

- discovery/train: подбор feature set и weights;
- calibration: выбор \(\lambda\) и thresholds;
- held-out test: только финальная оценка.

Нельзя случайно разделять queries одного episode между train и test: это leakage.

### 6.5. Что сохранять на каждом query

До выполнения chunk:

- RGB external и wrist observations;
- proprio и доступные object states;
- instruction;
- все candidate action chunks;
- stochastic noise seeds;
- predicted future image/latent/proprio;
- value samples;
- внутренние action/future/value latent copies;
- все online uncertainty metrics;
- score каждого candidate и выбранный candidate.

После выполнения chunk:

- реальный RGB/proprio/object state;
- число реально выполненных low-level steps;
- image MSE, SSIM, LPIPS;
- semantic latent distance;
- proprio L2;
- object-pose error;
- contact/grasp/drop/collision events;
- simulator success;
- timestamp первого необратимого fail.

Для каждого episode:

- полный MP4 до terminal state или 220 steps;
- query table в Parquet/CSV;
- machine-readable metadata JSON;
- storyboard с synchronized true/fail frames;
- краткая failure annotation.

### 6.6. Базовые uncertainty metrics

Пусть одна и та же policy из состояния \(s_q\) генерирует \(M\) stochastic samples:

$$
A^{(m)}\in\mathbb R^{H\times D_a},
\qquad
\hat P^{(m)}\in\mathbb R^{H_p\times D_p},
\qquad
\hat v^{(m)}\in\mathbb R.
$$

#### Первое действие

$$
U_{\mathrm{action,first}}
=
\sqrt{
\frac{1}{D_a}
\sum_{d=1}^{D_a}
\operatorname{Var}_{m}
\left[A^{(m)}_{0,d}\right]
}.
$$

Эта метрика не размывает ближайшее управляющее решение по всему chunk.

#### Полный action chunk

$$
U_{\mathrm{action,chunk}}
=
\sqrt{
\frac{1}{H D_a}
\sum_{h=0}^{H-1}
\sum_{d=1}^{D_a}
\operatorname{Var}_{m}
\left[A^{(m)}_{h,d}\right]
}.
$$

Дополнительно считаются translation, rotation и gripper uncertainty отдельно.

#### Value

$$
\mu_v=\frac{1}{M}\sum_m \hat v^{(m)},
\qquad
U_{\mathrm{value,std}}=\operatorname{Std}_m[\hat v^{(m)}],
$$

$$
U_{\mathrm{value,range}}
=
\max_m \hat v^{(m)}
-
\min_m \hat v^{(m)}.
$$

`value_range` относится к value samples, сгенерированным для одного candidate на одном query. Это не диапазон value по всему episode.

#### Future proprio

$$
U_{\mathrm{future\_proprio}}
=
\sqrt{
\frac{1}{H_p D_p}
\sum_{h,d}
\operatorname{Var}_{m}
\left[\hat P^{(m)}_{h,d}\right]
}.
$$

Future proprio - предсказанная последовательность будущих robot states: положение/orientation end-effector, gripper state и другие proprio components в формате Cosmos. Это не реальное observation после chunk.

#### Latent disagreement

Для latent tensor \(Z^{(m)}\in\mathbb R^{C_1\times\cdots\times C_r}\):

$$
U_{\mathrm{latent}}(Z)
=
\frac{1}{\prod_j C_j}
\sum_{c_1,\ldots,c_r}
\operatorname{Std}_m
\left[Z^{(m)}_{c_1,\ldots,c_r}\right].
$$

Именно так интерпретируются семейства:

- `latent_action_copy_std_*`;
- `latent_future_proprio_copy_std_*`;
- `latent_value_element_std_*`.

Suffix вида `mean_over_samples__std` означает последовательную агрегацию по внутренним dimensions, samples и queries. В итоговых моделях лучше использовать короткие, явно определенные имена, а mapping старых колонок хранить рядом с dataset schema.

### 6.7. Локальные temporal features

Для metric \(u_q\) на query \(q\):

$$
u_q^{\mathrm{jump}}=u_q-u_{q-1},
\qquad
u_q^{\mathrm{slope}}=
\frac{u_q-u_{q-L}}{L},
$$

$$
u_q^{\mathrm{SW}}=
\max_{t\le q}
\frac{1}{W}
\sum_{j=t-W+1}^{t}u_j.
$$

Для action chunk дополнительно:

$$
U_{\mathrm{osc}}
=
\frac{1}{(H-1)D_a}
\sum_{h=1}^{H-1}\sum_d
\mathbb 1
\left[
\operatorname{sign}(a_{h,d})
\ne
\operatorname{sign}(a_{h-1,d})
\right].
$$

Главные графики строятся:

- только до matched terminal moment success/fail;
- с вертикальными линиями query boundaries;
- с отметками grasp, lift, drop, place и success;
- со средним и bootstrap confidence interval для success/fail groups.

### 6.8. Planning strategies

#### Baseline 1: один sample

Обычный direct-policy candidate без planning.

#### Baseline 2: max predicted value

$$
k^*_{\mathrm{maxV}}=
\arg\max_k \mu_{v,k}.
$$

#### Strategy A: value lower confidence bound

$$
k^*_{\mathrm{LCB}}=
\arg\max_k
\left(
\mu_{v,k}
-
\lambda_v \sigma_{v,k}
\right).
$$

Это первая стратегия для обязательной проверки: она проста, прозрачна и использует uncertainty того же value, по которому работает baseline.

#### Strategy B: composite risk

Каждая metric стандартизуется **только по calibration set**, лучше robust scaling:

$$
z_j(u)=
\frac{
u-\operatorname{median}_{\mathrm{cal}}(u)
}{
\operatorname{IQR}_{\mathrm{cal}}(u)+\epsilon
}.
$$

Risk:

$$
R_k =
w_a z(U_{\mathrm{action,first},k})
+
w_v z(U_{\mathrm{value,std},k})
+
w_r z(U_{\mathrm{value,range},k})
+
w_p z(U_{\mathrm{future\_proprio},k})
+
w_\ell z(U_{\mathrm{latent},k}).
$$

Planner:

$$
k^*_{\mathrm{composite}}=
\arg\max_k
\left[
\mu_{v,k}-\lambda R_k
\right].
$$

Weights и \(\lambda\) выбираются один раз на calibration set. Нельзя подбирать их по test success.

#### Strategy C: overconfidence penalty

Опасный случай - высокое value при нестабильных predictions:

$$
R_{\mathrm{overconf},k}
=
\sigma(\alpha z(\mu_{v,k}))
\cdot
\operatorname{softplus}
\left(
\sum_j w_j z(U_{j,k})
\right).
$$

$$
\operatorname{score}_k
=
\mu_{v,k}
-
\lambda R_{\mathrm{overconf},k}.
$$

Так сильнее штрафуются candidates, которые одновременно выглядят очень ценными и имеют высокую uncertainty.

#### Strategy D: plan or abstain

$$
\text{mode}(o)=
\begin{cases}
\text{direct}, & U_{\mathrm{OOD}}(o)<\tau_1,\\
\text{risk-aware planning}, & \tau_1\le U_{\mathrm{OOD}}(o)<\tau_2,\\
\text{abstain/recovery}, & U_{\mathrm{OOD}}(o)\ge\tau_2.
\end{cases}
$$

Эта strategy требует явного fallback: уменьшенный chunk, повторный query, безопасное открытие gripper, возврат в pre-grasp pose или human intervention.

### 6.9. Честное сравнение strategies

Для каждого query желательно сначала один раз создать candidate set:

$$
\mathcal C_q=
\left\{
(A_k,\hat S_k,\hat V_k,\text{metrics}_k)
\right\}_{k=1}^{K},
$$

а затем offline вычислить, что выбрала бы каждая scoring rule. Для реального closed-loop rollout стратегии затем запускаются отдельно, но с одинаковыми initial states и seed schedule.

Считать:

- success rate и bootstrap 95% CI;
- paired win/loss/tie;
- McNemar test для paired binary outcomes;
- candidate regret относительно retrospective oracle;
- top-1 oracle hit rate;
- mean task progress;
- drop/collision/timeout rates;
- mean compute time на query;
- число replans/abstentions.

Для fail predictor:

- AUROC;
- AUPRC, особенно при редких fail;
- balanced accuracy;
- TPR и TNR;
- Brier score/calibration;
- detection lead time до первого необратимого failure event.

### 6.10. Ablations

Минимальный набор:

1. `max(mean_value)`.
2. `mean_value - lambda * value_std`.
3. `mean_value - lambda * action_first_std`.
4. Composite без latent metrics.
5. Composite с latent metrics.
6. Episode mean против sliding-window/jump features.
7. Одна policy со stochastic samples против независимого двухмодельного ensemble.
8. Без visual OOD routing против `act/plan/abstain`.
9. RGB prediction error против semantic/proprio/object-state errors.
10. Chunk 16 против более частого replanning около high-risk query.

### 6.11. Гипотезы и ожидаемые результаты

Это гипотезы, а не уже доказанные результаты:

- **H1:** `action_first_std`, `value_std/range` и некоторые latent disagreements будут возрастать около grasp/lift/place и отделять часть fail до необратимой ошибки.
- **H2:** local-window и jump features будут сильнее полного episode mean.
- **H3:** future proprio/object error будет лучше связан с contact failure, чем RGB MSE.
- **H4:** visual OOD score улучшит routing между direct/planning/abstain, но почти не поможет ranking candidates одного query.
- **H5:** moderate uncertainty penalty повысит success и снизит drops; слишком большой \(\lambda\) сделает policy консервативной и снизит progress.
- **H6:** independently trained ensemble даст более надежный epistemic OOD signal, чем stochastic copies одного checkpoint, но будет дороже.
- **H7:** learned heteroscedastic head в стиле SUREFlow может превзойти post-hoc dispersion после накопления размеченных natural failures.

### 6.12. Критерий сильного результата

Сильным результатом считается не красивое разделение двух выбранных видео, а одновременное выполнение условий:

1. Метрика и weights выбраны без test leakage.
2. Failure prediction лучше случайного на held-out task/init configurations.
3. Risk-aware planner статистически и практически лучше `max(value)` в paired rollouts.
4. Улучшение сохраняется хотя бы на двух разных PRO perturbation families.
5. Не происходит резкого роста timeout или излишних abstentions.
6. В логах виден механизм выигрыша: baseline выбрал overconfident candidate, а risk-aware score выбрал исполнимую альтернативу.

## 7. Рекомендуемый порядок запуска

| Этап | Цель | Объем |
|---|---|---:|
| Smoke | Проверить pipeline и полный MP4 | 1-3 rollout |
| Boundary search | Найти mixed success/fail configurations | 12 rollout на case |
| Metric screening | Убрать нестабильные и дублирующие features | Не менее 5 success + 5 fail |
| Strategy screening | Сравнить maxV, LCB, composite | 12 paired rollout на strategy |
| Held-out test | Финальная проверка без настройки | 30-50 rollout на strategy/case |
| Generalization | Новые task/init/PRO factors | Минимум два perturbation families |

Сначала следует завершить planning comparison на уже найденном mixed case. Затем frozen strategies переносятся на новые LIBERO-PRO configurations. Поиск новых cases и подбор formula на одних и тех же данных приведут к оптимистичной оценке.

## 8. Команды в текущем репозитории

Все команды ниже запускаются из корня `YSDA_WORD_MODELS_PP`. На сервере сначала надо проверить `nvidia-smi`; GPU 0 не использовать. Например, физическая GPU 2 передается процессу как:

```bash
CUDA_VISIBLE_DEVICES=2 command
```

### 8.1. Поиск natural success/fail на одном initial state

Пример для известной milk configuration. Collector меняет rollout seed, но сохраняет suite, task и init state:

```bash
CUDA_VISIBLE_DEVICES=2 \
LIBERO_PRO_NATURAL_PAIR_RUN_NAME=milk_task5_init0_pair_search \
LIBERO_PRO_NATURAL_PAIR_SUITES=libero_spatial_with_milk \
LIBERO_PRO_NATURAL_PAIR_TASK_IDS=5 \
LIBERO_PRO_NATURAL_PAIR_INIT_STATE_IDS=0 \
LIBERO_PRO_NATURAL_PAIR_MAX_ROLLOUTS=16 \
LIBERO_PRO_NATURAL_PAIR_MIN_SUCCESS=1 \
LIBERO_PRO_NATURAL_PAIR_MIN_FAILED=1 \
LIBERO_PRO_NATURAL_PAIR_BASE_SEED=97000 \
LIBERO_PRO_NATURAL_PAIR_UNCERTAINTY_SEEDS=0,1,2,3 \
LIBERO_PRO_NATURAL_PAIR_MAX_TIMESTEPS=220 \
LIBERO_PRO_NATURAL_PAIR_SAVE_VIDEOS=1 \
./scripts/run_libero_pro_natural_fail_same_init_search.sh
```

Этот режим может завершиться сразу после нахождения хотя бы одного success и одного fail. Чтобы собрать фиксированные 12 rollout независимо от исходов:

```bash
CUDA_VISIBLE_DEVICES=2 \
LIBERO_PRO_NATURAL_PAIR_RUN_NAME=milk_task5_init0_fixed12 \
LIBERO_PRO_NATURAL_PAIR_SUITES=libero_spatial_with_milk \
LIBERO_PRO_NATURAL_PAIR_TASK_IDS=5 \
LIBERO_PRO_NATURAL_PAIR_INIT_STATE_IDS=0 \
LIBERO_PRO_NATURAL_PAIR_MAX_ROLLOUTS=12 \
LIBERO_PRO_NATURAL_PAIR_MIN_SUCCESS=999 \
LIBERO_PRO_NATURAL_PAIR_MIN_FAILED=999 \
LIBERO_PRO_NATURAL_PAIR_BASE_SEED=97000 \
LIBERO_PRO_NATURAL_PAIR_UNCERTAINTY_SEEDS=0,1,2,3 \
LIBERO_PRO_NATURAL_PAIR_MAX_TIMESTEPS=220 \
LIBERO_PRO_NATURAL_PAIR_SAVE_VIDEOS=1 \
./scripts/run_libero_pro_natural_fail_same_init_search.sh
```

Основные outputs:

- `experiments/uncertainty/<run>__query_traces.csv`;
- `experiments/uncertainty/<run>__query_traces.parquet`;
- `experiments/uncertainty/<run>__pair_summary.csv`;
- `experiments/uncertainty/<run>__metadata.json`;
- `experiments/uncertainty/<run>__videos/`.

### 8.2. Анализ query traces

```bash
RUN_NAME=milk_task5_init0_fixed12

./scripts/analyze_libero_pro_uncertainty.sh \
  "experiments/uncertainty/${RUN_NAME}__query_traces.csv" \
  "experiments/uncertainty/${RUN_NAME}__analysis"
```

В analysis directory появляются:

- `episode_features.csv`;
- `ranked_episode_features.csv`;
- `ranked_within_pair_features.csv`;
- `ranked_uncertainty_error_correlations.csv`;
- `time_aligned_features.csv`;
- `summary.json`;
- plots top-ranked features.

Ranking из этого шага является exploratory. Feature selection надо заморозить до held-out planning test.

### 8.3. Реальное closed-loop сравнение planning strategies

Поддерживаемые текущим grid script стратегии:

- `max_value`;
- `uncertainty_penalty_action`;
- `uncertainty_penalty_value`;
- `uncertainty_penalty_combined`.

Текущая реализация в `uncertainty_comparison.py` использует:

$$
c^a_k =
\texttt{latent\_action\_first\_step\_copy\_l2\_std}_k,
$$

$$
c^v_k =
\texttt{latent\_value\_element\_std\_mean}_k.
$$

На каждом query value и обе uncertainty metrics отдельно z-нормализуются **внутри текущего candidate set**:

$$
z^V_k=z_{\mathcal C_q}(v_k),
\qquad
z^a_k=z_{\mathcal C_q}(c^a_k),
\qquad
z^v_k=z_{\mathcal C_q}(c^v_k).
$$

Тогда реальные scores grid script равны:

$$
\operatorname{score}^{\mathrm{action}}_k
=z^V_k-\lambda z^a_k,
$$

$$
\operatorname{score}^{\mathrm{value}}_k
=z^V_k-\lambda z^v_k,
$$

$$
\operatorname{score}^{\mathrm{combined}}_k
=z^V_k-\frac{\lambda}{2}(z^a_k+z^v_k).
$$

Это надо отличать от более общего proposed composite score из раздела 6.8, где scaling и weights обучаются на отдельном calibration set. Название `uncertainty_penalty_value` здесь означает uncertainty **внутреннего latent value prediction**, а не `value_range` по всему эпизоду.

Перед запуском значения `VALUE_LAMBDA` и `COMBINED_LAMBDA` должны быть выбраны на calibration runs:

```bash
: "${VALUE_LAMBDA:?Set VALUE_LAMBDA from calibration}"
: "${COMBINED_LAMBDA:?Set COMBINED_LAMBDA from calibration}"

CUDA_VISIBLE_DEVICES=2 \
LIBERO_PRO_PLANNING_GRID_PREFIX=milk_task5_init0_heldout12 \
LIBERO_PRO_PLANNING_GRID_SUITES=libero_spatial_with_milk \
LIBERO_PRO_PLANNING_GRID_TASK_IDS=5 \
LIBERO_PRO_PLANNING_GRID_INIT_STATE_IDS=0 \
LIBERO_PRO_PLANNING_GRID_MAX_ROLLOUTS_PER_INIT=12 \
LIBERO_PRO_PLANNING_GRID_BASE_SEED=120000 \
LIBERO_PRO_PLANNING_GRID_UNCERTAINTY_SEEDS=0,1,2,3 \
LIBERO_PRO_PLANNING_GRID_MAX_TIMESTEPS=220 \
LIBERO_PRO_PLANNING_GRID_STRATEGY_LAMBDAS="max_value:0 uncertainty_penalty_value:${VALUE_LAMBDA} uncertainty_penalty_combined:${COMBINED_LAMBDA}" \
LIBERO_PRO_PAIRED_SAVE_VIDEOS=1 \
LIBERO_PRO_PLANNING_GRID_FORCE=0 \
./scripts/run_libero_pro_planning_strategy_grid.sh
```

Grid автоматически:

1. Выполняет каждую strategy на общем seed schedule.
2. Сохраняет отдельные traces и logs.
3. Запускает `compare_real_planning_strategy_runs.py`.
4. Создает `planning_strategy_summary.csv`, per-case outcomes и success-rate plots.

`LIBERO_PRO_PLANNING_GRID_FORCE=0` пропускает уже завершенные runs с непустым trace. Это позволяет продолжить grid после отключения компьютера. Значение `1` следует использовать только для намеренного полного перезапуска.

### 8.4. Правила перед финальным запуском

1. Записать в metadata commit/hash кода, checkpoint, suite/task/init и все seeds.
2. Не менять formula и \(\lambda\) после просмотра held-out outcomes.
3. Использовать новые base seeds относительно discovery runs.
4. Проверить, что MP4 содержит все выполненные low-level steps до 220 или terminal.
5. Анализировать metrics только до matched completion/failure moment.
6. Отдельно помечать simulator timeout и физический manipulation failure.

## 9. Короткий список источников

1. [UQ for Flow-Based VLA, arXiv:2606.18043](https://arxiv.org/html/2606.18043)
2. [Cosmos Policy, arXiv:2601.16163](https://arxiv.org/html/2601.16163)
3. [mimic-video, arXiv:2512.15692](https://arxiv.org/html/2512.15692)
4. [LIBERO-Safety, arXiv:2606.23686](https://arxiv.org/html/2606.23686)
5. [pi0.5, arXiv:2504.16054](https://arxiv.org/abs/2504.16054)
6. [pi*0.6 / RECAP, arXiv:2511.14759](https://arxiv.org/abs/2511.14759)
7. [DreamDojo, arXiv:2602.06949](https://arxiv.org/html/2602.06949)
8. [Reconstruction or Semantics?, arXiv:2605.06388](https://arxiv.org/html/2605.06388)
9. [LIBERO-PRO, arXiv:2510.03827](https://arxiv.org/html/2510.03827)
10. [LIBERO-Plus, arXiv:2510.13626](https://arxiv.org/html/2510.13626)
11. [Act, Think or Abstain, arXiv:2603.05147](https://arxiv.org/html/2603.05147)
12. [Shifting Uncertainty to Critical Moments, arXiv:2603.18342](https://arxiv.org/html/2603.18342)
13. [SUREFlow, arXiv:2607.10504](https://arxiv.org/html/2607.10504)
14. [Junwon Seo: publications and projects](https://junwon.me/)
15. [UNISafe, arXiv:2505.00779](https://arxiv.org/html/2505.00779)
16. [AnySafe, arXiv:2509.19555](https://arxiv.org/html/2509.19555)
17. [StressDream, arXiv:2606.00267](https://arxiv.org/html/2606.00267)
18. [tau0-WM, arXiv:2606.01027](https://arxiv.org/html/2606.01027)
19. [Q-Learning With World Models, arXiv:2608.17163](https://arxiv.org/html/2608.17163)
20. [Bridging Active Exploration and Uncertainty-Aware Deployment, arXiv:2305.12240](https://arxiv.org/abs/2305.12240)
21. [E2-BKI, arXiv:2509.11964](https://arxiv.org/abs/2509.11964)
22. [Sentinel / STAC, CoRL 2024](https://proceedings.mlr.press/v270/agia25a.html)
23. [Bidirectional Decoding, ICLR 2025](https://arxiv.org/abs/2408.17355)
24. [ACT, RSS 2023](https://roboticsproceedings.org/rss19/p016.html)
25. [SEAM, arXiv:2607.04609](https://arxiv.org/abs/2607.04609)
26. [VLA-Corrector, arXiv:2607.01804](https://arxiv.org/abs/2607.01804)
27. [Diffusion Policy, RSS 2023 / IJRR 2024](https://diffusion-policy.cs.columbia.edu/)
28. [Real-Time Chunking, NeurIPS 2025](https://arxiv.org/abs/2506.07339)
29. [REMAC, arXiv:2601.20130](https://arxiv.org/abs/2601.20130)
30. [Legato, arXiv:2602.12978](https://arxiv.org/abs/2602.12978)
31. [FutureRTC, arXiv:2607.24008](https://arxiv.org/abs/2607.24008)
32. [Rewind-IL / TIDE, arXiv:2604.16683](https://arxiv.org/html/2604.16683)
33. [Hide-and-Seek in Trajectories, arXiv:2605.30834](https://arxiv.org/html/2605.30834)
34. [AutoIntervene, arXiv:2608.07065](https://arxiv.org/html/2608.07065)

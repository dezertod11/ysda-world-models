# Temporal overlap consistency: протокол проверки

Дата постановки: 20 августа 2026 года.

Статус: новая гипотеза и план эксперимента. Результатов по этой метрике пока
нет. Документ не следует переписывать после просмотра confirmatory outcomes;
изменения гиперпараметров должны фиксироваться отдельной amendment-записью.

## Короткая идея

Cosmos Policy предсказывает action chunk длины $H=16$, но контроллер может
выполнить только первые $K=8$ действий. Неисполненный хвост из восьми
действий сохраняется. После восьми реальных шагов модель получает новое
наблюдение и строит следующий chunk. Первые восемь действий нового chunk и
сохранённый хвост старого относятся к одним и тем же номинальным моментам
времени:

$$
A_q[8:16]
\quad\longleftrightarrow\quad
A_{q+1}[0:8].
$$

Основная гипотеза: если исполнение развивается ожидаемо и локальный план
остаётся корректным, два прогноза должны быть согласованы. Если реальный
переход оказался неожиданным, политика сменила несовместимый mode или впереди
возникает локальный failure, overlap disagreement должен вырасти до исполнения
следующих восьми действий.

Это не полностью новая идея. Практически такая же distributional постановка
уже предложена в Sentinel под названием Statistical Temporal Action
Consistency (STAC), а scalar MSE-вариант формализован в Rewind-IL как TIDE.
Наша исследовательская задача состоит в следующем:

1. перенести STAC с diffusion policies на Cosmos Policy;
2. проверить его на standard LIBERO, LIBERO-PRO и LIBERO-Safety;
3. отделить generative noise от изменения предсказания после нового
   наблюдения;
4. объединить overlap consistency с `value`, latent uncertainty и
   action-conditioned future signals;
5. проверить не только failure detection, но и causal улучшение planning.

## 1. Формальная постановка

Пусть query $q$ выполняется в simulator step $t_q$. Для stochastic sample
$i$ политика возвращает chunk

$$
A_q^{(i)}=
\left[
a_{t_q\mid q}^{(i)},
a_{t_q+1\mid q}^{(i)},
\ldots,
a_{t_q+H-1\mid q}^{(i)}
\right]
\in\mathbb R^{H\times D},
$$

где для LIBERO $H=16$, $D=7$. После исполнения первых $K$ действий
следующий query происходит в $t_{q+1}=t_q+K$. Длина overlap равна

$$
L=H-K.
$$

Старый прогноз и новый прогноз для общей части горизонта:

$$
X_q^{(i)}=A_q^{(i)}[K:H],
\qquad
Y_{q+1}^{(j)}=A_{q+1}^{(j)}[0:L].
$$

При $H=16$, $K=8$ обе матрицы имеют форму $8\times7$ и описывают
действия для абсолютных шагов $t_q+8,\ldots,t_q+15$. Это временное
выравнивание является обязательным. Сравнивать `A_q[0:8]` и
`A_{q+1}[0:8]` нельзя: они относятся к разным моментам времени.

### 1.1. Что именно измеряет disagreement

Большое расхождение может означать несколько разных явлений:

- реальная динамика после первых $K$ действий разошлась с ожидаемой;
- свежая камера обнаружила slip, missed grasp, contact loss или смещение
  объекта;
- соседние stochastic queries выбрали разные допустимые action modes;
- policy исправляет старый ошибочный план;
- генеративный noise велик даже при неизменном observation.

Поэтому disagreement является сигналом **revision/surprise**, но не готовой
вероятностью failure. Низкое расхождение также не гарантирует успех: модель
может быть последовательно и уверенно неправа. Для no-progress, wrong-object и
timeout failures нужен дополнительный progress/outcome monitor.

## 2. Проверяемые гипотезы

**H1. Local precursor.** Overlap disagreement перед первым физическим событием
`drop`, `missed grasp`, `contact loss`, `collision` или `wrong placement`
выше, чем в matched success queries той же фазы.

**H2. Distribution beats one sample.** Расстояние между распределениями
overlap chunks лучше переносится между cases, чем L2 одного selected old/new
chunk.

**H3. Observation revision beats sampling noise.** При одинаковых diffusion
seeds между соседними query disagreement лучше предсказывает failure, чем при
независимых seeds, потому что common random numbers подавляют чистый
generative noise.

**H4. Failure-mode specificity.** Action overlap лучше обнаруживает erratic
failures, но хуже no-progress/timeout. Временно выровненные future-state и
progress signals должны дополнять, а не заменять его.

**H5. Complementarity.** Добавление overlap features к лучшим текущим
`value`, internal-copy и action disagreement metrics повышает held-out AUPRC,
calibration и lead time.

**H6. Causal utility.** Frozen overlap alarm улучшает paired closed-loop
success или снижает safety-event rate, если по alarm сокращать execution
horizon либо выбирать поддержанный старым plan candidate. Простое сильное
притягивание к старому хвосту может ухудшить результат, сохраняя уже ошибочный
план.

**H7. Temporal supervision.** Phase-conditioned sequential detector по
overlap и action latent features лучше global threshold, если обучать его на
trajectory-level success/fail, но этот supervised результат не переносится на
zero-shot claim и должен публиковаться отдельно от TIDE/STAC.

## 3. Метрики

### 3.1. Selected-to-selected normalized RMSE

Для выбранных planner-ом chunks вводится масштабированное расстояние

$$
D_{\mathrm{sel},q}=
\sqrt{
\frac{
\sum_{\ell=0}^{L-1}w_\ell
\sum_{d=1}^{D_c}
\left(
\frac{X_{q,\ell d}^{(i_q)}-Y_{q+1,\ell d}^{(i_{q+1})}}{s_d}
\right)^2
}{D_c\sum_{\ell=0}^{L-1}w_\ell}
},
$$

где $D_c$ содержит непрерывные action dimensions, $s_d$ является robust
scale из successful calibration episodes, а

$$
w_\ell=\exp(-\beta\ell)
$$

даёт больший вес ближайшим действиям. Translation, rotation и gripper
сохраняются также как отдельные компоненты. Для дискретного gripper считается
не L2, а доля несовпадающих команд.

Обязательные варианты:

- `overlap_rmse_uniform` с $\beta=0$;
- `overlap_rmse_front` с $\beta>0$;
- `overlap_first_l2` только для ближайшего общего шага;
- `overlap_xyz_rmse`, `overlap_rot_rmse`, `overlap_gripper_mismatch`;
- cosine distance и direction reversal rate.

### 3.2. Сохранён ли старый plan в новом candidate set

Selected-to-selected score смешивает изменение policy support и новый выбор
planner-а. Поэтому отдельно считаются

$$
D_{\mathrm{support},q}
=\min_j d\left(X_q^{(i_q)},Y_{q+1}^{(j)}\right),
$$

$$
D_{\mathrm{switch},q}
=D_{\mathrm{sel},q}-D_{\mathrm{support},q}.
$$

- высокий `support` означает, что старое продолжение исчезло даже из нового
  sampled support;
- низкий `support`, но высокий `switch` означает, что подходящий mode остался,
  однако planner переключился на другой candidate.

Для двух полных candidate sets используется symmetric Chamfer distance:

$$
D_{\mathrm{set},q}=
\frac{1}{2B}\left[
\sum_i\min_j d(X_q^{(i)},Y_{q+1}^{(j)})+
\sum_j\min_i d(Y_{q+1}^{(j)},X_q^{(i)})
\right].
$$

Есть важная causal оговорка. Реальное состояние в $q+1$ возникло после prefix
только выбранного candidate $i_q$. Старые samples $i\ne i_q$ могли иметь
другие prefixes и описывают контрфактические transitions. Поэтому
`selected-old-tail -> new-set support` является primary selection-aware
метрикой, а full-set STAC ниже - обязательным published baseline, но не
единственной интерпретацией.

При достаточном $B$ проверяется prefix-conditioned old distribution:

$$
\omega_i=
\frac{
\exp\left[-d^2\left(A_q^{(i)}[0:K],A_q^{(i_q)}[0:K]\right)/\tau\right]
}{
\sum_r
\exp\left[-d^2\left(A_q^{(r)}[0:K],A_q^{(i_q)}[0:K]\right)/\tau\right]
}.
$$

Weighted MMD использует веса $\omega_i$ для old tails. Если при $B=4$ почти
весь вес получает selected sample, этот estimator не выдаётся за
distributional и сводится к support/selected comparison.

### 3.3. STAC: расстояние между распределениями

При $B$ stochastic samples на каждом query строятся эмпирические
распределения старых tails и новых prefixes. Основной published baseline -
MMD с RBF kernel:

$$
k(x,y)=\exp\left(-\frac{\|x-y\|_2^2}{\gamma}\right),
$$

$$
\widehat{\mathrm{MMD}}^2_q=
\frac{1}{B(B-1)}\sum_{i\ne j}k(X_i,X_j)
+\frac{1}{B(B-1)}\sum_{i\ne j}k(Y_i,Y_j)
-\frac{2}{B^2}\sum_{i,j}k(X_i,Y_j).
$$

Перед kernel каждое continuous action dimension нормируется по successful ID
calibration data. Bandwidth $\gamma$ выбирается median heuristic только на
train/calibration split и затем замораживается.

Sentinel использовал также forward/reverse KL через KDE. Для Cosmos это
дорогой baseline: в высоком измерении и при текущих $B=4$ KDE нестабилен.
Поэтому первый sweep сравнивает:

- selected RMSE;
- support и symmetric Chamfer;
- MMD;
- energy distance;
- diagonal studentized mean shift.

Последний score:

$$
D_{\mathrm{shift},q}=
\frac{\|\mu_X-\mu_Y\|_2}
{\sqrt{\operatorname{tr}(\Sigma_X)+
\operatorname{tr}(\Sigma_Y)+\epsilon}}.
$$

Полную covariance при $B\ll LD$ инвертировать нельзя.

### 3.4. Coupled и independent sampling

Нужно собирать два режима:

1. `independent`: обычные независимые stochastic seeds на соседних query;
2. `coupled`: sample $i$ на обоих query использует одинаковый generative
   seed/noise schedule.

В coupled режиме

$$
D_{\mathrm{coupled},q}=
\frac1B\sum_{i=1}^{B}d(X_q^{(i)},Y_{q+1}^{(i)}).
$$

Для causal interpretation отдельно публикуется coupled distance выбранного
old sample и prefix-conditioned subset. Усреднение всех paired indices остаётся
diagnostic measure: common seed не делает неисполненные old prefixes
фактическими transitions.

Контрольный experiment повторно вызывает модель на **том же observation**:
разность при одинаковом seed должна быть близка к численной
невоспроизводимости, а при разных seeds оценивает чистый sampling floor.

### 3.5. Агрегация по времени

Сначала оценивается instantaneous $D_q$. Затем сравниваются:

- rolling mean/max за 2-3 query;
- EWMA;
- raw cumulative STAC score $\eta_q=\sum_{r\le q}D_r$;
- phase-calibrated CUSUM.

Для CUSUM параметры nominal distribution оцениваются отдельно по task phase:

$$
z_q=\frac{D_q-\operatorname{median}_{\mathrm{ID,phase}}(D)}
{1.4826\operatorname{MAD}_{\mathrm{ID,phase}}(D)+\epsilon},
$$

$$
C_q=\max(0,C_{q-1}+z_q-\kappa).
$$

Raw cumulative score зависит от длины эпизода, поэтому не должен быть
единственным detector-ом.

## 4. Как добавить image, proprio и value без временной ошибки

### 4.1. Почему нельзя просто сравнить соседние future predictions

В текущем collector `future_image`, `future_wrist_image` и future proprio
являются endpoint prediction для chunk. При стандартном forward:

$$
F_q \text{ относится к } t_q+16,
\qquad
F_{q+1} \text{ относится к } t_q+24.
$$

Их непосредственная разность смешивает uncertainty с обычным развитием сцены.
То же ограничение относится к value: соседние value оценивают разные
conditioned futures и разные task phases.

### 4.2. Честные варианты

1. **Prediction versus reality.** Старый endpoint $F_q(t_q+16)$ сравнить с
   реальным observation после ещё восьми действий. Это сильный post-hoc target,
   но он становится доступен только в $t_q+16$.
2. **Fixed absolute endpoint.** В $q+1$ предсказать оставшиеся восемь шагов
   до $t_q+16$, зафиксировав aligned action tail. Тогда можно сравнить две
   оценки одного будущего момента.
3. **Temporal latent sequence.** Если forward будет возвращать промежуточные
   video/state latents, сопоставлять только одинаковые absolute timestamps.
4. **Revision after reality.** Prediction error предыдущего prefix уже известен
   на $q+1$ и может быть causal feature для решения о следующем chunk.

До реализации пунктов 2-3 primary experiment использует только action overlap.
Наивная разность соседних endpoint images/proprio/value не включается в
confirmatory score.

## 5. Что уже сделано в литературе

| Работа | Совпадение с гипотезой | Главное отличие от нашей проверки |
|---|---|---|
| [Sentinel / STAC, CoRL 2024](https://proceedings.mlr.press/v270/agia25a.html) | Практически точное: сравнивает распределения temporally overlapping action chunks; для PushT использует $H=16,K=8$ | Detects erratic failures, но не проверяет Cosmos, LIBERO-PRO, joint world-model outputs и causal planning improvement |
| [Rewind-IL / TIDE, 2026](https://arxiv.org/html/2604.16683) | Почти точная scalar-версия: MSE между выровненными overlapping chunks, split-conformal threshold и recovery | Проверен на ACT/flow matching, RoboCasa и real robot; не проверяет Cosmos/LIBERO-PRO и distributional best-of-$N$ selection |
| [BID, ICLR 2025](https://arxiv.org/abs/2408.17355) | Взвешенный L2 между новым chunk и прошлым overlapping decision | Использует consistency для candidate selection, а не как calibrated fail predictor |
| [ACT, RSS 2023](https://roboticsproceedings.org/rss19/p016.html) | Temporal ensembling объединяет несколько прогнозов одного physical action | Усреднение сглаживает траекторию, но не отделяет incompatible modes и не выдаёт risk score |
| [SEAM, 2026](https://arxiv.org/abs/2607.04609) | Ровно использует unexecuted old tail как prior для нового flow chunk | Оптимизирует smoothness; standard LIBERO-10, а не OOD failure prediction |
| [VLA-Corrector, 2026](https://arxiv.org/abs/2607.01804) | Сравнивает predicted и actual visual latent dynamics, затем сокращает horizon | Нужен отдельный learned 40M corrector; это dynamics mismatch, а не cross-query action distribution distance |
| [Hide-and-Seek, 2026](https://arxiv.org/html/2605.30834) | Учит последовательный fail score по frozen VLA action embeddings и сравнивается со STAC | Нужны success/fail trajectory labels; это learned complement к overlap, а не training-free metric |
| [AutoIntervene, 2026](https://arxiv.org/html/2608.07065) | Сравнивает proposed prefix с phase-local visual-action support и калибрует intervention | Нужны reference memory и оператор; полезен как support/intervention baseline, но не self-consistency test |
| [Diffusion Policy, RSS 2023](https://diffusion-policy.cs.columbia.edu/) | Базовая receding-horizon схема: предсказать sequence, выполнить prefix, replan | Не использует overlap disagreement как uncertainty |
| [RTC, NeurIPS 2025](https://arxiv.org/abs/2506.07339) | Inpainting обеспечивает continuation между chunks | Решает asynchronous latency и continuity, не failure detection |
| [REMAC, 2026](https://arxiv.org/abs/2601.20130), [Legato, 2026](https://arxiv.org/abs/2602.12978), [FutureRTC, 2026](https://arxiv.org/abs/2607.24008) | Учат или прогнозируют continuation, state и observation при chunk transitions | Сосредоточены на real-time execution и smoothness; полезны как будущие correction baselines |

### 5.1. Sentinel/STAC: прямой аналог

Sentinel формулирует старые tails и новые prefixes как два распределения и
измеряет MMD либо forward/reverse KL. Per-query distances суммируются, а alarm
threshold калибруется по successful trajectories. В simulation авторы
используют 50 successful calibration rollouts и 95-й percentile threshold;
для multimodal PushT берут 256 samples, для менее multimodal задач - 32.

Сильные стороны для нашего протокола:

- правильное absolute-time alignment;
- distributional comparison сохраняет multimodality;
- threshold не требует failed calibration data;
- оцениваются TPR, TNR и detection time.

Ограничения:

- сама статья подчёркивает detection failures as they occur, а не гарантирует
  предсказание до события;
- STAC плохо ловит temporally consistent no-progress failures, поэтому Sentinel
  добавляет отдельный video progress monitor;
- $B=32\ldots256$ слишком дорого для полного Cosmos rollout;
- эксперименты не проводились на LIBERO.

Следовательно, наша первая цель - не объявлять новую метрику, а проверить
**sample-efficient STAC for Cosmos** при $B=4,8,16$, с локальными event labels
и положительным lead time.

### 5.2. BID и SEAM: consistency уже используется для управления

BID выбирает candidate по backward coherence

$$
\mathcal L_B=
\sum_{\ell=0}^{L-1}\rho^\ell
\left\|Y_{q+1,\ell}-X_{q,\ell}\right\|_2.
$$

Это почти наш `overlap_rmse_front`, но в BID score минимизируется во время
decoding. Авторы отдельно отмечают опасность: старый prior может быть
субоптимален после неожиданного движения объекта. Поэтому большой disagreement
нельзя автоматически исправлять жёстким возвратом к old tail.

SEAM переносит тот же принцип внутрь flow denoising. На LIBERO-10 с
π₀.₅ авторы сообщают снижение boundary jerk на 28% и chunk transition
discontinuity на 27% при сохранении success около baseline. При слишком сильном
guidance success падает. Это ещё один аргумент сначала использовать overlap как
monitor/gate, а hard consistency проверять отдельной ablation.

### 5.3. VLA-Corrector: ближайшая идея для image/state

VLA-Corrector обучает external latent dynamics model и сравнивает ожидаемое и
реальное изменение visual features:

$$
E_t=1-\operatorname{CosSim}
\left(\Delta Z_{t+k}^{\mathrm{expected}},
\Delta Z_{t+k}^{\mathrm{real}}\right).
$$

Persistent anomaly вызывает досрочное прерывание stale chunk и corrective
replanning. Это подтверждает направление `predicted future versus reality`, но
не заменяет action overlap: первое измеряет ошибку dynamics после исполнения,
второе доступно на границе до исполнения следующего overlap prefix.

### 5.4. Rewind-IL/TIDE: почти точная scalar-формулировка

Rewind-IL называет этот сигнал Temporal Inter-chunk Discrepancy Estimate:

$$
\operatorname{TIDE}_q=
\frac{1}{BDL}
\sum_{b=1}^{B}\sum_{d=1}^{D}\sum_{\ell=0}^{L-1}
\left(
\widehat A_{q,\ell,d}^{(b)}-
\widetilde A_{q+1,\ell,d}^{(b)}
\right)^2.
$$

Здесь $\widehat A_q$ - оставшийся согласованный plan из прошлого query,
$\widetilde A_{q+1}$ - новый aligned prefix. Alarm возникает при
$\operatorname{TIDE}_q>\hat q$, где $\hat q$ - conformal quantile на
успешных calibration trajectories. В статье используется $\alpha=0.001$.
Авторы сообщают average balanced accuracy 0.95 на шести ACT-задачах и 0.99
на трёх flow-matching задачах; в RoboCasa recovery повышает success с
55-60% до 70-80% на трёх задачах.

Это ещё сильнее сужает claim новизны. `selected_overlap_rmse` или MSE надо
называть **TIDE-style baseline**, а не новым методом. Отличимые вопросы для
нас: работает ли сигнал при редком $B=4$ sampling Cosmos, даёт ли warning
до физического event, переносится ли между LIBERO-PRO factors и помогает ли
выбирать candidate, а не только останавливать/восстанавливать execution.

### 5.5. Hide-and-Seek: learned baseline с trajectory-level labels

Hide-and-Seek обучает лёгкий LSTM на frozen action embeddings. Для trajectory
prefix $\tau_{\le t}=(h_1,\ldots,h_t)$ модель выдаёт
$s_t=f_\phi(\tau_{\le t})$. Inter-trajectory loss требует, чтобы максимальный
score failed trajectory был выше самого подозрительного шага successful
trajectory; intra-trajectory loss усиливает разрыв до и после автоматически
найденного onset. Нужны только episode-level success/fail labels.

Работа проверена на standard LIBERO-10 с OpenVLA и $\pi_0$, на VLABench с
$\pi_{0.5}$ и на real robot. На LIBERO использовано 500 episodes на policy,
held-out task split и три training seeds. Среди двенадцати baselines есть STAC
с десятью samples на step. Авторы сообщают для OpenVLA bACC 0.852/0.834 на
seen/unseen tasks против 0.665/0.624 у STAC. Это не доказывает превосходство
для Cosmos, но показывает, что чистый overlap не должен быть единственным
baseline.

Для threshold полезна их functional conformal calibration:

$$
\zeta_t=\mu_t+h\,\sigma(t),
$$

то есть допустимый score меняется по фазе эпизода. Это особенно важно для
grasp/release boundaries, где normal overlap revision естественно выше. В
нашем confirmatory test сравниваются scalar split-CP threshold, phase/query
conditioned threshold и learned sequential detector. Hide-and-Seek требует
failed training trajectories и поэтому не заменяет training-free TIDE/STAC,
а задаёт supervised upper baseline.

### 5.6. AutoIntervene: от alarm к поддержке решения

AutoIntervene проверяет proposed action prefix вместе с visual embedding
против phase-local memory успешных trajectories. Отдельные calibrated
thresholds управляют передачей контроля оператору и возвратом policy. Для
нашего simulator-only этапа оператор не нужен, но полезны две идеи:

1. сравнивать action только с reference support той же task phase;
2. требовать persistent alarm в нескольких query, чтобы единичный mode switch
   не вызывал ложное вмешательство.

Это мотивирует phase-aware normalization и persistence ablation, а позднее -
варианты `shorten horizon`, `resample candidates` и `abstain/recovery` вместо
безусловного штрафа за любое изменение plan.

## 6. План экспериментов

### E0. Integrity и noise floor

1. Сохранить полные $B\times16\times7$ action chunks, а не только первые
   actions.
2. На одном observation повторить query с теми же seeds: tensors и metrics
   должны воспроизводиться в пределах tolerance.
3. Повторить с независимыми seeds и оценить pure sampling floor.
4. Unit-test absolute alignment на синтетических chunks с известными индексами.
5. Проверить, что CSV/NPZ round-trip не меняет selected candidate и metrics.

### E1. Passive pilot без изменения поведения

- $H=16,K=8,B=4$, текущий `max_value` либо frozen current planner;
- не менее 6 mixed-outcome LIBERO-PRO cases по 20 rollout seeds;
- standard LIBERO successes для false-alarm calibration;
- записывать score до исполнения нового prefix;
- не использовать overlap score для выбора action.

Цель pilot: проверить масштаб, event alignment, долю positive query labels и
выбрать 2-3 distance functions. Pilot не используется для итогового вывода.

### E2. Sample-count и horizon ablation на сохранённых contexts

На фиксированном наборе query contexts:

| Фактор | Значения |
|---|---|
| Samples $B$ | 1, 4, 8, 16; 32 только на небольшом subset |
| Execution $K$ при $H=16$ | 4, 8, 12 |
| Noise pairing | independent, coupled |
| Distance | RMSE, support, Chamfer, MMD, energy, shift |
| Old-set conditioning | full STAC, selected-only, prefix-weighted STAC |
| Dimensions | xyz, rotation, continuous all, gripper separately |
| Temporal aggregation | instantaneous, max-3, EWMA, cumulative, CUSUM |
| Calibration | global split CP, query/phase-conditioned CP |

Compute сравнивается при одинаковом числе policy forwards. Нельзя приписывать
выигрыш MMD методу, если он просто получил в 64 раза больше samples.

### E3. Frozen confirmatory detection

Минимальный confirmatory target:

- не менее 12 cases из как минимум трёх LIBERO-PRO factor families;
- около 40 paired rollout seeds на case;
- split по **целым cases/tasks**, а не по query rows;
- отдельный held-out OOD family test;
- standard LIBERO используется только для ID false alarms;
- LIBERO-Safety оценивается отдельно по official event labels.

Основной локальный label в момент вычисления $D_q$:

$$
Y_q^{(R)}=
\mathbb 1\{\text{первое critical event произойдёт в следующие }R
\text{ simulator steps}\},
$$

где $R\in\{8,16,32\}$. Query после первого необратимого event исключаются из
задачи early warning. Terminal episode fail является secondary label, потому
что timeout может не совпадать с моментом физической ошибки.

Primary metrics:

- query-level AUPRC;
- AUROC как secondary metric;
- TPR при frozen FPR 5% на ID/success calibration;
- median lead time до первого event;
- Brier score и calibration curve;
- event-specific AUPRC;
- cluster bootstrap CI по episodes/cases.

Сравниваются training-free и learned baselines:

1. current uncertainty/value metrics;
2. deterministic TIDE-style selected overlap MSE;
3. distributional STAC MMD;
4. selected support/Chamfer/energy и prefix-weighted STAC;
5. current + лучшие frozen overlap features;
6. current + overlap + causal previous-chunk prediction error;
7. learned sequential detector по action/latent embeddings в стиле
   Hide-and-Seek;
8. Oracle post-hoc features только как upper bound.

Простой комбинированный detector обучается только после univariate ablation:

$$
P(Y_q^{(R)}=1)=
\sigma\left(
b+\beta_1 z(D_{\mathrm{MMD},q})
+\beta_2 z(D_{\mathrm{support},q})
+\beta_3 z(U_{\mathrm{action},q})
+\beta_4 z(U_{\mathrm{value},q})
+\beta_5 z(E_{q-1}^{\mathrm{proprio}})
\right).
$$

Regularization и threshold выбираются только на train/validation cases.

### E4. Causal planning intervention

После frozen detection test выполняется paired closed-loop comparison:

| Strategy | Selection | Horizon rule |
|---|---|---|
| `maxV_h8` | max value | всегда 8 |
| `overlap_rank_h8` | value минус weak overlap penalty | всегда 8 |
| `overlap_alarm_h4` | max value | 4 при alarm, иначе 8 |
| `overlap_combined` | risk-aware candidate при alarm | 4 при alarm, иначе 8 |
| `old_tail_commit` | продолжить old tail | diagnostic ablation, не основной метод |

Candidate score для мягкого варианта:

$$
S_i=z(V_i)-\lambda_u z(U_i)
-\lambda_o z\left[d\left(X_q^{(i_q)},Y_{q+1}^{(i)}\right)\right].
$$

`old_tail_commit` нужен, чтобы проверить причинный смысл disagreement. Он может
ухудшать результат, если новый query правильно исправляет старый plan.

Adaptive horizon меняет геометрию следующего overlap: при $K=4$ длина
$L=12$, а не 8. Поэтому каждая строка хранит фактический $K$; detector либо
сравнивает фиксированное ближайшее окно
$M=\min(8,H-K)$, либо использует отдельную calibration для каждого
$(K,L)$. Threshold, обученный только на $K=8$, нельзя молча применять к
$K=4$ scores.

Primary endpoint - paired task success. Secondary endpoints: official safety
events, drop/contact loss, timeout, число policy queries, wall-clock latency,
success per query и failure-mode shift. Candidate pool, init state и rollout
seed должны быть matched между strategies.

## 7. Изменения collector-а

Текущий `uncertainty_comparison.py` сохраняет
`candidate_first_actions_json`, но не полный selected/candidate chunk. Поэтому
старые кампании нельзя честно доанализировать для STAC.

Для новых runs нужен episode-level NPZ/Zarr sidecar:

```text
candidate_actions_raw        [Q, B, 16, 7]
candidate_actions_normalized [Q, B, 16, 7]
candidate_values             [Q, B]
candidate_seeds              [Q, B]
selected_sample_idx          [Q]
query_t                      [Q]
executed_steps               [Q]
actual_executed_actions      [T, 7]
future_proprio               [Q, B, ...]
future_image_paths           [Q, B, camera]
action_latent_embeddings     [Q, B, tokens, hidden]  # optional sidecar
event_timestamps             structured table
```

CSV остаётся компактным индексом и содержит уже рассчитанные scalar metrics.
Большие tensors нельзя сериализовать в JSON внутри каждой строки.

Минимальные новые scalar columns:

```text
overlap_valid
overlap_length
overlap_selected_rmse
overlap_support_min
overlap_switch_gap
overlap_set_chamfer
overlap_mmd
overlap_coupled_mean
overlap_xyz_rmse
overlap_rot_rmse
overlap_gripper_mismatch
overlap_cusum
steps_to_first_event
```

Текущую запущенную campaign менять нельзя. Collector обновляется только для
следующего run после завершения P0.

## 8. Критерии решения

**Detection go:** overlap features дают положительный lead time и улучшают
held-out AUPRC/TPR@5%FPR относительно лучших текущих online features без
регрессии false alarms на standard LIBERO.

**Planning go:** frozen overlap strategy имеет положительный paired success
delta или снижает official safety events при сопоставимой query cost; CI и
per-case regressions показываются обязательно.

**Partial result:** сигнал работает только для drops/contact failures. Тогда он
остаётся специализированным erratic-failure detector и объединяется с progress
monitor, а не объявляется универсальным fail predictor.

**No-go:** disagreement не переносится между cases, исчезает при coupled noise
или возникает уже после event. В этом случае его можно использовать для
smoothness/diagnostics, но не для anticipatory planning.

## 9. Ожидаемый научный вклад

Само сравнение overlap chunks уже существует в STAC, TIDE, BID и SEAM.
Потенциально новый результат нашего проекта формулируется уже:

> Sample-efficient, world-model-aware temporal consistency for flow-based VLA
> planning under LIBERO OOD and safety shifts.

Сильный вклад потребует показать одновременно:

1. prediction до локального event, а не только detection после него;
2. перенос threshold на held-out tasks/OOD families;
3. дополнительную пользу относительно обычной stochastic uncertainty;
4. causal улучшение action selection или adaptive feedback horizon;
5. отдельное объяснение erratic и no-progress failure modes.

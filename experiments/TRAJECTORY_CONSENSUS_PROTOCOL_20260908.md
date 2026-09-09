# P4c2: trajectory-density consensus for Cosmos Policy

Дата: 8 сентября 2026. Статус: новая экспериментальная проверка, эффективность не установлена.

## Задача и основание

Выбрать один из native action chunks Cosmos Policy без обучения и дополнительных
world-model forwards. Проверяем, помогает ли согласованность **траекторий**, а не
только отдельных координат действий, избежать ошибочного максимума value.

Предыдущий P4c не подтвердил преимущество consensus: pure medoid 7/40 против
max-value 8/40; guarded K5 6/20 против 5/20, но 3 rescue / 2 harm и широкий CI.
Это не положительный benchmark-результат. По новому запросу запускаем более
широкую архитектурно согласованную проверку перед P5, сохраняя старый NO-GO.
[Исходные результаты](CONSENSUS_MEDOID_PRE_P5_RESULTS_20260907.md).

Источники: [KeyStone](https://arxiv.org/abs/2605.08638),
[KDPE](https://arxiv.org/abs/2508.10511),
[A3](https://arxiv.org/abs/2605.11567),
[AAC](https://arxiv.org/abs/2604.04161),
[TACO](https://arxiv.org/abs/2512.02834).
Что именно заимствовано, а что не реализовано, разобрано в
[общем обзоре статей, раздел 10](../articles/LIBERO_EXPERIMENTS_AND_PAPERS.md#10-trajectory-consensus-и-density-selection-8-сентября-2026).

## Модель и управление

Checkpoint: `nvidia/Cosmos-Policy-LIBERO-Predict2-2B`.
На каждом query модель получает реальные RGB двух камер, proprio и instruction.
Независимые diffusion seeds дают K=4 native samples
$(A_i,\hat s_i',\hat V_i)$; K=1 используется для non-planning control.
Здесь применяется **parallel joint prediction**, а не дополнительная цепочка
$a\to s'\to v$. Это наш зафиксированный max-value baseline, не заявление о
точном воспроизведении всех настроек planning из оригинальной статьи Cosmos.

Генерируются 16 действий, выполняются 16 либо до terminal/лимита. Во всех
стратегиях одинаковые H16, 5 diffusion steps и лимит 280 low-level steps.
Предыдущий P4c выполнял H5 и использовал K3/K5: его проценты нельзя напрямую
сравнивать с новой кампанией. Поэтому все baseline здесь считаются заново.
Warm-up из 10 dummy steps не входит в 280 и в видео. Предсказание будущего
состояния сравниваем с реальностью **только при выполненных 16 действиях**;
прерванные success/final chunks исключены из prediction-error анализа.

## Формулы

Пусть $a_{i,t}=(u^p_{i,t},u^r_{i,t},u^g_{i,t})\in[-1,1]^7$.
Для проверенных параметров LIBERO OSC controller строим descriptors:

$$
p_{i,t}=\sum_{k=1}^{t}0.05u^p_{i,k},\qquad
R_{i,t}=\operatorname{Exp}(0.5u^r_{i,t})R_{i,t-1},\quad R_{i,0}=I,
\qquad g_{i,t}=\operatorname{sign}_{+}(u^g_{i,t}).
$$

Здесь $\operatorname{sign}_{+}(0)=1$. Команды предварительно clipping-уются в
диапазон controller. Это **кинематические descriptors**, не rollout физики:
контакт, tracking error и падение предмета таким интегрированием не предсказываются.
Перед запуском проверяем реальные input/output scales и delta-mode controller.

$$
d_{ij}(t,s)=\frac{\|p_{i,t}-p_{j,s}\|_2}{0.05}
+0.5\frac{\theta(R_{i,t}R_{j,s}^{\top})}{0.5}
+0.25\mathbb 1[g_{i,t}\ne g_{j,s}],
\qquad \theta(R)=\arccos\frac{\operatorname{tr}(R)-1}{2}.
$$

Агрегируем весь выполняемый горизонт, немного усиливая ближайшие действия:

$$
w_t=\frac{0.95^{t-1}}{\sum_{k=1}^{16}0.95^{k-1}},\qquad
D_{ij}=\frac12\sum_{t=1}^{16}w_t
\left[\min_{|s-t|\le b}d_{ij}(t,s)+\min_{|s-t|\le b}d_{ij}(s,t)\right].
$$

$b=0$ сравнивает одинаковое время, $b=1$ допускает локальный сдвиг на один шаг.
Это ablation геометрии, не полноценный conditional re-decoding / verifier A3.

$$
h=\max(\operatorname{median}_{i<j}D_{ij},10^{-6}),\qquad
\rho_i=\frac1{K-1}\sum_{j\ne i}\exp\left(-\frac{D_{ij}^2}{2h^2}\right),
$$

$$
z_i^V=\frac{\hat V_i-\operatorname{median}(\hat V)}{\max(\operatorname{IQR}(\hat V),10^{-4})},
\qquad S_i=z_i^V+\lambda\log\max(\rho_i,10^{-12}).
$$

$\rho_i$ измеряет относительную поддержку кандидата текущими samples. Это не
дисперсия, не calibrated epistemic uncertainty и не вероятность успеха.
Выбираем **существующий sample**, а не среднее нескольких движений.

Пусть $m=\arg\max_i\hat V_i$, $j=\arg\max_i S_i$. Guard:

$$
i^*=\begin{cases}
j,&\displaystyle\frac{\hat V_m-\hat V_j}{\max(\operatorname{IQR}(\hat V),10^{-4})}\le\delta_V
\quad\land\quad\log\rho_j-\log\rho_m\ge\delta_\rho,\\
m,&\text{иначе}.
\end{cases}
$$

Равные scores разрешаются по большему value, затем индексу. Pure medoid
использует $\arg\min_i\sum_jD_{ij}$; pure density использует
$\arg\max_i\rho_i$, без guard. Pure-версии нужны для ablation.

## Последовательность экспериментов

| Этап | Варианты | Данные | Объём |
|---|---|---|---:|
| Offline, завершён | 2 pure + 2 geometry x 5 lambda x 3 value margins | ранее открытые P4b terminal pools; только exact replay | 194 K4 состояния, 32 настройки |
| Smoke | K1, max-value, old guarded, physical medoid, physical density, 2 finalists | Object task0/init0 | 7 rollout |
| Development | те же 7 | Object/Environment: 10 задач x init0-1; Position: x/y 0.2/0.3 x tasks0,2,5,9 x init0 | 392 rollout |
| Full, после freeze | K1, max-value K4, один выбранный метод K4 | 10 задач во всех трёх факторах | 4500 rollout |

Full на каждый метод:

| Perturbation | Suite | Задачи | Inits | Rollout |
|---|---|---:|---|---:|
| Object | `libero_object_object` | 0-9 | 0-49 | 500 |
| Environment | `libero_object_env`, изолированная материализация | 0-9 | 0-49 | 500 |
| Position | `libero_object_temp`, x/y 0.1,0.2,0.3,0.4,0.5 | 0-9 на каждом уровне | 0-4 | 500 |

Environment создаётся в `.runtime/trajectory_consensus_20260908_environment`,
50 init, seed 20260908, вариант `living_room_table` из PRO perturbator.
Это полный task/init прогон выбранного Environment-варианта, не перебор
всех вообразимых фонов. Другие кампании не должны менять этот каталог.
Development и full используют различные новые rollout seeds. Все методы
получают одинаковые task/init/seed в пределах этапа. Автоматический анализ
также проверяет точное q0 simulator state соответствующих эпизодов.

Это **prospective new-seed benchmark**, а не полностью unseen-init набор:
некоторые init использованы в development. Дополнительно публикуется subset,
не использованный в текущем development: Object/Environment init2-49,
Position init1-4, всего 1360 эпизодов на метод. Он не объявляется untouched
относительно всей истории проекта. Разные процессы и разные состояния после
выбора действий не гарантируют одинаковых candidate pools; это deployment
comparison, а не exact counterfactual experiment на каждом query.

## Выбор параметров и защита теста

Offline: $\lambda\in\{0.25,0.5,1,2,4\}$,
$\delta_V\in\{0.25,0.5,1\}$, $\delta_\rho=0.1$, $b\in\{0,1\}$.
В каждом geometry family выбран лучший macro uplift минус положительный
macro drop-rate uplift. Оба finalist: lambda0.25, value margin0.25, gain0.1.

Development выбирает одну из новых trajectory-стратегий по
`macro_SR - max(0, macro_drop - baseline_macro_drop)`; tie-break: меньший drop,
затем стабильный порядок. В `winner.json` сохраняются выбранные параметры и
hash исходной таблицы. До full фиксируются SHA256 winner, config и исходников
runtime. После просмотра full outcomes параметры не подбираются.

Полный тест запускается по явному запросу даже при отрицательном development
результате. В этом случае он маркируется проверкой границ применимости, а не
подтверждением уже найденного выигрыша. Нулевой и отрицательный результат
публикуется наравне с положительным.

## Метрики и критерий полезности

Primary: paired delta SR выбранного метода против K4 max-value, macro по
Object/Environment/Position. Показываем также SR по каждой задаче/уровню,
rescue/harm, group bootstrap 95% CI (5000 resamples task/init внутри фактора).
Position levels одного task/init остаются в одном bootstrap cluster.
Интервал характеризует этот фиксированный набор задач, а не доказанный
перенос на неизвестные задачи.
McNemar приведён как дополнительная pooled диагностика, без претензии
на независимость всех коррелированных perturbation trials.

Практический критерий: положительный macro uplift, CI не пересекает ноль,
нет роста drop-proxy и нет скрытого ухудшения отдельного фактора. Публикуем
switch rate, число queries, длину эпизода и wall-clock затраты. K1 нужен
для оценки стоимости planning: это не compute-matched comparison с K4.

Drop tracker и другие physical-event признаки здесь являются **PRO proxies**.
Эта кампания не является официальным LIBERO-Safety benchmark. Timeout значит
невыполнение success predicate за 280 шагов, а не обязательно падение.
Старое поле `prediction_error_value_abs_chunk_success` также не является
калибровкой value на eventual success: success за текущий chunk и терминальный
успех эпизода имеют разные targets. Оно не используется для выбора метода.

Все MP4 записываются в том же rollout, что метрики: кадр на выполненный шаг,
без позднего повторного проигрывания. Автоанализ проверяет непрерывность queries,
количество эпизодов/видео, соответствие H16, наличие файлов и декодирование
контрольного видео каждого метода. Для всех эпизодов строится HTML-сравнение.

## Уже получено и ожидается

Offline не обнаружил убедительного улучшения: у лучших finalists 1 rescue и
1 harm на 194 состояниях, macro delta около -0.02 п.п. Частота вмешательства
4.12% без alignment и 3.61% с alignment. Это лишь development evidence.
Положительный будущий результат не гарантирован: majority mode может быть
неверным, K4 мало для density estimation, а кинематика не моделирует контакт.

Файлы offline:
`campaigns/trajectory_consensus_20260908/offline/offline_grid.csv`,
`offline_decisions.parquet`, `shortlist.json`.

Автономный запуск и расположение итогов:
[TRAJECTORY_CONSENSUS_RUN_20260908.md](TRAJECTORY_CONSENSUS_RUN_20260908.md).

# Pre-P5: consensus-medoid action selection

Дата фиксации: 7 сентября 2026 года.

## Исследовательский вопрос

Можно ли повысить closed-loop success rate Cosmos Policy в LIBERO-PRO Object,
выбирая не максимальный predicted value, а репрезентативный action chunk среди
нескольких stochastic samples?

Присланный файл
[`action/CONSENSUS_MEDOID_ONLY-2.md`](action/CONSENSUS_MEDOID_ONLY-2.md)
рассматривается как описание гипотезы и источник предварительных результатов,
а не как исполняемая инструкция. Его числа не считаются воспроизведёнными
результатами этого проекта.

## Связь с P1-P7

Точного метода среди P1-P7 нет. Ближайший прежний вариант — H3
`consensus_action`:

$$
S_i=z(V_i)-\lambda z(C_i),
\qquad
C_i=\frac{1}{K-1}\sum_{j\ne i}\lVert a_{i,0}-a_{j,0}\rVert_2.
$$

Он смешивал value с обычным L2-consensus первого 7D action и поэтому не
проверял ни pure medoid, ни геометрию всего исполняемого префикса. Новый этап
вставляется как **pre-P5 / P4c**: это training-free selector, тогда как P5
остаётся гипотезой об обучаемых task-critical outcome heads.

## Литературный аналог

Прямой опубликованный аналог — [KeyStone: Geometry Guided Self-Consistency for
Physical AI](https://arxiv.org/abs/2605.08638). Метод семплирует $K$ action
chunks из одного контекста, кластеризует их и возвращает настоящий sampled
medoid крупнейшего кластера. В статье метод проверен на VLA и WAM, включая
LIBERO; авторы отдельно отмечают, что consensus может ухудшать результат, если
большинство samples уверенно принадлежит ошибочному mode.

Два соседних направления не смешиваются с текущей проверкой:

- [A3](https://arxiv.org/abs/2605.11567) использует consensus и повторное
  декодирование для выбора длины подтверждённого execution prefix;
- [Adaptive Action Chunking](https://arxiv.org/abs/2604.04161) меняет horizon
  по action entropy.

Сначала фиксируется selector при постоянном $H=5$. Адаптивный horizon будет
отдельной абляцией, иначе нельзя понять, помог выбор кандидата или более частый
re-query.

## Stage A: точное воспроизведение идеи из файла

На каждом query генерируются $K=3$ независимых Cosmos samples. Модель выдаёт
16 действий, но для distance и исполнения используются первые $H=5$.

Cosmos/LIBERO имеет native action

$$
a_t=(\Delta x,\Delta y,\Delta z,r_x,r_y,r_z,g)\in\mathbb R^7,
$$

а не 10D action из присланного файла. Три компоненты $r$ являются axis-angle
командой. Поэтому 6D Gram-Schmidt из файла заменяется эквивалентным для native
представления преобразованием axis-angle $r\mapsto R(r)\in SO(3)$. Остальная
формула сохранена:

$$
d(a,b)=
\frac{\lVert\Delta p_a-\Delta p_b\rVert_2}{\sqrt3}
+0.5\frac{\arccos\!\left(\operatorname{clip}
\frac{\operatorname{tr}(R_aR_b^\top)-1}{2},-1,1\right)}{\pi}
+0.25\,\mathbf1[\operatorname{sign}(g_a)\ne\operatorname{sign}(g_b)].
$$

$$
D_{ij}=\frac{\sum_{t=0}^{4}0.9^t d(a^{(i)}_t,a^{(j)}_t)}
{\sum_{t=0}^{4}0.9^t},
\qquad
C_i=\frac{1}{K-1}\sum_{j\ne i}D_{ij},
\qquad
i^*=\arg\min_i C_i.
$$

Ни value, ни continuity, ни smoothness, ни gripper-switch regularizer в
`consensus_medoid_only` не используются.

### Контроли

| Метод | Candidates | Выбор | Execution horizon |
|---|---:|---|---:|
| `first` | 1 | единственный stochastic sample | 5 |
| `max_value` | 3 | $\arg\max_i V_i$ | 5 |
| `consensus_medoid_only` | 3 | $\arg\min_i C_i$ | 5 |

Все методы используют одинаковые suite/task/init/rollout seeds. Первый
development screen: `libero_object_object`, task 0, init states 0-39, один
rollout на init, максимум 280 simulator steps.

## Stage B: KeyStone и Cosmos-aware selector

### Published comparator

`keystone_cluster_medoid` реализует опубликованную схему: flatten полного
16-step chunk, L2 distance, global-medoid guard

$$
s=\frac{\lVert\bar x-x_m\rVert_2}
{\operatorname{median}_{i<j}\lVert x_i-x_j\rVert_2+\varepsilon},
$$

global medoid при $s<0.3$, иначе $C=2$ clusters и medoid крупнейшего cluster.

### Наша архитектурно-адаптированная версия

Cosmos в parallel mode совместно генерирует action chunk, future proprio и
value в одной latent diffusion sequence. Это не causal rollout
$a\rightarrow s'\rightarrow V$; три выхода являются совместным sample из
одного denoising pass. Поэтому future proprio и value используются только как
проверка межсемпловой согласованности, а не как доказанный verifier действия.

1. KeyStone guard находит dominant action mode $\mathcal M$.
2. Medoid costs действия $C_i^a$ считаются structured-метрикой Stage A.
3. Для joint outputs считаются

$$
C_i^p=\frac{1}{K-1}\sum_{j\ne i}\lVert\hat p'_i-\hat p'_j\rVert_2,
\qquad
C_i^v=\frac{1}{K-1}\sum_{j\ne i}|V_i-V_j|.
$$

4. Каждая модальность делится на robust within-query scale, после чего

$$
J_i=\frac{C_i^a}{s_a}
+0.25\frac{C_i^p}{s_p}
+0.10\frac{C_i^v}{s_v},
\qquad
r=\arg\min_{i\in\mathcal M}J_i.
$$

5. После отрицательного P4b результата применяется conservative switch gate.
Пусть $m=\arg\max_i V_i$. Тогда

$$
i^*=\begin{cases}
r,&V_m-V_r\le0.02,\quad
\dfrac{C_m^a-C_r^a}{s_a}\ge0.1,\quad J_m-J_r>0,\\
m,&\text{иначе}.
\end{cases}
$$

Таким образом, geometry предлагает альтернативу, а max-value остаётся
fallback. Это защищает от главного failure mode pure consensus: плотного, но
ошибочного большинства.

Stage B сравнивает при одинаковом $K=5$: `max_value`, опубликованный
`keystone_cluster_medoid` и `cosmos_consensus_guarded`. Значения $K$, value
margin и consensus margin являются development settings; перед confirmatory
holdout они должны быть заморожены.

## Метрики и статистические решения

Primary endpoint — бинарный LIBERO task success. Для каждой пары методов
сохраняются:

- paired SR delta на одинаковых task/init/rollout seeds;
- rescues и harms;
- exact McNemar p-value;
- init-cluster bootstrap 95% CI;
- mean query count и final simulator step;
- switch rate относительно `max_value`;
- drop/contact/safety diagnostics;
- action, future-proprio и value consensus по каждому query.

Stage A считается перспективным, если pure medoid имеет больше rescues, чем
harms относительно `first`, а paired CI не показывает крупного отрицательного
эффекта. Stage B не открывает новый confirmatory holdout, пока улучшенный
selector не превосходит `max_value` и pure KeyStone на development и не
увеличивает drop/safety signals.

## Ожидаемые исходы

1. Если неуспешные diffusion samples являются рассеянными выбросами, pure
   medoid должен повысить SR и уменьшить run-to-run variance.
2. Если dominant mode систематически ошибочен, pure medoid может не помочь или
   навредить; это согласуется с ограничением KeyStone.
3. Если Cosmos value полезен локально, conservative gate должен сохранить
   большую часть max-value решений и переключаться только при явном
   multimodal disagreement.
4. Если parallel future proprio не добавляет within-pool information, его вес
   следует обнулить в следующей preregistered ablation, а не подгонять по
   confirmatory outcomes.

## Артефакты

- реализация: `cosmos-policy/cosmos_policy/experiments/robot/libero/consensus_medoid.py`;
- runtime integration: `uncertainty_comparison.py`;
- campaign config:
  `configs/libero_campaign_consensus_medoid_pre_p5_20260907.json`;
- analysis: `scripts/analyze_consensus_medoid_campaign.py`;
- автономный запуск: `scripts/run_consensus_medoid_pre_p5_sequence.sh`.


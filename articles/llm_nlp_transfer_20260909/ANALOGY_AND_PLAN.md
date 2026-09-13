# Что переносить из LLM/NLP в Cosmos Policy

Дата: **9 сентября 2026 года**. Статус: анализ литературы и **предлагаемые**
эксперименты, не отчёт о новых робототехнических результатах.

**Обновление 10 сентября вечером:** [новые результаты и порядок проверок](../../experiments/RESEARCH_PRIORITIES_20260910_EVENING.md).
После отрицательного matched-K/continuity screen и неподтверждённого
neighboring P5 transfer приоритет переносится с большого verifier fit на
CRITIC-inspired physical probe/verify/repair. Это не полная реплика CRITIC,
semantic entropy или PAV; отдельная prover-policy PAV ещё не реализована.
Большой generator fine-tuning остаётся отложенным до качественных labels.

## 1. Краткий ответ

Для нашей задачи стоит искать не «самую сильную LLM», а решения четырёх
отдельных проблем: **качество предложений, выбор среди предложений,
получение внешнего feedback и исправление уже обнаруженной ошибки**.
Улучшение одной из них не гарантирует улучшения остальных.

Наиболее перспективный перенос, по нашему анализу:

| Приоритет | Направление | Что меняется у нас |
|---|---|---|
| 1 | Grounded process/outcome verification, PRM/PAV | Учим различать реальные исходы кандидатов одного состояния; добавляем признаки захвата, объекта и контакта |
| 2 | Tool-grounded correction, CRITIC / SCoRe / Solve-Detect-Verify | Реальное наблюдение запускает проверку и полезное восстановление, а не просто повторное семплирование |
| Контроль | MBR-BoN и structure-conditional MBR | Проверяем опубликованный аналог value + consensus на уже собранных pools; не выдаём его за новую формулу |
| 3 | Semantic uncertainty и entropy probes | Различаем гипотезы о физическом исходе; затем пробуем дешёвый probe вместо многократной генерации |
| Позже | Diffusion-DPO / DDPO / Flow-GRPO | Меняем сам генератор, если хороший action не появляется даже в candidate pool |

Это приоритеты **для нашей архитектуры и накопленных данных**, а не рейтинг
универсального SOTA. Показатели на математике, переводе и предпочтениях к
изображениям не сопоставимы напрямую с LIBERO-PRO SR. Разбор результатов,
условий и ограничений каждой работы: [PAPER_REVIEW.md](PAPER_REVIEW.md).

## 2. Как искать такие исследования

### 2.1. Искать по механизму, а не по названию модели

| Наша проблема | Запросы и семейства литературы |
|---|---|
| Max-value выбирает не лучший action | `best-of-N imperfect verifier`, `reward model overoptimization`, `minimum Bayes risk reward regularization` |
| Метрика различает трудность задачи, но не кандидатов | `process advantage verifier`, `within-prompt preference`, `process reward model evaluation` |
| Модель согласованно ошибается | `semantic uncertainty`, `agent uncertainty survey`, `self-correction external feedback` |
| Нужно выбирать момент проверки | `adaptive test-time compute`, `solve detect verify`, `selective prediction` |
| Среди кандидатов нет успешного | `on-policy self correction`, `diffusion preference optimization`, `flow matching online reinforcement learning` |

Начальные точки: обзоры [test-time scaling](https://arxiv.org/abs/2503.24235),
[PRM](https://aclanthology.org/2026.acl-long.163/),
[uncertainty агентов](https://aclanthology.org/2026.acl-long.738/) и
[self-correction](https://aclanthology.org/2024.tacl-1.78/).
Затем изучались исходные методы, постановка их экспериментов, отрицательные
результаты и применимость к flow/diffusion. В подборку включены 26 PDF;
это целевой обзор, без заявления о полноте систематического поиска.

### 2.2. Критерии пригодности

1. Есть ли у метода независимый сигнал правильности, а не только self-value?
2. Улучшается ли выбор **внутри одного запроса**, а не pooled AUROC?
3. Работает ли метод при малом K, сопоставимом с нашим K4/K8?
4. Нужны ли token log-probabilities, которых наш API не предоставляет?
5. Проверены ли внешний feedback, необратимые действия и стоимость коррекции?
6. Что именно измеряли авторы: terminal correctness, proxy reward, preference,
   локализацию ошибки или качество изображений?

Точные PDF, версии и проверки находятся в [каталоге](papers.json),
[manifest загрузок](download_manifest.json) и [аудите источников](source_audit.json).
Отозванная SuperFlow исключена; причина записана в [README](README.md).

## 3. Какая у нас архитектура

### 3.1. Модель и входы

Наша базовая модель: `nvidia/Cosmos-Policy-LIBERO-Predict2-2B`.
Это video-latent diffusion / rectified-flow модель с DiT, не
авторегрессионная текстовая LLM. В текущей LIBERO-конфигурации query получает:

$$
o_t=(I_t^{\mathrm{external}},I_t^{\mathrm{wrist}},p_t),
\qquad p_t\in\mathbb R^9,
\qquad e_\ell=\mathrm{T5}(\text{инструкция}).
$$

То есть два **текущих реальных RGB-наблюдения**, proprio робота и embedding
команды. Название video model не означает, что policy получает длинный
реальный видеоролик эпизода. `Future proprio` описывает робота, не положение
тарелки или кружки.

### 3.2. Совместная генерация и декодирование

В используемом parallel planning генерируется совместный sample:

$$
(A_i,\widehat p'_i,\widehat I'_i,\widehat V_i)
=G_\theta(o_t,e_\ell,\epsilon_i),
\qquad A_i\in\mathbb R^{H\times7},\quad H=16.
$$

Для текущей раскладки latent slots имеют порядок:

```text
blank | current proprio | current wrist RGB | current external RGB |
action chunk | future proprio | future wrist RGB | future external RGB | value
```

Типичная форма выходного latent tensor: `B x 16 x 9 x 28 x 28`, где `B`
содержит samples, `16` здесь число каналов, `9` число slots. **Число каналов
16 не является action horizon 16**, совпадение чисел случайно.
Низкоразмерные action/proprio/value закодированы с повторениями значений
в latent-блоках; при извлечении копии усредняются. Value затем переводится
из нормированной шкалы в `[0,1]` и ограничивается этим интервалом.
RGB восстанавливается через VAE. Код:
[`get_action` и извлечение predictions](../../cosmos-policy/cosmos_policy/experiments/robot/cosmos_utils.py).

Основное актуальное сравнение использует K4, H16, 5 denoising steps;
P5 pilot предусматривает K8/H16. Ранние H8/requery исследования имеют
другие протоколы. Нельзя объединять их SR как одну настройку.

Отдельный последовательный вариант имеет факторизацию

$$
p(A\mid o,\ell)\,p(\widehat s'\mid o,\ell,A)\,
p(\widehat V\mid o,\ell,A,\widehat s').
$$

Он доступен, но основные текущие parallel-результаты **не** являются
полной репликацией такого авторегрессионного planning.
Физический шаг $t$, номер query $q$ и время denoising $\tau$ различны.
После выполнения первых $h\le H$ действий поступает новое реальное
наблюдение; это не ещё один denoising step.

### 3.3. Словарь аналогий

| NLP | Наш аналог | Где аналогия ломается |
|---|---|---|
| Prompt + контекст | Команда + реальные камеры/proprio | Наблюдение частичное, объект может быть закрыт |
| Candidate solution | Action chunk вместе с imagined future/value | Это совместная генерация, не независимая проверка action |
| Outcome reward model | Predicted value / обучаемый terminal critic | Высокий self-value не является физическим доказательством |
| Process verifier | Action-conditioned grasp/drop/progress heads | Корректный захват не гарантирует terminal success |
| Unit test / внешний инструмент | Фактический результат исполнения в симуляторе | На настоящем роботе нельзя бесплатно откатить действие |
| Revision | Requery, retreat, regrasp или новая policy | Исправление текста обратимо, падение предмета может быть необратимо |
| Semantic equivalence | Один объект, контакт, цель и тип исхода | Близкие action-векторы могут иметь разные физические последствия |
| Token likelihood | Плотность генеративного процесса | Среднее latent-value и denoising MSE не являются log-probability |

Многократное семплирование при фиксированном $\theta$ измеряет разнообразие
предсказаний, не автоматически epistemic uncertainty параметров.
Разброс latent-копий также не является ансамблем независимых моделей.

## 4. Что наши результаты уже говорят об этой аналогии

Это сохранённые результаты, не повторные запуски в рамках обзора.
Подробности и ограничения:
[общая сводка](../../experiments/RESEARCH_SYNTHESIS_AND_PUBLICATION_READINESS_20260908.md),
[valid-support consensus](../../experiments/CONSENSUS_P5_NIGHT_PROTOCOL_20260909.md).

| Проверка | Наш результат | Следствие для переноса |
|---|---|---|
| Frozen H16 ranker | Offline dense regret -43.1%; closed-loop 165/360 -> 164/360 | Хорошее локальное surrogate-ранжирование не заменяет terminal labels |
| P4b residual risk | Prediction residual -2.14%; SR 58.5% -> 56.5%; pooled failure AUROC 0.650, within-pool 0.509 | Предсказуемость и сложность состояния не равны качеству выбора action |
| OSC medoid, valid199 | Macro-SR 54.09% против max-value 54.77%; разница -0.68 п.п., CI [-3.33; +1.99] | Consensus пока не дал подтверждённого превосходства |
| Shared-prefix feedback | 46/100 -> 64/100; +18 п.п., CI [+4; +32] | Реальное наблюдение полезно в конкретной Object task0 конфигурации |
| P3c RGB regrasp | 13/40 -> 24/40; +27.5 п.п., CI [+12.5; +42.5] | Восстановление захвата работает на новых init восьми выбранных Position cells |
| P3e routing против full regrasp | 53/75 -> 55/75; 2 rescue / 0 harm; p=0.5 | Большая часть эффекта системы уже есть в recovery, вклад router предварительный |

Это мотивирует grounded verification и correction, но не доказывает,
что наши неудачи вызваны именно reward hacking. Для этого нужно показать
расхождение proxy/реального результата при контролируемом усилении отбора.
Такой механизм рассматривается в
[Reward Model Overoptimization](https://proceedings.mlr.press/v202/gao23h.html)
и [Imperfect Verifiers](https://arxiv.org/abs/2411.17501).

Положительные recovery-результаты ограничены изученными распределениями.
`t=72` оставляем фиксированным контролем, не универсальной фазой ошибки:
[решение по timing](../../experiments/RECOVERY_TIMING_DECISION_20260909.md).

## 5. Формулы и адаптация методов

Ниже формулы с физическими состояниями, action chunks и нашими метриками
являются **предлагаемой адаптацией**, если явно не сказано обратное.

### 5.1. MBR-BoN: опубликованный аналог value + consensus

[MBR-BoN, M11](https://aclanthology.org/2025.naacl-long.472/) объединяет
reward и среднюю utility относительно других samples. Наш перенос:

$$
i^*=\arg\max_i\left[
\widehat V_i+\frac{\beta}{K}\sum_{j=1}^{K}u(\psi_i,\psi_j)
\right].
$$

При $u=-d$ получаем value минус среднее расстояние до других кандидатов.
При $\beta=0$ это max-value; при доминирующем штрафе и отсутствии ties
приближаемся к medoid. Это **не новая общая формула** нашего исследования.
Включение/исключение диагонали меняет масштаб коэффициента и должно
фиксироваться в реализации.

Простой контролируемый distance для действий:

$$
d_A(A_i,A_j)=\sum_{r=0}^{H-1}w_r
\sqrt{\frac1{7}\sum_{d=1}^{7}
\left(\frac{A_{i,r,d}-A_{j,r,d}}{s_d+\epsilon}\right)^2},
\qquad \sum_r w_r=1.
$$

$s_d$ фиксируется по train/development, а не по тесту. Uniform $w_r=1/H$
проверяет весь чанк; отдельный заранее заданный prefix-вариант проверяет
ближайшие действия. Gripper и пространственные компоненты нельзя незаметно
смешивать в разных единицах.

В [structure-conditional MBR, M10](https://aclanthology.org/2025.emnlp-main.1616/)
важно учитывать структуру вариантов. Наш кандидат на улучшение: utility
по task-critical признакам $\psi_i$ (целевой объект, захват, контакт, достижение
цели), а не только по raw action distance. Однако правильный редкий grasp
может оказаться вне большинства. «Самый частый» не означает «самый успешный».
Max-value у нас также не является MAP по вероятности генерации.

### 5.2. PRM/PAV: оценивать последствия конкретного действия

[PAV, M2](https://arxiv.org/abs/2410.08146) связывает process reward с
advantage относительно продолжения решения. Для робототехники фиксируем
политику продолжения $\pi_c$ и определяем:

$$
Q^{\pi_c}(b_t,A_i)=
\mathbb E[Y\mid b_t,\operatorname{do}(A_i),\pi_c],
\qquad
\widehat Q_i=\frac1R\sum_{r=1}^{R}Y_{i,r}.
$$

$b_t$ обозначает доступную историю наблюдений, $Y$ terminal success;
все кандидаты исполняются из одного exact simulator snapshot при сборе
данных. Повторные continuation seeds дают шумовую оценку исхода одного action,
а не дополнительные независимые состояния.

Для сравнения внутри pool можно центрировать targets:

$$
\widehat A_i=\widehat Q_i-\frac1K\sum_j\widehat Q_j.
$$

**Вычитание одинакового baseline само по себе не меняет argmax!** Поэтому
ещё один `value - mean(value)` не является новым planner. В PAV важны
обучение и выбор prover/continuation policy; у нас terminal ridge critic
уже использовал advantage. Новая проверка должна менять информацию и
targets, а не переименовывать старое центрирование.

Предлагаемый input отдельного verifier:

$$
f_\phi(b_t,A_i,\widehat I'_i,\widehat p'_i,z_i)
\longrightarrow
(\widehat Q_i,\widehat p_{\mathrm{miss},i},
\widehat p_{\mathrm{drop},i},\widehat p_{\mathrm{wrong},i}).
$$

$z_i$ содержит доступные до исполнения latent/action признаки. Нужны
реальные task-critical RGB признаки; predicted proprio не сообщает,
удерживается ли тарелка. Предсказанное будущее допустимо во входе, но
фактическое будущее того же action используется **только как label**.

Простой baseline обучения: terminal BCE. Более целевой вариант:
pairwise logistic loss только между кандидатами одного состояния:

$$
\mathcal L_{\mathrm{pair}}=
-\sum_{s}\sum_{(i,j)\in\mathcal P_s}w_{ij}
\log\sigma\big(f_\phi(s,A_i)-f_\phi(s,A_j)\big),
$$

где $\mathcal P_s$ содержит пары с подтверждённым на development преимуществом
кандидата $i$. При одном стохастическом terminal label это шумные предпочтения,
а не известный истинный порядок. Нужны repeats/soft labels и проверка
чувствительности, а не удаление всех неудобных outcomes.

Для осторожного вмешательства относительно max-value кандидата $i_0$:

$$
\widehat\Delta_i=\widehat Q_i-\widehat Q_{i_0},
\quad L_i=\widehat\Delta_i-\lambda\widehat\sigma_{\Delta,i},
\quad
i^*=\begin{cases}
\arg\max_i L_i,&\max_i L_i>\delta\text{ и выполнены ограничения},\\
i_0,&\text{иначе}.
\end{cases}
$$

Здесь $\widehat\sigma_{\Delta,i}$ относится к оценке **разницы terminal outcome**
(например, grouped bootstrap ensemble), не к копиям latent-value.
Без отдельной калибровки $L_i$ только консервативный score, не гарантированная
нижняя доверительная граница. Если все кандидаты небезопасны, нужен
отдельный допустимый fallback; возврат к $i_0$ не гарантирует безопасность.

### 5.3. Semantic uncertainty вместо любого разброса

В [Semantic Uncertainty, M7](https://arxiv.org/abs/2302.09664) разные тексты
объединяются по смыслу. Наша адаптация объединяет samples по гипотезе
физического результата, например `grasp target / miss / wrong object / drop`:

$$
\widehat p_c=\frac{n_c}{K},\qquad
U_{\mathrm{outcome}}=-\sum_c\widehat p_c\log\widehat p_c.
$$

Это эмпирическая entropy по частотам, **не точная likelihood-weighted entropy
из NLP**. Кластеризатор нужно независимо проверить: label «захват» на
воображаемом кадре может быть галлюцинацией. K4 даёт очень грубую оценку;
уверенно одинаковые неправильные predictions дадут низкую entropy.

Есть два разных эксперимента:

- Разные $A_i$: насколько различаются предложенные стратегии/исходы в state.
- Один фиксированный $A_i$, разные samples будущего: насколько ненадёжен
  **этот action** по предсказанию динамики.

Второй требует conditional future generation с зафиксированным action.
Обычный joint pool меняет и action, и imagined future, поэтому не измеряет
чистую transition uncertainty одного кандидата. Новые вызовы учитываются
в compute budget; фиксированный action должен сохраняться точно.

После проверки полезности teacher можно обучить дешёвый probe на DiT features:

$$
\widehat U=g_\phi(z_t),\qquad
\mathcal L_{\mathrm{probe}}=(\widehat U-U_{\mathrm{teacher}})^2.
$$

Это предлагаемый regression-вариант; оригинальная работа
[Semantic Entropy Probes, M8](https://arxiv.org/abs/2406.15927) также использует
бинаризацию high/low entropy. Probe экономит samples, но не превращает
бесполезный teacher в хороший детектор fail.

Перекрытие старого и нового action chunk тоже можно проверять в пространстве
исходов/контактов, не только Euclidean distance. Новое реальное наблюдение
может закономерно изменить правильный план; отсутствие расхождения не
гарантирует отсутствие ошибки.

### 5.4. Detect -> verify -> correct с реальным feedback

Внешняя проверка и обученная коррекция представлены в
[CRITIC](https://arxiv.org/abs/2305.11738),
[SCoRe](https://arxiv.org/abs/2409.12917) и
[Solve-Detect-Verify](https://aclanthology.org/2026.acl-long.2190/).
Для нас это не просьба к той же модели «подумать ещё раз», а цепочка:

```text
real RGB/proprio -> event detector -> grounded verifier ->
continue / shorter execution / retreat / regrasp -> new real observation
```

Предлагаемый detector оценивает событие в ближайшем физическом интервале:

$$
r_t=P(\text{miss/drop/no-progress в }[t,t+h]\mid b_t,A_t).
$$

Сам по себе высокий $r_t$ ещё не говорит, какое вмешательство полезно.
Для выбора $u$ нужна его ожидаемая **добавочная** полезность:

$$
u^*=\arg\max_u\left[
\widehat Q(b_t,u)-\widehat Q(b_t,\mathrm{continue})
-\eta\,\mathrm{cost}(u)\right].
$$

Старые CATE/VoF модели уже проверяли близкий принцип и плохо переносились.
Новая гипотеза относится к распознаванию физических событий и обученной
recovery policy, не к повтору такого же ridge fit. `t=72`, random-time и
периодический requery остаются отдельными controls.

Для on-policy обучения коррекции можно проверять reward:

$$
R_{\mathrm{corr}}=Y_u+
\alpha\,\mathbf1[Y_0=0,Y_u=1]
-\gamma\,\mathbf1[Y_0=1,Y_u=0]
-\eta\,\mathrm{cost}(u).
$$

Это **наша проектная формула**, не формула SCoRe. $Y_0$ и $Y_u$ требуют
counterfactual branches из одного snapshot при обучении/оценке в симуляторе.
Они недоступны одновременно на одном реальном онлайн-эпизоде. Контроли
correct-to-correct нужны, чтобы коррекция не портила уже успешные случаи.

### 5.5. DPO и Flow-GRPO: если нужно менять предложения

Оригинальный [DPO](https://arxiv.org/abs/2305.18290) обучает policy на
предпочтениях, а не только reranker. Его типичная запись:

$$
\mathcal L_{\mathrm{DPO}}=-\log\sigma\left[
\beta\left(
\log\frac{\pi_\theta(y^+\mid x)}{\pi_{\mathrm{ref}}(y^+\mid x)}
-\log\frac{\pi_\theta(y^-\mid x)}{\pi_{\mathrm{ref}}(y^-\mid x)}
\right)\right].
$$

Нельзя подставить вместо log-policy наш clipped value. Для Cosmos нужны
likelihood/variational surrogate генеративного процесса. Мосты:
[Diffusion-DPO](https://arxiv.org/abs/2311.12908),
[DDPO](https://arxiv.org/abs/2305.13301),
[Flow-GRPO](https://arxiv.org/abs/2505.05470).

Для Flow-GRPO существенны group reward и отношение вероятностей
**стохастических переходов генерации**:

$$
\widehat A_i=\frac{R_i-\overline R}{\operatorname{std}(R)+\epsilon},
\qquad
\rho_{i,\tau}=\frac{
p_\theta(z_{\tau-1}\mid z_\tau,o)}{
p_{\mathrm{old}}(z_{\tau-1}\mid z_\tau,o)}.
$$

Это не отношение значений value и не вероятность физического перехода
робота. Авторы используют ODE-to-SDE преобразование; его условия и
дискретизацию надо адаптировать к conditional joint latent Cosmos.
Детерминированный ODE sampler со случайным initial noise сам по себе не
даёт нужную transition density для PPO/GRPO.

Для нас $R_i$ должен опираться на **фактически исполненные** действия,
terminal успех и отдельно заданные safety costs. Если оптимизировать только
собственный imagined value, модель может улучшать картинку/оценку без успеха
робота. При all-fail pools бинарный reward даёт нулевое относительное
преимущество: нужны успешные recovery proposals, экспертные данные или
проверенные промежуточные rewards.

Переобучение генератора может нарушить future prediction. Поэтому отдельная
ablation должна сравнить action-only адаптер и joint адаптацию с сохранением
обучения на реальных transition targets. Это пока исследовательская идея,
не готовая совместимая реализация Flow-GRPO для нашего checkpoint.

## 6. Что уже делали, что планировали, что действительно добавляется

Здесь используются текущие P-обозначения из раздела `Current decision queue`
[roadmap](../../experiments/RESEARCH_ROADMAP_20260820.md), а не одноимённые
исторические ветки в старых протоколах.

| Семейство | Наш статус | Что добавляет подборка |
|---|---|---|
| Best-of-N + uncertainty/consensus | Делали многократно; P4c и OSC, reference-очередь | MBR-BoN как прямой литературный baseline; структура utility вместо нового coefficient sweep |
| Process/advantage verifier | Terminal ridge уже был; task-critical P5 запланирован | Явно разделить local event / continuation success; проверить prover dependence и task-critical representation |
| Adaptive compute / difficulty routing | P0 положительный локальный, P1/P2 transfer отрицательные | Не повторять difficulty-only; проверять пользу конкретной проверки при matched compute |
| Grounded correction | P3/P3b/P3c сильная узкая ветка; P3d/P3e ограничены | Event-trigger и on-policy learned correction, correct-to-correct controls |
| Ensemble/residual uncertainty | P4/P4b закрыты в проверенных формулировках | Outcome-semantic teacher и его probe отличаются от прежнего residual/JRD |
| Fixed-action future tail risk | Близко к запланированному P6 | Явно отделить action diversity от conditional dynamics uncertainty |
| Constraints / abstention | P7 запланирован | Калибровать отказ/проверку; не обещать OOD guarantee из conformal на ID |
| Preference/RL обновление Cosmos | Не реализовано в рассмотренной очереди | Flow-specific обучение самого proposer, только после grounded labels и support audit |

Уже наличие PAV, MBR-BoN и SCoRe означает, что формулировки
«мы первые используем uncertainty/advantage/self-correction» недостаточны.
Потенциальная новая работа: **action-conditioned проверка task-critical
физического исхода для joint action/future/value flow-модели, с отделением
proposal failure, ranking failure и пользы нового реального наблюдения**.
Её новизну и эффективность ещё нужно установить экспериментально.

## 7. План проверок и критерии остановки

### E0. Сначала аудит доступной возможности, без новых full rollouts

Использовать сохранённые exact-state pools и текущий P5 pilot после его
завершения. Не считать очередь завершённой по этому обзору: текущий статус
сервера здесь не проверялся. Существующий
[night protocol](../../experiments/CONSENSUS_P5_NIGHT_PROTOCOL_20260909.md)
не меняется.

Для фиксированной sampled реализации terminal branches:

$$
O_K(s)=\max_{i\le K}Y_i,\quad
B_K(s)=Y_{\arg\max_{i\le K}\widehat V_i},\quad
G_K(s)=O_K(s)-B_K(s).
$$

$O_K$ является oracle **данного sampled pool и continuation**, не верхней
границей всех достижимых стратегий. Сравнивать вложенные K4/K8 одного pool,
а не разные seeds под видом эффекта K.

- `all-pass`: мало информации о ранжировании, полезно для оценки harm.
- `mixed`: данные для выбора между хорошим и плохим кандидатом.
- `all-fail`: сначала менять proposal/recovery; никакой selector не выберет
  успешный элемент из этого реализованного pool.
- `mixed`, но max-value уже успешен: oracle opportunity для rescue отсутствует,
  хотя тест на harm остаётся важен.

На этих же development pools: max-value, raw/OSC medoid, MBR-BoN с малой
заранее заданной сеткой коэффициентов и uniform random. Дедуплицировать
математически эквивалентные ранее выполненные варианты. Не переобучать
коэффициенты на уже открытом valid199 test.

**Gate:** сначала существующие replay/opportunity gates P5 (в том числе
не менее восьми mixed pools, трёх task IDs и двух факторов). Это разрешение
на расширение development, не доказательство достаточной выборки для fit.
Если opportunity нет, переходить к новым proposals, а не к дорогому ranker.

### E1. Task-critical grounded P5

Единица данных: exact snapshot + команда + RGB/proprio + K candidates +
повторные реальные continuation outcomes. Сохранять task/init/seed,
идентификатор pool, query, время, горизонты, checkpoint и sampler config.
Queries одного task/init остаются в одной группе при split.

Предлагаемые сравнения при одном и том же наборе candidates:

| Вариант | Входы | Targets |
|---|---|---|
| Старый ridge control | Value, action summaries, latent uncertainty | Прежний target без переименования |
| Terminal-only head | Те же базовые признаки | Реальный terminal success |
| Grounded head | + target-conditioned текущие RGB/contact признаки | Terminal success |
| Task-critical multi-head | + predicted future признаки | Terminal + miss/drop/wrong-object events |
| Pairwise multi-head | Те же входы, фиксированная ёмкость | Те же labels + within-state pairwise loss |

Начать с малых heads на frozen features; полный DiT не обучать одновременно
с изменением targets. Oracle simulator object poses допустимы как labels и
отдельный privileged upper bound, **не** как скрытый input deployable модели.

Пилотный контроль шума: повторить одни и те же actions с несколькими
continuation seeds на заранее выбранном поднаборе, не только на ошибках
лучшего ranker. Если сравниваются разные continuation policies, кандидаты
и стартовые snapshots фиксированы; меняется явно только $\pi_c$.

Не смешивать label «предмет упал в первом chunk» с label «не завершил задачу
к 280 шагам». Отдельно размечать recovery после ошибки и время первой ошибки;
на development проверить proxy labels по видео. Это отвечает предупреждениям
о process-label ошибках в [M4](https://aclanthology.org/2025.findings-acl.547/).

**Gate:** group-disjoint within-pool advantage над max-value с интервалом,
разумная calibration, положительный terminal selection gain и отсутствие
систематического harm. Только затем один frozen closed-loop test.
Новая head не проходит gate только благодаря pooled AUROC.

### E2. Event-triggered verification и correction

Сравнить на одинаковых task/init/seed конфигурациях: continue, fixed-time
control, random-time control с тем же числом вмешательств, periodic requery,
event-triggered requery, event-triggered retreat и full regrasp.

Момент проверки выбирается только из доступных real observations. Если
для проверки требуется исполнить h=8 вместо16, это отдельный controller
с иной стоимостью и latency, не бесплатный verifier H16 baseline.
Сначала подобрать detector на development; затем держать порог, бюджет
вмешательств и recovery primitives неизменными на новых целых cells.

**Gate:** дополнительный terminal gain относительно сильного full-regrasp
control, либо тот же SR при меньшей стоимости/меньшем harm. Отдельно оценивать
предотвращение ошибки и восстановление после неё. Timing-transfer не
объяснять автоматически, пока не пройдены fixed/random/phase controls.

### E3. Семантическая uncertainty и её дешёвый probe

Сначала проверить teacher на сохранённых candidates: raw action std,
value std/range, copy std, outcome clusters. Затем небольшой fixed-action
future-resampling тест отделит diversity actions от uncertainty transition.
В рамках равного общего WM budget сравнивать, например, больше actions с
одним future против меньшего числа actions с повторными futures.

**Gate:** teacher даёт информацию о task-critical fail до события и/или
улучшает within-pool выбор сверх terminal score. Только после этого обучать
probe. Проверять качество и p95 latency; высокая корреляция probe с teacher
не заменяет terminal SR.

### E4. Адаптивный бюджет, только после проверки E1/E2

Выбирать дополнительный sample / requery / проверку / recovery по ожидаемой
добавочной полезности. Не отождествлять трудную задачу с задачей, где полезно
потратить больше compute. Сравнение: fixed K, fixed periodic feedback,
uncertainty-only router и benefit-aware router при matched budget.

В работе [M1](https://arxiv.org/abs/2408.03314) оценка difficulty может сама
стоить много samples. У нас измеряется **полная** стоимость её получения;
не использовать скрытый pass@K из terminal outcomes как online input.

### E5. Обучение proposer, если остаётся all-fail bottleneck

Сначала получить ground-truth preference пары через исполнение candidates,
recovery или эксперта. Сравнить frozen proposer + verifier, лёгкий
action-conditioned адаптер, затем flow-specific preference/RL адаптацию.
Результат должен увеличивать частоту хороших proposals и closed-loop SR,
а не только predicted value или качество imagined images.

**Gate:** сперва sampler/likelihood integration test и отсутствие деградации
ID policy / реального future prediction. Полное RL обучение 2B модели не
является первым дешёвым экспериментом этого плана.

## 8. Общий протокол честного сравнения

- Основной benchmark: согласованный LIBERO-PRO Object с раздельными
  Environment, Position, Object perturbations. Публиковать SR каждого фактора
  и macro-SR; не подменять его удобными boundary cases из development.
- Отдельный стандартный LIBERO ID контроль проверяет деградацию. Safety
  события можно логировать в PRO, но это не превращает PRO в официальный
  LIBERO-Safety. Отдельный safety benchmark требует собственного протокола.
- Сохранять K, H, реально выполняемый h, denoising steps, seed mapping,
  task/init assets и timeout. Ошибка benchmark asset не является policy fail.
- Development выбирает не больше одного-двух frozen кандидатов для нового
  confirmatory теста. Все старые открытые holdouts считаются известными данными.
- Held-out task/perturbation cells проверяют перенос; новые seeds старой cell
  проверяют только воспроизводимость внутри неё. Отчёты должны разделять их.
- Primary outcome: paired terminal SR gain; дополнительно rescue/harm,
  drop/wrong-object, event lead time, intervention rate, calibration/Brier,
  within-pool concordance и regret. All-tie pools не входят в concordance,
  но остаются в итоговом SR и отчёте о coverage.
- AUROC/AUPRC раннего detector считать до первой ошибки, с фиксированным
  горизонтом прогноза и label времени. Prediction error после chunk не
  использовать как предсказание ошибки, уже случившейся внутри этого chunk.
- Интервалы кластеризовать по task/init, а для переноса также показывать
  чувствительность по целым cells/tasks; не считать K actions, R suffix seeds
  и последовательные queries независимыми экспериментальными единицами.
- Публиковать WM calls, denoising/decoder/verifier costs, latency p50/p95,
  simulator steps и GPU-hours. Equal-K не означает equal-compute при разном
  числе условных future/value вызовов.
- Размер confirmatory выборки определяется по development discordance и
  минимальному практически полезному SR gain до открытия теста; не останавливать
  сбор, как только p-value впервые оказался удобным.

[Conformal Language Modeling](https://arxiv.org/abs/2306.10193) полезен для
калибровки набора/отказа. Но гарантия наличия допустимого кандидата в наборе
не гарантирует правильного выбора одного action, а calibration на ID не
даёт автоматической coverage на произвольном OOD.

## 9. Итоговое решение

**Не начинать ещё один большой sweep `value - lambda * uncertainty`.**
Ближайший полезный шаг: закончить текущий opportunity audit, затем проверить
task-critical grounded P5 с terminal и event labels. Параллельная перспективная
ветка после отдельного freeze: event-conditioned correction с сильными
fixed-time/full-regrasp controls.

MBR-BoN нужен как литературно корректный baseline; semantic probes как
возможный способ удешевить полезный verifier; Flow-GRPO как более позднее
средство исправить распределение proposals. Такой порядок проверяет
разные причины fail и использует уже накопленные данные, вместо повторения
закрытых отрицательных гипотез под новыми названиями.

Существующая очередь и frozen-протоколы этим обзором **не изменены**.

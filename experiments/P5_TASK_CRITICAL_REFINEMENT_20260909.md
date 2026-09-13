# P5: уточнение метода до следующего обучающего эксперимента

9 сентября 2026. Статус: **проект следующего протокола**, не новый запущенный
метод. Текущие `p5_boundary_candidates_20260909` config/collector/freeze
не изменяются. [Приоритеты и live audit](RESEARCH_PRIORITIES_20260909.md).

## 1. Задача и гипотеза

При одинаковом наблюдении $b$ Cosmos предлагает $K$ action chunks и совместные
future/value predictions. Нужно выбрать candidate с более высоким
**фактическим terminal success**, а не минимальной ошибкой предсказания
всей картинки. Гипотеза: различия в состоянии target/contact объясняют
внутри-pool outcome лучше, чем общая трудность состояния и latent std.

Основное сравнение сохраняет H16, joint parallel generation, denoise=5,
ограничение 280 environment steps. K4 является дешёвым baseline; K8 pilot
позволяет вложенный анализ. Shorter-horizon/recovery controller сравнивается
отдельно: изменение частоты real feedback нельзя приписать новой head.

## 2. Что уже сохраняется и чего нет

Код проверен в
[`collect_counterfactual_feedback.py`](../scripts/collect_counterfactual_feedback.py),
[`analyze_p5_boundary_pilot.py`](../scripts/analyze_p5_boundary_pilot.py),
[`terminal_grounded_critic.py`](../scripts/terminal_grounded_critic.py).

| Артефакт | Уже предусмотрено | Ограничение |
|---|---|---|
| NPZ snapshot | Runtime state, current external/wrist RGB, proprio | Пригодно для replay; не означает независимого нового episode |
| Action pool | Actions, values, sampling seeds | Нужны SHA при повторном исполнении, actions не пересэмплировать |
| Predicted future | Images/wrist/proprio при наличии | Проверять ключи и finite/непустые arrays, не считать отсутствующее нулями |
| Фактический endpoint | State/RGB/proprio каждого candidate | Разрешён как label/evaluation, запрещён как online feature того же candidate |
| Terminal labels | Success, failure type, drop/wrong-object/safety summaries | Одна continuation realization; это не точная probability of success |
| Локальные summaries | Progress, lift, contact/drop proxies | Эвристические labels; не готовая ручная разметка miss-grasp |
| Event times | Tracker сохраняет drop/wrong-object timestamps в terminal summary | Generic failure_event_t может быть timeout; полный покадровый trace не гарантирован |
| Audit | Strict replay и finite прежних scalar critic features | Не проверяет качество task-critical representation или точность event labels |
| Representation | Старые action/value/latent/proprio features | Нет готовой обученной target-contact head/semantic entropy probe |

Из кода `SafetySignalTracker`: при отсутствии физического event failed
episode может иметь `failure_event_t=final_t`. Эту величину нельзя использовать
как доказанный момент падения. Для pre-failure анализа брать проверенный
`target_drop_candidate_t`/другой конкретный event и валидировать proxy.

## 3. Два разных targets

Terminal target зависит от продолжения:

$$
Q^{\pi_c}(b,A)=\mathbb E[Y\mid b,\operatorname{do}(A),\pi_c].
$$

Local event targets относятся к физическому интервалу исполнения:

$$
E_h=(\mathrm{target\ grasp},\mathrm{miss},\mathrm{drop},
\mathrm{wrong\ object},\mathrm{goal\ progress})_{[t,t+h]}.
$$

Успешный episode может иметь ранний drop и последующий recovery.
Неуспешный episode может корректно выполнить текущий chunk и ошибиться позже.
Поэтому нельзя размечать каждый action failed episode как ошибочный.
Значение `value` модели также не является автоматически вероятностью любого
из этих локальных событий.

Текущий pilot использует одну K1/H16 continuation с общей seed schedule
между ветвями: `rollout_seed + 10_000_000 + absolute_t*1000 + offset`.
Для noise audit дополнительно менять suffix seed независимо от proposal
noise, сохраняя actions. В experiment card записывать $\pi_c$, число repeats
и соответствие seeds; разные продолжения не сливать в один target без метки.

## 4. Предлагаемая head

$$
x_i=[\phi_{\mathrm{RGB}}(I_t,\ell),\ p_t,\ \psi(A_i),\
\phi_{\mathrm{target}}(\widehat I'_i,\ell),\ \widehat p'_i,\ \widehat V_i,\ u_i].
$$

$\phi_{\mathrm{RGB}}$ использует текущие доступные камеры и команду;
$\psi$ описывает полный chunk и его prefix; $u_i$ содержит candidate-specific
latent consistency, а не один общий scalar uncertainty на всё состояние.
Target-conditioned features могут включать локализацию, относительное
положение gripper/target, признаки предполагаемого контакта. Применимость
существующего RGB-localizer к новым объектам и **predicted** изображениям
не доказана; проверить её отдельно. Frozen CLIP global embedding уже не
дал нужного переноса и не считается достаточным новым представлением.

$$
f_\phi(x_i)\to(\widehat Q_i,\widehat E_{h,i}).
$$

Контроли одной ёмкости:

1. State-only: одна оценка на все candidates; выявляет task difficulty.
2. Старые scalar features + terminal BCE: честный baseline.
3. Scalar + target/contact representation, terminal BCE.
4. Те же features + локальные event losses и within-state pairwise objective.
5. Shuffled candidate/action association: проверка, действительно ли модель
   использует соответствие action/future, а не только состояние.

Shuffle выполняется при диагностике внутри pool с явным seed и без смешивания
train/test. Нельзя разрушать target label в основном train и затем сравнивать
это как обычный честный baseline без пояснения.

## 5. Обучение и выбор

Пример общей цели, коэффициенты выбираются только на development:

$$
\mathcal L=\mathcal L_{\mathrm{terminal\ BCE}}+
\alpha\mathcal L_{\mathrm{local\ events}}+
\beta\mathcal L_{\mathrm{within\ pool}}.
$$

Local heads обучаются с mask для отсутствующих/невалидных labels. Ошибка
label не превращается в отрицательный класс. Для pairwise objective:

$$
\mathcal L_{\mathrm{within\ pool}}
=-\sum_s\sum_{(i,j)\in\mathcal P_s}
w_{ij}\log\sigma(f_\phi(x_i)-f_\phi(x_j)).
$$

$\mathcal P_s$ задаёт предпочтения terminal исхода внутри одного exact-state
pool. При noisy repeats использовать soft preferences/веса; не считать одну
случайную разницу истинным детерминированным порядком.

Первый deployment-control: $i^*=\arg\max_i\widehat Q_i$.
Второй возможный вариант допускает switch только при достаточной
предсказанной добавочной полезности к max-value candidate $i_0$:

$$
\widehat\Delta_i=\widehat Q_i-\widehat Q_{i_0},\qquad
S_i=\widehat\Delta_i-\lambda\widehat\sigma_{\Delta,i}.
$$

Это кандидат на ablation, не обязательное добавление новых гиперпараметров
в первый тест. Общая константа $V(s)$ сама ranking не меняет. Ensemble std
не является гарантированной confidence bound без калибровки. Thresholds
и допустимый fallback фиксируются до prospective rollouts.

Методологическая основа: [PAV](https://arxiv.org/abs/2410.08146),
[PRM Lessons](https://aclanthology.org/2025.findings-acl.547/).
Старый terminal critic уже имел advantage/ensemble; новая гипотеза относится
к task-critical информации и реальным targets, не к новизне этих формул.

## 6. Gates: чего недостаточно в нынешнем пилоте

Исходный `analyze_p5_boundary_pilot.py` оставляем воспроизводимым.
После него отдельный development-аудит должен проверить:

- **Rescue opportunity, не только mixed:** есть pools, где max-value failed,
  а другой сохранённый candidate succeeded. Учитывать количество целых групп
  и task IDs, а не лишь число pairwise comparisons.
- **Task support:** выгода не полностью определяется двумя известными tasks.
  Уже найденные Object task0 / Environment task3 пригодны для проверки
  признаков, не для подтверждения межзадачного переноса.
- **Phase support:** q0/q3 представлены раздельно; отсутствие signal в раннем
  query не опровергает contact-phase head. Расширение фаз только новым protocol.
- **Continuation noise:** preference не исчезает полностью при смене suffix
  seeds. Общая seed schedule первого pilot не заменяет такую проверку.
- **Feature readiness:** current/predicted RGB и task conditioning доступны
  для всех групп; simulator endpoint features исключены из online matrix.
- **Label readiness:** проверить хотя бы 24 stratified development примера
  contact/drop/release/no-event по доступным изображениям или точному replay.
  Endpoint одной картинки недостаточно для времени события; спорные labels
  помечать unknown. Это label audit, не новые 24 независимых rollouts.
- **Selection utility:** pooled AUROC не gate. Grouped OOF selection gain,
  rescue/harm, calibration и uncertainty интервала считаются отдельно.

Не использовать открытые test outcomes для настройки и затем называть этот
же набор holdout. Candidate pairs, q0/q3 и repeats одного task/init остаются
в одной split group. Группа должна объединять также варианты среды одного
init при проверке заявленного transfer; конкретные split axes фиксируются.

Пока task-disjoint fold имеет слишком мало mixed/rescuable states, его
результат не позволяет сильных статистических выводов. Нужен bounded сбор
новых **целых cells**, а не искусственное увеличение числа pairwise строк.

## 7. Ограниченное расширение после audit

Приоритет использования существующих данных: Environment task3 и Object
task0, плюс остальные states как all-pass/all-fail/harm controls. Для нового
сбора проверять Environment и Object tasks, отличные от уже информативных
двух; Position добавлять для ranking только если новый K8 pilot покажет
доступное улучшение. Для all-fail Position нужна ветка новых proposals/recovery.

Один возможный development batch: **4 заранее выбранные cells x 2 init x
2 query/phase x K4 = 64 terminal branches**, с заранее фиксированными seeds.
Task/init assets и split проверяются до запуска. ID cells выбираются из
существующего screening, не в этом документе задним числом по новым outcomes.
Это upper budget на расширение, не автоматическая команда запуска.

При сомнении в labels вместо расширения сначала **48 suffix-repeat branches**
из плана приоритетов. Оба больших направления не запускаются одновременно
без вывода первого audit. Уже собранные pools и признаки переиспользуются.

## 8. Научный итог и stop rule

Достаточное основание для нового closed-loop screen: frozen candidate head
даёт устойчивый terminal selection gain на group-disjoint development,
использует action-dependent информацию, имеет приемлемый harm и проходит
replay/label audit. Один-единственный улучшенный pool не является основанием
для массового запуска.

Если задача определяется трудностью state, но кандидаты внутри state
неразличимы, оставить detector как diagnostic. Если нет успешных proposals,
закрыть ranking для этого support и перейти к recovery/proposer. Если
улучшение только на известных двух tasks, честно оставить narrow result,
не масштабировать claim до всего LIBERO-PRO.

Эксперименты Flow-GRPO/DPO, длинный autoregressive tree search и новый
широкий uncertainty sweep не являются ближайшими шагами этого P5.

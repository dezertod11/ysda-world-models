# Observation Contract: информация перед recovery

11 сентября 2026. Campaign `observation_contract_20260911`.
Протокол фиксируется до новых GPU-результатов. Статус запуска отдельно в
[акте проверки](campaigns/observation_contract_20260911/LAUNCH_VERIFIED.md).

## Задача и выбор архитектуры

[Последняя серия](TIMING_ELIGIBILITY_RESULTS_20260911.md): immediate recovery
76/96, continue 63/96, delayed fresh и checked 74/96. Checked не изменил
ни одного исхода относительно fresh. Все 17 общих failures лежали вне
исходного trigger. Поэтому сейчас проверяем архитектуру получения наблюдения
и допуска к recovery, а не ещё один sweep задержки или коэффициентов value.
P5 scorer пока не показал надёжного переноса; широкое обучение P5/P6 отложено.

[Offline-аудит](campaigns/observation_contract_20260911/prior_audit/README.md)
сравнивает прежнюю RGB-локализацию с истинным body origin цели: медианная
ошибка на x0.2/task9 около 0.366 м, на y0.2/task2 около 0.558 м.
Это диагностические ошибки координат, не доказательство ошибки точки захвата.
Старый workspace описывает область калибровочных данных: даже истинная
позиция салатной заправки в y0.2 выходит за неё. Он не равен физической
достижимости робота. Сам по себе oracle gate ещё не означает oracle success.

Гипотезы:
1. Небольшое движение наблюдения без смены команды захвата может уменьшить
   окклюзию и открыть полезное recovery в исходно ненадёжных состояниях.
2. Часть вреда наблюдения с разжатием связана со сменой gripper-команды,
   а не с самой новой локализацией. Нужны open/preserve и only/regrasp controls.
3. Если oracle существенно лучше learned, приоритет имеет зрение/калибровка;
   если оба oracle не помогают, надо менять recovery или момент его вызова.

Связь со статьями: [CRITIC](https://arxiv.org/abs/2305.11738) показывает
коррекцию LLM через внешнюю обратную связь; аналогия здесь только на уровне
получения независимого сигнала перед исправлением. Это не перенос его
бенчмарка или численных результатов. [Active Perception and Representation
for Robotic Manipulation](https://arxiv.org/abs/2003.06734) рассматривает
активное восприятие для манипуляции. Наша фиксированная трёхшаговая проба
не воспроизводит их learned viewpoint policy. Новизна и преимущество пока
не установлены; нужны положительный механизм и независимое подтверждение.

## Политика и формулы

Сохраняем frozen gate $G_t=F_t C_t W_t R_t M_t$: конечность оценок,
confidence score, calibration workspace, reach distance, miss-distance.
Все object-specific пороги и старый RGB localizer неизменны.

Допуск к наблюдению при $G_t=0$:

$$
U_t=F_t\,\mathbb{1}[\neg(C_t\land W_t\land R_t)]\,B(p_t,g_{t-1}).
$$

$B$: конечные EEF xyz и предыдущая gripper-команда, $|x|,|y|\le0.45$ м,
$z\ge0$, $z+0.08\le0.50$ м. При отказе только по miss-distance проба
не вызывается. Это ограничение движения, не collision/grasp safety guarantee.
Проба: до трёх servo steps к $p_t+(0,0,0.08)$, tolerance 0.015 м.

$$
g_{\mathrm{open}}=-1,\qquad
g_{\mathrm{preserve}}=\operatorname{clip}(a_{t-1,\mathrm{gripper}},-1,1).
$$

Preserve означает прежнюю фактическую команду: она может быть открытой!
Мы не предполагаем, что предмет удерживается, и не закрываем захват заново.
После пробы regrasp-ветви вновь получают RGB-оценку и проверяют
$G'_t=F'_t C'_t W'_t R'_t$ (без повторного miss-distance), затем выполняют
оставшийся старый primitive. Второго retreat нет. В следующих стадиях
primitive снова использует open/close; preserve относится только к пробе.
Отказ fresh gate не отменяет уже выполненные физические действия.

## Восемь ветвей

| Arm | При исходном G=1 | При G=0 | Роль |
|---|---|---|---|
| continue_h8 | Cosmos | Cosmos | Без recovery |
| physical_regrasp | Старый full primitive | Cosmos | Сильный контроль |
| refresh_open_only | Старый full primitive | При U: open-проба, затем Cosmos | Контроль движения |
| refresh_preserve_only | Старый full primitive | При U: preserve-проба, затем Cosmos | Контроль gripper |
| refresh_open_regrasp | Старый full primitive | При U: open-проба, fresh gate, recovery | Контроль recovery |
| refresh_preserve_regrasp | Старый full primitive | При U: preserve-проба, fresh gate, recovery | Primary candidate |
| oracle_calibrated | Истинные xyz, старые геометрические guards | Тот же oracle gate | Только privileged diagnostic |
| oracle_physical | Истинные xyz, расширенный workspace | Тот же oracle gate | Только privileged diagnostic |

В oracle confidence принудительно равен object-specific порогу, истинные
xyz берутся также после retreat. Calibrated сохраняет старый workspace;
physical заменяет только его на box [-.45,-.45,-.03] ... [.45,.45,.45] м,
сохраняя reach<=0.5 м и miss>=0.08 м на входе. Это не IK/collision-проверка.
Oracle нельзя называть deployable методом или включать в SR нового метода.
GT не подаётся шести обычным ветвям, но используется для offline diagnostics.

## Данные и модель

LIBERO-PRO **Position perturbations семейства Object tasks**, а не полный
официальный LIBERO-PRO benchmark и не LIBERO-Safety. Уровни x0.1/x0.2/y0.1/y0.2,
tasks 2/5/9, init 46-49. Те же 96 сохранённых nonterminal t72 prefixes:
12 cells, 48 init clusters, по два исходных prefix seeds.
Для каждого prefix два suffix seed: исходный и заранее заданный новый.
Итого **192 paired suffix cases, 1536 основных ветвей**. Это не 192 независимых
initial states; состояние переиспользуется после предыдущего анализа.

Дополнительно **24 технические ветви**: 3 prefixes с допущенным recovery,
ненадёжной локализацией/open и ненадёжной локализацией/closed. Они не входят
в основную статистику. Общий объём 1560; holdout init38-45 не открывается.

Cosmos frozen, K=4, generated action horizon=16; suffix выполняет первые8.
Prefix K4/H16 до t72. Пять denoising steps, joint/parallel action/state/value,
не авторегрессионная цепочка a->s->v. Начало suffix query5, отдельные seed
для каждого query/candidate. Максимум280 физических действий включая probe
и recovery. Все камеры и действия записываются до terminal/max_t.
Видео начинаются в t72, содержат внешнюю и wrist камеры; localizer использует
только внешнюю RGB. Это не two-view verifier и не adaptive event detector.
t72 сохранено для изоляции механизма, не объявляется универсальной точкой.

## Метрики и заранее выбранные сравнения

Primary: paired terminal SR относительно physical_regrasp, rescue/harm,
95% stratified init-cluster bootstrap CI. Независимая единица: (cell,init),
prefix/suffix seeds усредняются внутри неё. Cells имеют одинаковые веса.
Дополнительно drop/wrong-object proxies, число probes/full recoveries,
последующие отказы guards, query cost и paired видео. Safety proxies локальные,
не официальные LIBERO-Safety scores. Анализ завершается только по полным cases.

Шесть predeclared contrasts с Holm-коррекцией:
primary-physical; primary-open_regrasp; primary-preserve_only;
preserve_only-open_only; oracle_calibrated-physical;
oracle_physical-oracle_calibrated. Вторая suffix-серия показывается отдельно
как replication случайного продолжения на прежних состояниях, не new-init test.

Кандидат на будущий независимый тест: pooled delta>=5 п.п., CI lower>0,
Holm p<=.05, положительный delta в обоих suffix blocks, drop count не выше
baseline. Это только правило рекомендации, без автоматического holdout.
Oracle-выигрыш не продвигает learned primary. Не подбираем пороги по новой SR.

## Проверки и автономность

24 smoke должны пройти прежде чем откроется screen: точные старые controls
(actions, final simulator state, signals), совпадение refresh с baseline при
G=1, одинаковое probe-окончание в matched only/regrasp, seeds, GT provenance,
hashes, конечные действия, step/video accounting. После загрузки Cosmos явно
восстанавливаем seed/deterministic cuDNN даже для cached prefix.
Отдельные CPU regression tests до запуска и серверный аудит после phases.

Scheduler: только свободные GPU0-7, max7 workers, совместные GPU locks,
две case jobs одного position level на загрузку модели. Занятые карты
пропускаются, чужие процессы не завершаются. На момент подготовки свободны
0-3; 4-7 используются чужими задачами. Deadline: 8 часов от первого запуска,
но не позднее 12 сентября05:00MSK; resume не продлевает бюджет. После deadline
останавливаются только собственные workers. Один retry технического batch,
после повторной ошибки или failed replay gate очередь останавливается.
Нет автоматического продолжения исследований после этой серии.

Скрипты: `scripts/run_observation_contract.py --prepare/--launch/--status`.
Ожидаемые отчёты: `analysis/smoke/`, затем `analysis/screen/` внутри campaign.
Локальная копия статуса не live. После окончания синхронизировать результаты
и разобрать paired harms до принятия решения о следующем эксперименте.

### Размещение данных при заполненном NFS2

До запуска общий NFS2 достиг100%, передача новых файлов завершилась ENOSPC.
На NFS-home свободно около2ТБ. Campaign сохранён по каноническому пути через
symlink на `/home/jovyan/.local/share/malnev_world_model_spill/observation_contract_20260911`.
Это отдельная наша папка; исходники и окружение остаются в каноническом проекте.
Assets Position не переписываются каждым batch: проверяются SHA256 всех80
ранее подготовленных BDDL/init файлов против исходных вариантов.

Чтобы разместить исходники и ссылку, старая резервная копия
`.runtime/libero_safety/libero_t5_embeddings.pkl.backup` перенесена на тот же
свободный том, в `preserved_backups/`, и заменена ссылкой. SHA256 исходного
и перенесённого файла совпал:
`80bdb53df727afa6dd06cc088f8c4c999c2c5889ecbe7204a4fdb2eca8ca164d`.
Рабочий T5-файл не изменён. Экспериментальные результаты не удалялись.
Новый campaign не зависит от освобождения места на NFS2 для видео/логов.
